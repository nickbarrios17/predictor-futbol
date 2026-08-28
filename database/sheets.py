# database/sheets.py - v2.2
"""
Sincronizacion con Google Sheets.

Esta version verifica la escritura leyendo de vuelta la columna de IDs.
Asi evitamos mostrar "sincronizado" cuando la hoja visible no recibio filas.

Las credenciales se leen del archivo credentials.json si existe (uso
local), o si no, del contenido JSON crudo en la variable de entorno
GOOGLE_CREDENTIALS_JSON (uso en hosting sin filesystem persistente,
ej. Streamlit Cloud secrets).
"""
import json
import os

try:
    import gspread
    from google.oauth2.service_account import Credentials

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


SHEET_ID = "1aHkzk4a6IgqJnXUV_Ouk-wn0mlLnaxkmKC0Dmc4ipyc"
CREDS_PATH = "credentials.json"
DEFAULT_TAB = "Predicciones"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COLUMNS = [
    "ID",
    "Fecha prediccion",
    "Partido",
    "Competicion",
    "Sede",
    "P(local)%",
    "P(empate)%",
    "P(visita)%",
    "Resultado predicho",
    "Marcador predicho",
    "Lambda local",
    "Lambda visita",
    "Elo local",
    "Elo visita",
    "Over 2.5%",
    "BTTS Si%",
    "Stage",
    "Confianza IA",
    "Prediccion IA",
    "Marcador IA",
    "IA coincide modelo",
    "Resultado real",
    "Goles local real",
    "Goles visita real",
    "OK 1X2",
    "OK Over 2.5",
    "OK BTTS",
    "Brier Score",
    "Log Loss",
    "Version modelo",
    "Notas",
]


def _get_client():
    if not GSPREAD_AVAILABLE:
        raise RuntimeError("Instala gspread: pip install gspread google-auth")

    if os.path.exists(CREDS_PATH):
        creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        return gspread.authorize(creds)

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)

    raise FileNotFoundError(
        f"No se encontro {CREDS_PATH} ni la variable de entorno "
        "GOOGLE_CREDENTIALS_JSON. Descarga las credenciales desde "
        "Google Cloud Console."
    )


def _get_or_create_worksheet(client, tab_name: str):
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        return spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=35)


def _worksheet_url(ws) -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={ws.id}"


def _update_range(ws, range_name: str, values: list[list]) -> None:
    # gspread v5/v6 changed positional argument expectations. Keywords are safer.
    ws.update(range_name=range_name, values=values)


def _setup_headers(ws) -> None:
    _update_range(ws, "A1", [COLUMNS])
    ws.format(
        "A1:AE1",
        {
            "backgroundColor": {"red": 0.12, "green": 0.27, "blue": 0.45},
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            },
            "horizontalAlignment": "CENTER",
        },
    )
    ws.freeze(rows=1)


def _yn(val):
    if val is None:
        return "-"
    return "SI" if val else "NO"


def _pred_to_row(p: dict) -> list:
    real = "-"
    if p.get("actual_home_goals") is not None:
        real = f"{p['actual_home_goals']}-{p['actual_away_goals']}"

    return [
        p.get("id", ""),
        p.get("created_at", "")[:16].replace("T", " "),
        f"{p.get('home_team','')} vs {p.get('away_team','')}",
        p.get("competition", "-"),
        p.get("venue", "-"),
        p.get("prob_home", ""),
        p.get("prob_draw", ""),
        p.get("prob_away", ""),
        p.get("predicted_result", "-"),
        p.get("predicted_score", "-"),
        p.get("lambda_home", ""),
        p.get("lambda_away", ""),
        p.get("elo_home", ""),
        p.get("elo_away", ""),
        p.get("over_25", ""),
        p.get("btts_si", ""),
        p.get("stage", "-"),
        p.get("ai_confidence", "-"),
        p.get("ai_prediction", "-"),
        p.get("ai_score", "-"),
        _yn(p.get("ai_agrees_model")),
        real,
        p.get("actual_home_goals", ""),
        p.get("actual_away_goals", ""),
        _yn(p.get("result_correct")),
        _yn(p.get("over25_correct")),
        _yn(p.get("btts_correct")),
        p.get("brier_score", ""),
        p.get("log_loss", ""),
        p.get("model_version", "-"),
        "",
    ]


