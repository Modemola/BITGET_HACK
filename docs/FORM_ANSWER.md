# Project Description — paste verbatim into the Google Form

The form asks for **five** parts, not the six `SUBMISSION.md` is structured
around. It says plainly: *"Do not repeat your deliverables list here"* (separate
field) and *"GitHub, X, or external documents cannot replace this answer"* (so
paste, never link).

First person singular. Change "I" to "we" if entering as a team.

---

## Part 1 · Thesis

I set out to build a trading strategy. It didn't work, and the tool is what came
out of finding that out properly.

Tokenized US stocks trade around the clock; the market that prices them doesn't.
CME Globex closes Friday at 17:00 New York time and doesn't reopen until Sunday
at 18:00. For those 49 hours an rToken is the only venue on earth quoting US
equity exposure. No cash market, no futures, nobody able to hedge or redeem. I
assumed a thin, retail-only venue trading alone must misprice, and went looking
for the trade.

The premium does widen as venues shut. Dispersion goes from 0.42% in the cash
session to 0.51% overnight to 0.70% in a blackout, and the half-life stretches
from 0.2 hours to 1.0 to 6.0. Across 28 weekends the gap narrowed at the reopen
79% of the time. I was pleased with that for about a day.

Then I asked not "did the gap close" but "which side closed it". Between 78% and
98% of the convergence happens because fair value catches up to the token, not
because the token corrects. The reference was asleep; the token was already
right. The leg you can actually trade wins 46.4% of the time and loses 0.083%
per weekend after 10bp of costs. I tried four versions of the idea, including
trading the futures side instead, and they all agreed. Signals got worse at
stronger thresholds, which is what noise does and an edge doesn't.

So the premium is an information lead, not a mispricing. That makes it dangerous
rather than useless, because it looks exactly like free money. Blackout Desk
prices the risk someone is carrying through the window and tells them the gap is
not a trade, with the working shown.

Existing tools can't do this because they assume an opening bell. Trackers show a
price that has been stale since Friday. Risk calculators assume you can sell.
Nothing reasons in closure windows, because until rToken there was nothing to
reason about.

## Part 2 · Target user and product value

Self-directed retail traders holding $10,000 to $500,000 of tokenized US stock
across a weekend. Their own money, on Bitget or on-chain. Days-to-weeks holds,
directional long in single names, sometimes levered, never market-neutral. No
risk desk, no Bloomberg; position sizing comes from instinct.

The range is chosen, not decorative. Below $10,000 the weekend gap is noise.
Above roughly $500,000 the books are too thin to act on anything the tool says —
the deepest NVDAx pool is about $2.1m, so a large position can't be hedged or
exited during a blackout regardless.

Two reasons they need it. First, they sleep through 49 hours they cannot watch,
and 39% of weekends end with the price more than 1% from where the reference left
it. The worst in my sample was 2.14%, which is $5,350 on a $250,000 position.
Nobody has ever shown them that distribution.

Second, they are exposed to one expensive mistake: reading a 1% weekend premium
as an arbitrage. It's wrong, and it costs money gradually rather than
dramatically, so it can take years to notice. Plenty of tools will show you the
premium. None of them tell you where it came from.

## Part 3 · Validation data and key metrics

The research is measured; the product usage isn't. Labelled accordingly.

Observed:

- 1 March to 14 September 2026. 197 days, 4,702 hourly bars of NVDAx joined to
  NVDA, NQ and ES futures, and BTC/ETH.
- 28 weekend blackouts. I report windows rather than bars throughout, because
  158 hourly bars from one weekend are not 158 independent observations.
- Dispersion 0.42% cash / 0.51% weeknight / 0.70% blackout. AR(1) half-life
  0.2h / 1.0h / 6.0h.
- Drift across a blackout: 0.86% mean absolute, 1.94% at the 95th percentile,
  2.14% worst, 39% of weekends beyond 1%.
- The tradeable leg: 46.4% hit rate, -0.083% per weekend net of 10bp. Token share
  of the convergence 6%, 22% and 2% at one, six and twelve hours.
- Hedges live during a blackout: BTC +0.66, ETH +0.60, TSLAx +0.78, none of them
  stable. The tool reports the instability instead of recommending them.
- 148 tests, including one that fails if the prose in the docs drifts away from
  the numbers in the data.

All of it regenerates from committed raw data with one script. The whole argument
is that the figures are checkable, so a screenshot was never going to do.

Observed usage: none. Zero test users. I built this inside the competition window
and haven't put it in front of anyone. I'd rather say so than invent a number.

Targeted, first 60 days: 50 people complete a closure-window assessment, 40%
return for a second weekend, under 3 minutes from landing to a sized answer.

Validation plan: 10 to 15 traders holding rToken over one weekend. Before they
open the tool, ask how far they think the position can move by Monday and whether
the premium is worth trading. Show them the tool. Ask again. Count how many
change their answer. That's the product's actual claim and one weekend tests it.

On distribution: volume is the wrong metric for a tool whose job is to prevent
trades. Retention across weekends is the right one — did they come back the
following Friday.

## Part 4 · Progress

Built: seven tools, the analytics engine, the data pipeline, and the page on two
deployments — a plain static URL, and a Claude artifact carrying the
natural-language layer. 148 tests, CI on Ubuntu and Windows, and a weekly job
that refreshes data and opens a pull request showing which figures moved.

Not built: user testing. The event calendar covers FOMC only — I required
anything in it to come from the issuing authority rather than a scraped
aggregator, and doing the Fed properly used the time I had.

Problems worth naming:

The strategy failing. I had the data spine and the fair-value model finished
before the decomposition showed there was no trade in it.

pandas 2 infers microsecond resolution from a timestamp string, so `.asi8`
returned microseconds against nanosecond calendars. It doesn't raise; it silently
puts everything in 1970. I found it through a 481,662-hour countdown.

GeckoTerminal caps a page at 1000 bars. My first probe asked for 1000, got 1000,
and concluded the history was 41 days long. That false negative nearly killed the
project on day one.

A bare NaN in the payload makes JSON.parse fail, which renders the page entirely
blank with nothing in the console.

Next: user testing, more of the calendar, and sub-hourly data if I can source it.
Everything here is hourly and I can't say what happens inside the hour.

Stack: Python with pandas, numpy and exchange_calendars for the NYSE and CME
session calendars. Claude for the language layer through the artifact runtime.
Data from GeckoTerminal, Yahoo, and federalreserve.gov.

Bitget tools: I tried to use Agent Hub and the bitget-signal Skills and couldn't.
api.bitget.com doesn't resolve from my machine — a DNS failure, not a key
problem — so I could not authorise an Agentic account. I'd rather say that than
claim an integration I don't have.

## Part 5 · Your take on AI Trading

The most useful thing AI did on this project was kill my idea.

I was pleased with a 79% convergence rate. The test that asked which leg
converged took it apart in about ten minutes. I'm not sure I'd have written that
test as honestly, or as early, on my own. Everything about a backtest wants to
flatter you, and the work that argues back is slow and easy to skip when the
first result looks good.

So what I'd want more of isn't idea generation. Ideas are free, and mine was
wrong. It's automated falsification: pre-registered holdouts, decomposition
before belief, sample size printed next to the statistic instead of buried under
it. The bottleneck for a retail trader was never thinking of something. It's
finding out you were wrong before the market charges you to learn it.

On the 7x24 framing: the interesting thing about tokenized equities isn't more
trading hours. It's that they create windows where one venue prices an asset
completely alone, and those windows are exactly where the assumptions every
retail tool was built on quietly stop being true.
