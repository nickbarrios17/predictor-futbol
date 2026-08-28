# model/monte_carlo.py — v2.0
"""
Modelo de marcador Dixon-Coles (Poisson bivariado con correccion de
baja puntuacion), calculado de forma analitica en vez de por
simulacion Monte Carlo.

Cambios v2.0:
  - Se reemplazo el muestreo aleatorio (rng.poisson × N_SIMULATIONS)
    por una grilla de probabilidad exacta P(x, y) para cada posible
    marcador, con la correccion tau de Dixon & Coles (1997) aplicada
    a los marcadores bajos (0-0, 1-0, 0-1, 1-1). Dos ventajas:
      1. Es la pieza que faltaba para llamarse "Dixon-Coles" de
         verdad — antes solo se usaba su formula de ataque×defensa,
         sin la correccion de correlacion que le da nombre al metodo.
      2. Es determinista: la misma prediccion con los mismos datos
         ya no cambia levemente cada vez que se recalcula.
  - El nombre del archivo quedo igual por compatibilidad con el
    resto del proyecto (predictor.py, backtesting, worldcup.py),
    aunque ya no hace Monte Carlo.

Cambios v1.1 (se mantienen):
  - Formula de lambda usando attack/defense por sede.
    Si A juega de local:
      λ_A = avg_home_goals × attack_home_A × defense_away_B
      λ_B = avg_away_goals × attack_away_B × defense_home_A
  - HOME_ADVANTAGE eliminado del cálculo de lambdas.
    La ventaja local ya está implícita en attack_home vs attack_away
    y en defense_home vs defense_away. Aplicar un multiplicador
    adicional era el doble efecto del Bug 3.
"""
import numpy as np
from scipy.stats import poisson as _poisson
from config import LEAGUE_AVG_GOALS, MAX_GOALS_GRID, DIXON_COLES_RHO
from model.match_context import MatchContext


def _get_avg(competition: str) -> tuple[float, float]:
    """
    Devuelve (avg_home_goals, avg_away_goals) de la competición.

    Ambos valores son iguales a propósito: la ventaja de localía ya
    la capturan por separado attack_home/attack_away y
    defense_home/defense_away de cada equipo (ver strength.py), que
    salen del propio historial local/visitante del equipo. Aplicar
    ademas un +10%/-10% aca duplicaba el efecto (un equipo con split
    real de 2.5 vs 0.9 goles quedaba en ~3.4 vs 0.8 en vez de 2.5 vs 0.9).
    """
    comp_lower = competition.lower()
    for key, avg in LEAGUE_AVG_GOALS.items():
        if key.lower() in comp_lower:
            return avg, avg
    avg = LEAGUE_AVG_GOALS["default"]
    return avg, avg


def _score_grid(lambda_a: float, lambda_b: float) -> np.ndarray:
    """
    Grilla de probabilidad P(goles_A=x, goles_B=y) para
    x, y en [0, MAX_GOALS_GRID], con la correccion tau de
    Dixon-Coles (1997) aplicada a los 4 marcadores bajos.

    Sin la correccion, un Poisson bivariado independiente
    (P(x,y) = Pois(x;λ_A) × Pois(y;λ_B)) tiende a des/sobreestimar
    0-0, 1-0, 0-1 y 1-1 frente a lo que se observa en partidos
    reales, porque el resultado parcial cambia como juegan los
    equipos (un 0-0 no es tan independiente entre ambos lados
    como en el resto de los marcadores).
    """
    xs = np.arange(MAX_GOALS_GRID + 1)
    px = _poisson.pmf(xs, lambda_a)
    py = _poisson.pmf(xs, lambda_b)
    grid = np.outer(px, py)  # grid[x, y] = P(x) * P(y), independiente

    rho = DIXON_COLES_RHO
    grid[0, 0] *= 1 - lambda_a * lambda_b * rho
    grid[0, 1] *= 1 + lambda_a * rho
    grid[1, 0] *= 1 + lambda_b * rho
    grid[1, 1] *= 1 - rho

    grid = np.clip(grid, 0, None)  # por si rho lo manda negativo con λ extremos
    grid /= grid.sum()             # renormalizar: tau cambia la masa total
    return grid


def simular(
    strength_a: dict,
    strength_b: dict,
    venue:      str          = "neutral",
    context:    MatchContext = None,
    verbose:    bool         = False,
) -> dict:
    """
    Calcula las probabilidades del partido con el modelo Dixon-Coles
    (grilla de Poisson bivariado exacta, sin simulacion aleatoria).

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

    lambda_a *= ctx.lineup_factor("a")
    lambda_b *= ctx.lineup_factor("b")

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

    # ── Grilla de probabilidad (Dixon-Coles) ────────────────────
    grid = _score_grid(lambda_a, lambda_b)
    xs   = np.arange(MAX_GOALS_GRID + 1)
    X, Y = np.meshgrid(xs, xs, indexing="ij")  # X[i,j]=goles A, Y[i,j]=goles B
    total = X + Y

    # ── Resultados ─────────────────────────────────────────────
    v_a    = grid[X > Y].sum()
    empate = grid[X == Y].sum()
    v_b    = grid[X < Y].sum()

    flat_order = np.argsort(-grid, axis=None)[:10]
    top_idx    = np.unravel_index(flat_order, grid.shape)
    top10 = [
        (f"{x}-{y}", round(float(grid[x, y]) * 100, 1))
        for x, y in zip(*top_idx)
    ]

    ou = {
        "over_05":  round(float(grid[total > 0.5].sum())  * 100, 1),
        "over_15":  round(float(grid[total > 1.5].sum())  * 100, 1),
        "over_25":  round(float(grid[total > 2.5].sum())  * 100, 1),
        "over_35":  round(float(grid[total > 3.5].sum())  * 100, 1),
        "under_05": round(float(grid[total <= 0.5].sum()) * 100, 1),
        "under_15": round(float(grid[total <= 1.5].sum()) * 100, 1),
        "under_25": round(float(grid[total <= 2.5].sum()) * 100, 1),
        "under_35": round(float(grid[total <= 3.5].sum()) * 100, 1),
    }

    btts_si = round(float(grid[(X > 0) & (Y > 0)].sum()) * 100, 1)

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
            # "base" ya incluye la ventaja de sede (viene de attack_home
            # vs attack_away / defense_home vs defense_away), no hay un
            # paso "post sede" separado.
            "base":       (round(lam_a_base, 3), round(lam_b_base, 3)),
            "intensity":  intensity,
            "motivation": (ctx.motivation_factor("a"),
                           ctx.motivation_factor("b")),
            "lineup":     (ctx.lineup_factor("a"),
                           ctx.lineup_factor("b")),
            "second_leg": (mult_a, mult_b),
            "final":      (round(lambda_a, 3), round(lambda_b, 3)),
        }

    return result
