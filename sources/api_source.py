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
