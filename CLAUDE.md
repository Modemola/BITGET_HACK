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
python -m pytest -q                     # 74 tests
python -m blackout.build                # analytics -> web/data/desk.json
python scripts/build_page.py            # desk.json + template -> web/desk.html
python scripts/analyse_basis.py         # reproduce the research finding
python scripts/blackout_stats.py        # closure-window calendar structure
```

Refreshing market data (needs open network):

```bash
python scripts/probe_sources.py         # rToken hourly; rate-limited, resumable
python scripts/fetch_reference.py       # native equity, futures, crypto proxies
python scripts/fetch_events.py          # FOMC decisions, parsed from federalreserve.gov
```

## Layout

```
src/blackout/
  clock.py           closure regimes + time-to-reopen. Nothing else works without it.
  basis.py           fair value reconstruction, premium, leg decomposition
  distributions.py   drift by elapsed blackout hour
  exposure.py        positions -> per-regime exposure
  hedges.py          what still trades during a blackout, and whether it helps
  analogues.py       causal feature table + weighted kNN over past windows
  calendar_events.py scheduled events vs a closure window (FOMC, from the Fed)
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
- **Analogue features must be knowable at Friday 15:45.** Features and outcomes
  are built separately so lookahead cannot creep in; two tests enforce it. Note
  that reading the *previous* weekend's blackout is causal, not lookahead — the
  five-day window legitimately reaches back into it.
- **Label figures observed / estimated / targeted** — the submission form
  requires it and it is how the research reads as credible.
- **The page must work without the LLM.** `claude.use("sample")` returns `null`
  for a signed-out viewer, so every analytic renders statically and the language
  layer is an enhancement only.
- **Never inline a figure into the page or the payload by hand.** `verdict` was
  once transcribed literals; a data refresh would have left the product's
  central claim contradicting the numbers printed beside it. `test_build.py`
  now re-derives those four numbers and fails if they drift.
- **The payload must never carry NaN.** Python writes a bare `NaN` token, which
  `JSON.parse` rejects, which renders the page *entirely blank* with no error.
  `build._json_safe` maps non-finite values to null and both writers pass
  `allow_nan=False`. The page's formatters render null as an em dash.
- **Retrieval exists twice**, in `analogues.py` and again in JS on the page.
  `test_js_parity.py` extracts the real functions from the template and runs
  them under node against the shipped payload, requiring identical ordering and
  distances. Don't delete it; a drifted copy would not error, it would quietly
  show the wrong five weekends.

## Traps already hit — don't repeat them

- **pandas 2+ non-nanosecond units.** `pd.Timestamp("2026-09-11 12:00", tz=...)`
  infers *microsecond* resolution, so `.asi8` returns microseconds. Mixed against
  nanosecond calendar arrays it silently yields timestamps in 1970. `clock.py`
  pins everything through `_to_utc_index`.
- **GeckoTerminal caps a page at 1000 bars** and answers **401 as well as 429**
  under load. A single unpaginated page reads as "only 41 days of history exist"
  and an unspaced burst of searches fails every symbol. `probe_sources.py` has a
  global 3.5s limiter, backoff, and a resumable on-disk cache.
- **Windows defaults to cp1252, and it bites in two places.** Printed script
  output mangles em-dashes and arrows, so keep script output ASCII (the HTML
  page is UTF-8 and unaffected). And `subprocess.run(..., text=True)` decodes
  with the *locale* codec, so any test shelling out to node must pass
  `encoding="utf-8"` or non-ASCII output comes back corrupted and comparisons
  fail for reasons that look nothing like encoding.
- **The Claude Code web sandbox cannot reach any market data host** (403 at the
  proxy). Only GitHub and package registries resolve. Data is committed to the
  repo deliberately — that is how it travels between machines.
- **`data/` is force-listed in `.gitignore`** via negation rules so CSVs commit
  normally. Don't "tidy" that up.
- **`ClosureClock.annotate` labels out-of-range timestamps `WEEKNIGHT`** rather
  than flagging them, so anything comparing events against the calendar must
  first restrict to the span the clock was built over. The page's JS clock does
  report out-of-range correctly (`currentRun` returns null).
- **The Fed's FOMC page carries each meeting twice** — a statement link with the
  exact date for past meetings, and a month plus day range for future ones. Only
  the range exists for the meetings that matter, and straddling meetings use
  abbreviated months (`Jan/Feb`). `fetch_events.py` parses ranges for all of
  them and cross-checks against the statement dates, so past meetings validate
  the parser the future ones depend on.

## Open items

- All seven tools are built.
- The event calendar covers FOMC only. Anything added must come from its issuing
  authority; a scraped aggregator has no place in a tool whose argument is that
  its numbers are checkable.
- Bitget API DNS fails on the operator's machine, blocking Agent Hub /
  `bitget-signal` Skills integration (a scoring item — stretch goal).
- The artifact is **private by default**; it must be shared from the page's
  share menu before judges can open it.
