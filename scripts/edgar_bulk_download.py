#!/usr/bin/env python3
"""
EDGAR Bulk Downloader: Sovereign Bond Prospectus Pipeline

Downloads prospectuses from SEC EDGAR for sovereign issuers.
Key differences from NSM pipeline:
  - Documents are 97% HTML, not PDF → BeautifulSoup text extraction
  - Direct URL construction from submissions.json (no two-hop)
  - Strict rate limit: 10 req/sec (we use 4 req/sec = 250ms spacing)
  - No page numbers for HTML documents → section-level citations

Usage:
    python scripts/edgar_bulk_download.py [--config CONFIG] [--limit N] [--dry-run]
    python scripts/edgar_bulk_download.py --tiers 1        # priority countries only
    python scripts/edgar_bulk_download.py --limit 10       # test with 10 docs
"""

import argparse
import contextlib
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

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{filename}"
USER_AGENT = "Teal Insights lte@tealinsights.com"
DEFAULT_DELAY = 0.25  # 4 req/sec — well under 10 req/sec limit
DEFAULT_TIMEOUT = 60

# Prospectus form types to download
PROSPECTUS_FORMS = {"424B2", "424B5", "424B3", "424B4", "424B1", "FWP"}

# Sovereign CIKs discovered via SIC 8888 query (March 24, 2026)
# Organized by research priority tiers matching NSM pipeline
SOVEREIGN_CIKS: dict[int, list[dict[str, str]]] = {
    1: [  # Countries overlapping with NSM Tier 1-2 priorities + major EM
        {"cik": "0001627521", "country": "Nigeria", "name": "Federal Republic of Nigeria"},
        {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        {"cik": "0000917142", "country": "Colombia", "name": "REPUBLIC OF COLOMBIA"},
        {"cik": "0001719614", "country": "Indonesia", "name": "Republic of Indonesia"},
        {"cik": "0000869687", "country": "Turkey", "name": "REPUBLIC OF TURKEY"},
        {"cik": "0000205317", "country": "Brazil", "name": "FEDERATIVE REPUBLIC OF BRAZIL"},
        {"cik": "0000932419", "country": "South Africa", "name": "REPUBLIC OF SOUTH AFRICA"},
    ],
    2: [  # Latin America + Caribbean
        {"cik": "0000101368", "country": "Mexico", "name": "UNITED MEXICAN STATES"},
        {"cik": "0000019957", "country": "Chile", "name": "REPUBLIC OF CHILE"},
        {"cik": "0000076027", "country": "Panama", "name": "PANAMA REPUBLIC OF"},
        {"cik": "0000077694", "country": "Peru", "name": "PERU REPUBLIC OF"},
        {"cik": "0000102385", "country": "Uruguay", "name": "URUGUAY REPUBLIC OF"},
        {"cik": "0001030717", "country": "Philippines", "name": "REPUBLIC OF THE PHILIPPINES"},
        {"cik": "0001163395", "country": "Jamaica", "name": "GOVERNMENT OF JAMICA"},
        {"cik": "0000053078", "country": "Jamaica", "name": "JAMAICA GOVERNMENT OF"},
        {"cik": "0001179453", "country": "Belize", "name": "GOVERNMENT OF BELIZE"},
    ],
    3: [  # Asia + Europe
        {"cik": "0000873465", "country": "Korea", "name": "REPUBLIC OF KOREA"},
        {"cik": "0000052749", "country": "Israel", "name": "ISRAEL, STATE OF"},
        {"cik": "0000889414", "country": "Hungary", "name": "HUNGARY"},
        {"cik": "0000052782", "country": "Italy", "name": "ITALY REPUBLIC OF"},
    ],
    4: [  # DM / lower priority
        {"cik": "0000931106", "country": "Greece", "name": "HELLENIC REPUBLIC"},
        {"cik": "0000035946", "country": "Finland", "name": "FINLAND REPUBLIC OF"},
        {"cik": "0000225913", "country": "Sweden", "name": "SWEDEN KINGDOM OF"},
        {"cik": "0000230098", "country": "Canada", "name": "CANADA"},
        {"cik": "0000837056", "country": "Japan", "name": "JAPAN"},
        {"cik": "0000216105", "country": "New Zealand", "name": "HER MAJESTY THE QUEEN IN RIGHT OF NEW ZEALAND"},
        {"cik": "0000911076", "country": "Portugal", "name": "REPUBLIC OF PORTUGAL"},
    ],
}


# Clause scanning patterns (shared with NSM pipeline)
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
    "registration_no": r"(?:Registration (?:No\.|Number|Statement No\.))\s*([\d-]+)",
}

