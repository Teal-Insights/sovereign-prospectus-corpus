"""Regenerate data/manifests/pdip_manifest.jsonl from the current DB + inventory CSV.

This is a one-off bridge for the tech debt tracked in #66 — PDIP data was
ingested via a path that predates the manifest-canonical pipeline, so no
JSONL manifest exists. Without one, a full DB rebuild from manifests would
lose all 823 PDIP documents.

Approach:
    1. Read the authoritative "what's actually downloaded" list from the
       current DB (data/db/corpus.duckdb, pdip rows).
    2. LEFT JOIN data/pdip/pdip_document_inventory.csv on native_id = id for
       richer metadata (title, country, instrument_type, dates).
    3. Normalize free-text inventory dates (e.g. "January 20, 2017",
       "24 September 2025", "July 6th, 2018") to ISO YYYY-MM-DD so they
       survive DuckDB's DATE column; preserve the raw string in
       source_metadata.document_date_raw for audit.
    4. Derive download_url deterministically from native_id.
    5. Write data/manifests/pdip_manifest.jsonl atomically (.part → rename).

Idempotent: running twice produces the same manifest. Safe to re-run.

Usage:
    uv run python scripts/regenerate_pdip_manifest.py
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import duckdb

log = logging.getLogger(__name__)

PDIP_PDF_URL = "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/{native_id}"

# Date formats observed in data/pdip/pdip_document_inventory.csv as of 2026-04-10:
#   "January 20, 2017"   → %B %d, %Y
#   "24 September 2025"  → %d %B %Y
#   "December 17, 2018"  → %B %d, %Y
# Ordinal suffixes ("6th", "1st") are stripped before parsing.
_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y")
_ORDINAL_RE = re.compile(r"(\d+)(st|nd|rd|th)\b", re.IGNORECASE)


def _parse_free_text_date(raw: str | None) -> str | None:
    """Parse a free-text date from the inventory CSV to ISO YYYY-MM-DD.

    Returns ``None`` if the input is empty or cannot be parsed by any of
    the known formats. Never raises — unparseable dates become ``None``
    rather than crashing the rebuild, but the raw value is logged as a
    warning so a new inventory format isn't lost silently.
    """
    if not raw:
        return None
    cleaned = _ORDINAL_RE.sub(r"\1", raw.strip())
    if not cleaned:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    log.warning("Unparseable PDIP document_date: %r", raw)
    return None


def _load_inventory(inventory_csv: Path) -> dict[str, dict[str, str]]:
    """Read the inventory CSV keyed by id (= native_id).

    Uses ``utf-8-sig`` so Excel-exported CSVs with a UTF-8 BOM don't bleed
    the BOM into the first column name (which would make ``row.get("id")``
    always return ``None``).
    """
    if not inventory_csv.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with inventory_csv.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row.get("id")
            if doc_id:
                rows[doc_id] = row
    return rows


def _build_record(db_row: dict[str, Any], inv_row: dict[str, str] | None) -> dict[str, Any]:
    """Build a single manifest record from DB + optional inventory enrichment."""
    native_id = db_row["native_id"]
    inv = inv_row or {}
    raw_date = inv.get("document_date", "") or ""
    iso_date = _parse_free_text_date(raw_date)
    return {
        "source": "pdip",
        "native_id": native_id,
        "storage_key": db_row["storage_key"],
        "title": (inv.get("document_title") or "").strip() or None,
        "issuer_name": (inv.get("country") or "").strip() or None,
        "doc_type": (inv.get("instrument_type") or "").strip() or None,
        "publication_date": iso_date,
        "download_url": PDIP_PDF_URL.format(native_id=native_id),
        "file_path": db_row.get("file_path"),
        "file_hash": db_row.get("file_hash"),
        "is_sovereign": db_row.get("is_sovereign", True),
        "issuer_type": db_row.get("issuer_type", "sovereign"),
        "scope_status": db_row.get("scope_status", "in_scope"),
        "source_metadata": {
            "tag_status": inv.get("tag_status", ""),
            "country": inv.get("country", ""),
            "instrument_type": inv.get("instrument_type", ""),
            "creditor_country": inv.get("creditor_country", ""),
            "creditor_type": inv.get("creditor_type", ""),
            "entity_type": inv.get("entity_type", ""),
            "maturity_date": inv.get("maturity_date", ""),
            "document_date_raw": raw_date,  # Audit trail for the parser
        },
    }


def regenerate_pdip_manifest(
    *,
    db_path: Path,
    inventory_csv: Path,
    manifest_dir: Path,
) -> int:
    """Regenerate pdip_manifest.jsonl. Returns number of records written."""
    manifest_dir.mkdir(parents=True, exist_ok=True)
    target = manifest_dir / "pdip_manifest.jsonl"
    part = manifest_dir / "pdip_manifest.jsonl.part"

    inventory = _load_inventory(inventory_csv)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        result = conn.execute(
            "SELECT native_id, storage_key, file_path, file_hash, "
            "is_sovereign, issuer_type, scope_status "
            "FROM documents WHERE source = 'pdip' ORDER BY native_id"
        )
        rows = result.fetchall()
        columns = [d[0] for d in result.description or []]
    finally:
        conn.close()

    with part.open("w") as f:
        for row in rows:
            db_row = dict(zip(columns, row, strict=True))
            inv_row = inventory.get(db_row["native_id"])
            record = _build_record(db_row, inv_row)
            f.write(json.dumps(record) + "\n")

    os.replace(part, target)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/db/corpus.duckdb"),
        help="Path to corpus.duckdb",
    )
    parser.add_argument(
        "--inventory-csv",
        type=Path,
        default=Path("data/pdip/pdip_document_inventory.csv"),
        help="Path to PDIP inventory CSV",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifests"),
        help="Directory for manifest JSONL files",
    )
    args = parser.parse_args()
    count = regenerate_pdip_manifest(
        db_path=args.db_path,
        inventory_csv=args.inventory_csv,
        manifest_dir=args.manifest_dir,
    )
    print(f"Wrote {count} PDIP records to {args.manifest_dir / 'pdip_manifest.jsonl'}")


if __name__ == "__main__":
    main()
