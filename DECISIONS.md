# DECISIONS.md — append-only design log

> Every non-trivial design choice gets an entry here **with its economic or methodological
> reason** (HARD RULE 5: every parameter needs a prior reason, not just a better curve).
> Append only. Never rewrite history; if a decision is reversed, add a new entry that says so.

---

### D-0001 · 2026-06-26 · Hand-rolled event-driven backtester over vectorbt
**Reason:** The single most fatal bug in this domain is look-ahead via transaction-date entry
(HARD RULE 1). A hand-rolled event loop lets us make "entry = filing date, never transaction
date" an explicit, testable invariant rather than something we hope a vectorized library
respects. Control over the filing-date gate is worth more than vectorbt's speed at our data
scale. Revisit only if event-loop performance becomes a real bottleneck.

### D-0002 · 2026-06-26 · Point-in-time storage via parquet/duckdb, raw filings cached to disk
**Reason:** Reproducibility (HARD RULE 9) and SEC fair-access politeness. Caching raw EDGAR
documents means a re-run reads from disk and reproduces the same result without re-hitting the
network. Parquet/duckdb give us cheap columnar point-in-time queries without a DB server.

### D-0003 · 2026-06-26 · Single global RANDOM_SEED in config.py
**Reason:** HARD RULE 9 (reproducible to the same result). Centralizing the seed avoids
scattered, divergent seeds across modules. Default 42; any process that uses randomness calls
`config.seed_everything()`.

### D-0004 · 2026-06-26 · Modules are real Python packages; the *signal* is the swap point
**Reason:** Architecture goal (CLAUDE.md §4): insider clusters today, congressional trades later,
**no rewrite**. Each signal module will expose a uniform `generate_signals(date_range) -> events`
interface so the backtest/analysis pipeline is signal-agnostic. Locking this contract early
prevents the pipeline from baking in insider-specific assumptions.

### D-0005 · 2026-06-26 · Dependency versions pinned but not yet install-verified
**Reason:** HARD RULE 9 wants pinned, reproducible deps. They are declared in
`requirements.txt`. They are NOT yet confirmed to install in this environment (pip network not
verified at Stage 0). Flagged in PROGRESS.md; first Stage-1 task verifies the install and, if a
pin is unavailable, records the substitution here as a follow-up decision.
**UPDATE (same day, see D-0006):** install verified; one pin changed.

