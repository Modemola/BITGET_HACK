"""Tests for the closure-window analytics that back the desk's claims.

Every figure the product shows a trader comes through these functions, so the
invariants here are about not misleading: drift measured from the right base,
sample sizes reported honestly, and no silent fabrication when data is absent.
"""

import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from blackout import ClosureClock, Regime
from blackout.distributions import (
    drift_by_elapsed_hour, summarise, terminal_gap, window_paths,
)
from blackout.exposure import Position, horizon_breakdown, unhedgeable_exposure

CLOCK = ClosureClock(start="2026-01-01", end="2026-12-31")


def synthetic_frame(premium_path=None):
    """Hourly frame across two known weekends, with a controllable premium."""
    grid = pd.date_range("2026-09-07", "2026-09-21", freq="h", tz="UTC")
    ann = CLOCK.annotate(grid)
    df = pd.DataFrame(index=grid)
    df[["regime", "tau_futures_h", "tau_cash_h"]] = ann.values
    df["prem"] = 0.0 if premium_path is None else premium_path(grid)
    return df


def test_drift_is_measured_from_the_window_start_not_from_zero():
    """A token already rich at the close has not drifted; only new movement counts."""
    df = synthetic_frame(lambda idx: np.full(len(idx), 0.02))   # constant 2% rich
    paths = window_paths(df, CLOCK)
    assert not paths.empty
    assert paths["drift"].abs().max() == pytest.approx(0.0, abs=1e-12)


def test_drift_tracks_movement_within_the_window():
    df = synthetic_frame(lambda idx: np.linspace(0, 0.05, len(idx)))
    paths = window_paths(df, CLOCK)
    ordered = paths.sort_values(["window_start", "elapsed_h"])
    first = ordered.groupby("window_start")["drift"].first().abs()
    last = ordered.groupby("window_start")["drift"].last().abs()
    assert (first < last).all()


def test_sample_size_is_reported_per_window_not_per_bar():
    """n counts hourly bars and is not independent; n_windows is the honest figure."""
    df = synthetic_frame(lambda idx: np.random.default_rng(0).normal(0, 0.01, len(idx)))
    table = drift_by_elapsed_hour(window_paths(df, CLOCK))
    assert {"n", "n_windows"} <= set(table.columns)
    assert (table["n_windows"] <= table["n"]).all()
    assert table["n_windows"].max() <= 2, "only two weekends exist in this range"


def test_short_windows_are_skipped_rather_than_silently_included():
    df = synthetic_frame()
    assert window_paths(df, CLOCK, min_bars=10_000).empty


def test_summarise_reports_nothing_rather_than_fabricating():
    empty = window_paths(synthetic_frame(), CLOCK, min_bars=10_000)
    assert summarise(empty) == {"n_windows": 0}
    assert terminal_gap(empty).empty
    assert drift_by_elapsed_hour(empty).empty


def test_friday_afternoon_faces_a_49_hour_blackout():
    """The exposure headline: most of the next 72 hours is unhedgeable."""
    as_of = pd.Timestamp("2026-09-11 15:45", tz="America/New_York").tz_convert("UTC")
    e = unhedgeable_exposure([Position("NVDAx", 250_000)], CLOCK, as_of, horizon_h=72)
    assert e["blackout_hours"] == pytest.approx(49.0)
    assert e["share_of_horizon"] > 0.6
    assert e["gross_usd"] == 250_000


def test_horizon_breakdown_accounts_for_every_hour():
    as_of = pd.Timestamp("2026-09-11 15:45", tz="America/New_York").tz_convert("UTC")
    b = horizon_breakdown(CLOCK, as_of, 72)
    assert b["hours"].sum() == 72
    assert b["share"].sum() == pytest.approx(1.0)


def test_midweek_horizon_has_no_blackout():
    as_of = pd.Timestamp("2026-09-08 10:00", tz="America/New_York").tz_convert("UTC")
    b = horizon_breakdown(CLOCK, as_of, 24)
    blackout = b[b["regime"].isin([Regime.WEEKEND_BLACKOUT.value, Regime.HOLIDAY_BLACKOUT.value])]
    assert blackout["hours"].sum() == 0


# --- hedges -----------------------------------------------------------------

from blackout.hedges import HedgeQuote, hedge_menu, quote_hedge, window_returns  # noqa: E402


def _returns(n=30, seed=0, corr=0.9):
    """Two return series with a controllable relationship."""
    rng = np.random.default_rng(seed)
    hedge = rng.normal(0, 0.02, n)
    noise = rng.normal(0, 0.02 * np.sqrt(max(1 - corr**2, 0)), n)
    return pd.DataFrame({
        "window_start": pd.date_range("2026-01-03", periods=n, freq="7D", tz="UTC"),
        "TOKEN": corr * hedge + noise,
        "HEDGE": hedge,
    })


def test_a_strong_stable_hedge_is_reported_as_usable():
    q = quote_hedge(_returns(corr=0.95), "TOKEN", "HEDGE")
    assert q.correlation > 0.8
    assert q.risk_reduction > 0.3
    assert q.is_stable
    assert "removes" in q.verdict


def test_a_sign_flipping_correlation_is_never_called_a_hedge():
    """The measured BTC case: high average correlation, unstable underneath."""
    rng = np.random.default_rng(3)
    n = 30
    hedge = rng.normal(0, 0.02, n)
    token = hedge.copy()
    token[: n // 2] *= -1              # correlation inverts across the sample
    r = pd.DataFrame({"TOKEN": token, "HEDGE": hedge})
    q = quote_hedge(r, "TOKEN", "HEDGE")
    assert not q.is_stable
    assert "unstable" in q.verdict


def test_declines_to_quote_on_thin_history():
    q = quote_hedge(_returns(n=4), "TOKEN", "HEDGE")
    assert q.n_windows < 12
    assert q.verdict == "insufficient history to quote"


def test_menu_prices_the_hedge_in_dollars_not_just_ratios():
    r = _returns(corr=0.9)
    menu = hedge_menu(r, "TOKEN", ["HEDGE"], exposure_usd=250_000)
    row = menu.iloc[0]
    assert row["notional_usd"] == pytest.approx(250_000 * abs(row["hedge_ratio"]))
    assert row["cost_usd"] > 0
    assert row["cost_usd"] == pytest.approx(row["notional_usd"] * row["cost_pct"])


def test_menu_never_offers_the_exposure_as_its_own_hedge():
    menu = hedge_menu(_returns(), "TOKEN", ["TOKEN", "HEDGE"], exposure_usd=1000)
    assert "TOKEN" not in set(menu["instrument"])


def test_window_returns_skips_windows_with_thin_coverage():
    clock = ClosureClock(start="2026-01-01", end="2026-12-31")
    grid = pd.date_range("2026-09-07", "2026-09-21", freq="h", tz="UTC")
    df = pd.DataFrame({"A": np.linspace(100, 110, len(grid))}, index=grid)
    assert window_returns(df, clock, ["A"], min_bars=10_000).empty
    assert not window_returns(df, clock, ["A"], min_bars=5).empty
