# Project Description — paste verbatim into the Google Form

The form's "Project Description" field asks for **five** parts, not six. Its own
instruction is explicit: *"Do not repeat your deliverables list here — list them
line by line under 'Submission Material Links.'"* So Deliverables, which
`SUBMISSION.md` carries as its Part 5, is a **separate field** and must not
appear below.

The same field says *"GitHub, X, or external documents cannot replace this
answer."* A link is not a valid submission. Paste the whole thing.

Written first person singular. If entering as a team, change "I" to "we"
throughout.

---

## Part 1 · Thesis

I set out to build a trading strategy. It didn't work, and the tool is what came
out of finding that out properly.

The starting idea was simple. Tokenized US stocks trade around the clock, but the
market that prices them doesn't. Every Friday at 17:00 New York time CME Globex
closes, and it doesn't reopen until Sunday at 18:00. For those 49 hours an rToken
is the only thing on earth quoting US equity exposure. No cash market, no
futures, no options, nobody able to hedge or redeem. That sounded like an obvious
place to find mispricing. Thin book, retail flow, no arbitrageurs. So I went
looking for the trade.

The premium does behave the way you would expect. Over 197 days of hourly data,
dispersion widens from 0.42% during the cash session to 0.51% overnight to 0.70%
inside a blackout. It also gets stickier as venues shut: the half-life goes from
0.2 hours to 1.0 to 6.0. Divergence builds through the weekend, and across 28
weekends the gap narrowed at the reopen 79% of the time. I was fairly pleased
with that for about a day.

Then I ran the test that mattered, which was not "did the gap close" but "which
side closed it". You can split the convergence into the leg you can trade and the
leg you can't. Between 78% and 98% of it happens because fair value catches up to
the token, not because the token corrects. The reference was asleep. The token
was already right. The leg you can actually trade wins 46.4% of the time and
loses 0.083% per weekend once you pay 10bp of costs. I tried four versions of the
idea, including trading the futures side instead, and they all agreed. The
signals got worse at stronger thresholds, which is what noise does and what a
real edge doesn't.

So the hypothesis inverted. The weekend premium isn't a mispricing, it's an
information lead. And that makes it worse than useless to a trader, because it
looks exactly like free money to anyone who notices it.

That's what the tool is for. Someone holding NVDAx into a Friday close is
carrying a position they can't hedge through a third of the week with no
reference price. If they spot a 1% gap on Sunday afternoon they will probably
trade it, and they will lose slowly and quietly to fees. Blackout Desk shows them
what they are actually exposed to, and tells them the gap is not a trade, with
the working shown.

Existing tools don't do this because they were built for markets that have an
opening bell. Portfolio trackers show a last price that has been stale since
Friday afternoon. Risk calculators assume you can sell. Nothing reasons in terms
of closure windows at all, because until rToken existed there was nothing to
reason about.

## Part 2 · Target user and product value

Self-directed retail traders holding between $10,000 and $500,000 of tokenized US
stock across a weekend.

To be more specific: they trade their own money on Bitget or on-chain, they hold
for days or weeks rather than minutes, their main market is US equities through
rTokens with some crypto alongside, and their risk appetite is directional long
in single names, sometimes levered, not market-neutral. No risk desk, no
Bloomberg, no prime broker. Position sizing comes from instinct and the size of
the account.

The capital range is chosen, not decorative. Below about $10,000 the weekend gap
is noise and the tool isn't worth opening. Above roughly $500,000 the books are
too thin for anything it tells you to be actionable. The deepest NVDAx pool on
Solana is around $2.1m, so a large position cannot be hedged or exited in size
during a blackout even if the trader wants to. The people this helps are the ones
big enough for the risk to be real and small enough to still be able to act.

Why they need it comes down to two things.

First, they go to sleep on Friday holding something they cannot watch, and 39% of
weekends end with the price more than 1% away from where the reference left it.
The worst in my sample was 2.14%. On a $250,000 position that's between $2,150
and $5,350. They have no way to size that, because nobody has ever shown them the
distribution.

Second, they are exposed to one specific expensive mistake. Seeing a 1% weekend
premium and reading it as an arbitrage is the natural conclusion to draw. It's
wrong. And it's the kind of wrong that costs money gradually rather than
dramatically, so it can take a very long time to notice.

What existing tools fail at is the second one especially. Several of them will
happily show you the premium. Some will imply it's an opportunity. None of them
will tell you where it came from.

## Part 3 · Validation data and key metrics

This is a tool entry, and the honest split is that the research is measured and
the product usage isn't. Everything below is labelled.

Research, all observed:

- Test period 1 March to 14 September 2026. 197 days, 4,702 hourly bars of NVDAx
  joined to NVDA, NQ and ES futures, and BTC/ETH.
- 28 weekend blackouts. I report the number of windows rather than the number of
  bars throughout, because 158 hourly observations from a single weekend are not
  158 independent data points.
- Premium dispersion 0.42% cash, 0.51% weeknight, 0.70% blackout. AR(1)
  half-life 0.2h, 1.0h, 6.0h.
- Drift across a blackout: 0.86% mean absolute, 1.94% at the 95th percentile,
  2.14% worst, and 39% of weekends finish beyond 1%.
