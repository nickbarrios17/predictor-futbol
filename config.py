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
N_SIMULATIONS      = 10_000

# ── IA local ───────────────────────────────────────────────────
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_HOST  = "http://localhost:11434"

# ── Caché ──────────────────────────────────────────────────────
CACHE_DIR         = "cache"
CACHE_HOURS_TEAMS = 24
CACHE_HOURS_CTX   = 6

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
# FIX Bug 1: agregado "group_meaningless" que faltaba y causaba KeyError.
STAKES_WEIGHT = {
    "final":               1.00,
    "semifinal":           0.97,
    "quarterfinal":        0.94,
    "round_of_16":         0.91,
    "round_of_32":         0.88,
    "group_must_win":      0.90,
    "group_stage":         0.75,
    "group_meaningless":   0.45,   # ← AGREGADO: faltaba y causaba KeyError
    "qualifier_decisive":  0.88,
    "qualifier_normal":    0.80,
    "league_title":        0.88,
    "league_relegation":   0.87,
    "league_normal":       0.80,
    "league_meaningless":  0.45,
    "friendly_competitive":0.50,
    "friendly_normal":     0.35,
    "friendly_rotation":   0.20,
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
