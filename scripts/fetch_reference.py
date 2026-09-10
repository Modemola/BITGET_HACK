"""Fetch the reference leg: native equity and index futures, hourly.

Blackout Basis prices the rToken band against a fair value that has to be
reconstructed differently in each regime:

  US_CASH     the native stock trades, so fair value is observable directly.
  WEEKNIGHT   the stock is shut but index futures quote continuously, so fair
              value is the last native close carried forward by the futures
              return since that close. This is the regime that carries the
              statistical weight -- roughly 4,463 hours a year against 2,588 in
              blackouts -- so the futures series is not optional.
  BLACKOUT    nothing quotes. There is no reference, which is the whole point.

Yahoo serves hourly bars back about 730 days for both equities and the futures
continuations (NQ=F, ES=F), which covers the 211 days of rToken history we have.
Pre- and post-market bars are requested too, since they extend native coverage
to 04:00-20:00 ET and narrow the window we have to synthesise.

    python scripts/fetch_reference.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 30
PAUSE_S = 1.5

# Underlyings for the rToken symbols that passed, plus the index futures that
# quote through the weeknight window.
TARGETS = {
    "NVDA": "native equity — underlying for NVDAx",
    "TSLA": "native equity — underlying for TSLAx",
    "NQ=F": "Nasdaq-100 futures — weeknight reference",
    "ES=F": "S&P 500 futures — weeknight reference / risk proxy",
}


def fetch(symbol: str) -> pd.DataFrame:
    r = requests.get(
        CHART.format(symbol=symbol),
        params={"range": "2y", "interval": "1h", "includePrePost": "true"},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]

    quote = result["indicators"]["quote"][0]
    df = pd.DataFrame(
        {
            "ts": result["timestamp"],
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "volume": quote["volume"],
        }
    )
    # Yahoo emits null rows for halted or untraded bars; they are not zeros.
    return df.dropna(subset=["close"]).drop_duplicates("ts").sort_values("ts")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    print("Fetching reference leg (native equity + index futures), hourly\n")
    print(f"{'symbol':<8}{'bars':>8}{'span':>8}{'wknd':>7}  range")
    print("-" * 62)

    failures = []
    for symbol, note in TARGETS.items():
        try:
            df = fetch(symbol)
            out = RAW / f"{symbol.replace('=', '_')}_hour.csv"
            df.to_csv(out, index=False)

            ts = pd.to_datetime(df["ts"], unit="s", utc=True)
            span = (ts.max() - ts.min()).days
            weekend = float((ts.dt.dayofweek >= 5).mean())
            print(f"{symbol:<8}{len(df):>8}{span:>7}d{weekend:>6.0%}  "
                  f"{ts.min():%Y-%m-%d} to {ts.max():%Y-%m-%d}")
        except Exception as e:  # noqa: BLE001
            failures.append(symbol)
            print(f"{symbol:<8}{'—':>8}{'—':>8}{'—':>7}  {type(e).__name__}: {e}")
        time.sleep(PAUSE_S)

    print("\nExpected weekend share: ~0% for equities (session-only, correctly),")
    print("and low-but-nonzero for futures, whose Sunday 18:00 ET session opens the week.")

    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        print("Without a futures series the weeknight regime cannot be priced, which")
        print("removes the strategy's largest sample. Say so rather than working around it.")
        return 1

    print(f"\nAll reference series cached under {RAW.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
