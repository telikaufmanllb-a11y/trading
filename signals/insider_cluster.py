"""Insider cluster-buy signal — the first concrete, swappable signal module.

Implements the project's signal contract (DECISIONS.md D-0004): `generate_signals(...) -> events`,
so the backtest/analysis pipeline stays signal-agnostic and a future congressional-trade module
can slot in unchanged.

LOOK-AHEAD CORRECTNESS (HARD RULE 1) — the key subtlety this module gets right:
A cluster is only *actionable* once the N-th insider's purchase is PUBLICLY FILED. So the entry
(trigger) date is the filing date at which the rolling window first contains `min_insiders`
DISTINCT insiders — NOT the date of the first buy (which is unknowable as a cluster until later).
The eyeball tool reported the window's first date for inspection; a tradable signal must not.

Coordinated events (fixed-price offerings, director purchase plans) are excluded by default via
the opportunistic classifier (D-0013/D-0015), since they are not the independent accumulation the
hypothesis targets. Joint/affiliated owners must already be collapsed to one insider upstream
(D-0016) — this module counts whatever distinct `insider_cik` values it is given.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from features.opportunistic import InsiderBuy, assess_coordination


@dataclass(frozen=True)
class ClusterBuy:
    """Input record: one insider's open-market purchase of one issuer.

    `insider_cik` should already represent a single economic decision-maker (joint owners
    collapsed upstream, D-0016). `filing_date` is the public-disclosure date (HARD RULE 1).
    """

    issuer_cik: str
    issuer_name: str
    ticker: Optional[str]
    insider_cik: str
    filing_date: date
    price: Optional[float] = None
    transaction_date: Optional[date] = None


@dataclass(frozen=True)
class SignalEvent:
    """An actionable cluster signal. `entry_date` is the earliest date the cluster was knowable."""

    issuer_cik: str
    issuer_name: str
    ticker: Optional[str]
    entry_date: date          # filing date of the N-th insider — the actionable date (HARD RULE 1)
    n_insiders: int
    window_start: date        # earliest member filing date within the triggering window
    window_end: date          # == entry_date
    is_coordinated: bool


def _cluster_trigger(
    insider_first_dates: list[tuple[date, str]],
    *,
    min_insiders: int,
    window_days: int,
) -> Optional[tuple[date, date, set[str]]]:
    """Earliest date a rolling `window_days` window holds `min_insiders` distinct insiders.

    `insider_first_dates` is one (earliest_filing_date, insider_cik) per distinct insider.
    Returns (trigger_date, window_start, member_ciks) or None. Two-pointer sweep over sorted
    dates; the trigger is the EARLIEST window that reaches the threshold, so entry happens the
    moment the cluster becomes public — never earlier.
    """
    fd = sorted(insider_first_dates, key=lambda t: t[0])
    left = 0
    for right in range(len(fd)):
        while fd[right][0] - fd[left][0] > timedelta(days=window_days):
            left += 1
        if right - left + 1 >= min_insiders:
            members = {fd[k][1] for k in range(left, right + 1)}
            return fd[right][0], fd[left][0], members
    return None


def generate_signals(
    buys: Iterable[ClusterBuy],
    *,
    min_insiders: int = 3,
    window_days: int = 15,
    exclude_coordinated: bool = True,
    date_range: Optional[tuple[date, date]] = None,
) -> list[SignalEvent]:
    """Turn insider open-market-purchase records into actionable cluster signal events.

    Events are emitted at the FILING-DATE trigger (HARD RULE 1) and, by default, only for clusters
    that pass the opportunistic filter. `date_range` (inclusive) filters on `entry_date`.
    """
    by_issuer: dict[str, list[ClusterBuy]] = {}
    for b in buys:
        by_issuer.setdefault(b.issuer_cik, []).append(b)

    events: list[SignalEvent] = []
    for issuer_cik, issuer_buys in by_issuer.items():
        # Earliest filing date per distinct insider (when their purchase first became public).
        first_date: dict[str, date] = {}
        for b in issuer_buys:
            if b.insider_cik not in first_date or b.filing_date < first_date[b.insider_cik]:
                first_date[b.insider_cik] = b.filing_date

        trig = _cluster_trigger(
            [(d, cik) for cik, d in first_date.items()],
            min_insiders=min_insiders,
            window_days=window_days,
        )
        if trig is None:
            continue
        trigger_date, window_start, member_ciks = trig

        # Assess coordination on the member insiders' buys (within the triggering window).
        member_buys = [
            InsiderBuy(b.insider_cik, b.price, b.transaction_date or b.filing_date)
            for b in issuer_buys
            if b.insider_cik in member_ciks and b.price is not None
        ]
        assessment = assess_coordination(member_buys)
        if exclude_coordinated and assessment.is_coordinated:
            continue

        if date_range is not None and not (date_range[0] <= trigger_date <= date_range[1]):
            continue

        rep = issuer_buys[0]
        events.append(
            SignalEvent(
                issuer_cik=issuer_cik,
                issuer_name=rep.issuer_name,
                ticker=rep.ticker,
                entry_date=trigger_date,
                n_insiders=len(member_ciks),
                window_start=window_start,
                window_end=trigger_date,
                is_coordinated=assessment.is_coordinated,
            )
        )

    events.sort(key=lambda e: e.entry_date)
    return events
