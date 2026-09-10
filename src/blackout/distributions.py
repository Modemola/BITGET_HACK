"""Empirical drift through a closure window.

Answers the desk's third question: given that a blackout is H hours old, how far
has the token typically travelled from where it started?

This is the measurement the whole product rests on, so it is deliberately blunt:
no model, no fitted curve, just the observed distribution with its sample size
attached. 27 weekends is thin, and every consumer of these numbers is expected
to show the `n` beside them.

Drift is measured relative to the premium at the *start* of the window, not to
zero. A token already trading 20bp rich when NYSE closes has not drifted; what
we care about is what the closure itself opened up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .clock import ClosureClock, Regime

QUANTILES = (0.05, 0.25, 0.50, 0.75, 0.95)


def window_paths(df: pd.DataFrame, clock: ClosureClock,
                 regime: str = Regime.WEEKEND_BLACKOUT.value,
                 min_bars: int = 20) -> pd.DataFrame:
    """One row per (window, elapsed hour) with the drift accumulated so far.

    Args:
        df: hourly frame carrying a `prem` column (see basis.add_premium).
        clock: the calendar used to enumerate closure windows.
        regime: which blackout type to walk.
        min_bars: skip windows with less coverage than this.

    Returns:
        Columns: window_start, elapsed_h, tau_futures_h, prem, drift.
    """
    windows = clock.blackouts()
    windows = windows[
        (windows["regime"] == regime)
        & (windows["start"] >= df.index.min())
        & (windows["end"] <= df.index.max())
    ]

    rows = []
    for _, w in windows.iterrows():
        inside = df[(df.index >= w["start"]) & (df.index < w["end"])].dropna(subset=["prem"])
        if len(inside) < min_bars:
            continue
        base = inside["prem"].iloc[0]
        elapsed = (inside.index - w["start"]).total_seconds() / 3600
        rows.append(pd.DataFrame({
            "window_start": w["start"],
            "elapsed_h": elapsed,
            "tau_futures_h": inside["tau_futures_h"].values,
            "prem": inside["prem"].values,
            "drift": inside["prem"].values - base,
        }))

    if not rows:
        return pd.DataFrame(columns=["window_start", "elapsed_h", "tau_futures_h", "prem", "drift"])
    return pd.concat(rows, ignore_index=True)


def drift_by_elapsed_hour(paths: pd.DataFrame, bucket_h: int = 6) -> pd.DataFrame:
    """Distribution of accumulated drift, bucketed by how old the blackout is.

    The `n_windows` column is the honest sample size. `n` counts hourly
    observations and will look reassuringly large; it is not independent, since
    the same weekend contributes many rows. Report `n_windows`.
    """
    if paths.empty:
        return pd.DataFrame()

    p = paths.copy()
    p["bucket"] = (p["elapsed_h"] // bucket_h).astype(int) * bucket_h

    out = p.groupby("bucket").agg(
        n=("drift", "size"),
        n_windows=("window_start", "nunique"),
        mean_abs=("drift", lambda s: s.abs().mean()),
        std=("drift", "std"),
    )
    for q in QUANTILES:
        out[f"q{int(q * 100):02d}"] = p.groupby("bucket")["drift"].quantile(q)
    return out.reset_index().rename(columns={"bucket": "elapsed_h_from"})


def terminal_gap(paths: pd.DataFrame) -> pd.DataFrame:
    """Where each window ended up — the number a trader is actually exposed to."""
    if paths.empty:
        return pd.DataFrame()
    last = paths.sort_values("elapsed_h").groupby("window_start").tail(1)
    return last[["window_start", "elapsed_h", "prem", "drift"]].reset_index(drop=True)


def summarise(paths: pd.DataFrame) -> dict:
    """Headline figures for the page, with sample size carried alongside."""
    if paths.empty:
        return {"n_windows": 0}
    term = terminal_gap(paths)
    return {
        "n_windows": int(paths["window_start"].nunique()),
        "median_window_hours": float(paths.groupby("window_start")["elapsed_h"].max().median()),
        "mean_abs_terminal_drift": float(term["drift"].abs().mean()),
        "p95_abs_terminal_drift": float(term["drift"].abs().quantile(0.95)),
        "worst_terminal_drift": float(term["drift"].abs().max()),
        "share_exceeding_1pct": float((term["drift"].abs() > 0.01).mean()),
    }
