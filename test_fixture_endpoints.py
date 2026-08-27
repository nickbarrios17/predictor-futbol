# test_fixture_endpoints.py
"""
Script de diagnóstico — correr UNA SOLA VEZ para saber
qué endpoints de fixture/calendario tiene tu plan de RapidAPI.

Uso:
    python test_fixture_endpoints.py

No modifica nada del proyecto. Solo imprime resultados.
"""
import requests
import time
import json
from config import RAPIDAPI_KEY

BASE_URL = "https://sofascore.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
}

print("="*60)
print("DIAGNÓSTICO DE ENDPOINTS DE FIXTURE — SofaScore/RapidAPI")
print("="*60)

# ── Test 1: Buscar el torneo "FIFA World Cup" ──────────────────
print("\n[1] Buscando torneo 'FIFA World Cup'...")
time.sleep(1)
try:
    resp = requests.get(
        f"{BASE_URL}/search",
        headers=HEADERS,
        params={"q": "FIFA World Cup", "page": "0"},
        timeout=10
    )
    print(f"    Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"    Respuesta (primeros 500 chars): {json.dumps(data)[:500]}")
    else:
        print(f"    Error: {resp.text[:300]}")
except Exception as e:
    print(f"    EXCEPCIÓN: {e}")

# ── Test 2: Endpoint directo de tournament/unique-tournament ──
print("\n[2] Probando endpoint unique-tournament (ID conocido del Mundial = 16)...")
time.sleep(1)
try:
    resp = requests.get(
        f"{BASE_URL}/tournaments/get-info",
        headers=HEADERS,
        params={"tournamentId": "16"},
        timeout=10
    )
    print(f"    Status: {resp.status_code}")
    print(f"    Respuesta: {resp.text[:500]}")
except Exception as e:
    print(f"    EXCEPCIÓN: {e}")

# ── Test 3: Endpoint de eventos/fixture por temporada ──────────
print("\n[3] Probando endpoint de events por season...")
time.sleep(1)
try:
    resp = requests.get(
        f"{BASE_URL}/tournaments/get-events",
        headers=HEADERS,
        params={"tournamentId": "16", "seasonId": "57883", "course_events": "last"},
        timeout=10
    )
    print(f"    Status: {resp.status_code}")
    print(f"    Respuesta: {resp.text[:500]}")
except Exception as e:
    print(f"    EXCEPCIÓN: {e}")

# ── Test 4: Listar TODOS los endpoints disponibles (si existe) ─
print("\n[4] Intentando endpoint raíz para ver documentación...")
time.sleep(1)
try:
    resp = requests.get(
        f"{BASE_URL}/",
        headers=HEADERS,
        timeout=10
    )
    print(f"    Status: {resp.status_code}")
    print(f"    Respuesta: {resp.text[:300]}")
except Exception as e:
    print(f"    EXCEPCIÓN: {e}")

print("\n" + "="*60)
print("FIN DEL DIAGNÓSTICO")
print("="*60)
print("\nCopiá TODO este output y pegámelo para que decida")
print("la estrategia correcta de fixture_fetcher.py")
