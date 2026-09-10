"""Fetch rToken history and judge whether it can back the Blackout Basis backtest.

This started as a throwaway probe and is now the ingestion step, because the
data it pulls is the data the backtest needs. Everything it fetches is cached
under data/, and a run resumes from that cache, so a rate-limit failure halfway
through never costs the pages already retrieved.

What the strategy needs, for at least one tokenized US stock:

  * intraday (<=1h) history spanning >=180 days (a 60-day sample holds only nine
    blackout windows -- see scripts/blackout_stats.py),
  * genuine weekend coverage,
  * enough pool depth to be tradeable at a stated size,
  * a joinable native equity series for the same underlying.

Weekend coverage is the make-or-break property. Saturdays and Sundays are 28.6%
of wall-clock time, so a true 7x24 series lands near that; a number near zero
means session-only data and the whole thesis is untestable on it.

GeckoTerminal's free tier allows roughly 30 calls a minute across every
endpoint, search included. Exceeding it returns 429, and sometimes 401 rather
than 429, which looks like an auth problem but is not. Every request therefore
goes through one global rate limiter with backoff.

    pip install pandas requests
    python scripts/probe_sources.py                # default: 3 deepest symbols
    python scripts/probe_sources.py --pages 10     # reach further back
    python scripts/probe_sources.py --refresh      # ignore the cache

Exit code 0 means at least one rToken source cleared the bar.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
RAW = ROOT / "data" / "raw"

GT = "https://api.geckoterminal.com/api/v2"
HEADERS = {"Accept": "application/json", "User-Agent": "blackout-basis-probe/1.0"}
TIMEOUT = 30

# 30 calls/min is the documented free-tier ceiling. 3.5s spacing leaves headroom
# for the burst the retry path can add.
MIN_INTERVAL_S = 3.5
MAX_RETRIES = 5
THROTTLE_CODES = {401, 429, 500, 502, 503, 504}

PAGE_LIMIT = 1000          # GeckoTerminal's hard cap; ~41 days of hourly bars
DEFAULT_PAGES = 6          # ~250 days
DEFAULT_DEEP_SYMBOLS = 3   # only page the deepest pools; discovery is cheap, paging is not

MIN_DAYS = 180
MIN_WEEKEND_SHARE = 0.15
MIN_LIQUIDITY_USD = 100_000

XSTOCK_SYMBOLS = ["AAPLx", "TSLAx", "NVDAx", "SPYx", "MSTRx", "COINx", "GOOGLx", "METAx"]

_last_call = 0.0


def api_get(path: str, params: dict | None = None) -> dict:
    """One global rate limiter and backoff for every GeckoTerminal call."""
    global _last_call
    for attempt in range(MAX_RETRIES):
        gap = MIN_INTERVAL_S - (time.monotonic() - _last_call)
        if gap > 0:
            time.sleep(gap)
        _last_call = time.monotonic()

        r = requests.get(f"{GT}{path}", params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code in THROTTLE_CODES and attempt < MAX_RETRIES - 1:
            hinted = float(r.headers.get("Retry-After") or 0)
            backoff = max(hinted, MIN_INTERVAL_S * (2 ** attempt))
            print(f"      throttled ({r.status_code}), waiting {backoff:.0f}s", flush=True)
            time.sleep(backoff)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("unreachable")


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
        return bool(self.bars) and not self.reasons and not self.error

    def judge(self) -> "Candidate":
        if self.error or not self.bars:
            return self
        if self.span_days < MIN_DAYS:
            tail = "" if self.hit_page_limit else " (pool may be younger than that)"
            self.reasons.append(f"history {self.span_days:.0f}d < {MIN_DAYS}d{tail}")
        if self.weekend_share < MIN_WEEKEND_SHARE:
            self.reasons.append(f"weekend share {self.weekend_share:.0%} — not 7x24")
        if self.liquidity < MIN_LIQUIDITY_USD:
            self.reasons.append(f"liquidity ${self.liquidity:,.0f} < ${MIN_LIQUIDITY_USD:,}")
        return self


def discover(refresh: bool) -> list[Candidate]:
    """Find the deepest Solana pool per symbol. Cached — discovery rarely changes."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / "pools.json"
    if cache_file.exists() and not refresh:
        print(f"  using cached pool discovery ({cache_file.relative_to(ROOT)})")
        return [Candidate(**row) for row in json.loads(cache_file.read_text())]

    out: list[Candidate] = []
    for sym in XSTOCK_SYMBOLS:
        c = Candidate(symbol=sym)
        try:
            print(f"  discovering {sym}...", flush=True)
            pools = api_get("/search/pools", {"query": sym, "network": "solana"}).get("data", [])
            if not pools:
                c.error = "no Solana pool found"
            else:
                best = max(pools, key=lambda p: float(p["attributes"].get("reserve_in_usd") or 0))
                a = best["attributes"]
                c.pool = best["id"].split("_", 1)[-1]
                c.liquidity = float(a.get("reserve_in_usd") or 0)
                c.volume_24h = float((a.get("volume_usd") or {}).get("h24") or 0)
        except Exception as e:  # noqa: BLE001
            c.error = f"{type(e).__name__}: {e}"
        out.append(c)

    cache_file.write_text(json.dumps(
        [{"symbol": c.symbol, "pool": c.pool, "liquidity": c.liquidity,
          "volume_24h": c.volume_24h, "error": c.error} for c in out], indent=1))
    return out


