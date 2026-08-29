# tests/test_elo.py
"""Tests para features/elo.py."""
from features.elo import EloRating, BASE_RATINGS


def test_opponent_factor_is_clamped_to_plus_minus_40_pct():
    elo = EloRating()
    # Rival mucho mas fuerte que el promedio de la competicion -> clamp a 1.40
    factor_fuerte = elo.get_opponent_factor("Spain", "World Cup Qualification")
    assert factor_fuerte <= 1.40

    # Rival mucho mas debil -> clamp a 0.60
    factor_debil = elo.get_opponent_factor("Cuba", "UEFA Champions League")
    assert factor_debil >= 0.60


def test_get_rating_exact_match():
    elo = EloRating()
    assert elo.get_rating("Argentina") == BASE_RATINGS["Argentina"]


def test_get_rating_partial_match_alias():
    elo = EloRating()
    # "Bosnia" no esta como clave exacta, pero "Bosnia & Herzegovina" si
    assert elo.get_rating("Bosnia") == BASE_RATINGS["Bosnia & Herzegovina"]


def test_get_rating_unknown_team_falls_back_to_competition_avg():
    elo = EloRating()
    rating = elo.get_rating("Equipo Totalmente Desconocido FC", "Premier League")
    assert rating == elo.get_competition_avg("Premier League")


def test_get_competition_avg_partial_key_match():
    elo = EloRating()
    avg = elo.get_competition_avg("CONMEBOL World Cup Qualification 2026")
    assert avg == 1600  # matchea "World Cup Qualification"


def test_get_competition_avg_unknown_falls_back_to_default():
    elo = EloRating()
    assert elo.get_competition_avg("Liga Regional Desconocida") == \
        elo.get_competition_avg("default")


def _synthetic_matches(team_name: str, rival: str, n: int = 6) -> list[dict]:
    """Historial sintetico: team_name gana siempre de local contra el mismo rival."""
    matches = []
    for i in range(n):
        matches.append({
            "date": f"2026-01-{i + 1:02d}",
            "team_home": team_name,
            "team_away": rival,
            "goals_home": 2,
            "goals_away": 0,
            "competition": "Int. Friendly Games",
        })
    return matches


def test_compute_rating_is_pure_and_deterministic():
    """
    Regresion del bug: calcular el rating dos veces con el mismo historial
    debe dar exactamente el mismo resultado. Con el `update_from_matches`
    original (que muta self._ratings) la segunda llamada arranca desde el
    rating ya elevado por la primera, así que los resultados difieren.
    """
    matches = _synthetic_matches("Testland", "Rivalia")

    elo_1 = EloRating()
    rating_first_call = elo_1.compute_rating(matches, "Testland")
    rating_second_call = elo_1.compute_rating(matches, "Testland")

    assert rating_first_call == rating_second_call


def test_compute_rating_does_not_mutate_shared_state():
    matches = _synthetic_matches("Testland", "Rivalia")
    elo = EloRating()

    base_rating_before = elo.get_rating("Testland")
    elo.compute_rating(matches, "Testland")
    base_rating_after = elo.get_rating("Testland")

    assert base_rating_before == base_rating_after


def test_compute_rating_matches_expected_direction():
    """Un equipo que gana siempre de local debe terminar con Elo mas alto que el base."""
    matches = _synthetic_matches("Testland", "Rivalia")
    elo = EloRating()

    base_rating = elo.get_rating("Testland")
    final_rating = elo.compute_rating(matches, "Testland")

    assert final_rating > base_rating


def test_compute_rating_with_few_matches_returns_base_rating():
    """Con menos de 5 partidos no hay suficiente señal para actualizar."""
    matches = _synthetic_matches("Testland", "Rivalia", n=3)
    elo = EloRating()

    assert elo.compute_rating(matches, "Testland") == elo.get_rating("Testland")
