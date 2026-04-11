"""Tests for document_pages build and FTS index."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb

from corpus.db.pages import build_pages, create_fts_index
from corpus.db.schema import create_schema

if TYPE_CHECKING:
    from pathlib import Path


def _setup_db_with_doc(conn: duckdb.DuckDBPyConnection, storage_key: str = "nsm__123") -> int:
    """Create schema and insert a test document, return document_id."""
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


def _write_jsonl(path: Path, storage_key: str, pages: list[dict]) -> None:
    header = {"storage_key": storage_key, "page_count": len(pages), "parse_tool": "docling"}
    lines = [json.dumps(header)]
    for p in pages:
        lines.append(json.dumps(p))
    path.write_text("\n".join(lines) + "\n")


def test_build_pages_inserts_from_jsonl(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    doc_id = _setup_db_with_doc(conn, "nsm__123")

    _write_jsonl(
        tmp_path / "nsm__123.jsonl",
        "nsm__123",
        [
            {"page": 0, "text": "First page content", "char_count": 18},
            {"page": 1, "text": "Second page content", "char_count": 19},
        ],
    )

    stats = build_pages(conn, tmp_path)
    assert stats["pages_inserted"] == 2
    assert stats["files_processed"] == 1

    rows = conn.execute(
        "SELECT page_number, page_text FROM document_pages WHERE document_id = ? ORDER BY page_number",
        [doc_id],
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] == 1  # 0-indexed → 1-indexed
    assert rows[0][1] == "First page content"
    assert rows[1][0] == 2


def test_build_pages_skips_unknown_storage_key(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")

    _write_jsonl(
        tmp_path / "nsm__999.jsonl", "nsm__999", [{"page": 0, "text": "x", "char_count": 1}]
    )

    stats = build_pages(conn, tmp_path)
    assert stats["files_skipped"] == 1
    assert stats["pages_inserted"] == 0


def test_build_pages_skips_already_processed(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")

    _write_jsonl(
        tmp_path / "nsm__123.jsonl", "nsm__123", [{"page": 0, "text": "x", "char_count": 1}]
    )

    # First run
    build_pages(conn, tmp_path)
    # Second run — should skip
    stats = build_pages(conn, tmp_path)
    assert stats["files_skipped"] == 1
    assert stats["pages_inserted"] == 0


def test_fts_index_creation(tmp_path: Path):
    conn = duckdb.connect(":memory:")
    _setup_db_with_doc(conn, "nsm__123")

    _write_jsonl(
        tmp_path / "nsm__123.jsonl",
        "nsm__123",
        [
            {"page": 0, "text": "collective action clauses are important", "char_count": 40},
            {"page": 1, "text": "governing law of this prospectus", "char_count": 32},
        ],
    )
    build_pages(conn, tmp_path)
    create_fts_index(conn)

    # FTS search
    results = conn.execute(
        "SELECT page_id, page_text, score "
        "FROM (SELECT *, fts_main_document_pages.match_bm25(page_id, 'collective action') AS score "
        "FROM document_pages) WHERE score IS NOT NULL ORDER BY score DESC"
    ).fetchall()
    assert len(results) >= 1
    assert "collective action" in results[0][1]
