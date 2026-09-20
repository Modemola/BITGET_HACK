# Blackout Desk

Entry for the **Bitget AI Base Camp Hackathon S2**, 🟧 AI Trading Desk track,
Decision Stress Testing sub-theme. **Deadline: 21 September 2026 (UTC+8).**

A closure-window risk desk for traders holding tokenized US stocks (rToken).
Full design in `docs/ARCHITECTURE.md`; competition rules in `docs/S2_BRIEF.md`.

**Two deployments, see `docs/DEPLOY.md`.** `python scripts/build_page.py` emits
both from one template:

- `public/index.html` — a complete document for Vercel. The public demo: a plain
  URL, no account, no sharing step. **https://blackout-desk-eight.vercel.app**,
  built from `main` — Vercel deploys the production branch, so work must reach
  `main` to go live.
- `web/desk.html` — a **fragment** for the Claude artifact, which supplies its
  own doctype, charset and viewport. Carries the natural-language layer.
  https://claude.ai/artifact/3eKJskZZThj72zRwZjBpK2 —
  republish by calling the Artifact tool on that same path.

Never give the artifact build a document shell, and never ship the fragment to a
static host: no charset breaks every em-dash, no viewport breaks every
responsive rule. `tests/test_deploy.py` pins both.

## The finding everything rests on

Across 197 days of hourly rToken data, the closure-window premium is **not a
mispricing — it is an information lead**. When the reference reopens, 78–98% of
the gap closes because fair value catches up to the token, not because the token
corrects. Fading it is a 46% coin flip that dies at 10bp costs.

This was measured, not assumed, and it falsified our original strategy. Four
variants were tested and all agree (`docs/FINDINGS.md`). The product's job is to
tell a trader that the premium they are looking at is not free money.

**Never describe the weekend premium as an arbitrage opportunity** in code
comments, copy, or the page. That is the specific error the product exists to
prevent.

## Commands

```bash
pip install -e ".[dev]"                 # editable install; no sys.path hacks needed
python -m pytest -q                     # 196 tests
python -m blackout.build                # analytics -> web/data/desk.json
python scripts/build_page.py            # desk.json + template -> web/desk.html
python scripts/analyse_basis.py         # reproduce the research finding
python scripts/blackout_stats.py        # closure-window calendar structure
python scripts/research_task.py         # the required demo task, all 7 tools end to end
python scripts/cross_venue.py           # the same test on Bitget's book vs Solana's
python -m blackout.tools                # list the seven tools; add a name to run one
```

Refreshing market data (needs open network):

```bash
python scripts/probe_sources.py         # rToken hourly; rate-limited, resumable
python scripts/fetch_reference.py       # native equity, futures, crypto proxies
python scripts/fetch_events.py          # FOMC decisions, parsed from federalreserve.gov
python scripts/fetch_bitget.py          # rToken candles from Bitget's own spot market
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
  tools.py           the 7 tools behind one contract: Desk + TOOLS registry
  build.py           precompute -> web/data/desk.json
web/
  desk.template.html page source, with a __DESK_JSON__ placeholder
  desk.html          GENERATED - never hand-edit, rebuild instead
```

## The tool contract

`tools.py` is a façade over the analytics modules, not a second implementation:
`Desk` loads each series once, every tool is a function over it returning a plain
dict, and `TOOLS` carries the question each answers. Its only value is returning
*the same numbers* the analysis does, so `test_tools.py` pins each one against
the shipped payload. That parity check immediately earned itself — the first
version counted a blackout still in progress as a completed one, giving 29
weekends where every other path counts 28, and every decomposition figure moved
with it. **Only completed windows have a close.**

## Conventions

- **Every number traces to raw data.** Nothing appears on the page that
  `scripts/analyse_basis.py` cannot reproduce.
