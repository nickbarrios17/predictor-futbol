# tests/test_api_source_parsing.py
"""
Tests para sources/api_source.py — parseo de partidos, incluyendo la
regresión del bug de marcadores de tanda de penales (todo offline,
con eventos sintéticos con forma de SofaScore).
"""
from sources.api_source import (
    _is_valid,
    _parse_match,
    MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT,
)


def _event(home_current, away_current, home_normaltime=None,
          away_normaltime=None, home="River Plate", away="Boca Juniors"):
    home_score = {"current": home_current}
    away_score = {"current": away_current}
    if home_normaltime is not None:
        home_score["normaltime"] = home_normaltime
    if away_normaltime is not None:
        away_score["normaltime"] = away_normaltime

    return {
        "startTimestamp": 1700000000,
        "homeTeam": {"name": home},
        "awayTeam": {"name": away},
        "homeScore": home_score,
        "awayScore": away_score,
        "tournament": {"name": "CONMEBOL Sudamericana", "category": {"name": "South America"}},
        "roundInfo": {"name": "Round of 16"},
    }


def test_normal_match_uses_current_when_no_normaltime():
    ev = _event(home_current=2, away_current=1)
    assert _is_valid(ev) is True
    parsed = _parse_match(ev)
    assert parsed["goals_home"] == 2
    assert parsed["goals_away"] == 1


def test_penalty_shootout_score_is_rejected_when_no_normaltime_field():
    """
    Regresion del bug real: River Plate 8-9 Independiente Santa Fe en
    un cruce que terminó 0-0 en la cancha (Copa Sudamericana, Round of
    16). Sin "normaltime" disponible, el marcador inverosímil se
    descarta en vez de usarse como si fueran goles reales.
    """
    ev = _event(home_current=8, away_current=9)
    assert _is_valid(ev) is False


def test_normaltime_preferred_over_current_when_present():
    """Si SofaScore trae "normaltime", se usa eso y no el marcador de penales."""
    ev = _event(home_current=8, away_current=9,
               home_normaltime=0, away_normaltime=0)
    assert _is_valid(ev) is True
    parsed = _parse_match(ev)
    assert parsed["goals_home"] == 0
    assert parsed["goals_away"] == 0


def test_plausible_lopsided_blowout_is_not_rejected():
    """Una goleada real (un lado alto, el otro bajo/cero) no debe filtrarse."""
    ev = _event(home_current=8, away_current=0)
    assert _is_valid(ev) is True


def test_boundary_only_one_side_high_is_not_rejected():
    ev = _event(home_current=MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT, away_current=1)
    assert _is_valid(ev) is True


def test_boundary_both_sides_at_threshold_is_rejected():
    ev = _event(home_current=MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT,
               away_current=MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT)
    assert _is_valid(ev) is False

    ev_below = _event(home_current=MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT - 1,
                      away_current=MIN_GOALS_BOTH_SIDES_LOOKS_LIKE_SHOOTOUT - 1)
    assert _is_valid(ev_below) is True


def test_missing_score_is_invalid():
    ev = _event(home_current=None, away_current=1)
    assert _is_valid(ev) is False