# Shutdown coordination
_shutdown_requested = False

# ============================================================================
# SETUP: DIRECTORIES, LOGGING
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
HTML_DIR = DATA_DIR / "html" / "edgar"
TEXT_DIR = DATA_DIR / "text" / "edgar"
DB_DIR = DATA_DIR / "db"
TELEMETRY_DIR = DATA_DIR / "telemetry"
LOGS_DIR = PROJECT_ROOT / "logs"

for directory in [HTML_DIR, TEXT_DIR, DB_DIR, TELEMETRY_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / f"edgar_bulk_download_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logger = logging.getLogger("edgar")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(console_handler)


# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def _signal_handler(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning(f"Received signal {signum}. Gracefully shutting down...")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ============================================================================
# CORPUSDB: THIN SQLITE WRAPPER (shared schema with NSM)
# ============================================================================

class CorpusDB:
    """SQLite wrapper for EDGAR corpus, compatible with NSM schema."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn


    def _ensure_tables(self) -> None:
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
            source TEXT DEFAULT 'edgar',
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
            cik TEXT,
            accession_number TEXT,
            form_type TEXT,
            primary_document TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

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
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO documents (
            id, country, issuer, doc_type, headline,
            source, source_url, local_path, text_path,
            filing_date, file_size_bytes, file_hash,
            page_count, word_count, estimated_tokens,
            status, quarantine_reason,
            cik, accession_number, form_type, primary_document
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            status = excluded.status,
            file_size_bytes = excluded.file_size_bytes,
            file_hash = excluded.file_hash,
            word_count = excluded.word_count,
            estimated_tokens = excluded.estimated_tokens,
            text_path = excluded.text_path,
            updated_at = datetime('now')
        """, (
            doc["id"], doc["country"], doc.get("issuer"),
            doc.get("doc_type"), doc.get("headline"),
            doc.get("source", "edgar"), doc.get("source_url"),
            doc.get("local_path"), doc.get("text_path"),
            doc.get("filing_date"), doc.get("file_size_bytes"),
            doc.get("file_hash"), doc.get("page_count"),
            doc.get("word_count"), doc.get("estimated_tokens"),
            doc.get("status", "PENDING"), doc.get("quarantine_reason"),
            doc.get("cik"), doc.get("accession_number"),
            doc.get("form_type"), doc.get("primary_document"),
        ))

        conn.commit()
        conn.close()

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def save_telemetry(self, entry: dict[str, Any]) -> None:
        telemetry_file = TELEMETRY_DIR / f"edgar_run_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(telemetry_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def summary(self) -> dict[str, Any]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as cnt FROM documents GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT SUM(file_size_bytes) FROM documents WHERE file_size_bytes IS NOT NULL")
        total_bytes = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM documents WHERE word_count IS NOT NULL")
        parsed_count = cursor.fetchone()[0]
        conn.close()
        return {"by_status": status_counts, "total_bytes_mb": round(total_bytes / 1024 / 1024, 1), "parsed_documents": parsed_count}



# ============================================================================
# HTTP SESSION
# ============================================================================

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html, application/json",
    })
    return session


# ============================================================================
# TEXT EXTRACTION & PROCESSING
# ============================================================================

def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from EDGAR HTML filing."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()

    return soup.get_text(separator=" ", strip=True)


def compute_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def scan_for_clauses(text: str) -> dict[str, int]:
    compiled = {ct: re.compile(pattern) for ct, pattern in CLAUSE_PATTERNS.items()}
    return {
        clause_type: count
        for clause_type, pattern in compiled.items()
        if (count := len(pattern.findall(text))) > 0
    }


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def country_slug(country: str) -> str:
    return country.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(",", "")


# ============================================================================
# EDGAR API: FETCH SUBMISSIONS & BUILD FILING LIST
# ============================================================================

def fetch_submissions(
    session: requests.Session,
    cik: str,
    delay: float = DEFAULT_DELAY,
) -> dict[str, Any] | None:
    """Fetch submissions.json for a CIK."""
    url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
    try:
        time.sleep(delay)
        response = session.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch submissions for CIK {cik}: {e}")
        return None


