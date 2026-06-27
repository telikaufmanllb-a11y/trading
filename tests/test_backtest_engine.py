"""Tests for the event-driven backtest engine: cost/tax math, filing-date entry, survivorship."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd
import pytest

from backtest.engine import CostModel, run_backtest, run_multi_horizon
from data.prices import PRICE_COLUMNS, DelistingInfo, InMemoryPriceSource


@dataclass(frozen=True)
class Ev:
    ticker: Optional[str]
    entry_date: date


def _frame(dates, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes,
         "adj_close": closes, "volume": [1_000_000] * len(closes)},
        index=idx,
    )


# --- cost model ------------------------------------------------------------------------------

def test_round_trip_cost_fraction():
    cm = CostModel(commission_bps=1, half_spread_bps=25, slippage_bps=25)
    # (1+25+25) bps per side * 2 sides = 102 bps = 0.0102
    assert cm.round_trip_cost_fraction() == pytest.approx(0.0102)


def test_net_of_costs_taxes_only_gains():
    cm = CostModel(commission_bps=0, half_spread_bps=0, slippage_bps=0, short_term_tax_rate=0.35)
    # No costs: a +10% gross gain is taxed at 35% -> +6.5%.
    assert cm.net_of_costs(0.10) == pytest.approx(0.065)
    # A loss is not taxed (no per-trade credit) and passes through unchanged.
    assert cm.net_of_costs(-0.10) == pytest.approx(-0.10)


def test_costs_can_turn_a_small_gross_gain_negative():
    cm = CostModel(commission_bps=1, half_spread_bps=25, slippage_bps=25)  # 102 bps round trip
    assert cm.net_of_costs(0.005) < 0  # +0.5% gross < 1.02% costs -> net loss


# --- engine ----------------------------------------------------------------------------------

def _source():
    # Stock doubles-ish; SPY up 10% over the window.
    return InMemoryPriceSource({
        "AAA": _frame(["2024-01-02", "2024-04-01"], [100.0, 120.0]),
        "SPY": _frame(["2024-01-02", "2024-04-01"], [400.0, 440.0]),
    })


def test_basic_trade_net_and_abnormal():
    src = _source()
    cm = CostModel(commission_bps=0, half_spread_bps=0, slippage_bps=0, short_term_tax_rate=0.0)
    res = run_backtest([Ev("AAA", date(2024, 1, 2))], src, holding_days=90, cost_model=cm)
    assert res.n_trades == 1
    t = res.trades[0]
    assert t.gross_return == pytest.approx(0.20)
    assert t.net_return == pytest.approx(0.20)        # zero costs/tax
    assert t.benchmark_return == pytest.approx(0.10)  # SPY +10%
    assert t.abnormal_return == pytest.approx(0.10)


def test_costs_and_tax_reduce_net():
    src = _source()
    cm = CostModel(commission_bps=1, half_spread_bps=25, slippage_bps=25, short_term_tax_rate=0.35)
    res = run_backtest([Ev("AAA", date(2024, 1, 2))], src, holding_days=90, cost_model=cm)
    t = res.trades[0]
    expected = (0.20 - 0.0102) * (1 - 0.35)
    assert t.net_return == pytest.approx(expected)
    assert t.net_return < t.gross_return


def test_entry_uses_first_bar_on_or_after_filing_date():
    # Filing-date entry (HARD RULE 1): event dated before the first bar still enters at first bar.
    src = InMemoryPriceSource({"AAA": _frame(["2024-01-10", "2024-02-10"], [50.0, 55.0])})
    cm = CostModel(commission_bps=0, half_spread_bps=0, slippage_bps=0, short_term_tax_rate=0.0)
    res = run_backtest([Ev("AAA", date(2024, 1, 1))], src, holding_days=60,
                       cost_model=cm, benchmark_ticker="NONE")
    assert res.trades[0].gross_return == pytest.approx(0.10)


def test_delisted_name_realizes_loss_not_dropped():
    # Survivorship (HARD RULE 2): a delisted cluster-buy must show its loss, not vanish.
    src = InMemoryPriceSource(
        {"ZZZ": _frame(["2024-01-02", "2024-01-20"], [10.0, 8.0])},
        {"ZZZ": DelistingInfo("ZZZ", date(2024, 1, 21), -1.0, "bankruptcy")},
    )
    res = run_backtest([Ev("ZZZ", date(2024, 1, 2))], src, holding_days=90,
                       benchmark_ticker="NONE")
    assert res.n_trades == 1
    assert res.trades[0].gross_return == pytest.approx(-1.0)
    assert res.trades[0].net_return < 0


def test_missing_price_is_skipped_not_crashed():
    src = _source()
    res = run_backtest([Ev("NOPE", date(2024, 1, 2))], src, holding_days=90)
    assert res.n_trades == 0
    assert res.n_signals == 1
    assert res.n_skipped_no_price == 1


def test_summary_metrics():
    src = InMemoryPriceSource({
        "WIN": _frame(["2024-01-02", "2024-04-01"], [10.0, 13.0]),   # +30%
        "LOSE": _frame(["2024-01-02", "2024-04-01"], [10.0, 9.0]),   # -10%
        "SPY": _frame(["2024-01-02", "2024-04-01"], [100.0, 105.0]),  # +5%
    })
    cm = CostModel(commission_bps=0, half_spread_bps=0, slippage_bps=0, short_term_tax_rate=0.0)
    res = run_backtest([Ev("WIN", date(2024, 1, 2)), Ev("LOSE", date(2024, 1, 2))],
                       src, holding_days=90, cost_model=cm)
    assert res.win_rate == pytest.approx(0.5)
    assert res.mean_net_return == pytest.approx((0.30 + -0.10) / 2)
    assert res.mean_benchmark_return == pytest.approx(0.05)
    assert res.beats_benchmark_rate == pytest.approx(0.5)  # WIN beats SPY, LOSE doesn't


def test_multi_horizon_runs_all_periods():
    src = _source()
    out = run_multi_horizon([Ev("AAA", date(2024, 1, 2))], src, holding_periods=(21, 63))
    assert set(out.keys()) == {21, 63}
    assert all(r.n_signals == 1 for r in out.values())
