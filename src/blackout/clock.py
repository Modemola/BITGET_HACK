"""Closure-window clock.

The premise of this strategy is that US equity exposure is quoted on three
different clocks, and that the gaps between them are what create the rToken
arbitrage band:

    US_CASH           NYSE regular session. rToken, native equity and index
                      futures all trade. Authorised participants can hedge and
                      create/redeem, so the band is at its tightest.

    WEEKNIGHT         NYSE shut, CME Globex open. No creation/redemption, but a
                      continuously-quoted reference price still exists, so the
                      band is wider but anchored.

    WEEKEND_BLACKOUT  NYSE shut and Globex shut. rToken is the only venue on
                      earth quoting the underlying. No reference price, no
                      hedge, no arbitrageur.

    HOLIDAY_BLACKOUT  As above, created by an exchange holiday rather than a
                      weekend. Rarer and usually longer.

A blackout is defined as "index futures are closed" rather than "the cash
market is closed", because the futures session is what determines whether a
reference price exists at all.

Everything here is computed from exchange calendars alone. It needs no market
data, which is why it is the first thing built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import exchange_calendars as xc
import numpy as np
import pandas as pd

ET = "America/New_York"
NS_PER_HOUR = 3_600_000_000_000

CASH_CALENDAR = "XNYS"
FUTURES_CALENDAR = "CMES"


class Regime(str, Enum):
    US_CASH = "US_CASH"
    WEEKNIGHT = "WEEKNIGHT"
    WEEKEND_BLACKOUT = "WEEKEND_BLACKOUT"
    HOLIDAY_BLACKOUT = "HOLIDAY_BLACKOUT"

    @property
    def is_blackout(self) -> bool:
        return self in (Regime.WEEKEND_BLACKOUT, Regime.HOLIDAY_BLACKOUT)


def _to_utc_index(ts) -> pd.DatetimeIndex:
    """Normalise to a UTC, nanosecond-resolution index.

    Forcing the unit matters: pandas 2 infers microsecond resolution from a
    string like "2026-09-11 12:00", and `.asi8` then returns microseconds. Mixed
    against nanosecond calendar arrays that silently yields timestamps in 1970.
    """
    idx = pd.DatetimeIndex(pd.Series(ts).values) if not isinstance(ts, pd.DatetimeIndex) else ts
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.as_unit("ns")


@dataclass
class ClosureClock:
    """Classifies any timestamp into a closure regime and measures time-to-reopen.

    Args:
        start / end: calendar range to precompute, as ISO dates.
        futures_close_offset_minutes: exchange_calendars models the CMES session
            as running 18:00 ET to 18:00 ET with no gap, but Globex actually
            halts for maintenance from 17:00 ET and reopens at 18:00 ET. Pulling
            each session close back by 60 minutes reproduces both the daily halt
            and the true Friday 17:00 ET close, which is what sets the length of
            the weekend blackout.
        min_blackout_hours: gaps shorter than this (i.e. the daily maintenance
            halt) are treated as WEEKNIGHT rather than a blackout. A one-hour
            halt carries no information risk; a weekend does.
    """

    start: str = "2023-01-01"
    end: str = "2027-12-31"
    futures_close_offset_minutes: int = 60
    min_blackout_hours: float = 6.0

    _cash: tuple[np.ndarray, np.ndarray] = field(init=False, repr=False)
    _fut: tuple[np.ndarray, np.ndarray] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._cash = self._intervals(CASH_CALENDAR, 0)
        self._fut = self._intervals(FUTURES_CALENDAR, self.futures_close_offset_minutes)

    def _intervals(self, code: str, close_offset_min: int) -> tuple[np.ndarray, np.ndarray]:
        cal = xc.get_calendar(code, start=self.start, end=self.end)
        opens = cal.opens.dropna().sort_values()
        closes = cal.closes.dropna().sort_values()
        o = _to_utc_index(pd.DatetimeIndex(opens.values)).asi8
        c = _to_utc_index(pd.DatetimeIndex(closes.values)).asi8
        c = c - int(close_offset_min) * 60 * 1_000_000_000
        keep = c > o
        return o[keep], c[keep]

    @staticmethod
    def _inside(intervals: tuple[np.ndarray, np.ndarray], t: np.ndarray) -> np.ndarray:
        opens, closes = intervals
        i = np.searchsorted(closes, t, side="right")
        ok = i < len(opens)
        out = np.zeros(len(t), dtype=bool)
        out[ok] = opens[i[ok]] <= t[ok]
        return out

    @staticmethod
    def _hours_to_next_open(intervals: tuple[np.ndarray, np.ndarray], t: np.ndarray) -> np.ndarray:
        opens, _ = intervals
        j = np.searchsorted(opens, t, side="right")
        out = np.full(len(t), np.nan)
        ok = j < len(opens)
        out[ok] = (opens[j[ok]] - t[ok]) / NS_PER_HOUR
        return out

    def annotate(self, ts) -> pd.DataFrame:
        """Label a timestamp index with regime and hours-to-reopen.

        tau_cash is the horizon over which an authorised participant cannot
        create or redeem; tau_futures is the horizon over which no reference
        price exists at all. Both are zero while the respective venue is open.
        """
        idx = _to_utc_index(ts)
        t = idx.asi8

        in_cash = self._inside(self._cash, t)
        in_fut = self._inside(self._fut, t)

        tau_cash = np.where(in_cash, 0.0, self._hours_to_next_open(self._cash, t))
        tau_fut = np.where(in_fut, 0.0, self._hours_to_next_open(self._fut, t))

        regime = np.where(in_cash, Regime.US_CASH.value, Regime.WEEKNIGHT.value).astype(object)

        blackout = self.blackouts()
        starts = _to_utc_index(pd.DatetimeIndex(blackout["start"])).asi8
        ends = _to_utc_index(pd.DatetimeIndex(blackout["end"])).asi8
        k = np.searchsorted(ends, t, side="right")
        hit = (k < len(starts))
        hit[hit] &= starts[k[hit]] <= t[hit]
        labels = blackout["regime"].values
        regime[hit] = labels[k[hit]]

        return pd.DataFrame(
            {
                "regime": pd.Categorical(regime, categories=[r.value for r in Regime]),
                "tau_cash_h": tau_cash,
                "tau_futures_h": tau_fut,
            },
            index=idx,
        )

    def blackouts(self) -> pd.DataFrame:
        """Every window in which index futures are closed for long enough to matter."""
        if getattr(self, "_blackout_cache", None) is not None:
            return self._blackout_cache

        opens, closes = self._fut
        gap_start, gap_end = closes[:-1], opens[1:]
        hours = (gap_end - gap_start) / NS_PER_HOUR
        keep = hours >= self.min_blackout_hours
        gap_start, gap_end, hours = gap_start[keep], gap_end[keep], hours[keep]

        start = pd.DatetimeIndex(gap_start.astype("datetime64[ns]")).tz_localize("UTC")
        end = pd.DatetimeIndex(gap_end.astype("datetime64[ns]")).tz_localize("UTC")

        regime = [
            Regime.WEEKEND_BLACKOUT.value if self._covers_saturday(s, e) else Regime.HOLIDAY_BLACKOUT.value
            for s, e in zip(start, end)
        ]

        df = pd.DataFrame(
            {"start": start, "end": end, "hours": hours, "regime": regime}
        ).sort_values("start").reset_index(drop=True)
        self._blackout_cache = df
        return df

    @staticmethod
    def _covers_saturday(start: pd.Timestamp, end: pd.Timestamp) -> bool:
        span = pd.date_range(start.tz_convert(ET).floor("h"), end.tz_convert(ET).ceil("h"), freq="h")
        return bool((span.dayofweek == 5).any())

    _blackout_cache = None
