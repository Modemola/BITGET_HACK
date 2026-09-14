"""Offline tests for the ingestion script's rate limiting and resumption.

Two live runs were lost to this script: the first fetched a single 1000-bar page
and judged the source for returning exactly what was asked, the second fired
eight unspaced search calls into a 30-call-per-minute limit. Both failure modes
are pinned here so neither can return silently.
"""

import sys, pathlib, types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd
import pytest

import probe_sources as ps

HOUR = 3600
NEWEST = 1_760_000_000


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    """Record sleeps instead of taking them, and clear the limiter between tests."""
    slept: list[float] = []
    monkeypatch.setattr(ps.time, "sleep", lambda s: slept.append(s))
    monkeypatch.setattr(ps, "_last_call", 0.0)
    return slept


def _resp(status=200, payload=None, headers=None):
    r = types.SimpleNamespace(status_code=status, headers=headers or {})
    r.json = lambda: payload or {}
    def raise_for_status():
        if status >= 400:
            raise ps.requests.HTTPError(f"{status} Client Error")
    r.raise_for_status = raise_for_status
    return r


def test_calls_are_spaced_by_the_rate_limiter(monkeypatch, _reset):
    monkeypatch.setattr(ps.requests, "get", lambda *a, **k: _resp(payload={"ok": 1}))
    clock = iter([0.0, 0.0, 0.1, 0.1, 0.2, 0.2])
    monkeypatch.setattr(ps.time, "monotonic", lambda: next(clock))

    ps.api_get("/a"); ps.api_get("/b")

    assert _reset, "expected the limiter to sleep between calls"
    assert max(_reset) >= ps.MIN_INTERVAL_S - 0.5


