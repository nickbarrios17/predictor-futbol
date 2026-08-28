# predictor.py — v2.0
"""
Punto de entrada único del sistema.

Fix Bug 2: save_prediction fue ELIMINADO de acá.
El guardado ahora es responsabilidad exclusiva de app.py,
después de que el usuario confirma que no es duplicado.
"""
import sys

# Los prints de debug usan emojis; en Windows la consola por defecto
# es cp1252 y no puede codificarlos, lo que crashea el proceso.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from data.fetcher           import fetch_matches
from model.strength         import calcular_lambda
from model.monte_carlo      import simular
from model.match_context    import MatchContext
from agents.context_agent   import get_match_context
from agents.analysis_agent  import generar_analisis
from sources.web_source     import get_match_news
from features.elo           import get_elo


def _racha_resumen(strength: dict) -> str:
    return (
        f"{strength['partidos_usados']} partidos, "
        f"ataque global {round(strength.get('attack_global', 0), 2)} / "
        f"defensa global {round(strength.get('defense_global', 0), 2)}"
    )


def predecir(
    equipo_a:    str,
    equipo_b:    str,
    venue:       str  = "neutral",
    competition: str  = "",
    team_type:   str  = "default",
    verbose:     bool = False,
) -> dict:
    """
    Predice el resultado de cualquier partido.

    Devuelve el dict completo con probabilidades, lambdas,
    historial, contexto y análisis de IA.
    NO guarda en SQLite — eso lo hace app.py.
    """
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

    # ── 2. Elo (preprocesamiento — solo una vez por equipo) ───
    print("\n📈 Actualizando Elo...")
    elo = get_elo()
    elo.update_from_matches(matches_a, equipo_a)
    elo.update_from_matches(matches_b, equipo_b)

    # ── 3. Fuerzas ────────────────────────────────────────────
    print("\n📐 Calculando fuerzas...")
    strength_a = calcular_lambda(matches_a, equipo_a, verbose=verbose)
    strength_b = calcular_lambda(matches_b, equipo_b, verbose=verbose)

    print(f"  {equipo_a}: Elo={strength_a.get('team_elo')} "
          f"ataque={round(strength_a.get('attack_global',0),3)} "
          f"defensa={round(strength_a.get('defense_global',0),3)} "
          f"({strength_a['partidos_usados']} partidos)")
    print(f"  {equipo_b}: Elo={strength_b.get('team_elo')} "
          f"ataque={round(strength_b.get('attack_global',0),3)} "
          f"defensa={round(strength_b.get('defense_global',0),3)} "
          f"({strength_b['partidos_usados']} partidos)")

    # ── 4. Noticias ───────────────────────────────────────────
    print("\n📰 Buscando noticias...")
    noticias = get_match_news(equipo_a, equipo_b, competition, n_urls=3)
    print(f"  Total texto: {len(noticias)} caracteres")

    # ── 5. Contexto ───────────────────────────────────────────
    print("\n🤖 Detectando contexto...")
    ctx_data = get_match_context(
        equipo_a, equipo_b,
        competition = competition,
        racha_a     = _racha_resumen(strength_a),
        racha_b     = _racha_resumen(strength_b),
        noticias    = noticias,
    )
    ctx_data["_noticias_chars"] = len(noticias)
    print(f"  Stage: {ctx_data.get('stage')} "
          f"(confianza: {ctx_data.get('confidence')})")

    context = MatchContext(
        competition     = competition or "Unknown",
        stage           = ctx_data.get("stage",           "league_normal"),
        motivation_a    = ctx_data.get("motivation_a",    "normal"),
        motivation_b    = ctx_data.get("motivation_b",    "normal"),
        is_second_leg   = ctx_data.get("is_second_leg",   False),
        first_leg_score = (tuple(ctx_data["first_leg_score"])
                           if ctx_data.get("first_leg_score") else None),
        notes           = ctx_data.get("notes",           ""),
        confidence      = ctx_data.get("confidence",      "low"),
    )

    # ── 6. Simulación ─────────────────────────────────────────
    print("\n🎲 Simulando 10.000 partidos...")
    resultado = simular(strength_a, strength_b,
                        venue=venue, context=context, verbose=verbose)

    # ── 7. Análisis de IA ─────────────────────────────────────
    print("\n🧠 Generando análisis de IA...")
    try:
        analisis_ia = generar_analisis(
            resultado  = {**resultado,
                          "equipo_a":    equipo_a,
                          "equipo_b":    equipo_b,
                          "context_raw": ctx_data,
                          "strength_a":  strength_a,
                          "strength_b":  strength_b},
            matches_a  = matches_a,
            matches_b  = matches_b,
            noticias   = noticias,
        )
        print(f"  Predicción IA: {analisis_ia.get('prediccion')} "
              f"| Coincide modelo: {analisis_ia.get('coincide_modelo')}")
    except Exception as e:
        print(f"  ⚠️  IA no disponible: {e}")
        analisis_ia = {"error": str(e)}

    # ── Ensamblar resultado ───────────────────────────────────
    resultado["equipo_a"]    = equipo_a
    resultado["equipo_b"]    = equipo_b
    resultado["venue"]       = venue
    resultado["context_raw"] = ctx_data
    resultado["strength_a"]  = strength_a
    resultado["strength_b"]  = strength_b
    resultado["matches_a"]   = matches_a
    resultado["matches_b"]   = matches_b
    resultado["noticias"]    = noticias
    resultado["analisis_ia"] = analisis_ia
    # pred_id se asigna en app.py después del guardado
    resultado["pred_id"]     = None

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