### D-0006 · 2026-06-26 · numpy pinned to 1.26.4 (not 2.x) for quantstats compatibility
**Reason:** Verifying the install (the D-0005 follow-up) surfaced a real conflict: `quantstats
0.0.64` requires `numpy<2.0.0`, so the original `numpy==2.2.1` pin was unresolvable alongside
it. Chose to keep quantstats (ready-made, well-understood tearsheets are worth more to this
analysis-heavy project than numpy 2.x's marginal gains) and pin `numpy==1.26.4`, the latest 1.x,
which satisfies quantstats, pandas 2.2.3, and matplotlib 3.10. The full pinned set now installs
cleanly and `pytest` passes (4/4). If we ever need numpy 2.x, the alternative is to drop
quantstats and hand-roll the tearsheet metrics — revisit then, not now.

### D-0007 · 2026-06-26 · Filing date sourced from submissions metadata, never from Form 4 XML
**Reason:** HARD RULE 1 (no look-ahead). The Form 4 XML carries only transaction dates; the
public-disclosure date lives in EDGAR submission metadata (`filings.recent.filingDate`, or the
`<ACCEPTANCE-DATETIME>` header). `parse_form4_xml` therefore takes `filing_date` as an explicit
caller-supplied input and never infers it from the document. Pinned by
`test_filing_date_is_not_invented_from_xml`. This makes the single most fatal bug in the project
a structural impossibility at the parser boundary, not a convention we hope to remember.

### D-0008 · 2026-06-26 · lxml with recover=True for Form 4 parsing
**Reason:** Real historical filings carry occasional malformations (stray trailing bytes, odd
encodings). `recover=True` lets us still extract the issuer/owner/transactions instead of hard-
failing a whole filing, which matters for a point-in-time corpus that must include messy old
documents. Pinned by `test_recovers_from_trailing_garbage`.

### D-0009 · 2026-06-26 · Raw Form 4 XML resolved by stripping the XSL viewer dir
**Reason:** EDGAR's submissions index points `primaryDocument` at the styled viewer path
(`xslF345X06/form4.xml`); the machine-readable XML is the same filename without that directory.
`EdgarClient.raw_document_name` strips it so `load_form4`/`iter_issuer_form4s` fetch parseable
XML. Validated against a saved real Apple Form 4 (`tests/fixtures/form4_real_aapl.xml`).

### D-0010 · 2026-06-26 · Price source MUST be delisting-aware; yfinance barred from the backtest
**Reason:** HARD RULE 2 (survivorship bias = invalid results). yfinance is installed and fine for
quick *eyeballing*, but it is survivor-biased: it drops delisted/bankrupt/acquired tickers, which
would silently delete exactly the cluster-buys that went to zero and make any strategy look
brilliant. **Decision:** the backtest price layer will sit behind a swappable `PriceSource`
interface, and its production implementation must come from a delisting-aware source (e.g. a
point-in-time vendor such as CRSP/Norgate/Sharadar, or a survivorship-free dataset we assemble
from EDGAR delisting events + a corporate-actions feed). yfinance may be used ONLY in throwaway
inspection scripts, never imported on the backtest path. This is recorded now so the constraint
is locked before any price code is written. Concrete provider selection is the next task.

### D-0011 · 2026-06-26 · Cross-issuer enumeration via the EDGAR daily master index
**Reason:** The per-issuer submissions JSON can't surface clusters *across* companies, which is
what the signal needs. The daily master index (`daily-index/YYYY/QTRn/master.YYYYMMDD.idx`,
pipe-delimited) lists every filing for a day; filtering Form Type == "4" enumerates all Form 4s
to fetch and parse. Weekend/holiday indexes 404 → treated as empty. **Regression caught by live
validation:** daily-index "Date Filed" is `YYYYMMDD`, not ISO `YYYY-MM-DD`; the ISO-only parser
silently dropped every row (0 results) until fixed. The unrealistic ISO fixture had hidden the
bug — fixture now uses the real format, pinned by `test_parse_master_index_handles_yyyymmdd_dates`.
Lesson re-affirmed: eyeball real data; a green test against a wrong fixture proves nothing.

### D-0012 · 2026-06-26 · Form 4 XML extracted from the full-submission .txt; acceptance time = filing date
**Reason:** The daily index points at the full-submission `.txt`, not the standalone XML.
`extract_xml_from_submission` pulls the `<XML>…</XML>` block to feed the parser, and
`acceptance_datetime_from_submission_header` reads `<ACCEPTANCE-DATETIME>` as the public-
disclosure timestamp — the correct filing-date source (HARD RULE 1). Validated end-to-end against
a real 2026-06-25 filing (916 Form 4s enumerated that day).

### D-0013 · 2026-06-26 · Code "P" ≠ pure open-market; opportunistic filter must exclude coordinated offerings
**Reason (Stage 1 eyeball finding — the whole point of "build intuition first"):** The eyeball
tool flagged First Carolina Financial (FCBM) with 15 insiders buying on 2026-06-22 — implausibly
high (HARD RULE 6), so I inspected it. All 15 (CEO, CFO, directors) bought at a *uniform $12.50*
on the *same day*. That is a coordinated capital event (fixed-price offering / private placement),
NOT 15 people independently judging the stock cheap. SEC transaction code **P is defined as "open
market OR private purchase"**, so code-P alone admits directed offerings — the *opposite* of the
opportunistic, independent cluster-buy the hypothesis targets ("multiple insiders *independently*
making open-market purchases").
**Consequence for Stage 2:** the opportunistic-vs-routine classifier must DOWN-WEIGHT or EXCLUDE
clusters that look coordinated — heuristics to test: near-uniform price across insiders, same/near
filing date en masse, price at/near a stated offering price, 10b5-1 plan flags, and footnotes
indicating a subscription/rights/placement. Counting raw code-P insiders (as this eyeball tool
does) will badly over-count clusters; that's acceptable for *inspection* but must NOT define the
tradable signal. Logged so Stage 2 builds the filter in from the start rather than discovering it
in a suspiciously-good backtest.

### D-0014 · 2026-06-26 · PriceSource interface with delisting as a first-class concept
**Reason:** HARD RULE 2 + architecture goal. The backtest depends only on the abstract
`PriceSource` (swappable provider, D-0010), and delisting is modeled explicitly via `DelistingInfo`
rather than as missing data. The `holding_period_return` primitive runs a delisted name to its
last bar and compounds the delisting return; an UNKNOWN delisting return defaults to -100% (total
loss), never silently to a survivor's outcome. This makes survivorship safety a property of the
data contract, not something the backtest must remember. `InMemoryPriceSource` exercises the
contract offline; 8 tests pin the delisting math (wipeout, unknown→conservative, buyout residual,
delisting-after-exit ignored). yfinance is intentionally NOT adapted here (survivor-biased).

### D-0015 · 2026-06-26 · Opportunistic-vs-coordinated classifier (prototype) in features/
**Reason:** Implements the D-0013 requirement. `features/opportunistic.assess_coordination` flags a
cluster as coordinated when BOTH (a) per-insider prices are near-uniform (price CV ≤ 1%) AND (b)
buys are time-concentrated (span ≤ 1 day) — the fingerprint of a fixed-price offering or director
purchase plan. Both conditions are required because either alone is too weak (cheap stocks have
low dispersion; one busy day can be coincidence). Thresholds are provisional with economic
rationale (HARD RULE 5), to be validated against labeled examples before defining a tradable
signal. Validated on real cached data: FCBM (15 insiders, cv=0.003, same day) and FMBM (8
directors, cv=0.000, same day) both correctly flagged coordinated.

### D-0016 · 2026-06-26 · Joint/affiliated owners on one filing = ONE insider (over-count bug fixed)
**Reason (real bug found via eyeball cross-check, HARD RULE 6):** A single Form 4 can name several
joint reporting owners. Energizer's 2026-06-22 filing had ONE filing with SIX joint owners (an
affiliated fund group controlled by one person). The eyeball tool emitted one record per owner, so
one decision-maker was counted as six independent insiders — manufacturing a phantom 6-insider
cluster. Fixed: one filing → one record, keyed by the sorted set of owner CIKs
(`owner_group_key`), so joint owners collapse to a single insider. Pinned by
`test_joint_owners_on_one_filing_count_as_one_insider`. After the fix, the 800-filing sample's
candidate clusters dropped 4→2 (Energizer and Mammoth were joint-filer artifacts).

### FINDING-1 · 2026-06-26 · Genuine opportunistic clusters are RARE; naive code-P counts mislead
In a sample of 800 Form 4s (one day), after fixing joint-owner inflation, the only two surviving
≥3-insider clusters (FCBM, FMBM) were BOTH coordinated events (an offering and a director purchase
plan) — i.e. ZERO genuine independent opportunistic clusters in the sample. Implication for the
backtest universe: the tradable cluster population is much smaller than raw code-P counts imply,
and a strategy built on unfiltered counts would be trading mostly non-predictive coordinated
events. The opportunistic filter is not a refinement — it is load-bearing. (Sample is tiny; this
is intuition, not a measured base rate. A fuller scan should quantify the coordinated fraction.)

### D-0017 · 2026-06-26 · Eyeball pipeline reports coordinated-vs-genuine; daily index 403 = absent
**Reason:** Wired `assess_coordination` into the cluster pipeline so the eyeball output labels each
cluster COORDINATED vs. genuine and reports the genuine count — making the FINDING-1 effect
visible per-run rather than via ad-hoc scripts. `PurchaseRecord` now carries the insider's mean
P-buy price and earliest transaction date to feed the classifier. Also hardened
`get_daily_form4_index`: EDGAR returns **403 (not 404)** for daily-index paths that don't exist
yet (e.g. today's index before publication), which previously crashed a scan that included today;
both 403 and 404 are now treated as "no index for this day." Pinned by
`test_get_daily_index_treats_403_and_404_as_absent`. Demonstrated: cached 800-filing sample →
0 of 2 clusters genuinely opportunistic.

### D-0018 · 2026-06-26 · Judgement calls on the two open questions (user delegated)
**Reason:** User said "use your best judgement for any unanswered questions."
**(a) Base-rate scan — AUTHORIZED & running.** A real coordinated-vs-genuine base rate needs
several CONSECUTIVE full days (genuine independent clusters only form across a multi-day window;
single-day clusters are inherently the coordinated kind). Launched a full trading-week (2026-06-22
..26), uncapped, polite (8 req/s, cached) background scan → `reports/cluster_scan_week.json`.
Within SEC fair-access limits; ~15 min. Added `--out` to persist results + a JSON-serializable
`scan()` entry point.
**(b) Price vendor — DEFERRED as real-world procurement (not auto-decidable).** A delisting-aware
vendor (CRSP/Norgate/Sharadar) requires an account + payment + credentials, which I will not
create on the user's behalf even under "best judgement" — that is a real-money/identity action,
not a code decision. Plan: keep the `PriceSource` interface ready; when the backtest needs data,
add a clearly-fenced FREE adapter (yfinance/stooq) for PROTOTYPING ONLY, with loud survivorship
caveats, and treat any results from it as provisional until a delisting-aware source is supplied.
No trusted/holdout result will ever come from the survivor-biased prototype source (D-0010 holds).

### FINDING-2 · 2026-06-26 · First measured base rate + a CONFIRMED genuine cluster (Lovesac)
Scan of ~3,600 Form 4s across 2026-06-22..24 (~2.4 trading days; `reports/cluster_scan_2day.json`):
  * 266 insider open-market-purchase records (after joint-owner collapse, D-0016)
  * 5 raw ≥3-insider/15-day clusters → 4 COORDINATED, **1 genuine** (~20% survive the filter)
  * Coordinated excluded: FCBM (offering, 15), FMBM (director plan, 8), BZFD (4), KARD (3).
  * **Genuine: LOVE (Lovesac)** — director (30k @ $14.68, txn 6/18), President (1.7k @ $14.41,
    6/22), CEO (1.8k @ $13.64, 6/22): three distinct insiders, ~7% price spread, multiple days =
    independent accumulation. Textbook opportunistic cluster.
**Implications:** (1) Genuine clusters EXIST and the pipeline isolates them — the hypothesis is
testable. (2) They are RARE: order-of-magnitude ~2/week from this sample → a small universe;
position sizing and statistical power will be real constraints (need many years of history). (3)
The opportunistic filter is doing real work (it removed 80% of raw clusters here). Caveat: tiny
sample (2.4 days), recent-only; not a statistically meaningful rate — a multi-year scan is needed
for that, which requires the heavier ingestion still gated on environment/time, not correctness.

### D-0019 · 2026-06-26 · signals/insider_cluster.py — swappable signal with look-ahead-correct trigger
**Reason:** Productizes the validated cluster logic behind the D-0004 contract
(`generate_signals(...) -> events`). The important correctness point: a cluster's entry date is the
filing date at which the rolling window FIRST contains `min_insiders` distinct insiders — i.e. when
the N-th insider's purchase becomes public — NOT the first buy's date (which is not yet a knowable
cluster). The eyeball tool reported the window's first date for inspection; this module computes the
actionable trigger via a two-pointer sweep (`_cluster_trigger`), so backtest entries can never use
information from before the cluster was disclosable (HARD RULE 1). Coordinated clusters excluded by
default (D-0015); joint owners assumed collapsed upstream (D-0016). Validated on the real LOVE
cluster: entry_date = 2026-06-23 (3rd insider's filing), not 2026-06-22. 7 unit tests pin the
trigger-date logic, window boundaries, coordination exclusion, dedup, and date-range filtering.

### D-0020 · 2026-06-26 · Event-driven backtest engine built & tested against InMemoryPriceSource
**Reason:** Stage 3 core. Chose to build the engine against the offline `InMemoryPriceSource`
rather than first wiring a yfinance prototype adapter — the engine logic (costs, tax, filing-date
entry, delisting handling) is the high-value, bug-prone part and is now fully deterministic and
unit-tested without depending on a possibly-blocked, survivor-biased external feed. `CostModel`
charges commission + half-spread + slippage on BOTH sides and short-term tax on net gains only
(conservative; punitive microcap defaults, HARD RULE 3). `run_backtest` enters at `event.entry_date`
(filing date, HARD RULE 1) and gets returns from `PriceSource.holding_period_return` (delisting-
safe, HARD RULE 2). The engine is signal-agnostic (duck-typed events; never imports the insider
module) and places no orders (HARD RULE 7). 14 tests pin cost/tax math, filing-date entry, a
delisted-name loss, skip-on-missing-price, and summary metrics. The yfinance prototype adapter is
deferred — only needed to run on real-ish prices, and a delisting-aware source is required for any
TRUSTED result anyway (D-0010/D-0018b).

### D-0021 · 2026-06-28 · analysis/metrics.py with built-in implausibility warnings
**Reason:** Stage 3 metrics. Hand-rolled CAGR/Sharpe/drawdown/hit-rate/abnormal-t-stat so they are
deterministic and unit-tested (quantstats can layer on for plots later). Crucially, `compute_metrics`
emits WARNINGS for implausible results — per-trade Sharpe>2, >500% compounded, <30 trades, or
near-zero drawdown with many trades — operationalizing HARD RULE 6 (a great number is a bug to
investigate first). End-to-end integration test (signal→backtest→metrics on synthetic data) proves
the signal-agnostic contract composes. 9 new tests; 81/81 green.

### D-0022 · 2026-06-28 · Prototype yfinance PriceSource built; live fetch blocked in THIS container
**Reason:** Built `data/prices_prototype.YFinancePriceSource` (fenced, survivor-biased; `delisting()`
always None; loud warning) with a pure, unit-tested `to_price_frame` column mapper (flat +
MultiIndex + auto_adjust cases). Implements the swappable `PriceSource` so the backtest can run on
real-ish prices for PLUMBING only — never trusted results (D-0010/D-0018b). **Limitation found:**
yfinance uses `curl_cffi` (TLS impersonation) which cannot negotiate through this environment's
re-terminating egress proxy (BoringSSL "invalid library" error); setting CURL_CA_BUNDLE/SSL_CERT_FILE
did not help, and per the proxy README we must NOT disable TLS verification. So a live prototype run
is not possible inside this container — it will work on the GitHub Actions runner (no proxy) or any
normal machine. The adapter and its mapping are committed and tested regardless; this is purely an
environment networking limit, not a code defect. A trusted run still requires a delisting-aware
source anyway.

### D-0023 · 2026-06-28 · Train/holdout splitter + honest markdown report writer
**Reason:** Stage 3 finish-line infrastructure, buildable offline before real data lands.
`backtest/split.py` does CHRONOLOGICAL train/holdout splits by filing date (never random — that
leaks the future; HARD RULE 4) with a fraction helper; the "validate holdout only once" rule stays
a logged process commitment. `analysis/report.py` renders a markdown tearsheet that (a) surfaces
the `compute_metrics` implausibility warnings at the TOP (HARD RULE 6), (b) always includes the
non-financial-advice disclaimer (HARD RULE 8/§10), (c) loudly flags PROTOTYPE/survivor-biased data,
and (d) gives a cautious verdict that returns "Inconclusive" for <30 trades and states the kill-
condition reading ("no edge") when nothing beats SPY — never manufacturing an edge from thin or
in-sample data. 10 new tests; 91/91 green.

### D-0024 · 2026-06-28 · End-to-end research orchestration (scripts/run_research.py)
**Reason:** Ties the pipeline together: EDGAR cluster buys → `generate_signals` → multi-horizon
backtest → markdown report. Core `run_research(buys, price_source, …)` is pure and unit-tested
offline (InMemoryPriceSource); `main()` wires real EDGAR signals + a chosen price source and
REFUSES to run without one (no trusted source ⇒ exits with guidance), only allowing the fenced
prototype via an explicit `--prototype-prices` flag that stamps the report PROTOTYPE/not-a-
conclusion. Train/holdout: with `--train-fraction`, only TRAIN is scored and the holdout is
reserved+counted (validate once, HARD RULE 4). 4 tests; 95/95 green. **This completes the offline-
buildable pipeline** — further progress needs a real (delisting-aware) price source, which is a
human procurement decision.

### D-0025 · 2026-06-28 · Run the first real-data (PROTOTYPE) backtest on GitHub Actions, not in-container
**Reason (best-intuition call, user-delegated):** Both free price sources are unreachable from this
dev container — yfinance's curl_cffi can't negotiate the egress proxy (D-0022) and Stooq now serves
a JS anti-bot page instead of CSV. The blocker is the *environment*, not the pipeline. A GitHub
Actions runner has open network, so the stack can run on real prices there. Added
`.github/workflows/research-run.yml` (workflow_dispatch, **no secret needed** — pure Python): scans
a HISTORICAL EDGAR window (default 2023-02, old enough that 21–252d holds have elapsed), runs
`scripts.run_research --prototype-prices --train-fraction 0.7`, and uploads the report as an
artifact. Added `trading_days_between` + `--start/--end` so the scan can target historical dates
(recent-N-days can't backtest — nothing has elapsed). This produces the project's FIRST end-to-end
real-data result the moment the user enables Actions — but it is PROTOTYPE/survivor-biased, loudly
stamped, and the kill condition is NOT evaluated on it (a delisting-aware vendor is still required
for any trusted conclusion). 1 new test; 96/96 green.
