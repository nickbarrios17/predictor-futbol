# tests/test_metrics.py
"""Tests para backtesting/metrics.py."""
import math

import pytest

from backtesting.metrics import calcular_metricas, resumen_metricas


def test_calcular_metricas_brier_and_log_loss_hand_computed():
    r = calcular_metricas(
        prob_home=70, prob_draw=20, prob_away=10,
        over25_prob=60, btts_prob=40,
        real_home=2, real_away=0,
    )
    # brier = ((0.7-1)^2 + (0.2-0)^2 + (0.1-0)^2) / 3
    expected_brier = ((0.7 - 1) ** 2 + (0.2 - 0) ** 2 + (0.1 - 0) ** 2) / 3
    expected_log_loss = -math.log(0.7)

    assert r["brier_score"] == pytest.approx(round(expected_brier, 4))
    assert r["log_loss"]    == pytest.approx(round(expected_log_loss, 4))
    assert r["actual_result"]    == "home"
    assert r["predicted_result"] == "home"
    assert r["result_correct"]   is True


def test_calcular_metricas_over25_and_btts_correctness():
    r = calcular_metricas(
        prob_home=70, prob_draw=20, prob_away=10,
        over25_prob=60, btts_prob=40,
        real_home=2, real_away=0,
    )
    # 2 goles totales -> no es over 2.5, pero el modelo dijo 60% (>=50 -> "predijo over")
    assert r["real_over25"]    is False
    assert r["over25_correct"] is False
    # BTTS real es False (away no metio), modelo dijo 40% (<50 -> "predijo no")
    assert r["real_btts"]      is False
    assert r["btts_correct"]   is True


def test_calcular_metricas_score_correct_when_top_score_matches():
    r = calcular_metricas(
        prob_home=70, prob_draw=20, prob_away=10,
        over25_prob=60, btts_prob=40,
        real_home=2, real_away=1,
        top_scores=[("2-1", 18.0), ("1-1", 12.0)],
    )
    assert r["score_correct"] is True


def test_calcular_metricas_draw_prediction():
    r = calcular_metricas(
        prob_home=30, prob_draw=40, prob_away=30,
        over25_prob=50, btts_prob=50,
        real_home=1, real_away=1,
    )
    assert r["predicted_result"] == "draw"
    assert r["actual_result"]    == "draw"
    assert r["result_correct"]   is True


def test_resumen_metricas_aggregates_accuracy():
    resultados = [
        calcular_metricas(70, 20, 10, 60, 40, real_home=2, real_away=0),  # acierta home
        calcular_metricas(70, 20, 10, 60, 40, real_home=0, real_away=2),  # falla (predijo home, fue away)
    ]
    resumen = resumen_metricas(resultados)

    assert resumen["total_partidos"] == 2
    assert resumen["accuracy_1x2"] == 50.0
    assert resumen["n_pred_home"] == 2


def test_resumen_metricas_empty_returns_error():
    assert "error" in resumen_metricas([])
