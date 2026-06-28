"""Offline tests for the cluster eyeball grouping logic (filing-date windows, HARD RULE 1)."""

from datetime import date

from data.form4 import Form4, Form4Transaction, ReportingOwner
from scripts.eyeball_clusters import (
    PurchaseRecord,
    assess_cluster_coordination,
    find_clusters,
    owner_group_key,
    purchase_record_from_form4,
)


def _owner(cik):
    return ReportingOwner(cik=cik, name=f"Owner {cik}", is_director=True, is_officer=False,
                          is_ten_percent_owner=True, is_other=False)


def _p_buy():
    return Form4Transaction(security_title="Common Stock", transaction_date=date(2026, 6, 22),
                            code="P", shares=1000, price_per_share=12.5, acquired_disposed="A")


def test_joint_owners_on_one_filing_count_as_one_insider():
    # The Energizer trap: one filing, six joint affiliated owners = ONE economic decision-maker.
    f = Form4(
        issuer_cik="1632790", issuer_name="ENERGIZER HOLDINGS", issuer_ticker="ENR",
        period_of_report=date(2026, 6, 22),
        owners=[_owner(c) for c in ["1788233", "1788376", "1788225", "1788232"]],
        transactions=[_p_buy()],
        filing_date=date(2026, 6, 22),
    )
    rec = purchase_record_from_form4(f, fallback_cik="1632790", fallback_name="ENR")
    assert rec is not None
    # The insider key collapses all joint owners into one stable, sorted key.
    assert rec.insider_cik == "1788225+1788232+1788233+1788376"
    # So a single joint filing can never by itself form a >=3-insider cluster.
    assert find_clusters([rec], min_insiders=3, window_days=15) == []


def test_filing_without_open_market_purchase_yields_no_record():
    f = Form4(
        issuer_cik="1", issuer_name="X", issuer_ticker="X", period_of_report=date(2026, 1, 1),
        owners=[_owner("9")],
        transactions=[Form4Transaction("Common", date(2026, 1, 1), "S", 1, 1.0, "D")],
        filing_date=date(2026, 1, 1),
    )
    assert purchase_record_from_form4(f, fallback_cik="1", fallback_name="X") is None


def test_record_captures_mean_price_and_earliest_date():
    f = Form4(
        issuer_cik="1", issuer_name="X", issuer_ticker="X", period_of_report=date(2026, 1, 5),
        owners=[_owner("9")],
        transactions=[
            Form4Transaction("Common", date(2026, 1, 5), "P", 100, 10.0, "A"),
            Form4Transaction("Common", date(2026, 1, 3), "P", 100, 12.0, "A"),
        ],
        filing_date=date(2026, 1, 6),
    )
    rec = purchase_record_from_form4(f, fallback_cik="1", fallback_name="X")
    assert rec.price == 11.0                       # mean of 10 and 12
    assert rec.transaction_date == date(2026, 1, 3)  # earliest P-buy date


def _prec(issuer, insider, d, price):
    return PurchaseRecord(issuer_cik=issuer, issuer_name=f"I{issuer}", ticker="T",
                          insider_cik=insider, filing_date=d, price=price, transaction_date=d)


def test_cluster_coordination_flags_uniform_same_day():
    d = date(2026, 6, 22)
    recs = [_prec("100", c, d, 12.5) for c in ["A", "B", "C"]]
    clusters = find_clusters(recs, min_insiders=3, window_days=15)
    a = assess_cluster_coordination(clusters[0], recs, window_days=15)
    assert a.is_coordinated is True


def test_cluster_coordination_passes_dispersed_buys():
    recs = [
        _prec("100", "A", date(2026, 6, 1), 10.0),
        _prec("100", "B", date(2026, 6, 5), 11.2),
        _prec("100", "C", date(2026, 6, 12), 9.4),
    ]
    clusters = find_clusters(recs, min_insiders=3, window_days=15)
    a = assess_cluster_coordination(clusters[0], recs, window_days=15)
    assert a.is_coordinated is False


