"""Event-driven backtest engine — the heart of the project (CLAUDE.md Stage 3).

Consumes signal events (anything with `.ticker` and `.entry_date`) and a `PriceSource`, and
computes per-trade returns NET of realistic costs, holding each position for a fixed horizon.

The non-negotiables this engine enforces:
  * **Filing-date entry (HARD RULE 1).** Entry uses `event.entry_date`, which the signal layer
    already defines as the public-disclosure (filing) date — never a transaction date. The engine
    adds no look-ahead: `PriceSource.holding_period_return` enters at the first bar on/after that
    date.
  * **Reality modeled (HARD RULE 3).** Every trade pays commission, half-spread, and slippage on
    BOTH sides, and short-term capital-gains tax on net gains. Microcap slippage is severe, so the
    defaults are deliberately punitive and configurable.
  * **Survivorship-safe (HARD RULE 2).** Returns come from `PriceSource.holding_period_return`,
    which realizes delisting losses rather than dropping dead names.

This engine is signal-agnostic (architecture goal): it never imports the insider module, so the
congressional-trade signal will run through it unchanged. It also never places orders (HARD RULE 7).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional, Protocol

from data.prices import PriceSource


class _Event(Protocol):
    ticker: Optional[str]
    entry_date: date


@dataclass(frozen=True)
class CostModel:
    """Per-side transaction costs (bps of notional) + short-term tax on gains.

    Defaults are intentionally conservative for the small/microcap names where the insider edge is
    strongest and where spreads/slippage are punishing. Tune per market-cap bucket later; never
    optimize these to make results look good (HARD RULE 3 / §9).
    """

    commission_bps: float = 1.0       # per side
    half_spread_bps: float = 25.0     # per side (cross half the bid/ask)
    slippage_bps: float = 25.0        # per side (market impact; raise for microcaps)
    short_term_tax_rate: float = 0.35  # tax applied to NET gains only

    def round_trip_cost_fraction(self) -> float:
        per_side = (self.commission_bps + self.half_spread_bps + self.slippage_bps) / 1e4
        return 2.0 * per_side

    def net_of_costs(self, gross_return: float) -> float:
        """Apply round-trip costs, then short-term tax on any remaining gain.

        Tax is charged only on positive net-of-cost returns (a single trade gets no tax credit for
        a loss — conservative; loss-offset is a portfolio-level concern modeled later).
        """
        net = gross_return - self.round_trip_cost_fraction()
        if net > 0:
            net *= (1.0 - self.short_term_tax_rate)
        return net


@dataclass(frozen=True)
class Trade:
    ticker: Optional[str]
    entry_date: date
    exit_date: date
    holding_days: int
    gross_return: float
    net_return: float
    benchmark_return: Optional[float]
    abnormal_return: Optional[float]  # net_return - benchmark_return (None if no benchmark price)


@dataclass(frozen=True)
class BacktestResult:
    holding_days: int
    trades: list[Trade]
    n_signals: int
    n_skipped_no_price: int

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    def _mean(self, attr: str) -> Optional[float]:
        vals = [getattr(t, attr) for t in self.trades if getattr(t, attr) is not None]
        return statistics.fmean(vals) if vals else None

    @property
    def mean_net_return(self) -> Optional[float]:
        return self._mean("net_return")

    @property
    def median_net_return(self) -> Optional[float]:
        vals = [t.net_return for t in self.trades]
        return statistics.median(vals) if vals else None

    @property
    def mean_benchmark_return(self) -> Optional[float]:
        return self._mean("benchmark_return")

    @property
    def mean_abnormal_return(self) -> Optional[float]:
        return self._mean("abnormal_return")

    @property
    def win_rate(self) -> Optional[float]:
        if not self.trades:
            return None
        return sum(1 for t in self.trades if t.net_return > 0) / len(self.trades)

    @property
    def beats_benchmark_rate(self) -> Optional[float]:
        rel = [t for t in self.trades if t.abnormal_return is not None]
        if not rel:
            return None
        return sum(1 for t in rel if t.abnormal_return > 0) / len(rel)


def run_backtest(
    events: Iterable[_Event],
    price_source: PriceSource,
    *,
    holding_days: int,
    cost_model: Optional[CostModel] = None,
    benchmark_ticker: str = "SPY",
) -> BacktestResult:
    """Run one fixed-horizon backtest over `events`.

    Each event enters at its (filing) `entry_date` and exits `holding_days` calendar days later;
    `PriceSource` maps those to actual trading bars. Returns are net of `cost_model`. The benchmark
    is a same-window buy-and-hold of `benchmark_ticker` (shown gross — a passive index is the
    honest comparison baseline; we are not paying round-trip costs to hold SPY).
    """
    cost_model = cost_model or CostModel()
    trades: list[Trade] = []
    n_signals = 0
    n_skipped = 0
    for ev in events:
        n_signals += 1
        if ev.ticker is None:
            n_skipped += 1
            continue
        exit_date = ev.entry_date + timedelta(days=holding_days)
        gross = price_source.holding_period_return(ev.ticker, ev.entry_date, exit_date)
        if gross is None:
            n_skipped += 1
            continue
        net = cost_model.net_of_costs(gross)
        bench = price_source.holding_period_return(benchmark_ticker, ev.entry_date, exit_date)
        abnormal = (net - bench) if bench is not None else None
        trades.append(
            Trade(
                ticker=ev.ticker, entry_date=ev.entry_date, exit_date=exit_date,
                holding_days=holding_days, gross_return=gross, net_return=net,
                benchmark_return=bench, abnormal_return=abnormal,
            )
        )
    return BacktestResult(
        holding_days=holding_days, trades=trades,
        n_signals=n_signals, n_skipped_no_price=n_skipped,
    )


# Standard horizons (CLAUDE.md Stage 3): edge is documented to decay past ~6–12 months.
DEFAULT_HOLDING_PERIODS = (21, 63, 126, 252)


def run_multi_horizon(
    events, price_source, *, holding_periods=DEFAULT_HOLDING_PERIODS, **kwargs
) -> dict[int, BacktestResult]:
    """Run the backtest at several holding periods; events are materialized so they're reused."""
    events = list(events)
    return {h: run_backtest(events, price_source, holding_days=h, **kwargs) for h in holding_periods}
