"""Tests for daily master-index parsing and full-submission XML extraction (offline)."""

from datetime import date
from pathlib import Path

from data.edgar import EdgarClient
from data.form4 import (
    acceptance_datetime_from_submission_header,
    extract_xml_from_submission,
    parse_form4_xml,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_daily_master_index_url():
    url = EdgarClient.daily_master_index_url(date(2026, 6, 17))  # June → Q2
    assert url == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR2/master.20260617.idx"
    )


def test_parse_master_index_filters_form4():
    text = (FIXTURES / "master_sample.idx").read_text()
    entries = list(EdgarClient.parse_master_index(text, form_type="4"))
    # 3 Form 4s in the fixture; the 8-K and Form 3 must be excluded, header lines skipped.
    assert len(entries) == 3
    e = entries[0]
    assert e.cik == "320193"
    assert e.company == "Apple Inc."
    assert e.form_type == "4"
    assert e.date_filed == date(2026, 6, 17)
    assert e.accession == "0001140361-26-025622"
    assert e.submission_txt_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/0001140361-26-025622.txt"
    )


def test_parse_master_index_handles_yyyymmdd_dates():
    # Regression: daily master index dates are YYYYMMDD, not ISO. A live fetch showed the
    # ISO-only parser silently dropped every row. The fixture now uses the real format.
    text = (FIXTURES / "master_sample.idx").read_text()
    assert "20260617" in text and "2026-06-17" not in text
    entries = list(EdgarClient.parse_master_index(text, form_type="4"))
    assert len(entries) == 3
    assert all(e.date_filed == date(2026, 6, 17) for e in entries)


def test_get_daily_index_treats_403_and_404_as_absent(tmp_path):
    # A not-yet-published daily index (today) 403s; weekend/holiday 404s. Both -> [] not a crash.
    import requests

    from data.edgar import EdgarClient

    class _ErrResponse:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            raise requests.HTTPError(f"{self.status_code}", response=self)

    class _ErrSession:
        def __init__(self, code):
            self.headers = {}
            self._code = code

        def get(self, url, timeout=None):
            return _ErrResponse(self._code)

    for code in (403, 404):
        client = EdgarClient(cache_dir=tmp_path, session=_ErrSession(code), max_per_sec=1000)
        assert client.get_daily_form4_index(date(2026, 6, 26)) == []


def test_parse_master_index_no_filter_returns_all_data_rows():
    text = (FIXTURES / "master_sample.idx").read_text()
    entries = list(EdgarClient.parse_master_index(text))
    assert len(entries) == 5  # 3x Form 4 + 8-K + Form 3, no header rows


def test_extract_and_parse_form4_from_submission():
    text = (FIXTURES / "submission_sample.txt").read_text()
    xml = extract_xml_from_submission(text)
    assert xml is not None
    # The acceptance datetime is the filing-date source (HARD RULE 1), distinct from the XML.
    accepted = acceptance_datetime_from_submission_header(text)
    f = parse_form4_xml(xml, filing_date=accepted.date(), accepted_at=accepted)
    assert f.issuer_ticker == "EXMC"
    assert f.filing_date == date(2026, 6, 17)
    assert f.period_of_report == date(2024, 3, 15)  # transaction period, NOT the filing date
    assert len(f.open_market_purchases()) == 1


def test_extract_xml_missing_returns_none():
    assert extract_xml_from_submission("no xml block here") is None
