# PROGRESS.md — the loop's memory

> Read this first every cycle. Then read `DECISIONS.md`. Then do the single highest-value
> next task, validate against the HARD RULES in `CLAUDE.md`, log here, commit, stop clean.

---

## NEXT: (offline pipeline COMPLETE) — awaiting human inputs to go further

The full offline pipeline is built & tested end-to-end (95 tests): EDGAR ingest → cluster signal
(look-ahead-correct, opportunistic-filtered) → event-driven backtest (costs/tax/delisting) →
metrics (with implausibility warnings) → train/holdout split → markdown report → one-command
orchestration (`scripts/run_research.py`). There is intentionally NO strategy result yet, because
there is no trustworthy price data — and that is the honest state, not a gap to paper over.

**Two blockers, both genuinely human (logged, not code):**
1. **Delisting-aware price VENDOR** (HARD RULE 2; D-0010/D-0018b) — required for ANY trusted
   result. yfinance prototype is built but survivor-biased AND blocked by this container's proxy
   (D-0022); it would run on the GH Actions runner for PLUMBING only, never a conclusion.
2. **Durable loop:** add the `ANTHROPIC_API_KEY` repo secret + enable Actions write perms so
   `.github/workflows/research-loop.yml` can run unattended (docs/AUTONOMOUS_LOOP.md).

**Safe offline things a future tick COULD do (low marginal value — avoid churn):** a project-state
writeup in reports/; more features (role/cluster-size weighting) — but per §9 do NOT add complexity
before the simple version is validated on real data. Prefer to WAIT for the human inputs above.

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
| 0 | Frame: docs, repo skeleton, deps | ✅ done |
| 1 | EDGAR Form 4 ingest + eyeball clusters | ✅ ingest+eyeball done; ⬜ delisting-aware prices/universe (needs vendor) |
| 2 | Cluster-buy detector + opportunistic filter | ✅ done (signals/insider_cluster + features/opportunistic) |
| 3 | Event-driven backtest (filing-date, costs) | 🟡 engine+metrics done & tested; ⬜ train/holdout + kill condition (needs real prices) |
| 4 | Paper trade (NO live orders) | ⬜ not started |
| 5 | Generalize: congressional-trade module | ⬜ not started |

---

## Cycle log

## 2026-06-28 — Stage 3e (end-to-end research orchestration) — OFFLINE PIPELINE COMPLETE
NEXT: Awaiting human inputs — delisting-aware price vendor (for trusted results) and the Actions
     secret (for the durable loop). Offline pipeline is done; avoid low-value churn.
DID: Built `scripts/run_research.py` (EDGAR→signals→multi-horizon backtest→report; pure
     `run_research` core + CLI that refuses to run without a trusted price source, fenced prototype
     behind --prototype-prices; train/holdout reserves the holdout). 4 tests; 95/95 green. Logged
     D-0024. This completes the offline-buildable stack.
RESULTS: 95/95 tests green. No strategy numbers — by design (no trustworthy price data).
RED FLAGS / REVIEW NEEDED: Project is now genuinely BLOCKED on two human inputs (price vendor;
     Actions secret). Continuing to add code would risk complexity-before-validation (§9). The loop
     will idle/scale back until those land.
RULE CHECK: look-ahead [ok] | survivorship [ok] | costs modeled [y]

## 2026-06-28 — Stage 3d (train/holdout split + report writer)
NEXT: end-to-end research orchestration script (cached EDGAR signals → multi-horizon backtest →
     report), offline-testable with InMemoryPriceSource. After that, blocked on real price data
     (vendor=human) and the Actions secret for durable runs.
DID: Built `backtest/split.py` (chronological train/holdout by filing date, HARD RULE 4) and
     `analysis/report.py` (markdown tearsheet: warnings-first, disclaimer always, PROTOTYPE-data
     banner, cautious verdict that says "Inconclusive"/"no edge" rather than inventing an edge).
     10 tests; 91/91 green. Logged D-0023.
RESULTS: 91/91 tests green. No strategy numbers (no real price data) — by design.
RED FLAGS / REVIEW NEEDED: (carried, both human) delisting-aware price VENDOR for trusted results;
     add ANTHROPIC_API_KEY secret to enable the durable GitHub Actions loop. No code defects open.