- **Report `n_windows`, not `n`.** 158 hourly bars from one weekend are not 158
  independent observations. The honest sample is 28 weekends, and it is stated
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
  now re-derives those four numbers and fails if they drift. The rule was broken
  again where it was hardest to see: the prompt sent to the language layer told
  the model to state a sample size of 27 while the payload said 28, so the one
  feature that speaks to a judge in sentences was instructed to misreport it.
  The figure appears nowhere on screen; the model just repeats what it is told.
  `test_page_style.py` now scans the template for transcribed figures.
- **The payload must never carry NaN.** Python writes a bare `NaN` token, which
  `JSON.parse` rejects, which renders the page *entirely blank* with no error.
  `build._json_safe` maps non-finite values to null and both writers pass
  `allow_nan=False`. The page's formatters render null as an em dash.
- **Prose goes stale when the data refreshes.** `tests/test_doc_figures.py` pins
  every figure quoted in the docs to the payload field it came from and fails
  naming the file and sentence. It also rejects copy that frames the premium as
  free money, the one claim the product exists to prevent. Add a CLAIMS entry
  whenever a doc starts quoting a new number; don't delete entries to make a
  failure go away.
- **A page that parses is not a page that runs.** `tests/test_page_runtime.py`
  loads both builds in jsdom and counts what rendered. A stripped backslash once
  turned a string literal into a syntax error: the HTML validated, every element
  was in the markup, the whole suite passed, and both charts rendered empty with
  every control dead. Static checks cannot see that. Run `npm install` once.
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
- **Backslash escapes can be eaten in transit.** Writing JS through a shell
  heredoc has silently turned `\n` into a real newline and dropped `\u2014`
  entirely, breaking a string literal. Build multi-line strings as arrays of
  paragraphs and use real characters; for edits to page JS, prefer the Edit tool
  over shell-piped Python. It also has a *silent* variant: a CSS escape for the
  minus sign became U+0091 followed by a literal `2`, so every open accordion
  rendered a stray digit. Nothing could see it — the HTML validated, the CSS
  parsed, jsdom rendered the element, the suite passed, and the character has no
  width in an editor. `test_page_style.py` now rejects any control or format
  character in any build.
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
- **The rToken fetcher must catch up before it extends.** GeckoTerminal only
  pages backwards, so `probe_sources.py` first walks back from *now* until it
  overlaps the cache, then pages back from the cache's oldest bar for depth. It
  previously did only the second step, so a stale file stayed stale however
  often it ran and every new weekend was silently missed.
- **The Fed's FOMC page carries each meeting twice** — a statement link with the
  exact date for past meetings, and a month plus day range for future ones. Only
  the range exists for the meetings that matter, and straddling meetings use
  abbreviated months (`Jan/Feb`). `fetch_events.py` parses ranges for all of
  them and cross-checks against the statement dates, so past meetings validate
  the parser the future ones depend on.

## Frontend

`docs/FRONTEND.md` is the visual architecture. The governing idea is that the
page carries the closure state: as venues shut it darkens and drops chrome while
one amber accent stays lit, because the rToken lane is the only thing still
quoting. Regime and theme are separate axes — the viewer's theme picks the
palette, the regime modulates illumination inside it, and regime never changes a
hue.

**The page is single-theme dark, by decision.** It does not follow the viewer's
setting: the accent reads 9.2:1 against the void and 3.6:1 against white, where
it degrades to ochre, so a light rendering is worse rather than merely
different. `--ground` sits 9 L* above `--void` because an earlier palette put
them 2.5 L* apart — below the threshold of noticing — which made the blackout
column and the regime shift both invisible. Contrast ratios hide that (1.05:1
reads like a rounding error); `test_page_style.py` measures L* instead.

**Do not adopt Bitget's brand identity**; a page wearing it reads as an
official product of theirs, which this is not.

Steps 1-7 are built: token layer, masthead, the full-bleed week strip,
`applyRegime` wiring, the time scrubber, the verdict pull-quote, and an editable
position size. `tests/test_page_style.py` holds the visual invariants;
`test_js_parity.py` pins the regime stamp to the calendar and the position
input's clamping.

