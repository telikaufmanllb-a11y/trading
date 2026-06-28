"""End-to-end research run: EDGAR cluster buys → signals → multi-horizon backtest → report.

This is the orchestration glue that ties the whole pipeline together. The core `run_research`
function is pure (events + a PriceSource → markdown + results) and unit-tested offline against
`InMemoryPriceSource`; `main()` wires in real EDGAR signals and a chosen price source.

Honesty guards carried through:
  * Entries are filing-date triggers (HARD RULE 1, from the signal layer).
  * Costs/tax/delisting handled by the engine (HARD RULES 2/3).
  * Train/holdout split available; the holdout is reported as RESERVED, not scored, unless asked
    explicitly — validate it ONCE (HARD RULE 4).
  * If the price source is the survivor-biased prototype, the report says so loudly and no kill-
    condition conclusion is drawn (D-0010/D-0018b).
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Optional

from analysis.report import render_report
from backtest.engine import DEFAULT_HOLDING_PERIODS, CostModel, run_multi_horizon
from backtest.split import split_by_fraction
from signals.insider_cluster import ClusterBuy, generate_signals


def cluster_buys_from_records(records) -> list[ClusterBuy]:
    """Convert eyeball `PurchaseRecord`s (one per filing) into signal `ClusterBuy` inputs."""
    return [
        ClusterBuy(
            issuer_cik=r.issuer_cik, issuer_name=r.issuer_name, ticker=r.ticker,
            insider_cik=r.insider_cik, filing_date=r.filing_date,
            price=r.price, transaction_date=r.transaction_date,
        )
        for r in records
    ]


def run_research(
    buys,
    price_source,
    *,
    holding_periods=DEFAULT_HOLDING_PERIODS,
    cost_model: Optional[CostModel] = None,
    train_fraction: Optional[float] = None,
    title: str = "Insider Cluster-Buy Research",
    data_source_note: str = "",
    min_insiders: int = 3,
    window_days: int = 15,
) -> tuple[str, dict]:
    """Generate signals from `buys`, backtest at each horizon, and render a markdown report.

    If `train_fraction` is set, only the TRAIN slice is scored; the holdout is reserved and merely
    counted in the report (validate it once, separately — HARD RULE 4). Returns (markdown, results).
    """
    events = generate_signals(buys, min_insiders=min_insiders, window_days=window_days)

    config_desc = (f"{len(events)} signal events | min_insiders={min_insiders} "
                   f"window={window_days}d | costs={'default' if cost_model is None else 'custom'}")
    note = data_source_note
    if train_fraction is not None:
        th = split_by_fraction(events, train_fraction)
        scored = th.train
        note = (note + " | " if note else "") + (
            f"TRAIN slice only: {th.n_train} train / {th.n_holdout} holdout reserved "
            f"(split {th.split_date}); validate holdout ONCE separately (HARD RULE 4)")
    else:
        scored = events

    results = run_multi_horizon(scored, price_source, holding_periods=holding_periods,
                               cost_model=cost_model)
    md = render_report(title, results, config_desc=config_desc, data_source_note=note)
    return md, results


def main() -> None:
    import config
    from data.edgar import EdgarClient
    from scripts.eyeball_clusters import _trading_days_back, collect_purchase_records

    ap = argparse.ArgumentParser(description="Run the insider cluster-buy research pipeline.")
    ap.add_argument("--days", type=int, default=5, help="recent weekdays of EDGAR filings to scan")
    ap.add_argument("--max-filings", type=int, default=None)
    ap.add_argument("--train-fraction", type=float, default=None)
    ap.add_argument("--prototype-prices", action="store_true",
                    help="use the FENCED survivor-biased yfinance source (plumbing only)")
    ap.add_argument("--out", type=str, default="reports/research_report.md")
    args = ap.parse_args()

    if not args.prototype_prices:
        raise SystemExit(
            "No trusted price source is configured. A delisting-aware source is required for any "
            "trusted result (HARD RULE 2 / D-0010). To smoke-test PLUMBING only, re-run with "
            "--prototype-prices (survivor-biased; results are NOT a conclusion).")

    from data.prices_prototype import YFinancePriceSource
    price_source = YFinancePriceSource()
    note = "PROTOTYPE / survivor-biased (yfinance) — plumbing only, NOT a conclusion"

    client = EdgarClient(user_agent=config.EDGAR_USER_AGENT)
    days = _trading_days_back(args.days)
    print(f"Scanning {days[0]}..{days[-1]} for insider open-market purchases...")
    records = collect_purchase_records(client, days, max_filings=args.max_filings)
    buys = cluster_buys_from_records(records)
    print(f"{len(buys)} purchase records → generating signals + backtesting...")

    md, _ = run_research(buys, price_source, train_fraction=args.train_fraction,
                         data_source_note=note)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(md)
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
