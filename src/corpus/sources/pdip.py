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

import atexit
import tempfile
from pathlib import Path as _Path

import certifi
import requests
from requests.exceptions import (
    RequestException,
)

from corpus.io.safe_write import safe_write

log = logging.getLogger(__name__)

# Georgetown's server sends only the leaf cert, missing the InCommon RSA
# Server CA 2 intermediate.  We ship the intermediate in certs/ and build
# a combined CA bundle (certifi roots + intermediate) so SSL verification
# stays enabled.
#
# Cert provenance:
#   Subject:     InCommon RSA Server CA 2
#   Issuer:      USERTrust RSA Certification Authority
#   Valid:       2022-11-16 to 2032-11-15
#   SHA-256:     87:E0:1C:C4:DD:0C:9D:92:A3:DB:D4:90:92:FF:13:F9:
#                CD:38:74:45:CD:C5:7E:5B:98:4E:1B:77:21:B5:B0:29
#   Source URL:  http://crt.sectigo.com/InCommonRSAServerCA2.crt
#   Downloaded:  2026-03-26 via AIA extension in Georgetown's leaf cert
_INTERMEDIATE_CERT = (
    _Path(__file__).resolve().parent.parent.parent.parent
    / "certs"
    / "incommon_rsa_server_ca_2.pem"
)

# Module-level cache so we build the bundle at most once per process.
_ca_bundle_path: str | None = None


def _build_ca_bundle() -> str:
    """Return path to a CA bundle that includes the InCommon intermediate.

    Builds the bundle once, caches the path, and registers cleanup on exit.
    Falls back to certifi-only if the intermediate cert is missing or expired.
    """
    global _ca_bundle_path
    if _ca_bundle_path is not None:
        return _ca_bundle_path

    if not _INTERMEDIATE_CERT.exists():
        log.warning(
            "InCommon intermediate cert not found at %s — using certifi only",
            _INTERMEDIATE_CERT,
        )
        _ca_bundle_path = certifi.where()
        return _ca_bundle_path

    # Check if the cert has expired
    try:
        import ssl

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(_INTERMEDIATE_CERT)
    except ssl.SSLError:
        log.warning(
            "InCommon intermediate cert at %s failed to load — using certifi only",
            _INTERMEDIATE_CERT,
        )
        _ca_bundle_path = certifi.where()
        return _ca_bundle_path

    bundle = tempfile.NamedTemporaryFile(  # noqa: SIM115
        prefix="pdip_ca_bundle_", suffix=".pem", delete=False
    )
    bundle.write(_Path(certifi.where()).read_bytes())
    bundle.write(b"\n")
    bundle.write(_INTERMEDIATE_CERT.read_bytes())
    bundle.close()

    _ca_bundle_path = bundle.name
    atexit.register(lambda: _Path(bundle.name).unlink(missing_ok=True))
    return _ca_bundle_path


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


def _make_session(*, max_retries: int = 3) -> requests.Session:
    """Create a requests session with PDIP headers, SSL bundle, and retry."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers.update(PDIP_HEADERS)
    session.verify = _build_ca_bundle()

    retry = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def discover_pdip(
    *,
    output_path: Path,
    page_size: int = 100,
    delay: float = 1.0,
    max_retries: int = 3,
    timeout: int = 60,
) -> dict[str, Any]:
    """Query PDIP search API for all documents.

    Paginates through results, writes discovery JSONL. Returns stats dict.
    """
    session = _make_session(max_retries=max_retries)

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
            resp = session.post(PDIP_SEARCH_URL, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except (RequestException, json.JSONDecodeError) as exc:
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
    timeout: int = 60,
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
    resp = session.get(url, timeout=timeout)

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
    max_retries: int = 3,
    timeout: int = 60,
) -> dict[str, Any]:
    """Download PDIP documents from a discovery JSONL file.

    Reads discovery results, downloads each PDF, writes pdip_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "pdip_manifest.jsonl"

    session = _make_session(max_retries=max_retries)

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
                record, session=session, output_dir=output_dir, timeout=timeout
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
