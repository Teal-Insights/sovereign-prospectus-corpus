"""Tests for DuckDB schema creation and integrity."""

from __future__ import annotations

import duckdb
import pytest

from corpus.db.schema import create_schema

EXPECTED_TABLES = {
    "documents",
    "document_countries",
    "grep_matches",
    "source_events",
    "pipeline_runs",
}

DOCUMENTS_COLUMNS = {
    "document_id": "INTEGER",
    "source": "VARCHAR",
    "native_id": "VARCHAR",
    "storage_key": "VARCHAR",
    "family_id": "VARCHAR",
    "doc_type": "VARCHAR",
    "title": "VARCHAR",
    "issuer_name": "VARCHAR",
    "lei": "VARCHAR",
    "publication_date": "DATE",
    "submitted_date": "TIMESTAMP",
    "download_url": "VARCHAR",
    "file_path": "VARCHAR",
    "file_hash": "VARCHAR",
    "page_count": "INTEGER",
    "parse_tool": "VARCHAR",
    "parse_version": "VARCHAR",
    "is_sovereign": "BOOLEAN",
    "issuer_type": "VARCHAR",
    "scope_status": "VARCHAR",
    "source_metadata": "VARCHAR",
    "created_at": "TIMESTAMP",
    "updated_at": "TIMESTAMP",
}


@pytest.fixture()
def db() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with schema applied."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)
    return conn


def test_all_tables_exist(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    tables = {r[0] for r in rows}
    assert tables >= EXPECTED_TABLES, f"Missing tables: {EXPECTED_TABLES - tables}"


def test_documents_columns(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'documents'"
    ).fetchall()
    columns = {r[0]: r[1] for r in rows}
    for col, dtype in DOCUMENTS_COLUMNS.items():
        assert col in columns, f"Missing column: {col}"
        assert columns[col] == dtype, f"{col}: expected {dtype}, got {columns[col]}"


def test_documents_unique_storage_key(db: duckdb.DuckDBPyConnection) -> None:
    db.execute(
        "INSERT INTO documents (source, native_id, storage_key) VALUES ('nsm', '123', 'nsm__123')"
    )
    with pytest.raises(duckdb.ConstraintException):
        db.execute(
            "INSERT INTO documents (source, native_id, storage_key) VALUES ('nsm', '456', 'nsm__123')"
        )


def test_document_countries_has_required_columns(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'document_countries'"
    ).fetchall()
    columns = {r[0] for r in rows}
    assert {"document_id", "country_code", "country_name"} <= columns


def test_grep_matches_has_required_columns(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'grep_matches'"
    ).fetchall()
    columns = {r[0] for r in rows}
    assert {
        "document_id",
        "pattern_name",
        "pattern_version",
        "page_number",
        "matched_text",
    } <= columns


def test_source_events_has_required_columns(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'source_events'"
    ).fetchall()
    columns = {r[0] for r in rows}
    assert {"event_id", "source", "native_id", "event_type", "detected_at"} <= columns


def test_pipeline_runs_has_required_columns(db: duckdb.DuckDBPyConnection) -> None:
    rows = db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'pipeline_runs'"
    ).fetchall()
    columns = {r[0] for r in rows}
    assert {"run_id", "step", "started_at", "status"} <= columns


def test_schema_is_idempotent(db: duckdb.DuckDBPyConnection) -> None:
    """Calling create_schema twice should not error."""
    create_schema(db)
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    tables = {r[0] for r in rows}
    assert tables >= EXPECTED_TABLES
