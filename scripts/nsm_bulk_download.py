#!/usr/bin/env python3
"""
NSM Bulk Downloader: Production-Grade Overnight Sovereign Bond Prospectus Pipeline

Downloads prospectuses from the FCA National Storage Mechanism (NSM) for sovereign
issuers with comprehensive error handling, adaptive throttling, circuit breaker logic,
and Group A processing (text extraction + metadata + clause scanning).

Architecture:
  - CorpusDB: SQLite wrapper with resumability via status columns
  - Grep-first clause finding: locate clauses before sending to Claude
  - Atomic writes: download to .part, validate, then rename
  - Adaptive throttling: 429/timeout responses trigger exponential backoff
  - Signal handling: SIGINT/SIGTERM for clean shutdown
  - JSONL telemetry: one JSON object per download event
  - Group A processing: inline text extraction, hashing, clause scanning

Usage:
    python scripts/nsm_bulk_download.py [--config CONFIG] [--tiers 1,2,3,4] [--dry-run] [--limit N]

Examples:
    # Full run (all tiers)
    python scripts/nsm_bulk_download.py

    # Tier 1 only (defaulted countries)
    python scripts/nsm_bulk_download.py --tiers 1

    # Dry run: list documents that would be downloaded
    python scripts/nsm_bulk_download.py --dry-run

    # Custom config + limit to 50 docs for testing
    python scripts/nsm_bulk_download.py --config my_config.toml --limit 50
"""

import argparse
import contextlib
import csv
import hashlib
import json
import logging
import re
import signal
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

NSM_API_URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"
NSM_PDF_BASE = "https://data.fca.org.uk/artefacts"
PDF_HEADER = b"%PDF"
DEFAULT_TIMEOUT = 60
DEFAULT_CONFIG = "config.toml"

PROSPECTUS_TYPES = {
    "Publication of a Prospectus",
    "Base Prospectus",
    "Publication of a Supplementary Prospectus",
    "Final Terms",
}

# Country priority tiers (from CLAUDE.md)
COUNTRY_TIERS: dict[int, list[str]] = {
    1: [  # Defaulted / distressed
        "Ghana",
        "Ukraine",
        "Zambia",
        "Belarus",
        "Gabon",
        "Sri Lanka",
        "Congo",
    ],
    2: [  # Frontier/EM sub-investment grade
        "Nigeria",
        "Egypt",
        "Angola",
        "Montenegro",
        "Kenya",
        "Bahrain",
        "Albania",
        "Jordan",
        "Cameroon",
        "Morocco",
        "Rwanda",
        "Bosnia and Herzegovina",
        "Srpska",
    ],
    3: [  # EM investment grade / Gulf
        "UAE - Abu Dhabi",
        "Serbia",
        "Saudi Arabia",
        "Kazakhstan",
        "Uzbekistan",
        "Oman",
        "Qatar",
        "Kuwait",
    ],
    4: [  # Developed markets (control group)
        "Israel",
        "Hungary",
        "Cyprus",
        "Sweden",
        "Canada",
        "Finland",
        "Iceland",
    ],
}

# Clause type patterns for grep scanning
CLAUSE_PATTERNS: dict[str, str] = {
    "CAC": r"(?i)(?:collective action|CAC|modification.*resolution|aggregat(?:ed|ion).*clause|modification.*majority|modification.*voting|Reserved Matter)",
    "PARI_PASSU": r"(?i)(?:pari passu|rank equally|equal(?:ly)? (?:and ratably|rank)|same rank|pro[- ]?rata)",
    "EVENTS_OF_DEFAULT": r"(?i)(?:Events? of Default|failure to pay|moratorium)",
    "GOVERNING_LAW": r"(?i)(?:governing law|governed by|subject to (?:the laws of |English law|New York law))",
    "NEGATIVE_PLEDGE": r"(?i)(?:negative pledge|not.*create.*(?:lien|security interest)|Lien|Security Interest)",
    "SOVEREIGN_IMMUNITY": r"(?i)(?:sovereign immunity|waive.*immunity|irrevocably waive|Waiver of Immunity)",
    "CROSS_DEFAULT": r"(?i)(?:cross[- ]?default|cross[- ]?acceleration)",
    "EXTERNAL_INDEBTEDNESS": r"(?i)(?:External Indebtedness|Public External Indebtedness)",
    "ACCELERATION": r"(?i)(?:acceleration|accelerate|immediately due and payable)",
    "TRUSTEE_FISCAL_AGENT": r"(?i)(?:Fiscal Agent|Trustee|Agent Bank)",
}

