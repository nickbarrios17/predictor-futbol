# model/monte_carlo.py — v1.1
"""
Simulación Monte Carlo con Poisson.

Cambios v1.1:
  - Nueva fórmula de lambda usando attack/defense por sede.
    Si A juega de local:
      λ_A = avg_home_goals × attack_home_A × defense_away_B
      λ_B = avg_away_goals × attack_away_B × defense_home_A
    Esto es la fórmula estándar de Dixon & Coles (1997).

  - HOME_ADVANTAGE eliminado del cálculo de lambdas.
    La ventaja local ya está implícita en attack_home vs attack_away
    y en defense_home vs defense_away. Aplicar un multiplicador
    adicional era el doble efecto del Bug 3.

  - Sin seed fijo → resultados distintos en cada simulación.
  - Sin clamp artificial → los lambdas normalizados no lo necesitan.
"""
import numpy as np
from collections import Counter
from config import N_SIMULATIONS, LEAGUE_AVG_GOALS
from model.match_context import MatchContext


def _get_avg(competition: str) -> tuple[float, float]:
    """
    Devuelve (avg_home_goals, avg_away_goals) de la competición.
    Usa la asimetría real: equipos locales marcan más que visitantes.
    """
    comp_lower = competition.lower()
    for key, avg in LEAGUE_AVG_GOALS.items():
        if key.lower() in comp_lower:
            # Distribución típica: 58% local / 42% visitante
            return avg * 1.10, avg * 0.90
    avg = LEAGUE_AVG_GOALS["default"]
    return avg * 1.10, avg * 0.90


def simular(
    strength_a: dict,
    strength_b: dict,
    venue:      str          = "neutral",
    context:    MatchContext = None,
    verbose:    bool         = False,
) -> dict:
    """
    Corre N_SIMULATIONS partidos con Poisson.

    Parámetros:
        strength_a / strength_b → dicts devueltos por calcular_lambda()
        venue → "home_a" | "home_b" | "neutral"
        context → MatchContext con ajustes contextuales
    """
    ctx = context or MatchContext()

    competition = ctx.competition or "default"
    avg_home, avg_away = _get_avg(competition)

    # ── Seleccionar ataque/defensa según sede ──────────────────
    if venue == "home_a":
        # A juega de local, B de visitante
        att_a = strength_a.get("attack_home",  strength_a.get("attack_global",  1.0))
        def_a = strength_a.get("defense_home", strength_a.get("defense_global", 1.0))
        att_b = strength_b.get("attack_away",  strength_b.get("attack_global",  1.0))
        def_b = strength_b.get("defense_away", strength_b.get("defense_global", 1.0))
        # FIX Bug 3: la ventaja local ya está en home vs away stats.
        # NO multiplicar por HOME_ADVANTAGE.
        lambda_a = avg_home * att_a * def_b
        lambda_b = avg_away * att_b * def_a

    elif venue == "home_b":
        # B juega de local, A de visitante
        att_a = strength_a.get("attack_away",  strength_a.get("attack_global",  1.0))
        def_a = strength_a.get("defense_away", strength_a.get("defense_global", 1.0))
        att_b = strength_b.get("attack_home",  strength_b.get("attack_global",  1.0))
        def_b = strength_b.get("defense_home", strength_b.get("defense_global", 1.0))
        lambda_a = avg_away * att_a * def_b
        lambda_b = avg_home * att_b * def_a

    else:
        # Cancha neutral: usar promedios globales y avg neutro
        avg_neutral = (avg_home + avg_away) / 2
        att_a = strength_a.get("attack_global",  1.0)
        def_a = strength_a.get("defense_global", 1.0)
        att_b = strength_b.get("attack_global",  1.0)
        def_b = strength_b.get("defense_global", 1.0)
        lambda_a = avg_neutral * att_a * def_b
        lambda_b = avg_neutral * att_b * def_a

    lam_a_base, lam_b_base = lambda_a, lambda_b

    print(f"  📥 λ base → A: {lambda_a:.3f} | B: {lambda_b:.3f} | sede: {venue}")

    # ── Ajustes contextuales ───────────────────────────────────
    intensity = ctx.intensity()
    lambda_a *= intensity
    lambda_b *= intensity

    lambda_a *= ctx.motivation_factor("a")
    lambda_b *= ctx.motivation_factor("b")

    mult_a, mult_b = ctx.second_leg_adjustment()
    lambda_a *= mult_a
    lambda_b *= mult_b

    # FIX Problema 3 (H2H): h2h_adjustment ahora verifica
    # mínimo de partidos y antigüedad antes de aplicar.
    lambda_a, lambda_b = ctx.h2h_adjustment(lambda_a, lambda_b)

    # Los lambdas normalizados raramente superan 3.5.
    # Si lo hacen, es señal de datos anómalos.
    lambda_a = max(0.10, lambda_a)
    lambda_b = max(0.10, lambda_b)

    print(f"  📤 λ final → A: {lambda_a:.3f} | B: {lambda_b:.3f} "
          f"| intensidad: {intensity}")

    # ── Simulación ─────────────────────────────────────────────
    rng     = np.random.default_rng()   # sin seed fijo
    goles_a = rng.poisson(lambda_a, N_SIMULATIONS)
    goles_b = rng.poisson(lambda_b, N_SIMULATIONS)
    total   = goles_a + goles_b

    # ── Resultados ─────────────────────────────────────────────
    v_a    = np.mean(goles_a > goles_b)
    empate = np.mean(goles_a == goles_b)
    v_b    = np.mean(goles_b > goles_a)

    marcadores = Counter(zip(goles_a.tolist(), goles_b.tolist()))
    top10 = [
        (f"{g[0]}-{g[1]}", round(c / N_SIMULATIONS * 100, 1))
        for g, c in marcadores.most_common(10)
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
        # FIX Bug 2: redondear solo al mostrar, no internamente.
        # Los valores de probabilidad sí se redondean porque son
        # el output final que va a la UI.
        "victoria_a":     round(v_a    * 100, 1),
        "empate":         round(empate * 100, 1),
        "victoria_b":     round(v_b    * 100, 1),
        "lambda_a":       round(lambda_a, 3),   # solo 3 decimales al mostrar
        "lambda_b":       round(lambda_b, 3),
        "top_marcadores": top10,
        "ou":             ou,
        "btts_si":        btts_si,
        "btts_no":        round(100 - btts_si, 1),
        "context":        ctx.summary(),
    }

    if verbose:
        result["lambdas_detalle"] = {
            "base":       (round(lam_a_base, 3), round(lam_b_base, 3)),
            "post_sede":  (round(lam_a_base, 3), round(lam_b_base, 3)),
            "intensity":  intensity,
            "motivation": (ctx.motivation_factor("a"),
                           ctx.motivation_factor("b")),
            "second_leg": (mult_a, mult_b),
            "final":      (round(lambda_a, 3), round(lambda_b, 3)),
        }

    return result
