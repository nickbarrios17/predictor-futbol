# tests/test_football_data_fallback.py
"""
Tests para sources/football_data.py: enrutamiento primaria/fallback y
el tagging de IDs por fuente (todo offline, con las funciones de
sources.api_football_source / sources.api_source mockeadas).
"""
import pytest

from sources import football_data
from sources import football_quota


@pytest.fixture(autouse=True)
def isolated_quota_file(tmp_path, monkeypatch):
    monkeypatch.setattr(football_quota, "QUOTA_PATH", str(tmp_path / "quota.json"))


def test_search_team_uses_primary_when_budget_available(monkeypatch):
    monkeypatch.setattr(football_data.primary, "search_team",
                        lambda name: [{"id": 123, "name": "River Plate"}])
    fallback_called = []
    monkeypatch.setattr(football_data.fallback, "search_team",
                        lambda name: fallback_called.append(name) or [])

    result = football_data.search_team("River")

    assert result == [{"id": "af_123", "name": "River Plate"}]
    assert fallback_called == []


def test_search_team_falls_back_on_quota_exceeded(monkeypatch):
    def raise_quota(name):
        # En la vida real, QuotaExceeded siempre se levanta junto con
        # mark_exhausted() (ver api_football_source._get) -- se replica
        # eso acá para no romper ese invariante en el mock.
        football_quota.mark_exhausted()
        raise football_data.primary.QuotaExceeded("429")
    monkeypatch.setattr(football_data.primary, "search_team", raise_quota)
    monkeypatch.setattr(football_data.fallback, "search_team",
                        lambda name: [{"id": 456, "name": "River Plate"}])

    result = football_data.search_team("River")

    assert result == [{"id": "ss_456", "name": "River Plate"}]
    assert football_quota.has_budget() is False  # quedo marcada agotada


def test_search_team_skips_primary_when_no_budget(monkeypatch):
    monkeypatch.setattr(football_quota, "has_budget", lambda: False)
    primary_called = []
    monkeypatch.setattr(football_data.primary, "search_team",
                        lambda name: primary_called.append(name) or [])
    monkeypatch.setattr(football_data.fallback, "search_team",
                        lambda name: [{"id": 456, "name": "River Plate"}])

    result = football_data.search_team("River")

    assert primary_called == []
    assert result == [{"id": "ss_456", "name": "River Plate"}]


def test_empty_result_from_primary_does_not_trigger_fallback(monkeypatch):
    monkeypatch.setattr(football_data.primary, "search_team", lambda name: [])
    fallback_called = []
    monkeypatch.setattr(football_data.fallback, "search_team",
                        lambda name: fallback_called.append(name) or [])

    result = football_data.search_team("Equipo Que No Existe")

    assert result == []
    assert fallback_called == []  # un miss normal no gasta cuota de SofaScore


def test_get_team_matches_routes_by_id_prefix_to_primary(monkeypatch):
    calls = []
    monkeypatch.setattr(football_data.primary, "get_team_matches",
                        lambda team_id, limit: calls.append((team_id, limit)) or [])
    monkeypatch.setattr(football_data.fallback, "get_team_matches",
                        lambda team_id, limit: (_ for _ in ()).throw(
                            AssertionError("no deberia llamar al fallback")))

    football_data.get_team_matches("af_123", limit=20)

    assert calls == [("123", 20)]


def test_get_team_matches_routes_by_id_prefix_to_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(football_data.fallback, "get_team_matches",
                        lambda team_id, limit: calls.append((team_id, limit)) or [])
    monkeypatch.setattr(football_data.primary, "get_team_matches",
                        lambda team_id, limit: (_ for _ in ()).throw(
                            AssertionError("no deberia llamar a la primaria")))

    football_data.get_team_matches("ss_456", limit=20)

    assert calls == [("456", 20)]


def test_get_team_matches_with_untagged_id_raises():
    with pytest.raises(ValueError):
        football_data.get_team_matches("123", limit=20)


def test_search_then_matches_stays_on_same_source_even_if_quota_flips(monkeypatch):
    """
    Regresion del bug encontrado durante el diseño: el ID que devuelve
    search_team() debe fijar la fuente para las llamadas siguientes,
    sin volver a mirar la cuota (que puede haber cambiado justo en el
    medio).
    """
    monkeypatch.setattr(football_data.primary, "search_team",
                        lambda name: [{"id": 123, "name": "River Plate"}])

    equipo = football_data.search_team("River")[0]

    # Ahora la cuota se agota justo despues de resolver el equipo.
    monkeypatch.setattr(football_quota, "has_budget", lambda: False)

    calls = []
    monkeypatch.setattr(football_data.primary, "get_team_matches",
                        lambda team_id, limit: calls.append(team_id) or [])
    monkeypatch.setattr(football_data.fallback, "get_team_matches",
                        lambda team_id, limit: (_ for _ in ()).throw(
                            AssertionError("no deberia usar el ID de la primaria en el fallback")))

    football_data.get_team_matches(equipo["id"], limit=20)

    assert calls == ["123"]  # se mantuvo en la fuente que resolvio el ID
