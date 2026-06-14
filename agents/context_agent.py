# agents/context_agent.py
"""
Usa Ollama (IA local y gratuita) para extraer el contexto
del partido desde texto crudo de páginas web.
"""
import json
import re
import ollama
from sources.web_source import get_match_news, fetch_multiple, search_web
from config import OLLAMA_MODEL


def get_match_context(team_a: str, team_b: str,
                      competition: str = "",
                      racha_a: str = "",
                      racha_b: str = "",
                      noticias: str = None) -> dict:
    """
    Obtiene el contexto del partido.

    Si 'noticias' viene con contenido desde predictor.py → las usa.
    Si viene vacío o None → busca internamente con la competición incluida.
    """
    print(f"  🤖 Analizando contexto: {team_a} vs {team_b} [{competition}]")

    # ── Obtener texto de noticias ─────────────────────────────
    if noticias and len(noticias.strip()) > 100:
        texto = noticias
        print(f"  📄 Usando noticias pasadas por parámetro: {len(texto)} chars")
    else:
        # Buscar internamente, incluyendo la competición en la query
        print("  🔍 Buscando noticias internamente...")
        texto = get_match_news(team_a, team_b, competition, n_urls=3)

    if not texto or len(texto.strip()) < 50:
        print("  ⚠️  Sin texto suficiente. Usando contexto neutro.")
        return _default_context()

    return _extract_with_ai(texto, team_a, team_b, competition,
                             racha_a, racha_b)


def _extract_with_ai(text: str, team_a: str, team_b: str,
                     competition: str,
                     racha_a: str, racha_b: str) -> dict:

    # Inferir el stage base desde la competición si tenemos esa info
    # así la IA tiene un punto de partida aunque las noticias sean vagas
    stage_hint = _infer_stage_hint(competition)

    prompt = f"""You are a football analyst. Read the following text about the match:
{team_a} vs {team_b}
Competition: {competition if competition else "Unknown"}
{f"Stage hint from competition name: {stage_hint}" if stage_hint else ""}

Recent form stats (use these in your notes):
- {team_a}: {racha_a}
- {team_b}: {racha_b}

Extract this information as JSON. Use null if not found in the text.
Do NOT invent data. If the competition name implies a stage (e.g. "World Cup" 
implies group_normal or higher, "Champions League Final" implies final_champions),
use that as a fallback for the "stage" field.

Required JSON:
{{
  "stage": "one of: final_champions | final_libertadores | final_sudamericana | final_mundial | final_eurocopa | final_copa_america | final_local | semi_champions | semi_mundial | semi_local | knockout_early | group_must_win | group_normal | group_meaningless | qualifier_decisive | qualifier_normal | league_title | league_relegation | league_normal | league_meaningless | friendly_competitive | friendly_normal | friendly_rotation",
  "motivation_a": "one of: must_win | normal | can_draw | already_in | rotation",
  "motivation_b": "one of: must_win | normal | can_draw | already_in | rotation",
  "lineup_status_a": "one of: full | rotation | reserves | unknown",
  "lineup_status_b": "one of: full | rotation | reserves | unknown",
  "injuries_a": ["injured or suspended players from team A, empty list if none found"],
  "injuries_b": ["injured or suspended players from team B, empty list if none found"],
  "is_second_leg": false,
  "first_leg_score": null,
  "notes": "2-sentence summary combining the text AND the form stats above.",
  "confidence": "high | medium | low"
}}

TEXT FROM NEWS SOURCES:
{text[:3500]}

Respond ONLY with valid JSON. No markdown, no extra text.
"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )
        raw = response["message"]["content"].strip()
        result = _parse_json(raw)

        # Si la IA dejó stage en league_normal pero la competición
        # claramente dice otra cosa, lo corregimos
        if result.get("stage") == "league_normal" and stage_hint:
            result["stage"] = stage_hint
            print(f"  🔧 Stage corregido por nombre de competición: {stage_hint}")

        return result

    except Exception as e:
        print(f"  ⚠️  Error en IA: {e}")
        ctx = _default_context()
        if stage_hint:
            ctx["stage"] = stage_hint
        return ctx


def _infer_stage_hint(competition: str) -> str | None:
    """
    Infiere el stage probable solo desde el nombre de la competición.
    Usado como fallback cuando las noticias no tienen suficiente info.
    """
    if not competition:
        return None

    comp = competition.lower()

    # Finales
    if "final" in comp:
        if "champion" in comp:     return "final_champions"
        if "libertador" in comp:   return "final_libertadores"
        if "sudameric" in comp:    return "final_sudamericana"
        if "world cup" in comp or "mundial" in comp: return "final_mundial"
        if "euro" in comp:         return "final_eurocopa"
        if "copa america" in comp: return "final_copa_america"
        return "final_local"

    # Semis
    if "semi" in comp:
        if "champion" in comp: return "semi_champions"
        if "world cup" in comp or "mundial" in comp: return "semi_mundial"
        return "semi_local"

    # Grupos de torneos internacionales
    if "world cup" in comp or "mundial" in comp:
        return "group_normal"
    if "euro" in comp and "qualif" not in comp:
        return "group_normal"
    if "copa america" in comp:
        return "group_normal"
    if "libertador" in comp:
        return "group_normal"
    if "sudameric" in comp:
        return "group_normal"
    if "champion" in comp:
        return "group_normal"

    # Eliminatorias
    if "qualif" in comp or "clasif" in comp or "eliminat" in comp:
        return "qualifier_normal"

    # Amistoso
    if "friendly" in comp or "amistoso" in comp:
        return "friendly_normal"

    return None


def _parse_json(raw: str) -> dict:
    """Intenta parsear el JSON de la respuesta de la IA."""
    # Limpiar markdown si la IA lo incluyó
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Buscar el primer bloque JSON en el texto
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

    print("  ⚠️  No se pudo parsear el JSON de la IA")
    return _default_context()


def _default_context() -> dict:
    return {
        "stage":           "league_normal",
        "motivation_a":    "normal",
        "motivation_b":    "normal",
        "lineup_status_a": "unknown",
        "lineup_status_b": "unknown",
        "injuries_a":      [],
        "injuries_b":      [],
        "is_second_leg":   False,
        "first_leg_score": None,
        "notes":           "",
        "confidence":      "low",
    }
