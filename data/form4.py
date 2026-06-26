"""SEC Form 4 XML parser.

Parses the ownership-document XML that accompanies a Form 4 filing into typed records.

CRITICAL (HARD RULE 1 — no look-ahead):
The Form 4 XML contains the *transaction date* (`periodOfReport` and each transaction's
`transactionDate`) but NOT the *filing date* — i.e. the moment the filing became public on
EDGAR. The filing/acceptance date lives in the EDGAR submission metadata (the submission JSON's
`acceptanceDateTime`, or the `<ACCEPTANCE-DATETIME>` line in the full-submission header). The
only legal entry signal for the backtest is the filing date, never the transaction date, so this
parser keeps the two strictly separate: it parses transaction content from the XML and accepts
`filing_date` / `accepted_at` as explicit inputs sourced from submission metadata by the client.
It will never fabricate a filing date from the XML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from lxml import etree


@dataclass(frozen=True)
class ReportingOwner:
    """A single insider named on the filing, with their relationship to the issuer."""

    cik: Optional[str]
    name: Optional[str]
    is_director: bool
    is_officer: bool
    is_ten_percent_owner: bool
    is_other: bool
    officer_title: Optional[str] = None


@dataclass(frozen=True)
class Form4Transaction:
    """One non-derivative transaction line.

    `acquired_disposed` is 'A' (acquired) or 'D' (disposed). `code` is the SEC transaction code;
    'P' = open-market purchase (the signal we care about), 'S' = open-market sale, etc.
    `transaction_date` is the date of the trade itself — NOT a valid entry signal on its own.
    """

    security_title: Optional[str]
    transaction_date: Optional[date]
    code: Optional[str]
    shares: Optional[float]
    price_per_share: Optional[float]
    acquired_disposed: Optional[str]
    shares_owned_following: Optional[float] = None

    @property
    def is_open_market_purchase(self) -> bool:
        return self.code == "P" and self.acquired_disposed == "A"

    @property
    def dollar_value(self) -> Optional[float]:
        if self.shares is None or self.price_per_share is None:
            return None
        return self.shares * self.price_per_share


@dataclass(frozen=True)
class Form4:
    """A parsed Form 4 filing.

    `filing_date` / `accepted_at` come from EDGAR submission metadata, not the XML, and may be
    None when the XML is parsed standalone — see the module docstring and HARD RULE 1.
    """

    issuer_cik: Optional[str]
    issuer_name: Optional[str]
    issuer_ticker: Optional[str]
    period_of_report: Optional[date]
    owners: list[ReportingOwner] = field(default_factory=list)
    transactions: list[Form4Transaction] = field(default_factory=list)
    filing_date: Optional[date] = None        # from submission metadata (acceptanceDateTime date)
    accepted_at: Optional[datetime] = None    # full acceptance timestamp, if known
    accession: Optional[str] = None

    def open_market_purchases(self) -> list[Form4Transaction]:
        return [t for t in self.transactions if t.is_open_market_purchase]


# --- XML helpers ----------------------------------------------------------------------------

def _text(node, path: str) -> Optional[str]:
    """Return stripped text at `path` relative to `node`, or None."""
    found = node.find(path)
    if found is None or found.text is None:
        return None
    s = found.text.strip()
    return s or None


def _value(node, path: str) -> Optional[str]:
    """Many Form 4 fields wrap their content in a <value> child; fetch path/value text."""
    return _text(node, f"{path}/value")


def _bool(node, path: str) -> bool:
    """SEC encodes relationship flags as '1'/'0' (sometimes 'true'/'false')."""
    s = _text(node, path)
    return s in {"1", "true", "True"}


def _float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _date(s: Optional[str]) -> Optional[date]:
    if s is None:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _norm_cik(s: Optional[str]) -> Optional[str]:
    """Normalize a CIK to its canonical zero-stripped string (EDGAR pads to 10 digits)."""
    if s is None:
        return None
    s = s.strip().lstrip("0")
    return s or "0"


# --- public API -----------------------------------------------------------------------------

def parse_form4_xml(
    xml: bytes | str,
    *,
    filing_date: Optional[date] = None,
    accepted_at: Optional[datetime] = None,
    accession: Optional[str] = None,
) -> Form4:
    """Parse Form 4 ownership XML into a `Form4`.

    `filing_date`/`accepted_at`/`accession` come from EDGAR submission metadata and are passed
    through unchanged — this function never derives a filing date from the XML (HARD RULE 1).
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    # recover=True tolerates the minor malformations that show up in real historical filings.
    root = etree.fromstring(xml, parser=etree.XMLParser(recover=True))
    if root is None:
        raise ValueError("could not parse Form 4 XML (empty/invalid document)")

    issuer = root.find("issuer")
    issuer_cik = _norm_cik(_text(issuer, "issuerCik")) if issuer is not None else None
    issuer_name = _text(issuer, "issuerName") if issuer is not None else None
    issuer_ticker = _text(issuer, "issuerTradingSymbol") if issuer is not None else None

    owners: list[ReportingOwner] = []
    for ro in root.findall("reportingOwner"):
        owners.append(
            ReportingOwner(
                cik=_norm_cik(_text(ro, "reportingOwnerId/rptOwnerCik")),
                name=_text(ro, "reportingOwnerId/rptOwnerName"),
                is_director=_bool(ro, "reportingOwnerRelationship/isDirector"),
                is_officer=_bool(ro, "reportingOwnerRelationship/isOfficer"),
                is_ten_percent_owner=_bool(ro, "reportingOwnerRelationship/isTenPercentOwner"),
                is_other=_bool(ro, "reportingOwnerRelationship/isOther"),
                officer_title=_text(ro, "reportingOwnerRelationship/officerTitle"),
            )
        )

    transactions: list[Form4Transaction] = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        transactions.append(
            Form4Transaction(
                security_title=_value(tx, "securityTitle"),
                transaction_date=_date(_value(tx, "transactionDate")),
                # NB: transactionCode is a direct text element, NOT wrapped in <value> like the
                # amount fields below — a real schema quirk the fixture test pins down.
                code=_text(tx, "transactionCoding/transactionCode"),
                shares=_float(_value(tx, "transactionAmounts/transactionShares")),
                price_per_share=_float(_value(tx, "transactionAmounts/transactionPricePerShare")),
                acquired_disposed=_value(
                    tx, "transactionAmounts/transactionAcquiredDisposedCode"
                ),
                shares_owned_following=_float(
                    _value(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction")
                ),
            )
        )

    return Form4(
        issuer_cik=issuer_cik,
        issuer_name=issuer_name,
        issuer_ticker=issuer_ticker,
        period_of_report=_date(_text(root, "periodOfReport")),
        owners=owners,
        transactions=transactions,
        filing_date=filing_date,
        accepted_at=accepted_at,
        accession=accession,
    )


def extract_xml_from_submission(text: str) -> Optional[bytes]:
    """Pull the ownership-document XML out of an EDGAR full-submission (.txt) file.

    Full submissions wrap the Form 4 XML in `<XML> ... </XML>` tags inside a `<DOCUMENT>`. The
    daily index points at this .txt, so we extract the XML block to feed `parse_form4_xml`.
    Returns None if no XML block is present.
    """
    start_tag, end_tag = "<XML>", "</XML>"
    start = text.find(start_tag)
    end = text.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return None
    return text[start + len(start_tag): end].strip().encode("utf-8")


def acceptance_datetime_from_submission_header(text: str) -> Optional[datetime]:
    """Extract the acceptance timestamp from a full-submission (.txt) header.

    EDGAR full-submission files begin with a header containing a line like
    `<ACCEPTANCE-DATETIME>20240316180012`. That timestamp (Eastern) is when the filing became
    public — the correct filing-date source for HARD RULE 1. Returns None if not present.
    """
    marker = "<ACCEPTANCE-DATETIME>"
    idx = text.find(marker)
    if idx == -1:
        return None
    raw = text[idx + len(marker): idx + len(marker) + 14].strip()
    try:
        return datetime.strptime(raw, "%Y%m%d%H%M%S")
    except ValueError:
        return None
