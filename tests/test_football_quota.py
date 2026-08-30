# tests/test_football_quota.py
"""Tests para sources/football_quota.py (todo offline, sin red)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sources import football_quota


@pytest.fixture(autouse=True)
def isolated_quota_file(tmp_path, monkeypatch):
    """Cada test usa su propio archivo de cuota, no el real de cache/."""
    monkeypatch.setattr(football_quota, "QUOTA_PATH", str(tmp_path / "quota.json"))


class _FakeResponse:
    def __init__(self, headers: dict):
        self.headers = headers


def test_has_budget_true_when_no_file_yet():
    assert football_quota.has_budget() is True


def test_has_budget_true_on_a_new_day():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    football_quota._write(yesterday, 0)  # se agoto ayer
    assert football_quota.has_budget() is True


def test_has_budget_false_when_exhausted_today():
    football_quota.mark_exhausted()
    assert football_quota.has_budget() is False


def test_update_from_response_persists_remaining():
    resp = _FakeResponse({"x-ratelimit-requests-remaining": "42"})
    football_quota.update_from_response(resp)

    with open(football_quota.QUOTA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data["remaining"] == 42
    assert data["date"] == football_quota._today_utc()


def test_update_from_response_ignores_missing_header():
    resp = _FakeResponse({})
    football_quota.update_from_response(resp)
    assert football_quota.has_budget() is True  # no rompe nada, sigue como estaba


def test_has_budget_false_after_remaining_hits_zero():
    resp = _FakeResponse({"x-ratelimit-requests-remaining": "0"})
    football_quota.update_from_response(resp)
    assert football_quota.has_budget() is False
