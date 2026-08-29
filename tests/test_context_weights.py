# tests/test_context_weights.py
"""Tests para model/context.py."""
from model.context import get_competition_weight, get_stakes_weight, get_all_weights
from config import COMPETITION_WEIGHT, STAKES_WEIGHT


def test_get_competition_weight_known_competition():
    assert get_competition_weight("UEFA Champions League") == \
        COMPETITION_WEIGHT["UEFA Champions League"]


def test_get_competition_weight_unknown_falls_back():
    assert get_competition_weight("Torneo Regional Inventado") == \
        COMPETITION_WEIGHT["Unknown"]


def test_get_stakes_weight_detects_final():
    assert get_stakes_weight("UEFA Champions League", "Final") == \
        STAKES_WEIGHT["final"]


def test_get_stakes_weight_detects_semifinal():
    assert get_stakes_weight("Copa America", "Semifinal") == \
        STAKES_WEIGHT["semifinal"]


def test_get_stakes_weight_detects_group_stage():
    assert get_stakes_weight("FIFA World Cup", "Group Stage - 3") == \
        STAKES_WEIGHT["group_stage"]


def test_get_stakes_weight_detects_friendly():
    assert get_stakes_weight("Int. Friendly Games", "") == \
        STAKES_WEIGHT["friendly_normal"]


def test_get_stakes_weight_defaults_to_league_normal():
    assert get_stakes_weight("Premier League", "Round 14") == \
        STAKES_WEIGHT["league_normal"]


def test_get_all_weights_combines_comp_and_stakes():
    match = {"competition": "UEFA Champions League", "round": "Final"}
    weights = get_all_weights(match)

    assert weights["w_comp"] == COMPETITION_WEIGHT["UEFA Champions League"]
    assert weights["w_stakes"] == STAKES_WEIGHT["final"]
    assert weights["w_combined"] == weights["w_comp"] * weights["w_stakes"]
