"""Scheduled macro events, and where they sit relative to a closure window.

The desk's seventh question: what is scheduled between now and the moment you
can act again?

The answer is usually *nothing*, and that is the finding rather than a gap in
the data. Across every FOMC decision the Fed has published or scheduled, none
falls inside a weekend blackout -- decisions land midweek at 14:00 ET, when the
cash market is open and a trader can respond. So weekend blackout risk is
**unscheduled** risk by construction, which is exactly why it cannot be planned
around and why the distribution of past weekends is the only guide available.

What the calendar can still tell a trader is the shape of the window's far
edge. A position carried through a blackout does not stop being a position at
the reopen, and a Monday open followed by a Wednesday rate decision is a
different proposition from a quiet week. `events_after_reopen` covers that.

Populate with `python scripts/fetch_events.py`; every event traces to its
issuing authority.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .clock import ClosureClock, Regime

EVENTS_CSV = Path(__file__).resolve().parents[2] / "data" / "macro_events.csv"
SCHEMA = ("ts_utc", "label", "category", "importance")

#: How far past the reopen still counts as "carrying this position into".
LOOKAHEAD_AFTER_REOPEN_H = 72


def load_events() -> pd.DataFrame:
    """The event table, or an empty frame with the right columns if unpopulated."""
    if not EVENTS_CSV.exists():
        return pd.DataFrame(columns=list(SCHEMA))
    df = pd.read_csv(EVENTS_CSV)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df.sort_values("ts_utc").reset_index(drop=True)


def events_in_window(start: pd.Timestamp, end: pd.Timestamp,
                     events: pd.DataFrame | None = None) -> pd.DataFrame:
    ev = load_events() if events is None else events
    if ev.empty:
        return ev
    return ev[(ev["ts_utc"] >= start) & (ev["ts_utc"] < end)].reset_index(drop=True)


def next_blackout(clock: ClosureClock, as_of: pd.Timestamp) -> pd.Series | None:
    """The next closure window a position would be carried through."""
    windows = clock.blackouts()
    ahead = windows[windows["end"] > as_of]
    return None if ahead.empty else ahead.iloc[0]


def events_after_reopen(clock: ClosureClock, as_of: pd.Timestamp,
                        hours: int = LOOKAHEAD_AFTER_REOPEN_H,
                        events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Scheduled events in the days following the next reopen.

    The blackout itself is almost always empty; what a trader can actually plan
    around is what greets the position once trading resumes.
    """
    window = next_blackout(clock, as_of)
    if window is None:
        return load_events().iloc[0:0]
    reopen = window["end"]
    return events_in_window(reopen, reopen + pd.Timedelta(hours=hours), events)


def assess(clock: ClosureClock, as_of: pd.Timestamp,
           events: pd.DataFrame | None = None) -> dict:
    """What the calendar says about the window ahead, stated plainly.

    Reports the empty case as a finding rather than as missing data, because a
    blackout with nothing scheduled in it is the normal state and the reason the
    empirical distribution matters more than the calendar does.
    """
    ev = load_events() if events is None else events
    window = next_blackout(clock, as_of)
    if window is None:
        return {"has_window": False, "events_inside": 0, "events_after": 0}

    inside = events_in_window(window["start"], window["end"], ev)
    after = events_after_reopen(clock, as_of, events=ev)

    return {
        "has_window": True,
        "window_start": window["start"],
        "window_end": window["end"],
        "window_hours": float(window["hours"]),
        "regime": window["regime"],
        "events_inside": int(len(inside)),
        "events_after": int(len(after)),
        "next_event": (after.iloc[0]["label"] if len(after)
                       else (inside.iloc[0]["label"] if len(inside) else None)),
        "next_event_ts": (after.iloc[0]["ts_utc"] if len(after)
                          else (inside.iloc[0]["ts_utc"] if len(inside) else None)),
        "calendar_populated": bool(len(ev)),
    }


def historical_overlap(clock: ClosureClock, events: pd.DataFrame | None = None,
                       regime: str = Regime.WEEKEND_BLACKOUT.value) -> dict:
    """How often a scheduled event has ever landed inside a closure window.

    This is the evidence behind the claim that weekend risk is unscheduled, so
    the page can state it as a measurement rather than an assertion.
    """
    ev = load_events() if events is None else events
    windows = clock.blackouts()
    windows = windows[windows["regime"] == regime]
    if ev.empty or windows.empty:
        return {"windows": int(len(windows)), "events": int(len(ev)),
                "events_considered": 0, "overlaps": 0}

    # Only events the calendar actually spans can be said to have missed a
    # window. Counting a 2021 event against windows starting in 2024 would
    # inflate the denominator and quietly overstate the claim.
    covered = windows["start"].min(), windows["end"].max()
    ev = ev[(ev["ts_utc"] >= covered[0]) & (ev["ts_utc"] < covered[1])]
    if ev.empty:
        return {"windows": int(len(windows)), "events": 0,
                "events_considered": 0, "overlaps": 0}

    # Stay in pandas: a tz-aware column converted with to_numpy() becomes an
    # object array of Timestamps, which will not compare against datetime64.
    stamps = ev["ts_utc"]
    overlaps = sum(
        int(((stamps >= w["start"]) & (stamps < w["end"])).sum())
        for _, w in windows.iterrows()
    )
    return {"windows": int(len(windows)), "events": int(len(ev)),
            "events_considered": int(len(ev)), "overlaps": overlaps}
