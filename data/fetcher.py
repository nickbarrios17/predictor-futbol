# data/fetcher.py
"""
Obtiene el historial de partidos de un equipo.

Cambios clave respecto a versión anterior:
  - La caché ahora guarda la fecha de creación dentro del JSON,
    no depende solo del mtime del archivo (más confiable en Windows).
  - force_refresh=True para invalidar caché manualmente.
  - Mejor logging del estado de la caché.
"""
import os
import json
import time
import difflib
from datetime import datetime, timezone

from sources.api_source import search_team, get_team_matches
from config import CACHE_DIR, CACHE_HOURS_TEAMS, N_MATCHES

TEAMS_CACHE_DIR = os.path.join(CACHE_DIR, "teams")
os.makedirs(TEAMS_CACHE_DIR, exist_ok=True)


# ── Caché ─────────────────────────────────────────────────────

def _cache_path(team_id) -> str:
    return os.path.join(TEAMS_CACHE_DIR, f"{team_id}.json")


def _read_cache(team_id) -> list[dict] | None:
    path = _cache_path(team_id)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # La caché guarda la hora de creación dentro del JSON
        saved_at_str = data.get("_saved_at")
        if not saved_at_str:
            # Caché vieja sin timestamp → invalidar
            print(f"  🗑️  Caché sin timestamp → descartando")
            return None

        saved_at = datetime.fromisoformat(saved_at_str)
        now      = datetime.now(timezone.utc).replace(tzinfo=None)
        age_h    = (now - saved_at.replace(tzinfo=None)).total_seconds() / 3600

        if age_h > CACHE_HOURS_TEAMS:
            print(f"  🗑️  Caché vencida ({age_h:.1f}h > {CACHE_HOURS_TEAMS}h) → actualizando")
            return None

        matches = data.get("matches", [])
        print(f"  📦 Caché válida ({age_h:.1f}h) → {len(matches)} partidos")
        return matches

    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _write_cache(team_id, matches: list[dict]) -> None:
    path = _cache_path(team_id)
    try:
        data = {
            "_saved_at": datetime.now(timezone.utc).isoformat(),
            "matches":   matches,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"  ⚠️  No se pudo escribir caché: {e}")


def clear_cache(team_id=None):
    """
    Borra la caché de un equipo específico o de todos.
    Útil para forzar actualización de datos.
    """
    if team_id:
        path = _cache_path(team_id)
        if os.path.exists(path):
            os.remove(path)
            print(f"  🗑️  Caché borrada para ID {team_id}")
    else:
        for f in os.listdir(TEAMS_CACHE_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(TEAMS_CACHE_DIR, f))
        print("  🗑️  Toda la caché de equipos borrada")


# ── Matching de nombre ────────────────────────────────────────

def _best_match(team_name: str, candidatos: list[dict]) -> dict | None:
    """
    Elige el candidato más parecido al nombre buscado.
    Primero busca match exacto, luego por similitud.
    """
    if not candidatos:
        return None

    nombre_lower = team_name.strip().lower()

    # Match exacto
    for c in candidatos:
        if c.get("name", "").strip().lower() == nombre_lower:
            return c

    # Match por similitud
    mejor       = None
    mejor_score = -1.0
    for c in candidatos:
        score = difflib.SequenceMatcher(
            None, nombre_lower,
            c.get("name", "").strip().lower()
        ).ratio()
        if score > mejor_score:
            mejor_score = score
            mejor = c

    if mejor_score < 0.4:
        print(f"  ⚠️  Coincidencia baja ({mejor_score:.2f}) → "
              f"'{team_name}' mapeado a '{mejor.get('name')}'. "
              f"Verificá el nombre.")
    return mejor


# ── Función principal ─────────────────────────────────────────

def fetch_matches(team_name: str,
                  team_type: str = "default",
                  force_refresh: bool = False) -> list[dict]:
    """
    Busca los últimos partidos de un equipo.

    Flujo:
      1. Buscar el equipo en la API para obtener su ID
      2. Revisar caché local (si existe y es reciente, usarla)
      3. Si no hay caché válida, consultar la API con paginación
    """
    print(f"\nDEBUG: Consultando equipo: {team_name}")

    candidatos = search_team(team_name)
    if not candidatos:
        print(f"  ❌ No se encontró '{team_name}' en la API.")
        return []

    equipo = _best_match(team_name, candidatos)
    if not equipo:
        return []

    team_id   = equipo["id"]
    team_name_api = equipo["name"]
    print(f"DEBUG: Equipo '{team_name}' mapeado a '{team_name_api}' (ID: {team_id})")

    # Forzar limpieza si se pide
    if force_refresh:
        clear_cache(team_id)

    limit = N_MATCHES.get(team_type, N_MATCHES["default"])

    # Intentar caché
    # El archivo de caché guarda el batch completo (limit+10, para tener
    # margen de filtrado), así que hay que recortarlo igual que en el
    # camino de cache-miss. Si no, un cache-hit devuelve mas partidos
    # de los que team_type pide.
    cached = _read_cache(team_id)
    if cached is not None:
        return cached[:limit]

    # Consultar API con paginación
    # Pedimos más de lo necesario para tener margen de filtrado
    matches = get_team_matches(team_id, limit=limit + 10)

    if not matches:
        print(f"  ❌ La API no devolvió partidos para ID {team_id}")
        return []

    print(f"DEBUG: Se obtuvieron {len(matches)} partidos válidos para el ID {team_id}")

    # Guardar en caché con timestamp
    _write_cache(team_id, matches)

    return matches[:limit]
