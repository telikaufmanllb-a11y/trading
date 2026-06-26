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
