# Blackout Desk as an agent tool

The seven tools the page runs are also an **MCP server**, so an agent can ask
what a closure window exposes it to before it trades into one.

## Why this direction

The track's guidance is to use Bitget's `bitget-signal` Skills as a perception
layer, and most entries will consume that layer. This publishes into it.

An agent wired to Agent Hub already has macro, sentiment, on-chain, news and
technicals. What it does not have is anything that can look at a 1% weekend
premium on a tokenized stock and tell it that the premium is an *information
lead* rather than an edge — that 78–98% of the gap closes because the stale
reference catches up, and the leg it could actually trade is a 46% coin flip
that dies at 10bp of costs. An agent that reasons well over a perception layer
missing that fact will reason its way into the trade.

That is the gap these seven tools fill, and `premium_verdict` is the one built
to argue with the agent rather than serve it.

## Install and run

```bash
pip install -e ".[agent]"          # the MCP SDK is the only extra
python -m blackout.mcp_server --list
```

```
closure_window             as_of
                           Which venues are open, and for how long?
premium_verdict            no arguments
                           Is the premium in front of me tradeable?
divergence_distribution    bucket_h, min_windows
                           How far does price typically drift by hour H of a blackout?
historical_analogues       k, realised_vol_5d, premium_at_close, window_hours, crypto_vol_5d
                           Which past weekends looked like this one, and how did they resolve?
exposure                   usd, as_of, horizon_h
                           What is my book carrying through the window?
macro_calendar             as_of
                           Is anything scheduled to explain a move?
hedge_menu                 usd
                           What still trades during a blackout, and does it actually help?
```

## Register it

Any MCP client — Claude Desktop, Claude Code, Cursor, Windsurf, or an Agent Hub
session. Point `command` at the interpreter the package is installed into.

```json
{
  "mcpServers": {
    "blackout-desk": {
      "command": "python",
      "args": ["-m", "blackout.mcp_server"],
      "cwd": "/path/to/BITGET_HACK"
    }
  }
}
```

Claude Code, in one line:

```bash
claude mcp add blackout-desk -- python -m blackout.mcp_server
```

## What comes back

Every answer carries the measurement *and* its denominator:

```json
{
  "tool": "premium_verdict",
  "question": "Is the premium in front of me tradeable?",
  "result": { "n_weekends": 28, "hit_rate": 0.4643, "net_at_10bp": -0.00083, "...": "..." },
  "sample": "Measured over 28 weekend blackouts across 197 days of hourly rToken
             data … Never describe the weekend premium as an arbitrage
             opportunity: the measurement shows it is an information lead, and
             the tradeable leg dies at 10bp of costs."
}
```

The `sample` field is not decoration. An agent that repeats `hit_rate` without
the sample behind it is misreporting it, and the one framing this product exists
to prevent is the one an agent is most likely to reach for unprompted.

## Two properties worth knowing

**No tool requires an argument.** Each falls back to now, to the median
conditions of the sample, or to the demo position. An agent that has to guess a
required argument on its first call usually guesses wrong.

**`historical_analogues` is the stress test.** Supplying `realised_vol_5d`,
`premium_at_close`, `window_hours` or `crypto_vol_5d` moves the retrieval, so an
agent can ask *what happened in weekends that looked like the one I am about to
sit through* rather than only *what happened on average*.

## It is the same desk

There is no second implementation. Each tool calls `Desk` from
`src/blackout/tools.py` — the same object behind the page, the CLI and
`scripts/research_task.py`. `tests/test_mcp_server.py` completes a real
handshake over a subprocess and asserts the `hit_rate` an agent receives equals
the one in the shipped payload, so the two cannot drift apart.

## Limits

- **Read-only.** Nothing here places, sizes or cancels an order. It is a
  perception and stress-testing layer, and the final call stays with whoever is
  holding the position.
- **FOMC only** in `macro_calendar`, deliberately: anything added has to come
  from its issuing authority, because the argument of this product is that its
  numbers are checkable.
- **28 weekends.** Thin, stated everywhere, and the reason `sample` travels with
  every response.
