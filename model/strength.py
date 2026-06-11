# model/strength.py
"""
Calcula la fuerza ofensiva y defensiva de un equipo
a partir de su historial ponderado.
"""
import math
from datetime import date, datetime
from config  import DECAY_RATE, HOME_ADVANTAGE, MAX_MONTHS_HISTORY
from model.context import get_all_weights


def time_decay(match_date_str: str) -> float:
    """Partidos más recientes pesan más."""
    try:
        match_date = datetime.strptime(match_date_str,
                                       "%Y-%m-%d").date()
    except ValueError:
        return 0.5   # fecha inválida → peso bajo
    months_ago = (date.today() - match_date).days / 30
    return math.exp(-DECAY_RATE * months_ago)


def is_too_old(match_date_str: str) -> bool:
    """Descarta partidos más viejos que MAX_MONTHS_HISTORY."""
    try:
        match_date = datetime.strptime(match_date_str,
                                       "%Y-%m-%d").date()
    except ValueError:
        return True
    months_ago = (date.today() - match_date).days / 30
    return months_ago > MAX_MONTHS_HISTORY


def calcular_lambda(matches: list[dict], team_name: str,
                    verbose: bool = False) -> dict:
    """
    Calcula lambda_ataque y lambda_defensa del equipo.

    Pondera cada partido por:
      w_total = time_decay × w_comp × w_stakes × w_lineup
    """
    goles_favor  = 0.0
    goles_contra = 0.0
    peso_total   = 0.0
    partidos_usados = 0
    desglose = []

    for m in matches:
        # Descartar partidos demasiado viejos
        if is_too_old(m["date"]):
            continue

        w_time  = time_decay(m["date"])
        pesos   = get_all_weights(m)
        es_local = m["team_home"] == team_name

        # Peso base
        w = w_time * pesos["w_combined"]

        # Normalizar ventaja local para no inflar el ataque
        if es_local:
            gf = m["goals_home"]
            gc = m["goals_away"]
            w_adj = w / HOME_ADVANTAGE
        else:
            gf = m["goals_away"]
            gc = m["goals_home"]
            w_adj = w

        goles_favor  += gf * w_adj
        goles_contra += gc * w_adj
        peso_total   += w_adj
        partidos_usados += 1

        if verbose:
            rival = m["team_away"] if es_local else m["team_home"]
            desglose.append({
                "fecha":      m["date"],
                "rival":      rival,
                "goles":      f"{gf}-{gc}",
                "sede":       "L" if es_local else "V",
                "comp":       m.get("competition", "?")[:25],
                "w_time":     round(w_time, 3),
                "w_comp":     round(pesos["w_comp"], 3),
                "w_stakes":   round(pesos["w_stakes"], 3),
                "w_lineup":   round(pesos["w_lineup"], 3),
                "w_total":    round(w_adj, 4),
            })

    if peso_total == 0:
        raise ValueError(f"Sin datos válidos para '{team_name}'. "
                         f"Verificá el nombre del equipo.")

    resultado = {
        "team":             team_name,
        "lambda_ataque":    round(goles_favor  / peso_total, 3),
        "lambda_defensa":   round(goles_contra / peso_total, 3),
        "partidos_usados":  partidos_usados,
    }
    if verbose:
        resultado["desglose"] = desglose

    return resultado