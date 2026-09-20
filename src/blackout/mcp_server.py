"""Blackout Desk as an MCP server: the seven tools, callable by an agent.

The desk already answers these questions for a human reading a page. This makes
the same seven answers available to an agent -- Bitget's Agent Hub, Claude
Desktop, Cursor, or anything else that speaks MCP -- so a trading agent can ask
what a closure window exposes it to *before* it places an order into one.

That direction is the point. The track's own guidance is to use Bitget's
research Skills as a perception layer, and most entries will consume that layer.
This publishes into it: an agent with `bitget-signal` for macro and sentiment
still has nothing that can tell it the weekend premium in front of it is an
information lead rather than an edge. That is what these seven tools are for.

    pip install -e ".[agent]"
    python -m blackout.mcp_server            # stdio, for an MCP client
    python -m blackout.mcp_server --list     # what it exposes, without a client

Register it with any MCP client (`docs/AGENT.md` has the exact config):

    {"mcpServers": {"blackout-desk": {
        "command": "python", "args": ["-m", "blackout.mcp_server"]}}}

Every answer comes from `Desk` in `blackout.tools` -- the same registry the
page, the CLI and `scripts/research_task.py` use. An agent calling
`premium_verdict` gets the number the page prints because it is the same call,
not because two implementations were kept in step.
"""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any

from .tools import TOOLS, Desk

#: Stated with every answer, because an agent that repeats these figures without
#: the sample behind them is misreporting them.
SAMPLE = (
    "Measured over 28 weekend blackouts across 197 days of hourly rToken data "
    "(NVDAx against NVDA and NQ futures). That sample is thin and it is the "
    "honest denominator for every distribution here. Never describe the weekend "
    "premium as an arbitrage opportunity: the measurement shows it is an "
    "information lead, and the tradeable leg dies at 10bp of costs."
)

AsOf = Annotated[str | None, "ISO-8601 UTC instant, e.g. 2026-09-18T19:45:00Z. "
                             "Omit for now."]
Usd = Annotated[float, "Position size in US dollars."]


def _as_of(value: str | None):
    """Turn an instant off the wire into a UTC timestamp, or say why not.

    An agent can read "not a valid instant" and retry; a traceback just ends
    the turn.
    """
    if not value:
        return None
    import pandas as pd
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"as_of={value!r} is not a valid instant: {exc}") from exc
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _wrap(name: str, result: dict) -> dict:
    return {"tool": name, "question": TOOLS[name].question,
            "result": result, "sample": SAMPLE}


