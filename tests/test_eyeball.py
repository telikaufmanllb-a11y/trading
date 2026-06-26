"""Offline tests for the cluster eyeball grouping logic (filing-date windows, HARD RULE 1)."""

from datetime import date

from scripts.eyeball_clusters import PurchaseRecord, find_clusters


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
