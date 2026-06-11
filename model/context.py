# model/context.py
"""
Calcula el peso de cada partido histórico
según competición, importancia y alineación.
"""
from config import (COMPETITION_WEIGHT, STAKES_WEIGHT,
                    LINEUP_WEIGHT)

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


def get_stakes_weight(competition: str, round_name: str = "",
                      ctx: dict = None) -> float:
    """
    Detecta la importancia del partido histórico
    y devuelve su peso.
    """
    ctx = ctx or {}

    # Override manual tiene prioridad
    if "stakes" in ctx:
        return STAKES_WEIGHT.get(ctx["stakes"], 0.80)

    text = f"{competition} {round_name}".lower()

    for stake_key, keywords in _ROUND_MAP.items():
        if any(kw in text for kw in keywords):
            if stake_key == "group_stage":
                if ctx.get("group_situation") == "must_win":
                    return STAKES_WEIGHT["group_must_win"]
                if ctx.get("meaningless"):
                    return STAKES_WEIGHT["group_meaningless"]
                return STAKES_WEIGHT["group_stage"]
            if stake_key == "friendly_normal":
                if ctx.get("rotation"):
                    return STAKES_WEIGHT["friendly_rotation"]
                return STAKES_WEIGHT["friendly_normal"]
            return STAKES_WEIGHT.get(stake_key, 0.80)

    # Si es liga → league_normal por defecto
    return STAKES_WEIGHT["league_normal"]


def get_lineup_weight(ctx: dict = None) -> float:
    ctx = ctx or {}
    lineup = ctx.get("lineup", "unknown")
    return LINEUP_WEIGHT.get(lineup, LINEUP_WEIGHT["unknown"])


def get_all_weights(match: dict) -> dict:
    """
    Entrada: un partido del historial.
    Salida: diccionario con todos sus pesos.
    """
    ctx   = match.get("context", {})
    comp  = match.get("competition", "Unknown")
    round_= match.get("round", "")

    w_comp   = get_competition_weight(comp)
    w_stakes = get_stakes_weight(comp, round_, ctx)
    w_lineup = get_lineup_weight(ctx)

    return {
        "w_comp":   w_comp,
        "w_stakes": w_stakes,
        "w_lineup": w_lineup,
        "w_combined": w_comp * w_stakes * w_lineup,
    }