def build_filing_list(
    submissions: dict[str, Any],
    country: str,
    cik: str,
    forms: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Extract prospectus filings from submissions JSON."""
    if forms is None:
        forms = PROSPECTUS_FORMS

    recent = submissions.get("filings", {}).get("recent", {})
    form_list = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    issuer_name = submissions.get("name", "")

    filings = []
    for i, form in enumerate(form_list):
        if form not in forms:
            continue

        acc_raw = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        desc = descriptions[i] if i < len(descriptions) else ""
        date = dates[i] if i < len(dates) else ""

        if not acc_raw or not doc:
            continue

        # Build unique ID from accession number
        doc_id = f"edgar-{acc_raw}"

        # Build download URL
        cik_int = str(int(cik))  # strip leading zeros
        acc_nodash = acc_raw.replace("-", "")
        source_url = EDGAR_ARCHIVES_URL.format(
            cik_int=cik_int, acc_nodash=acc_nodash, filename=doc,
        )

        filings.append({
            "id": doc_id,
            "country": country,
            "issuer": issuer_name,
            "cik": cik,
            "accession_number": acc_raw,
            "form_type": form,
            "primary_document": doc,
            "filing_date": date,
            "headline": desc or f"{form} - {issuer_name}",
            "doc_type": form,
            "source": "edgar",
            "source_url": source_url,
        })

    return filings



# ============================================================================
# DOWNLOAD & PROCESS SINGLE FILING
# ============================================================================

def process_filing(
    filing: dict[str, Any],
    session: requests.Session,
    db: CorpusDB,
    delay: float = DEFAULT_DELAY,
) -> dict[str, Any]:
    """Download, extract text, and scan clauses for a single EDGAR filing."""
    telemetry: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "country": filing["country"],
        "doc_id": filing["id"],
        "form_type": filing["form_type"],
        "status": "failed",
        "errors": [],
    }

    try:
        # Check if already processed
        existing = db.get_document(filing["id"])
        if existing and existing["status"] in ["DOWNLOADED", "PARSED", "EXTRACTED"]:
            telemetry["status"] = "skipped"
            telemetry["reason"] = "already_downloaded"
            return telemetry

        # Download the filing
        time.sleep(delay)
        download_start = time.time()

        response = session.get(filing["source_url"], timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()

        raw_content = response.content
        file_size = len(raw_content)
        download_duration = time.time() - download_start

        telemetry["download_duration_seconds"] = download_duration
        telemetry["content_length_bytes"] = file_size

        # Determine file extension
        doc_name = filing["primary_document"]
        ext = doc_name.rsplit(".", 1)[-1].lower() if "." in doc_name else "htm"

        # Save raw file
        slug = country_slug(filing["country"])
        date_str = filing["filing_date"] or "unknown"
        safe_id = filing["accession_number"].replace("-", "")
        filename = f"{slug}_{date_str}_{safe_id}.{ext}"
        save_dir = HTML_DIR / slug
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename

        with open(save_path, "wb") as f:
            f.write(raw_content)

        # Extract text
        process_start = time.time()
        content_text = response.text

        if ext in ("htm", "html"):
            plain_text = extract_text_from_html(content_text)
        else:
            # For rare non-HTML filings, use raw text
            plain_text = content_text

        word_count = len(plain_text.split())
        tokens = estimate_tokens(plain_text)
        file_hash = compute_md5(raw_content)

        # Save extracted text
        text_dir = TEXT_DIR / slug
        text_dir.mkdir(parents=True, exist_ok=True)
        text_path = text_dir / f"{safe_id}.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(plain_text)

        # Scan for clauses
        clause_matches = scan_for_clauses(plain_text)

        process_duration = time.time() - process_start
        telemetry["process_duration_seconds"] = process_duration
        telemetry["word_count"] = word_count
        telemetry["estimated_tokens"] = tokens
        telemetry["clause_matches"] = clause_matches

        # Save to database
        db.save_document({
            **filing,
            "local_path": str(save_path.relative_to(PROJECT_ROOT)),
            "text_path": str(text_path.relative_to(PROJECT_ROOT)),
            "file_size_bytes": file_size,
            "file_hash": file_hash,
            "word_count": word_count,
            "estimated_tokens": tokens,
            "status": "PARSED",
        })

        # Save grep matches
        conn = db._get_conn()
        cursor = conn.cursor()
        for clause_type, count in clause_matches.items():
            cursor.execute(
                "INSERT INTO grep_matches (document_id, clause_type, match_count) VALUES (?, ?, ?)",
                (filing["id"], clause_type, count),
            )
        conn.commit()
        conn.close()

        telemetry["status"] = "parsed"
        logger.info(
            f"Parsed: {filing['id'][:30]:30s} | {filing['country']:12s} | "
            f"{filing['form_type']:6s} | {word_count:6d} words | "
            f"{len(clause_matches)} clause types"
        )

        return telemetry

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 0
        telemetry["errors"].append(f"HTTP {status_code}")
        logger.warning(f"HTTP error for {filing['id']}: {e}")

        # Rate limit detection
        if status_code == 429:
            logger.error("RATE LIMITED by SEC. Sleeping 660 seconds.")
            time.sleep(660)

        # Save as failed
        db.save_document({**filing, "status": "FAILED", "quarantine_reason": str(e)})
        return telemetry

    except Exception as e:
        telemetry["errors"].append(str(e))
        logger.error(f"Error processing {filing['id']}: {e}")
        db.save_document({**filing, "status": "FAILED", "quarantine_reason": str(e)})
        return telemetry



# ============================================================================
# MAIN PIPELINE: DISCOVER → DOWNLOAD → PROCESS
# ============================================================================

def download_country(
    cik_entry: dict[str, str],
    session: requests.Session,
    db: CorpusDB,
    delay: float = DEFAULT_DELAY,
    limit: int | None = None,
) -> dict[str, Any]:
    """Download all prospectus filings for a single sovereign CIK."""
    global _shutdown_requested

    country = cik_entry["country"]
    cik = cik_entry["cik"]

    logger.info(f"Fetching submissions for {country} (CIK {cik})...")

    stats: dict[str, Any] = {
        "country": country,
        "cik": cik,
        "filings_found": 0,
        "attempted": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "bytes": 0,
    }

    # Fetch submissions metadata
    submissions = fetch_submissions(session, cik, delay=delay)
    if not submissions:
        logger.error(f"{country}: Failed to fetch submissions")
        return stats

    # Build filing list
    filings = build_filing_list(submissions, country, cik)
    stats["filings_found"] = len(filings)
    logger.info(f"{country}: {len(filings)} prospectus-type filings found")

    if not filings:
        return stats

    # Also check for paginated older filings
    older_files = submissions.get("filings", {}).get("files", [])
    if older_files:
        logger.info(f"{country}: {len(older_files)} additional submission file(s) with older filings")
        for older_file in older_files:
            if _shutdown_requested:
                break
            older_url = f"https://data.sec.gov/submissions/{older_file['name']}"
            try:
                time.sleep(delay)
                older_resp = session.get(older_url, timeout=DEFAULT_TIMEOUT)
                older_resp.raise_for_status()
                older_data = older_resp.json()
                # older_data has same structure as filings.recent
                older_filings = build_filing_list(
                    {"filings": {"recent": older_data}, "name": submissions.get("name", "")},
                    country, cik,
                )
                filings.extend(older_filings)
                logger.info(f"{country}: +{len(older_filings)} older filings (total: {len(filings)})")
            except Exception as e:
                logger.warning(f"{country}: Failed to fetch older filings from {older_file['name']}: {e}")

    stats["filings_found"] = len(filings)

    # Process each filing
    for filing in filings:
        if _shutdown_requested:
            logger.info(f"{country}: Shutdown requested")
            break

        if limit and stats["success"] >= limit:
            logger.info(f"{country}: Reached limit of {limit}")
            break

        stats["attempted"] += 1
        telemetry = process_filing(filing, session, db, delay=delay)

        if telemetry["status"] == "parsed":
            stats["success"] += 1
            stats["bytes"] += telemetry.get("content_length_bytes", 0)
        elif telemetry["status"] == "skipped":
            stats["skipped"] += 1
        else:
            stats["failed"] += 1

        db.save_telemetry(telemetry)

    logger.info(
        f"{country}: {stats['success']} parsed, {stats['failed']} failed, "
        f"{stats['skipped']} skipped (of {stats['filings_found']} found)"
    )

    return stats



# ============================================================================
# SUMMARY & REPORTING
# ============================================================================

def print_summary(
    run_stats: dict[str, dict[str, Any]],
    start_time: datetime,
) -> None:
    end_time = datetime.now()
    duration = end_time - start_time
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    total_found = sum(s["filings_found"] for s in run_stats.values())
    total_attempted = sum(s["attempted"] for s in run_stats.values())
    total_success = sum(s["success"] for s in run_stats.values())
    total_failed = sum(s["failed"] for s in run_stats.values())
    total_skipped = sum(s["skipped"] for s in run_stats.values())
    total_bytes_mb = sum(s["bytes"] for s in run_stats.values()) / 1024 / 1024

    print("\n" + "=" * 70)
    print("EDGAR DOWNLOAD SUMMARY".center(70))
    print("=" * 70)
    print(f"Run:       {start_time.strftime('%Y-%m-%d %H:%M:%S')} -> {end_time.strftime('%H:%M:%S')}")
    print(f"Source:    SEC EDGAR (SIC 8888 sovereign filers)")
    print(f"Duration:  {hours}h {minutes}m {seconds}s")
    print()
    print(f"Discovery: {total_found} prospectus-type filings across {len(run_stats)} filers")
    print(f"Downloads: {total_attempted} attempted, {total_success} parsed, {total_failed} failed, {total_skipped} skipped")
    print()
    print(f"Data:      {total_bytes_mb:.1f}MB total")
    if total_success > 0:
        avg_kb = total_bytes_mb * 1024 / total_success
        print(f"           {avg_kb:.0f}KB avg per document")
    print()

    # Per-country breakdown
    print("By country:")
    for country, stats in sorted(run_stats.items(), key=lambda x: -x[1]["success"]):
        if stats["filings_found"] > 0:
            print(f"  {country:20s}: {stats['success']:4d}/{stats['filings_found']:4d} parsed")
    print()
    print(f"Log:       {LOG_FILE}")
    print("=" * 70)

    # Save summary
    summary_path = LOGS_DIR / f"edgar_summary_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(summary_path, "w") as f:
        f.write(f"Run: {start_time.isoformat()} -> {end_time.isoformat()}\n")
        f.write(f"Duration: {hours}h {minutes}m {seconds}s\n")
        f.write(f"Discovery: {total_found} filings\n")
        f.write(f"Downloads: {total_success} parsed, {total_failed} failed\n")
        f.write(f"Data: {total_bytes_mb:.1f}MB\n")
        for country, stats in sorted(run_stats.items(), key=lambda x: -x[1]["success"]):
            if stats["filings_found"] > 0:
                f.write(f"  {country}: {stats['success']}/{stats['filings_found']}\n")

    logger.info(f"Summary saved to {summary_path}")


# ============================================================================
# CLI & MAIN
# ============================================================================

def main() -> int:
    global _shutdown_requested

    parser = argparse.ArgumentParser(
        description="EDGAR Bulk Downloader: Sovereign bond prospectus pipeline"
    )
    parser.add_argument("--tiers", type=str, default="1,2,3,4",
                        help="Comma-separated tier numbers (default: all)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max documents per CIK (for testing)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Seconds between requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--dry-run", action="store_true",
                        help="List filings without downloading")
    parser.add_argument("--db", type=Path, default=None,
                        help="Path to SQLite database")

    args = parser.parse_args()

    # Parse tiers
    try:
        requested_tiers = [int(t.strip()) for t in args.tiers.split(",")]
    except ValueError:
        logger.error("Invalid tier specification")
        return 1

    # Build CIK list
    cik_entries = []
    for tier in sorted(requested_tiers):
        cik_entries.extend(SOVEREIGN_CIKS.get(tier, []))

    logger.info(f"Will process {len(cik_entries)} sovereign filers across {len(requested_tiers)} tier(s)")
    logger.info(f"Request delay: {args.delay}s ({1/args.delay:.1f} req/sec)")

    # Initialize database
    if args.db:
        db_path = args.db
    else:
        db_path = DB_DIR / "edgar_corpus.db"

    db = CorpusDB(db_path)
    logger.info(f"Using database: {db_path}")

    if args.dry_run:
        logger.info("DRY RUN MODE")
        session = create_session()
        total_filings = 0
        for entry in cik_entries:
            subs = fetch_submissions(session, entry["cik"], delay=args.delay)
            if subs:
                filings = build_filing_list(subs, entry["country"], entry["cik"])
                total_filings += len(filings)
                logger.info(f"  {entry['country']:20s}: {len(filings):4d} prospectus filings")
        logger.info(f"  TOTAL: {total_filings} filings would be downloaded")
        session.close()
        return 0

    # Create session and run pipeline
    session = create_session()
    start_time = datetime.now()
    logger.info(f"Starting EDGAR download pipeline at {start_time.isoformat()}")

    run_stats: dict[str, dict[str, Any]] = {}

    for entry in cik_entries:
        if _shutdown_requested:
            logger.info("Shutdown requested, stopping pipeline")
            break

        stats = download_country(entry, session, db, delay=args.delay, limit=args.limit)
        # Use country-CIK key to handle Jamaica's two CIKs
        key = f"{entry['country']}_{entry['cik']}"
        run_stats[key] = stats

    print_summary(run_stats, start_time)
    session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
