# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: quantify the coordinated fraction (fuller scan); price-VENDOR decision needs a human

Opportunistic classifier + joint-owner fix are done & tested. FINDING-1 (DECISIONS.md): in a tiny
sample, genuine opportunistic clusters were ~0 — coordinated events and joint-filer artifacts
dominate. Next autonomous steps (offline / light-network, cached):

1. **Quantify, don't eyeball.** Run a fuller cached/polite scan (e.g. a full trading week, no cap)
   and measure: how many raw ≥3 clusters, how many survive the joint-owner collapse, how many
   survive the opportunistic filter. This base rate decides whether the signal is even viable
   before any backtest. Persist the surviving genuine clusters for later use.
2. **Add an opportunistic flag to the cluster output** so the eyeball tool reports coordinated vs.
   genuine, and wire `assess_coordination` into the cluster summary.
3. **Then:** point-in-time universe scaffold (delisting-aware) once the provider is chosen.

⚠️ **REVIEW NEEDED (human decision):** A truly delisting-aware price source generally requires a
paid/licensed vendor (CRSP / Norgate / Sharadar) or a non-trivial survivorship-free build from
SEC Form 25 delistings + a corporate-actions feed. This has cost/licensing implications I should
NOT decide autonomously. The `PriceSource` interface is ready to accept whichever is chosen.

Do NOT build the backtest yet. Finish Stage 1 (concrete prices + universe) before Stage 2/3.

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

## 2026-06-26 — Stage 2a (opportunistic classifier + joint-owner over-count fix)
NEXT: Quantify the coordinated/genuine cluster fractions over a fuller scan; wire the
     opportunistic flag into the eyeball output (see top of file).
DID: Built `features/opportunistic.assess_coordination` (flags coordinated offerings: near-uniform
     price AND time-concentrated; provisional thresholds w/ economic rationale; 6 unit tests).
     Cross-checking it on real data EXPOSED a real over-count bug: the eyeball tool counted each
     joint owner of a single Form 4 as a separate insider — Energizer's one filing had 6 joint
     affiliated owners → phantom 6-insider cluster. Fixed (one filing → one record keyed by sorted
     owner-CIK set; `purchase_record_from_form4` + 3 tests). Re-ran the 800-filing sample:
     candidate clusters 4→2.
KEY FINDINGS (DECISIONS D-0015/D-0016/FINDING-1): both surviving clusters (FCBM offering @ uniform
     $12.50; FMBM 8 directors @ uniform $36.10) are COORDINATED, not opportunistic → ~0 genuine
     clusters in the sample. Two distinct inflation mechanisms identified: coordinated events and
     joint/affiliated filers. The opportunistic filter is load-bearing, not cosmetic.
RESULTS: 51/51 tests green. Sample base-rate intuition only (n=800 filings, 1 day) — not measured.
RED FLAGS / REVIEW NEEDED: (carried) concrete price-vendor choice is a human decision. No new bugs
     open — the joint-owner over-count was found AND fixed this cycle.
RULE CHECK: look-ahead [ok — filing-date windows; classifier uses only in-filing data] |
     survivorship [ok — no price DB yet] | costs modeled [n/a — no backtest yet]

## 2026-06-26 — Stage 1e (delisting-aware PriceSource interface)
NEXT: Prototype the opportunistic-vs-coordinated filter offline on cached clusters; price-vendor
     choice flagged for human (see top of file).
DID: Added `data/prices.py` — abstract `PriceSource` (swappable provider per D-0010), first-class
     `DelistingInfo`, canonical price schema + `validate_price_frame`, `InMemoryPriceSource` for
     tests, and the survivorship-safe `holding_period_return` (filing-date entry at next bar;
     delisting return compounded; UNKNOWN delisting return → conservative -100%, never a silent
     survivor). 8 new tests pin the delisting math. Logged D-0014.
RESULTS: 42/42 tests green. N/A on returns (no backtest yet).
RED FLAGS / REVIEW NEEDED: Choosing the CONCRETE delisting-aware price vendor is a human decision
     (cost/licensing) — flagged at top of file. The interface is ready to accept any provider.
RULE CHECK: look-ahead [ok — entry uses first bar on/after entry date] | survivorship [ok —
     delisting modeled first-class; unknown delisting defaults to total loss] | costs modeled
     [n/a — no backtest yet]

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
