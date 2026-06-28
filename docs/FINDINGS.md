# Findings — Insider Cluster-Buy Research Engine

*Status as of 2026-06-28. This is a living research note written to be **attacked** by a skeptical
reader (CLAUDE.md §7, criterion 5). It reports method and intermediate findings, **not** a
strategy result — there is no trustworthy backtest number yet, by design (see §5).*

> **Disclaimer.** Educational research using public data. NOT financial advice, NOT a
> recommendation. This project stops at paper trading and never submits real orders. Results are
> uncertain; even well-designed strategies lose money in some periods.

## 1. Hypothesis (falsifiable)
Buying stocks where ≥3 insiders made **open-market purchases** (Form 4 code `P`) within a 15-day
window, filtered to **opportunistic** trades and tilted to smaller caps, then held for a defined
period, produces positive risk-adjusted abnormal returns vs. the S&P 500 **net of all costs**, out
of sample.

**Kill condition (pre-committed):** if, after correct OOS backtesting net of costs, the strategy
does not beat SPY risk-adjusted → conclusion is "no edge." We log that and do **not** re-tune to
defeat it.

## 2. What is built (and tested: 95 unit tests, all green)
- **EDGAR ingest** (`data/edgar.py`, `data/form4.py`): polite cached client; daily master-index
  enumeration; Form 4 XML parsing.
- **Signal** (`signals/insider_cluster.py`): cluster detection with a **look-ahead-correct trigger
  date** — entry is the filing date at which the N-th *distinct* insider becomes public, never the
  first buy.
- **Opportunistic filter** (`features/opportunistic.py`): excludes coordinated events (see §3).
- **Backtest** (`backtest/engine.py`): filing-date entry, commission + spread + slippage + short-
  term tax, delisting-aware returns, multi-horizon (21/63/126/252d), train/holdout split.
- **Metrics + report** (`analysis/`): CAGR/Sharpe/drawdown/abnormal t-stat with **implausibility
  warnings**, and a markdown tearsheet whose verdict refuses to claim an edge from thin data.

## 3. Empirical findings so far (small samples — intuition, not measured rates)
1. **Code `P` ≠ "open market."** SEC code `P` is "open market **or private** purchase." A flagged
   15-insider cluster (First Carolina, FCBM) was 15 insiders buying at a *uniform $12.50 on one
   day* — a fixed-price offering, the opposite of independent accumulation. (DECISIONS D-0013.)
2. **Joint/affiliated filers inflate clusters.** Energizer showed an apparent 6-insider cluster
   that was **one filing with six joint affiliated owners** (one fund group). Counting reporting
   owners as independent insiders manufactures phantom clusters; we collapse joint owners to one.
   (D-0016.)
3. **Genuine clusters are rare.** In ~3,600 filings (≈2.4 trading days), 5 raw ≥3 clusters → 4
   coordinated, **1 genuine** (Lovesac/LOVE: director + President + CEO, dispersed prices/dates =
   independent accumulation). The opportunistic filter removed ~80% of raw clusters. (FINDING-2.)
   *Implication:* the tradable universe is far smaller than naive code-`P` counts, so statistical
   power will need many years of history.

## 4. Threats to validity — where a skeptic should push
- **Survivorship (biggest risk).** No trusted result exists until a **delisting-aware** price
  source is used. The yfinance prototype is survivor-biased and explicitly barred from trusted
  results.
- **Look-ahead.** Mitigated structurally (filing-date entry; trigger = N-th insider's filing) and
  unit-tested, but every new feature must be re-checked.
- **Multiple testing.** Parameters (min insiders=3, window=15d, cost levels) need prior reasons,
  not curve-fits; the holdout must be touched **once**. Tracked in DECISIONS.md.
- **Coordinated-event leakage.** The opportunistic filter is a prototype with provisional
  thresholds (price CV ≤1% AND same-window); it needs validation against labeled examples.
- **Tiny sample.** All empirical numbers above are from a few days of recent filings — directional
  intuition only, not a base rate.

## 5. Why there is no strategy result yet (and why that's correct)
A backtest run on survivor-biased data would look better than reality and violate HARD RULE 2. The
pipeline deliberately **refuses** to produce a "result" without a delisting-aware source. The next
real step is a human decision: procure such a source (e.g. CRSP / Norgate / Sharadar, or build a
survivorship-free set from SEC delistings + corporate actions). Until then, "no result" is the
honest state.

## 6. Reproducibility
Pinned `requirements.txt`; global seed in `config.py`; raw EDGAR docs cached; every design choice
logged in `DECISIONS.md` with its rationale; the loop's state in `PROGRESS.md`.
