# agents/analysis_agent.py
"""
Agente de análisis narrativo independiente.

Recibe TODOS los datos ya calculados y produce:
  - Análisis narrativo del partido
  - Predicción propia (resultado + marcador)
  - Factores clave identificados
  - Mercados recomendados
  - Si coincide o difiere del modelo estadístico

La IA NO usa su memoria de entrenamiento para inventar datos.
Razona exclusivamente sobre lo que le pasamos.
"""
import json
import re
import ollama
from config import OLLAMA_MODEL


# ─────────────────────────────────────────────────────────────
# HELPERS DE DATOS
# ─────────────────────────────────────────────────────────────

def _formato_historial(matches: list, team_name: str,
                       max_n: int = 8) -> str:
    """Historial legible con resultado, rival, sede y competición."""
    if not matches:
        return "  Sin datos."
    lineas = []
    for m in matches[:max_n]:
        es_local = m.get("team_home") == team_name
        rival    = m.get("team_away") if es_local else m.get("team_home")
        gh, ga   = m.get("goals_home", 0), m.get("goals_away", 0)
        gf       = gh if es_local else ga
        gc       = ga if es_local else gh
        sede     = "L" if es_local else "V"
        comp     = m.get("competition", "?")[:28]
        fecha    = m.get("date", "?")
        r        = "W" if gf > gc else ("D" if gf == gc else "L")
        lineas.append(
            f"  {fecha} [{r}] {gf}-{gc} vs {rival} ({sede}) | {comp}"
        )
    return "\n".join(lineas)


def _racha_5(matches: list, team_name: str) -> str:
    """Racha compacta: W-D-L-W-W"""
    res = []
    for m in matches[:5]:
        es_local = m.get("team_home") == team_name
        gh, ga   = m.get("goals_home", 0), m.get("goals_away", 0)
        gf       = gh if es_local else ga
        gc       = ga if es_local else gh
        res.append("W" if gf > gc else ("D" if gf == gc else "L"))
    return "-".join(res) if res else "N/A"


def _stats_local_visitante(matches: list, team_name: str) -> dict:
    """
    Separa las stats de goles por condición de sede.
    Le da a la IA info que el historial partido-a-partido no resume bien:
    un equipo que mete 2 goles/partido pero todos de local
    es muy distinto a uno que lo hace de visitante también.
    """
    local   = {"gf": [], "gc": [], "pts": []}
    visita  = {"gf": [], "gc": [], "pts": []}

    for m in matches:
        es_local = m.get("team_home") == team_name
        gh, ga   = m.get("goals_home", 0), m.get("goals_away", 0)
        gf       = gh if es_local else ga
        gc       = ga if es_local else gh

        if gf > gc:   pts = 3
        elif gf == gc: pts = 1
        else:          pts = 0

        bucket = local if es_local else visita
        bucket["gf"].append(gf)
        bucket["gc"].append(gc)
        bucket["pts"].append(pts)

    def _avg(lst): return round(sum(lst) / len(lst), 2) if lst else None
    def _pct(lst): return round(sum(lst) / (len(lst) * 3) * 100, 1) if lst else None

    return {
        "local": {
            "partidos":    len(local["gf"]),
            "goles_favor": _avg(local["gf"]),
            "goles_contra":_avg(local["gc"]),
            "rendimiento": _pct(local["pts"]),
        },
        "visita": {
            "partidos":    len(visita["gf"]),
            "goles_favor": _avg(visita["gf"]),
            "goles_contra":_avg(visita["gc"]),
            "rendimiento": _pct(visita["pts"]),
        },
    }


def _formato_stats_sede(stats: dict, team: str, venue_role: str) -> str:
    """
    Convierte las stats de sede en texto legible para la IA.
    venue_role: 'local' | 'visitante' | 'neutral'
    """
    lines = []
    for cond, label in [("local", "Como local"), ("visita", "Como visitante")]:
        s = stats[cond]
        if s["partidos"] == 0:
            lines.append(f"  {label}: sin datos")
            continue
        r = s["rendimiento"]
        lines.append(
            f"  {label} ({s['partidos']} partidos): "
            f"{s['goles_favor']} goles/p a favor | "
            f"{s['goles_contra']} goles/p en contra | "
            f"{r}% rendimiento"
        )
    # Marcar cuál es la condición del partido actual
    if venue_role != "neutral":
        lines.append(f"  → En este partido juega como {venue_role}")
    else:
        lines.append(f"  → En este partido juega en cancha neutral")
    return "\n".join(lines)


