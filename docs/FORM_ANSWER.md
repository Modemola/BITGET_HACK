# Project Description — paste verbatim into the Google Form

Five parts, not the six `SUBMISSION.md` uses. The form says *"Do not repeat your
deliverables list here"* (separate field) and *"GitHub, X, or external documents
cannot replace this answer"* — so paste it, never link it.

First person singular. Change "I" to "we" if entering as a team.

---

## Part 1 · Thesis

I set out to build a trading strategy. It didn't work, and the tool is what came
out of finding that out.

Tokenized US stocks trade around the clock; the market that prices them doesn't.
CME Globex closes Friday 17:00 New York and reopens Sunday 18:00. For those 49
hours an rToken is the only venue on earth quoting US equity exposure. No cash
market, no futures, nobody able to hedge or redeem. I assumed a thin, retail-only
venue trading alone must misprice, and went looking for the trade.

The premium does widen as venues shut: dispersion 0.42% in the cash session,
0.51% overnight, 0.70% in a blackout, with the half-life stretching from 0.2
hours to 1.0 to 6.0. Across 28 weekends the gap narrowed at the reopen 79% of the
time.

None of it is tradeable. Asking which side closed the gap, 78–98% of the
convergence is fair value catching up to the token rather than the token
correcting. The reference was asleep; the token was already right. The leg you
can actually trade wins 46.4% of the time and loses 0.083% per weekend after 10bp
of costs. Four variants agreed, and signals got worse at stronger thresholds,
which is what noise does and an edge doesn't.

So the premium is an information lead, not a mispricing. That makes it dangerous
rather than useless, because it looks exactly like free money. Blackout Desk
prices the risk you are carrying through the window and tells you the gap is not
a trade, with the working shown.

Existing tools assume an opening bell. Trackers show a price stale since Friday;
risk calculators assume you can sell. Nothing reasons in closure windows, because
until rToken there was nothing to reason about.

## Part 2 · Target user and product value

Self-directed retail traders holding $10,000 to $500,000 of tokenized US stock
across a weekend. Their own money, on Bitget or on-chain. Days-to-weeks holds,
directional long in single names, sometimes levered, never market-neutral. No
risk desk, no Bloomberg; sizing comes from instinct.

The band is chosen. Below $10,000 the weekend gap is noise. Above roughly
$500,000 the books are too thin to act on — the deepest NVDAx pool is about
$2.1m.

Why they need it: they sleep through 49 hours they cannot watch, and 39% of
weekends end with the price more than 1% from where the reference left it. The
worst in my sample was 2.14%, or $5,350 on a $250,000 position. Nobody has shown
them that distribution.

They are also exposed to one expensive mistake — reading a 1% weekend premium as
an arbitrage. It is wrong, and it loses money gradually enough to take years to
notice. Plenty of tools show the premium. None say where it came from.

## Part 3 · Validation data and key metrics

The research is measured; product usage isn't. Labelled accordingly.

**Observed.** 1 March to 14 September 2026: 197 days, 4,702 hourly bars of NVDAx
joined to NVDA, NQ and ES futures, and BTC/ETH. 28 weekend blackouts — I report
windows, not bars, because 158 bars from one weekend are not 158 independent
observations. Dispersion 0.42% / 0.51% / 0.70%; AR(1) half-life 0.2h / 1.0h /
6.0h. Drift 0.86% mean absolute, 1.94% at the 95th percentile, 2.14% worst, 39%
of weekends beyond 1%. Tradeable leg 46.4% hit rate, −0.083% net of 10bp; token
share of convergence 6%, 22% and 2% at one, six and twelve hours. Hedges BTC
+0.66, ETH +0.60, TSLAx +0.78, none stable — the tool reports the instability
instead of recommending them. 148 tests, one of which fails if the prose drifts
from the data. All of it regenerates from committed raw data with one script.

**Observed usage: none.** Zero test users. I built this inside the competition
window and would rather say so than invent a number.

**Targeted**, first 60 days: 50 completed closure-window assessments, 40%
returning for a second weekend, under 3 minutes from landing to a sized answer.

**Plan.** 10 to 15 traders holding rToken over one weekend. Before the tool, ask
how far they think the position can move by Monday and whether the premium is
worth trading. Show them the tool. Ask again. Count who changes their answer —
that is the product's claim, and one weekend tests it. On distribution: volume is
the wrong metric for a tool that prevents trades. Retention across weekends is
the right one.

## Part 4 · Progress

**Built:** seven tools, the analytics engine, the data pipeline, and the page on
two deployments — a plain static URL and a Claude artifact carrying the
natural-language layer. 148 tests, CI on Ubuntu and Windows, and a weekly job
that refreshes data and opens a pull request showing which figures moved.

**Not built:** user testing. The event calendar covers FOMC only — I required
anything in it to come from the issuing authority, and the Fed used the time.

**Problems.** The strategy failing, after the data spine was already finished.
pandas 2 infers microsecond resolution from a timestamp string, so `.asi8`
returned microseconds against nanosecond calendars and silently put everything in
1970 — found through a 481,662-hour countdown. GeckoTerminal caps a page at 1000
bars; my first probe asked for 1000, got 1000, and concluded the history was 41
days. A bare NaN in the payload makes `JSON.parse` fail, rendering the page blank
with nothing in the console.

**Next:** user testing, more of the calendar, sub-hourly data. Everything here is
hourly and I can't say what happens inside the hour.

**Stack.** Python with pandas, numpy and exchange_calendars for NYSE and CME
sessions; Claude for the language layer through the artifact runtime; data from
GeckoTerminal, Yahoo and federalreserve.gov. I tried Agent Hub and the
bitget-signal Skills and couldn't use them: api.bitget.com doesn't resolve from
my machine, a DNS failure rather than a key problem.

## Part 5 · Your take on AI Trading

The most useful thing AI did on this project was kill my idea. I was pleased with
a 79% convergence rate; the test asking which leg converged took it apart in
about ten minutes. I'm not sure I'd have written that test as honestly, or as
early, on my own.

So what I want more of isn't idea generation — ideas are free, and mine was
wrong. It's automated falsification: pre-registered holdouts, decomposition
before belief, sample size printed next to the statistic. The bottleneck was
never thinking of something. It's finding out you were wrong before the market
charges you to learn it.

On the 7×24 framing: the interesting thing isn't more trading hours. It's that
tokenized equities create windows where one venue prices an asset completely
alone, and that is exactly where the assumptions every retail tool rests on
quietly stop holding.
