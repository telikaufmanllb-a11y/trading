# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: Stage 1 (cont.) — wire fetch→parse for real filings, then prices + universe

EDGAR client, Form 4 parser, and deterministic tests are done (this cycle). Next highest-value:

1. **End-to-end fetch→parse of a real filing.** The submissions `primaryDocument` is the
   XSL-styled viewer path (`xslF345X06/form4.xml`); strip that prefix to get the raw parseable
   XML. Add an `EdgarClient` method that, given a Form 4 row, fetches the raw XML and returns a
   `Form4` with `filing_date` attached **from the submissions `filingDate`** (HARD RULE 1) —
   never from the XML. Cover with a test using a cached real fixture.
2. **Point-in-time price source + delisting-aware universe.** Must include delisted/bankrupt/
   acquired names (HARD RULE 2). yfinance is installed but is survivor-biased and drops dead
   tickers — decide in DECISIONS.md whether it's acceptable for an eyeball-only first pass or
   whether we need a delisting-aware source before any backtest. Do NOT let a survivor-only DB
   reach the backtest.
3. **Eyeball real clusters.** Pull a handful of historical ≥3-insider buy clusters and inspect
   them by hand; confirm the pattern matches the literature before automating the detector.

Do NOT build the cluster detector or backtest yet. Stage 1 is "data + eyeball" first.

---

## The hypothesis (from CLAUDE.md §2)

> Buying stocks where ≥3 insiders made open-market purchases (Form 4 transaction code `P`)
> within a 15-day window, filtered to opportunistic trades and weighted toward smaller-cap
> names, then holding for a defined period, produces positive risk-adjusted abnormal returns
> versus the S&P 500 — net of all costs — in out-of-sample data.

**Kill condition:** If, after correct out-of-sample backtesting, the strategy does not beat SPY
on a risk-adjusted basis net of costs → conclusion is "no edge." Log it honestly; do NOT
re-tune parameters to defeat the kill condition. (That is overfitting.)

---

## Stage status

| Stage | Description | Status |
|-------|-------------|--------|
| 0 | Frame: docs, repo skeleton, deps | ✅ done (this cycle) |
| 1 | EDGAR Form 4 ingest + point-in-time prices/universe + eyeball clusters | 🟡 in progress |
| 2 | Cluster-buy detector + features | ⬜ not started |
| 3 | Event-driven backtest (filing-date entries, costs, train/holdout, kill condition) | ⬜ not started |
| 4 | Paper trade (NO live orders) | ⬜ not started |
| 5 | Generalize: congressional-trade module | ⬜ not started |

---

## Cycle log

## 2026-06-26 — Stage 1a (EDGAR client + Form 4 parser)
NEXT: Wire fetch→parse for real filings (strip `xslF345X06/` to get raw XML; attach filing_date
     from submissions metadata), then point-in-time prices + delisting-aware universe, then
     eyeball real clusters (see top of file).
DID: Built `data/edgar.py` (read-only EDGAR client: fair-access User-Agent, <10 req/s rate
     limiter, sha256 disk cache so documents are never re-fetched, submissions-JSON fetch + Form
     4 row iterator) and `data/form4.py` (XML parser → typed `Form4`/`ReportingOwner`/
     `Form4Transaction`, open-market-purchase filter, acceptance-datetime header helper). Added a
     committed Form 4 fixture and 19 deterministic tests (parser + client cache/rate-limiter, no
     network). Also ran one live EDGAR smoke fetch by hand: client retrieved Apple's submissions
     and listed 589 Form 4s with filing dates — confirms the client works end-to-end.
RESULTS: 19/19 tests green. N/A on returns (no signal/backtest yet).
RED FLAGS / REVIEW NEEDED: None. Note (not a flag): yfinance is installed but is survivor-biased;
     it must NOT feed the backtest (HARD RULE 2). The price-source decision is the NEXT cycle's
     job and is called out above.
RULE CHECK: look-ahead [ok — parser refuses to derive filing_date from XML; filing_date comes
          only from submissions metadata, pinned by test_filing_date_is_not_invented_from_xml]
          | survivorship [ok so far — no price DB yet; flagged for next cycle]
          | costs modeled [n/a — no backtest yet]

## 2026-06-26 — Stage 0 (Frame)
NEXT: Stage 1 — EDGAR Form 4 read-only client + parser + parser unit tests (see top of file).
DID: Created repo skeleton (data/ signals/ features/ backtest/ analysis/ paper/ reports/ tests/
     as Python packages), standing docs (CLAUDE.md, PROGRESS.md, DECISIONS.md), README with the
     required disclaimer, pinned `requirements.txt`, `config.py` (paths + global RANDOM_SEED +
     seed helper), `.gitignore`, and a smoke test (`tests/test_config.py`) confirming the seed
     helper is deterministic and the package imports.
RESULTS: N/A (no data, no backtest yet — Stage 0 is framing only).
RED FLAGS / REVIEW NEEDED: None. Pinned deps were install-verified in a venv this cycle;
     surfaced a real conflict (quantstats 0.0.64 needs numpy<2.0.0) → re-pinned numpy to 1.26.4
     and logged it (DECISIONS.md D-0006). Full set now installs cleanly; pytest 4/4 green.
RULE CHECK: look-ahead [ok — no entry logic exists yet; parser will keep filing date separately]
          | survivorship [ok — no price DB yet; Stage 1 must use a delisting-aware source]
          | costs modeled [n/a — no backtest yet]
