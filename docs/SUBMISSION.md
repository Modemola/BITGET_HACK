# Submission — Blackout Desk

Everything below is written to be pasted into the Google Form. Field names match
the form exactly. Figures are labelled **observed**, **estimated** or **targeted**
as the form requires; anything unlabelled is observed.

- **Track → Sub-theme:** 🟧 AI Trading Desk → Decision Stress Testing
- **Project name:** Blackout Desk
- **Submission Materials Link:** see Part 5
- **Apply for Demo Day:** Yes
- **Apply for K3 Token Subsidy:** Yes
- **University Name:** *(fill if applicable — see Chapter II; note it is mutually
  exclusive with main-track prizes)*

---

## Project Description

### Part 1 · Thesis

**The pain point.** Tokenized US stocks trade 7×24, but the market that prices
them does not. For **49 hours every weekend** — Friday 17:00 ET, when CME Globex
closes, to Sunday 18:00 ET, when it reopens — an rToken is the only venue on
earth quoting US equity exposure. No cash market, no futures, no options, no
authorised participant able to hedge. A trader holding NVDAx into Friday's close
is carrying an unhedgeable position through a third of the week with no
reference price, and goes to sleep with no framework for what that costs them.

Every tool a retail trader can reach was built for a market with an opening
bell. Portfolio trackers show a stale last price. Risk calculators assume you
can trade out. Nothing reasons in terms of *closure windows* at all, because
until rToken existed the concept had no product surface.

**The hypothesis we started with, and why we abandoned it.** We began building a
strategy, not a tool. The premise was obvious: a thin, retail-dominated venue
trading alone for 49 hours must misprice, and that mispricing must be
harvestable. Across 210 days of hourly data the premium does behave exactly as
predicted — dispersion widens monotonically from **0.42%** in the cash session
to **0.51%** overnight to **0.70%** in a blackout, and the AR(1) half-life
stretches from 0.2h to 1.0h to 6.0h as venues shut. Divergence accumulates ~6×
across a weekend, and across 27 weekends the gap converged at the reopen **85%**
of the time.

None of it is tradeable. Decomposing that convergence into its two legs shows
**87–92% of it happens because fair value catches up to the token, not because
the token corrects.** The reference was stale; the token was already right. The
leg you can actually trade returns a **48.1%** hit rate — a coin flip — and
**−0.009%** per weekend after 10bp of costs. We tested four variants (fade the
blackout premium, follow the drift on futures, fade the weeknight premium at
three z-thresholds) and every one agrees. Signals got *worse* at stronger
thresholds, which is what noise does and a real edge never does.

**The thesis that replaced it.** The closure-window premium is **an information
lead, not a mispricing**. The 7×24 venue everyone assumes is inefficient is, at
hourly resolution, pricing weekend information correctly — while the reference
that looks authoritative is simply asleep.

That inverts the product. A trader who sees a 1% weekend premium and reads it as
free money will lose to fees, quietly and repeatedly. **Blackout Desk exists to
stop that trade and to price the risk they are actually carrying instead.** A
tool that prevents a losing trade is worth more than one that invents a winning
one, and we can prove this particular trade loses. No competing entry can make
that argument, because nobody else has run the decomposition.

### Part 2 · Target user and product value

**Not "all traders".** Specifically: **self-directed retail and semi-professional
traders holding $10k–$500k of tokenized US equity exposure across weekends.**

| Attribute | Value |
|---|---|
| Segment | Retail / semi-pro (below VIP; no desk, no risk system, no prime broker) |
| Capital | $10k–$500k in a single name or a handful |
| Frequency | Low — position-holders, days to weeks, not intraday |
| Primary market | Tokenized US equities (xStocks on Solana; Ondo and other issuers by extension), often alongside a crypto book |
| Risk appetite | Directional, concentrated, willing to hold overnight and over weekends |
| Use case | Friday afternoon: decide whether to hold, trim or hedge into the closure window |

**Why this segment specifically.** Capital small enough that thin rToken books
are not a binding constraint — a $2.1M NVDAx pool can absorb them, where it
cannot absorb an institution. Large enough that the observed **0.84% mean** and
**2.14% worst** weekend divergence is real money: on $250k that is $2,100 typical
and $5,350 at the observed worst. And crucially, this is the segment with **no
risk infrastructure at all** — an institution already models closure risk; a
retail holder has literally nothing, and the tools they can reach do not even
represent the concept.

**The value.** Three things no existing tool gives them: an honest distribution
of what the window has historically done rather than a point forecast; the
verdict that the premium is not an arbitrage, with the decomposition behind it;
and a hedge menu that tells them the truth, which is that **every available
hedge is unstable** and two of the three cost more than they are worth.

