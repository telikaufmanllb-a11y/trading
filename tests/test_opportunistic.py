"""Tests for opportunistic-vs-coordinated cluster classification (pure, offline)."""

from datetime import date

from features.opportunistic import InsiderBuy, assess_coordination


def _buy(cik, price, d):
    return InsiderBuy(insider_cik=cik, price=price, transaction_date=d)


def test_fixed_price_same_day_cluster_is_coordinated():
    # The FCBM pattern: many insiders, uniform price, single date → coordinated offering.
    d = date(2026, 6, 22)
    buys = [_buy(c, 12.50, d) for c in ["A", "B", "C", "D", "E"]]
    a = assess_coordination(buys)
    assert a.is_coordinated is True
    assert a.n_insiders == 5
    assert a.price_cv == 0.0
    assert a.span_days == 0


def test_dispersed_prices_over_days_is_opportunistic():
    # Independent accumulation: different prices, spread across the window → NOT coordinated.
    buys = [
        _buy("A", 10.00, date(2024, 3, 1)),
        _buy("B", 10.80, date(2024, 3, 4)),
        _buy("C", 9.60, date(2024, 3, 11)),
    ]
    a = assess_coordination(buys)
    assert a.is_coordinated is False
    assert a.price_cv > 0.01
    assert a.span_days == 10


def test_uniform_price_but_spread_in_time_not_flagged():
    # Same price but spread over days — could be coincidence; require BOTH signals.
    buys = [
        _buy("A", 20.00, date(2024, 3, 1)),
        _buy("B", 20.00, date(2024, 3, 10)),
        _buy("C", 20.00, date(2024, 3, 12)),
    ]
    a = assess_coordination(buys)
    assert a.is_coordinated is False
    assert any("not flagged" in r for r in a.reasons)


def test_same_day_but_dispersed_prices_not_flagged():
    # Busy day, but genuinely different prices → independent, not an offering.
    d = date(2024, 3, 5)
    buys = [_buy("A", 5.00, d), _buy("B", 5.50, d), _buy("C", 4.70, d)]
    a = assess_coordination(buys)
    assert a.is_coordinated is False
    assert a.price_cv > 0.01


def test_multiple_buys_per_insider_aggregate_to_one_price():
    # One insider's several same-day fills shouldn't inflate insider count or skew dispersion.
    d = date(2024, 3, 5)
    buys = [
        _buy("A", 12.50, d), _buy("A", 12.50, d), _buy("A", 12.50, d),
        _buy("B", 12.50, d),
        _buy("C", 12.50, d),
    ]
    a = assess_coordination(buys)
    assert a.n_insiders == 3
    assert a.is_coordinated is True


def test_empty_is_not_coordinated():
    a = assess_coordination([])
    assert a.is_coordinated is False
    assert a.n_insiders == 0
