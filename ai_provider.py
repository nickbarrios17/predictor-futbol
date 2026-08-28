"""Proveedor unico de IA para los agentes del predictor."""
from __future__ import annotations

import os

import google.generativeai as genai

from config import GEMINI_MODEL


def ask_ai(
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> str:
    """Ejecuta una consulta a Gemini y devuelve texto plano."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY en el entorno o archivo .env")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        },
    )

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini no devolvio texto")
    return text.strip()
