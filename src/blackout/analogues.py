"""Retrieve past closure windows that resemble the one ahead.

The desk's fourth question, and the centre of the Decision Stress Testing idea:
rather than asserting a forecast, show the trader what happened the last k times
conditions looked like this, and let them read the spread themselves.

Two constraints shape everything here.

**Every feature must be knowable at decision time.** A trader stands at Friday
15:45 with the window still ahead of them. Realised volatility over the days
behind them qualifies; anything measured during or after the window does not.
Features and outcomes are therefore built separately and never mixed, so a
lookahead cannot creep into the retrieval and flatter the result.

**Retrieval has to be legible.** With 27 windows, a black-box nearest neighbour
is worthless -- a trader must see *why* a weekend was pulled up or it is not
evidence, just a number. So similarity runs over four interpretable features and
the per-feature gap is reported alongside the distance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .clock import ClosureClock, Regime

#: Features are z-scored before distance, so a percentage-point premium and a
#: 40-vol sit on the same scale. Weights express what a trader actually cares
#: about matching: how stressed the tape was, and how stretched the token was.
FEATURE_WEIGHTS = {
    "realised_vol_5d": 1.0,
    "premium_at_close": 1.0,
    "window_hours": 0.5,
    "crypto_vol_5d": 0.5,
}
FEATURES = tuple(FEATURE_WEIGHTS)

OUTCOMES = ("terminal_drift", "max_abs_drift", "token_return")

LOOKBACK_H = 120          # five days of hourly bars before the window opens
HOURS_PER_YEAR = 24 * 365


def _annualised_vol(series: pd.Series) -> float:
    """Annualised realised volatility from hourly closes."""
    r = np.log(series.astype(float)).diff().dropna()
    if len(r) < 12:
        return float("nan")
    return float(r.std() * np.sqrt(HOURS_PER_YEAR))


def build_feature_table(df: pd.DataFrame, clock: ClosureClock, token: str = "x",
                        crypto: str | None = None,
                        regime: str = Regime.WEEKEND_BLACKOUT.value,
                        min_bars: int = 20) -> pd.DataFrame:
    """One row per historical window: features known beforehand, plus outcomes.

    Args:
        df: hourly frame carrying `prem` and the token price column.
        clock: calendar used to enumerate windows.
        token: column holding the rToken price.
        crypto: optional column for a crypto proxy, used for the risk-appetite
            feature. Omitted rather than faked when absent.
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

        # Strictly before the window opens -- this is the causality boundary.
        prior = df[(df.index < w["start"]) & (df.index >= w["start"] - pd.Timedelta(hours=LOOKBACK_H))]

        base = inside["prem"].iloc[0]
        drift = inside["prem"] - base
        px = inside[token].dropna()

        row = {
            "window_start": w["start"],
            "window_hours": float(w["hours"]),
            "realised_vol_5d": _annualised_vol(prior[token].dropna()) if token in prior else np.nan,
            "premium_at_close": float(base),
            "crypto_vol_5d": (_annualised_vol(prior[crypto].dropna())
                              if crypto and crypto in prior else np.nan),
            "terminal_drift": float(drift.iloc[-1]),
            "max_abs_drift": float(drift.abs().max()),
            "token_return": float(px.iloc[-1] / px.iloc[0] - 1) if len(px) > 1 else np.nan,
            "bars": int(len(inside)),
        }
        rows.append(row)

    table = pd.DataFrame(rows)
    if table.empty:
        return table
    # Drop features that are entirely absent rather than imputing them; a
    # fabricated feature would silently distort every distance.
    return table.dropna(axis=1, how="all").reset_index(drop=True)


def _usable_features(features: pd.DataFrame) -> list[str]:
    return [f for f in FEATURES if f in features.columns and features[f].notna().any()]


def find_analogues(features: pd.DataFrame, query: dict, k: int = 5) -> pd.DataFrame:
    """The k most similar past windows, with distance and per-feature gaps.

    Distance is a weighted Euclidean over z-scored features, computed only on the
    features the query actually supplies. Asking about volatility alone therefore
    matches on volatility alone, rather than quietly assuming a median for
    everything unspecified.

    Returns the matched windows with their outcomes, a `distance` column, and one
    `gap_<feature>` column per feature so the retrieval can be explained.
    """
    if features.empty:
        return features

    usable = [f for f in _usable_features(features) if f in query and query[f] is not None]
    if not usable:
        raise ValueError(
            f"query supplies none of the usable features {_usable_features(features)}"
        )

    stats = {f: (features[f].mean(), features[f].std(ddof=0)) for f in usable}
    dist_sq = np.zeros(len(features))
    out = features.copy()

    for f in usable:
        mu, sd = stats[f]
        sd = sd if sd and np.isfinite(sd) and sd > 0 else 1.0
        z_hist = (features[f] - mu) / sd
        z_query = (query[f] - mu) / sd
        delta = (z_hist - z_query).fillna(0.0)
        dist_sq += FEATURE_WEIGHTS[f] * delta.to_numpy() ** 2
        out[f"gap_{f}"] = features[f] - query[f]

    out["distance"] = np.sqrt(dist_sq)
    out["matched_on"] = ", ".join(usable)
    return out.nsmallest(min(k, len(out)), "distance").reset_index(drop=True)


def summarise_analogues(matches: pd.DataFrame) -> dict:
    """What the retrieved set says, phrased as a distribution rather than a call.

    Deliberately reports the spread and the worst case before any central
    tendency: with a handful of matches, the range is the honest signal and the
    mean is the misleading one.
    """
    if matches.empty:
        return {"n": 0}

    terminal = matches["terminal_drift"]
    return {
        "n": int(len(matches)),
        "worst_drift": float(terminal.abs().max()),
        "range_low": float(terminal.min()),
        "range_high": float(terminal.max()),
        "median_drift": float(terminal.median()),
        "median_abs_drift": float(terminal.abs().median()),
        "share_beyond_1pct": float((terminal.abs() > 0.01).mean()),
        "max_excursion": float(matches["max_abs_drift"].max()),
        "closest_distance": float(matches["distance"].min()),
    }