def fetch_ohlcv(c: Candidate, max_pages: int, refresh: bool) -> pd.DataFrame:
    """Page hourly bars backwards, writing after every page so progress survives.

    Resumes from whatever is already on disk: only pages older than the earliest
    cached bar are requested.
    """
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{c.symbol}_hour.csv"

    df = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    if path.exists() and not refresh:
        df = pd.read_csv(path)
        print(f"      resuming from {len(df)} cached bars", flush=True)

    for page in range(max_pages):
        span = _span_days(df)
        if span >= MIN_DAYS:
            break
        params = {"limit": PAGE_LIMIT}
        if len(df):
            params["before_timestamp"] = int(df["ts"].min())

        rows = api_get(f"/networks/solana/pools/{c.pool}/ohlcv/hour", params) \
            ["data"]["attributes"]["ohlcv_list"]
        if not rows:
            break

        page_df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
        before = len(df)
        df = pd.concat([df, page_df]).drop_duplicates("ts").sort_values("ts")
        df.to_csv(path, index=False)
        gained = len(df) - before
        print(f"      page {page + 1}: +{gained} bars, {_span_days(df):.0f}d total", flush=True)

        if gained == 0 or len(rows) < PAGE_LIMIT:
            break                      # history exhausted, or the API replayed a page
    else:
        c.hit_page_limit = True

    return df


def _span_days(df: pd.DataFrame) -> float:
    if len(df) < 2:
        return 0.0
    return (df["ts"].max() - df["ts"].min()) / 86400


def summarise(c: Candidate, df: pd.DataFrame) -> Candidate:
    if len(df):
        ts = pd.to_datetime(df["ts"], unit="s", utc=True)
        c.bars = len(df)
        c.span_days = _span_days(df)
        c.weekend_share = float((ts.dt.dayofweek >= 5).mean())
        c.earliest = ts.min()
    return c.judge()


