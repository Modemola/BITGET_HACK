"""What a trader can actually trade while the equity market is shut.

The desk's sixth question, and the answer is uncomfortably short. During a
weekend blackout the equity, futures and options markets are all closed. What
remains is:

  * the rToken itself, on a thin on-chain book,
  * another rToken (a cross-hedge, e.g. an index token against a single name),
  * crypto perpetuals, as a risk-on/off proxy.

The third is the only deep instrument, and it is a *proxy* — its usefulness is
an empirical question about weekend correlation, not an assumption. Pricing that
correlation honestly, including how unstable it is, is the point of this module.

Blocked on BTC/ETH hourly data: run scripts/fetch_reference.py.
"""

from __future__ import annotations

import pandas as pd


def weekend_correlation(rtoken: pd.Series, proxy: pd.Series) -> dict:
    """Correlation of blackout-window returns between an rToken and a proxy.

    Must report the rolling stability, not just the full-sample number: a hedge
    justified by an average correlation that swings between +0.6 and -0.2 is not
    a hedge.
    """
    raise NotImplementedError("Phase 1 — blocked on scripts/fetch_reference.py")


def hedge_menu(exposure_usd: float, symbol: str) -> pd.DataFrame:
    """Available instruments, hedge ratio, round-trip cost and residual risk."""
    raise NotImplementedError("Phase 1 — blocked on scripts/fetch_reference.py")
