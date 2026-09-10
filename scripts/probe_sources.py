"""Kill-criterion test: can we source enough rToken history to back a backtest?

The Blackout Basis strategy needs, for at least one tokenized US stock:

  * intraday (<=1h) price history,
  * spanning >=180 days (see blackout_stats.py -- a 60-day sample holds only
    nine blackout windows, which is too thin to claim anything),
  * covering weekends rather than only US session hours,
  * with enough pool liquidity to be tradeable at a stated size,
  * joinable to native equity OHLC for the same underlying.

The weekend requirement is the one that usually fails. Most equity data
providers have no rows at all for a Saturday, and a source that silently omits
weekends is useless to us no matter how long its history. Saturdays and Sundays
are 28.6% of wall-clock time, so a genuinely 7x24 series should show a weekend
share close to that; a number near zero means session-only data.

Run anywhere with open network:

    pip install pandas requests
    python scripts/probe_sources.py

Exit code 0 means at least one rToken source cleared the bar.
"""

from __future__ import annotations

import io
import sys
import time
from dataclasses import dataclass, field

import pandas as pd
import requests

TIMEOUT = 30
GT = "https://api.geckoterminal.com/api/v2"
HEADERS = {"Accept": "application/json"}

MIN_DAYS = 180
MIN_WEEKEND_SHARE = 0.15   # well under the 28.6% ideal, but far above session-only data
MIN_LIQUIDITY_USD = 100_000

# GeckoTerminal caps a page at 1000 bars, so hourly history must be paged
# backwards with before_timestamp. Six pages is roughly 250 days.
PAGE_LIMIT = 1000
MAX_PAGES = 8
PAGE_PAUSE_S = 2.5         # free tier allows ~30 calls/min

XSTOCK_SYMBOLS = ["AAPLx", "TSLAx", "NVDAx", "SPYx", "MSTRx", "COINx", "GOOGLx", "METAx"]


@dataclass
class Candidate:
    symbol: str
    pool: str = ""
    liquidity: float = 0.0
    volume_24h: float = 0.0
    bars: int = 0
    span_days: float = 0.0
    weekend_share: float = 0.0
    earliest: pd.Timestamp | None = None
    hit_page_limit: bool = False
    error: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.reasons and not self.error

    def judge(self) -> "Candidate":
        if self.error:
            return self
        if self.span_days < MIN_DAYS:
            note = " (pool may simply be younger than that)" if not self.hit_page_limit else ""
            self.reasons.append(f"history {self.span_days:.0f}d < {MIN_DAYS}d{note}")
        if self.weekend_share < MIN_WEEKEND_SHARE:
            self.reasons.append(f"weekend share {self.weekend_share:.0%} — not 7x24")
        if self.liquidity < MIN_LIQUIDITY_USD:
            self.reasons.append(f"liquidity ${self.liquidity:,.0f} < ${MIN_LIQUIDITY_USD:,}")
        return self


