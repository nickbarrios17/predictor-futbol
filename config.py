# config.py
import os
# ── Modelo ────────────────────────────────────────────────────
N_MATCHES = {
    "seleccion":  15,
    "club_top":   25,
    "club_menor": 18,
    "default":    20,
}
MAX_MONTHS_HISTORY = 30   
DECAY_RATE         = 0.08  # Ajustado para dar más peso a lo reciente
N_SIMULATIONS      = 10_000
HOME_ADVANTAGE     = 1.10  # Ajustado un poco hacia abajo para mundiales

# ── API SofaScore (RapidAPI) ──────────────────────────────────
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

# ── IA local con Ollama ───────────────────────────────────────
OLLAMA_MODEL   = "llama3.1:8b"
OLLAMA_HOST    = "http://localhost:11434"

# ── Caché ─────────────────────────────────────────────────────
CACHE_DIR         = "cache"
CACHE_HOURS_TEAMS = 24    
CACHE_HOURS_CTX   = 6     

# ── Pesos por competición (Ajustados para más realismo) ──────
COMPETITION_WEIGHT = {
    "FIFA World Cup":              1.00,
    "UEFA Champions League":       0.98,
    "UEFA European Championship":  0.97,
    "Copa America":                0.96,
    "Africa Cup of Nations":       0.94,
    "Copa Libertadores":           0.93,
    "Copa Sudamericana":           0.91,
    "World Cup Qualification":     0.88,
    "AFC Asian Cup":               0.80,
    "EAFF E-1 Football Championship": 0.65,
    "Int. Friendly Games":         0.40,  # Amistosos pesan mucho menos
    "Unknown":                     0.60,
}

# ── Pesos por importancia del partido ─────────────────────────
STAKES_WEIGHT = {
    "final":               1.00,
    "semifinal":           0.97,
    "quarterfinal":        0.94,
    "round_of_16":         0.91,
    "group_must_win":      0.95,
    "group_stage":         0.75,
    "qualifier_decisive":  0.88,
    "qualifier_normal":    0.80,
    "league_title":        0.88,
    "league_normal":       0.80,
    "friendly_competitive":0.50, # Amistosos pesan poco
    "friendly_normal":     0.35, # Amistosos pesan poco
    "friendly_rotation":   0.20,
}

# ── Pesos por alineación ──────────────────────────────────────
LINEUP_WEIGHT = {
    "full":    1.00,
    "rotation":0.75,
    "reserves":0.40,
    "youth":   0.25,
    "unknown": 0.85,
}

# ── Intensidad del partido a predecir ─────────────────────────
MATCH_INTENSITY = {
    "final_mundial":        0.80,
    "group_normal":         1.00,
    "league_normal":        1.00,
    "friendly_competitive": 0.90,
    "friendly_normal":      0.80,
    "friendly_rotation":    0.65,
}

# ── Motivación individual ─────────────────────────────────────
TEAM_MOTIVATION = {
    "must_win":  1.10,
    "normal":    1.00,
    "can_draw":  0.95,
    "already_in":0.80,
    "rotation":  0.70,
}

H2H_WEIGHT = 0.20