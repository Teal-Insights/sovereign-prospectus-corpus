"""PDIP source adapter — download documents from Georgetown PDIP.

Queries the PDIP search API for sovereign debt documents, downloads PDFs,
and writes pdip_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.logging import CorpusLogger

import requests
import urllib3

from corpus.io.safe_write import safe_write

# Georgetown's SSL cert chain is incomplete on some systems (macOS/Anaconda).
# Suppress the per-request InsecureRequestWarning since we set verify=False.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

PDIP_BASE_URL = "https://publicdebtispublic.mdi.georgetown.edu"
PDIP_SEARCH_URL = f"{PDIP_BASE_URL}/api/search/"
PDIP_PDF_URL = f"{PDIP_BASE_URL}/api/pdf/{{doc_id}}"

PDIP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": PDIP_BASE_URL,
    "Referer": f"{PDIP_BASE_URL}/search/",
}

# Metadata field mappings: API key -> discovery record key
_META_FIELDS = {
    "DebtorCountry": "country",
    "InstrumentType": "instrument_type",
    "CreditorCountry": "creditor_country",
    "CreditorType": "creditor_type",
    "InstrumentMaturityDate": "maturity_date",
    "InstrumentMaturityYear": "maturity_year",
}

# These metadata keys are promoted to top-level fields; remaining ones go in "metadata"
_PROMOTED_KEYS = set(_META_FIELDS.keys())


def _first_or_none(val: list[str] | None) -> str | None:
    """Extract first element from a list field, or None."""
    if isinstance(val, list) and val:
        return val[0]
    return None


def parse_search_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PDIP search API response into discovery records."""
    records: list[dict[str, Any]] = []

    for result in response.get("results", []):
        meta = result.get("metadata", {})

        record: dict[str, Any] = {
            "native_id": result["id"],
            "source": "pdip",
            "title": result.get("document_title", ""),
            "tag_status": result.get("tag_status", ""),
        }

        # Promote well-known metadata fields to top level
        for api_key, record_key in _META_FIELDS.items():
            record[record_key] = _first_or_none(meta.get(api_key))

        # Store remaining metadata
        extra_meta = {k: v for k, v in meta.items() if k not in _PROMOTED_KEYS}
        record["metadata"] = extra_meta

        records.append(record)

    return records


def discover_pdip(
    *,
    output_path: Path,
    page_size: int = 100,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Query PDIP search API for all documents.

    Paginates through results, writes discovery JSONL. Returns stats dict.
    """
    session = requests.Session()
    session.headers.update(PDIP_HEADERS)
    session.verify = False  # Georgetown cert chain incomplete on some systems

    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    page = 1
    pages_fetched = 0
    error: str | None = None

    while True:
        payload = {
            "page": page,
            "sortBy": "date",
            "sortOrder": "asc",
            "pageSize": page_size,
        }

        try:
            resp = session.post(PDIP_SEARCH_URL, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.error("PDIP search API failed on page %d: %s", page, exc)
            error = str(exc)
            break

        pages_fetched += 1
        results = data.get("results", [])
        records = parse_search_results(data)

        for record in records:
            if record["native_id"] not in seen_ids:
                seen_ids.add(record["native_id"])
                all_records.append(record)

        # Stop if no results, fewer than requested, or all documents seen
        # (API may ignore pageSize and return everything in one response)
        total = data.get("total", 0)
        if not results or len(results) < page_size or len(all_records) >= total:
            break

        page += 1
        if delay > 0:
            time.sleep(delay)

    # Only write discovery file if we got results — avoid clobbering a
    # previous successful discovery with an empty file on API failure.
    if all_records:
        content = "".join(json.dumps(r) + "\n" for r in all_records).encode()
        safe_write(output_path, content, overwrite=True)

    return {
        "total_documents": len(all_records),
        "pages_fetched": pages_fetched,
        "error": error,
    }


def download_pdip_document(
    record: dict[str, Any],
    *,
    session: Any,
    output_dir: Path,
) -> tuple[dict[str, Any] | None, str]:
    """Download a single PDIP document.

    Returns (enriched_record, status) where status is one of:
    "success", "skipped_exists", "not_found", "invalid_pdf".
    """
    native_id = record["native_id"]
    target = output_dir / f"pdip__{native_id}.pdf"

    if target.exists():
        return None, "skipped_exists"

    url = PDIP_PDF_URL.format(doc_id=native_id)
    resp = session.get(url, timeout=60)

    if resp.status_code == 404:
        return None, "not_found"

    resp.raise_for_status()
    content = resp.content

    if not content[:5].startswith(b"%PDF"):
        return None, "invalid_pdf"

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched: dict[str, Any] = {
        "source": "pdip",
        "native_id": native_id,
        "storage_key": f"pdip__{native_id}",
        "title": record.get("title", ""),
        "issuer_name": record.get("country", ""),
        "doc_type": record.get("instrument_type", ""),
        "publication_date": None,
        "download_url": url,
        "file_ext": "pdf",
        "file_path": str(target),
        "file_hash": file_hash,
        "file_size_bytes": len(content),
        "source_metadata": {
            "tag_status": record.get("tag_status", ""),
            "country": record.get("country", ""),
            "instrument_type": record.get("instrument_type", ""),
            "creditor_country": record.get("creditor_country"),
            "creditor_type": record.get("creditor_type"),
            "maturity_date": record.get("maturity_date"),
            "maturity_year": record.get("maturity_year"),
        },
    }

    return enriched, "success"


def run_pdip_download(
    *,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay: float = 1.0,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Download PDIP documents from a discovery JSONL file.

    Reads discovery results, downloads each PDF, writes pdip_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "pdip_manifest.jsonl"

    session = requests.Session()
    session.headers.update(PDIP_HEADERS)
    session.verify = False  # Georgetown cert chain incomplete on some systems

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "not_found": 0,
        "failed": 0,
        "total_in_discovery": 0,
        "aborted": False,
    }

    with discovery_file.open() as f:
        records = [json.loads(line) for line in f if line.strip()]

    stats["total_in_discovery"] = len(records)

    for record in records:
        if stats["aborted"]:
            break

        doc_id = record.get("native_id", "unknown")
        _start = time.monotonic()

        try:
            result, dl_status = download_pdip_document(
                record, session=session, output_dir=output_dir
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - _start) * 1000)
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="error",
                error_message=str(exc),
            )
            stats["failed"] += 1
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break
            if delay > 0:
                time.sleep(delay)
            continue

        elapsed_ms = int((time.monotonic() - _start) * 1000)

        if dl_status == "success" and result is not None:
            with manifest_path.open("a") as mf:
                mf.write(json.dumps(result) + "\n")
            stats["downloaded"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="success",
            )
        elif dl_status == "skipped_exists":
            stats["skipped"] += 1
        elif dl_status == "not_found":
            stats["not_found"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="not_found",
            )
        elif dl_status == "invalid_pdf":
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="invalid_pdf",
            )
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break

        if delay > 0:
            time.sleep(delay)

    return stats