def test_retries_on_429_then_succeeds(monkeypatch, _reset):
    seq = [_resp(429), _resp(429), _resp(payload={"data": "ok"})]
    monkeypatch.setattr(ps.requests, "get", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(ps.time, "monotonic", lambda: 1e6)

    assert ps.api_get("/x") == {"data": "ok"}
    assert not seq


def test_401_is_treated_as_throttling_not_auth(monkeypatch, _reset):
    """GeckoTerminal returns 401 under load; retrying is correct, giving up is not."""
    seq = [_resp(401), _resp(payload={"data": "ok"})]
    monkeypatch.setattr(ps.requests, "get", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(ps.time, "monotonic", lambda: 1e6)

    assert ps.api_get("/x") == {"data": "ok"}


def test_backoff_honours_retry_after(monkeypatch, _reset):
    seq = [_resp(429, headers={"Retry-After": "42"}), _resp(payload={"ok": 1})]
    monkeypatch.setattr(ps.requests, "get", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(ps.time, "monotonic", lambda: 1e6)

    ps.api_get("/x")
    assert 42 in _reset


def _page(n, oldest_ts):
    return {"data": {"attributes": {"ohlcv_list":
        [[oldest_ts + i * HOUR, 1, 1, 1, 1, 1] for i in range(n)][::-1]}}}


def test_fetch_pages_past_the_thousand_bar_cap(monkeypatch, tmp_path):
    monkeypatch.setattr(ps, "RAW", tmp_path)
    pages = [_page(ps.PAGE_LIMIT, NEWEST - ps.PAGE_LIMIT * HOUR),
             _page(ps.PAGE_LIMIT, NEWEST - 2 * ps.PAGE_LIMIT * HOUR),
             _page(120, NEWEST - 3 * ps.PAGE_LIMIT * HOUR)]
    monkeypatch.setattr(ps, "api_get", lambda p, params=None: pages.pop(0))

    df = ps.fetch_ohlcv(ps.Candidate("AAPLx", pool="p"), max_pages=6, refresh=True)
    assert len(df) == 2 * ps.PAGE_LIMIT + 120
    assert not pages, "should have paged until the short page ended history"


def test_fetch_writes_after_every_page(monkeypatch, tmp_path):
    """A throttle on page 3 must not cost pages 1 and 2."""
    monkeypatch.setattr(ps, "RAW", tmp_path)
    calls = {"n": 0}

    def flaky(path, params=None):
        calls["n"] += 1
        if calls["n"] == 3:
            raise ps.requests.HTTPError("429")
        return _page(ps.PAGE_LIMIT, NEWEST - calls["n"] * ps.PAGE_LIMIT * HOUR)

    monkeypatch.setattr(ps, "api_get", flaky)
    with pytest.raises(ps.requests.HTTPError):
        ps.fetch_ohlcv(ps.Candidate("AAPLx", pool="p"), max_pages=6, refresh=True)

    saved = pd.read_csv(tmp_path / "AAPLx_hour.csv")
    assert len(saved) == 2 * ps.PAGE_LIMIT, "first two pages must survive the failure"


def test_fetch_catches_up_before_extending_history(monkeypatch, tmp_path):
    """The first request must be anchored at *now*, not at the cache's oldest bar.

    This is the bug that made the fetcher unable to reach the present: it only
    ever paged backwards from the cache minimum, so a stale file stayed stale
    however often it ran, and every new weekend was silently missed.
    """
    monkeypatch.setattr(ps, "RAW", tmp_path)
    seed = pd.DataFrame({"ts": [NEWEST - i * HOUR for i in range(500)],
                         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1})
    seed.to_csv(tmp_path / "AAPLx_hour.csv", index=False)

    calls = []
    def capture(path, params=None):
        calls.append(dict(params or {}))
        # Overlap the cache immediately so catch-up terminates on the first page.
        return _page(10, NEWEST - 5 * HOUR)
    monkeypatch.setattr(ps, "api_get", capture)

    ps.fetch_ohlcv(ps.Candidate("AAPLx", pool="p"), max_pages=1, refresh=False)
    assert calls, "no request was made at all"
    assert "before_timestamp" not in calls[0], \
        "first request must fetch the newest bars, not page backwards from the cache"


def test_stale_cache_gains_new_bars(monkeypatch, tmp_path):
    """A cache with enough history but an old tail must still pull in new bars."""
    monkeypatch.setattr(ps, "RAW", tmp_path)
    # Deep history (well past MIN_DAYS) whose newest bar is four days old.
    stale_end = NEWEST - 96 * HOUR
    seed = pd.DataFrame({"ts": [stale_end - i * HOUR for i in range(24 * 200)],
                         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1})
    seed.to_csv(tmp_path / "AAPLx_hour.csv", index=False)
    assert ps._span_days(seed) >= ps.MIN_DAYS, "fixture must already satisfy the history bar"

    def serve(path, params=None):
        before = (params or {}).get("before_timestamp", NEWEST + HOUR)
        return _page(ps.PAGE_LIMIT, int(before) - ps.PAGE_LIMIT * HOUR)
    monkeypatch.setattr(ps, "api_get", serve)

    df = ps.fetch_ohlcv(ps.Candidate("AAPLx", pool="p"), max_pages=4, refresh=False)
    assert df["ts"].max() > stale_end, \
        "fetcher did not advance past the stale tail - it cannot reach the present"
    assert len(df) > len(seed)


def test_catch_up_stops_once_it_overlaps_the_cache(monkeypatch, tmp_path):
    """Catching up must not re-walk the entire history it already holds."""
    monkeypatch.setattr(ps, "RAW", tmp_path)
    seed = pd.DataFrame({"ts": [NEWEST - i * HOUR for i in range(24 * 200)],
                         "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1})
    seed.to_csv(tmp_path / "AAPLx_hour.csv", index=False)

    calls = []
    def serve(path, params=None):
        calls.append(dict(params or {}))
        before = (params or {}).get("before_timestamp", NEWEST + HOUR)
        return _page(ps.PAGE_LIMIT, int(before) - ps.PAGE_LIMIT * HOUR)
    monkeypatch.setattr(ps, "api_get", serve)

    ps.fetch_ohlcv(ps.Candidate("AAPLx", pool="p"), max_pages=8, refresh=False)
    assert len(calls) == 1, \
        f"an up-to-date cache should need one page, not {len(calls)}"


def test_weekend_share_separates_7x24_from_session_only():
    ts = pd.date_range("2026-01-01", periods=24 * 90, freq="h", tz="UTC")
    assert 0.26 < float((ts.dayofweek >= 5).mean()) < 0.30
    weekday_only = ts[ts.dayofweek < 5]
    assert float((weekday_only.dayofweek >= 5).mean()) < ps.MIN_WEEKEND_SHARE
