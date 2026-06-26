"""Central configuration for the Insider Signal Research Engine.

Keeps paths and the single global random seed in one place so every run is reproducible
(HARD RULE 9). Import this module rather than hard-coding paths or seeds elsewhere.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

# --- Paths -----------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_FILINGS_DIR = DATA_DIR / "raw"          # cached raw EDGAR documents (never re-fetched)
STORE_DIR = DATA_DIR / "store"              # point-in-time parquet/duckdb storage
REPORTS_DIR = ROOT / "reports"

# --- Reproducibility -------------------------------------------------------------------------
RANDOM_SEED = 42

# --- SEC EDGAR fair-access ------------------------------------------------------------------
# The SEC requires a descriptive User-Agent with a contact email and rate-limits to ~10 req/s.
# Override the email via the EDGAR_CONTACT env var; never ship a fake address to EDGAR.
EDGAR_CONTACT = os.environ.get("EDGAR_CONTACT", "insider-research-engine (set EDGAR_CONTACT env)")
EDGAR_USER_AGENT = f"InsiderSignalResearchEngine/0.1 ({EDGAR_CONTACT})"
EDGAR_MAX_REQUESTS_PER_SEC = 8  # stay under the SEC's 10/s ceiling with headroom


def seed_everything(seed: int | None = None) -> int:
    """Seed all RNGs we use. Returns the seed actually applied.

    Call at the start of any process that uses randomness so runs reproduce (HARD RULE 9).
    numpy is seeded lazily so this module imports cleanly before deps are installed.
    """
    s = RANDOM_SEED if seed is None else seed
    random.seed(s)
    try:
        import numpy as np

        np.random.seed(s)
    except ModuleNotFoundError:
        pass  # numpy not installed yet (Stage 0); stdlib seed still applied
    return s


def ensure_dirs() -> None:
    """Create the on-disk storage directories if they don't exist."""
    for d in (RAW_FILINGS_DIR, STORE_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
