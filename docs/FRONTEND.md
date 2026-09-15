# Frontend architecture — Blackout Desk

The current page is a competent research document. It reports the findings
accurately and it will not lose us marks. It also will not be remembered.

This is the plan to change that, for a track scored on **feature depth, research
quality, LUI fluency and a personalised thesis** — all four of which are
judgements a person makes in the first fifteen seconds and then spends the rest
of the review confirming.

---

## 0. On looking like Bitget

We should not. Two reasons, one practical and one strategic.

A page carrying another organisation's visual identity reads as an official
product of theirs, which it is not. That is a line worth respecting on its own
terms, and we do not have their real design tokens to work from anyway —
approximating them from memory produces an uncanny near-miss, which looks worse
than having no relationship to the brand at all.

Strategically it is also the weaker play. Judges will see a stack of entries
reaching for the host's palette, and they blur together. A product with its own
coherent identity reads as a product; a product wearing the host's colours reads
as a submission.

What we do instead is **ecosystem compatibility**: dark-first, tabular figures,
exchange-grade density, a restrained single accent. It will sit naturally beside
Bitget's surfaces without pretending to be one.

---

## 1. The design thesis

**The page should know what time it is, and show it.**

Every other trading interface looks identical at 3pm Tuesday and 3am Sunday.
Ours is about the difference between those two moments. So the interface itself
carries the closure state: as venues shut, the page darkens, drops chrome, and
lets a single lit accent remain — the rToken lane, because it is the only thing
still quoting.

That is not decoration. It is the thesis rendered as interface, and it means a
judge opening the page on a Saturday sees a visibly different product from one
opening it on a Tuesday. Nobody else in this competition will have that.

The supporting metaphor is **sodium light**: the amber of a streetlamp outside a
closed building. It is why the accent is warm against a cold dark ground, and it
is where the whole palette comes from.

### The risk, and the fix

A judge who opens the page during US cash hours never sees the dramatic state.
So the hero carries a **time scrubber**: drag across the week and the entire
page recomputes — regime, countdown, exposure split, which venues are lit. The
product demonstrates itself in about four seconds of dragging, and the scrub is
honest because every frame is real computed state, not an animation.

---

## 2. Colour

**One theme, deliberately.** The page does not follow the viewer's light/dark
setting, because the two are not equivalent renderings of the same design. The
accent is sodium-vapour amber — a lit window in a dark street, which is exactly
what an rToken is during a blackout. It reads **9.2:1 against the void and 3.6:1
against white**, where it degrades from a lit lamp to ochre. On a light ground
the idea the palette exists to carry simply is not present.

| Token | Hex | Role |
|---|---|---|
| `--void` | `#07090D` | the blackout itself — true absence, never a fill |
| `--ground` | `#171F2A` | page |
| `--surface` | `#1E2836` | panels |
| `--raised` | `#26303F` | inputs, hovered rows |
| `--ink` | `#E8ECF2` | 14.0:1 on ground |
| `--muted` | `#94A1B2` | 6.3:1 |
| `--faint` | `#6D7B93` | 3.1:1 on raised — the tightest pairing on the page |
| `--rule` / `--rule-strong` | `#2C3849` / `#3C4B5F` | hairlines |
| `--lit` | `#E8A33D` | **the signature.** rToken, still quoting |
| `--open` | `#C9D8E8` | cash session — full illumination |
| `--half` | `#5D7086` | weeknight — a futures reference exists |
| `--risk` | `#E5786B` | danger states only, never decorative |
| `--ok` | `#63BE9A` | stable / usable |

### The ground sits well above the void, on purpose

An earlier palette put `--ground` at `#0D1117`, **2.5 L\* from the void**. That is
below the threshold of noticing, and it meant the two most important things in
the design were invisible in the only theme that ships: the blackout column in
the week strip, and the page darkening when a blackout begins.

Contrast ratios hide this — the same pair reads 1.05:1, which sounds like a
rounding error rather than the design failing. Perceptual lightness is the right
measure for adjacent large blocks, and **9 L\* of separation** is what makes
either read. `tests/test_page_style.py` now enforces it.

