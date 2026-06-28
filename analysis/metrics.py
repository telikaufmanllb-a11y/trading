"""Performance metrics for a backtest (CLAUDE.md `analysis/`).

Hand-rolled core stats so they are deterministic and unit-tested (quantstats can layer on later for
plots). Everything here operates on a `BacktestResult`'s per-trade net returns. A key job of this
module is to FLAG implausible results (HARD RULE 6) rather than celebrate them — a great-looking
number is a bug to investigate first.

Caveat baked into the design: per-trade returns at a fixed holding horizon are NOT a clean daily
equity curve. We compound trades in entry-date order as a simple, transparent proxy and annualize
by trades-per-year; this is a summary, not a portfolio simulation (overlapping positions, position
sizing, and cash drag are modeled later). The numbers are honest about being approximate.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Metrics:
    n_trades: int
    mean_return: Optional[float]
    median_return: Optional[float]
    win_rate: Optional[float]
    volatility: Optional[float]          # stdev of per-trade net returns
    sharpe_per_trade: Optional[float]    # mean/stdev of trade returns (NOT annualized)
    total_compounded_return: Optional[float]
    max_drawdown: Optional[float]
    mean_abnormal: Optional[float]       # vs benchmark
    abnormal_t_stat: Optional[float]
    warnings: tuple[str, ...]


def _safe_mean(xs: Sequence[float]) -> Optional[float]:
    return statistics.fmean(xs) if xs else None


def compound(returns: Sequence[float]) -> float:
    """Compounded total return of a sequence of period returns."""
    eq = 1.0
    for r in returns:
        eq *= (1.0 + r)
    return eq - 1.0


def max_drawdown(returns: Sequence[float]) -> Optional[float]:
    """Worst peak-to-trough decline of the compounded equity curve (returns <= 0)."""
    if not returns:
        return None
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def sharpe(returns: Sequence[float]) -> Optional[float]:
    """Per-trade Sharpe (mean/stdev). Not annualized — annualize with care given overlap."""
    if len(returns) < 2:
        return None
    sd = statistics.stdev(returns)
    if sd == 0:
        return None
    return statistics.fmean(returns) / sd


def t_stat(values: Sequence[float]) -> Optional[float]:
    """One-sample t-stat vs 0 — is mean abnormal return distinguishable from zero?"""
    if len(values) < 2:
        return None
    sd = statistics.stdev(values)
    if sd == 0:
        return None
    return statistics.fmean(values) / (sd / math.sqrt(len(values)))


def compute_metrics(result, *, sharpe_red_flag: float = 2.0) -> Metrics:
    """Compute summary metrics from a `BacktestResult` and attach red-flag warnings."""
    net = [t.net_return for t in result.trades]
    abn = [t.abnormal_return for t in result.trades if t.abnormal_return is not None]

    vol = statistics.stdev(net) if len(net) >= 2 else None
    shp = sharpe(net)
    mdd = max_drawdown(net)
    abn_t = t_stat(abn)

    warnings: list[str] = []
    if shp is not None and abs(shp) > sharpe_red_flag:
        warnings.append(
            f"per-trade Sharpe {shp:.2f} exceeds {sharpe_red_flag} — implausible; audit for "
            f"look-ahead/survivorship BEFORE trusting (HARD RULE 6)")
    total = compound(net) if net else None
    if total is not None and total > 5.0:
        warnings.append(f"compounded return {total:.0%} is implausibly high — investigate")
    if result.n_trades < 30:
        warnings.append(
            f"only {result.n_trades} trades — too few for a statistically meaningful conclusion")
    if mdd is not None and mdd > -1e-9 and result.n_trades > 5:
        warnings.append("near-zero drawdown with many trades — suspiciously smooth; audit")

    return Metrics(
        n_trades=result.n_trades,
        mean_return=_safe_mean(net),
        median_return=statistics.median(net) if net else None,
        win_rate=result.win_rate,
        volatility=vol,
        sharpe_per_trade=shp,
        total_compounded_return=total,
        max_drawdown=mdd,
        mean_abnormal=_safe_mean(abn),
        abnormal_t_stat=abn_t,
        warnings=tuple(warnings),
    )