def _best_pool(symbol: str) -> tuple[str, float, float] | None:
    """Deepest Solana pool quoting this symbol, by USD reserves."""
    r = requests.get(f"{GT}/search/pools", params={"query": symbol, "network": "solana"},
                     headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    pools = r.json().get("data", [])
    if not pools:
        return None
    best = max(pools, key=lambda p: float(p["attributes"].get("reserve_in_usd") or 0))
    a = best["attributes"]
    return (
        best["id"].split("_", 1)[-1],
        float(a.get("reserve_in_usd") or 0),
        float((a.get("volume_usd") or {}).get("h24") or 0),
    )


def _paged_ohlcv(pool: str) -> tuple[pd.DatetimeIndex, bool]:
    """Page hourly OHLCV backwards until history runs out or MAX_PAGES is hit.

    Returns the timestamps and whether we stopped because of the page cap rather
    than because the pool ran out of history — the distinction that made the
    first version of this probe report a false negative.
    """
    stamps: list[int] = []
    before: int | None = None

    for page in range(MAX_PAGES):
        params = {"limit": PAGE_LIMIT}
        if before is not None:
            params["before_timestamp"] = before
        r = requests.get(f"{GT}/networks/solana/pools/{pool}/ohlcv/hour",
                         params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json()["data"]["attributes"]["ohlcv_list"]
        if not rows:
            return pd.to_datetime(sorted(set(stamps)), unit="s", utc=True), False

        ts = [int(row[0]) for row in rows]
        fresh = set(ts) - set(stamps)
        if not fresh:
            return pd.to_datetime(sorted(set(stamps)), unit="s", utc=True), False

        stamps.extend(ts)
        before = min(ts)

        if len(rows) < PAGE_LIMIT:      # exhausted this pool's history
            return pd.to_datetime(sorted(set(stamps)), unit="s", utc=True), False
        if page < MAX_PAGES - 1:
            time.sleep(PAGE_PAUSE_S)

    return pd.to_datetime(sorted(set(stamps)), unit="s", utc=True), True


def probe_xstock(symbol: str) -> Candidate:
    c = Candidate(symbol=symbol)
    try:
        found = _best_pool(symbol)
        if found is None:
            c.error = "no Solana pool found"
            return c
        c.pool, c.liquidity, c.volume_24h = found

        ts, capped = _paged_ohlcv(c.pool)
        if len(ts) == 0:
            c.error = "pool found but no OHLCV returned"
            return c

        c.bars = len(ts)
        c.span_days = (ts.max() - ts.min()).total_seconds() / 86400
        c.weekend_share = float((ts.dayofweek >= 5).mean())
        c.earliest = ts.min()
        c.hit_page_limit = capped
    except Exception as e:  # noqa: BLE001
        c.error = f"{type(e).__name__}: {e}"
    return c.judge()


def probe_native_equity() -> tuple[bool, str]:
    """The reference leg. Daily native OHLC is easy to source; try a few hosts."""
    attempts = [
        ("Stooq", "https://stooq.com/q/d/l/", {"s": "aapl.us", "i": "d"}),
        ("Stooq (pl)", "https://stooq.pl/q/d/l/", {"s": "aapl.us", "i": "d"}),
        ("Yahoo", "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
         {"range": "1y", "interval": "1d"}),
    ]
    for name, url, params in attempts:
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            if "yahoo" in url:
                n = len(r.json()["chart"]["result"][0]["timestamp"])
                return True, f"{name}: {n} daily bars for AAPL"
            if "Date" in r.text[:200]:
                df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
                return True, f"{name}: {len(df)} daily bars to {df['Date'].max():%Y-%m-%d}"
        except Exception as e:  # noqa: BLE001
            last = f"{name} -> {type(e).__name__}"
            continue
    return False, f"all native equity sources failed (last: {last})"


def main() -> int:
    print("Probing rToken data sources")
    print(f"bar: >={MIN_DAYS}d hourly history, >={MIN_WEEKEND_SHARE:.0%} weekend bars, "
          f">=${MIN_LIQUIDITY_USD:,} liquidity")
    print("(weekends are 28.6% of wall clock, so a true 7x24 series lands near that)\n")

    results = [probe_xstock(s) for s in XSTOCK_SYMBOLS]

    print(f"{'symbol':<8}{'liquidity':>13}{'vol 24h':>13}{'bars':>7}{'span':>8}{'wknd':>7}  earliest")
    print("-" * 78)
    for c in sorted(results, key=lambda x: -x.liquidity):
        if c.error and not c.pool:
            print(f"{c.symbol:<8}{'—':>13}{'—':>13}{'—':>7}{'—':>8}{'—':>7}  {c.error}")
            continue
        cap = "+" if c.hit_page_limit else " "
        earliest = f"{c.earliest:%Y-%m-%d}" if c.earliest is not None else "—"
        print(f"{c.symbol:<8}${c.liquidity:>12,.0f}${c.volume_24h:>12,.0f}"
              f"{c.bars:>7}{c.span_days:>7.0f}d{cap}{c.weekend_share:>6.0%}  {earliest}")
    print("\n('+' after span means we hit the page cap, so real history is longer)")

    print("\nPer-symbol verdict:")
    for c in sorted(results, key=lambda x: -x.liquidity):
        if c.ok:
            print(f"  [PASS] {c.symbol}")
        else:
            why = c.error or "; ".join(c.reasons)
            print(f"  [FAIL] {c.symbol:<8} {why}")

    native_ok, native_detail = probe_native_equity()
    print(f"\nNative equity leg: [{'PASS' if native_ok else 'FAIL'}] {native_detail}")

    passing = [c for c in results if c.ok]
    seven_by_24 = [c for c in results if c.weekend_share >= MIN_WEEKEND_SHARE and c.bars]

    print("\n" + "=" * 78)
    if passing:
        best = max(passing, key=lambda c: c.liquidity)
        print(f"VERDICT: GO. Best candidate {best.symbol} — {best.span_days:.0f}d of hourly "
              f"history, {best.weekend_share:.0%} weekend bars, ${best.liquidity:,.0f} liquidity.")
        return 0
    if seven_by_24:
        best = max(seven_by_24, key=lambda c: c.liquidity)
        print("VERDICT: PARTIAL. The 7x24 property holds — "
              f"{best.symbol} shows {best.weekend_share:.0%} weekend bars — but no symbol met "
              "every bar. Depth or history is the constraint, not weekend coverage.")
        print("This is a scope decision, not a stop: shorten the backtest window or accept")
        print("lower capacity. Do not fall back to Idea 3 on this result alone.")
        return 0
    print("VERDICT: NO-GO. No 7x24 rToken history found. Fall back to Idea 3 (Friday 15:45).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
