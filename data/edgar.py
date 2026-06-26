"""Read-only SEC EDGAR client.

Fetches Form 4 filings and submission metadata while respecting the SEC's fair-access policy:
a descriptive User-Agent with a contact email, a rate limit under 10 requests/second, and on-disk
caching so a re-run reads from disk and never re-hits EDGAR for the same document (politeness +
reproducibility, HARD RULE 9).

This module is strictly read-only: it GETs public documents. It never authenticates, never
writes to EDGAR, and has nothing to do with order submission (HARD RULE 7).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

import requests

import config
from data.form4 import Form4, parse_form4_xml

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVES_ROOT = "https://www.sec.gov/Archives/"
ARCHIVES_BASE = ARCHIVES_ROOT + "edgar/data"
DAILY_MASTER_INDEX_URL = (
    ARCHIVES_ROOT + "edgar/daily-index/{year}/QTR{qtr}/master.{yyyymmdd}.idx"
)


@dataclass(frozen=True)
class IndexEntry:
    """One row of an EDGAR master index (pipe-delimited)."""

    cik: str
    company: str
    form_type: str
    date_filed: Optional[date]
    filename: str  # e.g. edgar/data/320193/0001140361-26-025622.txt

    @property
    def accession(self) -> str:
        """Accession number (dashed) derived from the submission .txt filename."""
        return self.filename.rsplit("/", 1)[-1].removesuffix(".txt")

    @property
    def submission_txt_url(self) -> str:
        return ARCHIVES_ROOT + self.filename


def _cik10(cik: str | int) -> str:
    """EDGAR keys submissions by zero-padded 10-digit CIK."""
    return f"{int(str(cik).lstrip('0') or 0):010d}"


class RateLimiter:
    """Simple minimum-interval throttle. Single-process; deliberately conservative."""

    def __init__(self, max_per_sec: float, *, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = 1.0 / max_per_sec
        self._clock = clock
        self._sleep = sleep
        self._last = 0.0

    def wait(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            self._sleep(self.min_interval - elapsed)
        self._last = self._clock()


class EdgarClient:
    """Polite, cached, read-only EDGAR fetcher."""

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        user_agent: Optional[str] = None,
        max_per_sec: Optional[float] = None,
        session: Optional[requests.Session] = None,
    ):
        self.cache_dir = Path(cache_dir or config.RAW_FILINGS_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent or config.EDGAR_USER_AGENT
        self.limiter = RateLimiter(max_per_sec or config.EDGAR_MAX_REQUESTS_PER_SEC)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    # --- low-level cached GET ----------------------------------------------------------------

    def _cache_path(self, url: str) -> Path:
        """Deterministic cache filename: sha256(url) keeps it filesystem-safe and collision-free."""
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / f"{digest}.cache"

    def get_bytes(self, url: str, *, use_cache: bool = True) -> bytes:
        """GET `url`, returning raw bytes. Served from disk cache when available."""
        path = self._cache_path(url)
        if use_cache and path.exists():
            return path.read_bytes()
        self.limiter.wait()
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        content = resp.content
        if use_cache:
            path.write_bytes(content)
        return content

    def get_json(self, url: str, *, use_cache: bool = True) -> dict:
        import json

        return json.loads(self.get_bytes(url, use_cache=use_cache))

    # --- EDGAR-specific helpers --------------------------------------------------------------

    def get_submissions(self, cik: str | int, *, use_cache: bool = True) -> dict:
        """Fetch the submissions JSON (filing history) for an issuer or reporting owner CIK."""
        return self.get_json(SUBMISSIONS_URL.format(cik10=_cik10(cik)), use_cache=use_cache)

    @staticmethod
    def iter_form4_filings(submissions: dict):
        """Yield (accession_no_dashes, filing_date, primary_document) for each Form 4.

        Reads from the `filings.recent` block. `filingDate` here is EDGAR's filing date — the
        public-disclosure date used for entries (HARD RULE 1). Pagination via older `filings.files`
        is intentionally out of scope for this first cut.
        """
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accns = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        primaries = recent.get("primaryDocument", [])
        for i, form in enumerate(forms):
            if form != "4":
                continue
            accn = accns[i].replace("-", "") if i < len(accns) else None
            fdate = _parse_iso_date(dates[i]) if i < len(dates) else None
            primary = primaries[i] if i < len(primaries) else None
            yield accn, fdate, primary

    @staticmethod
    def filing_document_url(cik: str | int, accession_no_dashes: str, document: str) -> str:
        cik_int = int(str(cik).lstrip("0") or 0)
        return f"{ARCHIVES_BASE}/{cik_int}/{accession_no_dashes}/{document}"

    def fetch_form4_xml(
        self, cik: str | int, accession_no_dashes: str, document: str, *, use_cache: bool = True
    ) -> bytes:
        url = self.filing_document_url(cik, accession_no_dashes, document)
        return self.get_bytes(url, use_cache=use_cache)

    @staticmethod
    def raw_document_name(primary_document: str) -> str:
        """Strip EDGAR's XSL viewer directory from a primaryDocument path.

        Submissions list the *styled* primary document (e.g. `xslF345X06/form4.xml`); the raw,
        parseable XML is the same filename without that viewer directory.
        """
        return primary_document.rsplit("/", 1)[-1]

    def load_form4(
        self,
        cik: str | int,
        accession_no_dashes: str,
        primary_document: str,
        filing_date: Optional[date] = None,
        *,
        use_cache: bool = True,
    ) -> Form4:
        """Fetch a single Form 4's raw XML and parse it, attaching the filing date.

        `filing_date` MUST come from submission metadata (HARD RULE 1) — pass the `filingDate`
        yielded by `iter_form4_filings`. It is attached to the result, never derived from the XML.
        """
        raw = self.fetch_form4_xml(
            cik, accession_no_dashes, self.raw_document_name(primary_document), use_cache=use_cache
        )
        accession = _format_accession(accession_no_dashes)
        return parse_form4_xml(raw, filing_date=filing_date, accession=accession)

    # --- daily index (cross-issuer enumeration) ----------------------------------------------

    @staticmethod
    def daily_master_index_url(d: date) -> str:
        qtr = (d.month - 1) // 3 + 1
        return DAILY_MASTER_INDEX_URL.format(
            year=d.year, qtr=qtr, yyyymmdd=d.strftime("%Y%m%d")
        )

    @staticmethod
    def parse_master_index(text: str, *, form_type: Optional[str] = None) -> Iterator[IndexEntry]:
        """Parse a pipe-delimited EDGAR master index into entries.

        The file has a multi-line header; we identify data rows structurally (exactly 5
        pipe-separated fields whose 4th field parses as an ISO date) rather than counting header
        lines, which is robust to header-format drift. `form_type` filters (e.g. "4").
        """
        for line in text.splitlines():
            parts = line.split("|")
            if len(parts) != 5:
                continue
            cik, company, ftype, date_filed, filename = (p.strip() for p in parts)
            d = _parse_index_date(date_filed)
            if d is None:  # header / separator lines fail the date check
                continue
            if form_type is not None and ftype != form_type:
                continue
            yield IndexEntry(cik=cik.lstrip("0") or "0", company=company, form_type=ftype,
                             date_filed=d, filename=filename)

    def get_daily_form4_index(self, d: date, *, use_cache: bool = True) -> list[IndexEntry]:
        """Fetch one day's master index and return its Form 4 entries.

        Returns [] if the index is absent (weekend/holiday → HTTP 404)."""
        url = self.daily_master_index_url(d)
        try:
            text = self.get_bytes(url, use_cache=use_cache).decode("latin-1")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return []
            raise
        return list(self.parse_master_index(text, form_type="4"))

    def iter_issuer_form4s(self, cik: str | int, *, since: Optional[date] = None, use_cache: bool = True):
        """Yield parsed `Form4` objects for every Form 4 in an issuer's recent submissions.

        Each result carries its filing date from submission metadata. `since` filters to filings
        on/after that date. Fetches are rate-limited and disk-cached by the underlying client.
        """
        submissions = self.get_submissions(cik, use_cache=use_cache)
        for accn, fdate, primary in self.iter_form4_filings(submissions):
            if accn is None or primary is None:
                continue
            if since is not None and (fdate is None or fdate < since):
                continue
            yield self.load_form4(cik, accn, primary, fdate, use_cache=use_cache)


def _parse_iso_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_index_date(s: str) -> Optional[date]:
    """EDGAR index 'Date Filed' is YYYYMMDD in daily indexes and YYYY-MM-DD in some others."""
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _format_accession(accession_no_dashes: str) -> str:
    """Re-insert dashes into an 18-digit accession (0000320193-24-000010)."""
    s = accession_no_dashes
    if len(s) == 18 and "-" not in s:
        return f"{s[:10]}-{s[10:12]}-{s[12:]}"
    return s
