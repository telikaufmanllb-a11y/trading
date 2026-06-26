# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: Stage 1 — EDGAR Form 4 ingestion (start small + read-only inspection)

Begin Stage 1. Concretely, the next highest-value task is:

1. Build a **read-only EDGAR client** (`data/edgar.py`) that fetches the SEC submissions/
   full-text index and downloads raw Form 4 filings, **respecting the SEC fair-access rules**
   (declared `User-Agent` with contact email, ≤10 req/s, ret/backoff). Cache raw filings to
   disk so we never re-hit EDGAR for the same document (reproducibility + politeness).
2. Write a **Form 4 XML parser** (`data/form4.py`) that extracts: issuer (CIK, ticker),
   reporting owner (name, CIK, role flags: director/officer/10%-owner), and each non-derivative
   transaction (date, code, shares, price, acquired/disposed flag). **Keep both the transaction
   date AND the filing/acceptance date** — the filing date is the only legal entry signal
   (HARD RULE 1).
3. Unit-test the parser against a **saved sample Form 4 fixture** (committed to `tests/`), not
   against the live network, so tests are deterministic.

Do NOT build the cluster detector or backtest yet. Stage 1 is "data + eyeball": get real
filings parsed correctly, then manually inspect a few historical clusters before automating.

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
| 1 | EDGAR Form 4 ingest + point-in-time prices/universe + eyeball clusters | ⬜ not started |
| 2 | Cluster-buy detector + features | ⬜ not started |
| 3 | Event-driven backtest (filing-date entries, costs, train/holdout, kill condition) | ⬜ not started |
| 4 | Paper trade (NO live orders) | ⬜ not started |
| 5 | Generalize: congressional-trade module | ⬜ not started |

---

## Cycle log

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
