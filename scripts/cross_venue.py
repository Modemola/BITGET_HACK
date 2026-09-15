"""Re-measure the finding on Bitget's own book, and see whether it holds.

Every figure the desk reports comes from one venue: xStocks pools on Solana. A
result measured on a single venue is a result about that venue until someone
checks another one -- and Bitget lists the same underlyings itself, under an R
prefix. This runs the decisive test on both and prints them side by side.

    python scripts/cross_venue.py
    python scripts/cross_venue.py --json      # the same figures, for the guard

The comparable window is *derived, not assumed*. Bitget's rTokens did not always
trade through the weekend: for most of their history the weekend share of hourly
bars is near zero, which means they ran on the native equity clock and there is
no closure window in them to measure. `seven_by_twentyfour_start` finds the month
that changes, and everything is compared only from there -- otherwise the two
venues are being asked different questions.

That shortens the sample hard, to around a dozen weekends. The comparison is
still worth making, and the third row of the table is the reason: running the
*same* venue over the *same* short window shows how much of any difference is
the venue and how much is just the sample.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blackout import ClosureClock, Regime  # noqa: E402
from blackout.basis import add_premium, decompose_closure, hourly_frame  # noqa: E402
from blackout.tools import load_series  # noqa: E402

#: The venue pair, matched on the same underlying so only the venue differs.
SOLANA = "NVDAx"
BITGET = "RNVDAUSDT"
NATIVE = "NVDA"
INDEX = "NQ_F"

START = "2026-03-01"          # skip the Solana pool's partial launch month
HORIZONS = (1, 6, 12)

#: A month counts as 7x24 once this share of its bars fall on a weekend. A
#: continuously traded hourly series is ~28.6% weekend; a session-only one is
#: ~0%. The threshold sits between them with room on both sides, so it does not
#: turn on a few missing bars.
WEEKEND_SHARE_7X24 = 0.15


def seven_by_twentyfour_start(series: pd.Series) -> pd.Timestamp | None:
    """First month in which this series trades through the weekend.

    Returns None if it never does -- in which case there is no closure window in
    it and no comparison to make, which is a finding rather than an error.
    """
    weekend = series.index.dayofweek >= 5
    by_month = pd.Series(weekend, index=series.index).groupby(
        pd.Grouper(freq="MS")).mean()
    qualifying = by_month[by_month >= WEEKEND_SHARE_7X24]
    return None if qualifying.empty else qualifying.index[0]


def weekend_share_by_month(series: pd.Series) -> dict[str, float]:
    weekend = series.index.dayofweek >= 5
    by_month = pd.Series(weekend, index=series.index).groupby(
        pd.Grouper(freq="MS")).mean()
    return {f"{m:%Y-%m}": round(float(v), 4) for m, v in by_month.items()}


def priced(token: pd.Series, clock: ClosureClock, beta: float | None = None,
           start: str | pd.Timestamp = START) -> pd.DataFrame:
    """One token series against the shared reference, premium attached."""
    frame = hourly_frame(
        {"x": token, "nvda": load_series(NATIVE), "nq": load_series(INDEX)}, clock)
    frame = add_premium(frame, token="x", native="nvda", beta=beta)
    # `start` arrives either as a plain string or as a stamp already carrying UTC
    # from the cutover search; localize only the one that needs it.
    floor = pd.Timestamp(start)
    floor = floor.tz_localize("UTC") if floor.tzinfo is None else floor.tz_convert("UTC")
    return frame[frame.index >= floor].dropna(subset=["prem"])


def qualifying_windows(frame: pd.DataFrame, clock: ClosureClock) -> set[pd.Timestamp]:
    """Weekend blackouts this frame covers end to end, keyed by window start.

    Mirrors `tools.blackout_closes`: a window still in progress has bars in it
    and no close, and counting its latest bar as one silently adds an unfinished
    weekend to every figure below it.
    """
    first, last = frame.index.min(), frame.index.max()
    starts = set()
    for _, window in clock.blackouts().iterrows():
        if window["regime"] != Regime.WEEKEND_BLACKOUT.value:
            continue
        if window["start"] < first or window["end"] > last:
            continue
        inside = frame[(frame.index >= window["start"]) & (frame.index < window["end"])]
        after = frame[frame.index >= window["end"]]
        if len(inside) >= 20 and len(after) >= max(HORIZONS) + 1:
            starts.add(window["start"])
    return starts


def closes_for(frame: pd.DataFrame, clock: ClosureClock,
               starts: set[pd.Timestamp]) -> pd.DatetimeIndex:
    """Each venue's own last bar inside a *given* set of weekends.

    The set is passed in rather than derived here, because the whole comparison
    turns on the two venues being asked about the same weekends. Deriving it
    per-venue gave 15 weekends on one and 13 on the other and still called the
    rows "the same window", which would have made any difference between them
    partly a difference of sample -- the exact confound this script exists to
    separate.
    """
    stamps = []
    for _, window in clock.blackouts().iterrows():
        if window["start"] not in starts:
            continue
        inside = frame[(frame.index >= window["start"]) & (frame.index < window["end"])]
        if len(inside):
            stamps.append(inside.index.max())
    return pd.DatetimeIndex(sorted(stamps))


def dispersion(frame: pd.DataFrame) -> dict[str, float]:
    """Premium standard deviation per regime -- the shape the desk's chart shows."""
    out = {}
    for regime in (r.value for r in Regime):
        series = frame.loc[frame["regime"] == regime, "prem"]
        if len(series) >= 20:
            out[regime] = round(float(series.std()), 6)
    return out


