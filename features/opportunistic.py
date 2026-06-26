"""Opportunistic-vs-coordinated classification for insider buy clusters.

Motivated by the Stage 1 eyeball finding (DECISIONS.md D-0013): SEC transaction code `P` means
"open market OR private purchase," so a cluster of code-P buys can actually be a *coordinated
capital event* — e.g. 15 insiders all subscribing to a fixed-price offering on the same day
(observed at FCBM: 15 insiders, uniform $12.50, one date). That is the OPPOSITE of the
opportunistic, *independent* accumulation the hypothesis targets, and counting it as a cluster
would inflate the signal with non-predictive events.

This module flags coordinated-looking clusters so the signal layer can exclude or down-weight
them. It is a PROTOTYPE: the thresholds below are starting points with economic rationale
(HARD RULE 5), to be validated against labeled examples before they define a tradable signal.

It is a pure, offline-testable function over per-insider buy records — no I/O, no look-ahead.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional


@dataclass(frozen=True)
class InsiderBuy:
    """One insider's open-market purchase, reduced to what coordination detection needs."""

    insider_cik: str
    price: float
    transaction_date: date


@dataclass(frozen=True)
class CoordinationAssessment:
    n_insiders: int
    price_cv: float                 # coefficient of variation of per-insider prices (0 = identical)
    distinct_transaction_dates: int
    span_days: int                  # calendar days between earliest and latest transaction
    is_coordinated: bool
    reasons: tuple[str, ...]


# Provisional thresholds — economic rationale, not curve-fitting (HARD RULE 5):
#  * A fixed-price offering/placement produces ~0 price dispersion across insiders. Genuinely
#    independent open-market buys differ by the intraday range and each insider's own limit, so
#    even same-day independent buys usually disperse by >1%. 1% is a deliberately conservative line.
#  * Offerings are transacted/dated en masse on a single date; independent accumulation tends to
#    spread over the (e.g. 15-day) cluster window.
DEFAULT_PRICE_CV_THRESHOLD = 0.01
DEFAULT_MAX_SPAN_DAYS_FOR_COORDINATED = 1


def assess_coordination(
    buys: Iterable[InsiderBuy],
    *,
    price_cv_threshold: float = DEFAULT_PRICE_CV_THRESHOLD,
    max_span_days: int = DEFAULT_MAX_SPAN_DAYS_FOR_COORDINATED,
) -> CoordinationAssessment:
    """Assess whether a cluster of insider buys looks coordinated (offering) vs. independent.

    Aggregates to one representative price per insider (mean of their buys), then looks at price
    dispersion and date concentration across DISTINCT insiders. A cluster is flagged coordinated
    only when BOTH the prices are near-uniform AND the buys are concentrated in time — either alone
    is too weak (a cheap stock can have low dispersion; a single busy day can be coincidence).
    """
    # Aggregate to per-insider mean price, and collect transaction dates.
    by_insider: dict[str, list[float]] = {}
    dates: list[date] = []
    for b in buys:
        by_insider.setdefault(b.insider_cik, []).append(b.price)
        dates.append(b.transaction_date)

    n = len(by_insider)
    if n == 0:
        return CoordinationAssessment(0, 0.0, 0, 0, False, ("no buys",))

    insider_prices = [statistics.fmean(ps) for ps in by_insider.values()]
    mean_price = statistics.fmean(insider_prices)
    if mean_price > 0 and len(insider_prices) >= 2:
        stdev = statistics.pstdev(insider_prices)
        price_cv = stdev / mean_price
    else:
        price_cv = 0.0

    distinct_dates = len(set(dates))
    span_days = (max(dates) - min(dates)).days if dates else 0

    reasons: list[str] = []
    near_uniform_price = len(insider_prices) >= 2 and price_cv <= price_cv_threshold
    time_concentrated = span_days <= max_span_days
    if near_uniform_price:
        reasons.append(f"near-uniform price across insiders (cv={price_cv:.4f} ≤ {price_cv_threshold})")
    if time_concentrated:
        reasons.append(f"buys concentrated in time (span={span_days}d ≤ {max_span_days})")

    # Require BOTH signals: a fixed-price, single-window event. Need ≥2 insiders to judge price.
    is_coordinated = near_uniform_price and time_concentrated and n >= 2
    if not is_coordinated and reasons:
        reasons.append("→ not flagged: needs BOTH near-uniform price AND time concentration")

    return CoordinationAssessment(
        n_insiders=n,
        price_cv=price_cv,
        distinct_transaction_dates=distinct_dates,
        span_days=span_days,
        is_coordinated=is_coordinated,
        reasons=tuple(reasons) if reasons else ("looks independent/opportunistic",),
    )
