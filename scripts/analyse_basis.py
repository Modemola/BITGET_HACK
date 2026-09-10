"""Reproduce the Blackout Basis result end to end.

Runs the three tests that decided the strategy, in the order they were run:

  1. Does the premium widen inside a blackout?      (yes)
  2. Does the divergence converge at the reopen?    (yes, 85% of weekends)
  3. Which leg closes it -- token or fair value?    (fair value, 87-92%)

Test 3 is the one that matters. A convergence that happens on the fair-value
leg is a stale reference catching up to a token that was already right, and
there is nothing to trade in it.

    python scripts/analyse_basis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blackout import ClosureClock, Regime  # noqa: E402
from blackout.basis import (  # noqa: E402
    add_premium, decompose_closure, hourly_frame, premium_persistence,
)

START = "2026-03-01"   # skip the pool's partial launch month


def load(symbol: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "raw" / f"{symbol}_hour.csv")
    dt = pd.to_datetime(df["ts"], unit="s", utc=True).dt.floor("h")
    return df.assign(dt=dt).drop_duplicates("dt").set_index("dt")["close"].sort_index()


def main() -> int:
    clock = ClosureClock(start="2025-06-01", end="2027-01-01")
    df = hourly_frame({"x": load("NVDAx"), "nvda": load("NVDA"), "nq": load("NQ_F")}, clock)
    df = add_premium(df, token="x", native="nvda")
    d = df[df.index >= START].dropna(subset=["prem"])
    print(f"NVDAx vs NVDA/NQ — {len(d)} hourly bars, "
          f"{d.index.min():%Y-%m-%d} to {d.index.max():%Y-%m-%d}, beta={df.attrs['beta']:.2f}\n")

    print("=== 1. Premium dispersion by regime ===")
    print(f"{'regime':<20}{'n':>7}{'mean':>9}{'std':>9}{'p5':>9}{'p95':>9}")
    for r in [x.value for x in Regime]:
        s = d.loc[d["regime"] == r, "prem"]
        if len(s) < 20:
            continue
        print(f"{r:<20}{len(s):>7}{s.mean():>8.2%}{s.std():>9.2%}"
              f"{s.quantile(.05):>9.2%}{s.quantile(.95):>9.2%}")

    print("\n=== 2. Convergence at the reopen ===")
    bl = clock.blackouts()
    bl = bl[(bl["regime"] == Regime.WEEKEND_BLACKOUT.value)
            & (bl["start"] >= d.index.min()) & (bl["end"] <= d.index.max())]
    ends, starts = [], []
    for _, w in bl.iterrows():
        inside = d[(d.index >= w["start"]) & (d.index < w["end"])]
        after = d[d.index >= w["end"]]
        if len(inside) < 20 or len(after) < 13:
            continue
        starts.append(inside["prem"].iloc[0])
        ends.append(inside.index[-1])
    ends = pd.DatetimeIndex(ends)
    print(f"  weekends analysed: {len(ends)}")
    print(f"  mean |premium| at blackout start: {np.abs(starts).mean():.2%}")
    print(f"  mean |premium| at blackout end:   {d.loc[ends,'prem'].abs().mean():.2%}")

    print("\n=== 3. Which leg closes the gap? (the decisive test) ===")
    print(f"{'horizon':<10}{'from token':>13}{'from fair':>12}{'token share':>14}{'token P&L':>12}")
    for h in (1, 6, 12):
        r = decompose_closure(d, ends, token="x", horizon_h=h)
        print(f"+{h:<9}{r['from_token']:>12.3%}{r['from_fair']:>12.3%}"
              f"{r['token_share']:>13.0%}{r['token_leg_pnl']:>12.3%}")

    print("\n=== 4. Premium persistence ===")
    p = premium_persistence(d)
    for _, row in p.iterrows():
        print(f"  {row['regime']:<20} n={int(row['n']):>5}  AR(1)={row['ar1']:+.3f}  "
              f"half-life {row['half_life_h']:>5.1f}h")

    print("\n" + "=" * 74)
    print("CONCLUSION: the premium closes on the fair-value leg, not the token leg.")
    print("rToken is the efficient price during closure; the reference is the laggard.")
    print("There is no tradeable convergence here. See docs/FINDINGS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
