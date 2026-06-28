"""PROTOTYPE price source (yfinance) — FENCED, survivor-biased, NEVER for trusted results.

⚠️  READ THIS BEFORE USING ⚠️
This adapter exists ONLY to develop and smoke-test the backtest plumbing against real-ish prices.
yfinance is **survivor-biased**: it silently drops delisted/bankrupt/acquired tickers, which is
exactly the failure mode HARD RULE 2 forbids — it would delete the cluster-buys that went to zero
and make any strategy look better than reality. Its `delisting()` therefore always returns None,
which is itself a red flag, not a clean bill of health.

Consequences, enforced by convention (D-0010 / D-0018b):
  * NEVER import this module on the trusted/holdout backtest path. The engine depends only on the
    abstract `PriceSource`; inject this explicitly in clearly-labelled prototype scripts.
  * Any number produced with this source is PROVISIONAL plumbing output, never a conclusion.
  * The kill condition is NOT evaluated on prototype data — only on a delisting-aware source.
"""

from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

import config
from data.prices import PRICE_COLUMNS, DelistingInfo, PriceSource, validate_price_frame

_RENAME = {
    "Open": "open", "High": "high", "Low": "low", "Close": "close",
    "Adj Close": "adj_close", "Volume": "volume",
}


def to_price_frame(raw: pd.DataFrame, ticker: Optional[str] = None) -> pd.DataFrame:
    """Map a yfinance-style OHLCV frame to the canonical `PRICE_COLUMNS` schema (pure/testable).

    Handles both the flat and MultiIndex (per-ticker) column layouts yfinance has used, and the
    auto_adjust case where there is no separate 'Adj Close' (then adj_close := close).
    """
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        # Drop the ticker level (newer yfinance returns (field, ticker) columns).
        lvl = 1 if (ticker is not None and ticker in df.columns.get_level_values(-1)) else None
        df.columns = df.columns.droplevel(lvl) if lvl is not None else df.columns.droplevel(-1)
    df = df.rename(columns=_RENAME)
    if "adj_close" not in df.columns and "close" in df.columns:
        df["adj_close"] = df["close"]
    missing = [c for c in PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"yfinance frame missing columns after mapping: {missing}")
    df = df[PRICE_COLUMNS]
    df.index = pd.DatetimeIndex(df.index).tz_localize(None)
    return validate_price_frame(df)


class YFinancePriceSource(PriceSource):
    """Survivor-biased prototype `PriceSource`. See the module docstring — do not trust results."""

    def __init__(self, cache_dir: Optional[Path] = None, *, warn: bool = True):
        if warn:
            warnings.warn(
                "YFinancePriceSource is survivor-biased PROTOTYPE data — not for trusted results "
                "(HARD RULE 2 / D-0010).",
                stacklevel=2,
            )
        self.cache_dir = Path(cache_dir or (config.STORE_DIR / "yf_prototype"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper().replace('/', '_')}.parquet"

    def prices(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        path = self._cache_path(ticker)
        if path.exists():
            df = pd.read_parquet(path)
        else:
            import yfinance as yf

            raw = yf.download(ticker, progress=False, auto_adjust=False,
                              period="max", actions=False)
            if raw is None or raw.empty:
                return pd.DataFrame(columns=PRICE_COLUMNS)
            df = to_price_frame(raw, ticker)
            df.to_parquet(path)
        mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        return df.loc[mask]

    def delisting(self, ticker: str) -> Optional[DelistingInfo]:
        # yfinance cannot tell us — and that blind spot is precisely the survivorship hazard.
        return None
