# backtesting/backtester.py - v2.1
"""
Backtesting honesto para evaluar el modelo con partidos pasados.

Para cada partido historico:
  1. Usa solo partidos anteriores a la fecha evaluada.
  2. Busca historial propio del rival y tambien lo corta por fecha.
  3. Compara el modelo contra baselines simples.
"""
import os
import sys
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.baselines import elo_simple_baseline, uniform_baseline
from backtesting.metrics import calcular_metricas, resumen_metricas
from data.fetcher import fetch_matches
from model.match_context import MatchContext
from model.monte_carlo import simular
from model.strength import calcular_lambda


HistoryProvider = Callable[[str, str], list[dict]]


def backtest_equipo(
    matches: list[dict],
    team_name: str,
    n_test: int = 5,
    venue: str = "neutral",
    competition: str = "",
    team_type: str = "default",
    fetch_rival_history: bool = True,
    history_provider: HistoryProvider = None,
    verbose: bool = False,
) -> list[dict]:
    """
    Corre backtesting sobre los ultimos N partidos de un equipo.

    Cada prediccion usa solo informacion disponible antes del partido.
    """
    history_provider = history_provider or fetch_matches

    if len(matches) < n_test + 5:
        print(
            f"  ⚠️  Historial insuficiente para backtest "
            f"({len(matches)} partidos, minimo {n_test + 5})"
        )
        return []

    sorted_matches = sorted(matches, key=lambda m: m.get("date", ""))
    test_matches = sorted_matches[-n_test:]
    resultados = []

    for test_match in test_matches:
        test_date = test_match.get("date", "")
        train_subset = _matches_before(sorted_matches, test_date)
        if len(train_subset) < 3:
            continue

        es_local = test_match.get("team_home") == team_name
        rival = test_match.get("team_away") if es_local else test_match.get("team_home")
        gf_real = (test_match.get("goals_home") if es_local else test_match.get("goals_away")) or 0
        gc_real = (test_match.get("goals_away") if es_local else test_match.get("goals_home")) or 0

        test_venue = venue
        if venue == "auto":
            test_venue = "home_a" if es_local else "home_b"

        try:
            sa = calcular_lambda(train_subset, team_name, verbose=False)

            sb_matches, rival_source = _get_rival_training_matches(
                all_matches=sorted_matches,
                rival_name=rival,
                before_date=test_date,
                team_type=team_type,
                fetch_rival_history=fetch_rival_history,
                history_provider=history_provider,
            )

            if len(sb_matches) < 3:
                sb = {
                    "attack_home": 1.0,
                    "attack_away": 1.0,
                    "defense_home": 1.0,
                    "defense_away": 1.0,
                    "attack_global": 1.0,
                    "defense_global": 1.0,
                    "lambda_ataque": 1.0,
                    "lambda_defensa": 1.0,
                    "team_elo": 1600,
                    "partidos_usados": 0,
                }
                rival_source = f"{rival_source}; fallback_promedio"
            else:
                sb = calcular_lambda(sb_matches, rival, verbose=False)

            comp = test_match.get("competition", competition)
            ctx = MatchContext(competition=comp, stage="league_normal")
            res = simular(sa, sb, venue=test_venue, context=ctx, verbose=False)

            metricas = calcular_metricas(
                prob_home=res["victoria_a"],
                prob_draw=res["empate"],
                prob_away=res["victoria_b"],
                over25_prob=res["ou"]["over_25"],
                btts_prob=res["btts_si"],
                real_home=gf_real,
                real_away=gc_real,
                top_scores=res["top_marcadores"],
            )

            baseline_uniform = uniform_baseline(
                real_home=gf_real,
                real_away=gc_real,
                over25_prob=res["ou"]["over_25"],
                btts_prob=res["btts_si"],
            )
            baseline_elo = elo_simple_baseline(
                elo_a=sa.get("team_elo", 1600),
                elo_b=sb.get("team_elo", 1600),
                venue=test_venue,
                real_home=gf_real,
                real_away=gc_real,
                over25_prob=res["ou"]["over_25"],
                btts_prob=res["btts_si"],
            )

            metricas.update(
                {
                    "partido": f"{test_match.get('team_home')} vs {test_match.get('team_away')}",
                    "partido_modelo": f"{team_name} vs {rival}",
                    "fecha": test_match.get("date", ""),
                    "comp": comp[:30],
                    "resultado_real": f"{gf_real}-{gc_real}",
                    "resultado_real_partido": (
                        f"{test_match.get('goals_home', 0)}-"
                        f"{test_match.get('goals_away', 0)}"
                    ),
                    "prob_home": res["victoria_a"],
                    "prob_draw": res["empate"],
                    "prob_away": res["victoria_b"],
                    "lambda_a": res["lambda_a"],
                    "lambda_b": res["lambda_b"],
                    "train_matches_a": len(train_subset),
                    "train_matches_b": len(sb_matches),
                    "rival_source": rival_source,
                    "baselines": {
                        "uniforme": baseline_uniform,
                        "elo_simple": baseline_elo,
                    },
                }
            )
            resultados.append(metricas)

            if verbose:
                icon = "✅" if metricas["result_correct"] else "❌"
                print(
                    f"  {icon} {metricas['partido_modelo']} | "
                    f"Real: {gf_real}-{gc_real} | "
                    f"Pred: {metricas['predicted_result']} | "
                    f"Brier: {metricas['brier_score']:.3f}"
                )

        except Exception as e:
            print(f"  ⚠️  Error en partido {test_date}: {e}")
            continue

    return resultados


