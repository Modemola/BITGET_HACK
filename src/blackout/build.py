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
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .analogues import FEATURES, build_feature_table
from .basis import add_premium, decompose_closure, hourly_frame
from .calendar_events import historical_overlap, load_events
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


def _json_safe(value):
    """Replace NaN and infinities with null, recursively.

    Python emits bare `NaN` and `Infinity` tokens, which are not valid JSON and
    which `JSON.parse` rejects outright. Since the payload is inlined into the
    page, one NaN anywhere renders the entire page blank -- silently, with no
    error a viewer could act on. A legitimately absent value (a hedge quoted on
    too little history, say) becomes null, which the page can branch on.
    """
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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

    # Analogue features live on a frame carrying the premium AND the crypto
    # proxy, so retrieval can condition on risk appetite going into the window.
    feat_frame = hourly_frame({"x": series["NVDAx"], "nvda": series["NVDA"],
                               "nq": series["NQ_F"], "btc": series["BTC-USD"]}, clock)
    feat_frame = add_premium(feat_frame, token="x", native="nvda")
    feat_frame = feat_frame[feat_frame.index >= ANALYSIS_START]
    features = build_feature_table(feat_frame, clock, token="x", crypto="btc")

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

    # The last bar of each blackout: where a trader fading the premium would
    # have entered, and the moment the decomposition has to be measured from.
    closes = pd.DatetimeIndex([
        d[(d.index >= w["start"]) & (d.index < w["end"])].index.max()
        for _, w in clock.blackouts().iterrows()
        if len(d[(d.index >= w["start"]) & (d.index < w["end"])]) >= 20
        and w["regime"] == Regime.WEEKEND_BLACKOUT.value
        and w["start"] >= d.index.min() and w["end"] <= d.index.max()
    ])

    # Scheduled events. Only what is still ahead ships, since the page matches
    # them against its own live clock rather than a frozen build-time answer.
    events = load_events()
    upcoming_events = events[events["ts_utc"] > now] if not events.empty else events
    calendar_stats = historical_overlap(clock, events)

    horizons = {1: "1h", 6: "6h", 12: "12h"}
    verdict = {"n_weekends": int(paths["window_start"].nunique())}
    for hours, label in horizons.items():
        stats = decompose_closure(d, closes, token="x", horizon_h=hours)
        verdict[f"token_share_{label}"] = stats["token_share"]
        verdict[f"token_pnl_{label}"] = stats["token_leg_pnl"]
        if hours == 12:
            verdict["hit_rate"] = stats["hit_rate"]
            verdict["net_at_10bp"] = stats["token_leg_pnl"] - 0.0010

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
        # The whole feature table ships, so the page runs retrieval client-side
        # and a trader can move the query rather than read a frozen answer.
        "analogue_features": _records(features),
        "analogue_feature_names": list(FEATURES),
        "analogue_defaults": {
            f: (float(features[f].median()) if f in features.columns else None)
            for f in FEATURES
        },
        "hedges": _records(menu) if not menu.empty else [],
        "blackout_windows": windows,
        "regime_runs": runs,
        "events": [{"ts": int(r["ts_utc"].timestamp()), "label": r["label"],
                    "importance": r["importance"]}
                   for _, r in upcoming_events.iterrows()],
        "calendar_stats": calendar_stats,
        "demo": {
            "exposure_usd": DEMO_EXPOSURE,
            "symbol": DEMO_SYMBOL,
            "horizon_h": 72,
        },
        # The finding, as numbers the page can render rather than prose it repeats.
        # Derived, never transcribed: the page's headline evidence has to move
        # with the data like everything else on it, or a refresh leaves the one
        # claim the product is built on quietly out of date.
        "verdict": verdict,
    }


def main() -> int:
    payload = _json_safe(build())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False turns any surviving non-finite value into a loud build
    # failure rather than a page that will not parse in a browser.
    OUT.write_text(json.dumps(payload, indent=1, allow_nan=False), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({kb:.1f} KB)")
    print(f"  coverage : {payload['coverage']['bars']} bars, "
          f"{payload['coverage']['start'][:10]} to {payload['coverage']['end'][:10]}")
    print(f"  windows  : {payload['summary']['n_windows']} analysed, "
          f"{len(payload['blackout_windows'])} upcoming in calendar")
    print(f"  hedges   : {len(payload['hedges'])} instruments priced")
    print(f"  timeline : {len(payload['regime_runs'])} regime runs over 21 days")
    print(f"  analogues: {len(payload['analogue_features'])} windows, "
          f"features {', '.join(payload['analogue_feature_names'])}")
    cs = payload["calendar_stats"]
    print(f"  events   : {len(payload['events'])} ahead; "
          f"{cs['overlaps']} of {cs['events_considered']} ever fell inside "
          f"{cs['windows']} blackouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
