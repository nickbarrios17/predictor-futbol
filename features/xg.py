# features/xg.py — v2.0
"""
Módulo de Expected Goals (xG) — Arquitectura preparada.

Estado actual: los campos xG se guardan en el dict de fuerzas
pero el modelo usa goles reales como fuente principal.
Cuando haya datos de xG disponibles (FBref para ligas top),
se mezclan con los goles reales con un peso configurable.

Fuentes de xG gratuitas:
  - FBref.com: ligas top europeas + Champions + World Cup
  - Understat.com: 6 ligas top europeas solamente
  - Para selecciones y otras competiciones: no disponible gratis

Uso futuro:
  lambda_final = XG_WEIGHT * lambda_xg + (1 - XG_WEIGHT) * lambda_goals
"""
import httpx
from bs4 import BeautifulSoup
from config import CACHE_DIR
import os, json, time

# Peso del xG en el lambda final cuando hay datos disponibles
XG_WEIGHT = 0.30   # 30% xG + 70% goles reales (según literatura)

XG_CACHE_DIR = os.path.join(CACHE_DIR, "xg")
os.makedirs(XG_CACHE_DIR, exist_ok=True)

FBREF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def get_xg_stats(team_name: str,
                  competition: str = "") -> dict:
    """
    Intenta obtener estadísticas de xG para un equipo.

    Devuelve:
    {
      "xg_for":     float | None,   # xG a favor por partido
      "xg_against": float | None,   # xG en contra por partido
      "xg_home":    float | None,
      "xg_away":    float | None,
      "xg_last5":   float | None,   # xG a favor últimos 5
      "source":     str | None,
      "available":  bool
    }

    Si no hay datos disponibles, devuelve None en todos los campos
    y available=False. El modelo funciona igual sin xG.
    """
    # Verificar si la competición tiene datos en FBref
    if not _has_fbref_data(competition):
        return _empty_xg()

    # Intentar desde caché primero
    cache_key  = f"{team_name.lower().replace(' ', '_')}_{competition[:20].lower().replace(' ', '_')}"
    cache_path = os.path.join(XG_CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_path):
        age_h = (time.time() - os.path.getmtime(cache_path)) / 3600
        if age_h < 48:   # caché de xG válida 48h
            with open(cache_path) as f:
                return json.load(f)

    # Intentar scrapear FBref
    xg_data = _scrape_fbref(team_name, competition)

    if xg_data["available"]:
        with open(cache_path, "w") as f:
            json.dump(xg_data, f)

    return xg_data


def _has_fbref_data(competition: str) -> bool:
    """FBref tiene datos de xG solo para competiciones top."""
    comp = competition.lower()
    supported = [
        "premier league", "la liga", "bundesliga",
        "serie a", "ligue 1", "champions league",
        "europa league", "world cup", "european championship",
    ]
    return any(s in comp for s in supported)


def _scrape_fbref(team_name: str, competition: str) -> dict:
    """
    Scraping básico de FBref para obtener xG.
    Solo funciona para equipos de ligas top.
    """
    try:
        # FBref tiene una URL predecible para búsqueda de equipos
        search_url = f"https://fbref.com/en/search/search.fcgi?search={team_name.replace(' ', '+')}"
        resp = httpx.get(search_url, headers=FBREF_HEADERS,
                         timeout=10, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscar tabla de stats del equipo
        # FBref tiene columnas "xG" y "xGA" en la tabla de resultados
        xg_cells  = soup.find_all("td", {"data-stat": "xg"})
        xga_cells = soup.find_all("td", {"data-stat": "xga"})

        if not xg_cells:
            return _empty_xg()

        xg_values  = []
        xga_values = []

        for cell in xg_cells[:15]:   # últimos 15 partidos
            try:
                val = float(cell.get_text(strip=True))
                xg_values.append(val)
            except (ValueError, TypeError):
                pass

        for cell in xga_cells[:15]:
            try:
                val = float(cell.get_text(strip=True))
                xga_values.append(val)
            except (ValueError, TypeError):
                pass

        if not xg_values:
            return _empty_xg()

        return {
            "xg_for":     round(sum(xg_values)  / len(xg_values),  2),
            "xg_against": round(sum(xga_values) / len(xga_values), 2) if xga_values else None,
            "xg_home":    None,   # Se puede separar en v2.1
            "xg_away":    None,
            "xg_last5":   round(sum(xg_values[-5:]) / min(5, len(xg_values)), 2),
            "source":     "fbref",
            "available":  True,
        }

    except Exception as e:
        print(f"  ℹ️  xG no disponible para '{team_name}': {e}")
        return _empty_xg()


def blend_lambda_with_xg(lambda_goals: float,
                          xg_for: float | None) -> float:
    """
    Mezcla el lambda basado en goles con el xG.

    lambda_final = 0.7 * lambda_goals + 0.3 * xg_for

    Si no hay xG disponible, devuelve lambda_goals sin cambios.
    """
    if xg_for is None:
        return lambda_goals
    blended = (1 - XG_WEIGHT) * lambda_goals + XG_WEIGHT * xg_for
    print(f"  ⚡ xG blend: {lambda_goals:.3f} → {blended:.3f} "
          f"(xG={xg_for})")
    return blended


def _empty_xg() -> dict:
    return {
        "xg_for":     None,
        "xg_against": None,
        "xg_home":    None,
        "xg_away":    None,
        "xg_last5":   None,
        "source":     None,
        "available":  False,
    }
