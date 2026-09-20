# Blackout Desk — architecture

**Track:** 🟧 AI Trading Desk · **Sub-theme:** Decision Stress Testing
**Deadline:** 21 September 2026 (UTC+8)

---

## 1. What we are building

It is Friday, 15:45 in New York. A trader holds tokenized US stock exposure.
In fifteen minutes NYSE closes; in seventy-five, CME Globex follows. For the
next **49 hours** their position is quoted by exactly one venue on earth, they
cannot watch it, and no institutional arbitrageur is standing behind the price.

Blackout Desk answers, in natural language, the question no existing tool
answers: **what am I actually exposed to across the closure window, and what
should I do about it before it starts?**

### The thesis, and why it is not the obvious one

Our own research (`docs/FINDINGS.md`) falsified the intuitive read. Across 197
days of hourly rToken data we found the closure-window premium is **not a
mispricing** — it is an information lead. When the reference reopens, 78–98% of
the gap closes because fair value catches up to the token, not because the
token corrects. Trading against it is a coin flip that dies at 10bp costs.

That single finding is the product's spine. Every competing tool that notices a
1% weekend premium will call it an arbitrage opportunity. Blackout Desk tells
the trader it is information, shows the evidence, and stops them making the
trade. **A tool that prevents a losing trade is worth more than one that
invents a winning one**, and we can prove this one with data nobody else has run.

### Target user

Not "all traders". Specifically: **self-directed retail and semi-pro traders
holding $10k–$500k of tokenized US equity exposure across weekends**, trading on
Bitget or an on-chain venue, with no desk, no risk system, and no framework for
closure-window risk. Capital small enough that the thin rToken books are not a
constraint, large enough that a 1% weekend gap is real money.

---