def test_owner_group_key_none_when_no_ciks():
    f = Form4(issuer_cik="1", issuer_name="X", issuer_ticker="X", period_of_report=None,
              owners=[ReportingOwner(None, "n", False, False, False, False)],
              transactions=[_p_buy()], filing_date=date(2026, 1, 1))
    assert owner_group_key(f) is None


def _rec(issuer, insider, d, ticker="T"):
    return PurchaseRecord(
        issuer_cik=issuer, issuer_name=f"Issuer {issuer}", ticker=ticker,
        insider_cik=insider, filing_date=d,
    )


def test_three_distinct_insiders_in_window_is_a_cluster():
    recs = [
        _rec("100", "A", date(2024, 3, 1)),
        _rec("100", "B", date(2024, 3, 5)),
        _rec("100", "C", date(2024, 3, 14)),  # within 15d of Mar 1
    ]
    clusters = find_clusters(recs, min_insiders=3, window_days=15)
    assert len(clusters) == 1
    assert clusters[0].n_insiders == 3
    assert clusters[0].insider_ciks == ("A", "B", "C")
    assert clusters[0].window_start == date(2024, 3, 1)


def test_same_insider_repeated_does_not_count_as_three():
    # Distinct insiders, not distinct filings — three buys by one person is not a cluster.
    recs = [
        _rec("100", "A", date(2024, 3, 1)),
        _rec("100", "A", date(2024, 3, 2)),
        _rec("100", "A", date(2024, 3, 3)),
    ]
    assert find_clusters(recs, min_insiders=3, window_days=15) == []


def test_window_boundary_excludes_too_far_apart():
    # A on Mar 1, B on Mar 10, C on Mar 20 — no single 15d window holds all three.
    recs = [
        _rec("100", "A", date(2024, 3, 1)),
        _rec("100", "B", date(2024, 3, 10)),
        _rec("100", "C", date(2024, 3, 20)),
    ]
    # Best window (Mar 1..16 has A,B = 2; Mar 10..25 has B,C = 2) never reaches 3.
    assert find_clusters(recs, min_insiders=3, window_days=15) == []
    # But three insiders with a 25d window would qualify.
    assert len(find_clusters(recs, min_insiders=3, window_days=25)) == 1


def test_separate_issuers_not_merged():
    recs = [
        _rec("100", "A", date(2024, 3, 1)),
        _rec("100", "B", date(2024, 3, 2)),
        _rec("200", "C", date(2024, 3, 2)),
        _rec("200", "D", date(2024, 3, 3)),
    ]
    # Neither issuer reaches 3 distinct insiders.
    assert find_clusters(recs, min_insiders=3, window_days=15) == []


def test_clusters_sorted_by_size_desc():
    recs = [
        # issuer 100: 3 insiders
        _rec("100", "A", date(2024, 3, 1)), _rec("100", "B", date(2024, 3, 2)),
        _rec("100", "C", date(2024, 3, 3)),
        # issuer 200: 4 insiders
        _rec("200", "W", date(2024, 3, 1)), _rec("200", "X", date(2024, 3, 2)),
        _rec("200", "Y", date(2024, 3, 3)), _rec("200", "Z", date(2024, 3, 4)),
    ]
    clusters = find_clusters(recs, min_insiders=3, window_days=15)
    assert [c.n_insiders for c in clusters] == [4, 3]
    assert clusters[0].issuer_cik == "200"


def test_trading_days_between_excludes_weekends():
    from datetime import date
    from scripts.eyeball_clusters import trading_days_between
    # 2024-02-01 (Thu) .. 2024-02-05 (Mon): Thu,Fri,Mon = 3 weekdays (Sat/Sun dropped).
    days = trading_days_between(date(2024, 2, 1), date(2024, 2, 5))
    assert days == [date(2024, 2, 1), date(2024, 2, 2), date(2024, 2, 5)]
    assert trading_days_between(date(2024, 2, 5), date(2024, 2, 1)) == []  # reversed -> empty