def sync_to_sheets(predictions: list[dict], tab_name: str = DEFAULT_TAB) -> dict:
    """Vuelca todas las predicciones de SQLite al sheet."""
    try:
        client = _get_client()
        ws = _get_or_create_worksheet(client, tab_name)

        existing = ws.get_all_values()
        if not existing or existing[0] != COLUMNS:
            _setup_headers(ws)

        if not predictions:
            return {
                "ok": True,
                "rows": 0,
                "verified_rows": 0,
                "worksheet": ws.title,
                "url": _worksheet_url(ws),
                "message": f"Sin predicciones para sincronizar en pestana '{ws.title}'",
            }

        rows = [_pred_to_row(p) for p in predictions]

        last = max(len(existing), len(rows)) + 2
        ws.batch_clear([f"A2:AE{last}"])
        _update_range(ws, "A2", rows)

        written_ids = ws.get(f"A2:A{len(rows) + 1}")
        verified_rows = sum(1 for row in written_ids if row and str(row[0]).strip())

        if verified_rows != len(rows):
            msg = (
                f"Sheets respondio OK, pero solo verifique {verified_rows}/{len(rows)} "
                f"filas en pestana '{ws.title}'."
            )
            print(f"  Sheets: {msg}")
            return {
                "ok": False,
                "rows": len(rows),
                "verified_rows": verified_rows,
                "worksheet": ws.title,
                "url": _worksheet_url(ws),
                "message": msg,
            }

        msg = f"{verified_rows} predicciones sincronizadas en pestana '{ws.title}'"
        print(f"  Sheets: {msg}")
        return {
            "ok": True,
            "rows": len(rows),
            "verified_rows": verified_rows,
            "worksheet": ws.title,
            "url": _worksheet_url(ws),
            "message": msg,
        }

    except Exception as e:
        msg = f"Error: {e}"
        print(f"  Sheets: {msg}")
        return {"ok": False, "rows": 0, "verified_rows": 0, "message": msg}


def append_prediction(pred: dict, tab_name: str = DEFAULT_TAB) -> dict:
    """Agrega una sola fila nueva al final del sheet."""
    try:
        client = _get_client()
        ws = _get_or_create_worksheet(client, tab_name)

        existing = ws.get_all_values()
        if not existing or existing[0] != COLUMNS:
            _setup_headers(ws)

        ws.append_row(_pred_to_row(pred), value_input_option="USER_ENTERED")

        values = ws.get_all_values()
        found = any(row and str(row[0]).strip() == str(pred.get("id")) for row in values[1:])
        if not found:
            msg = f"No pude verificar la fila agregada en pestana '{ws.title}'"
            print(f"  Sheets: {msg}")
            return {
                "ok": False,
                "message": msg,
                "worksheet": ws.title,
                "url": _worksheet_url(ws),
            }

        msg = f"Fila agregada ID {pred.get('id')} en pestana '{ws.title}'"
        print(f"  Sheets: {msg}")
        return {
            "ok": True,
            "message": msg,
            "worksheet": ws.title,
            "url": _worksheet_url(ws),
        }

    except Exception as e:
        msg = f"Error: {e}"
        print(f"  Sheets: {msg}")
        return {"ok": False, "message": msg}


def sync_from_sheets(tab_name: str = DEFAULT_TAB) -> list[dict]:
    """Lee resultados reales escritos en la columna 'Resultado real'."""
    try:
        client = _get_client()
        ws = _get_or_create_worksheet(client, tab_name)
        rows = ws.get_all_records()

        pendientes = []
        for row in rows:
            pred_id = row.get("ID")
            real = str(row.get("Resultado real", "")).strip()

            if not real or real == "-" or "-" not in real:
                continue
            if row.get("OK 1X2") in ["SI", "NO"]:
                continue

            try:
                partes = real.replace(" ", "").split("-")
                pendientes.append(
                    {
                        "id": int(pred_id),
                        "home_goals": int(partes[0]),
                        "away_goals": int(partes[1]),
                    }
                )
            except (ValueError, IndexError):
                continue

        return pendientes

    except Exception as e:
        print(f"  Sheets: error leyendo sheet: {e}")
        return []


def update_result_row(pred_id: int, metricas: dict, tab_name: str = DEFAULT_TAB) -> bool:
    """Actualiza las columnas de metricas de una fila ya existente."""
    try:
        client = _get_client()
        ws = _get_or_create_worksheet(client, tab_name)
        rows = ws.get_all_values()
        headers = rows[0] if rows else []

        id_col = headers.index("ID") if "ID" in headers else 0
        target_row = None
        for i, row in enumerate(rows[1:], start=2):
            if row and str(row[id_col]).strip() == str(pred_id):
                target_row = i
                break

        if not target_row:
            return False

        updates = {
            "OK 1X2": _yn(metricas.get("result_correct")),
            "OK Over 2.5": _yn(metricas.get("over25_correct")),
            "OK BTTS": _yn(metricas.get("btts_correct")),
            "Brier Score": metricas.get("brier_score", ""),
            "Log Loss": metricas.get("log_loss", ""),
        }

        for col_name, value in updates.items():
            if col_name in headers:
                ws.update_cell(target_row, headers.index(col_name) + 1, value)

        return True

    except Exception as e:
        print(f"  Sheets: error actualizando fila: {e}")
        return False