### Part 3 · Validation data and key metrics

**Research validation (observed).** 4,607 hourly bars, 2026-03-01 → 2026-09-10,
NVDAx and TSLAx (xStocks, Solana) joined to NVDA/TSLA native equity, NQ/ES index
futures and BTC/ETH. 99% hourly coverage, 0% stale bars, no outliers beyond ±5%,
no nulls. Reproduce with `python scripts/analyse_basis.py`.

| Metric | Value | Label |
|---|---|---|
| Weekend blackouts analysed | 27 | observed |
| Premium dispersion, cash / weeknight / blackout | 0.42% / 0.51% / 0.70% | observed |
| AR(1) half-life, cash / weeknight / blackout | 0.2h / 1.0h / 6.0h | observed |
| Mean absolute terminal drift | 0.84% | observed |
| p95 / worst terminal drift | 1.95% / 2.14% | observed |
| Weekends ending beyond ±1% | 37% | observed |
| Closure attributable to the token leg (1h/6h/12h) | 6% / 27% / 13% | observed |
| Hit rate fading the premium | 48.1% | observed |
| Net per weekend at 10bp round-trip | −0.009% | observed |
| Scheduled rate decisions inside a blackout | 0 of 22, across 134 windows | observed |
| BTC hedge: correlation / variance removed | +0.71 / 29% | observed |
| BTC hedge: rolling correlation range | −0.51 to +0.89, sign-flipping | observed |

**Stated limitations.** The honest sample is **27 weekends** — thin, and reported
beside every distribution on the page rather than hidden behind an hourly bar
count that would look ten times larger. Hourly resolution says nothing about
sub-hourly microstructure. One issuer family (xStocks on Solana) and two names.
Cost assumptions are modelled, not executed.

**Product validation — not yet done, and stated as such.** Zero test users to
date. The build has run to a working demo faster than to a user study, and we
will not report a usage figure we have not measured.

The plan, in order:

1. **Task completion (targeted).** Five holders of tokenized equity, given one
   task — "you are long $250k NVDAx into this weekend; decide hold, trim or
   hedge, and justify it" — with no guidance. Target: 4 of 5 reach a justified
   decision unaided in under 5 minutes.
2. **Decision change (targeted).** The metric that matters for this product is
   not engagement, it is *prevented trades*. Ask each user, before and after,
   whether they would trade against a 1% weekend premium. Target: a majority who
   said yes beforehand say no after, and can state why.
3. **Retention proxy (targeted).** Returning on a subsequent Friday without a
   prompt. Target: 3 of 5 return within two weekends.

**How we would prove distribution.** The page is a URL with no install, no key
and no account, so distribution is measurable directly: unique openers per
Friday, share returning the following Friday, and questions asked of the
language layer per session. We would report those as observed once they exist,
and until then they are targets, not claims.

### Part 4 · Progress

**Built and working.** All seven tools, each load-bearing rather than decorative:

1. `closure_window` — regime and time-to-reopen, from the XNYS and CMES exchange calendars
2. `exposure` — a position split by regime across its holding period
3. `divergence_distribution` — drift by elapsed blackout hour, with quantile bands
4. `historical_analogues` — causal-feature kNN over past windows
5. `premium_verdict` — the decomposition, and the reason not to trade
6. `hedge_menu` — what still trades, with stability, not just average correlation
7. `macro_calendar` — scheduled events versus the window, from federalreserve.gov

Plus: a live demo with a genuine real-time clock, a static-first page that works
without the LLM, a reproducible research pipeline, and **74 tests**.

**Not built.** Live price feeds — analytics are stamped and frozen at build time,
and the page says so rather than implying live prices. Bitget Agent Hub and
`bitget-signal` Skills integration is blocked (below). Only one issuer family.

**Problems hit, and the fixes.** These are worth stating because each one would
have shipped silently:

- **Our own strategy was falsified by our own test.** The 85% convergence figure
  looked like an edge until we decomposed it. We built the test that killed it
  rather than the backtest that would have flattered it.
- **The payload could have rendered the page entirely blank.** Python writes
  non-finite floats as a bare `NaN` token, which `JSON.parse` rejects — and the
  payload is inlined, so one NaN kills the whole document with no visible error.
  Non-finite values are now mapped to null and both writers use `allow_nan=False`.
- **The page's headline numbers were hardcoded.** Four literals transcribed from
  an ad-hoc analysis; correct at the time, but a data refresh would have left the
  central claim contradicting the figures printed beside it. Now derived, with a
  test that re-derives them and fails on drift.
- **The retrieval algorithm exists twice**, in Python and in JS on the page. A
  drifted copy would not error — it would show a trader the wrong five weekends.
  A test extracts the real functions from the template and runs them under Node
  against the shipped payload, requiring identical ordering and distances.