def _formato_lambdas_detalle(lambdas: dict, ea: str, eb: str) -> str:
    """
    Muestra el desglose de cómo se construyó el lambda final.
    Permite a la IA razonar sobre los ajustes del modelo.
    """
    if not lambdas:
        return "  Desglose no disponible."

    base    = lambdas.get("base",       ("?", "?"))
    sede    = lambdas.get("post_sede",  ("?", "?"))
    intens  = lambdas.get("intensity",  "?")
    motiv   = lambdas.get("motivation", ("?", "?"))
    vuelta  = lambdas.get("second_leg", (1.0, 1.0))
    final   = lambdas.get("final",      ("?", "?"))

    return f"""
  λ base (ataque × defensa rival) → {ea}: {base[0]}  |  {eb}: {base[1]}
  Tras ventaja de sede             → {ea}: {sede[0]}  |  {eb}: {sede[1]}
  Multiplicador intensidad         → ×{intens} (finales bajan, grupos con presión suben)
  Multiplicador motivación         → {ea}: ×{motiv[0]}  |  {eb}: ×{motiv[1]}
  Multiplicador vuelta             → {ea}: ×{vuelta[0]}  |  {eb}: ×{vuelta[1]}
  λ FINAL usado en simulación      → {ea}: {final[0]}  |  {eb}: {final[1]}"""


def _formato_marcadores_top10(marcadores: list) -> str:
    """
    Top 10 marcadores con sus probabilidades.
    Con 10 la IA detecta patrones (¿se concentra en pocos goles? ¿hay mucha dispersión?).
    """
    if not marcadores:
        return "  Sin datos."
    lineas = []
    for i, (score, pct) in enumerate(marcadores[:10], 1):
        bar = "█" * int(pct / 2)
        lineas.append(f"  #{i:2} {score}  {bar} {pct}%")
    return "\n".join(lineas)


def _modelo_favorito(resultado: dict) -> str:
    va  = resultado.get("victoria_a", 0)
    emp = resultado.get("empate",     0)
    vb  = resultado.get("victoria_b", 0)
    ea  = resultado.get("equipo_a",   "Equipo A")
    eb  = resultado.get("equipo_b",   "Equipo B")
    if va >= emp and va >= vb:
        return f"Victoria {ea} ({va}%)"
    if vb >= va  and vb >= emp:
        return f"Victoria {eb} ({vb}%)"
    return f"Empate ({emp}%)"


# ─────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────

def generar_analisis(resultado: dict,
                     matches_a: list,
                     matches_b: list,
                     noticias:  str = "") -> dict:
    """
    Genera el análisis narrativo e independiente de la IA.

    Devuelve:
    {
      "prediccion":            "Victoria X" | "Empate",
      "marcador_predicho":     "2-1",
      "confianza":             "alta" | "media" | "baja",
      "coincide_modelo":       True | False | None,
      "factores_clave":        ["...", ...],
      "analisis":              "Texto narrativo...",
      "fortaleza_ofensiva_a":  "...",
      "fortaleza_ofensiva_b":  "...",
      "mercados_recomendados": ["..."],
      "advertencias":          ["..."],
      "error":                 None | "mensaje"
    }
    """
    ea  = resultado.get("equipo_a", "Equipo A")
    eb  = resultado.get("equipo_b", "Equipo B")
    ctx = resultado.get("context_raw", {})

    brief = _construir_brief(resultado, matches_a, matches_b,
                             ea, eb, ctx, noticias)

    print("  🧠 IA generando análisis narrativo...")
    raw = _llamar_ollama(brief)
    if raw is None:
        return _error_response("Ollama no respondió")

    analisis = _parsear_respuesta(raw)
    if analisis.get("error"):
        return analisis

    analisis["coincide_modelo"] = _evaluar_coincidencia(
        analisis, resultado, ea, eb
    )
    return analisis


# ─────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL BRIEF
# ─────────────────────────────────────────────────────────────

