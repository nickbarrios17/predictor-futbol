# model/context.py
"""
Calcula el peso de cada partido histórico según competición e
importancia de la ronda.
"""
from config import COMPETITION_WEIGHT, STAKES_WEIGHT

_ROUND_MAP = {
    "final":            ["final"],
    "semifinal":        ["semi"],
    "quarterfinal":     ["quarter", "cuarto"],
    "round_of_16":      ["round of 16", "octavos", "last 16"],
    "round_of_32":      ["round of 32"],
    "group_stage":      ["group", "grupo", "matchday", "jornada"],
    "qualifier_normal": ["qualif", "clasif"],
    "friendly_normal":  ["friendly", "amistoso"],
}


def get_competition_weight(competition: str) -> float:
    comp = competition.lower()
    for key, w in COMPETITION_WEIGHT.items():
        if key.lower() in comp:
            return w
    return COMPETITION_WEIGHT["Unknown"]


def get_stakes_weight(competition: str, round_name: str = "") -> float:
    """
    Detecta la importancia del partido histórico a partir del texto
    de competición/ronda y devuelve su peso.
    """
    text = f"{competition} {round_name}".lower()

    for stake_key, keywords in _ROUND_MAP.items():
        if any(kw in text for kw in keywords):
            return STAKES_WEIGHT.get(stake_key, 0.80)

    # Si es liga → league_normal por defecto
    return STAKES_WEIGHT["league_normal"]


def get_all_weights(match: dict) -> dict:
    """
    Entrada: un partido del historial.
    Salida: diccionario con todos sus pesos.
    """
    comp  = match.get("competition", "Unknown")
    round_= match.get("round", "")

    w_comp   = get_competition_weight(comp)
    w_stakes = get_stakes_weight(comp, round_)

    return {
        "w_comp":     w_comp,
        "w_stakes":   w_stakes,
        "w_combined": w_comp * w_stakes,
    }