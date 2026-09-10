"""Structural facts about the closure window, computed from exchange calendars.

These need no market data, so they stand up regardless of what rToken history we
can source. They answer the design question that decides the backtest: does a
60-day sample contain enough blackout windows to say anything?

Usage: python3 scripts/blackout_stats.py [start] [end]
"""

from __future__ import annotations

import sys
import pathlib

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from blackout import ClosureClock, Regime  # noqa: E402

ET = "America/New_York"


def main(start: str = "2025-01-01", end: str = "2026-09-10") -> None:
    clock = ClosureClock(start="2024-06-01", end="2027-06-30")

    grid = pd.date_range(start, end, freq="5min", tz="UTC", inclusive="left")
    ann = clock.annotate(grid)
    share = ann["regime"].value_counts(normalize=True).reindex([r.value for r in Regime]).fillna(0)

    print(f"=== Where the clock actually sits, {start} to {end} ===")
    print(f"{'regime':<20}{'% of wall clock':>16}{'hours/yr':>12}")
    for regime, pct in share.items():
        print(f"{regime:<20}{pct:>15.1%}{pct * 8760:>12.0f}")
    blackout_share = share[Regime.WEEKEND_BLACKOUT.value] + share[Regime.HOLIDAY_BLACKOUT.value]
    print(f"\nrToken is the only quoted venue {blackout_share:.1%} of all wall-clock time.")
    print(f"The native cash market is open just {share[Regime.US_CASH.value]:.1%} of it.")

    b = clock.blackouts()
    b = b[(b["start"] >= pd.Timestamp(start, tz="UTC")) & (b["end"] <= pd.Timestamp(end, tz="UTC"))]

    print(f"\n=== Blackout windows in the sample ===")
    print(f"{'type':<20}{'count':>8}{'mean h':>10}{'total h':>10}")
    for regime, g in b.groupby("regime", observed=True):
        print(f"{regime:<20}{len(g):>8}{g['hours'].mean():>10.1f}{g['hours'].sum():>10.0f}")

    # The sample-size question for a >=60-day backtest with >=30-day out-of-sample.
    print(f"\n=== Sample size available to the backtest ===")
    for window in (60, 90, 180):
        cut = pd.Timestamp(end, tz="UTC") - pd.Timedelta(days=window)
        w = b[b["start"] >= cut]
        weekends = (w["regime"] == Regime.WEEKEND_BLACKOUT.value).sum()
        print(f"  trailing {window:>3}d: {len(w):>3} blackouts ({weekends} weekend) "
              f"= {w['hours'].sum():>5.0f} blackout hours")

    print(f"\n=== Longest blackouts (the fat-tail trades) ===")
    top = b.nlargest(6, "hours")
    for _, r in top.iterrows():
        s = r["start"].tz_convert(ET)
        print(f"  {s:%a %d %b %Y %H:%M} ET  {r['hours']:>5.0f}h  {r['regime']}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