## 2. System architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  L5  EVIDENCE          docs/FINDINGS.md · scripts/analyse_basis.py │
│      Every number the desk states is reproducible from raw data.   │
└───────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────┐
│  L4  INTERFACE         web/desk.html → published Artifact          │
│      • static analytics ALWAYS render (no LLM required)            │
│      • LUI layer via `sample` capability + page-defined tools      │
└───────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────┐
│  L3  TOOL LAYER        src/blackout/tools.py  (typed, 7 tools)     │
│      One contract, two bindings: Python for CLI/MCP, mirrored in   │
│      JS inside the page for the in-artifact agent.                 │
└───────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────┐
│  L2  ANALYTICS         exposure · distributions · analogues ·      │
│                        hedges · calendar_events                    │
└───────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────┐
│  L1  DATA SPINE        clock.py · basis.py · data/raw/*.csv        │
│      Built and tested. 4,702 usable hourly bars, 99% coverage.     │
└───────────────────────────────────────────────────────────────────┘
```

Build step: `python -m blackout.build` runs L1→L2 over the raw CSVs and emits a
single precomputed `web/data/desk.json`, which is inlined into `desk.html` at
publish time. The page therefore needs no backend, no API key and no network.

### Why there are two demos

The track requires an **accessible Demo**, and accessible is the operative word.
The primary demo is therefore a plain Vercel URL — no account, no consent
prompt, no sharing step: https://blackout-desk-eight.vercel.app. A second build
runs as a Claude Artifact, where the `sample` capability supplies the language
interface and tool use, so the workbench is conversational rather than a static
dashboard.

Both come from one template via `python scripts/build_page.py`, which is what
keeps them from diverging; `docs/DEPLOY.md` explains why one is a document and
the other a fragment.

**Designed for absence.** `claude.use("sample")` returns `null` when the viewer
is not signed in or declines consent. Every analytic must therefore render
statically without it: the LUI is an enhancement, never the load-bearing path.
A judge who never touches the chat still sees the full research product — which
is also the answer to the `sample` layer being unavailable to them, since no
screen capture of the conversational flow was recorded.

---

## 3. The tool contract

Seven tools, each answering one research question. This *is* the "feature depth
/ integration count" the track scores, so each must be load-bearing rather than
decorative.

| # | Tool | Question it answers |
|---|---|---|
| 1 | `closure_window(as_of)` | Which regime am I in, when does each venue reopen, how many blackout hours are ahead? |
| 2 | `exposure(positions, as_of)` | What is my book worth per regime, and what is unhedgeable? |
| 3 | `divergence_distribution(symbol, elapsed_h)` | How far does price typically drift by hour *H* of a blackout? |
| 4 | `historical_analogues(symbol, conditions, k)` | Which past weekends looked like this one, and how did they resolve? |
| 5 | `premium_verdict(symbol, as_of)` | Is the current premium tradeable? *(Almost always: no — with evidence.)* |
| 6 | `hedge_menu(exposure)` | What can I actually trade during the blackout, and what does it cost? |
| 7 | `macro_calendar(window)` | What is scheduled between now and the reopen? |

All seven are built and pinned against the shipped payload by `test_tools.py`.
Tools 3, 4 and 5 are backed by our own measured data and are the ones no other
entry can produce. Tool 5 is the thesis in executable form.

### The demo research task (a required deliverable)

> *"I'm long $250k of NVDAx into this weekend. What am I exposed to, and should
> I hedge?"*

Flows through 1 → 2 → 7 → 3 → 4 → 5 → 6 and ends on a numeric recommendation
with a stated confidence and an explicit "here is what would change my answer".
Question to actionable insight, in one pass.

---

## 4. Repository layout

```
src/blackout/
  clock.py              ✅ closure regimes + time-to-reopen
  basis.py              ✅ fair value, premium, leg decomposition
  exposure.py           ✅ positions → per-regime exposure
  distributions.py      ✅ empirical drift by elapsed blackout hour
  analogues.py          ✅ nearest-neighbour retrieval over past windows
  hedges.py             ✅ instruments live during blackout + cost model
  calendar_events.py    ✅ macro events inside a window
  tools.py              ✅ the 7 tools behind one contract; Desk + TOOLS registry
  build.py              ✅ L1+L2 → web/data/desk.json
web/
  desk.template.html    ✅ page source (static + LUI)
  desk.html             ✅ generated; published as the live demo
  data/desk.json        ✅ generated; never hand-edited
scripts/
  probe_sources.py      ✅ rToken ingestion, rate-limited, resumable
  fetch_reference.py    ✅ native equity + index futures + crypto proxies
  fetch_events.py       ✅ FOMC decisions, parsed from federalreserve.gov
  fetch_bitget.py       ✅ the same rTokens from Bitget's own spot market
  analyse_basis.py      ✅ reproduces the research finding
  cross_venue.py        ✅ re-runs the decisive test on both venues
  blackout_stats.py     ✅ calendar structure
  research_task.py      ✅ the required demo task, all 7 tools end to end
  build_page.py         ✅ payload + template → both deployed builds
  make_images.py        ✅ the mark → share card + touch icon
  figures.py            ✅ canonical figures, stable and diffable
docs/
  FINDINGS.md           ✅ the research result, and the cross-venue check
  ARCHITECTURE.md       ✅ this file
  FRONTEND.md           ✅ the visual architecture
  DEPLOY.md             ✅ the two builds and why they differ
  RESEARCH_TASK.md      ✅ generated; the required deliverable
  BLACKOUT_BASIS.md     ✅ the original strategy spec, kept as the record
  S2_BRIEF.md           ✅ competition rules
  SUBMISSION.md         ✅ the six-part project description
```

---

## 5. Known gaps

| Gap | Impact | Plan |
|---|---|---|
| ~~No BTC/ETH data~~ | Resolved 10 Sep. BTC correlates +0.66 with NVDAx across blackouts and removes 25% of variance, but the rolling correlation spans −0.51 to +0.89 and changes sign, so `hedges.py` reports every candidate as unstable | Done |
| ~~No macro calendar source~~ | Resolved 10 Sep. FOMC decisions parsed from federalreserve.gov, cross-validated against published statement dates. Across 134 weekend blackouts, **none of the 22 scheduled decisions has ever fallen inside one** — weekend risk is unscheduled risk, now a measurement rather than an assertion | Done |
| **`sample` may be unavailable to a judge** | LUI silent | Static-first design + screen recording |
| **28 weekends is a thin sample** | Distributions are wide | State it on the page beside every figure rather than hiding it |
| ~~Bitget DNS fails on the operator's machine~~ | Diagnosed 15 Sep: the block is DNS alone. Every Bitget domain fails to resolve locally while resolving fine through a public resolver, and a direct TLS connection to the resolved address returns `200 OK`. `fetch_bitget.py` carries a DoH fallback so it works either way | Done |
| **Agent Hub / `bitget-signal` Skills not integrated** | A scoring item left on the table | Unblocked by the DNS diagnosis but not built; stated rather than implied |
| **Longer horizons do not replicate cross-venue** | +6h and +12h move by tens of points between venues and between samples | Only 13 weekends overlap the two venues. `docs/FINDINGS.md` reports the +1h agreement and says plainly that the rest is sample noise |
| **No user testing** | Part 3's product metrics are unobserved | Labelled `targeted` throughout; no usage number is reported that was not measured |

---

## 6. What shipped, against the plan

Written as a plan to 21 September; kept as the record of what the plan survived.

| Day | Planned | What happened |
|---|---|---|
| **10 Sep** | Architecture, scaffold, hedges, build pipeline, live demo URL | Done. Demo gate cleared 6 days early |
| 11–12 Sep | L2 analytics: distributions, analogues, exposure | Done |
| 12 Sep | Reference data: BTC/ETH landed | Done, via `fetch_reference.py` (planned under the name `fetch_hedges.py`) |
| 13–14 Sep | `tools.py` + `build.py` → `desk.json` | `build.py` done. `tools.py` was assumed built and was not — the seven-tool contract the architecture promised had no single entry point until the 15 Sep sweep found it missing |
| 15–16 Sep | Analogues + macro calendar | Done. FOMC parsed from the Fed, cross-validated against statement dates |
| 17–18 Sep | LUI layer: `sample` + tool bindings | Done, static-first: every analytic renders for a signed-out viewer |
| 19 Sep | Polish, mobile, screen recording | Visual layer rebuilt over several passes; screen recording **not done** |
| 20 Sep | `SUBMISSION.md`, form dry run | Submission written; cross-venue replication added and its figures corrected |
| **21 Sep** | Submit | Buffer day, as planned |

Two things landed that were not in the plan at all. The leg decomposition
falsified the strategy the plan was written around, which is why this document
describes a risk desk rather than a trading system. And the finding was
re-measured on Bitget's own book (`scripts/cross_venue.py`), which confirmed the
+1h result on a second venue and bounded what the longer horizons can claim.

**Hard rule, met:** a judge-accessible URL existed by 16 Sep. An accessible demo
is a validity gate — a polished local build that judges cannot open scores zero.

---

## 7. Design principles

1. **Every number traces to raw data.** No figure appears on the page that
   `scripts/analyse_basis.py` cannot reproduce.
2. **Label observed / estimated / targeted**, as the submission form demands.
3. **State the sample size next to the statistic.** 28 weekends is thin; saying
   so is credibility, hiding it is the thing judges are trained to catch.
4. **The page works without the LLM.** Degrade per capability, never fail.
5. **Prevented losses count.** The product's headline value is talking a trader
   out of a bad trade, and we can prove that trade is bad.
