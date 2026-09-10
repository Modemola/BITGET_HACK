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

Our own research (`docs/FINDINGS.md`) falsified the intuitive read. Across 210
days of hourly rToken data we found the closure-window premium is **not a
mispricing** — it is an information lead. When the reference reopens, 87–92% of
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
│      Built and tested. 4,607 usable hourly bars, 99% coverage.     │
└───────────────────────────────────────────────────────────────────┘
```

Build step: `python -m blackout.build` runs L1→L2 over the raw CSVs and emits a
single precomputed `web/data/desk.json`, which is inlined into `desk.html` at
publish time. The page therefore needs no backend, no API key and no network.

### Why the demo is an Artifact

The track requires an **accessible Demo**. An Artifact gives a judge a URL that
works immediately — no deployment, no cold start, no credentials. The `sample`
capability supplies the language interface, including tool use, so the workbench
is genuinely conversational rather than a static dashboard.

**Designed for absence.** `claude.use("sample")` returns `null` when the viewer
is not signed in or declines consent. Every analytic must therefore render
statically without it: the LUI is an enhancement, never the load-bearing path.
A judge who never touches the chat still sees the full research product. We also
record a screen capture of the conversational flow as a backup deliverable.

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
| 4 | `historical_analogues(symbol, conditions, k)` | Which past weekends looked like this one, and how did they resolve? ✅ |
| 5 | `premium_verdict(symbol, as_of)` | Is the current premium tradeable? *(Almost always: no — with evidence.)* |
| 6 | `hedge_menu(exposure)` | What can I actually trade during the blackout, and what does it cost? |
| 7 | `macro_calendar(window)` | What is scheduled between now and the reopen? ✅ |

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
  clock.py              ✅ closure regimes + time-to-reopen        (8 tests)
  basis.py              ✅ fair value, premium, leg decomposition
  exposure.py           ▢  positions → per-regime exposure
  distributions.py      ▢  empirical drift by elapsed blackout hour
  analogues.py          ✅ nearest-neighbour retrieval over past windows
  hedges.py             ✅ instruments live during blackout + cost model
  calendar_events.py    ✅ macro events inside a window
  tools.py              ▢  the 7 typed tools; single source of truth
  build.py              ✅ L1+L2 → web/data/desk.json
web/
  desk.template.html    ✅ page source (static + LUI)
  desk.html             ✅ generated; published as the live demo
  data/desk.json        ▢  generated; never hand-edited
scripts/
  probe_sources.py      ✅ rToken ingestion, rate-limited, resumable
  fetch_reference.py    ✅ native equity + index futures
  analyse_basis.py      ✅ reproduces the research finding
  blackout_stats.py     ✅ calendar structure
docs/
  FINDINGS.md           ✅ the research result
  ARCHITECTURE.md       ✅ this file
  S2_BRIEF.md           ✅ competition rules
  SUBMISSION.md         ▢  the six-part project description
```

---

## 5. Known gaps

| Gap | Impact | Plan |
|---|---|---|
| ~~No BTC/ETH data~~ | Resolved 10 Sep. BTC correlates +0.71 with NVDAx across blackouts and removes 29% of variance, but the rolling correlation spans −0.51 to +0.89 and changes sign, so `hedges.py` reports every candidate as unstable | Done |
| ~~No macro calendar source~~ | Resolved 10 Sep. FOMC decisions parsed from federalreserve.gov, cross-validated against published statement dates. Across 134 weekend blackouts, **none of the 22 scheduled decisions has ever fallen inside one** — weekend risk is unscheduled risk, now a measurement rather than an assertion | Done |
| **`sample` may be unavailable to a judge** | LUI silent | Static-first design + screen recording |
| **27 weekends is a thin sample** | Distributions are wide | State it on the page beside every figure rather than hiding it |
| **Bitget DNS fails on the operator's machine** | Blocks Agent Hub / bitget-signal integration | Diagnose separately; treat Skills integration as a stretch goal |

---

## 6. Plan to 21 September

| Day | Milestone | Gate |
|---|---|---|
| **10 Sep** | ✅ Architecture, scaffold, hedges, build pipeline, **live demo URL** | Demo gate cleared 6 days early |
| 11–12 Sep | L2 analytics: distributions, analogues, exposure | Tests green on each |
| 12 Sep | `fetch_hedges.py` run; BTC/ETH landed | Needs one operator run |
| 13–14 Sep | `tools.py` + `build.py` → `desk.json` | 7 tools callable from Python |
| 15–16 Sep | ~~Artifact v1~~ done 10 Sep — use this slot for analogues + macro calendar | Judge-accessible URL exists |
| 17–18 Sep | LUI layer: `sample` + tool bindings | Demo task runs end to end |
| 19 Sep | Polish, mobile, screen recording | |
| 20 Sep | `SUBMISSION.md`, form dry run | |
| **21 Sep** | Submit (buffer day) | |

**Hard rule:** a judge-accessible URL must exist by 16 Sep, even if thin. An
accessible demo is a validity gate — a polished local build that judges cannot
open scores zero.

---

## 7. Design principles

1. **Every number traces to raw data.** No figure appears on the page that
   `scripts/analyse_basis.py` cannot reproduce.
2. **Label observed / estimated / targeted**, as the submission form demands.
3. **State the sample size next to the statistic.** 27 weekends is thin; saying
   so is credibility, hiding it is the thing judges are trained to catch.
4. **The page works without the LLM.** Degrade per capability, never fail.
5. **Prevented losses count.** The product's headline value is talking a trader
   out of a bad trade, and we can prove that trade is bad.
