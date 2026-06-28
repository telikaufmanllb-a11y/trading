"""Tests for analysis/metrics — including the implausibility warnings (HARD RULE 6)."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pytest

from analysis.metrics import compound, compute_metrics, max_drawdown, sharpe, t_stat


def test_compound():
    assert compound([0.1, 0.1]) == pytest.approx(0.21)
    assert compound([0.5, -1.0]) == pytest.approx(-1.0)  # wipeout


def test_max_drawdown():
    # +20% then -50%: equity 1.2 -> 0.6, drawdown -50%.
    assert max_drawdown([0.2, -0.5]) == pytest.approx(-0.5)
    assert max_drawdown([0.1, 0.1]) == pytest.approx(0.0)  # monotonic up


def test_sharpe_and_tstat():
    assert sharpe([0.1, 0.1, 0.1]) is None       # zero variance
    assert sharpe([0.1]) is None                  # too few
    assert sharpe([0.2, -0.1, 0.1, 0.0]) is not None
    assert t_stat([0.2, -0.1, 0.1, 0.0]) is not None


# Minimal fake BacktestResult-like object for compute_metrics.
@dataclass(frozen=True)
class FakeTrade:
    net_return: float
    abnormal_return: Optional[float]


class FakeResult:
    def __init__(self, nets, abns):
        self.trades = [FakeTrade(n, a) for n, a in zip(nets, abns)]

    @property
    def n_trades(self):
        return len(self.trades)

    @property
    def win_rate(self):
        return sum(1 for t in self.trades if t.net_return > 0) / len(self.trades)


def test_compute_metrics_basic():
    res = FakeResult([0.3, -0.1], [0.25, -0.15])
    m = compute_metrics(res)
    assert m.n_trades == 2
    assert m.mean_return == pytest.approx(0.1)
    assert m.win_rate == pytest.approx(0.5)
    assert m.mean_abnormal == pytest.approx(0.05)


def test_few_trades_warning():
    m = compute_metrics(FakeResult([0.1, 0.2], [0.05, 0.1]))
    assert any("too few" in w for w in m.warnings)


def test_implausible_sharpe_warning():
    # Consistently positive, low-variance returns -> high Sharpe -> must warn.
    nets = [0.10, 0.11, 0.09, 0.10, 0.105, 0.095] * 6  # 36 trades, tight cluster
    m = compute_metrics(FakeResult(nets, [0.0] * len(nets)))
    assert m.sharpe_per_trade > 2.0
    assert any("Sharpe" in w and "HARD RULE 6" in w for w in m.warnings)


def test_implausible_total_return_warning():
    nets = [0.5] * 10  # compounds to ~57x
    m = compute_metrics(FakeResult(nets, [0.0] * 10))
    assert any("implausibly high" in w for w in m.warnings)