**One accent, spent in one place.** `--lit` appears on the rToken lane, the
countdown, and the single primary action. Semantic colours are separate from it
and are never used for emphasis.

---

## 3. Type

Three faces, three jobs, none of them the safe default.

| Role | Face | Use |
|---|---|---|
| Display | **Instrument Serif** (400 + italic) | The masthead, the verdict, the countdown. High contrast, only at 32px and above where that contrast reads. |
| UI | **Archivo** (400/500/600) | Everything a person reads. A sturdy grotesque that holds up at 13px, and deliberately not Inter. |
| Data | **IBM Plex Mono** (400/500) | Every figure, timestamp, ticker and axis label. `font-variant-numeric: tabular-nums` throughout. |

Scale (1.25 ratio, capped): `11 · 12.5 · 14 · 15 · 18 · 22 · 28 · 40 · 64`.
The 64 is used exactly twice — the masthead and the countdown.

**The typographic move that carries the page:** the verdict is set in Instrument
Serif at 40px, italic, as a pull-quote with real air around it. It is the one
sentence we want a judge to remember, and it should look like a thesis, not a
notification.

Running text stays near 65 characters. Uppercase labels get `.14em` tracking.
Headings get `text-wrap: balance`.

---

## 4. Layout architecture

```
┌─────────────────────────────────────────────────────────────┐
│ MASTHEAD          Blackout Desk        [regime chip]        │
│                                        49h 12m  ← 64px      │
├─────────────────────────────────────────────────────────────┤
│ THE WEEK                                        full bleed  │
│   NYSE    ▓▓▓▓░░░░░▓▓▓▓░░░░░▓▓▓▓░░░·····················    │
│   GLOBEX  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░·····················    │
│   RTOKEN  ████████████████████████████████████████████████  │
│                                     └── amber through void  │
│   [═══════════◉══════════════════]  ← scrubber              │
├─────────────────────────────────────────────────────────────┤
│ THE VERDICT                                                 │
│   "That premium is not free money."       ← 40px serif      │
│   [ 22% ][ 46% ][ −0.08% ][ 39% ]         ← evidence tiles  │
├─────────────────────────────────────────────────────────────┤
│ WHAT YOU ARE CARRYING     $[250,000] ← editable             │
│   ▓▓▓▓▓░░░░░░░████████████████████                          │
│   6h open · 17h reference · 49h dark                        │
│   Before the window: FOMC, Wed 16 Sep                       │
├─────────────────────────────────────────────────────────────┤
│ HOW FAR IT DRIFTS            fan chart, quantile bands      │
├─────────────────────────────────────────────────────────────┤
│ WEEKENDS LIKE THIS ONE       sliders + retrieved set        │
├─────────────────────────────────────────────────────────────┤
│ WHAT YOU CAN HEDGE WITH      table, stability-first         │
├─────────────────────────────────────────────────────────────┤
│ ASK THE DESK                 LUI, when available            │
└─────────────────────────────────────────────────────────────┘
```

### Section-by-section changes from today

| Section | Now | Becomes |
|---|---|---|
| Masthead | Small chip + 26px countdown | 64px countdown in display serif; regime chip reads as a lamp, lit or dark |
| The Week | 168px timeline in a card | **Full-bleed**, 240px tall, blackout drawn as true void, `--lit` running unbroken through it. The hero. |
| Scrubber | — | **New.** Drag to move `as_of`; everything below recomputes live |
| Verdict | Bordered callout | Pull-quote at 40px with air; evidence tiles below as a hairline-ruled row |
| Exposure | Fixed $250k | **Editable position size.** The judge types their own number |
| Calendar | Three text columns | Folded into exposure as a single "what's ahead" line |
| Drift | Fan chart | Same chart, restyled: endpoint emphasised, axis in `--faint`, band in `--lit` at 12%/26% |
| Analogues | Table + sliders | Same, with a match-strength bar per row and the range stated before the median |
| Hedges | Table | Stability pill leads the row, not the correlation |
| Ask | Plain box | Suggested questions as chips; answer streams in |

---

## 5. The living-state mechanic

One function owns it:

