"""Regression tests for the PDIP manifest regeneration bridge script.

Critical: these tests must round-trip the regenerated manifest through
``ingest_manifests`` into DuckDB. Writing a well-formed JSON record is not
enough — free-text dates like "January 20, 2017" in the inventory CSV will
pass JSON serialization but crash the rebuild with a ConversionException on
the DATE column.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from typing import TYPE_CHECKING

import duckdb
import pytest

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def fake_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a miniature corpus layout:
       - tmp DB with three PDIP rows (impoverished, matches current state)
       - tmp inventory CSV with enrichment for all three, using the three
         free-text date formats observed in production
       - tmp manifest dir
    Returns (db_path, inventory_csv_path, manifest_dir)."""
    db_path = tmp_path / "corpus.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    conn.execute(
        "INSERT INTO documents (source, native_id, storage_key, file_path) VALUES "
        "('pdip', 'VEN85', 'pdip__VEN85', 'data/pdfs/pdip/venezuela/VEN85.pdf'), "
        "('pdip', 'GHA33', 'pdip__GHA33', 'data/pdfs/pdip/ghana/GHA33.pdf'), "
        "('pdip', 'IDN199', 'pdip__IDN199', 'data/pdfs/pdip/indonesia/IDN199.pdf')"
    )
    conn.close()

    inventory = tmp_path / "pdip_document_inventory.csv"
    # utf-8-sig writer so the test file has a BOM, matching the script's
    # utf-8-sig reader choice (defends against Excel-exported CSVs).
    with inventory.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "document_title",
                "tag_status",
                "country",
                "instrument_type",
                "creditor_country",
                "creditor_type",
                "entity_type",
                "document_date",
                "maturity_date",
            ]
        )
        # Format 1: "Month Day, Year"
        writer.writerow(
            [
                "VEN85",
                "Loan Agreement for Sample Project",
                "Annotated",
                "Venezuela",
                "Loan",
                "",
                "",
                "",
                "January 20, 2017",
                "",
            ]
        )
        # Format 2: "Day Month Year"
        writer.writerow(
            [
                "GHA33",
                "Eurobond Prospectus",
                "Annotated",
                "Ghana",
                "Bond",
                "",
                "",
                "",
                "24 September 2025",
                "",
            ]
        )
        # Format 3: "Month Day[ordinal], Year" — ordinal suffix
        writer.writerow(
            [
                "IDN199",
                "Bond with ordinal date",
                "Annotated",
                "Indonesia",
                "Bond",
                "",
                "",
                "",
                "July 6th, 2018",
                "",
            ]
        )

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    return db_path, inventory, manifest_dir


def test_regenerate_pdip_manifest_enriches_from_csv(
    fake_corpus: tuple[Path, Path, Path],
) -> None:
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir)

    manifest_path = manifest_dir / "pdip_manifest.jsonl"
    assert manifest_path.exists()
    records = [json.loads(line) for line in manifest_path.read_text().splitlines() if line]
    assert len(records) == 3
    by_id = {r["native_id"]: r for r in records}

    # "January 20, 2017" → "2017-01-20"
    ven = by_id["VEN85"]
    assert ven["source"] == "pdip"
    assert ven["storage_key"] == "pdip__VEN85"
    assert ven["title"] == "Loan Agreement for Sample Project"
    assert ven["issuer_name"] == "Venezuela"
    assert ven["doc_type"] == "Loan"
    assert ven["publication_date"] == "2017-01-20"
    assert ven["download_url"] == "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85"
    assert ven["file_path"] == "data/pdfs/pdip/venezuela/VEN85.pdf"
    assert ven["source_metadata"]["tag_status"] == "Annotated"
    # Raw date preserved in source_metadata for audit trail
    assert ven["source_metadata"]["document_date_raw"] == "January 20, 2017"

    # "24 September 2025" → "2025-09-24"
    assert by_id["GHA33"]["publication_date"] == "2025-09-24"

    # "July 6th, 2018" → "2018-07-06" (ordinal suffix stripped)
    assert by_id["IDN199"]["publication_date"] == "2018-07-06"


def test_regenerate_pdip_manifest_round_trips_through_ingest(
    fake_corpus: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The regenerated manifest must survive a full ingest into a fresh
    DuckDB without raising ConversionException. This is the canary for the
    date-parsing bug caught in review."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir)

    rebuild_db_path = tmp_path / "rebuild.duckdb"
    rebuild_conn = duckdb.connect(str(rebuild_db_path))
    try:
        create_schema(rebuild_conn)
        # Must NOT raise. Before the fix, this crashed with
        # ConversionException: invalid date field format: "January 20, 2017"
        stats = ingest_manifests(rebuild_conn, manifest_dir)
        assert stats["documents_inserted"] == 3
        assert stats["documents_skipped"] == 0

        rows = rebuild_conn.execute(
            "SELECT native_id, publication_date FROM documents "
            "WHERE source = 'pdip' ORDER BY native_id"
        ).fetchall()
    finally:
        rebuild_conn.close()

    by_id = {native_id: pub_date for native_id, pub_date in rows}
    assert by_id["VEN85"] == _dt.date(2017, 1, 20)
    assert by_id["GHA33"] == _dt.date(2025, 9, 24)
    assert by_id["IDN199"] == _dt.date(2018, 7, 6)


def test_regenerate_pdip_manifest_handles_row_missing_from_inventory(
    tmp_path: Path,
) -> None:
    """A PDIP row that exists in the DB but not in the inventory CSV must
    still land in the manifest with publication_date = None, not crash."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path = tmp_path / "corpus.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    conn.execute(
        "INSERT INTO documents (source, native_id, storage_key, file_path) VALUES "
        "('pdip', 'ORPHAN1', 'pdip__ORPHAN1', 'data/pdfs/pdip/xxx/ORPHAN1.pdf')"
    )
    conn.close()

    inventory = tmp_path / "pdip_document_inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "document_title", "document_date"])
        # No ORPHAN1 row at all.

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    regenerate_pdip_manifest(db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir)

    records = [
        json.loads(line)
        for line in (manifest_dir / "pdip_manifest.jsonl").read_text().splitlines()
        if line
    ]
    assert len(records) == 1
    assert records[0]["native_id"] == "ORPHAN1"
    assert records[0]["publication_date"] is None
    assert records[0]["title"] is None


def test_regenerate_pdip_manifest_is_atomic(
    fake_corpus: tuple[Path, Path, Path],
) -> None:
    """The script must write to .part and rename, never leaving a partial file."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir)
    assert (manifest_dir / "pdip_manifest.jsonl").exists()
    assert not (manifest_dir / "pdip_manifest.jsonl.part").exists()
