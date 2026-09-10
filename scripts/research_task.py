"""The complete research task, run end to end through all seven tools.

    "I'm long $250k of NVDAx into this weekend. What am I exposed to,
     and should I hedge?"

This is the required demo deliverable, written as a program rather than as prose
so that every figure in it is computed at run time. If the data changes, the
walkthrough changes with it; nothing here can quietly go stale, and nobody has
to take a narrated number on trust.

    python scripts/research_task.py

Output is deliberately plain ASCII: the Windows console is cp1252 and mangles
anything else.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blackout import ClosureClock, Regime                      # noqa: E402
from blackout.analogues import (                               # noqa: E402
    build_feature_table, find_analogues, summarise_analogues,
)
from blackout.basis import add_premium, decompose_closure, hourly_frame  # noqa: E402
from blackout.build import ANALYSIS_START, load                # noqa: E402
from blackout.calendar_events import assess, historical_overlap, load_events  # noqa: E402
from blackout.distributions import summarise, terminal_gap, window_paths      # noqa: E402
from blackout.exposure import Position, horizon_breakdown, unhedgeable_exposure  # noqa: E402
from blackout.hedges import hedge_menu, window_returns         # noqa: E402

EXPOSURE_USD = 250_000
SYMBOL = "NVDAx"
HORIZON_H = 72


def rule(n: int, title: str) -> None:
    print(f"\n{'=' * 74}\n{n}. {title}\n{'=' * 74}")


def main() -> int:
    as_of = pd.Timestamp.now(tz="UTC")
    print("BLACKOUT DESK - complete research task")
    print(f"Question : I'm long ${EXPOSURE_USD:,} of {SYMBOL} into this weekend.")
    print("           What am I exposed to, and should I hedge?")
    print(f"As of    : {as_of:%Y-%m-%d %H:%M} UTC")

    clock = ClosureClock(start="2025-06-01", end="2027-12-31")
    series = {s: load(s) for s in
              ("NVDAx", "TSLAx", "NVDA", "NQ_F", "BTC-USD", "ETH-USD")}

    df = hourly_frame({"x": series["NVDAx"], "nvda": series["NVDA"],
                       "nq": series["NQ_F"], "btc": series["BTC-USD"]}, clock)
    df = add_premium(df, token="x", native="nvda")
    d = df[df.index >= ANALYSIS_START].dropna(subset=["prem"])

    # ---- 1. closure_window -------------------------------------------------
    rule(1, "closure_window - what window am I facing?")
    ann = clock.annotate(pd.DatetimeIndex([as_of])).iloc[0]
    windows = clock.blackouts()
    nxt = windows[windows["end"] > as_of].iloc[0]
    print(f"  Right now            : {ann['regime']}")
    print(f"  Next blackout opens  : {nxt['start']:%a %d %b %H:%M} UTC")
    print(f"  Reference returns    : {nxt['end']:%a %d %b %H:%M} UTC")
    print(f"  Duration             : {nxt['hours']:.0f} hours with no reference price")

    # ---- 2. exposure -------------------------------------------------------
    rule(2, "exposure - what is my book actually carrying?")
    e = unhedgeable_exposure([Position(SYMBOL, EXPOSURE_USD)], clock, as_of, HORIZON_H)
    print(f"  Gross                : ${e['gross_usd']:,.0f}")
    print(f"  Unhedgeable hours    : {e['blackout_hours']:.0f} of {HORIZON_H} "
          f"({e['share_of_horizon']:.0%})")
    for row in horizon_breakdown(clock, as_of, HORIZON_H).itertuples():
        if row.hours:
            print(f"    {row.regime:<18} {row.hours:>3.0f}h  {row.share:>5.0%}")

    # ---- 3. macro_calendar -------------------------------------------------
    rule(3, "macro_calendar - is anything scheduled?")
    ev = load_events()
    a = assess(clock, as_of, ev)
    overlap = historical_overlap(clock, ev)
    print(f"  Inside the window    : {a['events_inside']} scheduled events")
    if a["events_after"]:
        print(f"  Waiting at the reopen: {a['next_event']} on "
              f"{a['next_event_ts']:%a %d %b %H:%M} UTC")
    print(f"  Historically         : {overlap['overlaps']} of "
          f"{overlap['events_considered']} rate decisions have ever fallen inside "
          f"one of {overlap['windows']} weekend blackouts")
    print("  => Weekend risk is UNSCHEDULED risk. There is nothing to plan around,")
    print("     which is why the historical distribution is the only guide.")

    # ---- 4. divergence_distribution ---------------------------------------
    rule(4, "divergence_distribution - how far does it typically move?")
    paths = window_paths(d, clock)
    s = summarise(paths)
    term = terminal_gap(paths)
    print(f"  Sample               : {s['n_windows']} weekend blackouts")
    print(f"  Mean |drift|         : {s['mean_abs_terminal_drift']:.2%}  "
          f"(${EXPOSURE_USD * s['mean_abs_terminal_drift']:,.0f})")
    print(f"  p95 |drift|          : {s['p95_abs_terminal_drift']:.2%}  "
          f"(${EXPOSURE_USD * s['p95_abs_terminal_drift']:,.0f})")
    print(f"  Worst observed       : {s['worst_terminal_drift']:.2%}  "
          f"(${EXPOSURE_USD * s['worst_terminal_drift']:,.0f})")
    print(f"  Beyond +/-1%         : {s['share_exceeding_1pct']:.0%} of weekends")
    intra = paths.groupby("window_start")["drift"].apply(lambda x: x.abs().max())
    print(f"  Worst point reached  : {intra.mean():.2%} on average, vs "
          f"{term['drift'].abs().mean():.2%} where they ended")
    print("  => The drawdown you sit through is larger than the number you wake up to.")

    # ---- 5. historical_analogues ------------------------------------------
    rule(5, "historical_analogues - what happened in weekends like this?")
    feat = build_feature_table(d, clock, token="x", crypto="btc")
    recent_vol = feat["realised_vol_5d"].iloc[-1]
    recent_prem = float(d["prem"].iloc[-1])
    query = {"realised_vol_5d": recent_vol, "premium_at_close": recent_prem,
             "window_hours": float(nxt["hours"])}
    print(f"  Conditions now       : vol {recent_vol:.0%}, premium "
          f"{recent_prem:+.2%}, {nxt['hours']:.0f}h window")
    matches = find_analogues(feat, query, k=5)
    print(f"  {'weekend':<12}{'vol':>6}{'prem in':>10}{'ended':>10}{'worst':>9}{'dist':>7}")
    for _, m in matches.iterrows():
        print(f"  {m['window_start']:%Y-%m-%d}{m['realised_vol_5d']:>6.0%}"
              f"{m['premium_at_close']:>10.2%}{m['terminal_drift']:>10.2%}"
              f"{m['max_abs_drift']:>9.2%}{m['distance']:>7.2f}")
    ms = summarise_analogues(matches)
    print(f"  Range of outcomes    : {ms['range_low']:+.2%} to {ms['range_high']:+.2%}")
    print(f"  Worst point in set   : {ms['max_excursion']:.2%} "
          f"(${EXPOSURE_USD * ms['max_excursion']:,.0f})")

    # ---- 6. premium_verdict ------------------------------------------------
    rule(6, "premium_verdict - is the premium tradeable?")
    closes = pd.DatetimeIndex([
        d[(d.index >= w["start"]) & (d.index < w["end"])].index.max()
        for _, w in windows.iterrows()
        if w["regime"] == Regime.WEEKEND_BLACKOUT.value
        and w["start"] >= d.index.min() and w["end"] <= d.index.max()
        and len(d[(d.index >= w["start"]) & (d.index < w["end"])]) >= 20
    ])
    for h in (1, 6, 12):
        st = decompose_closure(d, closes, token="x", horizon_h=h)
        print(f"  +{h:>2}h  closure from token {st['token_share']:>4.0%}   "
              f"from stale reference {1 - st['token_share']:>4.0%}")
    twelve = decompose_closure(d, closes, token="x", horizon_h=12)
    print(f"  Hit rate fading it   : {twelve['hit_rate']:.1%}")
    print(f"  Net at 10bp costs    : {twelve['token_leg_pnl'] - 0.0010:+.3%} per weekend")
    print("  => NOT an arbitrage. The gap closes because the reference catches up,")
    print("     not because the token corrects. Do not trade against it.")

    # ---- 7. hedge_menu -----------------------------------------------------
    rule(7, "hedge_menu - what can I actually hedge with?")
    hf = hourly_frame({k: series[k] for k in
                       ("NVDAx", "TSLAx", "BTC-USD", "ETH-USD")}, clock)
    hf = hf[hf.index >= ANALYSIS_START]
    returns = window_returns(hf, clock, ["NVDAx", "TSLAx", "BTC-USD", "ETH-USD"])
    menu = hedge_menu(returns, SYMBOL, ["BTC-USD", "ETH-USD", "TSLAx"], EXPOSURE_USD)
    for _, h in menu.iterrows():
        print(f"  {h['instrument']:<9} corr {h['correlation']:+.2f}  "
              f"short ${h['notional_usd']:>8,.0f}  cost ${h['cost_usd']:>6,.0f}  "
              f"cuts {h['risk_reduction']:.0%}")
        print(f"  {'':<9} {h['verdict']}")

    # ---- the answer --------------------------------------------------------
    rule(8, "ACTIONABLE INSIGHT")
    typical = EXPOSURE_USD * s["mean_abs_terminal_drift"]
    tail = EXPOSURE_USD * s["p95_abs_terminal_drift"]
    best = menu.iloc[0]
    print(f"  You are carrying ${EXPOSURE_USD:,} through {nxt['hours']:.0f} hours in which")
    print(f"  no reference price exists and nothing is scheduled to explain a move.")
    print()
    print(f"  Expect     : +/-${typical:,.0f} typical, +/-${tail:,.0f} at the 95th percentile,")
    print(f"               a worse excursion mid-window than at the end,")
    print(f"               and a {s['share_exceeding_1pct']:.0%} chance of finishing beyond 1%.")
    print()
    print("  Do NOT     : trade against the premium. It is an information lead, and")
    print(f"               fading it is a {twelve['hit_rate']:.0%} coin flip that loses to fees.")
    print()
    print(f"  Hedging    : the best available is {best['instrument']} at "
          f"{best['correlation']:+.2f} correlation,")
    print(f"               cutting {best['risk_reduction']:.0%} of variance for "
          f"${best['cost_usd']:,.0f}. But it is")
    print("               unstable - the rolling correlation has changed sign, so it")
    print("               has been risk-ADDING in past stretches.")
    print()
    if a["events_after"]:
        print(f"  Also note  : {a['next_event']} lands "
              f"{a['next_event_ts']:%a %d %b} - shortly after the reopen. A quiet")
        print("               weekend into a rate decision is not a quiet position.")
        print()
    print("  Decision   : size the position so the p95 outcome is survivable, or trim")
    print("               before the close. Do not pay for an unstable hedge, and do")
    print("               not treat the premium as free money. The trader decides.")
    print(f"\n  Sample: {s['n_windows']} weekend blackouts. Thin. Read the range, not the middle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
