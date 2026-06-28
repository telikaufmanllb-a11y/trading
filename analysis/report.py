"""Human-readable backtest report (CLAUDE.md `reports/`).

Renders a markdown tearsheet from one or more `BacktestResult`s plus their `Metrics`. Two things
it deliberately does:
  * Surfaces the implausibility WARNINGS from `compute_metrics` at the TOP, not buried — a great
    number is a bug to investigate first (HARD RULE 6).
  * Always includes the standing non-financial-advice caveat (HARD RULE 8 / CLAUDE.md §10).

Plain markdown (no plotting) so it is deterministic, testable, and dependency-light; quantstats
plots can be attached later for richer tearsheets.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from analysis.metrics import Metrics, compute_metrics

DISCLAIMER = (
    "> **Disclaimer.** Educational research using public data. NOT financial advice and NOT a "
    "recommendation. Results are uncertain and provisional; even well-designed strategies lose "
    "money in some periods. This project stops at paper trading and never submits real orders."
)


def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


def _num(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def render_report(
    title: str,
    results_by_horizon: dict[int, object],
    *,
    config_desc: str = "",
    data_source_note: str = "",
    generated_at: Optional[datetime] = None,
) -> str:
    """Render a markdown report for a multi-horizon backtest.

    `results_by_horizon` maps holding_days -> BacktestResult (e.g. from `run_multi_horizon`).
    `data_source_note` should loudly state if the prices are PROTOTYPE/survivor-biased.
    """
    gen = (generated_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [f"# {title}", "", DISCLAIMER, "", f"*Generated {gen}*", ""]
    if data_source_note:
        lines += [f"**Data source:** {data_source_note}", ""]
    if config_desc:
        lines += [f"**Config:** {config_desc}", ""]

    # Collect warnings across horizons and show them first.
    all_warnings: list[str] = []
    metrics_by_h: dict[int, Metrics] = {}
    for h, res in sorted(results_by_horizon.items()):
        m = compute_metrics(res)
        metrics_by_h[h] = m
        for w in m.warnings:
            all_warnings.append(f"[{h}d] {w}")

    if all_warnings:
        lines += ["## ⚠️ Red flags / caveats (read first)", ""]
        lines += [f"- {w}" for w in all_warnings]
        lines += [""]

    lines += ["## Results by holding period", "",
              "| Horizon | Trades | Mean net | Median net | Win rate | Mean SPY | "
              "Mean abnormal | Abn t-stat | Beats SPY | Max DD |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for h, m in sorted(metrics_by_h.items()):
        res = results_by_horizon[h]
        lines.append(
            f"| {h}d | {m.n_trades} | {_pct(m.mean_return)} | {_pct(m.median_return)} | "
            f"{_pct(m.win_rate)} | {_pct(res.mean_benchmark_return)} | "
            f"{_pct(m.mean_abnormal)} | {_num(m.abnormal_t_stat)} | "
            f"{_pct(res.beats_benchmark_rate)} | {_pct(m.max_drawdown)} |"
        )
    lines += ["", _verdict(metrics_by_h), "", DISCLAIMER, ""]
    return "\n".join(lines)


def _verdict(metrics_by_h: dict[int, Metrics]) -> str:
    """A cautious, honest read — never declares an edge from in-sample/insufficient data."""
    too_few = all(m.n_trades < 30 for m in metrics_by_h.values())
    if too_few:
        return ("**Verdict:** Inconclusive — too few trades for a statistically meaningful claim. "
                "Do NOT treat any positive number here as an edge (HARD RULE 6). Need more history "
                "and a holdout validation before the kill condition can be applied.")
    any_beat = any((m.mean_abnormal or -1) > 0 and (m.abnormal_t_stat or 0) > 2
                   for m in metrics_by_h.values())
    if any_beat:
        return ("**Verdict:** Some horizon shows positive abnormal return with t>2 — promising, but "
                "verify on the untouched holdout ONCE and re-audit for look-ahead/survivorship "
                "before believing it.")
    return ("**Verdict:** No horizon beats SPY on a risk-adjusted basis after costs. Per the "
            "pre-committed kill condition, the honest reading is 'no edge' — log it; do NOT re-tune "
            "to defeat the kill condition.")
