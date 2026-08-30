# sources/api_football_source.py — v1.0
"""
Fuente de datos alternativa: API-Football (api-sports.io), v3.

Mismo contrato de salida que sources/api_source.py (SofaScore) — los
mismos 6 nombres de función, mismo shape de dict — para que
sources/football_data.py pueda usarlas indistintamente. No pagina de a
10 como SofaScore: /fixtures?team=X&last=N devuelve los N partidos en
un solo call.

Cada call actualiza la cuota persistida en sources/football_quota.py a
partir del header `x-ratelimit-requests-remaining`. Un 429 marca la
cuota como agotada y levanta QuotaExceeded para que football_data.py
caiga al fallback.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from config import API_FOOTBALL_KEY
from sources import football_quota

AR_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

BASE_URL = "https://v3.football.api-sports.io"
HEADERS  = {"x-apisports-key": API_FOOTBALL_KEY}

FINISHED_STATUSES = {"FT", "AET", "PEN"}


class QuotaExceeded(Exception):
    """Se agotó la cuota diaria de API-Football (HTTP 429)."""


def _to_ar_time(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=AR_TZ)


def _get(path: str, params: dict) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/{path}", headers=HEADERS,
                        params=params, timeout=10)

    if resp.status_code == 429:
        football_quota.mark_exhausted()
        raise QuotaExceeded(f"429 en /{path}")

    football_quota.update_from_response(resp)
    resp.raise_for_status()

    data = resp.json()
    errors = data.get("errors")
    if errors:
        raise RuntimeError(f"API-Football error en /{path}: {errors}")

    return data.get("response", [])


# ── Equipos ───────────────────────────────────────────────────

def search_team(name: str) -> list[dict]:
    """Busca equipos por nombre y devuelve lista de {id, name}."""
    try:
        response = _get("teams", {"search": name})
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en search_team (API-Football): {e}")
        return []

    return [
        {"id": t["team"]["id"], "name": t["team"]["name"]}
        for t in response
    ]


def get_team_matches(team_id: int, limit: int = 20) -> list[dict]:
    """Últimos N partidos finalizados de un equipo, ya ordenados por fecha desc."""
    try:
        response = _get("fixtures", {"team": str(team_id), "last": str(limit)})
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en get_team_matches (API-Football): {e}")
        return []

    matches = [
        _parse_match(m) for m in response
        if m.get("fixture", {}).get("status", {}).get("short") in FINISHED_STATUSES
    ]
    matches.sort(key=lambda x: x["date"], reverse=True)
    return matches[:limit]


def _parse_match(m: dict) -> dict:
    fixture = m.get("fixture", {})
    league  = m.get("league", {})
    teams   = m.get("teams", {})
    goals   = m.get("goals", {})

    match_date = _to_ar_time(fixture.get("timestamp", 0)).strftime("%Y-%m-%d")

    return {
        "date":        match_date,
        "team_home":   teams.get("home", {}).get("name", "Unknown"),
        "team_away":   teams.get("away", {}).get("name", "Unknown"),
        "goals_home":  goals.get("home") or 0,
        "goals_away":  goals.get("away") or 0,
        "competition": league.get("name", "Unknown"),
        "category":    league.get("country", ""),
        "round":       league.get("round", ""),
        "context":     {},
    }


# ── Próximos partidos ────────────────────────────────────────────

def get_team_next_matches(team_id: int, limit: int = 5) -> list[dict]:
    """Próximos partidos programados (no jugados) de un equipo."""
    try:
        response = _get("fixtures", {"team": str(team_id), "next": str(limit)})
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en get_team_next_matches (API-Football): {e}")
        return []

    matches = [
        _parse_upcoming_match(m) for m in response
        if m.get("fixture", {}).get("status", {}).get("short") not in FINISHED_STATUSES
    ]
    matches.sort(key=lambda x: (x["date"], x["time"]))
    return matches[:limit]


def _parse_upcoming_match(m: dict) -> dict:
    fixture = m.get("fixture", {})
    league  = m.get("league", {})
    teams   = m.get("teams", {})

    dt = _to_ar_time(fixture.get("timestamp", 0))
    round_name = league.get("round") or "Fecha ?"

    return {
        "event_id":     fixture.get("id"),
        "date":         dt.strftime("%Y-%m-%d"),
        "time":         dt.strftime("%H:%M"),
        "team_home":    teams.get("home", {}).get("name", "Unknown"),
        "team_away":    teams.get("away", {}).get("name", "Unknown"),
        "team_home_id": teams.get("home", {}).get("id"),
        "team_away_id": teams.get("away", {}).get("id"),
        "competition":  league.get("name", "Unknown"),
        "round":        None,
        "round_name":   round_name,
    }


# ── Torneos ───────────────────────────────────────────────────

def search_tournament(name: str) -> list[dict]:
    """Busca torneos (ligas) por nombre y devuelve lista de {id, name, country}."""
    try:
        response = _get("leagues", {"search": name})
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en search_tournament (API-Football): {e}")
        return []

    return [
        {
            "id":      t["league"]["id"],
            "name":    t["league"]["name"],
            "country": t.get("country", {}).get("name", ""),
        }
        for t in response
    ]


def get_tournament_current_season_id(tournament_id: int) -> int | None:
    """
    API-Football no tiene un "season id" separado como SofaScore: la
    temporada es directamente un año. Devuelve el year marcado como
    current=true para este torneo (se usa como "season" en
    get_tournament_fixtures).
    """
    try:
        response = _get("leagues", {"id": str(tournament_id)})
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en get_tournament_current_season_id (API-Football): {e}")
        return None

    if not response:
        return None

    for season in response[0].get("seasons", []):
        if season.get("current"):
            return season.get("year")
    return None


def get_tournament_fixtures(tournament_id: int, season_id: int,
                            max_pages: int = 1) -> list[dict]:
    """
    Próximos partidos programados del torneo para la temporada dada.
    `season_id` acá es el año (ver get_tournament_current_season_id).
    A diferencia de SofaScore, no hay ventana fija: se pide una tanda
    grande de próximos partidos del torneo de una.
    """
    try:
        response = _get("fixtures", {
            "league": str(tournament_id),
            "season": str(season_id),
            "next":   "50",
        })
    except QuotaExceeded:
        raise
    except Exception as e:
        print(f"  ⚠️ Error en get_tournament_fixtures (API-Football): {e}")
        return []

    matches = [
        _parse_upcoming_match(m) for m in response
        if m.get("fixture", {}).get("status", {}).get("short") not in FINISHED_STATUSES
    ]
    matches.sort(key=lambda x: (x["date"], x["time"]))
    return matches
