"""Reconstruct rToken fair value and the premium to it, regime by regime.

Fair value cannot be observed directly outside the cash session, so it is
carried forward from the last native close by the beta-scaled index-futures
move since that close:

    fair(t) = native_close(anchor) * (1 + beta * (NQ(t)/NQ(anchor) - 1))

During a blackout the futures are shut too, so NQ forward-fills flat and fair
value freezes. That frozen anchor is not a modelling shortcut -- it is the
actual information state of the market, and the divergence that opens against
it is what the strategy set out to trade.

The premium must always be decomposed before it is believed. A premium can
close because the token moved back (tradeable) or because fair value caught up
when the reference reopened (not tradeable -- nothing to capture on the token
leg). See decompose_closure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .clock import ClosureClock, Regime


def hourly_frame(series: dict[str, pd.Series], clock: ClosureClock) -> pd.DataFrame:
    """Align every series onto one hourly UTC grid and label the regime."""
    start = min(s.index.min() for s in series.values())
    end = max(s.index.max() for s in series.values())
    grid = pd.date_range(start, end, freq="h", tz="UTC")
    df = pd.DataFrame({k: s.reindex(grid) for k, s in series.items()}, index=grid)
    ann = clock.annotate(grid)
    df[["regime", "tau_futures_h", "tau_cash_h"]] = ann.values
    return df


def estimate_beta(df: pd.DataFrame, native: str, index: str = "nq") -> float:
    """Beta of the underlying to the index, fitted only where both actually trade."""
    cash = df[df["regime"] == Regime.US_CASH.value].dropna(subset=[native, index])
    rn, ri = np.log(cash[native]).diff(), np.log(cash[index]).diff()
    ok = rn.notna() & ri.notna()
    if ok.sum() < 50:
        raise ValueError(f"only {ok.sum()} paired cash-hour returns; too few for a beta")
    return float(np.polyfit(ri[ok], rn[ok], 1)[0])


def add_premium(df: pd.DataFrame, token: str, native: str, index: str = "nq",
                beta: float | None = None) -> pd.DataFrame:
    b = estimate_beta(df, native, index) if beta is None else beta
    idx_ff = df[index].ffill()
    anchor_px = df[native].ffill()
    anchor_idx = idx_ff.where(df[native].notna()).ffill()
    df = df.copy()
    df["fair"] = anchor_px * (1 + b * (idx_ff / anchor_idx - 1))
    df["prem"] = df[token] / df["fair"] - 1
    df.attrs["beta"] = b
    return df


def decompose_closure(df: pd.DataFrame, entries: pd.DatetimeIndex, token: str,
                      horizon_h: int) -> dict[str, float]:
    """Split premium closure into the token leg and the fair-value leg.

    Only the token-leg share is capturable by trading the token. A high
    fair-value share means the reference was stale and the token was right --
    an efficient forecast, not a mispricing.
    """
    later = entries + pd.Timedelta(hours=horizon_h)
    sign = np.sign(df.loc[entries, "prem"].values)

    d_token = df[token].reindex(later).values / df.loc[entries, token].values - 1
    d_fair = df["fair"].reindex(later).values / df.loc[entries, "fair"].values - 1
    keep = ~(np.isnan(d_token) | np.isnan(d_fair))

    from_token = float((-sign[keep] * d_token[keep]).mean())
    from_fair = float((sign[keep] * d_fair[keep]).mean())
    total = from_token + from_fair
    return {
        "n": int(keep.sum()),
        "from_token": from_token,
        "from_fair": from_fair,
        "token_share": from_token / total if total else float("nan"),
        "token_leg_pnl": float((-sign[keep] * d_token[keep]).mean()),
    }


def premium_persistence(df: pd.DataFrame) -> pd.DataFrame:
    """AR(1) of the premium by regime, with the implied half-life in hours."""
    out = []
    for regime in [r.value for r in Regime]:
        p = df.loc[df["regime"] == regime, "prem"].dropna()
        if len(p) < 100:
            continue
        ac = p.autocorr(1)
        half = np.log(0.5) / np.log(abs(ac)) if 0 < abs(ac) < 1 else np.nan
        out.append({"regime": regime, "n": len(p), "ar1": ac, "half_life_h": half})
    return pd.DataFrame(out)
