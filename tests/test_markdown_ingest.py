"""Tests for document_markdown ingest."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from corpus.db.markdown import build_markdown
from corpus.db.schema import create_schema

if TYPE_CHECKING:
    from pathlib import Path


def _setup_db_with_doc(conn: duckdb.DuckDBPyConnection, storage_key: str = "nsm__123") -> int:
    create_schema(conn)
    conn.execute(
        "INSERT INTO documents (source, native_id, storage_key) VALUES (?, ?, ?)",
        ["nsm", "123", storage_key],
    )
    row = conn.execute(
        "SELECT document_id FROM documents WHERE storage_key = ?", [storage_key]
    ).fetchone()
    assert row is not None
    return row[0]


def test_inserts_markdown(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    doc_id = _setup_db_with_doc(conn, "nsm__123")

    (tmp_path / "nsm__123.md").write_text("## Title\n\nSome **bold** text\n")

    stats = build_markdown(conn, tmp_path)
    assert stats["inserted"] == 1

    row = conn.execute(
        "SELECT markdown_text FROM document_markdown WHERE document_id = ?", [doc_id]
    ).fetchone()
    assert row is not None
    assert "## Title" in row[0]


def test_skips_unknown_storage_key(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")
    (tmp_path / "nsm__999.md").write_text("# Unknown\n")

    stats = build_markdown(conn, tmp_path)
    assert stats["no_document"] == 1
    assert stats["inserted"] == 0


def test_skips_already_inserted(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")
    (tmp_path / "nsm__123.md").write_text("# Test\n")

    build_markdown(conn, tmp_path)
    stats = build_markdown(conn, tmp_path)
    assert stats["skipped"] == 1
    assert stats["inserted"] == 0


def test_skips_empty_markdown(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")
    (tmp_path / "nsm__123.md").write_text("   \n")

    stats = build_markdown(conn, tmp_path)
    assert stats["skipped"] == 1
