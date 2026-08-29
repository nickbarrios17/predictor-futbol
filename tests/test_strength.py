# tests/test_strength.py
"""Tests para model/strength.py."""
from datetime import date, timedelta

import pytest

from model.strength import calcular_lambda, time_decay, is_too_old
from config import MAX_MONTHS_HISTORY


def _recent_date(months_ago: int = 0) -> str:
    return (date.today() - timedelta(days=30 * months_ago)).strftime("%Y-%m-%d")


def _synthetic_history(team_name: str, rival: str, n: int = 6) -> list[dict]:
    matches = []
    for i in range(n):
        matches.append({
            "date": _recent_date(i),
            "team_home": team_name if i % 2 == 0 else rival,
            "team_away": rival if i % 2 == 0 else team_name,
            "goals_home": 2,
            "goals_away": 1,
            "competition": "Premier League",
        })
    return matches


def test_calcular_lambda_raises_on_empty_history():
    with pytest.raises(ValueError):
        calcular_lambda([], "Equipo Fantasma")


def test_calcular_lambda_counts_matches_within_window():
    matches = _synthetic_history("Estelar FC", "Rival FC", n=6)
    resultado = calcular_lambda(matches, "Estelar FC")
    assert resultado["partidos_usados"] == 6


def test_calcular_lambda_ignores_matches_older_than_max_months():
    matches = _synthetic_history("Estelar FC", "Rival FC", n=4)
    matches.append({
        "date":        _recent_date(MAX_MONTHS_HISTORY + 6),
        "team_home":   "Estelar FC",
        "team_away":   "Rival FC",
        "goals_home":  9,
        "goals_away":  0,
        "competition": "Premier League",
    })
    resultado = calcular_lambda(matches, "Estelar FC")
    assert resultado["partidos_usados"] == 4


def test_calcular_lambda_attack_and_defense_are_positive():
    matches = _synthetic_history("Estelar FC", "Rival FC", n=8)
    resultado = calcular_lambda(matches, "Estelar FC")
    assert resultado["attack_global"] > 0
    assert resultado["defense_global"] > 0
    assert resultado["attack_home"] > 0
    assert resultado["attack_away"] > 0


def test_time_decay_is_one_for_todays_match():
    assert time_decay(date.today().strftime("%Y-%m-%d")) == pytest.approx(1.0, abs=1e-9)


def test_time_decay_decreases_with_age():
    recent = time_decay(_recent_date(1))
    older = time_decay(_recent_date(12))
    assert recent > older


def test_time_decay_invalid_date_returns_half():
    assert time_decay("fecha-invalida") == 0.5


def test_is_too_old_boundary():
    assert is_too_old(_recent_date(MAX_MONTHS_HISTORY + 1)) is True
    assert is_too_old(_recent_date(1)) is False
