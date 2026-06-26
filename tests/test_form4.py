"""Deterministic Form 4 parser tests — run against a committed fixture, never the network."""

from datetime import date, datetime
from pathlib import Path

from data.form4 import (
    acceptance_datetime_from_submission_header,
    parse_form4_xml,
)

FIXTURE = Path(__file__).parent / "fixtures" / "form4_sample.xml"


def _parse(**kw):
    return parse_form4_xml(FIXTURE.read_bytes(), **kw)


def test_issuer_fields():
    f = _parse()
    assert f.issuer_cik == "320193"          # zero-stripped canonical CIK
    assert f.issuer_name == "EXAMPLE MICROCAP CORP"
    assert f.issuer_ticker == "EXMC"
    assert f.period_of_report == date(2024, 3, 15)


def test_reporting_owner_roles():
    f = _parse()
    assert len(f.owners) == 1
    owner = f.owners[0]
    assert owner.name == "DOE JANE A"
    assert owner.cik == "1214128"
    assert owner.is_director is True
    assert owner.is_officer is True
    assert owner.is_ten_percent_owner is False
    assert owner.officer_title == "Chief Executive Officer"


def test_transactions_parsed():
    f = _parse()
    assert len(f.transactions) == 2
    buy, sell = f.transactions
    assert buy.code == "P"
    assert buy.acquired_disposed == "A"
    assert buy.shares == 10000
    assert buy.price_per_share == 4.25
    assert buy.dollar_value == 42500.0
    assert buy.shares_owned_following == 110000
    assert sell.code == "S"
    assert sell.acquired_disposed == "D"


def test_open_market_purchase_filter():
    # Only the 'P'/'A' line is an open-market purchase; the 'S'/'D' sale must be excluded.
    f = _parse()
    purchases = f.open_market_purchases()
    assert len(purchases) == 1
    assert purchases[0].is_open_market_purchase is True
    assert purchases[0].shares == 10000


def test_filing_date_is_not_invented_from_xml():
    # HARD RULE 1: parsing the XML alone must NOT yield a filing date. The transaction date is
    # present, but filing_date stays None until supplied from submission metadata.
    f = _parse()
    assert f.filing_date is None
    assert f.accepted_at is None
    assert f.transactions[0].transaction_date == date(2024, 3, 15)


def test_filing_date_passthrough():
    # When the client supplies the filing date from submission metadata, it is preserved as-is.
    fd = date(2024, 3, 18)
    f = _parse(filing_date=fd, accession="0000320193-24-000010")
    assert f.filing_date == fd
    assert f.accession == "0000320193-24-000010"


def test_acceptance_datetime_from_header():
    header = (
        "<SEC-DOCUMENT>0000320193-24-000010.txt\n"
        "<ACCEPTANCE-DATETIME>20240318180012\n"
        "ACCESSION NUMBER: 0000320193-24-000010\n"
    )
    assert acceptance_datetime_from_submission_header(header) == datetime(2024, 3, 18, 18, 0, 12)


def test_acceptance_datetime_missing_returns_none():
    assert acceptance_datetime_from_submission_header("no header here") is None


def test_recovers_from_trailing_garbage():
    # Real filings occasionally have trailing bytes; recover=True should still parse the issuer.
    xml = FIXTURE.read_bytes() + b"\n<!-- stray -->garbage"
    f = parse_form4_xml(xml)
    assert f.issuer_ticker == "EXMC"
