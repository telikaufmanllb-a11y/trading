"""Tests for the prototype yfinance adapter — the pure column-mapping, no network."""

import pandas as pd
import pytest

from data.prices import PRICE_COLUMNS
from data.prices_prototype import to_price_frame


def _raw_flat():
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {"Open": [10, 11], "High": [10, 11], "Low": [10, 11], "Close": [10, 11],
         "Adj Close": [9.9, 10.9], "Volume": [100, 200]},
        index=idx,
    )


def test_maps_flat_columns_to_schema():
    df = to_price_frame(_raw_flat())
    assert list(df.columns) == PRICE_COLUMNS
    assert df["adj_close"].iloc[0] == 9.9
    assert isinstance(df.index, pd.DatetimeIndex)


def test_auto_adjust_without_adj_close_uses_close():
    raw = _raw_flat().drop(columns=["Adj Close"])
    df = to_price_frame(raw)
    assert (df["adj_close"] == df["close"]).all()


def test_maps_multiindex_columns():
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Adj Close", "Volume"], ["AAA"]])
    raw = pd.DataFrame([[1, 1, 1, 1, 0.9, 100], [2, 2, 2, 2, 1.9, 200]], index=idx, columns=cols)
    df = to_price_frame(raw, ticker="AAA")
    assert list(df.columns) == PRICE_COLUMNS
    assert df["adj_close"].iloc[1] == 1.9


def test_missing_required_column_raises():
    raw = _raw_flat().drop(columns=["Volume"])
    with pytest.raises(ValueError, match="missing columns"):
        to_price_frame(raw)
