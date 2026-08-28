# sources/api_source.py
import requests
import time
from datetime import datetime
from config import RAPIDAPI_KEY

BASE_URL = "https://sofascore.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
}


def search_team(name: str) -> list[dict]:
    """Busca equipos por nombre y devuelve lista de {id, name}."""
    time.sleep(1.0)
    url = f"{BASE_URL}/teams/search"
    try:
        resp = requests.get(url, headers=HEADERS,
                            params={"name": name}, timeout=10)
        resp.raise_for_status()
        teams = resp.json().get("teams", [])
        return [
            {"id": t["id"], "name": t.get("name", "?")}
            for t in teams
            if t.get("sport", {}).get("slug") == "football"
        ]
    except Exception as e:
        print(f"  ⚠️ Error en search_team: {e}")
        return []


def get_team_matches(team_id: int, limit: int = 20) -> list[dict]:
    """
    Obtiene los últimos N partidos finalizados de un equipo.

    SofaScore devuelve los partidos en páginas de ~10.
    Paginamos hasta tener suficientes partidos o agotar las páginas.
    Los resultados vienen ordenados de más reciente a más viejo.
    """
    all_matches = []
    seen_ids    = set()
    page = 0
    max_pages = 5  # máximo 50 partidos (5 páginas × 10)

    while len(all_matches) < limit and page < max_pages:
        time.sleep(1.0)
        url = f"{BASE_URL}/teams/get-last-matches"
        params = {"teamId": str(team_id), "page": str(page)}

        try:
            resp = requests.get(url, headers=HEADERS,
                                params=params, timeout=10)
            resp.raise_for_status()
            data      = resp.json()
            raw_events = data.get("events", [])

            print(f"  📡 Página {page}: {len(raw_events)} eventos")

            if not raw_events:
                # Sin más partidos
                break

            # Filtrar finalizados con score válido
            # SofaScore a veces repite eventos entre páginas consecutivas,
            # por eso se deduplica por ID de evento.
            for m in raw_events:
                event_id = m.get("id")
                if event_id is not None and event_id in seen_ids:
                    continue

                status = m.get("status", {})
                finished = (
                    status.get("code") == 100
                    or status.get("type") == "finished"
                )
                if finished and _is_valid(m):
                    if event_id is not None:
                        seen_ids.add(event_id)
                    all_matches.append(_parse_match(m))

            page += 1

        except Exception as e:
            print(f"  ⚠️ Error en get_team_matches página {page}: {e}")
            break

    # Ordenar de más reciente a más viejo y limitar
    all_matches.sort(key=lambda x: x["date"], reverse=True)

    print(f"  ✅ Total partidos válidos obtenidos: {len(all_matches)}")
    return all_matches[:limit]


def _is_valid(m: dict) -> bool:
    """El partido tiene resultado completo."""
    hs = m.get("homeScore", {})
    as_ = m.get("awayScore", {})
    return (
        hs.get("current") is not None
        and as_.get("current") is not None
    )


def _parse_match(m: dict) -> dict:
    """
    Convierte el evento crudo de SofaScore al formato interno.
    Incluye todos los campos que necesitan strength.py y context.py.
    """
    ts         = m.get("startTimestamp", 0)
    match_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

    # Nombre de la ronda (útil para detectar stakes)
    round_info = m.get("roundInfo", {})
    round_name = round_info.get("name", "") or round_info.get("nameCode", "") or ""

    # Nombre completo de la competición
    tournament  = m.get("tournament", {})
    competition = tournament.get("name", "Unknown")

    # Categoría (ayuda a distinguir mundiales de amistosos)
    category = tournament.get("category", {}).get("name", "")

    return {
        "date":        match_date,
        "team_home":   m.get("homeTeam", {}).get("name", "Unknown"),
        "team_away":   m.get("awayTeam", {}).get("name", "Unknown"),
        "goals_home":  m.get("homeScore", {}).get("current", 0),
        "goals_away":  m.get("awayScore", {}).get("current", 0),
        "competition": competition,
        "category":    category,
        "round":       round_name,
        "context":     {},  # se puede enriquecer después con la IA
    }


# ── Próximos partidos (todavía no jugados) ──────────────────────

