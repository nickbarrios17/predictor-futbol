# data/fetcher.py
"""
Obtiene el historial de partidos de un equipo, con:
  - Matching por similitud de nombre (no solo "el primero").
  - Caché local en disco para no repetir consultas el mismo día.
"""
import os
import json
import time
import difflib

from sources.api_source import search_team, get_team_matches
from config import CACHE_DIR, CACHE_HOURS_TEAMS, N_MATCHES


def _cache_path(team_id) -> str:
    return os.path.join(CACHE_DIR, "teams", f"{team_id}.json")


def _read_cache(team_id) -> list[dict] | None:
    path = _cache_path(team_id)
    if not os.path.exists(path):
        return None

    age_hours = (time.time() - os.path.getmtime(path)) / 3600
    if age_hours > CACHE_HOURS_TEAMS:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(team_id, matches: list[dict]) -> None:
    os.makedirs(os.path.join(CACHE_DIR, "teams"), exist_ok=True)
    path = _cache_path(team_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"  ⚠️  No se pudo escribir caché para {team_id}: {e}")


def _best_match(team_name: str, candidatos: list[dict]) -> dict | None:
    """
    Elige el candidato cuyo nombre sea más parecido a team_name,
    en vez de asumir que el primero es siempre el correcto.
    """
    if not candidatos:
        return None

    nombre_buscado = team_name.strip().lower()

    mejor = None
    mejor_score = -1.0

    for c in candidatos:
        nombre_candidato = c.get("name", "").strip().lower()

        if nombre_candidato == nombre_buscado:
            return c  # match exacto, listo

        score = difflib.SequenceMatcher(None, nombre_buscado, nombre_candidato).ratio()
        if score > mejor_score:
            mejor_score = score
            mejor = c

    # Umbral mínimo de similitud para evitar mapear a un equipo totalmente distinto
    if mejor_score < 0.4:
        print(
            f"  ⚠️  Coincidencia muy baja ({mejor_score:.2f}) entre "
            f"'{team_name}' y '{mejor.get('name')}'. Verificá el nombre del equipo."
        )

    return mejor


def fetch_matches(team_name: str, team_type: str = "default") -> list[dict]:
    """
    Busca partidos en la API de SofaScore para un equipo dado.
    Usa matching por similitud de nombre y caché local para no
    repetir la misma consulta varias veces el mismo día.
    """
    print(f"DEBUG: Consultando equipo: {team_name}")

    candidatos = search_team(team_name)

    if not candidatos:
        print(f"DEBUG: ¡Alerta! No se encontró ningún equipo llamado '{team_name}' en la API.")
        return []

    equipo_encontrado = _best_match(team_name, candidatos)
    if equipo_encontrado is None:
        return []

    id_encontrado = equipo_encontrado["id"]
    nombre_encontrado = equipo_encontrado["name"]

    print(f"DEBUG: Equipo '{team_name}' mapeado a '{nombre_encontrado}' (ID: {id_encontrado})")

    # 1. Intentar caché
    cached = _read_cache(id_encontrado)
    if cached is not None:
        print(f"DEBUG: Usando caché ({len(cached)} partidos) para ID {id_encontrado}")
        return cached

    # 2. Consultar API
    limit = N_MATCHES.get(team_type, N_MATCHES["default"])
    matches = get_team_matches(id_encontrado, limit=limit)

    if not matches:
        print(f"DEBUG: ¡Alerta! La API devolvió 0 partidos para el ID {id_encontrado}")
    else:
        print(f"DEBUG: Se obtuvieron {len(matches)} partidos válidos para el ID {id_encontrado}")
        _write_cache(id_encontrado, matches)

    return matches
