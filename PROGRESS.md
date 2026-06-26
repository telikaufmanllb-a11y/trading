# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: Stage 1 (cont.) — multi-issuer P-code ingest + eyeball a real cluster; PriceSource iface

Fetch→parse for real filings is done and tested; price-source policy is decided (D-0010:
delisting-aware required, yfinance barred from the backtest path). Next highest-value:

1. **Find and eyeball a real cluster.** Ingest Form 4s across a *set* of issuers over a window,
   keep only open-market purchases (code `P`/`A`), and surface cases where ≥3 distinct insider
   CIKs bought the same issuer within ~15 days. Manually inspect a few — confirm they look like
   the literature (opportunistic, small/mid-cap skew) before automating the detector in Stage 2.
   Note: the per-issuer submissions endpoint is owner-or-issuer keyed; to scan broadly we likely
   need the daily EDGAR Form 4 index (`full-index`/`daily-index`) — add that to the client.
2. **`PriceSource` interface (swappable, delisting-aware).** Define the abstract contract now
   (e.g. `prices(ticker, start, end) -> DataFrame` with point-in-time, delisting-marked data) so
   the backtest is provider-agnostic. Pick the concrete delisting-aware provider per D-0010. Do
   NOT import yfinance on any backtest path — eyeball-only scripts may use it, clearly fenced.

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

## 2026-06-26 — Stage 1b (real fetch→parse wiring + price-source policy)
NEXT: Multi-issuer P-code ingest to surface & eyeball a real ≥3-insider cluster (likely needs the
     EDGAR daily/full Form 4 index); define a swappable delisting-aware `PriceSource` interface
     (see top of file).
DID: Added `EdgarClient.raw_document_name` (strips the `xslF345X06/` viewer dir), `load_form4`
     (fetch raw XML → parse → attach filing_date + dashed accession from metadata), and
     `iter_issuer_form4s` (generator over an issuer's Form 4s, filing-date filtered). Saved a real
     Apple Form 4 as an offline fixture and added tests pinning raw-doc resolution, accession
     formatting, and that filing_date comes from metadata and stays distinct from periodOfReport.
     Eyeballed a real filing by hand: SVP/GC, codes M (option exercise, $0) + F (tax withholding)
     — correctly parsed and correctly yields ZERO open-market purchases (exactly the routine
     activity the strategy must ignore). Recorded price-source policy (D-0010).
RESULTS: 22/22 tests green. N/A on returns (no signal/backtest yet).
RED FLAGS / REVIEW NEEDED: None.
RULE CHECK: look-ahead [ok — load_form4 attaches filing_date from submissions metadata only;
          pinned by test_load_form4_attaches_filing_date_from_metadata]
          | survivorship [ok — price-source policy now bars survivor-biased yfinance from the
          backtest path (D-0010); no price code written yet]
          | costs modeled [n/a — no backtest yet]

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