def _construir_brief(resultado: dict, matches_a: list,
                     matches_b: list, ea: str, eb: str,
                     ctx: dict, noticias: str) -> str:

    # ── Historial y racha ─────────────────────────────────────
    hist_a  = _formato_historial(matches_a, ea, max_n=8)
    hist_b  = _formato_historial(matches_b, eb, max_n=8)
    racha_a = _racha_5(matches_a, ea)
    racha_b = _racha_5(matches_b, eb)

    # ── Stats por sede ────────────────────────────────────────
    venue   = resultado.get("venue", "neutral")
    stats_a = _stats_local_visitante(matches_a, ea)
    stats_b = _stats_local_visitante(matches_b, eb)

    # Determinar rol de cada equipo en este partido
    role_a  = "local"     if venue == "home_a" else \
              "visitante" if venue == "home_b" else "neutral"
    role_b  = "local"     if venue == "home_b" else \
              "visitante" if venue == "home_a" else "neutral"

    stats_a_txt = _formato_stats_sede(stats_a, ea, role_a)
    stats_b_txt = _formato_stats_sede(stats_b, eb, role_b)

    # ── Lambdas detallados ────────────────────────────────────
    lambdas_txt = _formato_lambdas_detalle(
        resultado.get("lambdas_detalle", {}), ea, eb
    )

    # ── Marcadores top 10 ─────────────────────────────────────
    marcadores_txt = _formato_marcadores_top10(
        resultado.get("top_marcadores", [])
    )

    # ── Probabilidades y mercados ─────────────────────────────
    va   = resultado.get("victoria_a", 0)
    emp  = resultado.get("empate",     0)
    vb   = resultado.get("victoria_b", 0)
    ou   = resultado.get("ou",         {})
    sa   = resultado.get("strength_a", {})
    sb   = resultado.get("strength_b", {})

    # ── Bajas ─────────────────────────────────────────────────
    bajas_a = ", ".join(ctx.get("injuries_a", [])) or "Ninguna reportada"
    bajas_b = ", ".join(ctx.get("injuries_b", [])) or "Ninguna reportada"

    # ── Noticias (limitadas para no saturar el contexto) ──────
    noticias_txt = (noticias[:1800] + "\n[...texto recortado]") \
                   if len(noticias) > 1800 else noticias
    if not noticias_txt.strip():
        noticias_txt = "No se encontraron noticias recientes."

    return f"""
╔══════════════════════════════════════════════════════════════╗
  DATOS PARA ANÁLISIS: {ea} vs {eb}
╚══════════════════════════════════════════════════════════════╝

COMPETICIÓN : {ctx.get('competition') or 'Desconocida'}
SEDE        : {venue}  ({ea} juega como {role_a} | {eb} juega como {role_b})
TIPO        : {ctx.get('stage', 'league_normal')}
MOTIVACIÓN  : {ea} → {ctx.get('motivation_a','normal')} | {eb} → {ctx.get('motivation_b','normal')}
ALINEACIÓN  : {ea} → {ctx.get('lineup_status_a','unknown')} | {eb} → {ctx.get('lineup_status_b','unknown')}
VUELTA      : {'Sí — resultado ida: ' + str(ctx.get('first_leg_score')) if ctx.get('is_second_leg') else 'No'}

══ MODELO ESTADÍSTICO ═══════════════════════════════════════════
Partidos analizados: {ea}: {sa.get('partidos_usados','?')} | {eb}: {sb.get('partidos_usados','?')}

Cómo se construyó el lambda (goles esperados):
{lambdas_txt}

Probabilidades finales:
  Victoria {ea}: {va}%
  Empate:        {emp}%
  Victoria {eb}: {vb}%

Distribución de marcadores (top 10):
{marcadores_txt}

Mercados de goles:
  Over 0.5: {ou.get('over_05','?')}%  |  Under 0.5: {ou.get('under_05','?')}%
  Over 1.5: {ou.get('over_15','?')}%  |  Under 1.5: {ou.get('under_15','?')}%
  Over 2.5: {ou.get('over_25','?')}%  |  Under 2.5: {ou.get('under_25','?')}%
  Over 3.5: {ou.get('over_35','?')}%  |  Under 3.5: {ou.get('under_35','?')}%
  BTTS Sí:  {resultado.get('btts_si','?')}%  |  BTTS No: {resultado.get('btts_no','?')}%

══ RENDIMIENTO POR SEDE ═════════════════════════════════════════
{ea}:
{stats_a_txt}

{eb}:
{stats_b_txt}

══ HISTORIAL {ea.upper()} (racha últimos 5: {racha_a}) ══════════════
{hist_a}

══ HISTORIAL {eb.upper()} (racha últimos 5: {racha_b}) ══════════════
{hist_b}

══ BAJAS Y SUSPENSIONES ═════════════════════════════════════════
{ea}: {bajas_a}
{eb}: {bajas_b}

══ NOTICIAS Y CONTEXTO RECIENTE ═════════════════════════════════
{noticias_txt}

══ FIN DE DATOS ═════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────
# LLAMADA A OLLAMA
# ─────────────────────────────────────────────────────────────

def _llamar_ollama(brief: str) -> str | None:
    prompt = f"""Sos un analista de fútbol experto. Analizá el siguiente partido
