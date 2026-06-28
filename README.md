# Insider Signal Research Engine

A modular research engine that tests whether **publicly disclosed insider activity** (SEC Form 4
*cluster buys*) can be turned into a backtested, paper-traded signal that beats a simple S&P 500
buy-and-hold **after costs, slippage, and taxes**.

This is a hobby/learning project. The agent brief and operating rules live in
[`CLAUDE.md`](./CLAUDE.md); current state lives in [`PROGRESS.md`](./PROGRESS.md); design
choices and their rationale live in [`DECISIONS.md`](./DECISIONS.md). A skeptic-facing write-up of
method and findings so far is in [`docs/FINDINGS.md`](./docs/FINDINGS.md), and how to run the loop
durably in [`docs/AUTONOMOUS_LOOP.md`](./docs/AUTONOMOUS_LOOP.md).

## What it does (and the order it's built in)

1. **Stage 1 — Data:** ingest SEC Form 4 filings from EDGAR, parse open-market purchases
   (transaction code `P`), and store them point-in-time alongside delisting-aware prices.
2. **Stage 2 — Signal:** detect cluster buys (≥N insiders buying the same stock in a short
   window) and score them with economically-justified features.
3. **Stage 3 — Backtest:** an event-driven engine that enters on the **filing date** (never the
   transaction date), models commissions/spread/slippage/tax, splits train vs. holdout, and
   applies a pre-committed kill condition.
4. **Stage 4 — Paper trade:** forward paper-trading only. **No live orders, ever.**
5. **Stage 5 — Generalize:** swap in a congressional-trade signal on the same pipeline.

## Repository layout

```
data/       ingestion + point-in-time storage (raw filings, prices, universe)
signals/    pluggable signal modules: generate_signals(date_range) -> events
features/   scoring features (role, size, cluster size, opportunistic flag, track record)
backtest/   event-driven engine; filing-date entries; costs/slippage/tax
analysis/   metrics (CAGR, Sharpe, drawdown, hit rate, vs-SPY), tearsheets
paper/       forward paper-trading harness (NO live orders)
reports/    generated, human-readable findings
tests/      deterministic unit tests (data/ and backtest/ are where silent bugs hide)
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Status

Stage 0 (framing/skeleton) complete. See [`PROGRESS.md`](./PROGRESS.md) for the live `NEXT:`
task. The project advances one validated checkpoint at a time per the LOOP PROTOCOL in
`CLAUDE.md`.

---

## ⚠️ Disclaimer (not financial advice)

This is an educational research project using public data. It is **not financial advice** and
produces **no recommendations**. Copying public disclosures is legal; results are uncertain; even
well-designed strategies lose money in some periods. This loop stops at **paper trading** and
never submits real-money orders. Real capital, if ever, is a deliberate human decision made well
outside this automated loop.