**Type and spacing come from tokens, never literals.** Five text sizes
(`--t-micro` … `--t-lead`), five display sizes (`--d-sm` … `--d-2xl`), a 4px
spacing scale (`--s1`…`--s7`), one `--measure` and one `--rail`. The page had
grown 22 distinct font sizes, a dozen half a pixel apart — 11/11.5/12/12.5 all
labelling, 13.5/14/14.5/15/15.5 all body — plus six max-widths and five tracking
values. Each difference is invisible alone and collectively they are why it
stopped reading as one system. `test_page_style.py` rejects new literals.

**Instrument Serif ships weight 400 and nothing else.** `.sec-head h2` asked for
500, so every section heading was synthetically bolded — the browser smearing
the outline — on the page's most repeated heading. Guarded now: any rule using
`var(--display)` with a weight other than 400 fails.

**The lattice bleeds wider than the page, so the root must clip.** It is inset
-30% each side by design; nothing clipped it, so it extended the document to
1163px behind a 485px viewport and the whole page scrolled sideways with every
panel cut off. `html{overflow-x:clip}` fixes it — `clip`, not `hidden`, so the
root does not become a scroll container. Verified in headless Chrome
(`scrollWidth == clientWidth` at 375/768/1280); pinned in CSS because CI has no
browser.

**Inputs that carry a figure must size to their content.** The position field
was a fixed `5.2ch` and clipped its own default: the heading read "$250,00"
while every number under it was computed from $250,000. `initPosition` sets the
width from the value's length.

**Navigating to a section is a journey, not a cut.** The tool rail used to
teleport — no travel, no arrival, nothing to say the page had moved rather than
been replaced. Native `scroll-behavior:smooth` does the travel, because it stays
interruptible by the reader's own wheel where a hand-rolled rAF scroll does not.
The destination then marks itself: an amber rule sweeps its top edge and its
number flares once. Two things to know if you touch it. `scrollIntoView`'s
`behavior:"auto"` defers to the CSS value, so the reduced-motion path must say
`"instant"` explicitly or it animates anyway. And the cue fires on the scroll
going quiet (a 110ms debounce), not on `scrollend` — that event is still absent
from Safari and did not fire for every scroll in testing, which left the cue to
a timeout guessing at the arrival.

**A signed figure gets a diverging bar.** Distance from centre is the magnitude,
side of centre is the sign. `test_page_runtime.py` checks both against the number
printed beside it — a bar leaning the wrong way tells a trader the opposite of
what the figure says.

**Decoration must stay cheap and out of the way.** The lattice behind the
masthead is ~620 CSS-hovered cells, not the 15,000 Framer-animated nodes of the
component it borrows from, and it lights in `--lit` alone because a page arguing
"one thing stays lit" cannot have a rainbow behind its headline. It is scoped to
the header so it can never intercept the week strip's pointer handlers;
`test_page_runtime.py` caps the node count and checks both.

**A resting state is always the visible one.** Entrance animations start from
opacity 0 *inside a keyframe*, never as a base style, so a failure to animate
leaves content on screen. `test_page_style.py` enforces that, allows it on
`::before`/`::after` decoration, and caps the whole entrance under 2.4s.

**Interactions are dispatched in tests, not inspected.** Markup being present
proves nothing — a handler that throws looks identical in the source. The smoke
test fires real pointer events at the week strip and drift chart and asserts the
readouts respond.

**Motion is meaning, not decoration.** The rToken lane carries a slow beacon:
faint while other venues are open, insistent during a blackout, because that is
when it is the only thing still transmitting. The animation is CSS but the class
it hooks is emitted by `drawTimeline` — a guard that only reads the stylesheet
keeps passing while nothing animates, so `test_page_runtime.py` checks the
rendered DOM instead. Looping animations stay above 1.5s and the global
reduced-motion rule removes them.

