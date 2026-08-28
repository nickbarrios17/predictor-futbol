# output/report.py

# Códigos de color para terminal
RESET  = "\033[0m"
BOLD   = "\033[1m"
BLUE   = "\033[94m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"


def _color_prob(pct: float) -> str:
    if   pct >= 50: return GREEN
    elif pct >= 35: return YELLOW
    else:           return RED


def imprimir_reporte(r: dict, verbose: bool = False):
    sep  = "─" * 54
    sep2 = "═" * 54

    ea = r["equipo_a"]
    eb = r["equipo_b"]
    ctx = r.get("context", {})

    print(f"\n{BLUE}{BOLD}{sep2}{RESET}")
    print(f"{BOLD}  ⚽  {ea}  vs  {eb}{RESET}")
    print(f"{GRAY}  {ctx.get('competition','')} "
          f"| {ctx.get('stage','')} "
          f"| Sede: {r.get('venue','neutral')}{RESET}")
    if ctx.get("notes"):
        print(f"{GRAY}  📝 {ctx['notes']}{RESET}")
    conf = ctx.get("confidence", "?")
    conf_color = GREEN if conf == "high" else (YELLOW if conf == "medium" else RED)
    print(f"{GRAY}  Confianza contexto: "
          f"{conf_color}{conf}{RESET}")
    print(f"{BLUE}{BOLD}{sep}{RESET}")

    # ── 1X2 ──────────────────────────────────────────────────
    va  = r["victoria_a"]
    emp = r["empate"]
    vb  = r["victoria_b"]

    print(f"\n{BOLD}  PROBABILIDADES{RESET}")
    print(f"  {'Victoria ' + ea:<32}"
          f"{_color_prob(va)}{BOLD}{va:>5.1f}%{RESET}")
    print(f"  {'Empate':<32}"
          f"{YELLOW}{BOLD}{emp:>5.1f}%{RESET}")
    print(f"  {'Victoria ' + eb:<32}"
          f"{_color_prob(vb)}{BOLD}{vb:>5.1f}%{RESET}")

    # ── Lambdas ───────────────────────────────────────────────
    print(f"\n{GRAY}  λ {ea}: {r['lambda_a']}  |  "
          f"λ {eb}: {r['lambda_b']}{RESET}")

    # ── Marcadores ───────────────────────────────────────────
    print(f"\n{BOLD}  MARCADORES MÁS PROBABLES{RESET}")
    for i, (score, pct) in enumerate(r["top_marcadores"], 1):
        bar = "█" * int(pct / 2)
        print(f"  {i}. {score:<8} {CYAN}{bar:<20}{RESET} {pct}%")

    # ── Over/Under ───────────────────────────────────────────
    print(f"\n{BOLD}  OVER / UNDER{RESET}")
    ou = r["ou"]
    for linea in ["05", "15", "25", "35"]:
        ov = ou[f"over_{linea}"]
        un = ou[f"under_{linea}"]
        print(f"  Over  {linea[0]}.{linea[1]}  "
              f"{_color_prob(ov)}{ov:>5.1f}%{RESET}   "
              f"Under {linea[0]}.{linea[1]}  "
              f"{_color_prob(un)}{un:>5.1f}%{RESET}")

    # ── BTTS ─────────────────────────────────────────────────
    print(f"\n{BOLD}  AMBOS MARCAN{RESET}")
    print(f"  Sí: {_color_prob(r['btts_si'])}"
          f"{BOLD}{r['btts_si']}%{RESET}   "
          f"No: {_color_prob(r['btts_no'])}"
          f"{BOLD}{r['btts_no']}%{RESET}")

    # ── Verbose: detalle de lambdas ───────────────────────────
    if verbose and "lambdas_detalle" in r:
        ld = r["lambdas_detalle"]
        print(f"\n{GRAY}  DETALLE LAMBDAS")
        print(f"  Base:       {ld['base']}")
        print(f"  Intensidad: {ld['intensity']}")
        print(f"  Motivación: {ld['motivation']}")
        print(f"  Alineación: {ld.get('lineup', (1.0, 1.0))}")
        print(f"  Vuelta:     {ld['second_leg']}")
        print(f"  Final:      {ld['final']}{RESET}")

    print(f"{BLUE}{BOLD}{sep2}{RESET}\n")