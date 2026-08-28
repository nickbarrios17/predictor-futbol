# database/sqlite.py — v2.1 (soporte Turso)
"""
Base de datos de predicciones. SQLite local por defecto; si están
definidas TURSO_DATABASE_URL / TURSO_AUTH_TOKEN usa una base Turso
(libSQL) remota en su lugar, para que el historial sobreviva a
reinicios en hosting con almacenamiento efímero (ej. Streamlit Cloud).

turso_serverless implementa DB-API 2.0 con la misma interfaz que
sqlite3 (placeholders "?", Row con acceso por nombre, lastrowid,
rowcount), asi que el resto de este archivo no necesita distinguir
entre ambos backends.

Fixes v2.0:
  Bug 1 — check_duplicates siempre retornaba has_similar=True
           cuando competition era string vacío. Corregido con
           manejo explícito de competition vacía.
  Bug 2 — save_prediction se llamaba dos veces (predictor.py + app.py).
           Eliminado de predictor.py. Solo se llama desde app.py.
  Bug 3 — el gestor de historial requería una predicción activa.
           Movido a la pestaña de Historial en app.py.
"""
import sqlite3
import json
import os
import math
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.path.join("database", "predictions.db")

TURSO_URL   = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")


def get_connection():
    if TURSO_URL:
        import turso_serverless
        conn = turso_serverless.connect(TURSO_URL, auth_token=TURSO_TOKEN)
        conn.row_factory = turso_serverless.Row
        return conn

    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at          TEXT    NOT NULL,
        model_version       TEXT    NOT NULL DEFAULT 'v2.0',
        home_team           TEXT    NOT NULL,
        away_team           TEXT    NOT NULL,
        competition         TEXT    DEFAULT '',
        season              TEXT    DEFAULT '',
        match_date          TEXT    DEFAULT '',
        venue               TEXT    DEFAULT 'neutral',
        prob_home           REAL    NOT NULL,
        prob_draw           REAL    NOT NULL,
        prob_away           REAL    NOT NULL,
        predicted_result    TEXT    NOT NULL,
        predicted_score     TEXT    DEFAULT '',
        lambda_home         REAL,
        lambda_away         REAL,
        elo_home            INTEGER,
        elo_away            INTEGER,
        over_25             REAL,
        under_25            REAL,
        btts_si             REAL,
        btts_no             REAL,
        top_scores          TEXT,
        stage               TEXT    DEFAULT '',
        motivation_home     TEXT    DEFAULT '',
        motivation_away     TEXT    DEFAULT '',
        lineup_home         TEXT    DEFAULT '',
        lineup_away         TEXT    DEFAULT '',
        injuries_home       TEXT    DEFAULT '[]',
        injuries_away       TEXT    DEFAULT '[]',
        ai_confidence       TEXT    DEFAULT '',
        ai_prediction       TEXT    DEFAULT '',
        ai_score            TEXT    DEFAULT '',
        ai_confidence_level TEXT    DEFAULT '',
        ai_analysis         TEXT    DEFAULT '',
        ai_agrees_model     INTEGER,
        actual_home_goals   INTEGER,
        actual_away_goals   INTEGER,
        actual_result       TEXT,
        result_loaded_at    TEXT,
        brier_score         REAL,
        log_loss            REAL,
        result_correct      INTEGER,
        score_correct       INTEGER,
        over25_correct      INTEGER,
        btts_correct        INTEGER
    )
    """)

    _migrate_predictions_schema(cursor)

    # Índices base
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_teams     ON predictions(home_team, away_team)",
        "CREATE INDEX IF NOT EXISTS idx_date      ON predictions(match_date)",
        "CREATE INDEX IF NOT EXISTS idx_version   ON predictions(model_version)",
        # Nuevos índices para filtrar por competición y temporada
        "CREATE INDEX IF NOT EXISTS idx_comp      ON predictions(competition)",
        "CREATE INDEX IF NOT EXISTS idx_season    ON predictions(season)",
    ]:
        cursor.execute(idx_sql)

    conn.commit()
    conn.close()


def _migrate_predictions_schema(cursor: sqlite3.Cursor) -> None:
    """Actualiza bases existentes sin borrar el historial."""
    cursor.execute("PRAGMA table_info(predictions)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    migrations = {
        "season": "ALTER TABLE predictions ADD COLUMN season TEXT DEFAULT ''",
    }

    for col, sql in migrations.items():
        if col not in existing_cols:
            cursor.execute(sql)

    if "season" not in existing_cols:
        cursor.execute("SELECT id, match_date FROM predictions")
        rows = cursor.fetchall()
        for row in rows:
            cursor.execute(
                "UPDATE predictions SET season = ? WHERE id = ?",
                (_infer_season(row["match_date"] or ""), row["id"]),
            )


def _infer_season(match_date: str) -> str:
    """Infiere la temporada desde la fecha. Ej: '2026-06-12' → '2025/26'"""
    if not match_date:
        return ""
    try:
        year = int(match_date[:4])
        month = int(match_date[5:7])
        # Temporada europea: julio-junio
        if month >= 7:
            return f"{year}/{str(year+1)[2:]}"
        else:
            return f"{year-1}/{str(year)[2:]}"
    except (ValueError, IndexError):
        return ""


def save_prediction(resultado: dict,
                    model_version: str = "v2.0") -> int:
    """
    Guarda una predicción. Devuelve el ID asignado.
    Solo debe llamarse desde app.py después de la confirmación del usuario.
    """
    init_db()
    conn = get_connection()

    ctx     = resultado.get("context_raw", {})
    ctx_sum = resultado.get("context", {})
    sa      = resultado.get("strength_a", {})
    sb      = resultado.get("strength_b", {})
    ia      = resultado.get("analisis_ia", {}) or {}
    ou      = resultado.get("ou", {})

    va  = resultado.get("victoria_a", 0)
    emp = resultado.get("empate",     0)
    vb  = resultado.get("victoria_b", 0)
    if va >= emp and va >= vb:   predicted = "home"
    elif vb >= va and vb >= emp: predicted = "away"
    else:                        predicted = "draw"

    top           = resultado.get("top_marcadores", [])
    predicted_score = top[0][0] if top else ""
    competition   = ctx.get("competition") or ctx_sum.get("competition") or ""
    match_date    = resultado.get("match_date") or ctx.get("match_date", "")

    row = {
        "created_at":       datetime.now(timezone.utc).isoformat(),
        "model_version":    model_version,
        "home_team":        resultado.get("equipo_a", ""),
        "away_team":        resultado.get("equipo_b", ""),
        "competition":      competition,
        "season":           _infer_season(match_date),
        "match_date":       match_date,
        "venue":            resultado.get("venue", "neutral"),
        "prob_home":        va,
        "prob_draw":        emp,
        "prob_away":        vb,
        "predicted_result": predicted,
        "predicted_score":  predicted_score,
        "lambda_home":      resultado.get("lambda_a"),
        "lambda_away":      resultado.get("lambda_b"),
        "elo_home":         sa.get("team_elo"),
        "elo_away":         sb.get("team_elo"),
        "over_25":          ou.get("over_25"),
        "under_25":         ou.get("under_25"),
        "btts_si":          resultado.get("btts_si"),
        "btts_no":          resultado.get("btts_no"),
        "top_scores":       json.dumps(top),
        "stage":            ctx.get("stage") or ctx_sum.get("stage") or "",
        "motivation_home":  ctx.get("motivation_a", ""),
        "motivation_away":  ctx.get("motivation_b", ""),
        "lineup_home":      ctx.get("lineup_status_a", ""),
        "lineup_away":      ctx.get("lineup_status_b", ""),
        "injuries_home":    json.dumps(ctx.get("injuries_a", [])),
        "injuries_away":    json.dumps(ctx.get("injuries_b", [])),
        "ai_confidence":    ctx.get("confidence", ""),
        "ai_prediction":    ia.get("prediccion", ""),
        "ai_score":         ia.get("marcador_predicho", ""),
        "ai_confidence_level": ia.get("confianza", ""),
        "ai_analysis":      ia.get("analisis", ""),
        "ai_agrees_model":  (1 if ia.get("coincide_modelo") is True
                             else 0 if ia.get("coincide_modelo") is False
                             else None),
    }

    cols         = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    cursor       = conn.cursor()
    cursor.execute(f"INSERT INTO predictions ({cols}) VALUES ({placeholders})",
                   list(row.values()))
    pred_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"  💾 Predicción guardada (ID: {pred_id})")
    return pred_id


def check_duplicates(home_team: str, away_team: str,
                     competition: str = "",
                     match_date:  str = "") -> dict:
    """
    Busca predicciones similares.

    Fix Bug 1: la query anterior usaba 'OR competition = ?' con
    competition='' lo que matcheaba TODAS las filas donde la
    competición era vacía. Ahora se maneja explícitamente.

    Devuelve:
      exact   → mismo partido + misma fecha  (casi seguro duplicado)
      similar → mismo partido + distinta fecha (puede ser otra fase)
    """
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()

    # Buscar por equipos en ambas direcciones
    # NO filtrar por competition aquí para no perder casos
    cursor.execute("""
    SELECT id, created_at, home_team, away_team, competition,
           match_date, stage, predicted_result,
           prob_home, prob_draw, prob_away,
           actual_result, actual_home_goals, actual_away_goals
    FROM predictions
    WHERE (home_team = ? AND away_team = ?)
       OR (home_team = ? AND away_team = ?)
    ORDER BY created_at DESC
    LIMIT 20
    """, (home_team, away_team, away_team, home_team))

    all_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    exact   = []
    similar = []

    for row in all_rows:
        # Filtrar por competición si se especificó
        # (solo si la row también tiene competición cargada)
        row_comp = (row.get("competition") or "").strip().lower()
        req_comp = competition.strip().lower()

        if req_comp and row_comp and req_comp != row_comp:
            # Distinta competición → ignorar (no es el mismo torneo)
            continue

        row_date = (row.get("match_date") or "").strip()
        req_date = match_date.strip()

        if req_date and row_date and req_date == row_date:
            exact.append(row)
        else:
            similar.append(row)

    return {
        "exact":       exact,
        "similar":     similar,
        "has_exact":   len(exact)   > 0,
        "has_similar": len(similar) > 0,
    }


def delete_prediction(pred_id: int) -> bool:
    """
    Elimina una predicción. Solo permite borrar las SIN resultado real.
    """
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT actual_result FROM predictions WHERE id = ?",
                   (pred_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    if row["actual_result"] is not None:
        conn.close()
        print(f"  ⚠️  ID {pred_id} tiene resultado real — no se puede eliminar")
        return False

    cursor.execute("DELETE FROM predictions WHERE id = ?", (pred_id,))
    conn.commit()
    conn.close()
    print(f"  🗑️  ID {pred_id} eliminado")
    return True


def load_result(pred_id: int,
                home_goals: int,
                away_goals: int) -> dict:
    """Carga el resultado real y calcula métricas."""
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM predictions WHERE id = ?", (pred_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"No existe predicción con ID {pred_id}")

    if home_goals > away_goals:   actual = "home"
    elif home_goals < away_goals: actual = "away"
    else:                         actual = "draw"

    p_h = row["prob_home"] / 100
    p_d = row["prob_draw"] / 100
    p_a = row["prob_away"] / 100
    o_h = 1.0 if actual == "home" else 0.0
    o_d = 1.0 if actual == "draw" else 0.0
    o_a = 1.0 if actual == "away" else 0.0

    # Brier Score dividido por 3 → rango 0-1 (Fix corrección 4)
    brier = ((p_h - o_h)**2 + (p_d - o_d)**2 + (p_a - o_a)**2) / 3

    eps = 1e-9
    p_correct = p_h if actual == "home" else (p_d if actual == "draw" else p_a)
    log_loss  = -math.log(max(p_correct, eps))

    predicted     = row["predicted_result"]
    result_correct = 1 if predicted == actual else 0

    score_correct = 0
    if row["predicted_score"]:
        try:
            ph, pa = row["predicted_score"].split("-")
            score_correct = 1 if (int(ph) == home_goals and
                                   int(pa) == away_goals) else 0
        except (ValueError, AttributeError):
            pass

    total_goles    = home_goals + away_goals
    over25_correct = 1 if ((total_goles > 2.5) == ((row["over_25"] or 0) >= 50)) else 0
    real_btts      = home_goals > 0 and away_goals > 0
    btts_correct   = 1 if (real_btts == ((row["btts_si"] or 0) >= 50)) else 0

    cursor.execute("""
    UPDATE predictions SET
        actual_home_goals = ?, actual_away_goals = ?,
        actual_result = ?, result_loaded_at = ?,
        brier_score = ?, log_loss = ?,
        result_correct = ?, score_correct = ?,
        over25_correct = ?, btts_correct = ?
    WHERE id = ?
    """, (home_goals, away_goals, actual,
          datetime.now(timezone.utc).isoformat(),
          round(brier, 6), round(log_loss, 6),
          result_correct, score_correct,
          over25_correct, btts_correct,
          pred_id))

    conn.commit()
    conn.close()

    return {
        "id":             pred_id,
        "resultado_real": f"{home_goals}-{away_goals} ({actual})",
        "result_correct": bool(result_correct),
        "score_correct":  bool(score_correct),
        "over25_correct": bool(over25_correct),
        "btts_correct":   bool(btts_correct),
        "brier_score":    round(brier,    4),
        "log_loss":       round(log_loss, 4),
    }


def get_all_predictions(with_results_only: bool = False) -> list[dict]:
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()
    if with_results_only:
        cursor.execute(
            "SELECT * FROM predictions WHERE actual_result IS NOT NULL "
            "ORDER BY created_at DESC"
        )
    else:
        cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_pending_results() -> list[dict]:
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, created_at, home_team, away_team, competition,
           match_date, prob_home, prob_draw, prob_away, predicted_result
    FROM predictions WHERE actual_result IS NULL
    ORDER BY created_at DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_summary_stats(model_version: str = None,
                      competition:   str = None,
                      season:        str = None) -> dict:
    """
    Resumen global de métricas.
    Ahora filtrable también por competition y season (Fix corrección 5).
    """
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()

    where  = "WHERE actual_result IS NOT NULL"
    params = []
    if model_version:
        where += " AND model_version = ?"
        params.append(model_version)
    if competition:
        where += " AND competition LIKE ?"
        params.append(f"%{competition}%")
    if season:
        where += " AND season = ?"
        params.append(season)

    cursor.execute(f"""
    SELECT
        COUNT(*)              AS total,
        SUM(result_correct)   AS result_hits,
        SUM(score_correct)    AS score_hits,
        SUM(over25_correct)   AS over25_hits,
        SUM(btts_correct)     AS btts_hits,
        AVG(brier_score)      AS avg_brier,
        AVG(log_loss)         AS avg_log_loss,
        AVG(CASE WHEN predicted_result='home' AND result_correct=1
                 THEN 1.0 ELSE 0.0 END) AS prec_home,
        AVG(CASE WHEN predicted_result='draw' AND result_correct=1
                 THEN 1.0 ELSE 0.0 END) AS prec_draw,
        AVG(CASE WHEN predicted_result='away' AND result_correct=1
                 THEN 1.0 ELSE 0.0 END) AS prec_away
    FROM predictions {where}
    """, params)

    row = cursor.fetchone()
    conn.close()

    if not row or row["total"] == 0:
        return {"total": 0, "mensaje": "Sin predicciones evaluadas"}

    n = row["total"]
    return {
        "total_evaluadas":  n,
        "accuracy_1x2":     round(row["result_hits"]  / n * 100, 1),
        "accuracy_score":   round(row["score_hits"]   / n * 100, 1),
        "accuracy_over25":  round(row["over25_hits"]  / n * 100, 1),
        "accuracy_btts":    round(row["btts_hits"]    / n * 100, 1),
        "avg_brier_score":  round(row["avg_brier"],    4),
        "avg_log_loss":     round(row["avg_log_loss"], 4),
        "brier_referencia": 0.333,   # con división por 3: rango 0-1
        "precision_home":   round((row["prec_home"] or 0) * 100, 1),
        "precision_draw":   round((row["prec_draw"] or 0) * 100, 1),
        "precision_away":   round((row["prec_away"] or 0) * 100, 1),
        "model_version":    model_version or "todas",
        "competition":      competition   or "todas",
        "season":           season        or "todas",
    }


def update_match_date(pred_id: int, match_date: str) -> bool:
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE predictions SET match_date = ?, season = ? WHERE id = ?",
                   (match_date, _infer_season(match_date), pred_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_seasons() -> list[str]:
    """Devuelve la lista de temporadas disponibles para filtrar."""
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT season FROM predictions "
        "WHERE season != '' ORDER BY season DESC"
    )
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows


def get_competitions() -> list[str]:
    """Devuelve la lista de competiciones disponibles para filtrar."""
    init_db()
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT competition FROM predictions "
        "WHERE competition != '' ORDER BY competition"
    )
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows
