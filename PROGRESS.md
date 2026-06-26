# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: Stage 1 (cont.) — PriceSource interface; then Stage 2 opportunistic filter

Cluster eyeball tooling is built, tested, and run on real data; it surfaced a key finding
(D-0013: code-P clusters include coordinated offerings, not just opportunistic buys). Next:

1. **`PriceSource` interface (swappable, delisting-aware).** Define the abstract contract
   (`prices(ticker, start, end) -> DataFrame`, point-in-time, delisting-marked) so the backtest is
   provider-agnostic. Pick the concrete delisting-aware provider per D-0010. yfinance only in
   fenced eyeball scripts, never on the backtest path. (Fully offline/testable — good next step.)
2. **(Stage 2 seed) Opportunistic-vs-coordinated classification.** Per D-0013, before any signal
   is tradable we must exclude coordinated/uniform-price offerings. Prototype the heuristics on
   the FCBM / FMBM / ENR / TUSK clusters already cached: near-uniform price across insiders, same
   filing date en masse, price ≈ a stated offering price, footnote/plan flags.

Do NOT build the backtest yet. Finish Stage 1 (prices + universe) before Stage 2/3.

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

## 2026-06-26 — Stage 1d (cluster eyeball tooling + first real-data finding)
NEXT: Define the delisting-aware `PriceSource` interface; prototype the opportunistic-vs-
     coordinated filter on the cached clusters (see top of file).
DID: Built `scripts/eyeball_clusters.py` — an inspection tool (NOT the Stage 2 detector, NOT on
     the backtest path) with a pure, offline-tested `find_clusters()` that groups open-market
     purchases by issuer using FILING-DATE windows (HARD RULE 1). 5 new unit tests (distinct-
     insider counting, window boundaries, issuer separation, sort order). Ran a bounded, polite
     live scan (cap 800 filings) → surfaced 4 candidate clusters, incl. two community banks
     (FCBM, FMBM) — matching the literature's small-cap/bank skew.
KEY FINDING: FCBM showed 15 insiders — implausibly high (HARD RULE 6), so I eyeballed it: all 15
     bought at a UNIFORM $12.50 on the SAME day = a coordinated fixed-price offering, not
     independent opportunistic buys. SEC code P means "open market OR private purchase," so code-P
     alone over-counts clusters. Logged as D-0013; Stage 2 must build an opportunistic filter that
     excludes coordinated offerings BEFORE the signal is treated as tradable.
RESULTS: 33/33 tests green. Live scan: 92 P-buy records from 800 filings → 4 raw candidate
     clusters (pre-opportunistic-filter, so an over-count by design). N/A on returns.
RED FLAGS / REVIEW NEEDED: None unresolved — the implausible 15-insider cluster was investigated
     and explained (offering). The finding tightens Stage 2, it does not indicate a bug.
RULE CHECK: look-ahead [ok — clustering keyed on filing date only] | survivorship [ok — no price
     DB yet] | costs modeled [n/a — no backtest yet]

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
