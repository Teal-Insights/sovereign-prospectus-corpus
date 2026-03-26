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

_UK_GILT_LEI = "ECTRVYYCEF89VWYS6K36"

_NAME_PATTERNS = [
    "Republic of",
    "Kingdom of",
    "State of",
    "Government of",
    "Sultanate of",
    "Emirate of",
]

_EDGE_CASE_NAMES = ["Georgia", "Min of Finance"]


def _lei_criteria(lei: str) -> list[dict[str, Any]]:
    """Build NSM API criteria for a single LEI lookup."""
    return [
        {"name": "company_lei", "value": ["", lei, "disclose_org", ""]},
        {"name": "latest_flag", "value": "Y"},
    ]


def _name_criteria(name: str) -> list[dict[str, Any]]:
    """Build NSM API criteria for a name-pattern search."""
    return [
        {"name": "company_lei", "value": [name, "", "disclose_org", "related_org"]},
        {"name": "latest_flag", "value": "Y"},
    ]


def build_sovereign_queries(
    *,
    reference_csv: Path | None = None,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Build a list of (label, criteria) tuples for sovereign-scoped NSM queries.

    Three categories:
    A) Name patterns (Republic of, Kingdom of, etc.)
    B) LEI queries parsed from reference CSV
    C) Edge cases (Georgia, Min of Finance)
    """
    import csv as csv_mod

    queries: list[tuple[str, list[dict[str, Any]]]] = []

    # A) Name patterns
    for pattern in _NAME_PATTERNS:
        queries.append((f"name:{pattern}", _name_criteria(pattern)))

    # B) LEI queries from reference CSV
    if reference_csv is not None and reference_csv.exists():
        with reference_csv.open() as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                lei_str = row.get("leis", "").strip()
                if not lei_str:
                    continue
                for lei in lei_str.split(";"):
                    lei = lei.strip()
                    if len(lei) == 20 and lei.isalnum() and lei != _UK_GILT_LEI:
                        queries.append((f"lei:{lei}", _lei_criteria(lei)))

    # C) Edge cases
    for name in _EDGE_CASE_NAMES:
        queries.append((f"name:{name}", _name_criteria(name)))

    return queries


def query_nsm_api(
    client: CorpusHTTPClient,
    *,
    criteria: list[dict[str, Any]] | None = None,
    from_offset: int = 0,
    size: int = 10000,
) -> tuple[list[dict[str, Any]], int]:
    """Query NSM API for filings. Returns (hits, total_count).

    If criteria is None, defaults to latest_flag=Y only (breadth-first).
    """
    if criteria is None:
        criteria = [{"name": "latest_flag", "value": "Y"}]
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
    resp = client.post(NSM_API_URL, json=payload)
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    return hits, total


def discover_nsm(
    *,
    client: CorpusHTTPClient,
    queries: list[tuple[str, list[dict[str, Any]]]],
    output_path: Path,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Run multiple NSM queries and deduplicate results into a JSONL file.

    Returns stats dict with queries_run, total_hits_raw, unique_filings,
    and per_query breakdown.
    """
    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    total_hits_raw = 0

    for label, crit in queries:
        hits, _total = query_nsm_api(client, criteria=crit, size=10000)
        total_hits_raw += len(hits)
        new_count = 0
        for hit in hits:
            src = hit.get("_source", {})
            disc_id = src.get("disclosure_id", hit.get("_id", ""))
            if disc_id and disc_id not in seen_ids:
                seen_ids.add(disc_id)
                all_records.append(src)
                new_count += 1
        per_query.append({"label": label, "hits": len(hits), "new": new_count})
        if delay > 0:
            time.sleep(delay)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    return {
        "queries_run": len(queries),
        "total_hits_raw": total_hits_raw,
        "unique_filings": len(seen_ids),
        "per_query": per_query,
    }


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
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay_download: float = 1.0,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Download PDFs from a discovery JSONL file.

    Reads discovery results, converts to manifest records via parse_hits,
    downloads each document, writes nsm_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "nsm_manifest.jsonl"

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "total_in_discovery": 0,
        "aborted": False,
    }

    with discovery_file.open() as f:
        raw_records = [json.loads(line) for line in f if line.strip()]

    stats["total_in_discovery"] = len(raw_records)

    hits = [{"_id": r.get("disclosure_id", ""), "_source": r} for r in raw_records]
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

    return stats
