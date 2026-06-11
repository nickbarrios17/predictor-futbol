# model/monte_carlo.py
import numpy as np
from collections import Counter
from config import N_SIMULATIONS, HOME_ADVANTAGE
from model.match_context import MatchContext


def simular(
    lambda_a: float,
    lambda_b: float,
    venue:    str          = "neutral",
    context:  MatchContext = None,
    verbose:  bool         = False,
) -> dict:
    """
    Corre N_SIMULATIONS partidos simulados con Poisson
    aplicando todos los ajustes de contexto.

    venue: "home_a" | "home_b" | "neutral"
    """
    ctx = context or MatchContext()

    # Guardar lambdas base para el reporte verbose
    lam_a_base, lam_b_base = lambda_a, lambda_b

    # ── 1. Ventaja de sede ────────────────────────────────────
    if venue == "home_a":
        lambda_a *= HOME_ADVANTAGE
    elif venue == "home_b":
        lambda_b *= HOME_ADVANTAGE

    # ── 2. Intensidad del partido ─────────────────────────────
    intensity = ctx.intensity()
    lambda_a *= intensity
    lambda_b *= intensity

    # ── 3. Motivación individual ──────────────────────────────
    lambda_a *= ctx.motivation_factor("a")
    lambda_b *= ctx.motivation_factor("b")

    # ── 4. Ajuste de vuelta (ida/vuelta) ──────────────────────
    mult_a, mult_b = ctx.second_leg_adjustment()
    lambda_a *= mult_a
    lambda_b *= mult_b

    # ── 5. Ajuste H2H ─────────────────────────────────────────
    lambda_a, lambda_b = ctx.h2h_adjustment(lambda_a, lambda_b)

    # Evitar lambdas negativos o absurdamente altos
    lambda_a = max(0.10, min(lambda_a, 6.0))
    lambda_b = max(0.10, min(lambda_b, 6.0))

    # ── Simulación ────────────────────────────────────────────
    rng = np.random.default_rng()
    goles_a = rng.poisson(lambda_a, N_SIMULATIONS)
    goles_b = rng.poisson(lambda_b, N_SIMULATIONS)
    total   = goles_a + goles_b

    # ── Resultados ────────────────────────────────────────────
    v_a    = np.mean(goles_a > goles_b)
    empate = np.mean(goles_a == goles_b)
    v_b    = np.mean(goles_b > goles_a)

    marcadores = Counter(zip(goles_a.tolist(), goles_b.tolist()))
    top5 = [
        (f"{g[0]}-{g[1]}", round(c / N_SIMULATIONS * 100, 1))
        for g, c in marcadores.most_common(5)
    ]

    ou = {
        "over_05":  round(np.mean(total > 0.5)  * 100, 1),
        "over_15":  round(np.mean(total > 1.5)  * 100, 1),
        "over_25":  round(np.mean(total > 2.5)  * 100, 1),
        "over_35":  round(np.mean(total > 3.5)  * 100, 1),
        "under_05": round(np.mean(total <= 0.5) * 100, 1),
        "under_15": round(np.mean(total <= 1.5) * 100, 1),
        "under_25": round(np.mean(total <= 2.5) * 100, 1),
        "under_35": round(np.mean(total <= 3.5) * 100, 1),
    }

    btts_si = round(np.mean((goles_a > 0) & (goles_b > 0)) * 100, 1)

    result = {
        "victoria_a":     round(v_a    * 100, 1),
        "empate":         round(empate * 100, 1),
        "victoria_b":     round(v_b    * 100, 1),
        "lambda_a":       round(lambda_a, 3),
        "lambda_b":       round(lambda_b, 3),
        "top_marcadores": top5,
        "ou":             ou,
        "btts_si":        btts_si,
        "btts_no":        round(100 - btts_si, 1),
        "context":        ctx.summary(),
    }

    if verbose:
        result["lambdas_detalle"] = {
            "base":         (round(lam_a_base, 3), round(lam_b_base, 3)),
            "post_sede":    (round(lambda_a / intensity, 3),
                             round(lambda_b / intensity, 3)),
            "intensity":    intensity,
            "motivation":   (ctx.motivation_factor("a"),
                             ctx.motivation_factor("b")),
            "second_leg":   (mult_a, mult_b),
            "final":        (round(lambda_a, 3), round(lambda_b, 3)),
        }

    return result