- The tradeable leg: 46.4% hit rate, -0.083% per weekend net of 10bp. Token share
  of the convergence 6% at one hour, 22% at six, 2% at twelve.
- Hedges available during a blackout: BTC correlates +0.66 with blackout moves,
  ETH +0.60, TSLAx +0.78. None of the three is stable across the sample, and the
  tool reports the instability instead of recommending them.
- 146 tests. Including ones that check the page's JavaScript returns the same
  answers as the Python it duplicates, and one that fails if the prose in the
  documents drifts away from the numbers in the data.

All of it regenerates from raw data with one script, and the data is committed to
the repository. That was deliberate: the entire argument is that the numbers are
checkable, so "trust the screenshot" was never going to be good enough.

Product usage, observed: none. Test users: 0. I built this inside the competition
window and haven't put it in front of anyone yet. I'd rather say that than invent
an activation number.

Targeted, first 60 days after launch: 50 people complete a full closure-window
assessment; 40% come back for a second weekend; median time from landing on the
page to a sized answer under 3 minutes.

Validation plan. The cheapest test that would actually tell me something is 10 to
15 traders who hold rToken over one weekend. Before they open the tool, ask each
of them two questions: how much do you think this position can move by Monday,
and is the premium you're looking at worth trading. Then show them the tool and
ask again. What I want to count is how many change their answer, and specifically
how many stop treating the premium as an opportunity. That's the product's actual
claim and it can be tested in a single weekend.

On proving distribution: for a tool whose job is to prevent trades, volume is the
wrong metric and I'm not going to pretend otherwise. Retention across weekends is
the right one. Did they come back the following Friday. I'd rather report a
number that only goes up when the tool is useful than one that goes up when users
lose money.

## Part 4 · Progress

Built: all seven tools, the analytics engine underneath them, the data pipeline,
and the page in two deployments. One is a plain static URL anyone can open. The
other is a Claude artifact carrying the natural-language layer, where you can ask
the desk a question and it answers using only the measurements on the page. 136
tests, CI on both Ubuntu and Windows, and a scheduled job that refreshes the data
weekly and opens a pull request showing which figures moved.

Not built: user testing, as above. The event calendar covers FOMC only. I decided
early that anything in it had to come from the issuing authority rather than a
scraped aggregator, and doing the Fed properly used up the time I had for it.

Problems, and what they cost me:

The strategy failing was the big one. I had the data spine and the fair-value
model finished before the decomposition told me there was no trade in it.
Recovering meant throwing away the premise and keeping the measurement.

pandas 2 infers microsecond resolution from a timestamp string, so `.asi8` was
returning microseconds while the exchange calendars were in nanoseconds. It
doesn't raise. It silently puts every timestamp in 1970. I found it because a
time-to-reopen came back as 481,662 hours.

GeckoTerminal caps a page at 1000 bars. My first data probe asked for exactly
1000, got exactly 1000, and concluded the history was only 41 days long. That
false negative nearly killed the project on day one. It also answers 401 rather
than 429 under load, which looks like an auth problem and isn't.

The payload could write a bare NaN, which JSON.parse rejects, which renders the
page completely blank with nothing in the console. Non-finite values now become
null and both writers refuse to emit NaN at all.

And one I only caught yesterday: a refresh moved the convergence rate from 85% to
79%, and five sentences across my own documents kept quoting the old figure. It's
now derived from the payload and pinned by a test, like the rest.

Next: user testing, more of the event calendar, and sub-hourly data if I can find
it. Everything here is measured at hourly resolution and I genuinely cannot say
what happens inside the hour.

Stack: Python with pandas, numpy, and exchange_calendars for the NYSE and CME
session calendars. Claude for the language layer, through the artifact `sample`
runtime rather than an API key, so there are no secrets in the page. Data from
GeckoTerminal for rToken, Yahoo for equities, futures and crypto, and
federalreserve.gov for FOMC dates parsed from the source.

On Bitget tools: I tried to use Agent Hub and the `bitget-signal` Skills, and
couldn't. api.bitget.com does not resolve from my machine. It's a DNS failure
rather than a rate limit or a key problem, and I ran out of time to diagnose it,
so I could not authorise an Agentic account or pull market data through it. I'd
rather state that plainly than claim an integration I don't have.

## Part 5 · Your take on AI Trading

The most useful thing AI did on this project was kill my idea.

I was excited about a 79% convergence rate. The test that mattered was the one
that asked which leg converged, and it took the excitement away in about ten
minutes. I'm not sure I would have run that test as honestly on my own, or as
early. Everything about a backtest wants to flatter you, and the work that argues
back is slow and boring and easy to skip when the first result looks good.

So the thing I'd want more of isn't idea generation. Ideas are free and mine was
wrong. It's automated falsification. Pre-registered holdouts, decomposing a
result before believing it, sample size printed next to the statistic instead of
buried underneath it. The bottleneck for a retail trader has never been thinking
of something. It's finding out you were wrong before the market charges you to
learn it.

On the 7x24 framing of this season: I think it's sharper than it first looks. The
interesting thing about tokenized equities isn't more trading hours. It's that
they create windows where one venue prices an asset completely alone, and those
windows are exactly where the assumptions every retail tool was built on quietly
stop being true. That seems like a real seam to me, and not many people are
looking at it yet.
