# BITGET_HACK

Bitget AI Base Camp Hackathon S2 — AI × US stock trading (tokenized US stocks / rToken).

**Entry:** Blackout Basis — trading the rToken arbitrage band across market-closure
windows. Alpha Factory track, Cross-Market Correlation sub-theme.

- [`docs/S2_BRIEF.md`](docs/S2_BRIEF.md) — consolidated competition rules, tracks, prizes, submission requirements.
- [`docs/BLACKOUT_BASIS.md`](docs/BLACKOUT_BASIS.md) — strategy spec, findings, current status.

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -q            # clock engine invariants
python3 scripts/blackout_stats.py      # structural facts (no network needed)
python3 scripts/probe_sources.py       # data kill-criterion test (needs open network)
```

**Deadline: 21 September 2026 (UTC+8).**
