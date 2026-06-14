# model/strength.py — v1.2
"""
Calcula la fuerza ofensiva y defensiva de un equipo.

Cambios v1.2:
  - Ajuste por calidad del rival usando Elo Rating (Mejora 1 del PDF).
    Argentina 3-0 Bolivia  ≠  Argentina 3-0 Francia
    Ahora los goles se ponderan por el opponent_factor del rival.

  - El opponent_factor se calcula con:
      goles_ajustados  = goles_reales × opponent_factor
      concedidos_ajust = goles_concedidos / opponent_factor
    Efecto: atacar a equipos fuertes infla el ataque,
    conceder a equipos débiles penaliza la defensa.

Todo lo demás de v1.1 se mantiene:
  - Normalización por promedio de liga.
  - Separación local/visitante.
  - Sin HOME_ADVANTAGE en el historial.
  - Sin redondeo interno.
"""
import math
from datetime import date, datetime
from config import (DECAY_RATE, MAX_MONTHS_HISTORY, LEAGUE_AVG_GOALS)
from model.context import get_all_weights
from features.elo import get_elo, get_opponent_factor


def time_decay(match_date_str: str) -> float:
    try:
        match_date = datetime.strptime(match_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0.5
    months_ago = (date.today() - match_date).days / 30
    return math.exp(-DECAY_RATE * months_ago)


def is_too_old(match_date_str: str) -> bool:
    try:
        match_date = datetime.strptime(match_date_str, "%Y-%m-%d").date()
    except ValueError:
        return True
    months_ago = (date.today() - match_date).days / 30
    return months_ago > MAX_MONTHS_HISTORY


def _get_league_avg(competition: str) -> float:
    comp_lower = competition.lower()
    for key, avg in LEAGUE_AVG_GOALS.items():
        if key.lower() in comp_lower:
            return avg
    return LEAGUE_AVG_GOALS["default"]


def calcular_lambda(matches: list[dict], team_name: str,
                    verbose: bool = False) -> dict:
    """
    Calcula las fuerzas del equipo con ajuste por calidad de rival.

    Fórmula por partido:
      gf_adj = (gf / avg_liga) × opponent_factor
      gc_adj = (gc / avg_liga) / opponent_factor

    Donde opponent_factor = rival_elo / competition_avg_elo:
      - rival fuerte (factor > 1) → goles anotados valen más,
                                     goles recibidos penalizan menos
      - rival débil  (factor < 1) → goles anotados valen menos,
                                     goles recibidos penalizan más
    """
    elo = get_elo()

    # Actualizar Elo con el historial del equipo antes de calcular
    # (así el factor del rival es más preciso)
    elo.update_from_matches(matches, team_name)

    # Acumuladores separados por sede
    ataque_local_num  = 0.0; ataque_local_den  = 0.0
    defensa_local_num = 0.0; defensa_local_den = 0.0
    ataque_visit_num  = 0.0; ataque_visit_den  = 0.0
    defensa_visit_num = 0.0; defensa_visit_den = 0.0

    partidos_usados = 0
    desglose = []

    for m in matches:
        if is_too_old(m["date"]):
            continue

        w_time = time_decay(m["date"])
        pesos  = get_all_weights(m)
        w      = w_time * pesos["w_combined"]

        es_local = m["team_home"] == team_name
        comp     = m.get("competition", "Unknown")
        avg_liga = _get_league_avg(comp)

        if es_local:
            rival = m.get("team_away", "Unknown")
            gf    = m.get("goals_home", 0) or 0
            gc    = m.get("goals_away", 0) or 0
        else:
            rival = m.get("team_home", "Unknown")
            gf    = m.get("goals_away", 0) or 0
            gc    = m.get("goals_home", 0) or 0

        # ── Ajuste por calidad del rival (v1.2) ───────────────
        opp_factor = get_opponent_factor(rival, comp)

        # Goles ajustados por calidad del rival y normalizados por liga
        gf_adj = (gf / avg_liga) * opp_factor
        gc_adj = (gc / avg_liga) / opp_factor

        if es_local:
            ataque_local_num  += gf_adj * w
            ataque_local_den  += w
            defensa_local_num += gc_adj * w
            defensa_local_den += w
        else:
            ataque_visit_num  += gf_adj * w
            ataque_visit_den  += w
            defensa_visit_num += gc_adj * w
            defensa_visit_den += w

        partidos_usados += 1

        if verbose:
            rival_elo = round(elo.get_rating(rival, comp))
            desglose.append({
                "fecha":       m["date"],
                "rival":       rival,
                "rival_elo":   rival_elo,
                "opp_factor":  opp_factor,
                "goles":       f"{gf}-{gc}",
                "goles_adj":   f"{gf_adj:.2f}-{gc_adj:.2f}",
                "sede":        "L" if es_local else "V",
                "comp":        comp[:25],
                "avg_liga":    avg_liga,
                "w_time":      w_time,
                "w_comp":      pesos["w_comp"],
                "w_stakes":    pesos["w_stakes"],
                "w_lineup":    pesos["w_lineup"],
                "w_total":     w,
            })

    if partidos_usados == 0:
        raise ValueError(
            f"Sin datos válidos para '{team_name}'. "
            f"Verificá el nombre del equipo."
        )

    def _safe_div(num, den, fallback=1.0):
        return num / den if den > 0 else fallback

    attack_home  = _safe_div(ataque_local_num,  ataque_local_den)
    attack_away  = _safe_div(ataque_visit_num,  ataque_visit_den)
    defense_home = _safe_div(defensa_local_num, defensa_local_den)
    defense_away = _safe_div(defensa_visit_num, defensa_visit_den)

    total_att_num = ataque_local_num  + ataque_visit_num
    total_att_den = ataque_local_den  + ataque_visit_den
    total_def_num = defensa_local_num + defensa_visit_num
    total_def_den = defensa_local_den + defensa_visit_den

    attack_global  = _safe_div(total_att_num, total_att_den)
    defense_global = _safe_div(total_def_num, total_def_den)

    # Fallback si hay < 3 partidos en una condición
    if ataque_local_den < 3 * 0.5:
        attack_home  = attack_global
        defense_home = defense_global
    if ataque_visit_den < 3 * 0.5:
        attack_away  = attack_global
        defense_away = defense_global

    # Rating Elo del equipo (para mostrar en UI)
    team_elo = round(elo.get_rating(team_name))

    resultado = {
        "team":            team_name,
        "team_elo":        team_elo,
        "elo_categoria":   _categoria_elo(team_elo),
        "attack_home":     attack_home,
        "attack_away":     attack_away,
        "defense_home":    defense_home,
        "defense_away":    defense_away,
        "attack_global":   attack_global,
        "defense_global":  defense_global,
        # Aliases para compatibilidad
        "lambda_ataque":   attack_global,
        "lambda_defensa":  defense_global,
        "partidos_usados": partidos_usados,
    }

    if verbose:
        resultado["desglose"] = desglose

    return resultado


def _categoria_elo(elo: int) -> str:
    if elo >= 2000: return "Elite mundial"
    if elo >= 1850: return "Top mundial"
    if elo >= 1750: return "Muy fuerte"
    if elo >= 1650: return "Fuerte"
    if elo >= 1550: return "Competitivo"
    if elo >= 1450: return "Promedio"
    return "Débil"
