"""Tests for analogue retrieval.

The load-bearing test here is causality. A retrieval that peeks inside the window
it is supposed to be forecasting will look excellent in a backtest and be worse
than useless to a trader standing at Friday 15:45. `test_features_cannot_see_inside_the_window`
is the one that would catch that, so it corrupts the data a feature must not be
able to read and asserts the features do not move.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from blackout import ClosureClock
from blackout.analogues import (
    FEATURES, build_feature_table, find_analogues, summarise_analogues,
)

CLOCK = ClosureClock(start="2025-06-01", end="2027-01-01")


def frame(seed: int = 0, weeks: int = 12) -> pd.DataFrame:
    """Hourly frame spanning several weekends, with a plausible premium path."""
    rng = np.random.default_rng(seed)
    grid = pd.date_range("2026-03-02", periods=24 * 7 * weeks, freq="h", tz="UTC")
    ann = CLOCK.annotate(grid)
    df = pd.DataFrame(index=grid)
    df[["regime", "tau_futures_h", "tau_cash_h"]] = ann.values
    df["x"] = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, len(grid))))
    df["btc"] = 50000 * np.exp(np.cumsum(rng.normal(0, 0.006, len(grid))))
    df["prem"] = rng.normal(0, 0.005, len(grid))
    return df


def test_features_cannot_see_inside_the_window():
    """A window's features must not move when only its own future is corrupted.

    Corrupting from one window's start onward isolates the causality claim.
    Corrupting *every* window instead would prove nothing: the five-day lookback
    from a Friday legitimately reaches back into the previous weekend's blackout,
    and reading that is causal -- a trader standing at Friday 15:45 already knows
    what last weekend did.
    """
    df = frame()
    before = build_feature_table(df, CLOCK, token="x", crypto="btc")
    assert len(before) >= 4

    target = before.iloc[-2]
    cut = target["window_start"]

    corrupted = df.copy()
    mask = corrupted.index >= cut          # the window itself and everything after
    n = int(mask.sum())
    # A ramp, not a constant. Drift is measured as prem minus its own first
    # value and the token return as a ratio, so a flat offset or a uniform
    # rescale cancels out of both and would corrupt nothing observable --
    # leaving the causality assertions below true but vacuous.
    corrupted.loc[mask, "prem"] += np.linspace(0.02, 0.05, n)
    corrupted.loc[mask, "x"] *= np.linspace(1.0, 3.0, n)
    corrupted.loc[mask, "btc"] *= np.linspace(1.0, 0.4, n)

    after = build_feature_table(corrupted, CLOCK, token="x", crypto="btc")
    row_after = after.loc[after["window_start"] == cut].iloc[0]

    # Everything drawn strictly from before the window opens must be untouched.
    for f in (f for f in FEATURES if f in before.columns and f != "premium_at_close"):
        assert row_after[f] == pytest.approx(target[f], rel=1e-12), f"{f} saw the future"

    # premium_at_close is read at the window's first bar, which the corruption
    # touched, so it is expected to move -- and its moving proves the corruption
    # actually landed, without which the assertions above would be vacuous.
    assert row_after["premium_at_close"] != pytest.approx(target["premium_at_close"])
    assert row_after["terminal_drift"] != pytest.approx(target["terminal_drift"])


def test_earlier_windows_are_unaffected_by_later_corruption():
    """Causality's mirror image: nothing before the cut may move either."""
    df = frame()
    before = build_feature_table(df, CLOCK, token="x", crypto="btc")
    cut = before.iloc[-2]["window_start"]

    corrupted = df.copy()
    mask = corrupted.index >= cut
    n = int(mask.sum())
    corrupted.loc[mask, "prem"] += np.linspace(0.02, 0.05, n)
    corrupted.loc[mask, "x"] *= np.linspace(1.0, 3.0, n)
    after = build_feature_table(corrupted, CLOCK, token="x", crypto="btc")

    earlier = before["window_start"] < cut
    cols = [c for c in before.columns if c != "window_start"]
    pd.testing.assert_frame_equal(
        before.loc[earlier, cols].reset_index(drop=True),
        after.loc[after["window_start"] < cut, cols].reset_index(drop=True),
    )


def test_outcomes_are_never_offered_as_features():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    with pytest.raises(ValueError, match="none of the usable features"):
        find_analogues(table, {"terminal_drift": 0.01})


def test_a_missing_proxy_is_dropped_rather_than_imputed():
    """No crypto column means no crypto feature -- never a fabricated one."""
    df = frame().drop(columns=["btc"])
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    assert "crypto_vol_5d" not in table.columns


def test_partial_query_matches_only_on_what_was_supplied():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    matches = find_analogues(table, {"realised_vol_5d": 0.5}, k=3)
    assert matches["matched_on"].iloc[0] == "realised_vol_5d"
    assert "gap_premium_at_close" not in matches.columns


def test_exact_self_match_has_zero_distance_and_ranks_first():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    target = table.iloc[3]
    query = {f: target[f] for f in FEATURES if f in table.columns}
    matches = find_analogues(table, query, k=3)
    assert matches["distance"].iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert matches["window_start"].iloc[0] == target["window_start"]


def test_gaps_explain_why_a_window_was_retrieved():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    matches = find_analogues(table, {"realised_vol_5d": 0.5, "premium_at_close": 0.0}, k=4)
    for _, row in matches.iterrows():
        assert row["gap_realised_vol_5d"] == pytest.approx(
            row["realised_vol_5d"] - 0.5, abs=1e-12)


def test_k_larger_than_the_sample_returns_the_sample():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    matches = find_analogues(table, {"realised_vol_5d": 0.5}, k=999)
    assert len(matches) == len(table)


def test_summary_leads_with_spread_not_a_point_estimate():
    df = frame()
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    s = summarise_analogues(find_analogues(table, {"realised_vol_5d": 0.5}, k=5))
    assert {"range_low", "range_high", "worst_drift", "max_excursion"} <= set(s)
    assert s["range_low"] <= s["median_drift"] <= s["range_high"]
    assert s["n"] == 5


def test_summary_of_nothing_reports_nothing():
    assert summarise_analogues(pd.DataFrame()) == {"n": 0}


def test_empty_history_returns_empty_rather_than_raising():
    df = frame(weeks=1).head(5)
    table = build_feature_table(df, CLOCK, token="x", crypto="btc")
    assert table.empty
    assert find_analogues(table, {"realised_vol_5d": 0.5}).empty
