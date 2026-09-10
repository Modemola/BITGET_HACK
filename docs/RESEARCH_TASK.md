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
what spread, and how thin the sample is. With 27 weekend blackouts the range is
the honest signal and the mean is the misleading one, so the range leads and the
sample size is repeated at the end of every section that quotes one.

The final recommendation is a sizing decision and two prohibitions, not a
direction. The trader decides.

## Captured run

```
BLACKOUT DESK - complete research task
Question : I'm long $250,000 of NVDAx into this weekend.
           What am I exposed to, and should I hedge?
As of    : 2026-09-10 22:25 UTC

==========================================================================
1. closure_window - what window am I facing?
==========================================================================
  Right now            : WEEKNIGHT
  Next blackout opens  : Fri 11 Sep 21:00 UTC
  Reference returns    : Sun 13 Sep 22:00 UTC
  Duration             : 49 hours with no reference price

==========================================================================
2. exposure - what is my book actually carrying?
==========================================================================
  Gross                : $250,000
  Unhedgeable hours    : 49 of 72 (68%)
    US_CASH              6h     8%
    WEEKNIGHT           17h    24%
    WEEKEND_BLACKOUT    49h    68%

==========================================================================
3. macro_calendar - is anything scheduled?
==========================================================================
  Inside the window    : 0 scheduled events
  Waiting at the reopen: FOMC rate decision on Wed 16 Sep 18:00 UTC
  Historically         : 0 of 22 rate decisions have ever fallen inside one of 134 weekend blackouts
  => Weekend risk is UNSCHEDULED risk. There is nothing to plan around,
     which is why the historical distribution is the only guide.

==========================================================================
4. divergence_distribution - how far does it typically move?
==========================================================================
  Sample               : 27 weekend blackouts
  Mean |drift|         : 0.84%  ($2,094)
  p95 |drift|          : 1.95%  ($4,887)
  Worst observed       : 2.14%  ($5,349)
  Beyond +/-1%         : 37% of weekends
  Worst point reached  : 1.28% on average, vs 0.84% where they ended
  => The drawdown you sit through is larger than the number you wake up to.

==========================================================================
5. historical_analogues - what happened in weekends like this?
==========================================================================
  Conditions now       : vol 48%, premium +0.80%, 49h window
  weekend        vol   prem in     ended    worst   dist
  2026-07-03   39%     0.43%     0.71%    0.75%   2.50
  2026-07-31   65%     0.36%     0.26%    0.97%   3.06
  2026-03-13   40%     0.27%     0.38%    0.75%   3.23
  2026-03-27   48%     0.23%     0.04%    0.52%   3.35
  2026-09-04   48%     0.23%     0.83%    1.09%   3.35
  Range of outcomes    : +0.04% to +0.83%
  Worst point in set   : 1.09% ($2,726)

==========================================================================
6. premium_verdict - is the premium tradeable?
==========================================================================
  + 1h  closure from token   6%   from stale reference  94%
  + 6h  closure from token  27%   from stale reference  73%
  +12h  closure from token  13%   from stale reference  87%
  Hit rate fading it   : 48.1%
  Net at 10bp costs    : -0.009% per weekend
  => NOT an arbitrage. The gap closes because the reference catches up,
     not because the token corrects. Do not trade against it.

==========================================================================
7. hedge_menu - what can I actually hedge with?
==========================================================================
  TSLAx     corr +0.76  short $ 233,409  cost $ 1,400  cuts 36%
            unstable - rolling correlation spans -0.45 to +0.97; has been risk-adding
  BTC-USD   corr +0.71  short $ 108,591  cost $   163  cuts 29%
            unstable - rolling correlation spans -0.51 to +0.89; has been risk-adding
  ETH-USD   corr +0.61  short $  66,034  cost $    99  cuts 21%
            unstable - rolling correlation spans -0.35 to +0.79; has been risk-adding

==========================================================================
8. ACTIONABLE INSIGHT
==========================================================================
  You are carrying $250,000 through 49 hours in which
  no reference price exists and nothing is scheduled to explain a move.

  Expect     : +/-$2,094 typical, +/-$4,887 at the 95th percentile,
               a worse excursion mid-window than at the end,
               and a 37% chance of finishing beyond 1%.

  Do NOT     : trade against the premium. It is an information lead, and
               fading it is a 48% coin flip that loses to fees.

  Hedging    : the best available is TSLAx at +0.76 correlation,
               cutting 36% of variance for $1,400. But it is
               unstable - the rolling correlation has changed sign, so it
               has been risk-ADDING in past stretches.

  Also note  : FOMC rate decision lands Wed 16 Sep - shortly after the reopen. A quiet
               weekend into a rate decision is not a quiet position.

  Decision   : size the position so the p95 outcome is survivable, or trim
               before the close. Do not pay for an unstable hedge, and do
               not treat the premium as free money. The trader decides.

  Sample: 27 weekend blackouts. Thin. Read the range, not the middle.
```

## Reproducing it

```bash
pip install -e ".[dev]"
python scripts/research_task.py
```

The same seven tools back the published demo at
https://claude.ai/code/artifact/15681462-d2cf-4c1c-afba-733d723bd461 — the page
renders them for the window currently ahead, computed against a live clock, and
its language layer answers questions grounded strictly in these measurements.
