# Blackout Basis — strategy spec and build log

**Track:** Alpha Factory · **Sub-theme:** Cross-Market Correlation Strategies

## Thesis

US equity exposure is quoted on three clocks, and the gaps between them create
the rToken arbitrage band:

| Regime | Venues quoting | Can an AP hedge / create / redeem? |
|---|---|---|
| `US_CASH` | rToken, native equity, index futures | Yes — band at its tightest |
| `WEEKNIGHT` | rToken, index futures | No, but a reference price exists |
| `WEEKEND_BLACKOUT` | **rToken only** | No, and no reference price exists |
| `HOLIDAY_BLACKOUT` | **rToken only** | As above, usually longer |

The premium/discount of rToken to fair value is therefore not a mispricing to be
threshold-traded. It is a **risk premium paid to whoever warehouses unhedgeable
delta until the next reopen**, and its fair width scales with σ√τ plus issuer
mint/redeem friction. We trade deviations from that term structure, not
deviations from NAV — positions converge mechanically at a reopen whose
timestamp is known in advance.

We are not authorised participants and cannot mint or redeem. We trade the
residual the APs leave behind.

## Established so far (calendar evidence, no market data required)

Computed by `scripts/blackout_stats.py` over 2025-01-01 → 2026-09-10 from the
XNYS and CMES exchange calendars:

- **rToken is the only quoted venue 30.6% of all wall-clock time** (2,681 h/yr).
- The native cash market is open just **18.4%** of wall-clock time.
- A normal weekend blackout is **49 hours** (Fri 17:00 ET Globex close → Sun
  18:00 ET reopen). Confirmed as the modal value across 88 weekend blackouts.
- Good Friday produces the fat tail: **73-hour** blackouts (2025-04-17, 2026-04-02).
  Thanksgiving and Independence Day produce 54-hour ones.

### Finding that changes the design

A trailing 60-day sample — the hackathon minimum — contains only **9 blackout
windows (8 weekends)**. That is far too thin to support a weekend-only claim.
180 days contains 27. Two consequences:

1. Run the backtest over **180+ days**, not the 60-day minimum, and state why.
2. The **weeknight basis carries the statistical weight** (~4,463 h/yr, a
   reference price exists, so the signal is cleanly measurable). Weekend
   blackouts are the fat-tail overlay, not the primary sample.

This is the opposite of how the strategy first looked, and it is only visible
because the calendar work was done before any data work.

## Status

| Component | State |
|---|---|
| Closure clock (regime + τ engine) | Built, 8 tests passing |
| Blackout statistics | Built, run above |
| Data source probe | Rewritten with pagination; first run gave a false negative |
| Synthetic reference price | Not started — blocked on data |
| Band model / backtest | Not started — blocked on data |

### Blocker: sandbox egress policy

This session's network policy allows GitHub and package registries only. Every
market data host tested returned a 403 at the proxy CONNECT stage:
`api.bitget.com`, `api.geckoterminal.com`, `api.coingecko.com`, `api.binance.com`,
`query1.finance.yahoo.com`, `stooq.com`, `data.sec.gov`, `www.alphavantage.co`,
`api.polygon.io`.

The kill-criterion test therefore has to run elsewhere:

```bash
pip install -r requirements.txt
python3 scripts/probe_sources.py     # exit 0 = Blackout Basis is GO
```

If no source clears the bar, the fallback is Idea 3 (the Friday 15:45 closure
risk desk), which reasons about closure risk qualitatively and needs no backtest.

### First probe run, 2026-09-10 — 7x24 property confirmed

The first run reported NO-GO. That verdict was wrong: the probe fetched a single
1000-bar page (the API maximum), then failed the source for returning exactly
what was asked of it. 1000 hourly bars is 41.7 days, which is the whole of the
reported "43d span".

What the run did establish, and it is the finding that matters:

- **AAPLx returned 27% weekend bars.** Saturdays and Sundays are 28.6% of
  wall-clock time, so the series is continuously quoted through weekends with
  essentially no gaps. This is the property the strategy depends on and the one
  most equity data sources fail outright.
- AAPLx pool liquidity was **$305,550** — thin, and a live constraint on
  strategy capacity rather than on validity.
- The Bitget failure was a DNS resolution error on the operator's machine, not
  a statement about data availability.
- The Stooq failure was a malformed URL in the probe.

The probe now pages backwards with `before_timestamp`, scans every xStocks
symbol rather than stopping at the first hit, reports liquidity and depth per
symbol, and distinguishes "hit the page cap" from "history exhausted" so that a
capped read can never again be mistaken for missing data.

## Layout

```
src/blackout/clock.py        closure regime + time-to-reopen engine
scripts/blackout_stats.py    structural facts for the thesis
scripts/probe_sources.py     data availability kill-criterion test
tests/test_clock.py          invariants of the clock
```
