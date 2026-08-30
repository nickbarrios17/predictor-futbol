# tests/test_api_football_source.py
"""
Tests para sources/api_football_source.py (todo offline: se mockea
requests.get / _get, nunca se pega a la API real).
"""
from datetime import datetime, timezone

import pytest

from sources import api_football_source as afs
from sources import football_quota


@pytest.fixture(autouse=True)
def isolated_quota_file(tmp_path, monkeypatch):
    monkeypatch.setattr(football_quota, "QUOTA_PATH", str(tmp_path / "quota.json"))


def _epoch(y, m, d, h=12) -> int:
    return int(datetime(y, m, d, h, 0, 0, tzinfo=timezone.utc).timestamp())


def _fixture(status="FT", timestamp=None, home="Manchester United",
            away="Newcastle", gh=3, ga=1, comp="Premier League",
            country="England", round_="Regular Season - 9"):
    return {
        "fixture": {
            "id": 999,
            "timestamp": timestamp or _epoch(2026, 1, 15),
            "status": {"short": status},
        },
        "league": {"name": comp, "country": country, "round": round_},
        "teams": {
            "home": {"id": 33, "name": home},
            "away": {"id": 34, "name": away},
        },
        "goals": {"home": gh, "away": ga},
    }


def test_parse_match_maps_to_internal_shape():
    parsed = afs._parse_match(_fixture())
    assert parsed["date"]        == "2026-01-15"
    assert parsed["team_home"]   == "Manchester United"
    assert parsed["team_away"]   == "Newcastle"
    assert parsed["goals_home"]  == 3
    assert parsed["goals_away"]  == 1
    assert parsed["competition"] == "Premier League"
    assert parsed["round"]       == "Regular Season - 9"


def test_parse_upcoming_match_maps_to_internal_shape():
    parsed = afs._parse_upcoming_match(_fixture(status="NS"))
    assert parsed["event_id"]     == 999
    assert parsed["date"]         == "2026-01-15"
    assert parsed["team_home_id"] == 33
    assert parsed["team_away_id"] == 34
    assert parsed["round_name"]   == "Regular Season - 9"


def test_get_team_matches_filters_unfinished_statuses(monkeypatch):
    raw = [
        _fixture(status="FT"),
        _fixture(status="NS"),   # todavia no jugado, no deberia entrar
        _fixture(status="PST"),  # postergado, tampoco
    ]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    result = afs.get_team_matches(33, limit=10)
    assert len(result) == 1


def test_get_team_next_matches_filters_finished_statuses(monkeypatch):
    raw = [
        _fixture(status="NS"),
        _fixture(status="FT"),  # ya jugado, no deberia entrar
    ]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    result = afs.get_team_next_matches(33, limit=10)
    assert len(result) == 1


def test_search_team_maps_id_and_name(monkeypatch):
    raw = [{"team": {"id": 33, "name": "Manchester United"}}]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    result = afs.search_team("Manchester")
    assert result == [{"id": 33, "name": "Manchester United"}]


def test_search_tournament_maps_id_name_country(monkeypatch):
    raw = [{"league": {"id": 39, "name": "Premier League"},
            "country": {"name": "England"}}]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    result = afs.search_tournament("Premier")
    assert result == [{"id": 39, "name": "Premier League", "country": "England"}]


def test_get_tournament_current_season_id_picks_current_year(monkeypatch):
    raw = [{"seasons": [
        {"year": 2024, "current": False},
        {"year": 2025, "current": True},
    ]}]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    assert afs.get_tournament_current_season_id(39) == 2025


def test_get_tournament_current_season_id_returns_none_if_no_current(monkeypatch):
    raw = [{"seasons": [{"year": 2024, "current": False}]}]
    monkeypatch.setattr(afs, "_get", lambda path, params: raw)

    assert afs.get_tournament_current_season_id(39) is None


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data  = json_data or {"response": []}
        self.headers      = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_get_raises_quota_exceeded_on_429(monkeypatch):
    monkeypatch.setattr(afs.requests, "get",
                        lambda *a, **k: _FakeResponse(status_code=429))

    with pytest.raises(afs.QuotaExceeded):
        afs._get("teams", {"search": "River"})

    assert football_quota.has_budget() is False


def test_get_updates_quota_from_response_headers(monkeypatch):
    monkeypatch.setattr(
        afs.requests, "get",
        lambda *a, **k: _FakeResponse(
            headers={"x-ratelimit-requests-remaining": "77"},
            json_data={"response": []},
        ),
    )
    afs._get("teams", {"search": "River"})

    with open(football_quota.QUOTA_PATH, encoding="utf-8") as f:
        import json as _json
        assert _json.load(f)["remaining"] == 77
