# model/worldcup.py - v1.0
"""Simulacion simple de grupos para torneos tipo Mundial."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from data.fetcher import fetch_matches
from model.match_context import MatchContext
from model.monte_carlo import simular
from model.strength import calcular_lambda


def build_group_fixtures(teams: list[str]) -> list[tuple[str, str]]:
    """Genera fixture todos contra todos a una vuelta."""
    clean = [t.strip() for t in teams if t and t.strip()]
    return list(combinations(clean, 2))


def load_strengths(
    teams: list[str],
    team_type: str = "seleccion",
    verbose: bool = False,
) -> tuple[dict[str, dict], list[str]]:
    """Carga historial y fuerza de cada equipo."""
    strengths = {}
    errors = []
    for team in teams:
        try:
            matches = fetch_matches(team, team_type)
            if not matches:
                errors.append(f"{team}: sin historial")
                continue
            strengths[team] = calcular_lambda(matches, team, verbose=verbose)
        except Exception as exc:
            errors.append(f"{team}: {exc}")
    return strengths, errors


def build_match_models(
    fixtures: list[tuple[str, str]],
    strengths: dict[str, dict],
    competition: str = "FIFA World Cup",
) -> dict[tuple[str, str], dict]:
    """Calcula probabilidades para cada partido del grupo."""
    models = {}
    ctx = MatchContext(
        competition=competition,
        stage="group_normal",
        confidence="medium",
    )
    for team_a, team_b in fixtures:
        if team_a not in strengths or team_b not in strengths:
            continue
        res = simular(
            strengths[team_a],
            strengths[team_b],
            venue="neutral",
            context=ctx,
            verbose=False,
        )
        models[(team_a, team_b)] = res
    return models


def simulate_group(
    teams: list[str],
    match_models: dict[tuple[str, str], dict],
    n_sims: int = 5000,
    seed: int | None = None,
) -> dict:
    """Simula una tabla de grupo muchas veces."""
    rng = np.random.default_rng(seed)
    clean_teams = [t.strip() for t in teams if t and t.strip()]
    counters = {
        team: {
            "first": 0,
            "second": 0,
            "qualified": 0,
            "eliminated": 0,
            "avg_points": 0.0,
            "avg_gd": 0.0,
            "avg_gf": 0.0,
        }
        for team in clean_teams
    }

    for _ in range(n_sims):
        table = {
            team: {"pts": 0, "gf": 0, "ga": 0, "gd": 0}
            for team in clean_teams
        }

        for fixture, model in match_models.items():
            team_a, team_b = fixture
            goals_a, goals_b = _sample_score(model, rng)
            _apply_result(table, team_a, team_b, goals_a, goals_b)

        ordered = sorted(
            clean_teams,
            key=lambda t: (
                table[t]["pts"],
                table[t]["gd"],
                table[t]["gf"],
                rng.random(),
            ),
            reverse=True,
        )

        for pos, team in enumerate(ordered, start=1):
            counters[team]["avg_points"] += table[team]["pts"]
            counters[team]["avg_gd"] += table[team]["gd"]
            counters[team]["avg_gf"] += table[team]["gf"]
            if pos == 1:
                counters[team]["first"] += 1
            if pos == 2:
                counters[team]["second"] += 1
            if pos <= 2:
                counters[team]["qualified"] += 1
            else:
                counters[team]["eliminated"] += 1

    rows = []
    for team in clean_teams:
        c = counters[team]
        rows.append({
            "Equipo": team,
            "Clasifica %": round(c["qualified"] / n_sims * 100, 1),
            "1ro %": round(c["first"] / n_sims * 100, 1),
            "2do %": round(c["second"] / n_sims * 100, 1),
            "Eliminado %": round(c["eliminated"] / n_sims * 100, 1),
            "Pts prom.": round(c["avg_points"] / n_sims, 2),
            "DG prom.": round(c["avg_gd"] / n_sims, 2),
            "GF prom.": round(c["avg_gf"] / n_sims, 2),
        })

    rows.sort(key=lambda r: (r["Clasifica %"], r["1ro %"], r["Pts prom."]), reverse=True)
    return {"n_sims": n_sims, "table": rows}


def match_summary_rows(match_models: dict[tuple[str, str], dict]) -> list[dict]:
    """Resumen compacto de probabilidades por partido."""
    rows = []
    for (team_a, team_b), model in match_models.items():
        rows.append({
            "Partido": f"{team_a} vs {team_b}",
            f"Gana {team_a} %": model["victoria_a"],
            "Empate %": model["empate"],
            f"Gana {team_b} %": model["victoria_b"],
            "Marcador mas probable": model["top_marcadores"][0][0],
        })
    return rows


def _apply_result(table: dict, team_a: str, team_b: str, goals_a: int, goals_b: int) -> None:
    table[team_a]["gf"] += goals_a
    table[team_a]["ga"] += goals_b
    table[team_b]["gf"] += goals_b
    table[team_b]["ga"] += goals_a
    table[team_a]["gd"] = table[team_a]["gf"] - table[team_a]["ga"]
    table[team_b]["gd"] = table[team_b]["gf"] - table[team_b]["ga"]

    if goals_a > goals_b:
        table[team_a]["pts"] += 3
    elif goals_b > goals_a:
        table[team_b]["pts"] += 3
    else:
        table[team_a]["pts"] += 1
        table[team_b]["pts"] += 1


def _sample_score(model: dict, rng: np.random.Generator) -> tuple[int, int]:
    lambda_a = model.get("lambda_a")
    lambda_b = model.get("lambda_b")
    if lambda_a is not None and lambda_b is not None:
        goals_a = rng.poisson(max(float(lambda_a), 0.1))
        goals_b = rng.poisson(max(float(lambda_b), 0.1))
        return int(goals_a), int(goals_b)

    scores = []
    weights = []
    for score, pct in model.get("top_marcadores", []):
        try:
            ga, gb = score.split("-")
            scores.append((int(ga), int(gb)))
            weights.append(max(float(pct), 0.01))
        except (ValueError, TypeError):
            continue

    if not scores:
        outcome = rng.choice(
            ["a", "d", "b"],
            p=_norm([model["victoria_a"], model["empate"], model["victoria_b"]]),
        )
        if outcome == "a":
            return 1, 0
        if outcome == "b":
            return 0, 1
        return 1, 1

    idx = rng.choice(len(scores), p=_norm(weights))
    return scores[idx]


def _norm(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        return [1 / len(values)] * len(values)
    return [v / total for v in values]
