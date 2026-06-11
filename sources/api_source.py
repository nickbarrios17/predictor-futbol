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
    """Busca equipos y devuelve una lista de diccionarios {id, name}."""
    time.sleep(1.5)
    url = f"{BASE_URL}/teams/search"
    querystring = {"name": name}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=querystring, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        teams = data.get("teams", [])
        
        # Filtramos resultados
        resultados = []
        for t in teams:
            # Filtramos por fútbol
            if t.get("sport", {}).get("slug") == "football":
                resultados.append({
                    "id": t.get("id"),
                    "name": t.get("name", "Desconocido")
                })
        return resultados
    except Exception as e:
        print(f"  ⚠️ Error en search_team: {e}")
        return []

def get_team_matches(team_id: int, limit: int = 25) -> list[dict]:
    """Obtiene los últimos partidos de un equipo con debug integrado."""
    time.sleep(1.5)
    url = f"{BASE_URL}/teams/get-last-matches"
    querystring = {"teamId": str(team_id)}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=querystring, timeout=10)
        resp.raise_for_status()
        json_data = resp.json()
        
        # --- DEBUG LOGS ---
        print(f"DEBUG API: Respuesta recibida para ID {team_id}")
        # Intentamos obtener eventos de la estructura estándar
        raw_events = json_data.get("events", [])
        print(f"DEBUG API: Cantidad de eventos encontrados: {len(raw_events)}")
        
        if len(raw_events) == 0:
            print("DEBUG API: No hay eventos. JSON puede estar vacío o en otra estructura.")
            return []

    except Exception as e:
        print(f"  ⚠️ Error en get_team_matches: {e}")
        return []

    # Filtrar solo partidos finalizados
    finished_matches = [
        m for m in raw_events 
        if m.get("status", {}).get("code") == 100 or m.get("status", {}).get("type") == "finished"
    ]
    
    # Parsear
    parsed_matches = [_parse_match(m) for m in finished_matches if _is_valid(m)]
    return parsed_matches[:limit]

def _is_valid(m: dict) -> bool:
    """Valida si el partido tiene datos de goles."""
    home_score = m.get("homeScore", {})
    away_score = m.get("awayScore", {})
    return home_score.get("current") is not None and away_score.get("current") is not None

def _parse_match(m: dict) -> dict:
    """Extrae la información relevante del JSON crudo."""
    timestamp = m.get("startTimestamp", 0)
    match_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    
    return {
        "date": match_date,
        "team_home": m.get("homeTeam", {}).get("name", "Unknown"),
        "team_away": m.get("awayTeam", {}).get("name", "Unknown"),
        "goals_home": m.get("homeScore", {}).get("current"),
        "goals_away": m.get("awayScore", {}).get("current"),
        "competition": m.get("tournament", {}).get("name", "Unknown")
    }