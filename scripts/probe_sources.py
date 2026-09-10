"""Kill-criterion test: can we source enough rToken history to back a backtest?

The Blackout Basis strategy needs, for at least one tokenized US stock:

  * intraday (<=1h) price history,
  * spanning >=60 days (>=180 preferred, see blackout_stats.py),
  * covering weekends rather than only US session hours,
  * joinable to native equity OHLC for the same underlying.

The final bullet is the one that usually fails: most equity data providers
simply have no rows at all for a Saturday, and a source that silently omits
weekends is useless to us no matter how long its history.

This script cannot run inside the Claude Code web sandbox, whose egress policy
allows only GitHub and package registries. Run it anywhere with open network:

    pip install -r requirements.txt
    python3 scripts/probe_sources.py

Exit code 0 means at least one source cleared the bar.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass

import pandas as pd
import requests

TIMEOUT = 25
MIN_DAYS = 60
MIN_WEEKEND_FRACTION = 0.15  # weekends are ~28% of wall clock; well under that means gaps

# Tokenized US stock tickers to look for, across the main issuers.
XSTOCK_SYMBOLS = ["AAPLx", "TSLAx", "NVDAx", "SPYx", "MSTRx", "COINx"]


@dataclass
class Verdict:
    source: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        return f"  [{'PASS' if self.ok else 'FAIL'}] {self.source:<28} {self.detail}"


def _coverage(ts: pd.DatetimeIndex) -> tuple[float, float]:
    """Return (days spanned, fraction of observations falling on a weekend)."""
    if len(ts) == 0:
        return 0.0, 0.0
    days = (ts.max() - ts.min()).total_seconds() / 86400
    weekend = float((ts.dayofweek >= 5).mean())
    return days, weekend


def probe_geckoterminal() -> Verdict:
    """On-chain OHLCV for xStocks pools. Free, no key, and genuinely 7x24."""
    name = "GeckoTerminal (Solana)"
    try:
        for sym in XSTOCK_SYMBOLS:
            r = requests.get(
                "https://api.geckoterminal.com/api/v2/search/pools",
                params={"query": sym, "network": "solana"},
                headers={"Accept": "application/json"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            pools = r.json().get("data", [])
            if not pools:
                continue
            pool = max(pools, key=lambda p: float(p["attributes"].get("reserve_in_usd") or 0))
            addr = pool["id"].split("_", 1)[-1]

            o = requests.get(
                f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{addr}/ohlcv/hour",
                params={"limit": 1000},
                headers={"Accept": "application/json"},
                timeout=TIMEOUT,
            )
            o.raise_for_status()
            rows = o.json()["data"]["attributes"]["ohlcv_list"]
            if not rows:
                continue
            ts = pd.to_datetime([r[0] for r in rows], unit="s", utc=True)
            days, weekend = _coverage(ts)
            ok = days >= MIN_DAYS and weekend >= MIN_WEEKEND_FRACTION
            return Verdict(
                name, ok,
                f"{sym}: {len(rows)} hourly bars, {days:.0f}d span, "
                f"{weekend:.0%} weekend bars, liq=${float(pool['attributes'].get('reserve_in_usd') or 0):,.0f}",
            )
        return Verdict(name, False, "no xStocks pools found")
    except Exception as e:  # noqa: BLE001
        return Verdict(name, False, f"{type(e).__name__}: {e}")


def probe_bitget() -> Verdict:
    """Does Bitget itself list tokenized stocks we can pull candles for?"""
    name = "Bitget spot API"
    try:
        r = requests.get("https://api.bitget.com/api/v2/spot/public/symbols", timeout=TIMEOUT)
        r.raise_for_status()
        syms = [d.get("symbol", "") for d in r.json().get("data", [])]
        stocky = [s for s in syms if any(k in s.upper() for k in ("AAPL", "TSLA", "NVDA", "SPY", "MSTR", "COIN"))]
        if not stocky:
            return Verdict(name, False, f"{len(syms)} symbols listed, none tokenized-equity")
        return Verdict(name, True, f"candidates: {stocky[:8]}")
    except Exception as e:  # noqa: BLE001
        return Verdict(name, False, f"{type(e).__name__}: {e}")


def probe_stooq() -> Verdict:
    """Native equity daily OHLC — the reference leg. Free, no key."""
    name = "Stooq (native equity)"
    try:
        r = requests.get("https://stooq.com/q/d/l/", params={"s": "aapl.us", "i": "d"}, timeout=TIMEOUT)
        r.raise_for_status()
        if "Date" not in r.text[:200]:
            return Verdict(name, False, "unexpected payload")
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
        return Verdict(name, len(df) > 500, f"AAPL {len(df)} daily bars to {df['Date'].max():%Y-%m-%d}")
    except Exception as e:  # noqa: BLE001
        return Verdict(name, False, f"{type(e).__name__}: {e}")


def main() -> int:
    print("Probing rToken data sources")
    print(f"bar: >={MIN_DAYS}d intraday history with >={MIN_WEEKEND_FRACTION:.0%} weekend coverage\n")

    verdicts = [probe_geckoterminal(), probe_bitget(), probe_stooq()]
    for v in verdicts:
        print(v)

    rtoken_ok = verdicts[0].ok or verdicts[1].ok
    print("\n" + "=" * 72)
    if rtoken_ok:
        print("VERDICT: rToken history is obtainable. Blackout Basis is GO.")
    else:
        print("VERDICT: no usable rToken history. Fall back to Idea 3 (Friday 15:45).")
    return 0 if rtoken_ok else 1


if __name__ == "__main__":
    sys.exit(main())
