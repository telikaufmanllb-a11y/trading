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
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests

import config

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


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


def _parse_iso_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
