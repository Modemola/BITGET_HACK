"""What a trader can actually trade while the equity market is shut.

The desk's sixth question, and the answer is uncomfortably short. During a
weekend blackout the equity, futures and options markets are all closed. What
remains is:

  * the rToken itself, on a thin on-chain book,
  * another rToken (a cross-hedge, e.g. an index token against a single name),
  * crypto perpetuals, the only deep instrument still quoting.

Crypto is a *proxy*, so whether it hedges anything is an empirical question
rather than an assumption. Measured over 27 weekend blackouts, BTC carries a
+0.71 correlation with NVDAx and removes roughly 29% of the variance -- which
sounds like a hedge until you look at the rolling window, where the same
correlation ranges from -0.51 to +0.89 and changes sign.

So every function here reports stability alongside the point estimate. A hedge
justified by an average correlation that flips sign is not a hedge, and a desk
that shows the average without the range is misleading its user.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .clock import ClosureClock, Regime

# Round-trip execution cost, as a fraction of notional. Bitget perpetual taker
# fees plus a funding allowance across a ~49h weekend; rToken legs pay a DEX
# swap fee and a spread that its thin book makes material.
COSTS = {
    "BTC-USD": 0.0015,   # 0.06% taker x2, plus ~3 funding periods
    "ETH-USD": 0.0015,
    "rtoken": 0.0060,    # DEX AMM swap plus slippage on a shallow pool
}

MIN_WINDOWS = 12         # below this, decline to quote a correlation at all
UNSTABLE_IF_SIGN_FLIPS = True


@dataclass(frozen=True)
class HedgeQuote:
    instrument: str
    correlation: float
    hedge_ratio: float
    risk_reduction: float
    residual_vol: float
    unhedged_vol: float
    cost_pct: float
    corr_min: float
    corr_max: float
    sign_flips: int
    n_windows: int

    @property
    def is_stable(self) -> bool:
        return self.sign_flips == 0 and self.corr_min > 0.2

    @property
    def verdict(self) -> str:
        if self.n_windows < MIN_WINDOWS:
            return "insufficient history to quote"
        if not self.is_stable:
            return (f"unstable - rolling correlation spans {self.corr_min:+.2f} to "
                    f"{self.corr_max:+.2f}; has been risk-adding")
        if self.risk_reduction < 0.15:
            return "too weak to be worth the cost"
        return f"removes {self.risk_reduction:.0%} of variance"


def window_returns(df: pd.DataFrame, clock: ClosureClock, columns: list[str],
                   regime: str = Regime.WEEKEND_BLACKOUT.value,
                   min_bars: int = 20) -> pd.DataFrame:
    """Return of each column across each closure window, one row per window."""
    windows = clock.blackouts()
    windows = windows[
        (windows["regime"] == regime)
        & (windows["start"] >= df.index.min())
        & (windows["end"] <= df.index.max())
    ]
    rows = []
    for _, w in windows.iterrows():
        seg = df[(df.index >= w["start"]) & (df.index < w["end"])].dropna(subset=columns)
        if len(seg) < min_bars:
            continue
        row = {"window_start": w["start"]}
        for c in columns:
            row[c] = seg[c].iloc[-1] / seg[c].iloc[0] - 1
        rows.append(row)
    return pd.DataFrame(rows)


def quote_hedge(returns: pd.DataFrame, exposure_col: str, hedge_col: str,
                roll: int = 8) -> HedgeQuote:
    """Measure a candidate hedge, with its stability, not just its average."""
    sub = returns[[exposure_col, hedge_col]].dropna()
    n = len(sub)
    if n < 3:
        return HedgeQuote(hedge_col, np.nan, np.nan, np.nan, np.nan, np.nan,
                          COSTS.get(hedge_col, COSTS["rtoken"]), np.nan, np.nan, 0, n)

    corr = float(sub[exposure_col].corr(sub[hedge_col]))
    ratio = float(np.polyfit(sub[hedge_col], sub[exposure_col], 1)[0])
    unhedged = float(sub[exposure_col].std())
    residual = float((sub[exposure_col] - ratio * sub[hedge_col]).std())

    rolling = sub[exposure_col].rolling(roll).corr(sub[hedge_col]).dropna()
    flips = int((np.sign(rolling).diff() != 0).sum() - 1) if len(rolling) > 1 else 0

    return HedgeQuote(
        instrument=hedge_col,
        correlation=corr,
        hedge_ratio=ratio,
        risk_reduction=1 - residual / unhedged if unhedged else np.nan,
        residual_vol=residual,
        unhedged_vol=unhedged,
        cost_pct=COSTS.get(hedge_col, COSTS["rtoken"]),
        corr_min=float(rolling.min()) if len(rolling) else np.nan,
        corr_max=float(rolling.max()) if len(rolling) else np.nan,
        sign_flips=max(flips, 0),
        n_windows=n,
    )


def hedge_menu(returns: pd.DataFrame, exposure_col: str,
               candidates: list[str], exposure_usd: float = 0.0) -> pd.DataFrame:
    """Every instrument live during a blackout, ranked, with its honest verdict."""
    quotes = [quote_hedge(returns, exposure_col, c) for c in candidates
              if c != exposure_col and c in returns.columns]
    rows = []
    for q in quotes:
        rows.append({
            "instrument": q.instrument,
            "correlation": q.correlation,
            "hedge_ratio": q.hedge_ratio,
            "notional_usd": exposure_usd * abs(q.hedge_ratio),
            "risk_reduction": q.risk_reduction,
            "cost_pct": q.cost_pct,
            "cost_usd": exposure_usd * abs(q.hedge_ratio) * q.cost_pct,
            "stable": q.is_stable,
            "verdict": q.verdict,
        })
    out = pd.DataFrame(rows)
    return out.sort_values("risk_reduction", ascending=False).reset_index(drop=True) \
        if not out.empty else out
