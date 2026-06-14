# predictor.py
from data.fetcher           import fetch_matches
from model.strength         import calcular_lambda
from model.monte_carlo      import simular
from model.match_context    import MatchContext
from agents.context_agent   import get_match_context
from agents.analysis_agent  import generar_analisis
from sources.web_source     import get_match_news


def _racha_resumen(strength: dict) -> str:
    return (
        f"{strength['partidos_usados']} partidos analizados, "
        f"promedio {strength['lambda_ataque']} goles a favor / "
        f"{strength['lambda_defensa']} en contra (ponderado)."
    )


def predecir(
    equipo_a:    str,
    equipo_b:    str,
    venue:       str  = "neutral",
    competition: str  = "",
    team_type:   str  = "default",
    verbose:     bool = False,
    noticias:    str  = None,
) -> dict:

    print(f"\n{'='*54}")
    print(f"⚽  {equipo_a}  vs  {equipo_b}")
    if competition:
        print(f"🏆  {competition}")
    print(f"{'='*54}")

    # ── 1. Historial ──────────────────────────────────────────
    print("\n📊 Obteniendo historial...")
    matches_a = fetch_matches(equipo_a, team_type)
    matches_b = fetch_matches(equipo_b, team_type)

    if not matches_a:
        raise ValueError(f"No se encontraron partidos para '{equipo_a}'.")
    if not matches_b:
        raise ValueError(f"No se encontraron partidos para '{equipo_b}'.")

    # ── 2. Fuerzas ────────────────────────────────────────────
    print("\n📐 Calculando fuerzas...")
    strength_a = calcular_lambda(matches_a, equipo_a, verbose=verbose)
    strength_b = calcular_lambda(matches_b, equipo_b, verbose=verbose)

    print(f"  {equipo_a}: λ_ataque={strength_a['lambda_ataque']} "
          f"λ_defensa={strength_a['lambda_defensa']} "
          f"({strength_a['partidos_usados']} partidos)")
    print(f"  {equipo_b}: λ_ataque={strength_b['lambda_ataque']} "
          f"λ_defensa={strength_b['lambda_defensa']} "
          f"({strength_b['partidos_usados']} partidos)")

    # ── 3. Noticias ───────────────────────────────────────────
    print("\n📰 Buscando noticias...")
    if not noticias or len(noticias.strip()) < 50:
        noticias = get_match_news(equipo_a, equipo_b, competition, n_urls=3)
    print(f"  Total texto: {len(noticias)} caracteres")

    # ── 4. Contexto estructurado ──────────────────────────────
    print("\n🤖 Detectando contexto...")
    ctx_data = get_match_context(
        equipo_a, equipo_b,
        competition = competition,
        racha_a     = _racha_resumen(strength_a),
        racha_b     = _racha_resumen(strength_b),
        noticias    = noticias,
    )
    ctx_data["_noticias_chars"] = len(noticias)

    context = MatchContext(
        competition     = competition or "Unknown",
        stage           = ctx_data.get("stage", "league_normal"),
        motivation_a    = ctx_data.get("motivation_a", "normal"),
        motivation_b    = ctx_data.get("motivation_b", "normal"),
        is_second_leg   = ctx_data.get("is_second_leg", False),
        first_leg_score = (
            tuple(ctx_data["first_leg_score"])
            if ctx_data.get("first_leg_score") else None
        ),
        notes    = ctx_data.get("notes", ""),
        confidence = ctx_data.get("confidence", "low"),
    )
    print(f"  Stage: {ctx_data.get('stage')} "
          f"(confianza: {ctx_data.get('confidence')})")

    # ── 5. Simulación Monte Carlo ─────────────────────────────
    # v1.1: simular() recibe los strength dicts completos.
    # Calcula lambdas internamente con fórmula normalizada
    # separada por local/visitante (Fix Bug 3 + Problema 1).
    print("\n🎲 Simulando 10.000 partidos...")
    resultado = simular(strength_a, strength_b,
                        venue=venue, context=context, verbose=verbose)

    resultado["equipo_a"]    = equipo_a
    resultado["equipo_b"]    = equipo_b
    resultado["venue"]       = venue
    resultado["context_raw"] = ctx_data
    resultado["strength_a"]  = strength_a
    resultado["strength_b"]  = strength_b
    # Guardamos matches para pasarlos al analysis_agent
    resultado["_matches_a"]  = matches_a
    resultado["_matches_b"]  = matches_b
    resultado["_noticias"]   = noticias

    # ── 6. Análisis narrativo de la IA ────────────────────────
    print("\n🧠 Generando análisis narrativo de la IA...")
    analisis_ia = generar_analisis(
        resultado  = resultado,
        matches_a  = matches_a,
        matches_b  = matches_b,
        noticias   = noticias,
    )
    resultado["analisis_ia"] = analisis_ia
    print(f"  Predicción IA: {analisis_ia.get('prediccion')} "
          f"| Marcador: {analisis_ia.get('marcador_predicho')} "
          f"| Coincide modelo: {analisis_ia.get('coincide_modelo')}")

    return resultado


if __name__ == "__main__":
    import sys
    from output.report import imprimir_reporte

    if len(sys.argv) < 3:
        print('Uso: python predictor.py "Equipo A" "Equipo B" '
              '[venue] [competition] [team_type]')
        sys.exit(1)

    res = predecir(
        equipo_a    = sys.argv[1],
        equipo_b    = sys.argv[2],
        venue       = sys.argv[3] if len(sys.argv) > 3 else "neutral",
        competition = sys.argv[4] if len(sys.argv) > 4 else "",
        team_type   = sys.argv[5] if len(sys.argv) > 5 else "default",
        verbose     = True,
    )
    imprimir_reporte(res, verbose=True)
