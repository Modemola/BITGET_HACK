# Bitget AI Base Camp Hackathon S2 — Consolidated Brief

> Source: official S2 handbook (bitget-ai.gitbook.io/bitgetai_hackathons2), reorganized.
> All dates UTC+8. Compiled 2026-09-10.

---

## 0. TL;DR — the five things that actually matter

1. **We have 11 days.** Deadline is 21 Sep 2026. Today is 10 Sep.
2. **The Agentic Trading track needs a paper-trading log that runs in wall-clock time.** Handbook recommends ≥2 weeks; starting 9/3 was the minimum. We cannot get 2 weeks anymore. If we pick that track, logging must start *today* (≈11 days) and we accept a soft-requirement miss.
3. **Alpha Factory has no wall-clock dependency** — its ≥60-day backtest is historical data. It is the only track fully achievable from a standing start today, and it is scored **purely quantitatively** (no judge taste, no popularity).
4. **A team may enter 2 different themes as 2 independent projects** = two independent shots at a 500 USDT Theme Prize. Theme Prizes are 1-winner-per-sub-theme, so *sub-theme selection is an EV decision, not a labelling decision*.
5. **An X post is a hard validity gate.** No compliant X post = invalid submission, not scored at all. Build-in-public also has its own 300 USDT prize.

---

## 1. Event fundamentals

| Item | Detail |
|---|---|
| Name | Bitget AI Base Camp Hackathon **Season 2** |
| Theme | AI × US stock trading, incl. tokenized US stocks (**rToken**) and related contract scenarios |
| Framing thesis | Tokenized US stocks trade 7×24 while native equities don't. Macro events keep firing on weekends. Humans sleep; agents don't. |
| Period | **3 Sep – 21 Sep 2026** (submission deadline 9/21) |
| Format | Global, online |
| Prize pool | 50,000 USDT total |
| Organizer | Bitget |
| Token sponsor | Alibaba Cloud Qwen |
| Partners | Bitget Wallet, Foresight, Arbitrum, Solana, Tether Foundation, Kaito AI, Cysic, Wave, 706, + 7 university blockchain associations |
| Registration | None separate — **submitting the form IS registering** |
| Stated preference | "Real, runnable strategies and tools" |

### 1.1 Timeline