```js
function applyRegime(regime) {
  document.documentElement.dataset.regime = regime;   // US_CASH | WEEKNIGHT | BLACKOUT
}
```

CSS responds through tokens only:

```css
:root[data-regime="WEEKNIGHT"] { --ground: /* one step darker */; --open: var(--half); }
:root[data-regime="BLACKOUT"]  { --ground: var(--void); --rule: /* dimmer */; }
```

Rules:

- **Regime never changes a hue, only illumination.** Panels dim, rules recede,
  `--lit` stays exactly as it is. That is the point: one thing stays on.
- **Transitions are 400ms ease on background and border only.** Text never
  animates. Under `prefers-reduced-motion` they are removed entirely.
- **It is driven by the same `currentRun()` the clock already uses**, so the
  visual state and the stated regime cannot disagree. The parity test in
  `test_js_parity.py` already pins that function to the Python calendar.

---

## 6. Motion policy

Deliberately sparse — over-animation is itself a tell of generated design.

| Allowed | Why |
|---|---|
| Countdown digits ticking | It is a clock |
| Regime cross-fade (400ms) | Carries the thesis |
| Scrubber-driven recompute | Direct manipulation |
| Chart draw-in on first paint (300ms, once) | Establishes the fan shape |
| The rToken lane's beacon (4.5s idle, 2.6s in a blackout) | Carries the argument: the lane is faint among open venues and insistent when it is the only one lit |

Everything else is static. No scroll-triggered reveals — the page must be
complete in its first still frame, since that frame is what a thumbnail and a
skim-reader get.

---

## 7. Component inventory

Build as plain functions over the existing payload; no framework, no build step.

1. `Masthead` — name, regime lamp, countdown
2. `WeekStrip` — the hero timeline + scrubber *(new scrubber)*
3. `Verdict` — pull-quote + evidence tiles
4. `PositionBar` — editable size, regime split, what's-ahead line *(new input)*
5. `DriftFan` — quantile chart
6. `AnalogueFinder` — sliders, retrieved rows, range summary
7. `HedgeTable` — stability-first rows
8. `AskDesk` — LUI, hidden when `sample` is unavailable
9. `Provenance` — footer: generated date, sample size, sources

---

## 8. What we are deliberately not doing

- No gradient hero, no glassmorphism, no glow effects
- No emoji as section markers
- No numbered step markers — the sections are not a sequence
- No card-with-accent-bar on every block; border and shadow are spent by role
- No `100vh` opener that pushes the content out of the first frame
- No animated counters on load — the numbers are real, not a slot machine
- No Bitget brand impersonation

---

## 9. Non-negotiables carried forward

These are already true and must survive the redesign:

- **The page works with no LLM.** Every analytic renders statically.
- **Sample size sits beside every distribution.** 28 weekends is thin, and the
  design must not make it look authoritative.
- **Every figure traces to the payload.** No hand-typed numbers in markup.
- **Both themes are complete**, with every token declared in the bare `:root`.
- **Phone width works** — the week strip scrolls horizontally in its own
  container; the body never does.

---

## 10. Build order

Each step ships independently, so we are never mid-refactor with a broken demo.

| Step | Work | Why first |
|---|---|---|
| 1 ✅ | Token layer: new palette, `[data-regime]` blocks, fonts | Everything else reads from it |
| 2 ✅ | Masthead + countdown at full scale | Highest impact per line changed |
| 3 ✅ | WeekStrip full-bleed with true void | The hero; the thing judges screenshot |
| 4 ✅ | `applyRegime` wiring | Turns the design into the thesis |
| 5 ✅ | Scrubber | Makes the page demo itself |
| 6 ✅ | Verdict pull-quote | The sentence we want remembered |
| 7 ✅ | Editable position size | Makes it the judge's own number |
| 8 | Restyle drift / analogues / hedges to the new tokens | Consistency pass |
| 9 | Mobile + reduced-motion + both-theme audit | Never optional |

**Gate:** after every step, `python -m pytest -q` stays green — the JS parity and
clock tests guard the functions this touches — and the page is republished, so
the live URL is never worse than it was.
