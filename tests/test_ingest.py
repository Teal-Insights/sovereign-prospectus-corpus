"""Tests for the JSONL manifest → DuckDB ingest module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from pathlib import Path

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


def _make_manifest(directory: Path, source: str, records: list[dict]) -> Path:
    """Write a JSONL manifest file and return its path."""
    manifest = directory / f"{source}_manifest.jsonl"
    with manifest.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return manifest


def _minimal_record(source: str = "nsm", native_id: str = "12345") -> dict:
    """Return a minimal valid manifest record."""
    return {
        "source": source,
        "native_id": native_id,
        "storage_key": f"{source}__{native_id}",
        "title": "Republic of Testland Bond Prospectus",
        "download_url": "https://example.com/doc.pdf",
        "file_path": f"data/original/{source}__{native_id}.pdf",
    }


def test_ingest_single_manifest(tmp_path: Path) -> None:
    """One manifest with one record produces one row in documents."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    _make_manifest(tmp_path, "nsm", [_minimal_record()])
    stats = ingest_manifests(conn, tmp_path)

    rows = conn.execute("SELECT * FROM documents").fetchall()
    assert len(rows) == 1
    assert stats["documents_inserted"] == 1


def test_ingest_multiple_sources(tmp_path: Path) -> None:
    """Manifests from different sources all get ingested."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    _make_manifest(tmp_path, "nsm", [_minimal_record("nsm", "001")])
    _make_manifest(tmp_path, "edgar", [_minimal_record("edgar", "002")])

    stats = ingest_manifests(conn, tmp_path)

    rows = conn.execute("SELECT source, native_id FROM documents ORDER BY source").fetchall()
    assert len(rows) == 2
    assert stats["documents_inserted"] == 2


def test_ingest_skips_duplicate_storage_key(tmp_path: Path) -> None:
    """Duplicate storage_key records are skipped, not errored."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    rec = _minimal_record()
    _make_manifest(tmp_path, "nsm", [rec, rec])
    stats = ingest_manifests(conn, tmp_path)

    rows = conn.execute("SELECT * FROM documents").fetchall()
    assert len(rows) == 1
    assert stats["documents_skipped"] >= 1


def test_ingest_records_pipeline_run(tmp_path: Path) -> None:
    """Ingest records itself in the pipeline_runs table."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    _make_manifest(tmp_path, "nsm", [_minimal_record()])
    stats = ingest_manifests(conn, tmp_path, run_id="test-run-001")

    runs = conn.execute(
        "SELECT * FROM pipeline_runs WHERE run_id = 'test-run-001' AND step = 'ingest'"
    ).fetchall()
    assert len(runs) == 1
    assert stats["run_id"] == "test-run-001"


def test_ingest_no_manifests(tmp_path: Path) -> None:
    """Empty directory produces zero inserts, no errors."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    stats = ingest_manifests(conn, tmp_path)
    assert stats["documents_inserted"] == 0


def test_ingest_populates_source_metadata(tmp_path: Path) -> None:
    """Extra fields in the manifest go into source_metadata JSON."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    rec = _minimal_record()
    rec["lei"] = "529900HNOAA1KXQJUQ27"
    rec["issuer_name"] = "Republic of Testland"
    rec["extra_nsm_field"] = "some_value"

    _make_manifest(tmp_path, "nsm", [rec])
    ingest_manifests(conn, tmp_path)

    row = conn.execute("SELECT lei, issuer_name, source_metadata FROM documents").fetchone()
    assert row is not None
    assert row[0] == "529900HNOAA1KXQJUQ27"
    assert row[1] == "Republic of Testland"
    # Extra fields go into source_metadata
    metadata = json.loads(row[2]) if row[2] else {}
    assert metadata.get("extra_nsm_field") == "some_value"


def test_ingest_populates_countries(tmp_path: Path) -> None:
    """Records with country info populate document_countries."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    rec = _minimal_record()
    rec["countries"] = [
        {"country_code": "TST", "country_name": "Testland", "role": "issuer"},
    ]

    _make_manifest(tmp_path, "nsm", [rec])
    ingest_manifests(conn, tmp_path)

    countries = conn.execute(
        "SELECT country_code, country_name, role FROM document_countries"
    ).fetchall()
    assert len(countries) == 1
    assert countries[0][0] == "TST"


def test_ingest_malformed_json_skipped(tmp_path: Path) -> None:
    """Malformed JSON lines are skipped, not fatal."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    manifest = tmp_path / "nsm_manifest.jsonl"
    good = json.dumps(_minimal_record())
    manifest.write_text(f"{good}\n{{bad json\n")

    stats = ingest_manifests(conn, tmp_path)
    assert stats["documents_inserted"] == 1
    assert stats["errors"] == 1


def test_ingest_missing_storage_key_skipped(tmp_path: Path) -> None:
    """Records without storage_key are skipped."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    rec = {"source": "nsm", "native_id": "999", "title": "No key"}
    _make_manifest(tmp_path, "nsm", [rec])

    stats = ingest_manifests(conn, tmp_path)
    assert stats["documents_inserted"] == 0
    assert stats["documents_skipped"] == 1


def test_ingest_country_missing_code_skipped(tmp_path: Path) -> None:
    """Country entries without country_code are silently skipped."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    rec = _minimal_record()
    rec["countries"] = [{"country_name": "Testland", "role": "issuer"}]

    _make_manifest(tmp_path, "nsm", [rec])
    ingest_manifests(conn, tmp_path)

    countries = conn.execute("SELECT * FROM document_countries").fetchall()
    assert len(countries) == 0


def test_ingest_pipeline_run_records_failure(tmp_path: Path) -> None:
    """Pipeline run status is 'completed' on success."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    _make_manifest(tmp_path, "nsm", [_minimal_record()])
    ingest_manifests(conn, tmp_path, run_id="run-ok")

    row = conn.execute("SELECT status FROM pipeline_runs WHERE run_id = 'run-ok'").fetchone()
    assert row is not None
    assert row[0] == "completed"