RULE CHECK: look-ahead [ok — chronological split, no random leakage] | survivorship [ok] |
     costs modeled [y]

## 2026-06-28 — Stage 3c (fenced prototype price adapter)
NEXT: train/holdout splitter + tearsheet writer (offline-buildable); real price data is the
     blocker for actual results (vendor = human; yfinance blocked in-container, D-0022).
DID: Built `data/prices_prototype.YFinancePriceSource` (fenced, survivor-biased, delisting()=None,
     loud warning) implementing the swappable `PriceSource`, with a pure unit-tested `to_price_frame`
     column mapper (flat/MultiIndex/auto_adjust). 4 new tests; 85/85 green. Tried a live fetch:
     yfinance's curl_cffi TLS can't negotiate through this container's egress proxy (D-0022) — not
     fixable without disabling TLS (forbidden), so no in-container live run; adapter will work on the
     GH Actions runner. Loop durability handled last cycle via .github/workflows/research-loop.yml
     (awaiting the user's ANTHROPIC_API_KEY secret).
RESULTS: 85/85 tests green. Still NO strategy results (no usable real price data) — nothing to
     over-trust, by design.
RED FLAGS / REVIEW NEEDED: (carried) delisting-aware price VENDOR for trusted results; loop
     durability needs the user to add the Actions secret. No code defects open.
RULE CHECK: look-ahead [ok] | survivorship [ok — prototype is fenced & clearly survivor-biased] |
     costs modeled [y, in engine]

## 2026-06-28 — Stage 3b (analysis/metrics + end-to-end integration; loop durability)
NEXT: A real price source to actually RUN the pipeline. Trusted result needs the delisting-aware
     vendor (human, D-0018b); a fenced yfinance prototype can do a PLUMBING-only real-ish run.
     Also: durable out-of-session loop driver (see below) — current in-session cron dies on
     container reclamation.
DID: Built `analysis/metrics.py` (compound/Sharpe/max-drawdown/t-stat + implausibility WARNINGS,
     HARD RULE 6) and an end-to-end integration test (generate_signals → run_backtest →
     compute_metrics on synthetic data). Fixed a test-fixture date bug (exit bar fell 1 day past
     the holding window — engine was correct). 81/81 green. Re-armed in-session cron after the
     prior one died with the reclaimed container.
RESULTS: 81/81 tests green. No strategy results yet (no real price data — by design, nothing to
     over-trust).
RED FLAGS / REVIEW NEEDED: **Loop durability** — in-session cron/ScheduleWakeup do NOT survive the
     ephemeral container being reclaimed (~18h gap observed). A durable driver must live on outside
     infra (GitHub Actions scheduled workflow, or a Claude Code web scheduled trigger). Proposed to
     the user. (carried) price vendor; multi-year scan.
RULE CHECK: look-ahead [ok] | survivorship [ok] | costs modeled [y]

## 2026-06-26 — Stage 3a (event-driven backtest engine)
NEXT: analysis/metrics.py + end-to-end integration test (offline); price source later (see top).
DID: Built `backtest/engine.py` — `CostModel` (commission+half-spread+slippage both sides, short-
     term tax on net gains only), `run_backtest` (filing-date entry via event.entry_date, returns
     via delisting-safe `PriceSource.holding_period_return`, SPY-relative abnormal return),
     `BacktestResult` summary metrics, and `run_multi_horizon` (21/63/126/252d). Signal-agnostic
     (duck-typed events; no insider import). 14 tests vs `InMemoryPriceSource` cover cost/tax math,
     filing-date entry, a delisted-name loss, skip-on-missing-price, summaries. Logged D-0020.
     Deferred the yfinance prototype adapter (engine is better validated offline; real source still
     needed for trusted results). Converged the loop onto durable cron `02479140` (no more
     ScheduleWakeup chain → no duplicate turns).
RESULTS: 72/72 tests green.
RED FLAGS / REVIEW NEEDED: (carried) delisting-aware vendor for trusted results; multi-year scan
     for power. Engine intentionally not yet run on real data (no trusted source) — so NO results
     to over-trust yet.
RULE CHECK: look-ahead [ok — entry at event.entry_date=filing date; tested] | survivorship [ok —
     returns via delisting-safe primitive; delisted-loss test] | costs modeled [y — commission,
     spread, slippage, short-term tax]

## 2026-06-26 — Stage 2d (swappable signal module, look-ahead-correct trigger)
NEXT: Fenced prototype price adapter → Stage 3 backtest skeleton (plumbing only) (see top).
DID: Built `signals/insider_cluster.py` implementing the D-0004 swappable contract
     `generate_signals(buys, …) -> [SignalEvent]`. Key correctness: entry/trigger date is the
     filing date at which the rolling window FIRST reaches `min_insiders` distinct insiders (the
     actionable disclosure date), via a two-pointer sweep — NOT the first buy (HARD RULE 1).
     Coordinated excluded by default (D-0015). 7 unit tests. Validated on real LOVE cluster:
     entry_date = 2026-06-23 (3rd/CEO filing), n=3, not coordinated. Logged D-0019.
RESULTS: 62/62 tests green.
RED FLAGS / REVIEW NEEDED: (carried) delisting-aware vendor for trusted results; multi-year scan
     for power. Neither blocks the next steps.
RULE CHECK: look-ahead [ok — trigger date is the N-th insider's FILING date, explicitly tested] |
     survivorship [ok — no price DB yet] | costs modeled [n/a — backtest is next]

## 2026-06-26 — Stage 2c (base-rate scan + first confirmed genuine cluster)
NEXT: Formalize `signals/insider_cluster.py` (swappable generate_signals); prototype price adapter;
     backtest skeleton (see top of file).
DID: User delegated the two open decisions ("use your best judgement") — logged as D-0018: (a)
     authorized + ran a base-rate scan; (b) deferred paid price-vendor procurement (real-money/
     identity action), will use a fenced free adapter for prototyping only. Added `--out` JSON dump
     + a JSON-serializable `scan()` entry point. NOTE: a long background scan was reaped by the env
     (exit 0 but incomplete) — lesson: run bounded foreground chunks, not long background jobs.
     Ran a bounded 2.4-day scan (3,600 filings, 2026-06-22..24).
KEY FINDING (FINDING-2): 266 P-buy records → 5 raw clusters → 4 coordinated, **1 GENUINE
     (Lovesac/LOVE)**, eyeball-confirmed (director+President+CEO, dispersed prices/dates =
     independent accumulation). Genuine clusters exist and the pipeline isolates them (~20% of raw)
     — hypothesis is testable — but they are rare (≈2/week here), so statistical power needs many
     years of data.
RESULTS: 55/55 tests green. Base rate: 5 raw / 4 coordinated / 1 genuine over ~2.4 days.
RED FLAGS / REVIEW NEEDED: (carried) delisting-aware vendor for any TRUSTED result; multi-year scan
     for power (heavy). Neither blocks formalizing the signal or building backtest plumbing.
RULE CHECK: look-ahead [ok — filing-date windows throughout] | survivorship [ok — no price DB yet;
     prototype adapter will be fenced] | costs modeled [n/a — no backtest yet]

## 2026-06-26 — Stage 2b (coordination wired into eyeball + 403 robustness)
NEXT: Measured base-rate scan (heavier, attended); add --out dump; price-vendor decision pending
     (see top of file).
DID: Wired `assess_coordination` into the cluster pipeline — `PurchaseRecord` now carries mean
     P-buy price + earliest transaction date, `assess_cluster_coordination` classifies each
     cluster, and `main()` labels COORDINATED vs. genuine and prints the genuine count. Hardened
     `get_daily_form4_index` to treat EDGAR 403 (today's not-yet-published index) as absent, not a
     crash. +4 tests. Demonstrated on the cached 800-filing sample: 0 of 2 clusters genuine.
RESULTS: 55/55 tests green. Cached-sample readout: 2 raw clusters, both COORDINATED → 0 genuine.
RED FLAGS / REVIEW NEEDED: Two open human decisions (carried): price vendor; authorization for a
     large base-rate EDGAR scan. Neither blocks progress or tests.
RULE CHECK: look-ahead [ok — filing-date windows; classifier uses in-filing price/date only] |
     survivorship [ok — no price DB yet] | costs modeled [n/a — no backtest yet]

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