# Metadata extraction patterns
METADATA_PATTERNS: dict[str, str] = {
    "governing_law": r"(?i)(English law|New York law|governed by the laws of [A-Z][a-z]+)",
    "isin": r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b",
    "listing_exchange": r"(?i)(London Stock Exchange|Euronext Dublin|Irish Stock Exchange|Ghana Stock Exchange|Luxembourg Stock Exchange|Singapore Exchange)",
}

# Global counters for clean shutdown
_shutdown_requested = False
_global_stats = {
    "downloads_attempted": 0,
    "downloads_success": 0,
    "downloads_failed": 0,
    "downloads_quarantined": 0,
    "bytes_total": 0,
    "documents_parsed": 0,
    "start_time": None,
    "end_time": None,
}


# ============================================================================
# SETUP: PROJECT STRUCTURE, LOGGING, CONFIG
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs" / "nsm"
TEXT_DIR = DATA_DIR / "text" / "nsm"
DB_DIR = DATA_DIR / "db"
TELEMETRY_DIR = DATA_DIR / "telemetry"
LOGS_DIR = PROJECT_ROOT / "logs"
QUARANTINE_DIR = PDF_DIR / "quarantine"

# Create all directories
for directory in [PDF_DIR, TEXT_DIR, DB_DIR, TELEMETRY_DIR, LOGS_DIR, QUARANTINE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Logging setup
LOG_FILE = LOGS_DIR / f"nsm_bulk_download_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


# ============================================================================
# SIGNAL HANDLERS (CLEAN SHUTDOWN)
# ============================================================================

def _signal_handler(signum: int, frame: Any) -> None:
    """Handle SIGINT/SIGTERM gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning(f"Received signal {signum}. Gracefully shutting down...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ============================================================================
# LIGHTWEIGHT TOML PARSER (Python 3.10 compatible)
# ============================================================================

def _parse_toml(content: str) -> dict[str, Any]:
    """Minimal TOML parser for config files. Handles sections and key=value pairs."""
    config: dict[str, Any] = {}
    current_section: str | None = None

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Section header
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if "." in current_section:
                parent, child = current_section.split(".", 1)
                if parent not in config:
                    config[parent] = {}
                current_section = f"{parent}.{child}"
            else:
                if current_section not in config:
                    config[current_section] = {}
            continue

        # Key-value pair
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Type conversion
            if value.lower() in ["true", "false"]:
                value = value.lower() == "true"
            else:
                with contextlib.suppress(ValueError):
                    value = float(value) if "." in value else int(value)

            if current_section:
                if "." in current_section:
                    parent, child = current_section.split(".", 1)
                    if parent not in config:
                        config[parent] = {}
                    if child not in config[parent]:
                        config[parent][child] = {}
                    config[parent][child][key] = value
                else:
                    if current_section not in config:
                        config[current_section] = {}
                    config[current_section][key] = value
            else:
                config[key] = value

    return config


# ============================================================================
# CORPUSDB: THIN SQLITE WRAPPER
# ============================================================================

class CorpusDB:
    """SQLite wrapper for corpus management with resumability."""

    def __init__(self, db_path: Path):
        """Initialize database connection with WAL mode."""
        self.db_path = db_path
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """Get new connection in WAL mode."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist, and migrate schema if needed."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            country TEXT NOT NULL,
            issuer TEXT,
            lei TEXT,
            doc_type TEXT,
            headline TEXT,
            source TEXT DEFAULT 'nsm',
            source_url TEXT,
            pdf_url TEXT,
            local_path TEXT,
            text_path TEXT,
            filing_date TEXT,
            file_size_bytes INTEGER,
            file_hash TEXT,
            page_count INTEGER,
            word_count INTEGER,
            estimated_tokens INTEGER,
            status TEXT DEFAULT 'PENDING',
            quarantine_reason TEXT,
            family_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Migrate: add columns that may be missing from older schema versions
        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(documents)").fetchall()
        }
        migrations = {
            "estimated_tokens": "ALTER TABLE documents ADD COLUMN estimated_tokens INTEGER",
            "family_id": "ALTER TABLE documents ADD COLUMN family_id TEXT",
            "quarantine_reason": "ALTER TABLE documents ADD COLUMN quarantine_reason TEXT",
            "pdf_url": "ALTER TABLE documents ADD COLUMN pdf_url TEXT",
            "text_path": "ALTER TABLE documents ADD COLUMN text_path TEXT",
            "file_hash": "ALTER TABLE documents ADD COLUMN file_hash TEXT",
        }
        for col_name, ddl in migrations.items():
            if col_name not in existing_columns:
                logger.info(f"Migrating schema: adding column '{col_name}'")
                cursor.execute(ddl)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS grep_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL REFERENCES documents(id),
            clause_type TEXT NOT NULL,
            match_count INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT,
            action TEXT NOT NULL,
            status TEXT,
            details TEXT,
            duration_seconds REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        conn.commit()
        conn.close()

    def save_document(self, doc: dict[str, Any]) -> None:
        """Save or update document record."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO documents (
            id, country, issuer, lei, doc_type, headline,
            source, source_url, pdf_url, local_path, text_path,
            filing_date, file_size_bytes, file_hash,
            page_count, word_count, estimated_tokens,
            status, quarantine_reason, family_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status = excluded.status,
            file_size_bytes = excluded.file_size_bytes,
            file_hash = excluded.file_hash,
            page_count = excluded.page_count,
            word_count = excluded.word_count,
            estimated_tokens = excluded.estimated_tokens,
            text_path = excluded.text_path,
            updated_at = datetime('now')
        """, (
            doc["id"], doc["country"], doc.get("issuer"), doc.get("lei"),
            doc.get("doc_type"), doc.get("headline"),
            doc.get("source", "nsm"), doc.get("source_url"), doc.get("pdf_url"),
            doc.get("local_path"), doc.get("text_path"),
            doc.get("filing_date"), doc.get("file_size_bytes"),
            doc.get("file_hash"), doc.get("page_count"),
            doc.get("word_count"), doc.get("estimated_tokens"),
            doc.get("status", "PENDING"), doc.get("quarantine_reason"),
            doc.get("family_id")
        ))

        conn.commit()
        conn.close()

    def update_status(self, doc_id: str, status: str, **kwargs: Any) -> None:
        """Update document status and optional fields."""
        conn = self._get_conn()
        cursor = conn.cursor()

        update_fields = ["status = ?", "updated_at = datetime('now')"]
        params = [status]

        for key, value in kwargs.items():
            if key in ["file_size_bytes", "file_hash", "page_count", "word_count",
                       "estimated_tokens", "text_path", "quarantine_reason"]:
                update_fields.append(f"{key} = ?")
                params.append(value)

        params.append(doc_id)

        cursor.execute(
            f"UPDATE documents SET {', '.join(update_fields)} WHERE id = ?",
            params
        )

        conn.commit()
        conn.close()

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Retrieve document by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_pending(self, source: str = "nsm", tier: int | None = None) -> list[dict[str, Any]]:
        """Get pending documents, optionally filtered by tier."""
        conn = self._get_conn()
        cursor = conn.cursor()

        where_clause = "WHERE source = ? AND status IN ('PENDING', 'FAILED')"
        params = [source]

        if tier:
            countries = COUNTRY_TIERS.get(tier, [])
            if countries:
                placeholders = ", ".join(["?" for _ in countries])
                where_clause += f" AND country IN ({placeholders})"
                params.extend(countries)

        cursor.execute(
            f"SELECT * FROM documents {where_clause} ORDER BY filing_date DESC",
            params
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_telemetry(self, entry: dict[str, Any]) -> None:
        """Append telemetry entry to JSONL file."""
        telemetry_file = TELEMETRY_DIR / f"nsm_run_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(telemetry_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def summary(self) -> dict[str, Any]:
        """Get corpus summary statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT status, COUNT(*) as cnt FROM documents GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) FROM documents WHERE country = 'Ghana'")
        ghana_count = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(file_size_bytes) FROM documents WHERE file_size_bytes IS NOT NULL")
        total_bytes = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM documents WHERE page_count IS NOT NULL")
        parsed_count = cursor.fetchone()[0]

        conn.close()

        return {
            "by_status": status_counts,
            "ghana_count": ghana_count,
            "total_bytes_mb": round(total_bytes / 1024 / 1024, 1),
            "parsed_documents": parsed_count,
        }


# ============================================================================
# CONFIGURATION & ISSUER REFERENCE
# ============================================================================

def load_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from TOML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = _parse_toml(f.read())

    return config


def load_issuer_reference(csv_path: Path) -> dict[str, dict[str, Any]]:
    """Load sovereign issuer reference from CSV."""
    issuers: dict[str, dict[str, Any]] = {}

    if not csv_path.exists():
        logger.warning(f"Issuer reference not found: {csv_path}")
        return issuers

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row.get("country", "").strip()
            if not country:
                continue

            leis = []
            lei_str = row.get("leis", "").strip()
            if lei_str:
                leis = [lei.strip() for lei in lei_str.split(";") if lei.strip()]

            name_variants = []
            names_str = row.get("name_variants", "").strip()
            if names_str:
                name_variants = [n.strip() for n in names_str.split(";") if n.strip()]

            issuers[country] = {
                "leis": leis,
                "name_variants": name_variants,
                "filing_count": int(row.get("filing_count", 0)),
            }

    return issuers


# ============================================================================
# HTTP SESSION & REQUEST UTILITIES
# ============================================================================

def create_session(config: dict[str, Any]) -> requests.Session:
    """Create HTTP session with retry strategy."""
    session = requests.Session()

    nsm_config = config.get("nsm", {})
    max_retries = nsm_config.get("max_retries", 5)
    backoff_factor = nsm_config.get("backoff_factor", 0.5)

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    user_agent = nsm_config.get("user_agent",
                                "Teal Insights Research Pipeline/1.0 (lte@tealinsights.com)")
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "application/json, text/html",
    })

    return session


# ============================================================================
# NSM API QUERYING
# ============================================================================

def query_nsm_api(
    session: requests.Session,
    country: str,
    issuer_ref: dict[str, Any] | None,
    config: dict[str, Any],
    from_offset: int = 0,
    size: int = 100,
) -> dict[str, Any] | None:
    """Query NSM API for a country."""
    nsm_config = config.get("nsm", {})
    timeout = nsm_config.get("timeout", 60)

    # Build query criteria
    # NOTE: Do NOT use latest_flag=Y — it filters out prospectuses, keeping only
    # recent notices (restructuring statements, meeting results, etc.).
    # Instead, we retrieve all filings and filter by doc_type in process_hit().
    criteria = []

    # Prefer LEI if available
    if issuer_ref and issuer_ref.get("leis"):
        for lei in issuer_ref["leis"]:
            criteria.append({"name": "company_lei", "value": ["", lei, "disclose_org", ""]})
        logger.debug(f"Querying {country} by LEI: {issuer_ref['leis']}")
    else:
        # Fall back to name search
        criteria.append({"name": "company_lei", "value": [country, "", "disclose_org", "related_org"]})
        logger.debug(f"Querying {country} by name")

    payload = {
        "from": from_offset,
        "size": size,
        "sort": "submitted_date",
        "sortorder": "desc",
        "criteriaObj": {
            "criteria": criteria,
            "dateCriteria": [],
        },
    }

    try:
        response = session.post(NSM_API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"NSM API error for {country}: {e}")
        return None


# ============================================================================
# PDF DOWNLOAD & VALIDATION
# ============================================================================

def resolve_pdf_url(session: requests.Session, url: str, timeout: int = 60) -> tuple[str | None, float]:
    """
    Resolve PDF URL, handling two-hop case (HTML metadata page -> PDF link).

    Strategy:
      1. If URL path ends in .pdf, assume direct PDF — skip HEAD check entirely
      2. Otherwise, HEAD to check content-type
      3. If HEAD fails or returns unexpected type, try GET and inspect first bytes
      4. If HTML, parse for PDF links (two-hop resolution)

    Returns:
        (pdf_url, resolution_time_seconds) or (None, resolution_time_seconds)
    """
    start_time = time.time()

    try:
        # Fast path: URL ends in .pdf → assume direct PDF link
        if url.lower().endswith(".pdf"):
            elapsed = time.time() - start_time
            logger.debug(f"Direct PDF URL (by extension): {url}")
            return url, elapsed

        # Try HEAD to determine content type
        content_type = ""
        try:
            head_resp = session.head(url, timeout=timeout, allow_redirects=True)
            content_type = head_resp.headers.get("content-type", "").lower()

            # Check if redirect landed on a .pdf URL
            if head_resp.url.lower().endswith(".pdf"):
                elapsed = time.time() - start_time
                return head_resp.url, elapsed

            if "application/pdf" in content_type:
                elapsed = time.time() - start_time
                return url, elapsed

        except requests.exceptions.RequestException as e:
            logger.debug(f"HEAD request failed for {url}: {e}")
            # Fall through to GET-based resolution

        # GET the page and inspect content
        response = session.get(url, timeout=timeout)
        response.raise_for_status()

        # Check if it's actually a PDF despite content-type header
        if response.content[:4] == PDF_HEADER:
            elapsed = time.time() - start_time
            logger.debug(f"Direct PDF (by magic bytes, despite content-type '{content_type}'): {url}")
            return url, elapsed

        # Parse as HTML to find PDF link (two-hop)
        soup = BeautifulSoup(response.content, "html.parser")

        # Strategy 1: Look for <a> tags with .pdf hrefs
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.lower().endswith(".pdf"):
                pdf_link = urljoin(url, href)
                elapsed = time.time() - start_time
                logger.debug(f"Two-hop resolved: {url} -> {pdf_link}")
                return pdf_link, elapsed

        # Strategy 2: Look for <a> tags with "download" text or class
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True).lower()
            if "download" in link_text or "pdf" in link_text:
                pdf_link = urljoin(url, link["href"])
                elapsed = time.time() - start_time
                logger.debug(f"Two-hop resolved (by link text): {url} -> {pdf_link}")
                return pdf_link, elapsed

        # Strategy 3: Look for meta refresh or iframe
        meta_refresh = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta_refresh:
            content_attr = meta_refresh.get("content", "")
            if "url=" in content_attr.lower():
                redirect_url = content_attr.split("url=", 1)[-1].strip().strip("'\"")
                redirect_url = urljoin(url, redirect_url)
                elapsed = time.time() - start_time
                logger.debug(f"Two-hop resolved (meta refresh): {url} -> {redirect_url}")
                return redirect_url, elapsed

        logger.warning(f"Could not find PDF link in {url}")
        elapsed = time.time() - start_time
        return None, elapsed

    except Exception as e:
        logger.debug(f"URL resolution error for {url}: {e}")
        elapsed = time.time() - start_time
        return None, elapsed


def download_pdf(
    session: requests.Session,
    pdf_url: str,
    target_path: Path,
    timeout: int = 60,
) -> tuple[bool, int, str | None]:
    """
    Download PDF with atomic write (to .part, then rename).

    Returns:
        (success, file_size_bytes, error_message)
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")

    try:
        response = session.get(pdf_url, timeout=timeout, stream=True)
        response.raise_for_status()

        content = response.content

        # Validate PDF header
        if not content.startswith(PDF_HEADER):
            return False, 0, "Invalid PDF header"

        # Write atomically
        with open(temp_path, "wb") as f:
            f.write(content)

        temp_path.rename(target_path)

        return True, len(content), None

    except requests.exceptions.Timeout:
        return False, 0, "Download timeout"
    except requests.exceptions.HTTPError as e:
        return False, 0, f"HTTP {e.response.status_code}"
    except Exception as e:
        return False, 0, str(e)
    finally:
        # Clean up .part file if it exists
        if temp_path.exists():
            with contextlib.suppress(Exception):
                temp_path.unlink()


# ============================================================================
# TEXT EXTRACTION & GROUP A PROCESSING
# ============================================================================

def extract_text_with_fitz(pdf_path: Path) -> tuple[str | None, int, int]:
    """
    Extract text from PDF using PyMuPDF (fitz).

    Returns:
        (text, page_count, word_count) or (None, 0, 0) on error
    """
    try:
        doc = fitz.open(str(pdf_path))
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text_parts.append(page.get_text())

        page_count = len(doc)
        doc.close()

        text = "\n".join(text_parts)
        word_count = len(text.split())

        return text, page_count, word_count

    except Exception as e:
        logger.warning(f"Text extraction failed for {pdf_path}: {e}")
        return None, 0, 0


def compute_md5(file_path: Path) -> str:
    """Compute MD5 hash of file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def scan_for_clauses(text: str) -> dict[str, int]:
    """Scan text for clause type occurrences."""
    matches = {}

    # Compile patterns once
    compiled = {ct: re.compile(pattern) for ct, pattern in CLAUSE_PATTERNS.items()}

    for clause_type, pattern in compiled.items():
        match_count = len(pattern.findall(text))
        if match_count > 0:
            matches[clause_type] = match_count

    return matches


def estimate_tokens(text: str) -> int:
    """Rough token estimation (OpenAI uses ~4 chars per token)."""
    return len(text) // 4


def group_a_process(
    pdf_path: Path,
    text_path: Path,
    doc_id: str,
    db: CorpusDB,
) -> dict[str, Any] | None:
    """
    Group A processing: text extraction, hashing, clause scanning.

    Returns:
        Dict with extracted metadata or None on failure
    """
    start_time = time.time()

    try:
        # Extract text
        text, page_count, word_count = extract_text_with_fitz(pdf_path)
        if text is None:
            logger.warning(f"Text extraction failed for {doc_id}")
            return None

        # Save text to file
        text_path.parent.mkdir(parents=True, exist_ok=True)
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)

        # Compute hash
        file_hash = compute_md5(pdf_path)
        file_size = pdf_path.stat().st_size

        # Scan for clauses
        clause_matches = scan_for_clauses(text)

        # Estimate tokens
        tokens = estimate_tokens(text)

        elapsed = time.time() - start_time

        logger.debug(f"Group A processed {doc_id}: {page_count} pages, {word_count} words in {elapsed:.2f}s")

        # Update database
        db.update_status(
            doc_id,
            "PARSED",
            file_hash=file_hash,
            file_size_bytes=file_size,
            page_count=page_count,
            word_count=word_count,
            text_path=str(text_path.relative_to(PROJECT_ROOT)),
            estimated_tokens=tokens,
        )

        # Save grep matches
        conn = db._get_conn()
        cursor = conn.cursor()
        for clause_type, count in clause_matches.items():
            cursor.execute("""
            INSERT INTO grep_matches (document_id, clause_type, match_count)
            VALUES (?, ?, ?)
            """, (doc_id, clause_type, count))
        conn.commit()
        conn.close()

        return {
            "status": "parsed",
            "page_count": page_count,
            "word_count": word_count,
            "file_hash": file_hash,
            "estimated_tokens": tokens,
            "clause_matches": clause_matches,
            "duration_seconds": elapsed,
        }

    except Exception as e:
        logger.error(f"Group A processing failed for {doc_id}: {e}")
        db.update_status(doc_id, "PARSE_FAILED", quarantine_reason=str(e))
        return None


# ============================================================================
# MAIN DOWNLOAD LOGIC
# ============================================================================

def country_slug(country: str) -> str:
    """Convert country name to path-safe slug."""
    return country.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(",", "")


def process_hit(
    hit: dict[str, Any],
    country: str,
    session: requests.Session,
    config: dict[str, Any],
    db: CorpusDB,
) -> tuple[str | None, dict[str, Any]]:
    """
    Process single NSM API hit: download, validate, extract metadata.

    Returns:
        (doc_id_if_success, telemetry_dict)
    """
    telemetry: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "country": country,
        "doc_id": None,
        "status": "failed",
        "errors": [],
    }

    try:
        source = hit.get("_source", {})
        doc_id = hit.get("_id", "")
        headline = source.get("headline", "")
        filing_date = source.get("submitted_date", "")
        download_link = source.get("download_link", "")
        lei = source.get("lei", "")
        doc_type = source.get("type", "")
        company = source.get("company", "")

        # Build full download URL from download_link field
        url = f"https://data.fca.org.uk/artefacts/{download_link}" if download_link else ""

        telemetry["doc_id"] = doc_id
        telemetry["headline"] = headline

        # Skip non-prospectus documents (check type field, not headline)
        is_prospectus = doc_type in PROSPECTUS_TYPES
        if not is_prospectus:
            telemetry["status"] = "skipped"
            telemetry["reason"] = "not_prospectus"
            return None, telemetry

        # Check if already downloaded
        existing = db.get_document(doc_id)
        if existing and existing["status"] in ["DOWNLOADED", "PARSED", "EXTRACTED"]:
            telemetry["status"] = "skipped"
            telemetry["reason"] = "already_downloaded"
            return None, telemetry

        # Resolve PDF URL (two-hop handling)
        download_start = time.time()
        pdf_url, resolve_time = resolve_pdf_url(session, url, timeout=config.get("nsm", {}).get("timeout", 60))

        telemetry["two_hop_required"] = resolve_time > 1.0
        telemetry["two_hop_duration_seconds"] = resolve_time

        if not pdf_url:
            telemetry["status"] = "failed"
            telemetry["errors"].append("URL resolution failed")
            return None, telemetry

        # Download PDF
        slug = country_slug(country)
        date_str = filing_date.split("T")[0] if filing_date else "unknown"
        filename = f"{slug}_{date_str}_{doc_id}.pdf"
        pdf_path = PDF_DIR / slug / filename
        text_path = TEXT_DIR / slug / f"{doc_id}.txt"

        success, file_size, error_msg = download_pdf(
            session,
            pdf_url,
            pdf_path,
            timeout=config.get("nsm", {}).get("timeout", 60),
        )

        download_duration = time.time() - download_start
        telemetry["download_duration_seconds"] = download_duration
        telemetry["content_length_bytes"] = file_size

        if not success:
            telemetry["status"] = "failed"
            telemetry["errors"].append(error_msg or "Download failed")

            # Save to database as FAILED
            db.save_document({
                "id": doc_id,
                "country": country,
                "issuer": company,
                "lei": lei,
                "doc_type": doc_type,
                "headline": headline,
                "source": "nsm",
                "source_url": url,
                "pdf_url": pdf_url,
                "filing_date": filing_date,
                "status": "FAILED",
                "quarantine_reason": error_msg,
            })

            return None, telemetry

        # PDF valid, save to database as DOWNLOADED
        db.save_document({
            "id": doc_id,
            "country": country,
            "issuer": company,
            "lei": lei,
            "doc_type": doc_type,
            "headline": headline,
            "source": "nsm",
            "source_url": url,
            "pdf_url": pdf_url,
            "local_path": str(pdf_path.relative_to(PROJECT_ROOT)),
            "filing_date": filing_date,
            "file_size_bytes": file_size,
            "status": "DOWNLOADED",
        })

        logger.info(f"Downloaded: {doc_id} ({file_size / 1024:.1f}KB)")
        telemetry["status"] = "downloaded"

        # Inline Group A processing
        try:
            group_a_result = group_a_process(pdf_path, text_path, doc_id, db)
            if group_a_result:
                telemetry["group_a_status"] = "success"
                telemetry.update(group_a_result)
                return doc_id, telemetry
            else:
                telemetry["group_a_status"] = "failed"
                return doc_id, telemetry
        except Exception as e:
            logger.warning(f"Group A processing skipped for {doc_id}: {e}")
            telemetry["group_a_status"] = "error"
            telemetry["errors"].append(f"Group A: {e}")
            return doc_id, telemetry

    except Exception as e:
        logger.error(f"Hit processing error: {e}")
        telemetry["errors"].append(str(e))
        return None, telemetry


def download_country(
    country: str,
    session: requests.Session,
    config: dict[str, Any],
    issuer_ref: dict[str, dict[str, Any]],
    db: CorpusDB,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Download all prospectuses for a country.

    Returns:
        Summary stats for the country
    """
    global _shutdown_requested

    logger.info(f"Starting downloads for {country}...")

    stats: dict[str, Any] = {
        "country": country,
        "attempted": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "bytes": 0,
        "documents": [],
    }

    from_offset = 0
    page_size = 100
    nsm_config = config.get("nsm", {})
    api_delay = nsm_config.get("delay_api", 1.0)
    download_delay = nsm_config.get("delay_download", 1.0)
    consecutive_failures = 0
    max_consecutive_failures = nsm_config.get("circuit_breaker", {}).get(
        "consecutive_failures_skip_country", 5
    )

    while True:
        if _shutdown_requested:
            logger.info(f"{country}: Shutdown requested, stopping")
            break

        if limit and stats["success"] >= limit:
            logger.info(f"{country}: Reached limit of {limit} documents")
            break

        # Query API
        issuer_data = issuer_ref.get(country)
        response = query_nsm_api(session, country, issuer_data, config, from_offset, page_size)

        if not response:
            logger.error(f"{country}: API query failed at offset {from_offset}")
            break

        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            logger.info(f"{country}: Completed (total pages: {from_offset // page_size})")
            break

        # Process each hit
        for hit in hits:
            if _shutdown_requested:
                logger.info(f"{country}: Shutdown requested, stopping")
                break

            if limit and stats["success"] >= limit:
                break

            doc_id, telemetry = process_hit(hit, country, session, config, db)

            stats["attempted"] += 1

            if doc_id:
                stats["success"] += 1
                consecutive_failures = 0
            else:
                if telemetry.get("status") == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["failed"] += 1
                    consecutive_failures += 1

            stats["bytes"] += telemetry.get("content_length_bytes", 0)
            stats["documents"].append(telemetry)

            # Save telemetry
            db.save_telemetry(telemetry)

            # Check circuit breaker
            if consecutive_failures >= max_consecutive_failures:
                logger.warning(f"{country}: {consecutive_failures} consecutive failures, skipping")
                break

            # Throttle between downloads
            time.sleep(download_delay)

        if _shutdown_requested:
            break

        from_offset += page_size

        # Prevent infinite loops
        if from_offset > 10000:
            logger.warning(f"{country}: Stopping at 10,000 results")
            break

        # Throttle between API calls
        time.sleep(api_delay)

    logger.info(f"{country}: {stats['success']} downloaded, {stats['failed']} failed, {stats['skipped']} skipped")

    return stats


# ============================================================================
# SUMMARY & REPORTING
# ============================================================================

def print_summary(run_stats: dict[str, dict[str, Any]], all_tiers_requested: list[int]) -> None:
    """Print formatted summary report."""
    global _global_stats

    _global_stats["end_time"] = datetime.now()

    start = _global_stats["start_time"]
    end = _global_stats["end_time"]
    duration = end - start if start and end else timedelta(0)
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)

    # Aggregate by tier
    tier_stats: dict[int, dict[str, int]] = defaultdict(lambda: {"attempted": 0, "success": 0, "failed": 0})

    for tier_num in all_tiers_requested:
        for country in COUNTRY_TIERS.get(tier_num, []):
            if country in run_stats:
                stats = run_stats[country]
                tier_stats[tier_num]["attempted"] += stats["attempted"]
                tier_stats[tier_num]["success"] += stats["success"]
                tier_stats[tier_num]["failed"] += stats["failed"]

    # Total across all countries
    total_attempted = sum(s["attempted"] for s in run_stats.values())
    total_success = sum(s["success"] for s in run_stats.values())
    total_failed = sum(s["failed"] for s in run_stats.values())
    total_bytes_mb = sum(s["bytes"] for s in run_stats.values()) / 1024 / 1024

    # Print summary
    print("\n" + "=" * 70)
    print("OVERNIGHT RUN SUMMARY".center(70))
    print("=" * 70)
    print(f"Run:       {start.strftime('%Y-%m-%d %H:%M:%S')} -> {end.strftime('%H:%M:%S')}")
    print("Source:    FCA NSM")
    print(f"Duration:  {hours}h {minutes}m")
    print()
    print(f"Downloads: {total_attempted} attempted, {total_success} success, {total_failed} failed")
    for tier_num in sorted(tier_stats.keys()):
        ts = tier_stats[tier_num]
        print(f"  Tier {tier_num}: {ts['success']}/{ts['attempted']} downloads")
    print()
    print(f"Data:      {total_bytes_mb:.1f}MB total")
    if total_success > 0:
        avg_mb = total_bytes_mb / total_success
        print(f"           {avg_mb:.2f}MB avg per document")
    print()
    print(f"Log:       {LOG_FILE}")
    print("=" * 70)

    # Save summary to file
    summary_path = LOGS_DIR / f"summary_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(summary_path, "w") as f:
        f.write(f"Run:       {start.strftime('%Y-%m-%d %H:%M:%S')} -> {end.strftime('%H:%M:%S')}\n")
        f.write(f"Duration:  {hours}h {minutes}m\n")
        f.write(f"Downloads: {total_attempted} attempted, {total_success} success, {total_failed} failed\n")
        f.write(f"Data:      {total_bytes_mb:.1f}MB\n")
        f.write(f"Log:       {LOG_FILE}\n")

    logger.info(f"Summary saved to {summary_path}")


