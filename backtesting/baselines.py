"""
Baselines simples para comparar el modelo principal.

La idea no es reemplazar el predictor, sino tener rivales faciles de
entender. Si el modelo no les gana, hay que revisar la mejora antes de
sumar mas complejidad.
"""
from backtesting.metrics import calcular_metricas


def uniform_baseline(
    real_home: int,
    real_away: int,
    over25_prob: float = 50.0,
    btts_prob: float = 50.0,
) -> dict:
    """Modelo sin informacion: 33.3% para cada resultado."""
    return calcular_metricas(
        prob_home=33.3,
        prob_draw=33.4,
        prob_away=33.3,
        over25_prob=over25_prob,
        btts_prob=btts_prob,
        real_home=real_home,
        real_away=real_away,
    )


def elo_simple_baseline(
    elo_a: int | float,
    elo_b: int | float,
    venue: str,
    real_home: int,
    real_away: int,
    over25_prob: float = 50.0,
    btts_prob: float = 50.0,
) -> dict:
    """
    Baseline 1X2 basada solo en diferencia Elo.

    Reserva una probabilidad fija de empate y reparte el resto segun una
    curva logistica Elo. Es simple a proposito: sirve como vara minima.
    """
    elo_a = float(elo_a or 1600)
    elo_b = float(elo_b or 1600)

    venue_bonus = 0.0
    if venue == "home_a":
        venue_bonus = 60.0
    elif venue == "home_b":
        venue_bonus = -60.0

    diff = elo_a - elo_b + venue_bonus
    p_a_no_draw = 1 / (1 + 10 ** (-diff / 400))

    p_draw = 0.26
    remaining = 1 - p_draw
    p_home = remaining * p_a_no_draw
    p_away = remaining * (1 - p_a_no_draw)

    return calcular_metricas(
        prob_home=round(p_home * 100, 1),
        prob_draw=round(p_draw * 100, 1),
        prob_away=round(p_away * 100, 1),
        over25_prob=over25_prob,
        btts_prob=btts_prob,
        real_home=real_home,
        real_away=real_away,
    )
