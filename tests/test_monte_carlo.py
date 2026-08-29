# tests/test_monte_carlo.py
"""Tests para model/monte_carlo.py (grilla Dixon-Coles)."""
import pytest

from model.monte_carlo import simular
from model.match_context import MatchContext


def _strength(attack: float = 1.0, defense: float = 1.0) -> dict:
    return {
        "attack_home": attack, "attack_away": attack,
        "defense_home": defense, "defense_away": defense,
        "attack_global": attack, "defense_global": defense,
        "team_elo": 1600, "partidos_usados": 10,
    }


def test_result_probabilities_sum_to_100():
    res = simular(_strength(), _strength(), venue="neutral")
    total = res["victoria_a"] + res["empate"] + res["victoria_b"]
    assert total == pytest.approx(100.0, abs=0.2)


def test_over_under_pairs_sum_to_100():
    res = simular(_strength(), _strength(), venue="neutral")
    ou = res["ou"]
    for line in ["05", "15", "25", "35"]:
        assert ou[f"over_{line}"] + ou[f"under_{line}"] == pytest.approx(100.0, abs=0.2)


def test_btts_pair_sums_to_100():
    res = simular(_strength(), _strength(), venue="neutral")
    assert res["btts_si"] + res["btts_no"] == pytest.approx(100.0, abs=0.1)


def test_equal_strength_neutral_venue_is_symmetric():
    res = simular(_strength(), _strength(), venue="neutral")
    assert res["victoria_a"] == pytest.approx(res["victoria_b"], abs=0.5)


def test_stronger_attack_increases_win_probability():
    fuerte = _strength(attack=1.6)
    debil  = _strength(attack=0.6)
    res = simular(fuerte, debil, venue="neutral")
    assert res["victoria_a"] > res["victoria_b"]


def test_top_marcadores_has_ten_entries_sorted_desc():
    res = simular(_strength(), _strength(), venue="neutral")
    top = res["top_marcadores"]
    assert len(top) == 10
    pcts = [pct for _, pct in top]
    assert pcts == sorted(pcts, reverse=True)


def test_context_intensity_scales_down_lambdas():
    ctx_final = MatchContext(stage="final_champions")  # intensity 0.82
    ctx_normal = MatchContext(stage="league_normal")    # intensity 1.00

    res_final  = simular(_strength(), _strength(), venue="neutral", context=ctx_final)
    res_normal = simular(_strength(), _strength(), venue="neutral", context=ctx_normal)

    assert res_final["lambda_a"] < res_normal["lambda_a"]