**Every time-dependent panel reads `viewTime()`, never `Date.now()`.** That one
value is what the scrubber moves, so dragging recomputes real analytics for that
moment rather than animating a mock-up. Adding a panel that reads the clock
directly breaks the scrubber silently.

## CI

`.github/workflows/ci.yml` runs on every push: the suite on Ubuntu **and
Windows** (the cp1252 console has broken this project three times), a check that
`web/desk.html` still matches template + payload, and a printout of the
canonical figures. The suite is hermetic — it passes with every socket blocked —
so CI never flakes on a third-party API.

`.github/workflows/refresh.yml` runs Mondays 06:00 UTC and on demand: pulls new
data, rebuilds, and opens a PR showing which figures moved. **Expect
`test_doc_figures` to fail in that PR** — prose is the one thing the job cannot
rewrite, and that failure names the sentences to fix. Fix the prose; never
weaken the guard. **CI cannot republish the artifact**, so the live demo serves
the old numbers until someone does it by hand.

`scripts/figures.py` prints the canonical figures in a stable, diffable form —
run it after any refresh to see what the prose has to be brought in line with.

## Submission

`docs/SUBMISSION.md` is written to be pasted into the Google Form: all six parts
of the project description, the LLM-role field, and the X post copy.
`docs/RESEARCH_TASK.md` is the required research-task deliverable, regenerated
by running `scripts/research_task.py` so its figures cannot go stale.

## Cross-venue data

`scripts/fetch_bitget.py` pulls rToken candles from Bitget's own spot market;
`scripts/cross_venue.py` runs the decisive test on both venues and prints them
side by side, so the cross-venue figures in the docs are reproducible rather
than transcribed.

- **Bitget's rTokens only traded 7×24 from June 2026.** Before that the weekend
  share of hourly bars is under 1%: the series ran on the native equity clock
  and has no closure window in it to measure. The script derives the cutover
  rather than hardcoding it.
- **Both window rows must be the same weekends.** Deriving the qualifying set
  per venue gave 15 and 13 and still called them "the same window", which folds
  a sample difference into what reads as a venue difference. `cross_venue.py`
  intersects them.
- **Report `n` per horizon.** A weekend missing the bar at close+h drops out of
  that horizon alone, so one row's horizons can rest on different counts — the
  Bitget +1h figure is 8 weekends, not 13.
- **Only +1h replicates.** At +6h and +12h thirteen weekends measure nothing:
  the same venue moves 22% → 54% at +6h purely by shortening the window. Don't
  quote the short-window figures as if they confirmed the headline ones.

## Open items

- All seven tools are built.
- **No user testing yet.** Part 3 of the submission states the plan and labels
  every product metric as targeted rather than observed. Do not report a usage
  number that has not been measured.
- The event calendar covers FOMC only. Anything added must come from its issuing
  authority; a scraped aggregator has no place in a tool whose argument is that
  its numbers are checkable.
- **Bitget's API is reachable; only DNS is blocked.** Diagnosed 15 Sep: every
  Bitget domain fails with `gaierror` locally while resolving fine through a
  public resolver, and a direct TLS connection to the resolved address returns
  `200 OK`. Switching the machine's DNS to 1.1.1.1 or 8.8.8.8 lifts it entirely;
  no VPN is needed. `fetch_bitget.py` carries a documented DoH fallback so it
  works either way. Agent Hub / `bitget-signal` Skills are therefore reachable
  too, and remain the open scoring item.
- The artifact is **private by default**. The Vercel URL is the accessible-demo
  answer, so sharing the artifact is now optional rather than a validity gate —
  but the language layer only exists there, and it is a scored feature.
- **A data refresh needs the artifact republished by hand.** Vercel redeploys on
  push; nothing republishes the artifact, and it keeps serving old numbers.
