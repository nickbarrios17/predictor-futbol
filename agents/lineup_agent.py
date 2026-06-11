# agents/lineup_agent.py
"""
Detecta si un equipo va a rotar basándose en noticias
de lesiones y calendario. Usa Ollama (gratis, local).
"""
import json
import re
import ollama
from sources.web_source import search_web, fetch_multiple
from config import OLLAMA_MODEL


def analyze_lineup(team: str, match_date: str = "",
                   competition: str = "") -> dict:
    """
    Analiza si el equipo va a rotar o jugar con titulares.
    """
    query = f"{team} lineup injuries suspension {competition} {match_date}"
    urls  = search_web(query, n=2)

    if not urls:
        return _default_lineup()

    texto = fetch_multiple(urls, max_chars=2000)

    if not texto.strip():
        return _default_lineup()

    return _extract_with_ai(texto, team)


def _extract_with_ai(text: str, team: str) -> dict:

    prompt = f"""Analyze this news about {team} before their next match.

Respond ONLY with this JSON:
{{
  "lineup_status": "full | rotation | reserves | unknown",
  "rotation_reason": "string or null",
  "confirmed_out": ["players definitely not playing"],
  "doubts": ["players who are doubts"],
  "key_player_missing": true or false,
  "confidence": "high | medium | low"
}}

Criteria:
- full: regular starting eleven
- rotation: 2-4 changes from regular lineup
- reserves: 5+ reserve/youth players
- unknown: not enough info

NEWS:
{text[:3000]}

Only the JSON:
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
        print(f"  ⚠️  Error en lineup agent: {e}")
        return _default_lineup()


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
    return _default_lineup()


def _default_lineup() -> dict:
    return {
        "lineup_status":     "unknown",
        "rotation_reason":   None,
        "confirmed_out":     [],
        "doubts":            [],
        "key_player_missing":False,
        "confidence":        "low",
    }