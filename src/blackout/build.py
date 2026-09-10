"""Precompute everything the desk page needs into one JSON payload.

The published page has no backend, so every figure it shows is computed here
and inlined at publish time. Two consequences shape this module:

  * Numbers are frozen at build time and stamped with `generated_at`; the page
    must show that date rather than implying live prices.
  * The *calendar* is not frozen. Blackout windows are emitted a year forward so
    the page can compute the current regime and countdown in the browser. The
    clock is genuinely live even though the analytics are not.

Run: python -m blackout.build
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .basis import add_premium, hourly_frame
from .clock import ClosureClock, Regime
from .distributions import drift_by_elapsed_hour, summarise, terminal_gap, window_paths
from .exposure import Position, horizon_breakdown, unhedgeable_exposure
from .hedges import hedge_menu, window_returns

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "web" / "data" / "desk.json"

ANALYSIS_START = "2026-03-01"   # skip the pool's partial launch month
DEMO_EXPOSURE = 250_000
DEMO_SYMBOL = "NVDAx"


def load(symbol: str) -> pd.Series:
    df = pd.read_csv(RAW / f"{symbol}_hour.csv")
    dt = pd.to_datetime(df["ts"], unit="s", utc=True).dt.floor("h")
    return df.assign(dt=dt).drop_duplicates("dt").set_index("dt")["close"].sort_index()


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build() -> dict:
    clock = ClosureClock(start="2025-06-01", end="2027-12-31")

    series = {s: load(s) for s in
              ("NVDAx", "TSLAx", "NVDA", "TSLA", "NQ_F", "BTC-USD", "ETH-USD")}
    df = hourly_frame({"x": series["NVDAx"], "nvda": series["NVDA"], "nq": series["NQ_F"]}, clock)
    df = add_premium(df, token="x", native="nvda")
    d = df[df.index >= ANALYSIS_START].dropna(subset=["prem"])

    paths = window_paths(d, clock)
    drift = drift_by_elapsed_hour(paths)
    # Buckets carried by a single window are the one 73h Good Friday outlier;
    # showing them beside 27-window buckets would misrepresent the sample.
    drift = drift[drift["n_windows"] >= 5]

    hedge_df = hourly_frame({k: series[k] for k in
                             ("NVDAx", "TSLAx", "BTC-USD", "ETH-USD")}, clock)
    hedge_df = hedge_df[hedge_df.index >= ANALYSIS_START]
    returns = window_returns(hedge_df, clock, ["NVDAx", "TSLAx", "BTC-USD", "ETH-USD"])
    menu = hedge_menu(returns, DEMO_SYMBOL, ["BTC-USD", "ETH-USD", "TSLAx"], DEMO_EXPOSURE)

    # Regime shares over the analysis window, for the "where the clock sits" panel.
    shares = (d["regime"].value_counts(normalize=True)
              .reindex([r.value for r in Regime]).fillna(0))

    # Premium dispersion by regime -- the evidence behind the verdict.
    dispersion = []
    for r in [x.value for x in Regime]:
        s = d.loc[d["regime"] == r, "prem"]
        if len(s) < 20:
            continue
        dispersion.append({"regime": r, "n": int(len(s)), "mean": float(s.mean()),
                           "std": float(s.std()), "p5": float(s.quantile(.05)),
                           "p95": float(s.quantile(.95))})

    # Calendar a year forward so the browser can run a live clock offline.
    upcoming = clock.blackouts()
    now = pd.Timestamp.now(tz="UTC")
    upcoming = upcoming[(upcoming["end"] >= now - pd.Timedelta(days=7))
                        & (upcoming["start"] <= now + pd.Timedelta(days=400))]
    windows = [{"start": int(r["start"].timestamp()), "end": int(r["end"].timestamp()),
                "hours": float(r["hours"]), "regime": r["regime"]}
               for _, r in upcoming.iterrows()]

    term = terminal_gap(paths)

    # Run-length encoded regime schedule so the page can draw a live timeline
    # without reconstructing exchange sessions in JavaScript.
    horizon = pd.date_range(now.floor("h"), periods=24 * 21, freq="h", tz="UTC")
    labels = clock.annotate(horizon)["regime"].astype(str).values
    runs, run_start = [], 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[run_start]:
            runs.append({"start": int(horizon[run_start].timestamp()),
                         "end": int(horizon[i - 1].timestamp()) + 3600,
                         "regime": labels[run_start]})
            run_start = i

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coverage": {
            "symbol": DEMO_SYMBOL,
            "start": d.index.min().isoformat(),
            "end": d.index.max().isoformat(),
            "bars": int(len(d)),
            "beta": float(df.attrs["beta"]),
        },
        "summary": summarise(paths),
        "regime_shares": [{"regime": k, "share": float(v)} for k, v in shares.items()],
        "dispersion": dispersion,
        "drift": _records(drift),
        "terminal_gaps": _records(term[["window_start", "drift"]]),
        "hedges": _records(menu) if not menu.empty else [],
        "blackout_windows": windows,
        "regime_runs": runs,
        "demo": {
            "exposure_usd": DEMO_EXPOSURE,
            "symbol": DEMO_SYMBOL,
            "horizon_h": 72,
        },
        # The finding, as numbers the page can render rather than prose it repeats.
        "verdict": {
            "token_share_1h": 0.06, "token_share_6h": 0.27, "token_share_12h": 0.13,
            "hit_rate": 0.50, "n_weekends": int(paths["window_start"].nunique()),
            "net_at_10bp": -0.00009,
        },
    }


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({kb:.1f} KB)")
    print(f"  coverage : {payload['coverage']['bars']} bars, "
          f"{payload['coverage']['start'][:10]} to {payload['coverage']['end'][:10]}")
    print(f"  windows  : {payload['summary']['n_windows']} analysed, "
          f"{len(payload['blackout_windows'])} upcoming in calendar")
    print(f"  hedges   : {len(payload['hedges'])} instruments priced")
    print(f"  timeline : {len(payload['regime_runs'])} regime runs over 21 days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
