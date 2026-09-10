"""Translate a book into closure-window exposure.

The desk's second question. A position is not simply "long $250k of NVDAx" — it
is $250k that will spend N hours quoted only by a thin on-chain venue, M hours
against a futures reference, and the rest in a normal cash session. Splitting
the holding period that way is what makes the risk legible.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .clock import ClosureClock, Regime


@dataclass(frozen=True)
class Position:
    symbol: str
    usd: float


def horizon_breakdown(clock: ClosureClock, as_of: pd.Timestamp,
                      horizon_h: int = 72) -> pd.DataFrame:
    """Hours spent in each regime over the next `horizon_h`, from `as_of`."""
    grid = pd.date_range(as_of, periods=horizon_h, freq="h", tz="UTC")
    ann = clock.annotate(grid)
    counts = ann["regime"].value_counts().reindex([r.value for r in Regime]).fillna(0)
    return pd.DataFrame({
        "regime": counts.index,
        "hours": counts.values,
        "share": counts.values / max(len(grid), 1),
    })


def unhedgeable_exposure(positions: list[Position], clock: ClosureClock,
                         as_of: pd.Timestamp, horizon_h: int = 72) -> dict:
    """Book value that will sit inside a blackout, where no reference price exists."""
    breakdown = horizon_breakdown(clock, as_of, horizon_h)
    blackout_hours = float(
        breakdown.loc[breakdown["regime"].isin(
            [Regime.WEEKEND_BLACKOUT.value, Regime.HOLIDAY_BLACKOUT.value]), "hours"].sum()
    )
    gross = sum(p.usd for p in positions)
    return {
        "gross_usd": gross,
        "blackout_hours": blackout_hours,
        "share_of_horizon": blackout_hours / max(horizon_h, 1),
        "breakdown": breakdown.to_dict("records"),
    }
