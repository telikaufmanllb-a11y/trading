"""Offline test of the end-to-end research orchestration (run_research)."""

from datetime import date

import pandas as pd

from backtest.engine import CostModel
from data.prices import InMemoryPriceSource
from scripts.run_research import cluster_buys_from_records, run_research
from signals.insider_cluster import ClusterBuy


def _frame(dates, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes,
         "adj_close": closes, "volume": [1_000_000] * len(closes)}, index=idx)


class _Rec:
    """Minimal stand-in for an eyeball PurchaseRecord."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_cluster_buys_from_records():
    recs = [_Rec(issuer_cik="1", issuer_name="X", ticker="X", insider_cik="A",
                 filing_date=date(2024, 1, 1), price=10.0, transaction_date=date(2024, 1, 1))]
    buys = cluster_buys_from_records(recs)
    assert len(buys) == 1 and isinstance(buys[0], ClusterBuy)
    assert buys[0].ticker == "X" and buys[0].price == 10.0


def test_run_research_end_to_end_offline():
    # Opportunistic cluster (dispersed prices/dates) on ACME.
    buys = [
        ClusterBuy("100", "Acme", "ACME", "A", date(2024, 1, 3), 10.0, date(2024, 1, 3)),
        ClusterBuy("100", "Acme", "ACME", "B", date(2024, 1, 5), 10.6, date(2024, 1, 5)),
        ClusterBuy("100", "Acme", "ACME", "C", date(2024, 1, 9), 9.7, date(2024, 1, 9)),
    ]
    src = InMemoryPriceSource({
        "ACME": _frame(["2024-01-09", "2024-03-01"], [10.0, 12.0]),
        "SPY": _frame(["2024-01-09", "2024-03-01"], [400.0, 412.0]),
    })
    md, results = run_research(buys, src, holding_periods=(21,),
                               cost_model=CostModel(0, 0, 0, 0.0),
                               data_source_note="UNIT TEST")
    assert "Insider Cluster-Buy Research" in md
    assert "UNIT TEST" in md
    assert "Disclaimer" in md
    # One event was generated and scored at the 21d horizon.
    assert results[21].n_signals == 1


def test_run_research_filters_coordinated_clusters():
    # Same-day uniform-price offering -> no signal -> no trades.
    buys = [ClusterBuy("200", "Bank", "BANK", c, date(2024, 2, 1), 25.0, date(2024, 2, 1))
            for c in ["X", "Y", "Z"]]
    src = InMemoryPriceSource({"SPY": _frame(["2024-02-01", "2024-04-01"], [400.0, 410.0])})
    md, results = run_research(buys, src, holding_periods=(21,))
    assert results[21].n_signals == 0
    assert "0 signal events" in md


def test_run_research_train_holdout_reserves_holdout():
    # Several events across time; with train_fraction the holdout is reserved (not scored).
    buys = []
    for i, mth in enumerate([1, 3, 5, 7, 9]):
        # each "cluster" = 3 distinct insiders within a window on a distinct issuer
        iss = str(100 + i)
        for j, cik in enumerate(["A", "B", "C"]):
            buys.append(ClusterBuy(iss, f"Co{iss}", f"T{iss}", f"{iss}{cik}",
                                   date(2024, mth, 1 + j * 3), 10.0 + j, date(2024, mth, 1 + j * 3)))
    src = InMemoryPriceSource({"SPY": _frame(["2024-01-01", "2025-01-01"], [400.0, 440.0])})
    md, _ = run_research(buys, src, holding_periods=(21,), train_fraction=0.6)
    assert "holdout reserved" in md
    assert "HARD RULE 4" in md
