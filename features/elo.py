# features/elo.py — v1.2
"""
Sistema de Elo Rating para ajustar la fuerza del rival.

Estrategia de tres capas:
  1. Ratings base predefinidos para los ~150 equipos más conocidos
     (selecciones nacionales + clubes top europeos y sudamericanos).
  2. Cálculo dinámico desde el historial: actualiza el rating base
     a partir de los partidos que ya tenemos en caché.
  3. Fallback: si un equipo no está en ninguna lista, asigna
     el rating promedio de la competición donde juega.

Uso del Elo en el modelo:
  opponent_factor = opponent_elo / competition_avg_elo

  Ejemplo:
    Francia (Elo 2050) → factor = 2050/1750 = 1.17
    Bolivia (Elo 1450) → factor = 1450/1750 = 0.83

  Entonces los goles se ajustan:
    goles_ajustados = goles_reales × opponent_factor
    goles_recibidos_ajustados = goles_recibidos / opponent_factor

  Efecto: un 3-0 contra Francia vale MUCHO más que un 3-0 contra Bolivia.
"""

from __future__ import annotations
import math
from datetime import datetime


# ── Constantes del sistema Elo ─────────────────────────────────
ELO_K_FACTOR = 20      # sensibilidad a cambios (estándar FIFA: 20)
ELO_DEFAULT  = 1500    # rating de un equipo desconocido


# ── Promedios por competición ──────────────────────────────────
# Usado para calcular el opponent_factor relativo.
COMPETITION_AVG_ELO = {
    "FIFA World Cup":              1780,
    "UEFA Champions League":       1850,
    "UEFA European Championship":  1760,
    "Copa America":                1720,
    "Africa Cup of Nations":       1580,
    "Copa Libertadores":           1680,
    "Copa Sudamericana":           1620,
    "UEFA Nations League":         1700,
    "UEFA Europa League":          1720,
    "World Cup Qualification":     1600,
    "UEFA Euro Qualification":     1650,
    "CONCACAF Nations League":     1550,
    "CONCACAF Gold Cup":           1530,
    "Premier League":              1800,
    "La Liga":                     1790,
    "Bundesliga":                  1780,
    "Serie A":                     1760,
    "Ligue 1":                     1720,
    "Int. Friendly Games":         1600,
    "default":                     1600,
}


