"""Tests for the scheduled-event tool.

The tool's most important behaviour is what it does when it has nothing to say.
A weekend blackout with no events in it is the normal case, not a data gap, and
reporting it as "unknown" would push a trader toward assuming the calendar was
merely incomplete. It has to say *nothing is scheduled* and mean it.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from blackout import ClosureClock, Regime
from blackout.calendar_events import (
    SCHEMA, assess, events_after_reopen, events_in_window, historical_overlap,
    load_events, next_blackout,
)

CLOCK = ClosureClock(start="2024-06-01", end="2028-01-01")
FRIDAY = pd.Timestamp("2026-09-11 15:45", tz="America/New_York").tz_convert("UTC")


def synthetic_events(stamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "ts_utc": pd.to_datetime(stamps, utc=True),
        "label": ["Test event"] * len(stamps),
        "category": ["monetary_policy"] * len(stamps),
        "importance": ["high"] * len(stamps),
    })


def test_an_empty_calendar_is_a_frame_not_a_crash(monkeypatch):
    import blackout.calendar_events as ce
    monkeypatch.setattr(ce, "EVENTS_CSV", pathlib.Path("does-not-exist.csv"))
    ev = ce.load_events()
    assert ev.empty
    assert set(SCHEMA) <= set(ev.columns), "callers rely on the columns existing"


def test_nothing_scheduled_is_reported_as_a_finding_not_as_unknown():
    """The normal case. It must be distinguishable from an unpopulated calendar."""
    quiet = synthetic_events(["2026-12-16 19:00"])          # far from our Friday
    result = assess(CLOCK, FRIDAY, quiet)
    assert result["has_window"] is True
    assert result["events_inside"] == 0
    assert result["calendar_populated"] is True, \
        "a populated calendar with no hits must not look like an empty one"


def test_an_unpopulated_calendar_says_so():
    result = assess(CLOCK, FRIDAY, synthetic_events([]))
    assert result["calendar_populated"] is False


def test_an_event_inside_the_window_is_found():
    inside = synthetic_events(["2026-09-12 12:00"])         # Saturday, mid-blackout
    result = assess(CLOCK, FRIDAY, inside)
    assert result["events_inside"] == 1
    assert result["next_event"] == "Test event"


def test_events_after_the_reopen_are_surfaced_separately():
    """A quiet weekend into a rate decision is not a quiet position."""
    after = synthetic_events(["2026-09-16 18:00"])          # Wednesday, post-reopen
    result = assess(CLOCK, FRIDAY, after)
    assert result["events_inside"] == 0
    assert result["events_after"] == 1
    assert result["next_event_ts"] == pd.Timestamp("2026-09-16 18:00", tz="UTC")


def test_the_window_boundary_is_half_open():
    """An event exactly at the reopen belongs to what follows, not to the window."""
    window = next_blackout(CLOCK, FRIDAY)
    at_end = synthetic_events([window["end"].isoformat()])
    assert len(events_in_window(window["start"], window["end"], at_end)) == 0
    assert len(events_after_reopen(CLOCK, FRIDAY, events=at_end)) == 1


def test_lookahead_after_reopen_is_bounded():
    far = synthetic_events(["2026-10-28 18:00"])            # weeks past the reopen
    assert len(events_after_reopen(CLOCK, FRIDAY, events=far)) == 0


def test_historical_overlap_counts_windows_and_events():
    ev = synthetic_events(["2026-09-12 12:00", "2026-09-16 18:00"])
    stats = historical_overlap(CLOCK, ev)
    assert stats["events"] == 2
    assert stats["windows"] > 100, "several years of weekends should be enumerated"
    assert stats["overlaps"] == 1, "only the Saturday event sits inside a blackout"


def test_overlap_of_an_empty_calendar_is_zero_not_an_error():
    stats = historical_overlap(CLOCK, synthetic_events([]))
    assert stats["overlaps"] == 0
    assert stats["events"] == 0


# --- the claim the product makes, checked against the real calendar ---------

def test_no_real_rate_decision_has_ever_fallen_inside_a_weekend_blackout():
    """The evidence for 'weekend risk is unscheduled risk'.

    The page states this as a measurement. If a future calendar ever contradicts
    it, the copy is wrong and this must fail rather than let the page keep
    asserting it.
    """
    ev = load_events()
    if ev.empty:
        pytest.skip("run `python scripts/fetch_events.py` first")
    stats = historical_overlap(CLOCK, ev)
    assert stats["overlaps"] == 0, (
        f"{stats['overlaps']} scheduled events now land inside a weekend blackout - "
        "the page's claim that weekend risk is unscheduled needs revisiting"
    )


def test_real_events_land_midweek_while_the_cash_market_is_open():
    """Why the overlap is zero: decisions are released when a trader can act."""
    ev = load_events()
    if ev.empty:
        pytest.skip("run `python scripts/fetch_events.py` first")
    # ClosureClock labels any timestamp outside the calendar it was built over
    # as WEEKNIGHT rather than flagging it, so restrict to the span it covers
    # before judging. Events from 2021 are older than this clock's range.
    windows = CLOCK.blackouts()
    covered = ev[(ev["ts_utc"] >= windows["start"].min())
                 & (ev["ts_utc"] < windows["end"].max())]
    assert len(covered) >= 8, "too few in-range events for this to mean anything"

    regimes = CLOCK.annotate(pd.DatetimeIndex(covered["ts_utc"]))["regime"]
    assert (regimes == Regime.US_CASH.value).all(), \
        "a rate decision released outside the cash session would change the analysis"