def _matches_before(matches: list[dict], before_date: str) -> list[dict]:
    """Devuelve solo partidos anteriores a la fecha de corte."""
    if not before_date:
        return list(matches)
    return [
        m
        for m in matches
        if m.get("date", "") and m.get("date", "") < before_date
    ]


def _get_rival_training_matches(
    all_matches: list[dict],
    rival_name: str,
    before_date: str,
    team_type: str,
    fetch_rival_history: bool,
    history_provider: HistoryProvider,
) -> tuple[list[dict], str]:
    """Obtiene historial propio del rival, con fallback al historial compartido."""
    if fetch_rival_history:
        try:
            rival_matches = history_provider(rival_name, team_type)
            rival_train = _matches_before(rival_matches, before_date)
            if len(rival_train) >= 3:
                return rival_train, "historial_rival"
        except Exception as e:
            print(f"  ⚠️  No se pudo traer historial de {rival_name}: {e}")

    fallback = _get_rival_matches_from_history(
        all_matches, rival_name, before_date=before_date
    )
    return fallback, "historial_compartido"


def _get_rival_matches_from_history(
    all_matches: list[dict],
    rival_name: str,
    before_date: str,
) -> list[dict]:
    """Extrae partidos previos del rival desde el historial compartido."""
    rival_matches = []
    for m in all_matches:
        if m.get("date", "") >= before_date:
            continue
        home = m.get("team_home", "")
        away = m.get("team_away", "")
        if rival_name in (home, away):
            rival_matches.append(m)
    return rival_matches


def backtest_multiple(
    equipos: list[tuple[str, list[dict]]],
    n_test: int = 5,
    verbose: bool = False,
) -> dict:
    """Corre backtesting sobre multiples equipos y acumula metricas."""
    todos_resultados = []

    for team_name, matches in equipos:
        print(f"\n  📊 Backtesting {team_name}...")
        resultados = backtest_equipo(
            matches,
            team_name,
            n_test=n_test,
            venue="auto",
            verbose=verbose,
        )
        todos_resultados.extend(resultados)

    if not todos_resultados:
        return {"error": "Sin resultados de backtesting"}

    return resumen_metricas(todos_resultados)
