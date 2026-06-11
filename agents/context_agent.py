# agents/context_agent.py
"""
Usa Ollama (IA local y gratuita) para extraer el contexto
del partido desde texto crudo de páginas web.
"""
import json
import re
import ollama
from sources.web_source import search_web, fetch_multiple
from config import OLLAMA_MODEL

def get_match_context(team_a: str, team_b: str,
                      competition: str = "", 
                      racha_a: str = "", 
                      racha_b: str = "") -> dict:
    """
    Busca noticias del partido y extrae el contexto
    usando la IA local. Devuelve un dict estructurado.
    """
    print(f"  🤖 Buscando contexto: {team_a} vs {team_b}...")

    query = f"{team_a} vs {team_b} {competition} preview lineup 2026"
    urls  = search_web(query, n=3)

    texto = ""
    if urls:
        texto = fetch_multiple(urls, max_chars=2500)
    else:
        print("  ⚠️  Sin resultados web. Usando contexto neutro.")
        # 👇 FIX: Frenar la función si no hay info web
        return _default_context()

    return _extract_with_ai(texto, team_a, team_b, competition, racha_a, racha_b)

def _extract_with_ai(text: str, team_a: str,
                     team_b: str, competition: str, 
                     racha_a: str, racha_b: str) -> dict:

    prompt = f"""You are a football analyst. Read the following text about the match:
{team_a} vs {team_b} ({competition})

Here is the exact recent form for both teams (incorporate this into your analysis):
- {team_a} Form: {racha_a}
- {team_b} Form: {racha_b}

Extract this information as JSON. Use null if not found in the text (except for the notes).
Do NOT invent data that is not in the text.

Required JSON:
{{
  "stage": "one of: final_champions | final_libertadores | final_sudamericana | final_mundial | final_eurocopa | final_copa_america | final_local | semi_champions | semi_mundial | semi_local | knockout_early | group_must_win | group_normal | group_meaningless | qualifier_decisive | qualifier_normal | league_title | league_relegation | league_normal | league_meaningless | friendly_competitive | friendly_normal | friendly_rotation",
  "motivation_a": "one of: must_win | normal | can_draw | already_in | rotation",
  "motivation_b": "one of: must_win | normal | can_draw | already_in | rotation",
  "lineup_status_a": "one of: full | rotation | reserves | unknown",
  "lineup_status_b": "one of: full | rotation | reserves | unknown",
  "injuries_a": ["list of injured or suspended players from team A"],
  "injuries_b": ["list of injured or suspended players from team B"],
  "is_second_leg": true or false,
  "first_leg_score": [goals_a, goals_b] or null,
  "notes": "Write a 2-sentence analytical summary combining the web text AND the recent form statistics I provided.",
  "confidence": "high | medium | low"
}}

TEXT:
{text[:3500]}

Respond ONLY with the JSON, no extra text.
"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}, 
        )
        raw = response["message"]["content"].strip()
        return _parse_json(raw)
    except Exception as e:
        print(f"  ⚠️  Error en IA: {e}")
        return _default_context()

def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
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