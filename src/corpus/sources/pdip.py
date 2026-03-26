"""PDIP source adapter — download documents from Georgetown PDIP.

Queries the PDIP search API for sovereign debt documents, downloads PDFs,
and writes pdip_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import requests

from corpus.io.safe_write import safe_write

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

        if len(results) < page_size:
            break

        page += 1
        if delay > 0:
            time.sleep(delay)

    content = "".join(json.dumps(r) + "\n" for r in all_records).encode()
    safe_write(output_path, content, overwrite=True)

    return {
        "total_documents": len(all_records),
        "pages_fetched": pages_fetched,
        "error": error,
    }
