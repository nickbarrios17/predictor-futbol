# predictor.py
"""
Punto de entrada único del sistema.

predecir() coordina todas las capas:
  1. data/fetcher        -> historial de partidos (API + caché)
  2. agents/context_agent -> contexto del partido vía web + IA local (Ollama)
  3. model/strength       -> lambdas de ataque/defensa por equipo
  4. model/monte_carlo    -> simulación y probabilidades finales
"""
from data.fetcher import fetch_matches
from model.strength import calcular_lambda
from model.monte_carlo import simular
from model.match_context import MatchContext
from agents.context_agent import get_match_context


def _racha_resumen(strength: dict) -> str:
    """Texto corto con la forma reciente del equipo, para pasarle al agente de IA."""
    return (
        f"{strength['partidos_usados']} partidos analizados, "
        f"promedio {strength['lambda_ataque']} goles a favor / "
        f"{strength['lambda_defensa']} en contra (ponderado)."
    )


def predecir(
    equipo_a: str,
    equipo_b: str,
    venue: str = "neutral",
    competition: str = "",
    team_type: str = "default",
    verbose: bool = False,
    noticias: str = None,
) -> dict:
    """
    venue: "home_a" | "home_b" | "neutral"
    team_type: clave de N_MATCHES en config.py ("seleccion", "club_top", etc.)
    """

    # ── 1. Historial de partidos ──────────────────────────────
    matches_a = fetch_matches(equipo_a, team_type)
    matches_b = fetch_matches(equipo_b, team_type)

    if not matches_a:
        raise ValueError(f"No se encontraron partidos para '{equipo_a}'.")
    if not matches_b:
        raise ValueError(f"No se encontraron partidos para '{equipo_b}'.")

    # ── 2. Fuerzas de ataque/defensa ──────────────────────────
    strength_a = calcular_lambda(matches_a, equipo_a, verbose=verbose)
    strength_b = calcular_lambda(matches_b, equipo_b, verbose=verbose)

    # ── 3. Contexto del partido (web + IA local) ──────────────
    ctx_data = get_match_context(
        equipo_a, equipo_b,
        competition=competition,
        racha_a=_racha_resumen(strength_a),
        racha_b=_racha_resumen(strength_b),
        noticias=noticias, 
    )

    context = MatchContext(
        competition=competition or "Unknown",
        stage=ctx_data.get("stage", "league_normal"),
        motivation_a=ctx_data.get("motivation_a", "normal"),
        motivation_b=ctx_data.get("motivation_b", "normal"),
        is_second_leg=ctx_data.get("is_second_leg", False),
        first_leg_score=tuple(ctx_data["first_leg_score"]) if ctx_data.get("first_leg_score") else None,
        notes=ctx_data.get("notes", ""),
        confidence=ctx_data.get("confidence", "low"),
    )

    # ── 4. Lambda inicial = ataque propio + defensa rival ─────
    lambda_a = (strength_a["lambda_ataque"] + strength_b["lambda_defensa"]) / 2
    lambda_b = (strength_b["lambda_ataque"] + strength_a["lambda_defensa"]) / 2

    # ── 5. Simulación Monte Carlo con contexto ────────────────
    resultado = simular(lambda_a, lambda_b, venue=venue, context=context, verbose=verbose)

    resultado["equipo_a"] = equipo_a
    resultado["equipo_b"] = equipo_b
    resultado["venue"] = venue
    # Guardar noticias en context_raw para el reporte de app.py
    if noticias:
        ctx_data["_noticias_raw"] = noticias
    resultado["context_raw"] = ctx_data
    resultado["strength_a"] = strength_a
    resultado["strength_b"] = strength_b

    return resultado


if __name__ == "__main__":
    import sys
    from output.report import imprimir_reporte

    if len(sys.argv) < 3:
        print('Uso: python predictor.py "Equipo A" "Equipo B" [venue] [competition]')
        sys.exit(1)

    equipo_a = sys.argv[1]
    equipo_b = sys.argv[2]
    venue = sys.argv[3] if len(sys.argv) > 3 else "neutral"
    competition = sys.argv[4] if len(sys.argv) > 4 else ""

    res = predecir(equipo_a, equipo_b, venue=venue, competition=competition, verbose=True)
    imprimir_reporte(res, verbose=True)
