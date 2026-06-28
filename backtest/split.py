"""Train/holdout splitting for out-of-sample validation (HARD RULE 4).

The discipline this enforces: choose parameters on the TRAIN period, then validate ONCE on a
HOLDOUT period you never peeked at. Re-touching the holdout invalidates it. This module makes the
split explicit and chronological (never random — that would leak future information across the
boundary); the "validate only once" rule is a process commitment the loop must honor, logged in
PROGRESS.md whenever the holdout is touched.

Splits are by FILING-DATE (`entry_date`), the same actionable date the backtest enters on, so the
boundary is meaningful in decision-time terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional


@dataclass(frozen=True)
class TrainHoldout:
    split_date: date
    train: list  # events with entry_date < split_date
    holdout: list  # events with entry_date >= split_date

    @property
    def n_train(self) -> int:
        return len(self.train)

    @property
    def n_holdout(self) -> int:
        return len(self.holdout)


def split_by_date(events: Iterable, split_date: date) -> TrainHoldout:
    """Chronological split: events strictly before `split_date` are train; on/after are holdout."""
    evs = list(events)
    train = [e for e in evs if e.entry_date < split_date]
    holdout = [e for e in evs if e.entry_date >= split_date]
    return TrainHoldout(split_date=split_date, train=train, holdout=holdout)


def choose_split_date(events: Iterable, train_fraction: float = 0.7) -> Optional[date]:
    """Pick a split date so ~`train_fraction` of events (chronologically) fall in train.

    Returns None if there are no events. Uses the entry_date at the fraction-th position so the
    boundary lands on a real event date; ties on a date all go to the same side via `split_by_date`.
    """
    evs = sorted(events, key=lambda e: e.entry_date)
    if not evs:
        return None
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be in (0, 1)")
    idx = max(1, min(len(evs) - 1, round(len(evs) * train_fraction)))
    return evs[idx].entry_date


def split_by_fraction(events: Iterable, train_fraction: float = 0.7) -> TrainHoldout:
    """Convenience: choose a chronological split date for ~`train_fraction` train, then split."""
    evs = list(events)
    cut = choose_split_date(evs, train_fraction)
    if cut is None:
        return TrainHoldout(split_date=date.min, train=[], holdout=[])
    return split_by_date(evs, cut)
