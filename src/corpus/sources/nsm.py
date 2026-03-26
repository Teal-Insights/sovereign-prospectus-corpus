"""NSM source adapter — download documents from FCA National Storage Mechanism.

Queries the NSM Elasticsearch API with no country/type filters (breadth-first),
downloads PDFs, and writes nsm_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from corpus.io.safe_write import safe_write

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.io.http import CorpusHTTPClient

NSM_API_URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"
NSM_ARTEFACT_BASE = "https://data.fca.org.uk/artefacts"
PDF_HEADER = b"%PDF"


def query_nsm_api(
    client: CorpusHTTPClient,
    *,
    from_offset: int = 0,
    size: int = 10000,
) -> tuple[list[dict[str, Any]], int]:
    """Query NSM API for all latest filings. Returns (hits, total_count)."""
    payload = {
        "from": from_offset,
        "size": size,
        "sort": "submitted_date",
        "sortorder": "desc",
        "criteriaObj": {
            "criteria": [
                {"name": "latest_flag", "value": "Y"},
            ],
            "dateCriteria": [],
        },
    }
    resp = client.post(NSM_API_URL, json=payload)
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    return hits, total


def parse_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw NSM API hits into manifest records."""
    records = []
    for hit in hits:
        src = hit.get("_source", {})
        disclosure_id = src.get("disclosure_id", hit.get("_id", ""))
        download_link = src.get("download_link", "")
        download_url = f"{NSM_ARTEFACT_BASE}/{download_link}" if download_link else ""

        record: dict[str, Any] = {
            "source": "nsm",
            "native_id": disclosure_id,
            "storage_key": f"nsm__{disclosure_id}",
            "title": src.get("headline", ""),
            "issuer_name": src.get("company", ""),
            "lei": src.get("lei", ""),
            "doc_type": src.get("type_code", ""),
            "publication_date": src.get("publication_date"),
            "submitted_date": src.get("submitted_date"),
            "download_url": download_url,
            "source_metadata": {
                "nsm_source": src.get("source", ""),
                "type_name": src.get("type", ""),
                "classifications": src.get("classifications", ""),
                "classifications_code": src.get("classifications_code", ""),
                "seq_id": src.get("seq_id", ""),
                "hist_seq": src.get("hist_seq", ""),
                "tag_esef": src.get("tag_esef", ""),
                "lei_remediation_flag": src.get("lei_remediation_flag", ""),
            },
        }
        records.append(record)
    return records


def resolve_pdf_url(url: str, *, client: CorpusHTTPClient) -> str | None:
    """Resolve a download URL to a direct PDF link.

    Direct .pdf URLs are returned unchanged. HTML metadata pages are
    fetched and parsed to extract the PDF link (two-hop pattern).
    Returns None if no PDF link can be found.
    """
    if url.lower().endswith(".pdf"):
        return url

    resp = client.get(url)
    html = resp.text

    # Look for <a> tags with href ending in .pdf
    pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.IGNORECASE)
    match = pdf_pattern.search(html)
    if match:
        return urljoin(url, match.group(1))

    return None


def download_nsm_document(
    record: dict[str, Any],
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
) -> dict[str, Any] | None:
    """Download a single NSM document. Returns enriched record or None on skip/fail.

    Skips if the file already exists on disk. Resolves HTML->PDF two-hop links.
    Validates that downloaded content starts with %PDF header.
    """
    storage_key = record.get("storage_key", "")
    target = output_dir / f"{storage_key}.pdf"

    if target.exists():
        return None

    download_url = record.get("download_url", "")
    if not download_url:
        return None

    # Resolve two-hop HTML links
    pdf_url = resolve_pdf_url(download_url, client=client)
    if pdf_url is None:
        return None

    resp = client.get(pdf_url)
    content = resp.content

    if not content.startswith(PDF_HEADER):
        return None

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched = dict(record)
    enriched["file_path"] = str(target)
    enriched["file_hash"] = file_hash
    return enriched
