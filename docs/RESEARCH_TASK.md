# Complete research task

**Required deliverable for the AI Trading Desk track: one full research task,
from question to actionable insight.**

> *"I'm long $250k of NVDAx into this weekend. What am I exposed to, and should
> I hedge?"*

This is a program, not prose: `python scripts/research_task.py`. Every figure
below is computed at run time from the raw data in `data/raw/`, so the
walkthrough cannot quietly go stale and no number here has to be taken on trust.
The run captured below is dated in its own header.

## How the seven tools compose

The question decomposes into seven sub-questions, and each tool answers exactly
one. They run in an order that mirrors how a trader actually reasons: establish
the window, size the exposure, check what is scheduled, consult the
distribution, look for precedent, test the tempting trade, then price the ways
out.

| Step | Tool | Sub-question |
|---|---|---|
| 1 | `closure_window` | Which window am I facing, and for how long? |
| 2 | `exposure` | What is my book carrying through it? |
| 3 | `macro_calendar` | Is anything scheduled to explain a move? |
| 4 | `divergence_distribution` | How far does price typically travel? |
| 5 | `historical_analogues` | What happened in weekends that looked like this? |
| 6 | `premium_verdict` | Is the premium in front of me tradeable? |
| 7 | `hedge_menu` | What can I actually hedge with, and at what cost? |

Three of these produce answers a trader would not get anywhere else. Step 3
establishes that **nothing is scheduled and nothing ever is** — weekend risk is
unscheduled by construction. Step 6 says the obvious trade is not a trade. Step 7
says every available hedge is unstable, including the one that looks best.

## Why the answer is a distribution and not a forecast

The desk never says what will happen. It says what has happened, how often, with
what spread, and how thin the sample is. With 28 weekend blackouts the range is
the honest signal and the mean is the misleading one, so the range leads and the
sample size is repeated at the end of every section that quotes one.

The final recommendation is a sizing decision and two prohibitions, not a
direction. The trader decides.

## Captured run

```
BLACKOUT DESK - complete research task
Question : I'm long $250,000 of NVDAx into this weekend.
           What am I exposed to, and should I hedge?
As of    : 2026-09-14 11:39 UTC

==========================================================================
1. closure_window - what window am I facing?
==========================================================================
  Right now            : WEEKNIGHT
  Next blackout opens  : Fri 18 Sep 21:00 UTC
  Reference returns    : Sun 20 Sep 22:00 UTC
  Duration             : 49 hours with no reference price

==========================================================================
2. exposure - what is my book actually carrying?
==========================================================================
  Gross                : $250,000
  Unhedgeable hours    : 0 of 72 (0%)
    US_CASH             21h    29%
    WEEKNIGHT           51h    71%

==========================================================================
3. macro_calendar - is anything scheduled?
==========================================================================
  Inside the window    : 0 scheduled events
  Historically         : 0 of 22 rate decisions have ever fallen inside one of 134 weekend blackouts
  => Weekend risk is UNSCHEDULED risk. There is nothing to plan around,
     which is why the historical distribution is the only guide.

==========================================================================
4. divergence_distribution - how far does it typically move?
==========================================================================
  Sample               : 28 weekend blackouts
  Mean |drift|         : 0.86%  ($2,148)
  p95 |drift|          : 1.94%  ($4,853)
  Worst observed       : 2.14%  ($5,349)
  Beyond +/-1%         : 39% of weekends
  Worst point reached  : 1.31% on average, vs 0.86% where they ended
  => The drawdown you sit through is larger than the number you wake up to.

==========================================================================
5. historical_analogues - what happened in weekends like this?
==========================================================================
  Conditions now       : vol 40%, premium -0.40%, 49h window
  weekend        vol   prem in     ended    worst   dist
  2026-06-12   49%    -0.31%     2.14%    2.14%   1.07
  2026-05-08   42%    -0.10%     0.52%    1.12%   1.69
  2026-04-10   39%    -0.09%    -2.04%    2.24%   1.70
  2026-07-17   44%    -0.00%     0.69%    0.69%   2.24
  2026-05-15   60%    -0.19%     0.63%    1.00%   2.39
  Range of outcomes    : -2.04% to +2.14%
  Worst point in set   : 2.24% ($5,602)

==========================================================================
6. premium_verdict - is the premium tradeable?
==========================================================================
  + 1h  closure from token   6%   from stale reference  94%
  + 6h  closure from token  22%   from stale reference  78%
  +12h  closure from token   2%   from stale reference  98%
  Hit rate fading it   : 46.4%
  Net at 10bp costs    : -0.083% per weekend
  => NOT an arbitrage. The gap closes because the reference catches up,
     not because the token corrects. Do not trade against it.

==========================================================================
7. hedge_menu - what can I actually hedge with?
==========================================================================
  TSLAx     corr +0.78  short $ 244,865  cost $ 1,469  cuts 37%
            unstable - rolling correlation spans -0.45 to +0.97; has been risk-adding
  BTC-USD   corr +0.66  short $ 107,602  cost $   161  cuts 25%
            unstable - rolling correlation spans -0.51 to +0.89; has been risk-adding
  ETH-USD   corr +0.60  short $  67,929  cost $   102  cuts 20%
            unstable - rolling correlation spans -0.35 to +0.79; has been risk-adding

==========================================================================
8. ACTIONABLE INSIGHT
==========================================================================
  You are carrying $250,000 through 49 hours in which
  no reference price exists and nothing is scheduled to explain a move.

  Expect     : +/-$2,148 typical, +/-$4,853 at the 95th percentile,
               a worse excursion mid-window than at the end,
               and a 39% chance of finishing beyond 1%.

  Do NOT     : trade against the premium. It is an information lead, and
               fading it is a 46% coin flip that loses to fees.

  Hedging    : the best available is TSLAx at +0.78 correlation,
               cutting 37% of variance for $1,469. But it is
               unstable - the rolling correlation has changed sign, so it
               has been risk-ADDING in past stretches.

  Decision   : size the position so the p95 outcome is survivable, or trim
               before the close. Do not pay for an unstable hedge, and do
               not treat the premium as free money. The trader decides.

  Sample: 28 weekend blackouts. Thin. Read the range, not the middle.
```
## Reproducing it

```bash
pip install -e ".[dev]"
python scripts/research_task.py
```

The same seven tools back the published demo at
https://claude.ai/artifact/3eKJskZZThj72zRwZjBpK2 — the page
renders them for the window currently ahead, computed against a live clock, and
its language layer answers questions grounded strictly in these measurements.