# ── Ratings base predefinidos ──────────────────────────────────
# Fuente: eloratings.net + clubelo.com (junio 2026, aproximados)
# Ordenados por categoría para facilitar mantenimiento.
BASE_RATINGS: dict[str, int] = {

    # ── Selecciones Europeas ───────────────────────────────────
    "Spain":              2050,
    "France":             2020,
    "England":            1980,
    "Germany":            1960,
    "Portugal":           1940,
    "Netherlands":        1920,
    "Belgium":            1900,
    "Italy":              1890,
    "Croatia":            1860,
    "Denmark":            1840,
    "Switzerland":        1820,
    "Austria":            1800,
    "Sweden":             1780,
    "Norway":             1760,
    "Turkey":             1740,
    "Czech Republic":     1720,
    "Poland":             1700,
    "Hungary":            1680,
    "Scotland":           1660,
    "Serbia":             1700,
    "Ukraine":            1680,
    "Wales":              1650,
    "Greece":             1620,
    "Slovakia":           1610,
    "Romania":            1600,
    "Russia":             1640,

    # ── Selecciones Sudamericanas ──────────────────────────────
    "Argentina":          2080,
    "Brazil":             2000,
    "Colombia":           1820,
    "Uruguay":            1800,
    "Chile":              1760,
    "Ecuador":            1720,
    "Peru":               1680,
    "Venezuela":          1620,
    "Paraguay":           1640,
    "Bolivia":            1480,

    # ── Selecciones de Concacaf ────────────────────────────────
    "United States":      1780,
    "USA":                1780,
    "Mexico":             1760,
    "Canada":             1720,
    "Costa Rica":         1640,
    "Jamaica":            1560,
    "Honduras":           1540,
    "Panama":             1560,
    "El Salvador":        1480,
    "Cuba":               1380,

    # ── Selecciones de Africa ──────────────────────────────────
    "Morocco":            1780,
    "Senegal":            1720,
    "Egypt":              1700,
    "Nigeria":            1680,
    "Cameroon":           1640,
    "Ghana":              1620,
    "Ivory Coast":        1660,
    "Tunisia":            1600,
    "Algeria":            1640,
    "South Africa":       1540,
    "Mali":               1560,
    "Congo DR":           1520,

    # ── Selecciones de Asia ────────────────────────────────────
    "Japan":              1780,
    "South Korea":        1740,
    "Iran":               1700,
    "Australia":          1680,
    "Saudi Arabia":       1620,
    "Qatar":              1560,
    "Iraq":               1560,
    "Uzbekistan":         1580,
    "Jordan":             1500,

    # ── Selecciones de Concacaf / Otras ───────────────────────
    "Bosnia & Herzegovina": 1660,
    "BiH":                1660,

    # ── Clubes europeos top ────────────────────────────────────
    "Real Madrid":        2050,
    "Manchester City":    2020,
    "Bayern Munich":      2000,
    "Liverpool":          1980,
    "Arsenal":            1940,
    "Barcelona":          1960,
    "Paris Saint-Germain":1940,
    "PSG":                1940,
    "Chelsea":            1900,
    "Atletico Madrid":    1900,
    "Inter Milan":        1880,
    "AC Milan":           1860,
    "Juventus":           1840,
    "Borussia Dortmund":  1840,
    "Napoli":             1820,
    "Bayer Leverkusen":   1860,
    "RB Leipzig":         1800,
    "Manchester United":  1820,
    "Tottenham":          1780,
    "Newcastle":          1760,
    "Aston Villa":        1760,
    "Benfica":            1780,
    "Porto":              1760,
    "Ajax":               1780,
    "Feyenoord":          1760,

    # ── Clubes sudamericanos ───────────────────────────────────
    "River Plate":        1820,
    "Boca Juniors":       1800,
    "Flamengo":           1820,
    "Palmeiras":          1800,
    "Atletico Mineiro":   1760,
    "Fluminense":         1740,
    "Gremio":             1700,
    "Internacional":      1680,
    "Racing Club":        1720,
    "Independiente":      1680,
    "San Lorenzo":        1660,
    "Nacional":           1680,
    "Penarol":            1660,
    "LDU Quito":          1640,
    "Estudiantes":        1660,


    # ── Aliases y nombres alternativos ────────────────────────
    # Nombres en español / variantes que devuelve SofaScore
    "Wales":              1650,
    "Gales":              1650,
    "Italy":              1890,
    "Italia":             1890,
    "Ireland":            1640,
    "Irlanda":            1640,
    "Republic of Ireland":1640,
    "Ivory Coast":        1660,
    "Cote d'Ivoire":      1660,
    "Côte d'Ivoire":      1660,
    "Costa de Marfil":    1660,
    "North Macedonia":    1560,
    "Macedonia del Norte":1560,
    "Suriname":           1440,
    "Haiti":              1380,
    "Cape Verde":         1520,
    "Cabo Verde":         1520,
    "Korea Republic":     1740,
    "South Korea":        1740,
    "Corea del Sur":      1740,
    "DR Congo":           1520,
    "Congo DR":           1520,
    "Congo RD":           1520,
    "Saudi Arabia":       1620,
    "Arabia Saudita":     1620,
    "United Arab Emirates":1520,
    "New Zealand":        1500,
    "Nueva Zelanda":      1500,
    "Jamaica":            1560,
    "Guatemala":          1480,
    "Trinidad and Tobago":1480,
    "Cuba":               1380,
    "Panama":             1560,
    "Panamá":             1560,
    "Honduras":           1540,
    "El Salvador":        1480,
    "Ecuador":            1720,
    "Peru":               1680,
    "Perú":               1680,
    "Venezuela":          1620,
    "Paraguay":           1640,
    "Bolivia":            1480,
    "Chile":              1760,
    "Algeria":            1640,
    "Argelia":            1640,
    "Tunisia":            1600,
    "Túnez":              1600,
    "Cameroon":           1640,
    "Camerún":            1640,
    "Nigeria":            1680,
    "Ghana":              1620,
    "Senegal":            1720,
    "Egypt":              1700,
    "Egipto":             1700,
    "Morocco":            1780,
    "Marruecos":          1780,
    "South Africa":       1540,
    "Sudáfrica":          1540,
    "Uganda":             1480,
    "Zimbabwe":           1440,
    "Mozambique":         1380,
    # ── Clubes mexicanos ───────────────────────────────────────
    "Club America":       1700,
    "Chivas":             1680,
    "Cruz Azul":          1660,
    "Tigres UANL":        1680,
    "Monterrey":          1660,
    "Pumas":              1620,
    "Santos Laguna":      1600,
    "Toluca":             1600,
}


# ── Clase principal ────────────────────────────────────────────

