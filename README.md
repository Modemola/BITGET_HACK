# Blackout Desk

**Bitget AI Base Camp Hackathon S2** — 🟧 AI Trading Desk · Decision Stress Testing

A closure-window risk desk for traders holding tokenized US stocks. It is Friday
15:45 in New York; for the next **49 hours** one venue on earth quotes your
position, you cannot watch it, and no arbitrageur stands behind the price.
Blackout Desk tells you what you are exposed to before that window opens.

Its central claim is counterintuitive and measured, not assumed: the weekend
premium on rToken is **not an arbitrage opportunity**. Across 210 days of hourly
data, 87–92% of the gap closes because the stale reference catches up, not
because the token corrects. Trading against it is a coin flip that dies at 10bp
costs. See [`docs/FINDINGS.md`](docs/FINDINGS.md).

## Documentation

| Doc | What it covers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design, tool contract, build plan to 21 Sep |
| [`docs/FINDINGS.md`](docs/FINDINGS.md) | The research result and every variant tested |
| [`docs/S2_BRIEF.md`](docs/S2_BRIEF.md) | Competition rules, tracks, submission requirements |

## Quick start

```bash
pip install -r requirements.txt
python -m pytest tests/ -q              # 41 tests
python scripts/analyse_basis.py         # reproduce the research finding
python scripts/blackout_stats.py        # closure-window calendar structure
```

Refreshing data (needs open network — market data hosts are blocked in the
Claude Code web sandbox):

```bash
python scripts/probe_sources.py         # rToken hourly, rate-limited, resumable
python scripts/fetch_reference.py       # native equity, futures, crypto proxies
```

**Deadline: 21 September 2026 (UTC+8).**
