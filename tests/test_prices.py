"""Tests for the delisting-aware PriceSource — survivorship handling is the critical part."""

from datetime import date

import pandas as pd
import pytest

from data.prices import (
    PRICE_COLUMNS,
    DelistingInfo,
    InMemoryPriceSource,
    validate_price_frame,
)


def _frame(dates, closes):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes,
         "adj_close": closes, "volume": [1000] * len(closes)},
        index=idx,
    )


def test_validate_rejects_missing_columns():
    bad = pd.DataFrame({"close": [1.0]}, index=pd.DatetimeIndex([pd.Timestamp("2024-01-01")]))
    with pytest.raises(ValueError, match="missing required columns"):
        validate_price_frame(bad)


def test_validate_rejects_non_datetime_index():
    bad = pd.DataFrame({c: [1.0] for c in PRICE_COLUMNS})
    with pytest.raises(ValueError, match="DatetimeIndex"):
        validate_price_frame(bad)


def test_simple_holding_period_return():
    src = InMemoryPriceSource({"AAA": _frame(
        ["2024-01-02", "2024-01-03", "2024-01-31"], [100.0, 101.0, 110.0])})
    r = src.holding_period_return("AAA", date(2024, 1, 2), date(2024, 1, 31))
    assert r == pytest.approx(0.10)


def test_entry_uses_first_bar_on_or_after_entry_date():
    # Filing-date entry lands on the next available trading bar.
    src = InMemoryPriceSource({"AAA": _frame(
        ["2024-01-03", "2024-01-31"], [50.0, 55.0])})
    r = src.holding_period_return("AAA", date(2024, 1, 1), date(2024, 1, 31))
    assert r == pytest.approx(0.10)  # entered at 50 (Jan 3), not before


def test_delisting_to_zero_is_a_total_loss():
    # The cluster-buy that went bankrupt — survivorship's whole point.
    src = InMemoryPriceSource(
        {"ZZZ": _frame(["2024-01-02", "2024-01-15"], [10.0, 8.0])},
        {"ZZZ": DelistingInfo("ZZZ", date(2024, 1, 16), -1.0, "bankruptcy")},
    )
    r = src.holding_period_return("ZZZ", date(2024, 1, 2), date(2024, 3, 1))
    assert r == pytest.approx(-1.0)  # not the +/- of a surviving name


def test_unknown_delisting_return_defaults_conservative():
    # Unknown delisting return must NOT be treated as a survivor — default to total loss.
    src = InMemoryPriceSource(
        {"ZZZ": _frame(["2024-01-02", "2024-01-15"], [10.0, 9.0])},
        {"ZZZ": DelistingInfo("ZZZ", date(2024, 1, 16), None)},
    )
    r = src.holding_period_return("ZZZ", date(2024, 1, 2), date(2024, 3, 1))
    assert r == pytest.approx(-1.0)
    # ...unless the caller deliberately overrides the conservative assumption.
    r2 = src.holding_period_return(
        "ZZZ", date(2024, 1, 2), date(2024, 3, 1), missing_delisting_return=0.0)
    assert r2 == pytest.approx(9.0 / 10.0 - 1.0)


def test_delisting_after_exit_is_ignored():
    # If the name is still listed through the holding period, normal return applies.
    src = InMemoryPriceSource(
        {"AAA": _frame(["2024-01-02", "2024-01-31"], [100.0, 120.0])},
        {"AAA": DelistingInfo("AAA", date(2024, 6, 1), -1.0)},
    )
    r = src.holding_period_return("AAA", date(2024, 1, 2), date(2024, 1, 31))
    assert r == pytest.approx(0.20)


def test_partial_delisting_return_compounds():
    # Cash buyout: price ran 10 -> 12 (last bar), then a final +5% delisting return.
    src = InMemoryPriceSource(
        {"BUY": _frame(["2024-01-02", "2024-01-10"], [10.0, 12.0])},
        {"BUY": DelistingInfo("BUY", date(2024, 1, 11), 0.05, "acquired")},
    )
    r = src.holding_period_return("BUY", date(2024, 1, 2), date(2024, 2, 1))
    assert r == pytest.approx((1.2) * (1.05) - 1.0)


def test_missing_ticker_returns_none():
    src = InMemoryPriceSource({})
    assert src.holding_period_return("NOPE", date(2024, 1, 2), date(2024, 1, 31)) is None