| Date | Milestone |
|---|---|
| Sep 3 | Opens. Submissions + Qwen credit applications open. Start posting on X. |
| Sep 3 – 21 | Build period. Submit any time. |
| **Sep 21** | **Hard submission deadline.** Bitget then publishes all valid project IDs. |
| Sep 22 – 28 | Public voting on X (comment project ID under Bitget's voting post) |
| Sep 22 – 28 (or – Oct 7, see §7) | Judge review — runs in parallel with voting, neither replaces the other |
| Oct 8 | Winner list announced |
| From Oct 9 | Demo Day, Spotlight content, prize payouts |

**Days remaining as of 2026-09-10: 11.**

---

## 2. Prize structure decoded

### 2.1 Judge-decided prizes (work quality)

| Award | Slots | Per winner | Basis |
|---|---|---|---|
| **Grand Prize** | 1 | 3,000 USDT | Best overall, across the whole hackathon |
| **Theme Prize** | 15 | 500 USDT | 5 named sub-themes × 3 tracks, **1 winner per sub-theme** |
| **Open Theme Prize** | 6 | 500 USDT | 2 open slots per track, top 1 each — **no 1st/2nd/3rd tiering** |

### 2.2 Other participant prizes

| Award | Slots | Per winner | Basis |
|---|---|---|---|
| **University Special Prize** | 10 | 500 USDT | Separate review layer over entries that filled the "University Name" field |
| **Best Spread Award** | 3 (1/track) | 300 USDT | X reach data of *your own / team's* posts. KOL/KOC ghost-posting excluded. |
| **Fan Favorite Prize** | 3 (1/track) | 300 USDT | Highest-voted project per track, public vote |

### 2.3 Audience prizes (voters, not builders)

| Award | Trigger | Pot |
|---|---|---|
| Lucky Draw | You voted for a project that becomes a Fan Favorite | 1,000 USDT, 50 random winners × 20 USDT |
| Prediction Prize | You voted for the project that wins Grand Prize | 1,000 USDT split among the **earliest 50** voters |

### 2.4 Exclusivity & stacking rules

- **Judge side, same entry: only the highest tier counts.** Grand Prize > Theme/Open > Best Spread.
- **University Special Prize is mutually exclusive with main-track prizes** — if you already won Grand/Theme/Open, you're out of the university pool. (It is *not* exclusive with a Demo Day invite.)
- **Fan Favorite stacks with everything** — all judge prizes and University.
- **Different themed entries from the same team are evaluated and awarded separately.** Entry A can win a Theme Prize while Entry B wins another.

**Practical max for a two-entry non-university team:** Theme/Open Prize on entry A (500) + Theme/Open Prize on entry B (500) + Fan Favorite (300) = 1,300 USDT, or 3,000 + 500 + 300 = 3,800 if one entry takes the Grand Prize.

### 2.5 Non-cash upside (arguably the real prize)

| Benefit | Detail |
|---|---|
| Official Spotlight | From 10/9: interviews, long-form articles, tweet series. High-quality non-winners may get short-form exposure too. |
| Demo Day | Open to **all** submitting teams (checkbox in form); winners/high scorers get priority. Routes to internships, product beta, investor networks. |
| Ecosystem exposure | Official RTs, partner/KOL amplification. Teams that build in public well get picked up. |
| **Playbook productization** | High-quality entries suitable for strategy productization may be invited into Bitget Playbook's product review and listing process — **with a possible commercial / revenue-share arrangement** if listed and distributed. Subject to separate negotiation; not guaranteed. |
| Qwen build credits | First 300 teams that apply + pass Bitget KYC → 30U-equivalent Qwen credits (separate form) |
| K3 post-event subsidy | Opt in via checkbox on the submission form → 30U-equivalent K3 credits. Both programs → up to 60U total. |

---

## 3. The three tracks

| Track | Pick this if… | Scoring mechanism |
|---|---|---|
| 🟦 **Alpha Factory** (Quant Strategies) | You want verifiable US-stock quant/algo strategies. AI is a *tool* for building them. | **100% quantitative** |
| 🟩 **Agentic Trading** (Agent Trading) | You want the LLM to be the *decision-maker* — sensing, judging, executing autonomously with risk controls. | **50% quantitative + 50% judge** |
| 🟧 **AI Trading Desk** (AI Research Workbench) | You want an AI research tool where the **human** makes the final call. | **100% judge subjective** |

---

### 3.1 🟦 Track 1 · Alpha Factory

**Positioning:** Runnable US-stock quantitative / algorithmic strategies. AI writes code, optimizes parameters, generates signals. The core judged object is **strategy effectiveness and verifiability**.

**Sub-themes (5 named + Open):**

| Sub-theme | Core logic | Example approaches |
|---|---|---|
| **Arbitrage** | Instantaneous spreads between rToken and native stock / across platforms; NAV premium-discount arbitrage under mint/redeem mechanics | Sell when rToken > NAV via mint; cross-platform spreads; same underlying, different issuers (Ondo, xStocks, …) |
| **After-Hours Information Pricing** | Macro events keep happening while US markets are shut; rToken trades 7×24 and prices that information in advance | Build rToken positions on weekend geopolitical/policy events; hedge after overnight macro decisions; close before Monday open |
| **Cross-Market Correlation** | Correlation shifts between rToken and native stock across time periods; rToken ↔ crypto cross-asset correlation | Pre/post-market pairs trading; mean-reversion when rToken overreacts to a macro shock the native stock hasn't priced |
| **rToken Factor Strategies** | Traditional factors behave differently in rToken's low-liquidity, retail-dominated microstructure | rToken momentum vs native stock; mean reversion in closed-market windows; factor divergence arbitrage |
| **Cross-Asset Allocation / Rotation** | Asset switching driven by macro factors, capital flows, risk appetite | Risk-on/off rotation (US stocks ↔ crypto ↔ commodities); sector rotation; weekend hedging |
| **Open Theme** | Anything else centered on US-stock AI quant. Handbook *examples*: execution-aware alpha (fees, slippage, funding, market impact, strategy capacity); market-regime / adaptive portfolio systems | — |

**Required materials:**
- Alpha source description (signal / spread logic) → in Project Description
- Strategy code → link in Submission Materials
- **Backtest record: total period ≥ 60 days, out-of-sample ≥ 30 days.** Market-making strategies may substitute continuous high/low-volatility environment records.
- Compliant X post

**Judging focus:** Sharpe, Sortino, max drawdown, turnover; **out-of-sample Sharpe decay (alert threshold: OS < 0.5 × IS)**; rolling 30-day Sharpe stability.

> ⚠️ That decay threshold is an explicit anti-overfitting tripwire. A beautiful in-sample curve that halves out-of-sample is a scored failure, not a neutral result.

---

### 3.2 🟩 Track 2 · Agentic Trading

**Positioning:** The LLM is the **primary trading decision-maker**, not an assistant. It must sense the environment, judge independently, and autonomously place orders under risk controls.

**Sub-themes (5 named + Open):**

| Sub-theme | Core question | Example approaches |
|---|---|---|
| **Event-Driven Agent** | How do news / announcements / macro events drive autonomous agent trading? | Policy speech → LLM interpretation → rebalance; earnings beat → add; rate decision → hedge rotation |
| **Market Sentiment Agent** | How does real-time social / forum / X sentiment become position signals? | FOMO detection → contrarian hedge; sentiment-top detection; de-risk before overheating |
| **Earnings-Driven Agent** | How does the agent interpret earnings / conference calls and execute autonomously? | EPS beat → add; guidance cut → reduce; post-earnings-announcement drift tracking |
| **Cross-Asset Execution Agent** | How does the agent manage rToken and crypto positions simultaneously? | Hedge crypto on rToken anomalies; dynamic cross-market allocation after macro shocks |
| **Factor Discovery Agent** | Can the agent propose hypotheses, discover alpha factors, and turn them into trades? | Agent proposes hypotheses → mines factors → backtests iteratively → trades after self-validation |
| **Open Theme** | LLM-autonomous decision-making + agent system with trading output. Handbook *example*: agent evaluation / benchmarks (decision consistency, risk-violation rate, max drawdown, stress behaviour, human-takeover rate, incremental value over fixed-rule or Human+AI baselines) | — |

**Required materials:**
- Runnable Demo
- Event → decision → execution flow demonstration (in Project Description; optional video/demo link)
- **Paper trading log, actually run during the competition period, recommended ≥ 2 weeks** (handbook notes "starting 9/3 meets minimum duration")
- Compliant X post

**Judging focus:** paper-trading Sharpe, max drawdown, win rate; **decision explainability**; agent architecture quality; risk-control layer effectiveness.

> ⚠️ **This is the track with a hard clock.** Starting 10 Sep gives us at most 11 days of log against a "recommended ≥2 weeks". Not disqualifying (the hard requirement is only "run during the competition period"), but it is a visible shortfall on a 50%-quantitative track. Every hour of delay makes it worse.

---

### 3.3 🟧 Track 3 · AI Trading Desk

**Positioning:** A natural-language-driven AI research workbench. AI processes information, invokes tools, presents analysis. **The human trader decides.**

**Sub-themes (5 named + Open):**

| Sub-theme | Core question | Example approaches |
|---|---|---|
| **Information Extraction & Signal Generation** | How does AI process unstructured earnings / macro / news? | Conference-call summary + expectation-gap detection; rate/inflation/geopolitical transmission chains |
| **Review & Self-Evolution** | After trading, how does AI help the trader review and iterate their research framework? | Auto-generated review reports; identify bad decision patterns; reusable checklists |
| **Decision Stress Testing** | Before opening a position, how does AI retrieve historically similar scenarios? | Input trade idea → retrieve historical distribution; preset stress tests |
| **Personalized Research Workbench** | How to build a customized workbench with a clear thesis? | Tech-stock event-driven workflow; macro quant toolset |
| **Execution Assistance** | After the trader decides, how does AI handle order splitting and slippage? | Large-order splitting; order-book depth analysis; slippage-pattern adjustment |
| **Open Theme** | AI-assisted tools / workbench / LUI for human traders. Handbook *example*: a portfolio-aware AI PM / Portfolio Copilot evaluating how a proposed trade changes beta, sector and factor exposures, correlation and concentration across an existing portfolio, with stress tests or hedge suggestions | — |

**Required materials:**
- Accessible Demo
- One **complete** research task demonstrated end-to-end (question → actionable insight)
- Compliant X post

**Judging focus:** feature depth (**number and effectiveness of data sources / Skill integrations**), research quality, LUI fluency, personalized thesis.

---

## 4. Submission mechanics

**Portal:** Google Form — https://forms.gle/GyWZCMCPocgJdJon6 (CN and EN versions, identical fields)

### 4.1 Form fields

| Field | Req | How to fill |
|---|---|---|
| **Project Description** | ✅ | One long-form answer, six parts (§4.2). GitHub / X links **cannot substitute**. |
| **Role of the LLM in Your Project** | ✅ | What the model actually does (coding, extraction, signal reasoning, agent decisions) and which models. If you got Qwen credits: where you used Qwen and whether it met your needs. Skip that part if you didn't. |
| **Submission Materials Link** | ✅ | Single field for demo / code / video / docs / logs |
| **X Promotional Post Link** | ✅ | Must contain `#BitgetHackathon` + `@Bitget_AI`, and be an interactive promotional post introducing the product/agent/strategy |
| **Track → Sub-theme** | ✅ | Track first, then sub-theme |
| University Name | ⚪ | Full school name → enters the university pool. Blank = not evaluated. |
| Apply for Demo Day | ⚪ | Any team may check. Blank = No. |
| Apply for K3 Token Subsidy | ⚪ | Opt in for 30U-equivalent K3 credits |

### 4.2 Project Description — the six parts

**Judges weigh the first three most heavily.**

| Part | What a good answer looks like |
|---|---|
| **1 · Thesis** *(highest weight)* | Why you built this and the core hypothesis. **Strategy entries:** signal sources, decision logic, risk controls. **Tool entries:** the pain point found and why existing solutions fall short. |
| **2 · Target user & product value** | A *concrete segment* — Retail / VIP / Pro + risk appetite, capital size, trading frequency, primary market, use case. **"All traders" is explicitly not accepted.** Plus why that segment needs it. |
| **3 · Validation data & key metrics** | Strategy/Agent: test period, returns, Sharpe/Sortino, max drawdown, win rate, turnover, **plus fee and slippage costs**. Tools: test users, task completion rate, usage data. **Label every figure observed / estimated / targeted.** No data yet → describe the validation plan. Then explain how you'll prove effective usage or distribution (users onboarded, volume, AUM, retention). |
| **4 · Progress** | Built vs not built, problems and fixes, next steps; frameworks / models / APIs used |
| **5 · Deliverables** | Enumerate what's behind the Submission Materials Link so judges can find it |
| **6 · Your take on AI Trading** *(optional)* | Experience with Bitget AI tools, or your view on agentic trading |

### 4.3 Validity gates — an entry is **invalid and unscored** if it lacks:
- a compliant X post, **or**
- the project description, **or**
- accessible submission materials.

Weak productization/validation answers don't invalidate — they "noticeably lower your score."

### 4.4 Multi-entry rules
- Max **2 different themes** per team.
- Each is an **independent project** with its own full material set, submitted through a **separate form submission**, under a **different project name**.
- Keep the **same Bitget UID / team info** across both.
- Awards computed per entry.

### 4.5 No S1 reuse
Direct ports of S1 entries, or renames / minor edits, are **not accepted**. Continuing an S1 direction requires describing substantive new additions in the form; judging is based on the new content only.

---

## 5. Developer toolkit

### 5.1 Bitget Agent Hub — https://github.com/BitgetLimited/agent_hub

Trading tools platform for AI developers: operate a Bitget account from inside Claude, Cursor, Codex, etc.

| Module | Contents |
|---|---|
| **MCP Server** | One-line config for Claude Desktop / Cursor / Windsurf / ChatGPT Desktop |
| **CLI** | `bgc` terminal trading tool for Claude Code / Codex CLI / OpenClaw |
| **Tools** | 89 UTA v3 operations (market data, spot, futures, account & funds, sub-accounts, loans, tax) condensed into **14 intent verbs**; agents follow discover → drill down → execute |
| **Skills** | Trading Skills (when to call a tool, whether to confirm before ordering) + `bitget-signal`'s 5 research Skills |
| **Agentic Account** | Dedicated agent sub-account — fund isolation, quota control, no withdrawals, OAuth (no manual API key) |
| **Market & Account Data** | Real-time market/account/trade data for crypto and US stocks (**US stock futures live; spot on the roadmap**) |

**Auto-install prompt:**
```
Please read https://www.bitget.careers/support/articles/12560603894122
and help me complete the Bitget Agentic account authorization process.
```

**Safety flags (strongly recommended during the hackathon):**
- `--read-only` → fully read-only session
- `--paper-trading` → routes to Bitget's Demo environment (**requires a separate Demo API key**). This both validates the pipeline and **produces exactly the paper-trading logs the Agentic Trading track requires.**
- High-risk ops (`cancelAll`, withdrawals) require explicit confirmation by default; any write can be previewed with `dryRun`.

**`bitget-signal` research Skills — no account or API key needed:**

| Skill | Capabilities |
|---|---|
| `macro-analyst` | Macro & cross-asset: Fed policy, BTC vs DXY / Nasdaq / Gold |
| `market-intel` | On-chain & institutional: ETF flows, whale activity, DeFi TVL |
| `news-briefing` | News aggregation & narrative synthesis; morning briefings, keyword search |
| `sentiment-analyst` | Fear & Greed Index, long/short ratio, funding rates |
| `technical-analysis` | 23 indicators across 6 categories |

**Official per-track tip:** Alpha Factory → use Playbook for backtesting. Agentic Trading → run on an Agentic account (isolated funds), flow built on Agent Hub Tools + MCP. AI Trading Desk → use `bitget-signal` Skills as the perception layer.

### 5.2 Bitget Playbook
AI-driven quant strategy platform: describe an idea in natural language → AI generates an executable strategy → backtest on real historical data → PnL, max drawdown, Sharpe → one-click deploy. Log in with a Bitget account. Directly usable for Alpha Factory backtesting/validation.

### 5.3 Qwen token subsidy
First 300 teams that apply + pass Bitget KYC → **$30 USD equivalent** in Qwen credits, keyed to the **team captain's UID**. Bitget verifies KYC every 24h; claim from a Telegram admin once approved.

- **Eligible tools: Cursor, Codex and similar coding agents. Claude Code is NOT supported at this time.**
- Applying is **not** registration — you must still submit normally.

**Qwen setup:** Base URL `https://hackathon.bitgetops.com/v1`, recommended model `qwen3.8-max`.

<details>
<summary>Codex config</summary>

```toml
model = "qwen3.8-max"
model_provider = "bitget-qwen"

[model_providers.bitget-qwen]
name = "Bitget Qwen"
base_url = "https://hackathon.bitgetops.com/v1"
env_key = "BITGET_QWEN_API_KEY"
wire_api = "responses"
```
Key goes in the environment, never in `config.toml`:
```
launchctl setenv BITGET_QWEN_API_KEY 'your real key'
launchctl getenv BITGET_QWEN_API_KEY
```
Then fully quit Codex (Cmd+Q) and reopen. Verify: bottom-right shows `Bitget Qwen`; or
`/Applications/Codex.app/Contents/Resources/codex doctor | grep model` → `qwen3.8-max`.
</details>

<details>
<summary>Cursor config</summary>

Cursor Settings (`Cmd+Shift+J` / `Ctrl+Shift+J`) → Models → paste key into OpenAI API Key → Verify →
enable **Override OpenAI Base URL** → `https://hackathon.bitgetops.com/v1` (the `/v1` suffix is required) →
`+ Add model` → `qwen3.8-max` → enable → select in Chat/Agent and test.
</details>

---

## 6. Resources

| Resource | Link |
|---|---|
| Submission form | https://forms.gle/GyWZCMCPocgJdJon6 |
| Qwen credits form | https://forms.gle/2QeJpvGB5VpipqQ68 *(see §7 — handbook is self-contradictory here)* |
| Telegram community | https://t.me/+o1tYqQ_lXxllYjgy |
| Landing page | https://www.bitget.com/activity-hub/hackathon |
| S2 handbook | https://bitget-ai.gitbook.io/bitgetai_hackathons2/ |
| Agent Hub | https://github.com/BitgetLimited/agent_hub |
| Playbook | https://www.bitget.com/zh-CN/activity/ai-get-agent/playbook?tab=explore |
| Official X | https://x.com/Bitget_AI |
| Voting post | TBD, published from 9/22 |

---

## 7. Contradictions and gaps in the source material

Flagged so we don't plan against a number that turns out wrong. Worth confirming in the Telegram community.

| # | Issue |
|---|---|
| 1 | **Judge review window.** Ch. II says 9/22 – 10/7. Ch. III timeline says 9/22 – 9/28. |
| 2 | **Voting window.** Stated as 9/22 – 10/7 in two places and 9/22 – 9/28 in two others. **Plan against 9/28** as the safe close. |
| 3 | **Sub-theme count.** Ch. II says 15 named sub-themes (5 × 3 tracks) + 3 Open. The form-field table says "18 named topics + 3 Open Themes". Track chapters confirm 5 named + 1 Open per track → **15 named + 3 Open**. The "18" appears to double-count. |
| 4 | **Qwen form link.** Ch. II links `forms.gle/2QeJpvGB5VpipqQ68`; Ch. III links the *submission* form for the same purpose. The `2Qe…` link is likely correct. |
| 5 | **K3 row mislabelled.** The form-field table's "Apply for K3 Token Subsidy" row is described as "Qwen credits use a separate application form, not this one" — text belonging to a different row. K3 is a checkbox on the submission form. |
| 6 | **Prize pool math.** Enumerated awards total **22,300 USDT** of the stated 50,000. ~27,700 is unallocated in the handbook. |
| 7 | **Announcement date.** Timeline says Oct 8; Ch. II says audience prizes announced "from 10/9"; Ch. III says "around 10/8". |
| 8 | **Qwen model names.** `qwen3.8-max` is given both as the standard model and as "the fast variant" — apparent copy-paste error. |
| 9 | **Missing content.** Submission FAQ (Ch. IV) and Ch. VI FAQ are empty in the source; the official post link and voting post link are both TBD. |

---

## 8. Strategic read

### 8.1 Track feasibility given 11 days

| Track | Wall-clock blocker | Verdict |
|---|---|---|
| 🟦 Alpha Factory | None — the ≥60d backtest / ≥30d OOS is historical data | **Fully achievable.** Only risk is data sourcing (§8.3). |
| 🟩 Agentic Trading | Paper-trading log must accrue in real time; ≤11 days vs "recommended ≥2 weeks" | **Achievable with a visible shortfall.** Viable only if logging starts immediately. |
| 🟧 AI Trading Desk | None — demo + one research task | **Fastest to build**, but 100% subjective scoring and the lowest barrier to entry, so likely the most crowded field. |

### 8.2 Where the expected value is

- **Theme Prizes are 1-winner-per-sub-theme.** 15 separate single-winner contests. Entering a sub-theme that attracts 8 entries instead of 60 is worth more than any amount of extra polish. Likely crowded: *Event-Driven Agent*, *Market Sentiment Agent*, *Arbitrage*, *Information Extraction*. Likely thin: *rToken Factor Strategies*, *Cross-Market Correlation*, *Decision Stress Testing*, *Review & Self-Evolution*, *Execution Assistance*, *Factor Discovery Agent*.
- **Open Theme is a trap for the median entry and a prize for the exceptional one.** Two slots per track, no tiering, and it will absorb every entry that didn't fit a named box plus every ambitious project. A named sub-theme is the higher-probability route to 500 USDT.
- **Two entries = two independent shots.** The obvious structure is one entry in each of two different sub-themes, ideally sharing infrastructure so the marginal cost of the second is low.
- **Alpha Factory's pure-quant scoring is the most legible path to winning on merit** — no dependence on judge taste, demo polish, or follower count. It is also the track where a bad result is unambiguous.
- **Fan Favorite stacks with everything** and costs only distribution effort, which we owe the X requirement anyway.

### 8.3 Open questions to resolve before committing

1. **rToken data availability.** Agent Hub lists US stock *futures* as live and *spot* as roadmap. Alpha Factory's arbitrage/factor/correlation sub-themes all assume rToken price history. Where does ≥60 days of it come from — Playbook, Agent Hub, or a third-party source? This is the single largest technical risk and should be settled first.
2. **Do we have a Bitget account + UID, and can we complete KYC?** Needed for Playbook, the Agentic account, and Qwen credits.
3. **Does the team qualify for the University pool?** If yes, note that it's mutually exclusive with main-track prizes — it's a floor, not an addition.
4. **X account reach.** Best Spread is judged on our own posts, not KOL amplification. Realistic assessment needed.

### 8.4 Immediate actions (time-sensitive, in order)

1. **Post on X today** — retweet the official post, introduce what we're building, `#BitgetHackathon` `@Bitget_AI`. It's a validity gate and a scored prize, and reach compounds over days we don't have many of.
2. **If Agentic Trading is in scope, stand up the paper-trading harness and start logging today.** Every day of delay is permanently lost log length.
3. Join the Telegram community; resolve the §7 ambiguities and the §8.3 data question.
4. Apply for Qwen credits only if we'll actually use Cursor or Codex — **Claude Code is not supported**, so the credits may be worth little to our workflow. The K3 checkbox is free and should just be ticked.
5. Set up the Bitget Agentic account (OAuth, isolated funds) and a Demo API key for `--paper-trading`.
