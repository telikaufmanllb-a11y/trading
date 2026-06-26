# CLAUDE.md — Insider Signal Research Engine

> **For the agent:** This file is your standing brief. On every session, follow the **LOOP PROTOCOL** below. Read `PROGRESS.md` first, do the next highest-value task, validate it against the **HARD RULES**, log what you did, and stop at a clean checkpoint. Optimize for *rigor and honest validation*, not for the prettiest backtest number. A strategy that looks too good is a bug to investigate, not a win to celebrate.

---

## 1. Mission

Build a modular research engine that tests whether **publicly disclosed insider activity** can be turned into a backtested, paper-traded signal that beats a simple S&P 500 buy-and-hold *after costs, slippage, and taxes*. This is a hobby/learning project that may earn money later — **only if** the evidence holds up under honest testing.

**Primary signal (start here):** Corporate insider *cluster buys* via SEC Form 4 — multiple insiders independently making open-market purchases of the same stock in a short window. This is the best-documented public-disclosure anomaly (decades of academic support; effect strongest in small/microcaps and for opportunistic, not routine, trades).

**Secondary signal (later, same engine):** US congressional trades (STOCK Act PTRs). Weaker, more crowded, more lagged — kept as a swappable module, not the focus.

---

## 2. The Hypothesis (falsifiable — this is the whole point)

> *Buying stocks where ≥3 insiders made open-market purchases within a 15-day window, filtered to opportunistic trades and weighted toward smaller-cap names, then holding for a defined period, produces positive risk-adjusted abnormal returns versus the S&P 500 — net of all costs — in out-of-sample data.*

**Falsification / kill condition (commit to this now):**
If, after correct out-of-sample backtesting, the strategy does **not** beat SPY on a risk-adjusted basis net of costs, the conclusion is "no edge" — log it honestly and do NOT keep re-tuning parameters until it looks good. Re-tuning to defeat a kill condition is the definition of overfitting.

---

## 3. HARD RULES (never violate — these protect against self-deception and real-world loss)

1. **No look-ahead, ever.** Backtest entries use the **filing date** (when the Form 4 became public), NEVER the transaction date. Every feature must be knowable at decision time. This is the #1 fatal error — guard it obsessively.
2. **Point-in-time universe.** Include delisted/bankrupt/acquired companies. A database of only-survivors silently deletes every cluster-buy that went to zero and makes any strategy look brilliant. Survivorship bias = invalid results.
3. **Model reality.** Always include commissions, bid/ask spread, slippage (especially severe in microcaps), and short-term capital-gains tax. A strategy that only wins gross is a losing strategy.
4. **Reserve a holdout.** Pick parameters on a training period; validate ONCE on a holdout period you never peeked at. Re-touching the holdout invalidates it.
5. **Guard against multiple testing.** Every parameter choice needs a *prior economic reason*, not just a better curve. Log how many configurations were tried; report results with that count in mind.
6. **Implausible = investigate.** Sharpe > 2, returns > ~30%/yr abnormal, or a suspiciously smooth equity curve are red flags for a bug (usually look-ahead or survivorship). When results look too good, STOP and audit before continuing. Flag it in `PROGRESS.md` for human review.
7. **NO LIVE TRADING.** This loop stops at **paper trading**. Never write code that submits real-money orders. Never store live brokerage credentials. Live capital is a human decision made outside this loop, after Stage 4 passes.
8. **Not financial advice.** This is a research tool. Nothing it outputs is a recommendation. Keep this disclaimer in any report or README the project generates.
9. **Reproducibility.** Every backtest run is logged with its exact config and a timestamp, and must be re-runnable to the same result (set random seeds).

---

## 4. Architecture (modularity is the most important decision)

Build so the **signal is swappable**. Same pipeline must run insider clusters today and congressional trades later with no rewrite.

```
data/        # ingestion + point-in-time storage (raw filings, prices, universe)
signals/     # pluggable signal modules; each exposes generate_signals(date_range) -> events
features/    # scoring features (role, size, cluster size, opportunistic flag, insider track record)
backtest/    # event-driven engine; consumes signals + prices; enforces filing-date entry, costs
analysis/    # metrics (CAGR, Sharpe, max drawdown, hit rate, vs-SPY), tearsheets, plots
paper/       # forward paper-trading harness (NO live orders)
reports/     # generated, human-readable findings
PROGRESS.md  # the loop's memory — current state, decisions, results, next tasks
DECISIONS.md # append-only log of design choices + the economic reason for each
```

**Order of effort:** ~80% in `data/`, `backtest/`, `analysis/`. Execution/paper plumbing is easy and comes LAST. Backtest-first, always.

---

## 5. LOOP PROTOCOL (what to do each session/iteration)

