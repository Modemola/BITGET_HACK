# Findings — rToken pricing across market-closure windows

**Data:** NVDAx and TSLAx hourly (Solana, xStocks), 2026-03-01 → 2026-09-10,
4,607 usable bars, joined to NVDA/TSLA native equity and NQ/ES index futures.
99% hourly coverage, 0% stale bars, 0 outliers beyond ±5%, 0 nulls.
Reproduce with `python scripts/analyse_basis.py`.

## Headline result

**During market-closure windows, rToken is the efficient price and the
reference is the laggard.** The arbitrage band closes because fair value catches
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
Across 27 weekends, the premium moved toward zero at the reopen **85%** of the
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
| Fade the blackout premium (token leg) | 27 weekends | Hit 48–52%, dies at 10bp costs |
| Follow the drift on the futures leg | 27 weekends | corr(signal, move) = −0.05; only 1 of 5 horizons positive; first half of sample negative |
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

Two caveats stated plainly. The sample is 27 weekends, which is what 210 days of
rToken history allows and is thin for anything Sharpe-based. And the test is at
hourly resolution — sub-hourly microstructure could behave differently, and we
have no data to say.

## Consequence

Blackout Basis is not viable as an Alpha Factory entry. The finding itself —
that the closure-window band is an information lead rather than a mispricing,
and what that implies for anyone holding rToken through a 49-hour blackout — is
the asset that survives.
