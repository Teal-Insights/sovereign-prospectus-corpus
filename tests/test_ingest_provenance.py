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


def test_ingest_derives_provenance_fields_when_manifest_omits_them(
    tmp_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """Source adapters (edgar.py, nsm.py, pdip.py) don't write
    source_page_url / source_page_kind into their manifest records. This
    test pins the ingest-layer fallback that calls ``resolve_source_page``
    when the fields are missing, so newly-discovered documents don't
    silently regress to NULL provenance columns after this PR.

    Regression test for a P1 finding from an external code review.
    """
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    # EDGAR record without source_page_url/source_page_kind, mimicking
    # exactly what src/corpus/sources/edgar.py writes today.
    edgar = {
        "source": "edgar",
        "native_id": "0001193125-20-188103",
        "storage_key": "edgar__0001193125-20-188103",
        "title": "TEST FILING",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    # NSM record, mimicking src/corpus/sources/nsm.py output.
    nsm = {
        "source": "nsm",
        "native_id": "abc",
        "storage_key": "nsm__abc",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
    }
    # PDIP record, mimicking legacy DB state (impoverished).
    pdip = {
        "source": "pdip",
        "native_id": "VEN85",
        "storage_key": "pdip__VEN85",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(edgar) + "\n")
    (manifest_dir / "nsm_manifest.jsonl").write_text(json.dumps(nsm) + "\n")
    (manifest_dir / "pdip_manifest.jsonl").write_text(json.dumps(pdip) + "\n")

    ingest_manifests(tmp_db, manifest_dir)

    rows = tmp_db.execute(
        "SELECT storage_key, source_page_url, source_page_kind FROM documents ORDER BY storage_key"
    ).fetchall()
    by_key = {r[0]: (r[1], r[2]) for r in rows}

    edgar_url, edgar_kind = by_key["edgar__0001193125-20-188103"]
    assert edgar_url is not None
    assert "914021" in edgar_url
    assert edgar_kind == "filing_index"

    nsm_url, nsm_kind = by_key["nsm__abc"]
    assert nsm_url == "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf"
    assert nsm_kind == "artifact_pdf"

    pdip_url, pdip_kind = by_key["pdip__VEN85"]
    assert pdip_url == "https://publicdebtispublic.mdi.georgetown.edu/search/"
    assert pdip_kind == "search_page"


def test_ingest_respects_manifest_values_when_both_keys_present(
    tmp_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """If the manifest already has source_page_url / source_page_kind,
    ingest must NOT overwrite them with a derived value — the manifest
    is canonical."""
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "edgar",
        "native_id": "override-test",
        "storage_key": "edgar__override-test",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
        "source_page_url": "https://example.com/manually-set",
        "source_page_kind": "filing_index",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(record) + "\n")

    ingest_manifests(tmp_db, manifest_dir)

    row = tmp_db.execute(
        "SELECT source_page_url FROM documents WHERE storage_key = ?",
        ["edgar__override-test"],
    ).fetchone()
    assert row is not None
    assert row[0] == "https://example.com/manually-set"
