"""Tests for the insider cluster signal — the look-ahead-correct trigger date is the crux."""

from datetime import date

from signals.insider_cluster import ClusterBuy, generate_signals


def _buy(insider, d, price=10.0, issuer="100", ticker="AAA"):
    return ClusterBuy(issuer_cik=issuer, issuer_name=f"Issuer {issuer}", ticker=ticker,
                      insider_cik=insider, filing_date=d, price=price, transaction_date=d)


def test_entry_date_is_the_nth_insider_filing_not_the_first():
    # HARD RULE 1: the cluster is only knowable when the 3rd insider's filing is public.
    buys = [
        _buy("A", date(2024, 3, 1), 10.0),
        _buy("B", date(2024, 3, 6), 11.0),
        _buy("C", date(2024, 3, 12), 9.5),  # completes the cluster
    ]
    events = generate_signals(buys, min_insiders=3, window_days=15)
    assert len(events) == 1
    assert events[0].entry_date == date(2024, 3, 12)   # NOT 2024-03-01
    assert events[0].window_start == date(2024, 3, 1)
    assert events[0].n_insiders == 3
    assert events[0].is_coordinated is False


def test_no_signal_when_window_too_short():
    buys = [
        _buy("A", date(2024, 3, 1)),
        _buy("B", date(2024, 3, 10)),
        _buy("C", date(2024, 3, 20)),
    ]
    assert generate_signals(buys, min_insiders=3, window_days=15) == []
    assert len(generate_signals(buys, min_insiders=3, window_days=25)) == 1


def test_coordinated_cluster_excluded_by_default_but_flagged_when_requested():
    # Uniform price, same day = coordinated offering.
    d = date(2024, 3, 5)
    buys = [_buy(c, d, 12.5) for c in ["A", "B", "C"]]
    assert generate_signals(buys, min_insiders=3, window_days=15) == []
    incl = generate_signals(buys, min_insiders=3, window_days=15, exclude_coordinated=False)
    assert len(incl) == 1 and incl[0].is_coordinated is True


def test_repeated_buys_by_same_insider_do_not_form_a_cluster():
    buys = [_buy("A", date(2024, 3, 1)), _buy("A", date(2024, 3, 2)), _buy("A", date(2024, 3, 3))]
    assert generate_signals(buys, min_insiders=3, window_days=15) == []


def test_earliest_distinct_filing_used_per_insider():
    # Insider A files twice; their first filing date is what counts toward the window.
    buys = [
        _buy("A", date(2024, 3, 1), 10.0),
        _buy("A", date(2024, 3, 30), 10.0),
        _buy("B", date(2024, 3, 4), 11.0),
        _buy("C", date(2024, 3, 9), 9.0),
    ]
    events = generate_signals(buys, min_insiders=3, window_days=15)
    assert len(events) == 1
    assert events[0].entry_date == date(2024, 3, 9)  # A(3/1), B(3/4), C(3/9) within 15d


def test_date_range_filters_on_entry_date():
    buys = [
        _buy("A", date(2024, 3, 1)), _buy("B", date(2024, 3, 5)), _buy("C", date(2024, 3, 10)),
    ]
    assert generate_signals(buys, date_range=(date(2024, 1, 1), date(2024, 3, 9))) == []
    assert len(generate_signals(buys, date_range=(date(2024, 1, 1), date(2024, 3, 31)))) == 1


def test_separate_issuers_emit_separate_events():
    buys = [
        _buy("A", date(2024, 3, 1), issuer="100", ticker="AAA"),
        _buy("B", date(2024, 3, 5), issuer="100", ticker="AAA"),
        _buy("C", date(2024, 3, 9), issuer="100", ticker="AAA"),
        _buy("X", date(2024, 4, 1), 5.0, issuer="200", ticker="BBB"),
        _buy("Y", date(2024, 4, 3), 5.4, issuer="200", ticker="BBB"),
        _buy("Z", date(2024, 4, 6), 4.7, issuer="200", ticker="BBB"),
    ]
    events = generate_signals(buys, min_insiders=3, window_days=15)
    assert [e.ticker for e in events] == ["AAA", "BBB"]  # sorted by entry_date
    assert events[0].entry_date < events[1].entry_date
