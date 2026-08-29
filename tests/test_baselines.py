# tests/test_baselines.py
"""Tests para backtesting/baselines.py."""
import pytest

from backtesting.baselines import uniform_baseline, elo_simple_baseline


def test_uniform_baseline_always_predicts_draw():
    r = uniform_baseline(real_home=1, real_away=0)
    assert r["predicted_result"] == "draw"


def test_elo_simple_baseline_equal_elos_neutral_splits_evenly():
    r = elo_simple_baseline(elo_a=1600, elo_b=1600, venue="neutral",
                            real_home=1, real_away=1)
    # p_draw fijo en 26%, resto repartido 50/50 -> 37%/26%/37%.
    # calcular_metricas desempata a favor de "home" cuando home==away, asi
    # que con Elos iguales el baseline predice local.
    assert r["predicted_result"] == "home"


def test_elo_simple_baseline_home_venue_bonus_can_flip_prediction():
    # B es un poco mejor que A -> en cancha neutral el baseline favorece a B.
    # Jugando A de local, el venue_bonus (+60 elo) alcanza para dar vuelta la
    # prediccion a favor de A.
    r_neutral = elo_simple_baseline(elo_a=1600, elo_b=1650, venue="neutral",
                                    real_home=1, real_away=0)
    r_home    = elo_simple_baseline(elo_a=1600, elo_b=1650, venue="home_a",
                                    real_home=1, real_away=0)
    assert r_neutral["predicted_result"] == "away"
    assert r_home["predicted_result"]    == "home"


def test_elo_simple_baseline_stronger_team_favored():
    r = elo_simple_baseline(elo_a=2000, elo_b=1500, venue="neutral",
                            real_home=2, real_away=0)
    assert r["predicted_result"] == "home"
    assert r["result_correct"] is True
