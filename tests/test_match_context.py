# tests/test_match_context.py
"""Tests para model/match_context.py."""
from datetime import date, timedelta

from model.match_context import MatchContext
from config import MATCH_INTENSITY, TEAM_MOTIVATION, LINEUP_WEIGHT, H2H_MIN_MATCHES


def test_intensity_known_stage():
    ctx = MatchContext(stage="final_champions")
    assert ctx.intensity() == MATCH_INTENSITY["final_champions"]


def test_intensity_unknown_stage_defaults_to_one():
    ctx = MatchContext(stage="algo_inventado")
    assert ctx.intensity() == 1.00


def test_motivation_factor_known():
    ctx = MatchContext(motivation_a="must_win", motivation_b="rotation")
    assert ctx.motivation_factor("a") == TEAM_MOTIVATION["must_win"]
    assert ctx.motivation_factor("b") == TEAM_MOTIVATION["rotation"]


def test_lineup_factor_unknown_status_is_neutral():
    ctx = MatchContext(lineup_status_a="unknown")
    assert ctx.lineup_factor("a") == 1.00


def test_lineup_factor_known_status():
    ctx = MatchContext(lineup_status_a="reserves")
    assert ctx.lineup_factor("a") == LINEUP_WEIGHT["reserves"]


def test_second_leg_adjustment_no_second_leg():
    ctx = MatchContext(is_second_leg=False)
    assert ctx.second_leg_adjustment() == (1.0, 1.0)


def test_second_leg_adjustment_table():
    cases = {
        2:  (0.88, 1.15),
        1:  (0.93, 1.08),
        0:  (1.00, 1.00),
        -1: (1.08, 0.93),
        -2: (1.15, 0.88),
    }
    for diff, expected in cases.items():
        ga = 3
        gb = ga - diff
        ctx = MatchContext(is_second_leg=True, first_leg_score=(ga, gb))
        assert ctx.second_leg_adjustment() == expected


def test_h2h_adjustment_ignored_below_minimum_matches():
    h2h = [{"date": "2026-01-01", "goals_a": 3, "goals_b": 0}
           for _ in range(H2H_MIN_MATCHES - 1)]
    ctx = MatchContext(h2h_matches=h2h)

    lam_a, lam_b = ctx.h2h_adjustment(1.5, 1.2)
    assert (lam_a, lam_b) == (1.5, 1.2)


def test_h2h_adjustment_applied_with_enough_recent_matches():
    h2h = [{"date": date.today().isoformat(), "goals_a": 4, "goals_b": 0}
           for _ in range(H2H_MIN_MATCHES)]
    ctx = MatchContext(h2h_matches=h2h)

    lam_a, lam_b = ctx.h2h_adjustment(1.0, 1.0)
    # w=0.05: lam_a = 0.95*1.0 + 0.05*4 = 1.15 ; lam_b = 0.95*1.0 + 0.05*0 = 0.95
    assert round(lam_a, 4) == 1.15
    assert round(lam_b, 4) == 0.95


def test_h2h_matches_older_than_max_years_are_filtered_out():
    old_date = (date.today() - timedelta(days=365 * 5)).isoformat()
    h2h = [{"date": old_date, "goals_a": 5, "goals_b": 0}
           for _ in range(H2H_MIN_MATCHES)]
    ctx = MatchContext(h2h_matches=h2h)

    # Todos son viejos -> quedan 0 validos -> por debajo del minimo -> se ignora
    lam_a, lam_b = ctx.h2h_adjustment(1.0, 1.0)
    assert (lam_a, lam_b) == (1.0, 1.0)
