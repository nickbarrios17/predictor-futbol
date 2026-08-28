# data/fixtures.py
"""
Caché para partidos que todavía no se jugaron: próximos partidos de
un equipo y fixture completo de un torneo por fecha.

Separado de data/fetcher.py (que cachea historial ya jugado) porque
son datos con un patrón de uso y un TTL bien distintos: el historial
no cambia una vez jugado, pero un fixture futuro puede reprogramarse,
y el fixture de un torneo entero es mucho más caro de pedir (∼1
pedido por equipo de la fecha) así que conviene un caché más largo.
"""
import os
import json
from datetime import datetime, timezone

from sources.api_source import (
    search_team,
    get_team_next_matches,
    search_tournament,
    get_tournament_current_season_id,
    get_tournament_fixtures,
)
from data.fetcher import _best_match
from config import (
    CACHE_DIR,
    CACHE_HOURS_NEXT_MATCHES,
    CACHE_HOURS_TOURNAMENT_FIXTURES,
)

NEXT_MATCHES_CACHE_DIR = os.path.join(CACHE_DIR, "next_matches")
TOURNAMENT_CACHE_DIR   = os.path.join(CACHE_DIR, "tournament_fixtures")
os.makedirs(NEXT_MATCHES_CACHE_DIR, exist_ok=True)
os.makedirs(TOURNAMENT_CACHE_DIR, exist_ok=True)


# ── Caché genérico (mismo formato que data/fetcher.py) ──────────

def _read_cache(path: str, max_age_hours: float):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        saved_at_str = data.get("_saved_at")
        if not saved_at_str:
            return None

        saved_at = datetime.fromisoformat(saved_at_str)
        now      = datetime.now(timezone.utc).replace(tzinfo=None)
        age_h    = (now - saved_at.replace(tzinfo=None)).total_seconds() / 3600

        if age_h > max_age_hours:
            print(f"  🗑️  Caché de fixtures vencida ({age_h:.1f}h > {max_age_hours}h)")
            return None

        print(f"  📦 Caché de fixtures válida ({age_h:.1f}h)")
        return data.get("items")

    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        return None


def _write_cache(path: str, items) -> None:
    try:
        data = {
            "_saved_at": datetime.now(timezone.utc).isoformat(),
            "items":     items,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"  ⚠️  No se pudo escribir caché de fixtures: {e}")


def clear_tournament_cache(tournament_id=None) -> None:
    if tournament_id:
        path = os.path.join(TOURNAMENT_CACHE_DIR, f"{tournament_id}.json")
        if os.path.exists(path):
            os.remove(path)
    else:
        for f in os.listdir(TOURNAMENT_CACHE_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(TOURNAMENT_CACHE_DIR, f))


# ── Próximos partidos de un equipo ───────────────────────────────

def fetch_team_next_matches(team_name: str, limit: int = 5,
                            force_refresh: bool = False) -> list[dict]:
    """
    Devuelve los próximos partidos programados de un equipo.
    Cada partido trae team_home/team_away tal cual los da la API,
    así que quien llame decide cuál es "el equipo buscado".
    """
    candidatos = search_team(team_name)
    if not candidatos:
        print(f"  ❌ No se encontró '{team_name}' en la API.")
        return []

    equipo = _best_match(team_name, candidatos)
    if not equipo:
        return []

    team_id = equipo["id"]
    path    = os.path.join(NEXT_MATCHES_CACHE_DIR, f"{team_id}.json")

    if not force_refresh:
        cached = _read_cache(path, CACHE_HOURS_NEXT_MATCHES)
        if cached is not None:
            return cached[:limit]

    matches = get_team_next_matches(team_id, limit=limit)
    _write_cache(path, matches)
    return matches


# ── Fixture completo de un torneo ────────────────────────────────

def fetch_tournament_fixtures(tournament_name: str,
                              force_refresh: bool = False) -> dict:
    """
    Busca un torneo por nombre y devuelve su fixture futuro agrupado
    por fecha/ronda:

    {
        "tournament_id":   155,
        "tournament_name": "Liga Profesional de Fútbol",
        "rounds": {7: [partido, ...], 8: [...], ...},
    }

    Devuelve {} si no se encontró el torneo.
    """
    torneos = search_tournament(tournament_name)
    if not torneos:
        print(f"  ❌ No se encontró el torneo '{tournament_name}' en la API.")
        return {}

    torneo = _best_match(tournament_name, torneos)
    if not torneo:
        return {}

    tournament_id = torneo["id"]
    path = os.path.join(TOURNAMENT_CACHE_DIR, f"{tournament_id}.json")

    if not force_refresh:
        cached = _read_cache(path, CACHE_HOURS_TOURNAMENT_FIXTURES)
        if cached is not None:
            return {
                "tournament_id":   tournament_id,
                "tournament_name": torneo["name"],
                "rounds":          _agrupar_por_ronda(cached),
            }

    season_id = get_tournament_current_season_id(tournament_id)
    if season_id is None:
        print(f"  ❌ No se pudo determinar la temporada actual de '{torneo['name']}'.")
        return {}

    fixtures = get_tournament_fixtures(tournament_id, season_id)
    _write_cache(path, fixtures)

    return {
        "tournament_id":   tournament_id,
        "tournament_name": torneo["name"],
        "rounds":          _agrupar_por_ronda(fixtures),
    }


def _agrupar_por_ronda(fixtures: list[dict]) -> dict:
    rondas: dict = {}
    for m in fixtures:
        r = m.get("round")
        rondas.setdefault(r, []).append(m)
    return dict(sorted(rondas.items(), key=lambda kv: (kv[0] is None, kv[0])))
