"""NSM source adapter — download documents from FCA National Storage Mechanism.

Queries the NSM Elasticsearch API with no country/type filters (breadth-first),
downloads PDFs, and writes nsm_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from corpus.io.safe_write import safe_write

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger

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
                "related_org": src.get("related_org", []),
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
) -> tuple[dict[str, Any] | None, str]:
    """Download a single NSM document.

    Returns (enriched_record, status) where status is one of:
    "downloaded", "skipped_exists", "skipped_no_url", "failed_no_pdf_link",
    "failed_invalid_pdf".
    """
    storage_key = record.get("storage_key", "")
    target = output_dir / f"{storage_key}.pdf"

    if target.exists():
        return None, "skipped_exists"

    download_url = record.get("download_url", "")
    if not download_url:
        return None, "skipped_no_url"

    # Resolve two-hop HTML links
    pdf_url = resolve_pdf_url(download_url, client=client)
    if pdf_url is None:
        return None, "failed_no_pdf_link"

    resp = client.get(pdf_url)
    content = resp.content

    if not content.startswith(PDF_HEADER):
        return None, "failed_invalid_pdf"

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched = dict(record)
    enriched["file_path"] = str(target)
    enriched["file_hash"] = file_hash
    enriched["file_size_bytes"] = len(content)
    return enriched, "downloaded"


def run_nsm_download(
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay_api: float = 1.0,
    delay_download: float = 1.0,
    page_size: int = 10000,
    total_failures_abort: int = 10,
    api_responses_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the full NSM download pipeline.

    Paginates through all NSM results, downloads PDFs, writes manifest JSONL.
    Circuit breaker aborts after total_failures_abort failures.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "nsm_manifest.jsonl"

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "api_pages_fetched": 0,
        "total_hits": 0,
        "aborted": False,
    }

    from_offset = 0

    while True:
        if stats["aborted"]:
            break

        with logger.timed("nsm-api", "query", page=from_offset):
            hits, total = query_nsm_api(client, from_offset=from_offset, size=page_size)

        if api_responses_dir is not None:
            api_responses_dir.mkdir(parents=True, exist_ok=True)
            page_data = {
                "total": total,
                "from": from_offset,
                "hit_count": len(hits),
                "hits": hits,
            }
            resp_file = api_responses_dir / f"nsm_page_{from_offset:06d}.json"
            resp_file.write_text(json.dumps(page_data, indent=2))

        stats["api_pages_fetched"] += 1
        if stats["total_hits"] == 0:
            stats["total_hits"] = total

        if not hits:
            break

        records = parse_hits(hits)

        for record in records:
            if stats["aborted"]:
                break

            doc_id = record.get("native_id", "unknown")

            try:
                with logger.timed(doc_id, "download"):
                    result, dl_status = download_nsm_document(
                        record, client=client, output_dir=output_dir
                    )
            except Exception as exc:
                logger.log(
                    document_id=doc_id,
                    step="download",
                    duration_ms=0,
                    status="error",
                    error_message=str(exc),
                )
                result, dl_status = None, "error"

            if dl_status == "downloaded" and result is not None:
                with manifest_path.open("a") as f:
                    f.write(json.dumps(result) + "\n")
                stats["downloaded"] += 1
            elif dl_status.startswith("skipped"):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
                logger.log(
                    document_id=doc_id,
                    step="download",
                    duration_ms=0,
                    status=dl_status,
                    error_message=f"Download failed: {dl_status}",
                )

            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break

            if delay_download > 0:
                time.sleep(delay_download)

        from_offset += page_size
        if from_offset >= total:
            break

        if delay_api > 0:
            time.sleep(delay_api)

    return stats