def get_team_next_matches(team_id: int, limit: int = 5) -> list[dict]:
    """
    Obtiene los próximos partidos programados (no jugados) de un equipo.
    Mismo patrón de paginación/deduplicación que get_team_matches.
    """
    all_matches = []
    seen_ids    = set()
    page = 0
    max_pages = 3

    while len(all_matches) < limit and page < max_pages:
        time.sleep(1.0)
        url = f"{BASE_URL}/teams/get-next-matches"
        params = {"teamId": str(team_id), "page": str(page)}

        try:
            resp = requests.get(url, headers=HEADERS,
                                params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                # El equipo no tiene proximos partidos cargados en SofaScore
                break

            raw_events = data.get("events", [])
            if not raw_events:
                break

            for m in raw_events:
                event_id = m.get("id")
                if event_id is not None and event_id in seen_ids:
                    continue
                if m.get("status", {}).get("type") == "finished":
                    continue
                if event_id is not None:
                    seen_ids.add(event_id)
                all_matches.append(_parse_upcoming_match(m))

            page += 1

        except Exception as e:
            print(f"  ⚠️ Error en get_team_next_matches página {page}: {e}")
            break

    all_matches.sort(key=lambda x: (x["date"], x["time"]))
    return all_matches[:limit]


def search_tournament(name: str) -> list[dict]:
    """Busca torneos por nombre y devuelve lista de {id, name, country}."""
    time.sleep(1.0)
    url = f"{BASE_URL}/tournaments/search"
    try:
        resp = requests.get(url, headers=HEADERS,
                            params={"name": name}, timeout=10)
        resp.raise_for_status()
        tournaments = resp.json().get("uniqueTournaments", [])
        return [
            {
                "id":      t["id"],
                "name":    t.get("name", "?"),
                "country": t.get("category", {}).get("name", ""),
            }
            for t in tournaments
            if t.get("category", {}).get("sport", {}).get("slug") == "football"
        ]
    except Exception as e:
        print(f"  ⚠️ Error en search_tournament: {e}")
        return []


def get_tournament_current_season_id(tournament_id: int) -> int | None:
    """
    Devuelve el id de la temporada actual del torneo. SofaScore lista
    las temporadas de mas reciente a mas vieja, asi que tomamos la
    primera de la lista.
    """
    time.sleep(1.0)
    url = f"{BASE_URL}/tournaments/get-seasons"
    try:
        resp = requests.get(url, headers=HEADERS,
                            params={"tournamentId": str(tournament_id)},
                            timeout=10)
        resp.raise_for_status()
        seasons = resp.json().get("seasons", [])
        return seasons[0]["id"] if seasons else None
    except Exception as e:
        print(f"  ⚠️ Error en get_tournament_current_season_id: {e}")
        return None


def get_tournament_fixtures(tournament_id: int, season_id: int,
                            max_pages: int = 4) -> list[dict]:
    """
    Obtiene los proximos partidos programados del torneo (todas las
    fechas/rondas futuras que la API tenga cargadas).
    """
    all_matches = []
    seen_ids    = set()
    page = 0

    while page < max_pages:
        time.sleep(1.0)
        url = f"{BASE_URL}/tournaments/get-next-matches"
        params = {
            "tournamentId": str(tournament_id),
            "seasonId":     str(season_id),
            "page":         str(page),
        }

        try:
            resp = requests.get(url, headers=HEADERS,
                                params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                break

            raw_events = data.get("events", [])
            if not raw_events:
                break

            for m in raw_events:
                event_id = m.get("id")
                if event_id is not None and event_id in seen_ids:
                    continue
                if m.get("status", {}).get("type") == "finished":
                    continue
                if event_id is not None:
                    seen_ids.add(event_id)
                all_matches.append(_parse_upcoming_match(m))

            page += 1

        except Exception as e:
            print(f"  ⚠️ Error en get_tournament_fixtures página {page}: {e}")
            break

    all_matches.sort(key=lambda x: (x["date"], x["time"]))
    return all_matches


def _parse_upcoming_match(m: dict) -> dict:
    """Convierte un evento crudo de SofaScore (aun no jugado) a formato interno."""
    ts = m.get("startTimestamp", 0)
    dt = datetime.fromtimestamp(ts)

    round_info  = m.get("roundInfo", {})
    tournament  = m.get("tournament", {})

    return {
        "event_id":      m.get("id"),
        "date":          dt.strftime("%Y-%m-%d"),
        "time":          dt.strftime("%H:%M"),
        "team_home":     m.get("homeTeam", {}).get("name", "Unknown"),
        "team_away":     m.get("awayTeam", {}).get("name", "Unknown"),
        "team_home_id":  m.get("homeTeam", {}).get("id"),
        "team_away_id":  m.get("awayTeam", {}).get("id"),
        "competition":   tournament.get("name", "Unknown"),
        "round":         round_info.get("round"),
        "round_name":    round_info.get("name")
                          or (f"Fecha {round_info['round']}"
                              if round_info.get("round") is not None else "Fecha ?"),
    }