# ============================================================================
# CLI & MAIN
# ============================================================================

def main() -> int:
    """Main entry point."""
    global _global_stats

    parser = argparse.ArgumentParser(
        description="NSM Bulk Downloader: Production-grade sovereign prospectus pipeline"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / DEFAULT_CONFIG,
        help=f"Path to config.toml (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--tiers",
        type=str,
        default="1,2,3,4",
        help="Comma-separated tier numbers to download (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List documents that would be downloaded without downloading",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max documents to download (for testing)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite database (default: data/db/nsm_corpus.db)",
    )

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    logger.info(f"Loaded config from {args.config}")

    # Parse tiers
    try:
        requested_tiers = [int(t.strip()) for t in args.tiers.split(",")]
    except ValueError:
        logger.error("Invalid tier specification. Use: --tiers 1,2,3,4")
        return 1

    # Build countries list
    countries_to_download = []
    for tier in sorted(requested_tiers):
        countries_to_download.extend(COUNTRY_TIERS.get(tier, []))

    logger.info(f"Will process {len(countries_to_download)} countries across {len(requested_tiers)} tier(s)")

    # Load issuer reference
    issuer_ref = load_issuer_reference(PROJECT_ROOT / "data" / "raw" / "sovereign_issuer_reference.csv")

    # Initialize database.
    # NOTE: SQLite doesn't work on Google Drive File Stream (journal I/O errors).
    # Default to /tmp if no --db flag is given and the data/db dir is not writable.
    if args.db:
        db_path = args.db
    else:
        preferred_path = PROJECT_ROOT / "data" / "db" / "nsm_corpus.db"
        try:
            # Test if we can create/open a SQLite DB here
            test_conn = sqlite3.connect(str(preferred_path))
            test_conn.execute("PRAGMA journal_mode=WAL")
            test_conn.execute("CREATE TABLE IF NOT EXISTS _test (x INTEGER)")
            test_conn.execute("DROP TABLE _test")
            test_conn.close()
            db_path = preferred_path
        except sqlite3.OperationalError:
            db_path = Path("/tmp") / "nsm_corpus.db"
            logger.warning(
                f"Cannot create SQLite DB at {preferred_path} (likely Google Drive). "
                f"Using local path: {db_path}"
            )

    db = CorpusDB(db_path)
    logger.info(f"Using database: {db_path}")

    # Check for pending documents
    pending = db.get_pending("nsm")
    logger.info(f"Database has {len(pending)} pending documents")

    if args.dry_run:
        logger.info("DRY RUN MODE: Not downloading, just listing")
        for doc in pending[:20]:
            logger.info(f"  Would download: {doc['country']} / {doc['headline']}")
        if len(pending) > 20:
            logger.info(f"  ... and {len(pending) - 20} more")
        return 0

    # Create HTTP session
    session = create_session(config)

    # Run download pipeline
    _global_stats["start_time"] = datetime.now()
    logger.info(f"Starting download pipeline at {_global_stats['start_time'].isoformat()}")

    run_stats: dict[str, dict[str, Any]] = {}

    for country in countries_to_download:
        if _shutdown_requested:
            logger.info("Shutdown requested, stopping pipeline")
            break

        stats = download_country(
            country,
            session,
            config,
            issuer_ref,
            db,
            limit=args.limit,
        )
        run_stats[country] = stats

    # Print summary
    print_summary(run_stats, requested_tiers)

    session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