def probe_native_equity() -> tuple[bool, str]:
    attempts = [
        ("Yahoo", "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
         {"range": "2y", "interval": "1d"}),
        ("Stooq", "https://stooq.com/q/d/l/", {"s": "aapl.us", "i": "d"}),
    ]
    last = "none tried"
    for name, url, params in attempts:
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            if "yahoo" in url:
                n = len(r.json()["chart"]["result"][0]["timestamp"])
                return True, f"{name}: {n} daily bars for AAPL"
            import io
            if "Date" in r.text[:200]:
                df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"])
                return True, f"{name}: {len(df)} daily bars to {df['Date'].max():%Y-%m-%d}"
        except Exception as e:  # noqa: BLE001
            last = f"{name} -> {type(e).__name__}"
    return False, f"all native equity sources failed (last: {last})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    ap.add_argument("--symbols", type=int, default=DEFAULT_DEEP_SYMBOLS,
                    help="how many of the deepest pools to page")
    ap.add_argument("--refresh", action="store_true", help="ignore cached data")
    args = ap.parse_args()

    print("Blackout Basis — rToken data ingestion")
    print(f"bar: >={MIN_DAYS}d hourly, >={MIN_WEEKEND_SHARE:.0%} weekend bars, "
          f">=${MIN_LIQUIDITY_USD:,} liquidity")
    print(f"rate limit: one call per {MIN_INTERVAL_S}s with backoff; cached under data/\n")

    print("Phase 1 — pool discovery")
    found = discover(args.refresh)
    live = sorted([c for c in found if c.pool], key=lambda c: -c.liquidity)
    for c in found:
        if not c.pool:
            print(f"  {c.symbol:<8} — {c.error}")
    print()
    print(f"{'symbol':<8}{'liquidity':>14}{'vol 24h':>14}")
    for c in live:
        print(f"{c.symbol:<8}${c.liquidity:>13,.0f}${c.volume_24h:>13,.0f}")

    deep = live[: args.symbols]
    print(f"\nPhase 2 — hourly history for the {len(deep)} deepest\n")
    for c in deep:
        print(f"  {c.symbol} ({c.pool[:12]}...)", flush=True)
        try:
            summarise(c, fetch_ohlcv(c, args.pages, args.refresh))
        except Exception as e:  # noqa: BLE001
            c.error = f"{type(e).__name__}: {e}"

    print(f"\n{'symbol':<8}{'bars':>7}{'span':>8}{'wknd':>7}  earliest")
    print("-" * 46)
    for c in deep:
        if c.error and not c.bars:
            print(f"{c.symbol:<8}{'—':>7}{'—':>8}{'—':>7}  {c.error}")
            continue
        cap = "+" if c.hit_page_limit else " "
        print(f"{c.symbol:<8}{c.bars:>7}{c.span_days:>7.0f}d{cap}{c.weekend_share:>6.0%}"
              f"  {c.earliest:%Y-%m-%d}")
    print("\n('+' means the page cap stopped us, so more history exists)")

    print("\nPer-symbol verdict:")
    for c in deep:
        print(f"  [{'PASS' if c.ok else 'FAIL'}] {c.symbol:<8} "
              f"{'' if c.ok else (c.error or '; '.join(c.reasons))}")

    native_ok, native_detail = probe_native_equity()
    print(f"\nNative equity leg: [{'PASS' if native_ok else 'FAIL'}] {native_detail}")

    passing = [c for c in deep if c.ok]
    seven_by_24 = [c for c in deep if c.bars and c.weekend_share >= MIN_WEEKEND_SHARE]

    print("\n" + "=" * 78)
    if passing:
        best = max(passing, key=lambda c: c.liquidity)
        print(f"VERDICT: GO. {best.symbol} — {best.span_days:.0f}d hourly, "
              f"{best.weekend_share:.0%} weekend bars, ${best.liquidity:,.0f} liquidity.")
    elif seven_by_24:
        best = max(seven_by_24, key=lambda c: c.liquidity)
        print(f"VERDICT: PARTIAL. 7x24 confirmed ({best.symbol}: {best.weekend_share:.0%} "
              f"weekend bars, {best.span_days:.0f}d) but not every bar was met.")
        print("Depth or history is the constraint, not weekend coverage. That is a scope")
        print("decision — shorten the window or accept lower capacity — not a stop.")
    else:
        print("VERDICT: NO-GO on this run. Check whether the failures above are throttling")
        print("(429/401) rather than missing data; if so, re-run — the cache resumes.")
        return 1

    print(f"\nData cached under {RAW.relative_to(ROOT)}/ — re-runs resume from it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
