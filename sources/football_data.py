# sources/football_data.py — v1.0
"""
Único punto de import para el resto de la app: expone las mismas 6
funciones que sources/api_source.py, pero eligiendo la fuente.

API-Football (api-sports.io) es la fuente primaria — más cuota
efectiva por día y sin la paginación de a 10 de SofaScore. Si se agotó
la cuota diaria (o falla duro: red, timeout, 5xx) cae a
sources/api_source.py (SofaScore/RapidAPI).

Un resultado vacío "de verdad" (equipo/torneo no encontrado en
API-Football) NO dispara el fallback — se devuelve tal cual, como
siempre. El fallback es solo por cuota agotada o fallo duro, para no
gastar de más la cuota mucho más escasa de SofaScore (500/15 días) en
cada miss normal.

IDs con prefijo de fuente:
Los IDs de equipo/torneo de API-Football y SofaScore son numeros de
espacios completamente distintos (mismo numero, equipos distintos). Si
search_team()/search_tournament() resuelven un ID en una fuente pero
la siguiente llamada (get_team_matches, etc.) decidiera la fuente de
nuevo por su cuenta, un cambio de cuota justo en el medio haria que se
consulte el ID equivocado en la fuente equivocada. Para evitar eso, los
IDs que devuelve este modulo vienen taggeados ("af_123" / "ss_123") y
las funciones siguientes enrutan de forma deterministica segun ese
prefijo, sin volver a mirar la cuota.
"""
import requests

from sources import api_football_source as primary
from sources import api_source as fallback
from sources import football_quota

_PRIMARY_PREFIX  = "af_"
_FALLBACK_PREFIX = "ss_"


def _tag(raw_id, prefix: str) -> str:
    return f"{prefix}{raw_id}"


def _untag(tagged_id):
    """(source_module, id_original) a partir de un id con prefijo de fuente."""
    s = str(tagged_id)
    if s.startswith(_PRIMARY_PREFIX):
        return primary, s[len(_PRIMARY_PREFIX):]
    if s.startswith(_FALLBACK_PREFIX):
        return fallback, s[len(_FALLBACK_PREFIX):]
    raise ValueError(
        f"id sin prefijo de fuente: {tagged_id!r} — ¿se generó fuera de "
        f"football_data.search_team()/search_tournament()?"
    )


def _resolve(fn_name: str, *args, **kwargs) -> list[dict]:
    """Para search_team/search_tournament: elige fuente y taggea los IDs."""
    primary_fn  = getattr(primary, fn_name)
    fallback_fn = getattr(fallback, fn_name)

    if football_quota.has_budget():
        try:
            results = primary_fn(*args, **kwargs)
            return [{**r, "id": _tag(r["id"], _PRIMARY_PREFIX)} for r in results]
        except primary.QuotaExceeded:
            print(f"  ⚠️  Cuota de API-Football agotada -> fallback a SofaScore ({fn_name})")
        except (requests.RequestException, RuntimeError) as e:
            print(f"  ⚠️  API-Football fallo en {fn_name} ({e}) -> fallback a SofaScore")
    else:
        print(f"  ℹ️  Sin cuota de API-Football hoy -> usando SofaScore ({fn_name})")

    results = fallback_fn(*args, **kwargs)
    return [{**r, "id": _tag(r["id"], _FALLBACK_PREFIX)} for r in results]


def _dispatch(tagged_id, fn_name: str, *args, **kwargs):
    """
    Para las funciones que reciben un ID ya resuelto: enruta según el
    prefijo, sin volver a chequear cuota. Si la fuente que resolvió el
    ID falla ahora (p.ej. se quedó sin cuota justo después de la
    búsqueda), no hay a dónde caer -- ese ID no existe en la otra
    fuente -- así que se devuelve vacío, igual que un "no encontrado".
    """
    source, raw_id = _untag(tagged_id)
    fn = getattr(source, fn_name)
    try:
        return fn(raw_id, *args, **kwargs)
    except primary.QuotaExceeded:
        print(f"  ⚠️  Cuota de API-Football agotada a mitad de resolución ({fn_name})")
        return [] if fn_name != "get_tournament_current_season_id" else None
    except (requests.RequestException, RuntimeError) as e:
        print(f"  ⚠️  Error en {fn_name} ({e})")
        return [] if fn_name != "get_tournament_current_season_id" else None


def search_team(name: str) -> list[dict]:
    return _resolve("search_team", name)


def get_team_matches(team_id, limit: int = 20) -> list[dict]:
    return _dispatch(team_id, "get_team_matches", limit=limit)


def get_team_next_matches(team_id, limit: int = 5) -> list[dict]:
    return _dispatch(team_id, "get_team_next_matches", limit=limit)


def search_tournament(name: str) -> list[dict]:
    return _resolve("search_tournament", name)


def get_tournament_current_season_id(tournament_id) -> int | None:
    return _dispatch(tournament_id, "get_tournament_current_season_id")


def get_tournament_fixtures(tournament_id, season_id, max_pages: int = 1) -> list[dict]:
    return _dispatch(tournament_id, "get_tournament_fixtures", season_id, max_pages=max_pages)