class EloRating:
    """
    Calcula y actualiza ratings Elo para equipos de fútbol.

    Los ratings se pueden actualizar dinámicamente a partir
    del historial de partidos, mejorando la precisión inicial.
    """

    def __init__(self):
        # Copia mutable de los ratings base
        self._ratings: dict[str, float] = {
            k: float(v) for k, v in BASE_RATINGS.items()
        }
        self._match_count: dict[str, int] = {}

    def get_rating(self, team_name: str,
                   competition: str = "default") -> float:
        """
        Devuelve el rating Elo de un equipo.
        Si no está registrado, devuelve el promedio de la competición.
        """
        # Búsqueda exacta
        if team_name in self._ratings:
            return self._ratings[team_name]

        # Búsqueda parcial (ej: "Bosnia" matchea "Bosnia & Herzegovina")
        team_lower = team_name.lower()
        for key, rating in self._ratings.items():
            if (key.lower() in team_lower or
                    team_lower in key.lower()):
                return rating

        # Fallback: promedio de la competición
        avg = self.get_competition_avg(competition)
        print(f"  ℹ️  Elo no encontrado para '{team_name}' "
              f"→ usando promedio competición: {avg}")
        return float(avg)

    def get_competition_avg(self, competition: str) -> float:
        """Promedio Elo de la competición."""
        comp_lower = competition.lower()
        for key, avg in COMPETITION_AVG_ELO.items():
            if key.lower() in comp_lower:
                return float(avg)
        return float(COMPETITION_AVG_ELO["default"])

    def get_opponent_factor(self, opponent_name: str,
                            competition: str = "default") -> float:
        """
        Calcula el factor de ajuste por calidad del rival.

        opponent_factor = opponent_elo / competition_avg_elo

        > 1.0 → rival más fuerte que el promedio → goles valen más
        < 1.0 → rival más débil → goles valen menos

        Ejemplos con competición avg = 1750:
          Francia (2020) → 2020/1750 = 1.154
          Bolivia (1480) → 1480/1750 = 0.846
        """
        opponent_elo = self.get_rating(opponent_name, competition)
        comp_avg     = self.get_competition_avg(competition)
        factor       = opponent_elo / comp_avg

        # Clamp suave: máximo ±40% de ajuste
        # Evita distorsiones extremas con rivales muy outliers
        return max(0.60, min(factor, 1.40))

    def update_from_matches(self, matches: list[dict],
                             team_name: str) -> None:
        """
        Actualiza el rating del equipo a partir de su historial.
        Usa el algoritmo estándar de Elo.

        Solo actualiza si tenemos suficientes partidos (>= 5)
        para que el rating converja a un valor significativo.
        """
        if len(matches) < 5:
            return

        # Ordenar de más viejo a más nuevo para actualizar en orden
        sorted_matches = sorted(matches, key=lambda m: m.get("date", ""))

        current_elo = self.get_rating(team_name)

        for m in sorted_matches:
            es_local   = m.get("team_home") == team_name
            rival      = m.get("team_away") if es_local else m.get("team_home")
            gf         = (m.get("goals_home", 0) if es_local
                          else m.get("goals_away", 0)) or 0
            gc         = (m.get("goals_away", 0) if es_local
                          else m.get("goals_home", 0)) or 0
            comp       = m.get("competition", "default")

            rival_elo  = self.get_rating(rival, comp)

            # Score real: W=1, D=0.5, L=0
            if gf > gc:   score = 1.0
            elif gf == gc: score = 0.5
            else:          score = 0.0

            # Score esperado (fórmula Elo estándar)
            expected = 1 / (1 + 10 ** ((rival_elo - current_elo) / 400))

            # Actualizar
            current_elo += ELO_K_FACTOR * (score - expected)

        # Guardar rating actualizado
        self._ratings[team_name] = current_elo
        self._ratings[rival]     = rival_elo   # actualizar también al rival

    def summary(self, team_name: str,
                competition: str = "default") -> dict:
        """Resumen del rating para mostrar en la UI."""
        elo    = self.get_rating(team_name, competition)
        avg    = self.get_competition_avg(competition)
        factor = self.get_opponent_factor(team_name, competition)
        return {
            "team":       team_name,
            "elo":        round(elo),
            "comp_avg":   round(avg),
            "factor":     round(factor, 3),
            "categoria":  _categoria(elo),
        }


def _categoria(elo: float) -> str:
    """Categoría descriptiva del rating."""
    if elo >= 2000: return "Elite mundial"
    if elo >= 1850: return "Top mundial"
    if elo >= 1750: return "Muy fuerte"
    if elo >= 1650: return "Fuerte"
    if elo >= 1550: return "Competitivo"
    if elo >= 1450: return "Promedio"
    return "Débil"


# ── Instancia global (singleton) ──────────────────────────────
# Se crea una sola vez y se reutiliza en toda la sesión.
# Esto permite que update_from_matches() acumule mejoras.
_elo_instance: EloRating | None = None


def get_elo() -> EloRating:
    """Devuelve la instancia global del sistema Elo."""
    global _elo_instance
    if _elo_instance is None:
        _elo_instance = EloRating()
    return _elo_instance


def get_opponent_factor(opponent_name: str,
                        competition: str = "default") -> float:
    """Shortcut para obtener el factor de ajuste de un rival."""
    return get_elo().get_opponent_factor(opponent_name, competition)
