"""EDGAR client tests — exercise caching, rate limiting, and parsing logic with a fake session.

No network is touched: a stub session returns canned bytes so tests are deterministic and fast.
"""

from datetime import date
from pathlib import Path

from data.edgar import EdgarClient, RateLimiter, _cik10, _format_accession

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


class _FakeSession:
    """Counts GETs so we can prove the cache prevents repeat fetches."""

    def __init__(self, content: bytes):
        self.content = content
        self.headers = {}
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return _FakeResponse(self.content)


def test_cik10_padding():
    assert _cik10("320193") == "0000320193"
    assert _cik10(320193) == "0000320193"
    assert _cik10("0000320193") == "0000320193"


def test_cache_prevents_refetch(tmp_path):
    session = _FakeSession(b"hello")
    client = EdgarClient(cache_dir=tmp_path, session=session, max_per_sec=1000)
    url = "https://data.sec.gov/example.json"
    assert client.get_bytes(url) == b"hello"
    assert client.get_bytes(url) == b"hello"  # second call served from disk
    assert session.calls == 1, "cached URL must not be re-fetched"


def test_user_agent_is_set(tmp_path):
    session = _FakeSession(b"x")
    EdgarClient(cache_dir=tmp_path, session=session, user_agent="UA/1 (a@b.com)")
    assert session.headers["User-Agent"] == "UA/1 (a@b.com)"


def test_rate_limiter_spaces_requests():
    # Fake clock/sleep: prove the limiter sleeps for the remaining interval when called too soon.
    now = {"t": 0.0}
    slept = []

    def clock():
        return now["t"]

    def sleep(secs):
        slept.append(secs)
        now["t"] += secs  # advance virtual time as if we slept

    limiter = RateLimiter(max_per_sec=10, clock=clock, sleep=sleep)  # 0.1s min interval
    limiter.wait()          # first call: no wait
    now["t"] += 0.02        # only 0.02s elapses
    limiter.wait()          # must sleep ~0.08s to honor the 0.1s spacing
    assert slept and abs(slept[-1] - 0.08) < 1e-9


def test_filing_document_url():
    url = EdgarClient.filing_document_url("0000320193", "000032019324000010", "form4.xml")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019324000010/form4.xml"
    )


def test_iter_form4_filings_selects_only_form4():
    submissions = {
        "filings": {
            "recent": {
                "form": ["4", "8-K", "4", "3"],
                "accessionNumber": [
                    "0000000000-24-000001",
                    "0000000000-24-000002",
                    "0000000000-24-000003",
                    "0000000000-24-000004",
                ],
                "filingDate": ["2024-03-18", "2024-03-19", "2024-03-20", "2024-03-21"],
                "primaryDocument": ["a.xml", "b.htm", "c.xml", "d.xml"],
            }
        }
    }
    rows = list(EdgarClient.iter_form4_filings(submissions))
    assert len(rows) == 2  # only the two Form 4s
    assert rows[0] == ("000000000024000001", date(2024, 3, 18), "a.xml")
    assert rows[1] == ("000000000024000003", date(2024, 3, 20), "c.xml")


def test_raw_document_name_strips_xsl_viewer_dir():
    assert EdgarClient.raw_document_name("xslF345X06/form4.xml") == "form4.xml"
    assert EdgarClient.raw_document_name("form4.xml") == "form4.xml"
    assert EdgarClient.raw_document_name("a/b/wf-form4_123.xml") == "wf-form4_123.xml"


def test_format_accession():
    assert _format_accession("000032019324000010") == "0000320193-24-000010"
    assert _format_accession("0000320193-24-000010") == "0000320193-24-000010"


def test_load_form4_attaches_filing_date_from_metadata(tmp_path):
    # Serve the saved REAL Apple Form 4 from a fake session; prove load_form4 resolves the raw
    # doc name, parses it, and attaches the caller-supplied filing date (HARD RULE 1) — never
    # the XML's periodOfReport.
    raw = (FIXTURES / "form4_real_aapl.xml").read_bytes()
    session = _FakeSession(raw)
    client = EdgarClient(cache_dir=tmp_path, session=session, max_per_sec=1000)
    fd = date(2026, 6, 17)
    f = client.load_form4(320193, "000114036126025622", "xslF345X06/form4.xml", fd)
    assert f.issuer_ticker == "AAPL"
    assert f.filing_date == fd                      # from metadata
    assert f.period_of_report == date(2026, 6, 15)  # from XML — and distinct from filing_date
    assert f.filing_date != f.period_of_report
    assert f.accession == "0001140361-26-025622"
    # This particular filing is routine (codes M/F), so it must yield NO open-market purchases.
    assert f.open_market_purchases() == []
