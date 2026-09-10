"""Scheduled macro events falling inside a closure window.

The desk's seventh question. Deliberately a small curated table rather than a
live feed: at 210 days of history the event set is enumerable by hand, and a
hand-checked calendar is more trustworthy here than a scraped one. The schema is
what matters — swapping in a feed later changes the loader, not the tool.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

EVENTS_CSV = Path(__file__).resolve().parents[2] / "data" / "macro_events.csv"
SCHEMA = ("ts_utc", "label", "category", "importance")


def load_events() -> pd.DataFrame:
    if not EVENTS_CSV.exists():
        return pd.DataFrame(columns=list(SCHEMA))
    df = pd.read_csv(EVENTS_CSV, parse_dates=["ts_utc"])
    return df.sort_values("ts_utc").reset_index(drop=True)


def events_in_window(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    ev = load_events()
    if ev.empty:
        return ev
    ts = pd.to_datetime(ev["ts_utc"], utc=True)
    return ev[(ts >= start) & (ts < end)]
