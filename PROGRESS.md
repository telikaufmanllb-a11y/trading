# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: Stage 1 (cont.) — run the cluster eyeball scan; then PriceSource iface

Cross-issuer enumeration now works (daily master index → Form 4 `.txt` → XML → parsed `Form4`),
validated live (916 Form 4s on 2026-06-25). Next highest-value:

1. **Run the bounded cluster eyeball.** Write an inspection script (`reports/`-oriented, not on
   the backtest path) that scans a small window of daily indices, fetches each Form 4, keeps only
   open-market purchases (code `P`/`A`), groups by issuer, and surfaces issuers with ≥3 distinct
   insider CIKs buying within ~15 days. Disk cache makes re-runs free; be polite on the first run
   (rate-limited; a day has ~900 Form 4s). Manually inspect a few clusters vs. the literature
   (opportunistic, small/mid-cap skew) before automating the detector in Stage 2.
2. **`PriceSource` interface (swappable, delisting-aware).** Define the abstract contract
   (`prices(ticker, start, end) -> DataFrame`, point-in-time, delisting-marked) so the backtest is
   provider-agnostic. Pick the concrete delisting-aware provider per D-0010. yfinance only in
   fenced eyeball scripts, never on the backtest path.

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

## 2026-06-26 — Stage 1c (cross-issuer enumeration via daily index)
NEXT: Run the bounded cluster eyeball scan (daily indices → P-code buys → group by issuer → ≥3
     insiders/15d), then define the delisting-aware `PriceSource` interface (see top of file).
DID: Added daily master-index support to `EdgarClient` (`daily_master_index_url`,
     `parse_master_index`, `get_daily_form4_index`) + an `IndexEntry` type, and
     `extract_xml_from_submission` to pull Form 4 XML out of a full-submission `.txt`. Offline
     fixtures (master index + wrapped submission) and tests. Live validation caught a REAL bug:
     daily-index dates are YYYYMMDD not ISO, so the parser silently returned 0 rows — fixed the
     date parser to accept both formats AND fixed the unrealistic fixture (added a regression
     test). Re-validated live: 916 Form 4s enumerated for 2026-06-25, one parsed end-to-end.
RESULTS: 28/28 tests green. N/A on returns (no signal/backtest yet).
RED FLAGS / REVIEW NEEDED: None. Methodology note: a green test against a fabricated fixture hid a
     real format bug until live data exposed it — reinforces the "eyeball real data" rule. The
     cluster eyeball scan will hit EDGAR for many docs; first run is rate-limited + cached.
RULE CHECK: look-ahead [ok — filing date taken from <ACCEPTANCE-DATETIME>/index date, never the
          XML transaction date] | survivorship [ok — still no price DB; policy D-0010 holds]
          | costs modeled [n/a — no backtest yet]

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
