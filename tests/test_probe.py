"""Offline tests for the source probe's pagination.

The first version of the probe reported a false negative because it fetched a
single 1000-bar page and then judged the source for returning exactly what it
asked for. These tests pin the fix without touching the network.
"""

import sys, pathlib, types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd
import pytest

import probe_sources as ps

HOUR = 3600
NEWEST = 1_760_000_000  # arbitrary fixed epoch second


def fake_api(total_bars: int, *, stuck: bool = False):
    """Serve descending hourly bars, oldest-first exhaustion, like GeckoTerminal."""
    def get(url, params=None, headers=None, timeout=None):
        params = params or {}
        before = params.get("before_timestamp", NEWEST + HOUR)
        limit = params.get("limit", ps.PAGE_LIMIT)
        if stuck:                                   # API keeps replaying one page
            start = NEWEST
        else:
            start = min(before - HOUR, NEWEST)
        oldest_allowed = NEWEST - total_bars * HOUR
        rows = [[t, 1, 1, 1, 1, 1]
                for t in range(start, max(start - limit * HOUR, oldest_allowed), -HOUR)]
        rows = rows[:limit]
        resp = types.SimpleNamespace()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"data": {"attributes": {"ohlcv_list": rows}}}
        return resp
    return get


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(ps.time, "sleep", lambda *_: None)


def test_pages_past_the_thousand_bar_cap(monkeypatch):
    """2500 bars must come back as 2500, not truncated at one page."""
    monkeypatch.setattr(ps.requests, "get", fake_api(2500))
    ts, capped = ps._paged_ohlcv("pool")
    assert len(ts) == 2500
    assert not capped
    assert (ts.max() - ts.min()).total_seconds() / 86400 > ps.MIN_DAYS * 0.5


def test_reports_when_it_stopped_at_the_page_cap(monkeypatch):
    """Deep history must be flagged as capped so it is never read as 'no data'."""
    monkeypatch.setattr(ps.requests, "get", fake_api(10_000_000))
    ts, capped = ps._paged_ohlcv("pool")
    assert capped
    assert len(ts) == ps.PAGE_LIMIT * ps.MAX_PAGES


def test_short_history_is_not_flagged_as_capped(monkeypatch):
    monkeypatch.setattr(ps.requests, "get", fake_api(120))
    ts, capped = ps._paged_ohlcv("pool")
    assert len(ts) == 120 and not capped


def test_repeated_page_terminates(monkeypatch):
    """A misbehaving API that replays a page must not spin forever."""
    monkeypatch.setattr(ps.requests, "get", fake_api(5000, stuck=True))
    ts, capped = ps._paged_ohlcv("pool")
    assert len(ts) == ps.PAGE_LIMIT and not capped


def test_weekend_share_of_a_continuous_series_matches_wall_clock():
    """Sanity-check the metric that decides whether a source is really 7x24."""
    ts = pd.date_range("2026-01-01", periods=24 * 90, freq="h", tz="UTC")
    assert 0.26 < float((ts.dayofweek >= 5).mean()) < 0.30


def test_session_only_series_is_caught():
    ts = pd.date_range("2026-01-01", periods=24 * 90, freq="h", tz="UTC")
    weekday_only = ts[ts.dayofweek < 5]
    assert float((weekday_only.dayofweek >= 5).mean()) < ps.MIN_WEEKEND_SHARE