- **The FOMC parser silently dropped two meetings** because month-straddling rows
  use abbreviations (`Jan/Feb`). Caught only because past meetings are
  cross-checked against published statement dates — the check that validates the
  parser the future meetings depend on.

**Next steps.** User testing per Part 3. Sub-hourly data to test whether the
efficiency finding survives at finer resolution. More issuers, to test whether
it is a property of xStocks or of tokenized equity generally.

**Stack.** Python 3.11+ (pandas, numpy, `exchange_calendars`), no framework.
Data: GeckoTerminal (Solana on-chain OHLCV), Yahoo Finance (native equity,
index futures, crypto), federalreserve.gov (FOMC). Front end: hand-written
HTML/CSS/JS, no build step, no dependencies. Hosting: Claude Artifacts, using
the `sample` runtime capability for the language layer.

### Part 5 · Deliverables

Everything is in the repository linked as **Submission Materials**:

| Deliverable | Where |
|---|---|
| **Accessible demo** (required) | https://claude.ai/code/artifact/15681462-d2cf-4c1c-afba-733d723bd461 |
| **Complete research task** (required) | `docs/RESEARCH_TASK.md` — question to actionable insight, end to end |
| Research finding and every variant tested | `docs/FINDINGS.md` |
| Reproduce the finding from raw data | `scripts/analyse_basis.py` |
| System design and tool contract | `docs/ARCHITECTURE.md` |
| Analytics engine | `src/blackout/` |
| Test suite (74) | `tests/` |
| Raw data (9 series, committed) | `data/raw/` |
| Data ingestion, rate-limited and resumable | `scripts/probe_sources.py`, `fetch_reference.py`, `fetch_events.py` |

### Part 6 · Our take on AI Trading

The most useful thing AI did on this project was **kill our idea**. We set out to
build an arbitrage strategy and spent the effort instead on a test designed to
falsify it — the leg decomposition — which showed the convergence we were
excited about happened on the leg we could not trade. Four further variants
agreed. That result is worth more than the strategy would have been, and it
became the product.

We think that is the underrated use of AI in trading. The bottleneck for a
retail trader is not idea generation; it is that ideas are cheap and honest
falsification is expensive. Everything about a backtest wants to flatter you.
The discipline worth automating is the one that argues with you — pre-registered
holdouts, decomposition before belief, sample sizes reported next to the
statistic rather than buried.

The 7×24 framing of S2 is also sharper than it first appears. The interesting
thing about tokenized equities is not that they trade more hours. It is that
they create windows where **one venue prices an asset alone**, and those windows
are where the assumptions every retail tool is built on quietly stop holding.

---

## Role of the LLM in Your Project

**Models used:** Claude Opus 5, via Claude Code, throughout. No Qwen credits were
received or used, so there is nothing to report on that.

**What the model actually did.** Three distinct roles, in order of how much they
mattered:

**1. Research partner, including adversarially.** The model wrote the analysis
that falsified our own strategy. The decisive step — decomposing premium closure
into the token leg and the fair-value leg — was not in the original plan; it came
from asking what would have to be true for the 85% convergence figure to be
misleading. It also caught that the τ framing in our spec was backwards
(correlation −0.409), that the first probe's NO-GO verdict was a false negative
caused by our own pagination, and that a causality test was passing vacuously
because the corruption it applied cancelled out of the metric it checked.

**2. Engineering.** The analytics engine, the ingestion pipeline, the page, and
all 74 tests. Notably the tests that guard the things a human reviewer would not
think to check: that the payload cannot ship a NaN, that the page's JavaScript
retrieval returns identical results to the Python it duplicates, that the
headline figures are derived rather than transcribed.

**3. In the product itself, at runtime.** The published page uses the Claude
`sample` capability so a trader can ask questions in natural language and get
answers grounded strictly in the measurements on the page — with an instruction
never to describe the weekend premium as an arbitrage, because that is the exact
error the product exists to prevent. The page is deliberately built static-first:
the language layer is an enhancement, and every analytic renders without it.

---

## X Promotional Post

Must include `#BitgetHackathon` and `@Bitget_AI`, and retweet the official post.

> We spent a week trying to arbitrage tokenized US stocks across the 49-hour
> weekend blackout, when rToken is the only venue on earth quoting US equity.
>
> The trade doesn't exist. 87–92% of the convergence happens because the
> *reference* catches up — not because the token corrects. Fading it is a 48%
> coin flip that dies at 10bp costs.
>
> So we built the tool that tells you that instead. Blackout Desk: what you're
> actually exposed to across the hours nobody is watching.
>
> #BitgetHackathon @Bitget_AI
