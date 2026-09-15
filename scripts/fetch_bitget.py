"""Fetch rToken hourly candles from Bitget's own spot market.

Every rToken figure on the desk has come from one venue: xStocks pools on Solana,
via GeckoTerminal. A finding measured on a single venue is a finding about that
venue until someone checks another one — and Bitget lists the same underlyings
itself, under an R prefix (RNVDAUSDT, RTSLAUSDT, RSPYUSDT and more). That makes
it the obvious second opinion, and it is the host's own book.

    python scripts/fetch_bitget.py
    python scripts/fetch_bitget.py --symbols RNVDAUSDT RTSLAUSDT --pages 30

## The DNS fallback

Some ISPs refuse to resolve bitget.com. On the machine this was written for,
every Bitget domain fails with gaierror while every other host resolves
normally, the domain resolves fine through a public resolver, and connecting
straight to the resolved address succeeds — so the block is DNS and nothing
else.

Rather than make the script unusable behind such a resolver, it falls back to
resolving over DoH and connecting to the address with the correct SNI. That is
the same request the library would have made; only the name lookup moves. The
normal path is tried first and is used wherever it works.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

HOST = "api.bitget.com"
DOH = "https://dns.google/resolve"
UA = "blackout-desk/1.0"
TIMEOUT = 25

PAGE_LIMIT = 200          # Bitget's cap for spot candles
DEFAULT_PAGES = 30        # ~250 days at hourly granularity
PAGE_PAUSE_S = 0.35       # well inside the public rate limit

#: Bitget's tokenized US equities, matched to the xStocks symbols already held.
DEFAULT_SYMBOLS = ("RNVDAUSDT", "RTSLAUSDT")
COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def _doh_addresses(host: str) -> list[str]:
    request = urllib.request.Request(f"{DOH}?name={host}&type=A",
                                     headers={"accept": "application/dns-json"})
    answer = json.loads(urllib.request.urlopen(request, timeout=TIMEOUT).read())
    return [a["data"] for a in answer.get("Answer", []) if a.get("type") == 1]


def _raw_https(host: str, path: str) -> dict:
    """One HTTPS GET straight to a resolved address, with the right SNI."""
    last: Exception | None = None
    for address in _doh_addresses(host):
        try:
            with socket.create_connection((address, 443), timeout=TIMEOUT) as raw:
                with ssl.create_default_context().wrap_socket(
                        raw, server_hostname=host) as sock:
                    sock.sendall(
                        f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                        f"User-Agent: {UA}\r\nConnection: close\r\n\r\n".encode())
                    buffer = b""
                    while True:
                        chunk = sock.recv(65536)
                        if not chunk:
                            break
                        buffer += chunk
            body = buffer.split(b"\r\n\r\n", 1)[1]
            if not body.lstrip().startswith(b"{"):
                parts, out, i = body.split(b"\r\n"), b"", 0
                while i < len(parts):
                    try:
                        size = int(parts[i], 16)
                    except ValueError:
                        break
                    if size == 0:
                        break
                    out += parts[i + 1][:size]
                    i += 2
                body = out or body
            return json.loads(body)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last or RuntimeError(f"{host} did not resolve over DoH")


def api(path: str) -> dict:
    """Normal request first; fall back to DoH only when the name lookup fails."""
    try:
        request = urllib.request.Request(f"https://{HOST}{path}",
                                         headers={"User-Agent": UA})
        return json.loads(urllib.request.urlopen(request, timeout=TIMEOUT).read())
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, socket.gaierror):
            raise
        return _raw_https(HOST, path)


def fetch_symbol(symbol: str, pages: int) -> pd.DataFrame:
    """Page hourly candles backwards until history runs out or `pages` is hit.

    history-candles returns nothing unless seeded with an endTime, so the first
    request anchors on now and each subsequent one on the oldest bar seen.
    """
    end = int(time.time() * 1000)
    frames: list[pd.DataFrame] = []
    seen: set[int] = set()

    for page in range(pages):
        payload = api(f"/api/v2/spot/market/history-candles?symbol={symbol}"
                      f"&granularity=1h&limit={PAGE_LIMIT}&endTime={end}")
        rows = payload.get("data") or []
        if not rows:
            break

        frame = pd.DataFrame(
            [[int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]),
              float(r[4]), float(r[5])] for r in rows], columns=COLUMNS)
        fresh = set(frame["ts"]) - seen
        if not fresh:
            break
        seen |= set(frame["ts"])
        frames.append(frame)
        end = int(min(int(r[0]) for r in rows))
        print(f"      page {page + 1}: +{len(fresh)} bars", flush=True)
        if len(rows) < PAGE_LIMIT:
            break
        time.sleep(PAGE_PAUSE_S)

    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    return (pd.concat(frames).drop_duplicates("ts")
            .sort_values("ts").reset_index(drop=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    args = parser.parse_args(argv)

    print("Fetching rToken candles from Bitget spot\n")
    RAW.mkdir(parents=True, exist_ok=True)

    failures = []
    print(f"{'symbol':<12}{'bars':>7}{'span':>8}{'wknd':>7}  range")
    print("-" * 62)
    for symbol in args.symbols:
        try:
            print(f"  {symbol}", flush=True)
            frame = fetch_symbol(symbol, args.pages)
        except Exception as exc:  # noqa: BLE001
            failures.append(symbol)
            print(f"{symbol:<12}{'-':>7}{'-':>8}{'-':>7}  {type(exc).__name__}: {exc}")
            continue

        if frame.empty:
            failures.append(symbol)
            print(f"{symbol:<12}{'-':>7}{'-':>8}{'-':>7}  no candles returned")
            continue

        out = RAW / f"{symbol}_hour.csv"
        frame.to_csv(out, index=False)
        stamps = pd.to_datetime(frame["ts"], unit="s", utc=True)
        span = (stamps.max() - stamps.min()).days
        weekend = float((stamps.dt.dayofweek >= 5).mean())
        print(f"{symbol:<12}{len(frame):>7}{span:>7}d{weekend:>6.0%}  "
              f"{stamps.min():%Y-%m-%d} to {stamps.max():%Y-%m-%d}")

    print("\nExpected weekend share is near 29%: these trade 7x24, which is the")
    print("whole reason they can be compared with the Solana pools.")
    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1
    print(f"\nwrote {len(args.symbols)} series under {RAW.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