usando EXCLUSIVAMENTE los datos que te proveo abajo.
NO uses tu memoria de entrenamiento para inventar resultados,
estadísticas, declaraciones o datos que no estén en el texto.
Si algo no está en los datos, decilo explícitamente.

{brief}

Basándote ÚNICAMENTE en los datos anteriores, respondé con este JSON.
Todos los campos son obligatorios:

{{
  "prediccion": "Victoria [nombre exacto del equipo]" o "Empate",
  "marcador_predicho": "X-Y",
  "confianza": "alta" | "media" | "baja",
  "factores_clave": [
    "Factor 1 — incluí el dato específico que lo respalda (mínimo 3, máximo 5)",
    "Factor 2...",
    "Factor 3..."
  ],
  "analisis": "Párrafo de 5-7 oraciones. Referenciá los lambdas, la racha, el rendimiento por sede, el desglose de ajustes del modelo y cualquier info de las noticias. Sé específico.",
  "fortaleza_ofensiva_a": "Evaluación del ataque del primer equipo basada en su lambda, racha y stats por sede (1-2 oraciones)",
  "fortaleza_ofensiva_b": "Ídem para el segundo equipo",
  "mercados_recomendados": [
    "Mercado específico con justificación basada en los datos (ej: Under 2.5 porque ambos lambdas son bajos y el partido es una final)"
  ],
  "advertencias": [
    "Factor de incertidumbre importante si existe"
  ]
}}

Respondé ÚNICAMENTE con el JSON válido. Sin texto antes ni después. Sin bloques ```."""

    try:
        resp = ollama.chat(
            model   = OLLAMA_MODEL,
            messages= [{"role": "user", "content": prompt}],
            options = {
                "temperature": 0.3,
                "num_predict": 1500,
            },
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        print(f"  ⚠️  Error Ollama: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# PARSEO Y VALIDACIÓN
# ─────────────────────────────────────────────────────────────

def _parsear_respuesta(raw: str) -> dict:
    clean = re.sub(r"```json\s*", "", raw)
    clean = re.sub(r"```\s*",     "", clean).strip()
    try:
        data = json.loads(clean)
        if "prediccion" not in data or "analisis" not in data:
            return _error_response("Respuesta de la IA incompleta")
        return data
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return _error_response(f"No se pudo parsear JSON. Raw: {raw[:300]}")


def _evaluar_coincidencia(analisis: dict, resultado: dict,
                           ea: str, eb: str) -> bool | None:
    pred = analisis.get("prediccion", "").lower()
    va   = resultado.get("victoria_a", 0)
    emp  = resultado.get("empate",     0)
    vb   = resultado.get("victoria_b", 0)

    if va >= emp and va >= vb:
        modelo = f"victoria {ea}".lower()
    elif vb >= va and vb >= emp:
        modelo = f"victoria {eb}".lower()
    else:
        modelo = "empate"

    if not pred:
        return None
    if "empate" in pred and "empate" in modelo:
        return True
    if ea.lower() in pred and ea.lower() in modelo:
        return True
    if eb.lower() in pred and eb.lower() in modelo:
        return True
    return False


def _error_response(msg: str) -> dict:
    return {
        "prediccion":           "No disponible",
        "marcador_predicho":    "?-?",
        "confianza":            "baja",
        "coincide_modelo":      None,
        "factores_clave":       [],
        "analisis":             f"Error al generar el análisis: {msg}",
        "fortaleza_ofensiva_a": "No disponible",
        "fortaleza_ofensiva_b": "No disponible",
        "mercados_recomendados":[],
        "advertencias":         [msg],
        "error":                msg,
    }
