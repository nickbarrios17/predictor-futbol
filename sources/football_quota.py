# sources/football_quota.py — v1.0
"""
Trackea la cuota diaria de API-Football (100 requests/día en el free
tier, resetea a las 00:00:00 UTC). Se persiste en disco (mismo patrón
de caché que data/fetcher.py) para sobrevivir reinicios del proceso.

La fuente de verdad es el header `x-ratelimit-requests-remaining` que
API-Football devuelve en cada respuesta — no se lleva una cuenta propia,
solo se refleja lo que dice el servidor.
"""
import json
import os
from datetime import datetime, timezone

from config import CACHE_DIR, API_FOOTBALL_DAILY_LIMIT

QUOTA_PATH = os.path.join(CACHE_DIR, "api_football_quota.json")
os.makedirs(CACHE_DIR, exist_ok=True)


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read() -> dict:
    if not os.path.exists(QUOTA_PATH):
        return {}
    try:
        with open(QUOTA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def _write(date: str, remaining: int) -> None:
    try:
        with open(QUOTA_PATH, "w", encoding="utf-8") as f:
            json.dump({"date": date, "remaining": remaining}, f)
    except OSError as e:
        print(f"  ⚠️  No se pudo guardar la cuota de API-Football: {e}")


def has_budget() -> bool:
    """
    True si todavía se puede intentar un call a API-Football hoy.
    Si el registro guardado es de un día anterior, se asume cuota
    fresca (el reset real lo hace el servidor a las 00:00 UTC).
    """
    data = _read()
    if data.get("date") != _today_utc():
        return True
    return data.get("remaining", API_FOOTBALL_DAILY_LIMIT) > 0


def update_from_response(response) -> None:
    """Lee el remanente real del header y lo persiste para hoy (UTC)."""
    header = response.headers.get("x-ratelimit-requests-remaining")
    if header is None:
        return
    try:
        remaining = int(header)
    except ValueError:
        return
    _write(_today_utc(), remaining)


def mark_exhausted() -> None:
    """Fuerza remaining=0 para hoy — se llama ante un 429 explícito."""
    _write(_today_utc(), 0)
