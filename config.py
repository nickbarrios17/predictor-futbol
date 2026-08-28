# config.py — v1.1
import os
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "TU_CLAVE_REAL_ACA")
if RAPIDAPI_KEY == "TU_CLAVE_REAL_ACA" or not RAPIDAPI_KEY:
    print("¡ALERTA! La variable RAPIDAPI_KEY no está cargada correctamente.")
else:
    print("DEBUG: Clave detectada correctamente.")

# ── Historial ──────────────────────────────────────────────────
N_MATCHES = {
    "seleccion":  15,
    "club_top":   25,
    "club_menor": 18,
    "default":    20,
}
MAX_MONTHS_HISTORY = 30
DECAY_RATE         = 0.08

# ── Modelo de marcador (Dixon-Coles) ────────────────────────────
# Grilla de probabilidad analitica en vez de simulacion Monte Carlo:
# exacta (sin ruido aleatorio) y mas rapida. MAX_GOALS_GRID acota los
# marcadores considerados (por encima de eso la probabilidad es
# despreciable para lambdas de futbol reales).
MAX_GOALS_GRID   = 10
# Parametro de correlacion de baja puntuacion del paper original de
# Dixon & Coles (1997) para la liga inglesa (~-0.13). Ajusta la
# probabilidad de 0-0, 1-0, 0-1 y 1-1, que el Poisson independiente
# por si solo sobre/subestima. No esta re-ajustado con datos propios.
DIXON_COLES_RHO  = -0.13

# ── Gemini ─────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-3.6-flash"

# ── Caché ──────────────────────────────────────────────────────
CACHE_DIR         = "cache"
CACHE_HOURS_TEAMS = 24
CACHE_HOURS_CTX   = 6

# Proximos partidos de un equipo: pueden reprogramarse, TTL corto.
CACHE_HOURS_NEXT_MATCHES        = 12
# Fixture de un torneo completo (todas las fechas futuras): cuesta
# ~1 pedido por equipo de la fecha (28 equipos en una liga de 14
# partidos), asi que conviene un TTL largo. Pensado para uso semanal
# (una fecha por vez), asi que 6 dias cubre toda la semana sin
# gastar cuota de nuevo y se refresca solo para la fecha siguiente.
CACHE_HOURS_TOURNAMENT_FIXTURES = 24 * 6

# ── Ventaja local ──────────────────────────────────────────────
# FIX Bug 3: HOME_ADVANTAGE solo se aplica en la simulación final.
# Ya NO se usa en strength.py para dividir el peso histórico.
# Antes se aplicaba dos veces (÷ en historial y × en simulación).
HOME_ADVANTAGE = 1.10

# ── Promedio de goles de liga (para normalización de lambdas) ──
# FIX Problema 1: nueva fórmula de lambda normalizada.
# Estos promedios se usan para calcular attack_strength y defense_strength.
# Fuente: promedios reales de competiciones internacionales y ligas top.
LEAGUE_AVG_GOALS = {
    # Selecciones
    "FIFA World Cup":              1.30,   # promedio goles/equipo/partido
    "UEFA European Championship":  1.25,
    "Copa America":                1.20,
    "Africa Cup of Nations":       1.10,
    "UEFA Nations League":         1.35,
    "World Cup Qualification":     1.40,
    "UEFA Euro Qualification":     1.50,
    "CONCACAF Nations League":     1.45,
    "Int. Friendly Games":         1.35,
    # Clubes europeos
    "UEFA Champions League":       1.40,
    "UEFA Europa League":          1.45,
    "Premier League":              1.45,
    "La Liga":                     1.35,
    "Bundesliga":                  1.55,
    "Serie A":                     1.30,
    "Ligue 1":                     1.35,
    # Clubes sudamericanos
    "Copa Libertadores":           1.25,
    "Copa Sudamericana":           1.30,
    # Default
    "default":                     1.35,
}

# ── Pesos por competición ──────────────────────────────────────
COMPETITION_WEIGHT = {
    "FIFA World Cup":              1.00,
    "UEFA Champions League":       0.98,
    "UEFA European Championship":  0.97,
    "Copa America":                0.96,
    "Africa Cup of Nations":       0.94,
    "Copa Libertadores":           0.93,
    "Copa Sudamericana":           0.91,
    "UEFA Nations League":         0.90,
    "UEFA Europa League":          0.89,
    "World Cup Qualification":     0.88,
    "UEFA Euro Qualification":     0.85,
    "CONCACAF Nations League":     0.84,
    "Premier League":              0.87,
    "La Liga":                     0.87,
    "Bundesliga":                  0.86,
    "Serie A":                     0.86,
    "Ligue 1":                     0.85,
    "AFC Asian Cup":               0.80,
    "CONCACAF Gold Cup":           0.82,
    "Int. Friendly Games":         0.40,
    "Unknown":                     0.60,
}

# ── Pesos por importancia del partido histórico ────────────────
# Solo quedan las categorias que get_stakes_weight() puede detectar
# de verdad por texto (competicion/ronda). Habia mas categorias
# (group_must_win, group_meaningless, qualifier_decisive, league_title,
# league_relegation, league_meaningless, friendly_competitive,
# friendly_rotation) que dependian de flags en match["context"], pero
# ese dict siempre llega vacio desde la API (ver api_source.py) — nunca
# se activaban con datos reales. Se sacaron para no sugerir una
# sofisticacion que no existe.
STAKES_WEIGHT = {
    "final":               1.00,
    "semifinal":           0.97,
    "quarterfinal":        0.94,
    "round_of_16":         0.91,
    "round_of_32":         0.88,
    "group_stage":         0.75,
    "qualifier_normal":    0.80,
    "league_normal":       0.80,
    "friendly_normal":     0.35,
}

# ── Pesos por alineación ───────────────────────────────────────
LINEUP_WEIGHT = {
    "full":     1.00,
    "rotation": 0.75,
    "reserves": 0.40,
    "youth":    0.25,
    "unknown":  0.85,
}

# ── Intensidad del partido a predecir ─────────────────────────
MATCH_INTENSITY = {
    "final_champions":      0.82,
    "final_libertadores":   0.84,
    "final_sudamericana":   0.86,
    "final_mundial":        0.80,
    "final_eurocopa":       0.81,
    "final_copa_america":   0.83,
    "final_local":          0.88,
    "semi_champions":       0.88,
    "semi_mundial":         0.87,
    "semi_local":           0.91,
    "knockout_early":       0.95,
    "group_must_win":       1.05,
    "group_normal":         1.00,
    "group_meaningless":    0.88,
    "qualifier_decisive":   1.02,
    "qualifier_normal":     1.00,
    "league_title":         1.03,
    "league_relegation":    1.04,
    "league_normal":        1.00,
    "league_meaningless":   0.85,
    "friendly_competitive": 0.90,
    "friendly_normal":      0.80,
    "friendly_rotation":    0.65,
}

# ── Motivación individual ──────────────────────────────────────
TEAM_MOTIVATION = {
    "must_win":  1.10,
    "normal":    1.00,
    "can_draw":  0.95,
    "already_in":0.80,
    "rotation":  0.70,
}

# ── H2H ───────────────────────────────────────────────────────
# FIX Problema 3: reducido de 0.20 a 0.05.
# Solo se aplica si hay >= 5 partidos en los últimos 3 años.
# Con menos partidos o más viejos se ignora completamente.
H2H_WEIGHT          = 0.05
H2H_MIN_MATCHES     = 5     # mínimo de partidos H2H para activarlo
H2H_MAX_YEARS       = 3     # solo H2H de los últimos N años
