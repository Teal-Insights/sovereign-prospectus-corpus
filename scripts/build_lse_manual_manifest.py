"""Build a bounded, verified manifest for manually retrieved LSE documents.

This is a stopgap for TEA-1005, not an LSE source adapter. It accepts an
operator-reviewed inventory and already retrieved PDF files, validates every
artifact before writing, copies them into the canonical data layout, and
atomically upserts ``lse_manifest.jsonl``.

Usage:
    uv run python scripts/build_lse_manual_manifest.py \
        --inventory docs/reports/2026-07-15-lse-congo-inventory.json \
        --input-dir /tmp/lse-congo-20260715/ready \
        --data-root data
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from corpus.io.manifest import portable_data_path, upsert_manifest_records
from corpus.io.safe_write import safe_write
from corpus.parsers.registry import get_parser

_EXPECTED_ISSUER = "THE REPUBLIC OF CONGO"
_NATIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]+$")
_REQUIRED_DOCUMENT_FIELDS = frozenset(
    {
        "native_id",
        "source_file",
        "title",
        "issuer_name",
        "doc_type",
        "publication_date",
        "download_url",
        "expected_sha256",
        "expected_size_bytes",
        "expected_page_count",
        "family_id",
        "document_role",
        "instrument_codes",
        "isins",
        "associated_issuance_dates",
    }
)
_ALLOWED_ARTIFACT_HOSTS = frozenset(
    {
        "assets.lsegissuerservices.com",
        "cache-api.lsegissuerservices.com",
    }
)


def _load_inventory(inventory_path: Path) -> dict[str, Any]:
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read LSE inventory {inventory_path}: {exc}") from exc
    if not isinstance(inventory, dict):
        raise ValueError("LSE inventory must be a JSON object")
    documents = inventory.get("documents")
    events = inventory.get("issuance_events")
    if not isinstance(documents, list) or not documents:
        raise ValueError("LSE inventory must contain a nonempty documents list")
    if not isinstance(events, list) or not events:
        raise ValueError("LSE inventory must contain a nonempty issuance_events list")
    if not inventory.get("retrieved_at") or not inventory.get("issuer_page_url"):
        raise ValueError("LSE inventory is missing retrieved_at or issuer_page_url")
    return inventory


def _validate_iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date string")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date string: {value!r}") from exc


def _validate_inventory_links(inventory: dict[str, Any]) -> int:
    documents = inventory["documents"]
    native_ids = {item.get("native_id") for item in documents if isinstance(item, dict)}
    if len(native_ids) != len(documents) or None in native_ids:
        raise ValueError("LSE document native_id values must be present and unique")

    events_with_files = 0
    seen_dates: set[str] = set()
    for event in inventory["issuance_events"]:
        if not isinstance(event, dict):
            raise ValueError("Each LSE issuance event must be a JSON object")
        event_date = _validate_iso_date(event.get("event_date"), "event_date")
        if event_date in seen_dates:
            raise ValueError(f"Duplicate LSE issuance event date: {event_date}")
        seen_dates.add(event_date)
        artifact_ids = event.get("artifact_native_ids")
        if not isinstance(artifact_ids, list):
            raise ValueError(f"artifact_native_ids must be a list for {event_date}")
        unknown = sorted(set(artifact_ids) - native_ids)
        if unknown:
            raise ValueError(
                f"Issuance event {event_date} references unknown artifact: {', '.join(unknown)}"
            )
        if artifact_ids:
            events_with_files += 1
        elif event.get("status") != "no_public_lse_document":
            raise ValueError(
                f"Issuance event {event_date} has no artifact and lacks "
                "status=no_public_lse_document"
            )
    return events_with_files


def _validate_document(
    item: dict[str, Any],
    *,
    input_dir: Path,
    data_root: Path,
    retrieved_at: str,
    issuer_page_url: str,
) -> tuple[dict[str, Any], bytes, Path]:
    if not isinstance(item, dict):
        raise ValueError("Each LSE document must be a JSON object")
    missing = sorted(_REQUIRED_DOCUMENT_FIELDS - item.keys())
    if missing:
        raise ValueError(f"LSE document is missing fields: {', '.join(missing)}")

    native_id = item["native_id"]
    if not isinstance(native_id, str) or _NATIVE_ID_RE.fullmatch(native_id) is None:
        raise ValueError(f"Unsafe LSE native_id: {native_id!r}")
    source_file = item["source_file"]
    if not isinstance(source_file, str) or Path(source_file).name != source_file:
        raise ValueError(f"Unsafe LSE source_file: {source_file!r}")
    if item["issuer_name"] != _EXPECTED_ISSUER:
        raise ValueError(
            f"Expected Republic of Congo issuer {_EXPECTED_ISSUER!r}, "
            f"found {item['issuer_name']!r}"
        )
    for field in ("title", "doc_type", "family_id", "document_role"):
        if not isinstance(item[field], str) or not item[field].strip():
            raise ValueError(f"LSE document {native_id} has invalid {field}")
    for field in ("instrument_codes", "isins", "associated_issuance_dates"):
        values = item[field]
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) and value for value in values)
        ):
            raise ValueError(f"LSE document {native_id} has invalid {field}")

    publication_date = _validate_iso_date(item["publication_date"], "publication_date")
    for associated in item["associated_issuance_dates"]:
        _validate_iso_date(associated, "associated_issuance_dates")

    download_url = item["download_url"]
    parsed_url = urlparse(download_url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in _ALLOWED_ARTIFACT_HOSTS:
        raise ValueError(
            f"LSE download_url is not an approved official artifact URL: {download_url}"
        )

    source_path = input_dir / source_file
    try:
        content = source_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Cannot read LSE source file {source_path}: {exc}") from exc
    if content[:4] != b"%PDF":
        raise ValueError(f"LSE artifact does not begin with %PDF: {source_path}")
    digest = hashlib.sha256(content).hexdigest()
    if digest != item["expected_sha256"]:
        raise ValueError(
            f"LSE artifact SHA-256 mismatch for {native_id}: "
            f"expected {item['expected_sha256']}, found {digest}"
        )
    if len(content) != item["expected_size_bytes"]:
        raise ValueError(
            f"LSE artifact size mismatch for {native_id}: "
            f"expected {item['expected_size_bytes']}, found {len(content)}"
        )

    parse_result = get_parser("pymupdf").parse(source_path)
    if parse_result.page_count <= 0 or not parse_result.text.strip():
        raise ValueError(f"LSE artifact has no parseable text or pages: {native_id}")
    if parse_result.page_count != item["expected_page_count"]:
        raise ValueError(
            f"LSE artifact page-count mismatch for {native_id}: "
            f"expected {item['expected_page_count']}, found {parse_result.page_count}"
        )

    storage_key = f"lse__{native_id}"
    destination = data_root / "original" / f"{storage_key}.pdf"
    record = {
        "source": "lse",
        "native_id": native_id,
        "storage_key": storage_key,
        "family_id": item["family_id"],
        "title": item["title"],
        "issuer_name": _EXPECTED_ISSUER,
        "doc_type": item["doc_type"],
        "publication_date": publication_date,
        "download_url": download_url,
        "source_page_url": download_url,
        "source_page_kind": "artifact_archive",
        "file_path": portable_data_path(destination, data_root=data_root),
        "file_hash": digest,
        "file_size_bytes": len(content),
        "page_count": parse_result.page_count,
        "is_sovereign": True,
        "issuer_type": "sovereign",
        "scope_status": "in_scope",
        "countries": [
            {
                "country_code": "COG",
                "country_name": "Republic of Congo",
                "role": "issuer",
            }
        ],
        "source_metadata": {
            "lse_document_id": native_id,
            "lse_issuer_code": "TREPCG",
            "lse_issuer_page_url": issuer_page_url,
            "instrument_codes": item["instrument_codes"],
            "isins": item["isins"],
            "document_role": item["document_role"],
            "associated_issuance_dates": item["associated_issuance_dates"],
            "retrieved_at": retrieved_at,
        },
    }
    return record, content, destination


def build_lse_manual_manifest(
    *, inventory_path: Path, input_dir: Path, data_root: Path
) -> dict[str, int]:
    """Validate and atomically reconcile the bounded LSE manual-ingest lane."""
    inventory = _load_inventory(inventory_path)
    events_with_files = _validate_inventory_links(inventory)

    prepared = [
        _validate_document(
            item,
            input_dir=input_dir,
            data_root=data_root,
            retrieved_at=inventory["retrieved_at"],
            issuer_page_url=inventory["issuer_page_url"],
        )
        for item in inventory["documents"]
    ]
    hashes = [record["file_hash"] for record, _, _ in prepared]
    duplicate_hashes = sorted({digest for digest in hashes if hashes.count(digest) > 1})
    if duplicate_hashes:
        raise ValueError(f"Duplicate artifact SHA-256 in LSE inventory: {duplicate_hashes[0]}")

    # Check every destination before the first write so a later conflict cannot
    # leave an earlier document promoted without its complete batch.
    for record, _, destination in prepared:
        if destination.exists():
            existing_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing_hash != record["file_hash"]:
                raise ValueError(
                    f"Existing LSE destination conflicts with inventory for {record['storage_key']}"
                )

    for _, content, destination in prepared:
        if not destination.exists():
            safe_write(destination, content)

    manifest_path = data_root / "manifests" / "lse_manifest.jsonl"
    upsert_manifest_records(manifest_path, [record for record, _, _ in prepared])
    return {
        "documents": len(prepared),
        "issuance_events": len(inventory["issuance_events"]),
        "events_with_files": events_with_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()
    stats = build_lse_manual_manifest(
        inventory_path=args.inventory,
        input_dir=args.input_dir,
        data_root=args.data_root,
    )
    print(
        f"Verified and reconciled {stats['documents']} LSE documents for "
        f"{stats['issuance_events']} issuance events "
        f"({stats['events_with_files']} with public artifacts)."
    )


if __name__ == "__main__":
    main()
