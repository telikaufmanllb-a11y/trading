"""Stage 1 eyeball tool: find candidate insider cluster-buys in real Form 4 data.

This is an INSPECTION script, deliberately NOT the Stage 2 detector and NOT on the backtest
path. Its only job is to let a human look at real ≥N-insider open-market-buy clusters and confirm
they resemble the literature (opportunistic, small/mid-cap skew) before we automate anything
(CLAUDE.md §6, Stage 1: "build intuition first").

The grouping uses FILING DATE windows, never transaction dates (HARD RULE 1), so what it surfaces
matches what would actually have been knowable at decision time.

Usage:
    python -m scripts.eyeball_clusters --days 3 --min-insiders 3 --window 15 [--max-filings N]
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional


@dataclass(frozen=True)
class PurchaseRecord:
    """One insider's open-market purchase of one issuer, keyed by filing date."""

    issuer_cik: str
    issuer_name: str
    ticker: Optional[str]
    insider_cik: str
    filing_date: date


@dataclass(frozen=True)
class Cluster:
    issuer_cik: str
    issuer_name: str
    ticker: Optional[str]
    insider_ciks: tuple[str, ...]
    window_start: date
    window_end: date

    @property
    def n_insiders(self) -> int:
        return len(self.insider_ciks)


def find_clusters(
    records: Iterable[PurchaseRecord],
    *,
    min_insiders: int = 3,
    window_days: int = 15,
) -> list[Cluster]:
    """Surface issuers where >= `min_insiders` DISTINCT insiders filed open-market buys within a
    rolling `window_days` window (inclusive), measured by FILING DATE.

    Pure function over records so it is unit-testable offline. For each issuer we slide the window
    start over each distinct filing date and keep the window with the most distinct insiders;
    if that count meets the threshold it's a cluster.
    """
    by_issuer: dict[str, list[PurchaseRecord]] = defaultdict(list)
    for r in records:
        by_issuer[r.issuer_cik].append(r)

    clusters: list[Cluster] = []
    for issuer_cik, recs in by_issuer.items():
        recs = sorted(recs, key=lambda r: r.filing_date)
        start_dates = sorted({r.filing_date for r in recs})
        best: Optional[tuple[set[str], date, date]] = None
        for start in start_dates:
            end = start + timedelta(days=window_days)
            insiders = {r.insider_cik for r in recs if start <= r.filing_date <= end}
            if best is None or len(insiders) > len(best[0]):
                best = (insiders, start, end)
        if best and len(best[0]) >= min_insiders:
            rep = recs[0]
            clusters.append(
                Cluster(
                    issuer_cik=issuer_cik,
                    issuer_name=rep.issuer_name,
                    ticker=rep.ticker,
                    insider_ciks=tuple(sorted(best[0])),
                    window_start=best[1],
                    window_end=best[2],
                )
            )
    # Most-clustered first, for eyeballing.
    clusters.sort(key=lambda c: c.n_insiders, reverse=True)
    return clusters


# --- live scan (inspection only) ------------------------------------------------------------

def owner_group_key(form4) -> Optional[str]:
    """Stable key identifying the (possibly joint) reporting person behind ONE filing.

    A single Form 4 can name several joint reporting owners — e.g. an affiliated fund group
    (Energizer 2026-06-22: one filing, six joint owners controlled by one person). They are ONE
    economic decision-maker, so we key by the sorted set of their CIKs and count them as a single
    insider, NOT one per owner. Returns None if no owner CIK is present.
    """
    ciks = sorted(o.cik for o in (form4.owners or []) if o.cik)
    return "+".join(ciks) if ciks else None


def purchase_record_from_form4(form4, *, fallback_cik: str, fallback_name: str) -> Optional[PurchaseRecord]:
    """Reduce one Form 4 to a single PurchaseRecord iff it has an open-market purchase.

    One filing → at most one record (one insider/decision-maker), collapsing joint owners.
    """
    if not form4.open_market_purchases() or form4.filing_date is None:
        return None
    key = owner_group_key(form4)
    if key is None:
        return None
    return PurchaseRecord(
        issuer_cik=form4.issuer_cik or fallback_cik,
        issuer_name=form4.issuer_name or fallback_name,
        ticker=form4.issuer_ticker,
        insider_cik=key,
        filing_date=form4.filing_date,
    )


def collect_purchase_records(
    client, days: list[date], *, max_filings: Optional[int] = None, verbose: bool = True
) -> list[PurchaseRecord]:
    """Walk daily Form 4 indices, parse each filing, and emit ONE record per filing that made an
    open-market purchase (code P / acquired). Rate-limited + disk-cached by `client`.
    """
    from data.form4 import (
        acceptance_datetime_from_submission_header,
        extract_xml_from_submission,
        parse_form4_xml,
    )

    records: list[PurchaseRecord] = []
    n_seen = 0
    for d in days:
        entries = client.get_daily_form4_index(d)
        if verbose:
            print(f"  {d}: {len(entries)} Form 4 filings")
        for e in entries:
            if max_filings is not None and n_seen >= max_filings:
                if verbose:
                    print(f"  reached max-filings cap ({max_filings}); stopping scan")
                return records
            n_seen += 1
            try:
                txt = client.get_bytes(e.submission_txt_url).decode("latin-1")
            except Exception as exc:  # network/document hiccup on a single filing: skip, don't die
                if verbose:
                    print(f"    skip {e.accession}: fetch error {exc}")
                continue
            xml = extract_xml_from_submission(txt)
            if xml is None:
                continue
            acc = acceptance_datetime_from_submission_header(txt)
            filing_date = acc.date() if acc else e.date_filed
            f = parse_form4_xml(xml, filing_date=filing_date, accepted_at=acc)
            rec = purchase_record_from_form4(f, fallback_cik=e.cik, fallback_name=e.company)
            if rec is not None:
                records.append(rec)
    return records


def _trading_days_back(n: int, end: Optional[date] = None) -> list[date]:
    """Last `n` weekdays up to (and including) `end` — weekend indices simply 404 to empty."""
    end = end or date.today()
    out: list[date] = []
    d = end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return sorted(out)


def main() -> None:
    import config
    from data.edgar import EdgarClient

    ap = argparse.ArgumentParser(description="Eyeball insider cluster-buys (Stage 1 inspection).")
    ap.add_argument("--days", type=int, default=3, help="number of recent weekdays to scan")
    ap.add_argument("--min-insiders", type=int, default=3)
    ap.add_argument("--window", type=int, default=15, help="cluster window in days (filing date)")
    ap.add_argument("--max-filings", type=int, default=None, help="cap filings fetched (politeness)")
    args = ap.parse_args()

    client = EdgarClient(user_agent=config.EDGAR_USER_AGENT)
    days = _trading_days_back(args.days)
    print(f"Scanning {days[0]}..{days[-1]} (filing-date windows; HARD RULE 1)")
    records = collect_purchase_records(client, days, max_filings=args.max_filings)
    print(f"Collected {len(records)} insider open-market-purchase records.")
    clusters = find_clusters(records, min_insiders=args.min_insiders, window_days=args.window)
    print(f"\n=== {len(clusters)} candidate cluster(s) "
          f"(>= {args.min_insiders} insiders / {args.window}d) ===")
    for c in clusters:
        print(f"  {c.ticker or '?':6} {c.issuer_name[:38]:38} "
              f"{c.n_insiders} insiders  {c.window_start}..{c.window_end}")


if __name__ == "__main__":
    main()
