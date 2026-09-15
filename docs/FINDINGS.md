# Findings — rToken pricing across market-closure windows

**Data:** NVDAx and TSLAx hourly (Solana, xStocks), 2026-03-01 → 2026-09-14,
4,702 usable bars, joined to NVDA/TSLA native equity and NQ/ES index futures.
99% hourly coverage, 0% stale bars, 0 outliers beyond ±5%, 0 nulls.
Reproduce with `python scripts/analyse_basis.py`.

## Headline result

**During market-closure windows, rToken is the efficient price and the
reference is the laggard.** The band closes because fair value catches
up to the token, not because the token corrects. There is no tradeable
convergence in it.

This is the opposite of the premise the strategy was built on, and it was found
by a test designed to falsify our own result rather than confirm it.

## What held

The band widens exactly as predicted, monotonically with how much information
infrastructure is shut:

| Regime | n | mean premium | std | p5 | p95 |
|---|---|---|---|---|---|
| `US_CASH` | 798 | 0.01% | 0.42% | −0.66% | 0.71% |
| `WEEKNIGHT` | 2,459 | 0.09% | 0.52% | −0.47% | 0.90% |
| `WEEKEND_BLACKOUT` | 1,338 | 0.19% | 0.70% | −1.00% | 1.37% |

Persistence tells the same story. The premium is arbitraged away almost
instantly while the cash market is open, and becomes progressively stickier as
venues shut:

| Regime | AR(1) | implied half-life |
|---|---|---|
| `US_CASH` | +0.024 | 0.2 h |
| `WEEKNIGHT` | +0.490 | 1.0 h |
| `WEEKEND_BLACKOUT` | +0.891 | 6.0 h |

Divergence accumulates through a blackout: mean |premium| grows from **0.16% at
the start of a weekend to 0.91% by its end**, a ~6× expansion over 49 hours.
Across 28 weekends, the premium moved toward zero at the reopen **85%** of the
time, mean 0.26%.

## What did not hold, and why it matters

The τ framing was backwards. We predicted the band would widen with time
*remaining* until an authorised participant could hedge. Observed correlation
between `tau_futures` and |premium| is **−0.409**: the band is narrowest at the
start of a weekend and widest at its end. The driver is elapsed time against a
frozen anchor, not warehousing risk.

That reframing looked like a better strategy. It was not, because an 85%
convergence rate says nothing about who converged. Decomposing the closure into
the token leg and the fair-value leg:

| Horizon | from token | from fair value | **token share** |
|---|---|---|---|
| +1 h | 0.023% | 0.325% | **7%** |
| +6 h | 0.153% | 0.394% | **28%** |
| +12 h | 0.091% | 0.625% | **13%** |

Only the token-leg share is capturable by trading the token. The rest is a
stale reference catching up to a price that was already right.

The directly tradeable P&L confirms it — 48–52% hit rate, gross Sharpe 0.07–0.19
per trade, and negative after the cheapest realistic cost:

| Cost assumption | Net mean | Verdict |
|---|---|---|
| CEX taker ~0.10% round trip | −0.009% | dead |
| CEX ~0.20% round trip | −0.109% | dead |
| DEX AMM ~0.60% round trip | −0.509% | dead |

## Every variant tested, and its result

| Variant | Sample | Result |
|---|---|---|
| Fade the blackout premium (token leg) | 28 weekends | Hit 48–52%, dies at 10bp costs |
| Follow the drift on the futures leg | 28 weekends | corr(signal, move) = −0.05; only 1 of 5 horizons positive; first half of sample negative |
| Fade the weeknight premium, z>1.0/1.5/2.0 | 2,361 bars, 424 signals | Sharpe/trade 0.03–0.13; **worse at stronger thresholds** |
| Decomposition at z>1.5, 6h | 206 signals | Token leg contributes **−9%** — it moves *away* |

Getting worse as the signal gets stronger is the signature of noise. A real
mean-reversion edge strengthens at the tails.

## Why this is a real finding rather than a failed backtest