def legs(frame: pd.DataFrame, clock: ClosureClock,
         starts: set[pd.Timestamp]) -> dict:
    closes = closes_for(frame, clock, starts)
    by_horizon = {}
    for hours in HORIZONS:
        result = decompose_closure(frame, closes, token="x", horizon_h=hours)
        by_horizon[f"{hours}h"] = {
            "token_share": round(result["token_share"], 6),
            "from_token": round(result["from_token"], 8),
            "from_fair": round(result["from_fair"], 8),
            "n": result["n"],
        }
    return {"n_weekends": len(closes), "by_horizon": by_horizon}


def cross_venue() -> dict:
    """The whole comparison, as data. The printout and the guard both read this."""
    clock = ClosureClock(start="2025-06-01", end="2027-01-01")
    solana_px, bitget_px = load_series(SOLANA), load_series(BITGET)

    cutover = seven_by_twentyfour_start(bitget_px)
    if cutover is None:
        raise ValueError(
            f"{BITGET} never trades through a weekend in this sample, so it has "
            "no closure window to compare. Re-run scripts/fetch_bitget.py."
        )

    solana_full = priced(solana_px, clock)
    # One beta for both venues. It is fitted on the native underlying against the
    # index and has nothing to do with where the token trades, so refitting it
    # per venue would introduce a difference that is not about the venue.
    beta = float(solana_full.attrs.get("beta", 0.0)) or None

    solana_window = priced(solana_px, clock, beta=beta, start=cutover)
    bitget_window = priced(bitget_px, clock, beta=beta, start=cutover)

    # Only weekends both venues cover end to end. Anything else compares two
    # different samples and reports the difference as a venue effect.
    shared = (qualifying_windows(solana_window, clock)
              & qualifying_windows(bitget_window, clock))
    if len(shared) < 5:
        raise ValueError(
            f"only {len(shared)} weekends are covered by both venues; too few to "
            "compare. Re-run scripts/fetch_bitget.py for more history."
        )

    return {
        "comparable_from": f"{cutover:%Y-%m}",
        "shared_weekends": len(shared),
        "weekend_share_by_month": {BITGET: weekend_share_by_month(bitget_px)},
        "dispersion": {
            SOLANA: dispersion(solana_window),
            BITGET: dispersion(bitget_window),
        },
        "legs": {
            f"{SOLANA}_full": legs(solana_full, clock,
                                   qualifying_windows(solana_full, clock)),
            f"{SOLANA}_window": legs(solana_window, clock, shared),
            f"{BITGET}_window": legs(bitget_window, clock, shared),
        },
    }


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true",
                        help="emit the figures as JSON instead of a table")
    args = parser.parse_args(argv)

    try:
        result = cross_venue()
    except FileNotFoundError as exc:
        print(f"missing data: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Cross-venue check: {SOLANA} (Solana pools) vs {BITGET} (Bitget spot)\n")

    print("=== When did Bitget's rToken start trading 7x24? ===")
    for month, share in result["weekend_share_by_month"][BITGET].items():
        mark = " <- comparable from here" if month == result["comparable_from"] else ""
        print(f"  {month}  weekend share {share:>6.1%}{mark}")
    print("\n  Below ~15% the series runs on the native equity clock and has no")
    print("  closure window in it at all, so those months cannot be compared.\n")

    print(f"=== Premium dispersion by regime, from {result['comparable_from']} ===")
    regimes = [r.value for r in Regime]
    print(f"{'venue':<14}" + "".join(f"{r:>20}" for r in regimes))
    for venue, row in result["dispersion"].items():
        print(f"{venue:<14}" + "".join(
            f"{row[r]:>19.2%}" if r in row else f"{'-':>20}" for r in regimes))

    print("\n=== Which leg closes the gap? (token share, by sample) ===")
    print(f"{'sample':<26}{'weekends':>10}"
          + "".join(f"{f'+{h}h':>12}" for h in HORIZONS))
    for name, row in result["legs"].items():
        cells = ""
        for hours in HORIZONS:
            cell = row["by_horizon"][f"{hours}h"]
            # A weekend with no bar at close+h drops out of that horizon only, so
            # the horizons in one row can rest on different numbers of weekends.
            cells += f"{_pct(cell['token_share'])} (n={cell['n']})".rjust(12)
        print(f"{name:<26}{row['n_weekends']:>10}{cells}")

    print("\n=== How big are the legs being divided? ===")
    for name, row in result["legs"].items():
        for hours in HORIZONS:
            cell = row["by_horizon"][f"{hours}h"]
            total = cell["from_token"] + cell["from_fair"]
            note = "  <- fair leg near zero; the share is not a measurement" \
                if abs(cell["from_fair"]) < 0.0005 else ""
            print(f"  {name:<24}+{hours:<3} token {cell['from_token']:+.4%}"
                  f"  fair {cell['from_fair']:+.4%}  total {total:+.4%}{note}")

    print("\n" + "=" * 74)
    print("Read the middle row against the bottom one before reading either against")
    print("the top. Same venue, shorter window is the sample effect; different venue,")
    print("same window is the venue effect. Where they disagree, it is the sample.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