1. **Read** `PROGRESS.md` and `DECISIONS.md`. Understand current state.
2. **Self-audit** the last iteration's output against the HARD RULES before trusting it.
3. **Pick** the single highest-value next task from the Roadmap (Section 6) or the open-tasks list in `PROGRESS.md`.
4. **Implement** it in small, testable pieces. Write tests for anything in `data/` or `backtest/` (these are where silent bugs hide).
5. **Validate**: run relevant tests; if it's a backtest change, check for look-ahead and survivorship explicitly.
6. **Log**: append results, decisions (with economic rationale), and any red flags to `PROGRESS.md` / `DECISIONS.md`. Commit with a clear message.
7. **Checkpoint & stop** at a clean, working state. Leave a clear "NEXT:" line at the top of `PROGRESS.md`.
8. **Escalate, don't bulldoze**: if results look implausibly good, if you hit the kill condition, or if a HARD RULE is in tension with a task — pause and write a `REVIEW NEEDED` note for the human instead of optimizing around it.

> To run continuously: each turn, just instruct the session to "continue per CLAUDE.md LOOP PROTOCOL." The loop's durability comes from `PROGRESS.md` being its memory, not from any single long session.

---

## 6. Roadmap (stages — do not skip ahead)

**Stage 0 — Frame.** Confirm the hypothesis and rules are crisp. Create `PROGRESS.md`, `DECISIONS.md`, repo skeleton, dependency setup. Write the one-sentence hypothesis and kill condition into `PROGRESS.md`.

**Stage 1 — Data + eyeball.** Ingest SEC Form 4 filings from EDGAR. Parse open-market purchases (transaction code `P`). Get a point-in-time price source and a delisting-aware universe. Then *manually inspect* several real historical clusters — confirm the pattern looks like the literature before automating anything. Build intuition first.

**Stage 2 — Signal + features.** Implement the cluster-buy detector (configurable: min insiders, window, min $ per buy). Add features: insider role (CEO/CFO > director), trade size vs. holdings, cluster size, opportunistic-vs-routine classification, insider historical hit-rate, market-cap bucket. Keep each feature justified in `DECISIONS.md`.

**Stage 3 — Backtest (the heart).** Event-driven engine. Filing-date entries. Costs/slippage/tax modeled. Multiple holding periods (21d / 63d / 126d / 252d) since edge decays past ~6–12 months. Train/holdout split. Produce honest tearsheets vs SPY. **Apply the kill condition.**

**Stage 4 — Paper trade.** If and only if Stage 3 survives out-of-sample: forward paper-trade with a pre-committed evaluation period and stop criteria. No real orders.

**Stage 5 — Generalize.** Add the congressional-trade signal module to demonstrate swappability and compare it head-to-head with insider clusters.

---

## 7. Definition of "best thing possible"

"Best" here = **most honest and most robust**, not highest backtest return. A credible negative result ("no exploitable edge after costs") is a SUCCESS, because it saves real money and is the truthful outcome for most strategies. Success criteria, in priority order:

1. Zero look-ahead / survivorship bias (verified, not assumed).
2. Results stable across multiple market regimes (include 2022 and 2025 stress periods).
3. Edge survives realistic costs and the holdout.
4. Code is modular, tested, reproducible.
5. Findings are written up clearly enough for a skeptical reader to attack.

---

## 8. Suggested stack

Python. `pandas`/`numpy` for data; `requests` for EDGAR; `sec-edgar-downloader` or direct EDGAR full-text/submissions API for Form 4; `vectorbt` or a hand-rolled event loop for backtesting (hand-rolled gives more control over filing-date logic); `matplotlib`/`quantstats` for tearsheets; `pytest` for tests; `duckdb` or parquet for point-in-time storage. Pin versions. Set seeds.

**Data sources:** SEC EDGAR (Form 4 — free, ~2-business-day disclosure). Prices: a delisting-aware source (avoid free APIs that drop dead tickers — that reintroduces survivorship bias). Later, for the congressional module: Senate eFD / House Clerk filings or a normalized API.

---

## 9. Things to explicitly NOT do

- Do NOT submit live orders or store brokerage keys.
- Do NOT optimize parameters against the holdout or against the kill condition.
- Do NOT use a survivor-only price database.
- Do NOT enter on transaction date.
- Do NOT report gross-of-cost returns as if they were achievable.
- Do NOT trust a great-looking result without auditing for the two classic bugs first.
- Do NOT add complexity (ML models, more signals) until the simple version is correctly validated.

---

## 10. Standing caveat (keep in generated outputs)

This is an educational research project using public data. It is not financial advice and produces no recommendations. Copying public disclosures is legal; results are uncertain; even well-designed strategies lose money in some periods. Real capital, if ever, is a deliberate human decision made well outside this automated loop.

---

### Append to PROGRESS.md each cycle:
```
## [timestamp]
NEXT: <single most important next task>
DID: <what was implemented/validated this cycle>
RESULTS: <metrics, vs SPY, net of costs — or N/A>
RED FLAGS / REVIEW NEEDED: <anything implausible or rule-tension>
RULE CHECK: look-ahead [ok/risk] | survivorship [ok/risk] | costs modeled [y/n]
```