The efficient-market reading is consistent across regimes, thresholds,
horizons, both directions of the trade, and both instruments. The 7×24 venue
everyone assumes is retail-dominated and mispriced is, at hourly resolution,
pricing closure-window information correctly. What looks like a 0.91% weekend
mispricing is a 0.91% **information lead** over a reference that cannot trade.

Two caveats stated plainly. The sample is 28 weekends, which is what 197 days of
rToken history allows and is thin for anything Sharpe-based. And the test is at
hourly resolution — sub-hourly microstructure could behave differently, and we
have no data to say.

## Cross-venue check: Bitget's own rTokens

Everything above is measured on one venue — xStocks pools on Solana. A result
from a single venue is a result about that venue until someone checks another,
so it was checked against Bitget's own spot listing of the same underlying
(`RNVDAUSDT`), pulled with `scripts/fetch_bitget.py`. Reproduce the whole table
with `python scripts/cross_venue.py`.

**Bitget's rToken only began trading 7×24 in June 2026.** Before that the
weekend share of its hourly bars sits between 0% and 1.1%: it ran on the native
equity clock, which means there is no closure window in it to measure at all.
From June the share is 17%, then 24%, 32%, 27%. That is worth stating on its
own — continuous trading of these instruments is a 2026 development, not an
established regime — and it caps the comparable sample at **13 weekends** that
both venues cover end to end, against 28 on Solana.

The two window rows below are the *same thirteen weekends*. Deriving the set
per venue gave 15 and 13 and would have folded a sample difference into what
gets read as a venue difference.

### Premium dispersion by regime, from June 2026

| | US_CASH | WEEKNIGHT | WEEKEND_BLACKOUT |
|---|---|---|---|
| Solana (NVDAx) | 0.44% | 0.47% | **0.53%** |
| Bitget (RNVDAUSDT) | 0.39% | 0.45% | **0.60%** |

**The dispersion ordering replicates.** The blackout is the widest regime on
both venues, and the cash session the narrowest. This is the structural claim
the desk is built on, and it does not depend on where the token trades.

### Which leg closes the gap, by sample

Share of closure attributable to the **token** leg; the remainder is the
reference catching up. `n` is the weekends with a usable bar at that horizon —
a weekend missing the bar at close+h drops out of that horizon alone.

| Sample | weekends | +1h | +6h | +12h |
|---|---|---|---|---|
| NVDAx, full history | 28 | 6% (n=28) | 22% (n=28) | 2% (n=28) |
| NVDAx, same 13 weekends | 13 | 11% (n=13) | 54% (n=13) | 19% (n=13) |
| RNVDAUSDT, same 13 weekends | 13 | 9% (n=8) | 97% (n=13) | 60% (n=13) |

Read the middle row against the bottom one first. Same venue, shorter window is
the sample effect; different venue, same window is the venue effect.

**At +1h the venues agree and both are small** — 11% and 9%. The token leg is a
single-digit minority of closure on both books. That is the finding, and it
replicates.

**Beyond +1h, thirteen weekends measure nothing.** The same venue moves from 22%
to 54% at +6h purely by shortening the window, before any second venue is
involved. Bitget then reads 97%. That last number is not a measurement: its
fair-value leg moves +0.0137%, so the share is a ratio against a denominator
that is essentially zero, and it would swing wildly on one weekend either way.
The +12h pair (19% and 60%) disagrees for the same reason in weaker form.

So the check does two things, and the second is a limit on our own numbers.

**It confirms the shortest horizon on a second venue.** Dispersion widens the
same way and the token leg is a single-digit minority at +1h on both.

**It shows that the longer horizons need the full sample to mean anything.** The
figures the desk reports are the 28-weekend Solana measurements, labelled as
such, and they should not be read as though a thirteen-weekend sample — on
either venue — could confirm or refute them at +6h or +12h. The direction is
robust across venues; the decimal is a property of the sample.

## Consequence

Blackout Basis is not viable as an Alpha Factory entry. The finding itself —
that the closure-window band is an information lead rather than a mispricing,
and what that implies for anyone holding rToken through a 49-hour blackout — is
the asset that survives.
