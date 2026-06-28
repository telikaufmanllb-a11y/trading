"""Tests for train/holdout splitting and the markdown report writer (offline)."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from analysis.report import render_report
from backtest.engine import CostModel, run_multi_horizon
from backtest.split import choose_split_date, split_by_date, split_by_fraction
from data.prices import InMemoryPriceSource


@dataclass(frozen=True)
class Ev:
    ticker: Optional[str]
    entry_date: date


def _evs(dates):
    return [Ev("AAA", d) for d in dates]


# --- split ----------------------------------------------------------------------------------

def test_split_by_date_is_chronological():
    evs = _evs([date(2020, 1, 1), date(2021, 1, 1), date(2022, 1, 1)])
    th = split_by_date(evs, date(2021, 6, 1))
    assert th.n_train == 2 and th.n_holdout == 1
    assert all(e.entry_date < date(2021, 6, 1) for e in th.train)
    assert all(e.entry_date >= date(2021, 6, 1) for e in th.holdout)


def test_split_boundary_goes_to_holdout():
    evs = _evs([date(2021, 6, 1)])
    th = split_by_date(evs, date(2021, 6, 1))
    assert th.n_train == 0 and th.n_holdout == 1  # on/after split_date -> holdout


def test_choose_split_date_fraction():
    evs = _evs([date(2020, m, 1) for m in range(1, 11)])  # 10 events
    cut = choose_split_date(evs, 0.7)
    th = split_by_date(evs, cut)
    assert th.n_train >= 6 and th.n_holdout >= 1  # ~70/30, both non-empty


def test_choose_split_date_empty():
    assert choose_split_date([], 0.7) is None
    th = split_by_fraction([], 0.7)
    assert th.n_train == 0 and th.n_holdout == 0


# --- report ---------------------------------------------------------------------------------

def _frame(dates, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes,
         "adj_close": closes, "volume": [1_000_000] * len(closes)}, index=idx)


def test_render_report_contains_disclaimer_and_warnings():
    src = InMemoryPriceSource({
        "AAA": _frame(["2024-01-02", "2024-02-01"], [10.0, 11.0]),
        "SPY": _frame(["2024-01-02", "2024-02-01"], [400.0, 404.0]),
    })
    results = run_multi_horizon([Ev("AAA", date(2024, 1, 2))], src, holding_periods=(21,),
                                cost_model=CostModel(0, 0, 0, 0.0))
    md = render_report("Test Run", results, data_source_note="PROTOTYPE/survivor-biased")
    assert "Disclaimer" in md
    assert "PROTOTYPE/survivor-biased" in md
    assert "too few" in md            # 1 trade -> implausibility warning surfaced
    assert "Results by holding period" in md
    assert "| 21d |" in md


def test_report_verdict_inconclusive_for_small_sample():
    src = InMemoryPriceSource({
        "AAA": _frame(["2024-01-02", "2024-02-01"], [10.0, 11.0]),
        "SPY": _frame(["2024-01-02", "2024-02-01"], [400.0, 404.0]),
    })
    results = run_multi_horizon([Ev("AAA", date(2024, 1, 2))], src, holding_periods=(21,))
    md = render_report("Small", results)
    assert "Inconclusive" in md
