import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

from blackout import ClosureClock, Regime

ET = "America/New_York"
CLOCK = ClosureClock(start="2025-01-01", end="2026-12-31")


def et(s):
    return pd.Timestamp(s, tz=ET)


def regime_at(s):
    return CLOCK.annotate(pd.DatetimeIndex([et(s)]))["regime"].iloc[0]


def test_cash_session_is_us_cash():
    assert regime_at("2026-09-11 12:00") == Regime.US_CASH.value


def test_weeknight_has_futures_but_no_cash():
    row = CLOCK.annotate(pd.DatetimeIndex([et("2026-09-09 22:00")])).iloc[0]
    assert row["regime"] == Regime.WEEKNIGHT.value
    assert row["tau_futures_h"] == 0.0   # Globex quoting
    assert row["tau_cash_h"] > 0.0       # but no creation/redemption


def test_saturday_is_a_full_blackout():
    row = CLOCK.annotate(pd.DatetimeIndex([et("2026-09-12 12:00")])).iloc[0]
    assert row["regime"] == Regime.WEEKEND_BLACKOUT.value
    # Globex reopens Sunday 18:00 ET; NYSE reopens Monday 09:30 ET.
    assert row["tau_futures_h"] == pytest.approx(30.0)
    assert row["tau_cash_h"] == pytest.approx(45.5)


def test_normal_weekend_blackout_is_49_hours():
    """Friday 17:00 ET Globex close to Sunday 18:00 ET reopen."""
    b = CLOCK.blackouts()
    weekends = b[b["regime"] == Regime.WEEKEND_BLACKOUT.value]
    assert weekends["hours"].mode().iloc[0] == 49.0


def test_daily_maintenance_halt_is_not_a_blackout():
    """The one-hour Globex halt carries no information risk and must not count."""
    assert CLOCK.blackouts()["hours"].min() >= CLOCK.min_blackout_hours


def test_blackout_means_futures_shut_but_not_the_reverse():
    """Every blackout has the futures shut; the converse holds only for real gaps.

    The daily Globex maintenance halt also has the futures shut, but it lasts an
    hour and carries no information risk, so it stays classified as WEEKNIGHT.
    """
    idx = pd.date_range("2026-09-07", "2026-09-21", freq="15min", tz="UTC")
    ann = CLOCK.annotate(idx)
    is_blackout = ann["regime"].isin([Regime.WEEKEND_BLACKOUT.value, Regime.HOLIDAY_BLACKOUT.value])

    assert (ann.loc[is_blackout, "tau_futures_h"] > 0).all()

    shut_but_not_blackout = ann.loc[~is_blackout & (ann["tau_futures_h"] > 0), "tau_futures_h"]
    assert not shut_but_not_blackout.empty, "expected to observe the daily maintenance halt"
    assert (shut_but_not_blackout <= 1.0).all(), "only the 1h halt may be shut outside a blackout"


def test_tau_decreases_monotonically_through_a_blackout():
    idx = pd.date_range(et("2026-09-11 18:00"), et("2026-09-13 17:00"), freq="1h")
    tau = CLOCK.annotate(idx)["tau_futures_h"]
    assert tau.is_monotonic_decreasing and tau.iloc[-1] > 0


def test_holiday_weekends_run_longer_than_normal_ones():
    b = CLOCK.blackouts()
    weekends = b[b["regime"] == Regime.WEEKEND_BLACKOUT.value]
    assert weekends["hours"].max() > 49.0
