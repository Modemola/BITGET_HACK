# Blackout Desk

Entry for the **Bitget AI Base Camp Hackathon S2**, 🟧 AI Trading Desk track,
Decision Stress Testing sub-theme. **Deadline: 21 September 2026 (UTC+8).**

A closure-window risk desk for traders holding tokenized US stocks (rToken).
Full design in `docs/ARCHITECTURE.md`; competition rules in `docs/S2_BRIEF.md`.

**Live demo:** https://claude.ai/code/artifact/15681462-d2cf-4c1c-afba-733d723bd461
Republish by rebuilding and calling the Artifact tool on `web/desk.html` — same
path keeps the same URL.

## The finding everything rests on

Across 210 days of hourly rToken data, the closure-window premium is **not a
mispricing — it is an information lead**. When the reference reopens, 87–92% of
the gap closes because fair value catches up to the token, not because the token
corrects. Fading it is a 48–52% coin flip that dies at 10bp costs.

This was measured, not assumed, and it falsified our original strategy. Four
variants were tested and all agree (`docs/FINDINGS.md`). The product's job is to
tell a trader that the premium they are looking at is not free money.

**Never describe the weekend premium as an arbitrage opportunity** in code
comments, copy, or the page. That is the specific error the product exists to
prevent.

## Commands

```bash
pip install -e ".[dev]"                 # editable install; no sys.path hacks needed
python -m pytest -q                     # 30 tests
python -m blackout.build                # analytics -> web/data/desk.json
python scripts/build_page.py            # desk.json + template -> web/desk.html
python scripts/analyse_basis.py         # reproduce the research finding
python scripts/blackout_stats.py        # closure-window calendar structure
```

Refreshing market data (needs open network):

```bash
python scripts/probe_sources.py         # rToken hourly; rate-limited, resumable
python scripts/fetch_reference.py       # native equity, futures, crypto proxies
```

## Layout

```
src/blackout/
  clock.py           closure regimes + time-to-reopen. Nothing else works without it.
  basis.py           fair value reconstruction, premium, leg decomposition
  distributions.py   drift by elapsed blackout hour
  exposure.py        positions -> per-regime exposure
  hedges.py          what still trades during a blackout, and whether it helps
  analogues.py       NOT BUILT - nearest-neighbour retrieval over past windows
  calendar_events.py macro events in a window (needs data/macro_events.csv)
  build.py           precompute -> web/data/desk.json
web/
  desk.template.html page source, with a __DESK_JSON__ placeholder
  desk.html          GENERATED - never hand-edit, rebuild instead
```

## Conventions

- **Every number traces to raw data.** Nothing appears on the page that
  `scripts/analyse_basis.py` cannot reproduce.
- **Report `n_windows`, not `n`.** 158 hourly bars from one weekend are not 158
  independent observations. The honest sample is 27 weekends, and it is stated
  beside every distribution.
- **Unbuilt modules raise, never return placeholder data.** A fabricated number
  in a risk tool is worse than a missing one.
- **Label figures observed / estimated / targeted** — the submission form
  requires it and it is how the research reads as credible.
- **The page must work without the LLM.** `claude.use("sample")` returns `null`
  for a signed-out viewer, so every analytic renders statically and the language
  layer is an enhancement only.

## Traps already hit — don't repeat them

- **pandas 2+ non-nanosecond units.** `pd.Timestamp("2026-09-11 12:00", tz=...)`
  infers *microsecond* resolution, so `.asi8` returns microseconds. Mixed against
  nanosecond calendar arrays it silently yields timestamps in 1970. `clock.py`
  pins everything through `_to_utc_index`.
- **GeckoTerminal caps a page at 1000 bars** and answers **401 as well as 429**
  under load. A single unpaginated page reads as "only 41 days of history exist"
  and an unspaced burst of searches fails every symbol. `probe_sources.py` has a
  global 3.5s limiter, backoff, and a resumable on-disk cache.
- **Windows console is cp1252.** Em-dashes and arrows in printed strings render
  as `?`. Keep script output ASCII; the HTML page is UTF-8 and unaffected.
- **The Claude Code web sandbox cannot reach any market data host** (403 at the
  proxy). Only GitHub and package registries resolve. Data is committed to the
  repo deliberately — that is how it travels between machines.
- **`data/` is force-listed in `.gitignore`** via negation rules so CSVs commit
  normally. Don't "tidy" that up.

## Open items

- `analogues.py` and `calendar_events.py` are scaffolded but unbuilt.
- No macro calendar source; `data/macro_events.csv` does not exist yet.
- Bitget API DNS fails on the operator's machine, blocking Agent Hub /
  `bitget-signal` Skills integration (a scoring item — stretch goal).
- The artifact is **private by default**; it must be shared from the page's
  share menu before judges can open it.
