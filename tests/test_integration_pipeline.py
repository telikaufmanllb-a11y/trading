"""End-to-end pipeline test: signal -> backtest -> metrics, all offline & deterministic.

Proves the modules compose through the signal-agnostic contract (SignalEvent flows straight into
the engine) without any network or real data. This is the plumbing check for the whole stack.
"""

from datetime import date

import pandas as pd

from analysis.metrics import compute_metrics
from backtest.engine import CostModel, run_backtest
from data.prices import InMemoryPriceSource
from signals.insider_cluster import ClusterBuy, generate_signals


def _frame(dates, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes,
         "adj_close": closes, "volume": [1_000_000] * len(closes)},
        index=idx,
    )


def test_signal_to_backtest_to_metrics():
    # An opportunistic cluster: 3 distinct insiders, dispersed prices, over several days.
    buys = [
        ClusterBuy("100", "Acme Microcap", "ACME", "A", date(2024, 1, 3), 10.0, date(2024, 1, 3)),
        ClusterBuy("100", "Acme Microcap", "ACME", "B", date(2024, 1, 5), 10.6, date(2024, 1, 5)),
        ClusterBuy("100", "Acme Microcap", "ACME", "C", date(2024, 1, 9), 9.7, date(2024, 1, 9)),
    ]
    events = generate_signals(buys, min_insiders=3, window_days=15)
    assert len(events) == 1
    assert events[0].entry_date == date(2024, 1, 9)   # look-ahead-correct trigger

    # Exit bars must fall on/before entry+90d (2024-04-08), else they're outside the window.
    src = InMemoryPriceSource({
        "ACME": _frame(["2024-01-09", "2024-04-05"], [10.0, 12.0]),   # +20% over hold
        "SPY": _frame(["2024-01-09", "2024-04-05"], [400.0, 420.0]),  # +5%
    })
    cm = CostModel(commission_bps=1, half_spread_bps=25, slippage_bps=25, short_term_tax_rate=0.35)
    result = run_backtest(events, src, holding_days=90, cost_model=cm)
    assert result.n_trades == 1
    t = result.trades[0]
    assert t.entry_date == date(2024, 1, 9)           # entered at the filing-trigger date
    assert t.gross_return > 0
    assert t.net_return < t.gross_return              # costs + tax bit
    assert t.abnormal_return is not None

    m = compute_metrics(result)
    assert m.n_trades == 1
    assert any("too few" in w for w in m.warnings)    # honest about sample size


def test_coordinated_cluster_produces_no_trade():
    # A fixed-price same-day offering must be filtered out before the backtest ever sees it.
    buys = [
        ClusterBuy("200", "Bank Co", "BANK", c, date(2024, 2, 1), 25.0, date(2024, 2, 1))
        for c in ["X", "Y", "Z"]
    ]
    events = generate_signals(buys, min_insiders=3, window_days=15)
    assert events == []
    src = InMemoryPriceSource({"SPY": _frame(["2024-02-01", "2024-05-01"], [400.0, 410.0])})
    result = run_backtest(events, src, holding_days=90)
    assert result.n_trades == 0
