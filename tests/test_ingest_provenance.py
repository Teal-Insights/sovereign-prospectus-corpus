"""Round-trip test: provenance URL fields land as top-level columns."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb
import pytest

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    """Create a fresh DuckDB with the corpus schema."""
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    return conn


def test_provenance_fields_are_top_level_columns(
    tmp_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """source_page_url and source_page_kind must be stored as columns,
    not merged into source_metadata JSON."""
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "edgar",
        "native_id": "0001193125-20-188103",
        "storage_key": "edgar__0001193125-20-188103",
        "title": "TEST FILING",
        "source_page_url": "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm",
        "source_page_kind": "filing_index",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(record) + "\n")

    ingest_manifests(tmp_db, manifest_dir)

    row = tmp_db.execute(
        "SELECT source_page_url, source_page_kind, source_metadata "
        "FROM documents WHERE storage_key = ?",
        ["edgar__0001193125-20-188103"],
    ).fetchone()
    assert row is not None
    assert row[0] == record["source_page_url"]
    assert row[1] == "filing_index"
    # Must NOT have been merged into source_metadata
    if row[2] is not None:
        meta = json.loads(row[2])
        assert "source_page_url" not in meta
        assert "source_page_kind" not in meta