def build_server():
    """Wire the seven tools to an MCP server.

    The SDK builds each tool's schema from the wrapper's annotations, so the
    wrappers are written out rather than generated: this is the contract an
    agent reads to decide what to call, and it should be legible as such.
    """
    from mcp.server import MCPServer

    server = MCPServer(
        name="blackout-desk",
        version="0.1.0",
        instructions=(
            "Closure-window risk for tokenized US stocks (rToken). Call "
            "closure_window first to establish the regime, then the tool that "
            "answers the question asked. premium_verdict is the one to reach "
            "for whenever a weekend premium is described as an opportunity: it "
            "will almost always say no, and it shows the working. " + SAMPLE
        ),
    )
    desk = Desk()

    def closure_window(as_of: AsOf = None) -> dict:
        """Which venues are open, and for how long?

        Call this first. Establishes the current regime, the hours until each
        venue reopens, and how many blackout hours lie ahead. Every other
        answer here is conditioned on it.
        """
        return _wrap("closure_window", desk.run("closure_window", as_of=_as_of(as_of)))

    def premium_verdict() -> dict:
        """Is the premium in front of me tradeable?

        Splits the closure of the rToken-to-fair-value gap into the leg that
        can be traded and the leg that cannot, then nets it against costs. Call
        this whenever a weekend premium is described as free money. The answer
        is almost always no, with the evidence attached.
        """
        return _wrap("premium_verdict", desk.run("premium_verdict"))

    def divergence_distribution(
        bucket_h: Annotated[int, "Width of each elapsed-hour bucket."] = 6,
        min_windows: Annotated[int, "Drop buckets backed by fewer weekends."] = 5,
    ) -> dict:
        """How far does price typically drift by hour H of a blackout?

        Returns the empirical distribution, not a point forecast. Use it to
        size against the spread of outcomes rather than the average.
        """
        return _wrap("divergence_distribution", desk.run(
            "divergence_distribution", bucket_h=bucket_h, min_windows=min_windows))

    def historical_analogues(
        k: Annotated[int, "How many past weekends to retrieve."] = 5,
        realised_vol_5d: Annotated[float | None,
                                   "Annualised 5-day realised vol as a "
                                   "fraction, e.g. 0.48 for 48%."] = None,
        premium_at_close: Annotated[float | None,
                                    "Premium at the Friday close as a "
                                    "fraction, e.g. 0.003 for +0.30%."] = None,
        window_hours: Annotated[float | None,
                                "Closure length in hours; 49 is ordinary."] = None,
        crypto_vol_5d: Annotated[float | None,
                                 "Annualised 5-day BTC vol as a fraction."] = None,
    ) -> dict:
        """Which past weekends looked like this one, and how did they resolve?

        Weighted nearest-neighbour retrieval over past blackouts, matched only
        on conditions knowable before the close. Supply any of the conditions to
        stress a scenario; omitted ones fall back to the median of the sample.
        Returns the worst point each weekend reached, not just where it ended.
        """
        query = {k_: v for k_, v in (
            ("realised_vol_5d", realised_vol_5d),
            ("premium_at_close", premium_at_close),
            ("window_hours", window_hours),
            ("crypto_vol_5d", crypto_vol_5d),
        ) if v is not None}
        return _wrap("historical_analogues",
                     desk.run("historical_analogues", k=k, **query))

    def exposure(
        usd: Usd = 250_000,
        as_of: AsOf = None,
        horizon_h: Annotated[int, "Hours ahead to account for."] = 72,
    ) -> dict:
        """What is my book carrying through the window?

        Breaks the position down by regime across the coming window and prices
        the typical, 95th-percentile and worst observed move against it.
        """
        return _wrap("exposure", desk.run(
            "exposure", usd=usd, as_of=_as_of(as_of), horizon_h=horizon_h))

    def macro_calendar(as_of: AsOf = None) -> dict:
        """Is anything scheduled to explain a move?

        Checks scheduled events against the window being held through. Sourced
        from the Federal Reserve's own calendar; covers FOMC decisions only,
        deliberately -- an aggregator has no place in a tool whose argument is
        that its numbers are checkable.
        """
        return _wrap("macro_calendar", desk.run("macro_calendar", as_of=_as_of(as_of)))

    def hedge_menu(usd: Usd = 250_000) -> dict:
        """What still trades during a blackout, and does it actually help?

        Prices the instruments still quoting while equities and futures are
        shut, and reports the rolling range of each correlation beside its mean.
        A hedge justified by an average correlation that changes sign is not a
        hedge.
        """
        return _wrap("hedge_menu", desk.run("hedge_menu", usd=usd))

    for fn in (closure_window, premium_verdict, divergence_distribution,
               historical_analogues, exposure, macro_calendar, hedge_menu):
        server.add_tool(fn)

    return server


async def _listing() -> list[Any]:
    return await build_server().list_tools()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    import asyncio

    if "--list" in argv:
        tools = asyncio.run(_listing())
        for tool in tools:
            args = ", ".join(tool.input_schema.get("properties", {})) or "no arguments"
            first = (tool.description or "").strip().splitlines()[0]
            print(f"{tool.name:26} {args}")
            print(f"{'':26} {first}")
        print(f"\n{len(tools)} tools. Run without --list to serve over stdio.")
        if len(tools) != len(TOOLS):
            print(f"WARNING: the desk has {len(TOOLS)} tools but {len(tools)} "
                  "are exposed", file=sys.stderr)
            return 1
        return 0

    asyncio.run(build_server().run_stdio_async())
    return 0


if __name__ == "__main__":
    sys.exit(main())
