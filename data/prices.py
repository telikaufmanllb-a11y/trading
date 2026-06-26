"""Price data interface — swappable, point-in-time, and delisting-aware.

The backtest must NEVER use a survivor-only price database (HARD RULE 2): a database of only-
survivors silently deletes every cluster-buy that went to zero and makes any strategy look
brilliant. This module encodes that discipline structurally:

  * `PriceSource` is an abstract, swappable contract. The backtest depends only on this, so the
    concrete provider can change (CRSP / Norgate / Sharadar / a survivorship-free build) without
    touching strategy code (architecture goal, CLAUDE.md §4; provider policy D-0010).
  * Delisting is a first-class concept (`DelistingInfo`), not an absence of data. A stock that
    stopped trading is represented explicitly so the backtest realizes its delisting return
    instead of silently dropping the position.
  * `holding_period_return` is the survivorship-safe primitive: if the stock delisted before the
    horizon, it applies the delisting return; if the delisting return is UNKNOWN it defaults to a
    conservative total loss (-100%) rather than treating the name as a survivor.

yfinance is deliberately NOT adapted here — it is survivor-biased and must stay off the backtest
path (D-0010). Eyeball-only scripts may use it, clearly fenced, elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

# Canonical price schema. `adj_close` is total-return adjusted (splits + dividends).
PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


@dataclass(frozen=True)
class DelistingInfo:
    """How and when a security stopped trading.

    `delisting_return` is the return realized on delisting (e.g. -1.0 for a wipeout, or a small
    residual for a cash buyout above the last trade). None means UNKNOWN — callers must treat
    unknown conservatively, never as zero/survivor (HARD RULE 2).
    """

    ticker: str
    delisting_date: date
    delisting_return: Optional[float]
    reason: Optional[str] = None


class PriceSource(ABC):
    """Abstract point-in-time, delisting-aware price provider."""

    @abstractmethod
    def prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """Return a DataFrame indexed by trading date (ascending) with `PRICE_COLUMNS`, covering
        [start, end]. May be empty or end early if the security delisted within the range."""

    @abstractmethod
    def delisting(self, ticker: str) -> Optional[DelistingInfo]:
        """Return delisting info for `ticker`, or None if it is still listed / never listed."""

    def holding_period_return(
        self,
        ticker: str,
        entry_date: date,
        exit_date: date,
        *,
        missing_delisting_return: float = -1.0,
    ) -> Optional[float]:
        """Total return from `entry_date` to `exit_date`, correctly handling delisting.

        Survivorship-safe (HARD RULE 2):
          * Entry uses the first adjusted close on/after `entry_date` (filing-date entry happens at
            the next available bar).
          * If the security delisted on/before `exit_date`, the return runs to the last bar and is
            compounded with the delisting return; an UNKNOWN delisting return falls back to
            `missing_delisting_return` (default -100%), never silently to zero.
          * Otherwise exit uses the last adjusted close on/before `exit_date`.

        Returns None only when there is no usable entry price at all.
        """
        df = self.prices(ticker, entry_date, exit_date)
        if df.empty or "adj_close" not in df.columns:
            return None
        entry_rows = df[df.index >= pd.Timestamp(entry_date)]
        if entry_rows.empty:
            return None
        entry_price = float(entry_rows["adj_close"].iloc[0])
        if entry_price <= 0:
            return None

        delist = self.delisting(ticker)
        if delist is not None and delist.delisting_date <= exit_date:
            # Run to the last available bar at/before the delisting, then apply the delisting return.
            up_to = df[df.index <= pd.Timestamp(delist.delisting_date)]
            last_price = float(up_to["adj_close"].iloc[-1]) if not up_to.empty else entry_price
            price_return = last_price / entry_price - 1.0
            dret = delist.delisting_return
            if dret is None:
                dret = missing_delisting_return
            return (1.0 + price_return) * (1.0 + dret) - 1.0

        exit_rows = df[df.index <= pd.Timestamp(exit_date)]
        if exit_rows.empty:
            return None
        exit_price = float(exit_rows["adj_close"].iloc[-1])
        return exit_price / entry_price - 1.0


class InMemoryPriceSource(PriceSource):
    """Dict-backed `PriceSource` for tests and small experiments.

    `frames` maps ticker -> DataFrame (date-indexed, `PRICE_COLUMNS`). `delistings` maps ticker ->
    `DelistingInfo`. Validates the schema on construction so test data can't drift from the
    contract.
    """

    def __init__(
        self,
        frames: dict[str, pd.DataFrame],
        delistings: Optional[dict[str, DelistingInfo]] = None,
    ):
        self._frames = {t: validate_price_frame(df) for t, df in frames.items()}
        self._delistings = dict(delistings or {})

    def prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        df = self._frames.get(ticker)
        if df is None:
            return pd.DataFrame(columns=PRICE_COLUMNS)
        mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        return df.loc[mask]

    def delisting(self, ticker: str) -> Optional[DelistingInfo]:
        return self._delistings.get(ticker)


def validate_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure a price frame matches the canonical schema; return it sorted by date ascending."""
    missing = [c for c in PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"price frame missing required columns: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("price frame must be indexed by a DatetimeIndex of trading dates")
    return df.sort_index()
