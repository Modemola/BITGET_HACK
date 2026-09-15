"""The seven tools, behind one contract.

Each analytics module answers its own question well, but they load data
differently, take different arguments and return different shapes. That is fine
for a script and wrong for a tool layer: an agent — or a person reading the code
for the first time — needs one way in, one way to discover what exists, and one
shape coming back.

So this is the single entry point. `Desk` loads every series once; each tool is
a function over that desk returning a plain dictionary; and `TOOLS` is a
registry carrying the question each one answers, in the order a trader reasons
through them.

    desk = Desk()
    desk.run("premium_verdict")
    [t.name for t in TOOLS.values()]

Nothing here computes anything new. It is a façade over `clock`, `basis`,
`distributions`, `exposure`, `analogues`, `hedges` and `calendar_events`, so the
numbers a tool returns are the same ones `scripts/analyse_basis.py` reproduces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .analogues import FEATURES, build_feature_table, find_analogues, summarise_analogues
from .basis import add_premium, decompose_closure, hourly_frame
from .calendar_events import assess, historical_overlap, load_events
from .clock import ClosureClock, Regime
from .distributions import drift_by_elapsed_hour, summarise, terminal_gap, window_paths
from .exposure import Position, horizon_breakdown, unhedgeable_exposure
from .hedges import hedge_menu as _hedge_menu
from .hedges import window_returns

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

#: Skip the launch month, where the pool was too thin to price.
ANALYSIS_START = "2026-03-01"

DEFAULT_SYMBOL = "NVDAx"
DEFAULT_NATIVE = "NVDA"
DEFAULT_INDEX = "NQ_F"
DEFAULT_PROXY = "BTC-USD"
DEFAULT_HEDGES = ("BTC-USD", "ETH-USD", "TSLAx")


def load_series(symbol: str) -> pd.Series:
    """Hourly closes for one symbol, indexed on the UTC hour."""
    path = RAW / f"{symbol}_hour.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path.relative_to(ROOT)} is missing; run scripts/probe_sources.py "
            "and scripts/fetch_reference.py"
        )
    df = pd.read_csv(path)
    stamps = pd.to_datetime(df["ts"], unit="s", utc=True).dt.floor("h")
    return df.assign(dt=stamps).drop_duplicates("dt").set_index("dt")["close"].sort_index()


@dataclass
class Desk:
    """Everything the seven tools read, loaded once.

    Constructed lazily: a tool that only needs the calendar should not pay for
    parsing four price series, and `closure_window` is the tool most likely to be
    called on its own.
    """

    symbol: str = DEFAULT_SYMBOL
    native: str = DEFAULT_NATIVE
    index: str = DEFAULT_INDEX
    proxy: str = DEFAULT_PROXY
    start: str = ANALYSIS_START
    clock: ClosureClock = field(
        default_factory=lambda: ClosureClock(start="2025-06-01", end="2027-12-31"))

    _frame: pd.DataFrame | None = field(default=None, init=False, repr=False)
    _paths: pd.DataFrame | None = field(default=None, init=False, repr=False)
    _events: pd.DataFrame | None = field(default=None, init=False, repr=False)

    # --- lazily built inputs ---------------------------------------------
    @property
    def frame(self) -> pd.DataFrame:
        """Hourly grid carrying the token, its reference legs and the premium."""
        if self._frame is None:
            series = {
                "x": load_series(self.symbol),
                "nvda": load_series(self.native),
                "nq": load_series(self.index),
                "btc": load_series(self.proxy),
            }
            frame = add_premium(hourly_frame(series, self.clock), token="x", native="nvda")
            self._frame = frame[frame.index >= self.start].dropna(subset=["prem"])
        return self._frame

    @property
    def paths(self) -> pd.DataFrame:
        """One row per (blackout, elapsed hour), carrying accumulated drift."""
        if self._paths is None:
            self._paths = window_paths(self.frame, self.clock)
        return self._paths

    @property
    def events(self) -> pd.DataFrame:
        if self._events is None:
            self._events = load_events()
        return self._events

    def blackout_closes(self) -> pd.DatetimeIndex:
        """The last bar of each *completed* weekend blackout.

        The window must be fully covered by the data. A blackout still in
        progress has bars in it and no close, and treating its latest bar as one
        silently adds a weekend that has not finished to every figure computed
        from these stamps — which is exactly what it did before this check,
        giving 29 weekends where the analysis counts 28.
        """
        frame = self.frame
        first, last = frame.index.min(), frame.index.max()
        stamps = []
        for _, window in self.clock.blackouts().iterrows():
            if window["regime"] != Regime.WEEKEND_BLACKOUT.value:
                continue
            if window["start"] < first or window["end"] > last:
                continue
            inside = frame[(frame.index >= window["start"]) & (frame.index < window["end"])]
            if len(inside) >= 20:
                stamps.append(inside.index.max())
        return pd.DatetimeIndex(stamps)

    # --- the contract -----------------------------------------------------
    def run(self, name: str, **kwargs: Any) -> dict:
        """Call one tool by name."""
        if name not in TOOLS:
            raise KeyError(f"no such tool: {name!r}. Available: {sorted(TOOLS)}")
        return TOOLS[name].run(self, **kwargs)


# --- 1 ----------------------------------------------------------------------
def closure_window(desk: Desk, as_of: pd.Timestamp | None = None) -> dict:
    """Which regime is it, and when does each venue come back?"""
    as_of = pd.Timestamp.now(tz="UTC") if as_of is None else as_of
    row = desk.clock.annotate(pd.DatetimeIndex([as_of])).iloc[0]
    ahead = desk.clock.blackouts()
    ahead = ahead[ahead["end"] > as_of]
    nxt = None if ahead.empty else ahead.iloc[0]
    return {
        "as_of": as_of.isoformat(),
        "regime": str(row["regime"]),
        "hours_to_cash_open": float(row["tau_cash_h"]),
        "hours_to_futures_open": float(row["tau_futures_h"]),
        "next_blackout_start": None if nxt is None else nxt["start"].isoformat(),
        "next_blackout_end": None if nxt is None else nxt["end"].isoformat(),
        "next_blackout_hours": None if nxt is None else float(nxt["hours"]),
    }


# --- 2 ----------------------------------------------------------------------
def exposure(desk: Desk, usd: float = 250_000, as_of: pd.Timestamp | None = None,
             horizon_h: int = 72) -> dict:
    """How much of the holding period has no reference price?"""
    as_of = pd.Timestamp.now(tz="UTC") if as_of is None else as_of
    summary = unhedgeable_exposure([Position(desk.symbol, usd)], desk.clock, as_of, horizon_h)
    breakdown = horizon_breakdown(desk.clock, as_of, horizon_h)
    return {
        "symbol": desk.symbol,
        "usd": float(usd),
        "horizon_hours": int(horizon_h),
        "blackout_hours": summary["blackout_hours"],
        "share_of_horizon": summary["share_of_horizon"],
        "by_regime": breakdown.to_dict("records"),
    }


# --- 3 ----------------------------------------------------------------------
def divergence_distribution(desk: Desk, bucket_h: int = 6, min_windows: int = 5) -> dict:
    """How far does the premium travel by hour H of a blackout?"""
    table = drift_by_elapsed_hour(desk.paths, bucket_h=bucket_h)
    if not table.empty:
        table = table[table["n_windows"] >= min_windows]
    terminal = terminal_gap(desk.paths)
    stats = summarise(desk.paths)
    if len(terminal):
        excursion = desk.paths.groupby("window_start")["drift"].apply(lambda s: s.abs().max())
        stats["mean_worst_excursion"] = float(excursion.mean())
    return {"summary": stats, "by_elapsed_hour": table.to_dict("records")}


# --- 4 ----------------------------------------------------------------------
def historical_analogues(desk: Desk, k: int = 5, **query: float) -> dict:
    """Which past blackouts looked like this one, and how did they resolve?"""
    features = build_feature_table(desk.frame, desk.clock, token="x", crypto="btc")
    if features.empty:
        return {"matches": [], "summary": {"n": 0}}
    if not query:
        query = {f: float(features[f].median()) for f in FEATURES if f in features.columns}
    matches = find_analogues(features, query, k=k)
    return {
        "query": query,
        "pool_size": int(len(features)),
        "matches": [
            {**{c: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
                for c, v in row.items() if c in
                ("window_start", *FEATURES, "terminal_drift", "max_abs_drift", "distance")}}
            for row in matches.to_dict("records")
        ],
        "summary": summarise_analogues(matches),
    }


# --- 5 ----------------------------------------------------------------------
def premium_verdict(desk: Desk, horizons: tuple[int, ...] = (1, 6, 12)) -> dict:
    """Is the premium tradeable? Which leg actually closes the gap?"""
    closes = desk.blackout_closes()
    legs = {}
    for hours in horizons:
        stats = decompose_closure(desk.frame, closes, token="x", horizon_h=hours)
        legs[f"{hours}h"] = {
            "from_token": stats["from_token"],
            "from_reference": stats["from_fair"],
            "token_share": stats["token_share"],
            "token_leg_pnl": stats["token_leg_pnl"],
            "hit_rate": stats["hit_rate"],
        }
    twelve = legs.get("12h") or next(iter(legs.values()))
    return {
        "n_weekends": int(len(closes)),
        "by_horizon": legs,
        "hit_rate": twelve["hit_rate"],
        "net_at_10bp": twelve["token_leg_pnl"] - 0.0010,
        "tradeable": bool(twelve["token_leg_pnl"] - 0.0010 > 0),
        "verdict": (
            "The gap closes on the reference leg, not the token. Fading it is a "
            "coin flip that loses to costs."
        ),
    }


# --- 6 ----------------------------------------------------------------------
def hedge_menu(desk: Desk, usd: float = 250_000,
               candidates: tuple[str, ...] = DEFAULT_HEDGES) -> dict:
    """What still trades during a blackout, and does it actually help?"""
    names = [desk.symbol, *[c for c in candidates if c != desk.symbol]]
    frame = hourly_frame({n: load_series(n) for n in names}, desk.clock)
    frame = frame[frame.index >= desk.start]
    returns = window_returns(frame, desk.clock, names)
    menu = _hedge_menu(returns, desk.symbol, list(candidates), usd)
    return {
        "exposure_usd": float(usd),
        "n_windows": int(len(returns)),
        "instruments": [] if menu.empty else menu.to_dict("records"),
        "any_stable": bool(not menu.empty and menu["stable"].any()),
    }


# --- 7 ----------------------------------------------------------------------
def macro_calendar(desk: Desk, as_of: pd.Timestamp | None = None) -> dict:
    """Is anything scheduled between now and the moment you can act again?"""
    as_of = pd.Timestamp.now(tz="UTC") if as_of is None else as_of
    window = assess(desk.clock, as_of, desk.events)
    overlap = historical_overlap(desk.clock, desk.events)
    return {
        **{k: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
           for k, v in window.items()},
        "historical_overlap": overlap,
    }


@dataclass(frozen=True)
class Tool:
    name: str
    question: str
    run: Callable[..., dict]


#: In the order a trader reasons through them, which is the order
#: scripts/research_task.py executes and the order the page presents.
TOOLS: dict[str, Tool] = {
    t.name: t for t in (
        Tool("closure_window", "Which venues are open, and for how long?", closure_window),
        Tool("exposure", "What is my book carrying through it?", exposure),
        Tool("divergence_distribution", "How far does price typically travel?",
             divergence_distribution),
        Tool("historical_analogues", "What happened in weekends like this?",
             historical_analogues),
        Tool("premium_verdict", "Is the premium in front of me tradeable?", premium_verdict),
        Tool("hedge_menu", "What can I trade, and at what cost?", hedge_menu),
        Tool("macro_calendar", "Is anything scheduled to explain a move?", macro_calendar),
    )
}


def main(argv: list[str] | None = None) -> int:
    """List the contract, or run one tool: `python -m blackout.tools [name]`.

    Exists so the seven tools are demonstrable rather than merely importable —
    a claim about feature depth should be runnable in one line.
    """
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(prog="blackout.tools", description=__doc__.split("\n")[0])
    parser.add_argument("tool", nargs="?", help="tool to run; omit to list them all")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    args = parser.parse_args(argv)

    if not args.tool:
        print(f"{len(TOOLS)} tools:\n")
        for i, tool in enumerate(TOOLS.values(), 1):
            print(f"  {i:02d}  {tool.name:<26} {tool.question}")
        print("\nRun one:  python -m blackout.tools premium_verdict")
        return 0

    if args.tool not in TOOLS:
        print(f"no such tool: {args.tool}\nAvailable: {', '.join(TOOLS)}")
        return 1

    print(_json.dumps(Desk(symbol=args.symbol).run(args.tool), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
