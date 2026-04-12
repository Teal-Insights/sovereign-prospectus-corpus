"""Tests for explorer database queries.

These tests require the local corpus.duckdb to exist with data.
Skip if the DB is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DB_PATH = Path("data/db/corpus.duckdb")

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="Local corpus.duckdb not available")


@pytest.fixture
def con():
    """Connect to the local DB. Requires sovereign_issuers table to exist.

    Run Task 6 (populate DB) before these tests. All query functions JOIN
    on sovereign_issuers, so they fail with CatalogError if the table is
    missing.
    """
    import duckdb

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    conn.execute("INSTALL fts; LOAD fts")
    # Verify sovereign_issuers table exists
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "sovereign_issuers" not in tables:
        pytest.skip("sovereign_issuers table not yet populated -- run Task 6 first")
    yield conn
    conn.close()


def test_browse_query_returns_rows(con):
    from explorer.queries import browse_documents

    df = browse_documents(con, limit=10)
    assert len(df) > 0
    assert "display_name" in df.columns


def test_browse_query_null_safe(con):
    """No None values in display columns."""
    from explorer.queries import browse_documents

    df = browse_documents(con, limit=50)
    assert df["display_name"].isna().sum() == 0


def test_search_returns_results(con):
    from explorer.queries import search_documents

    results = search_documents(con, "collective action", limit=10)
    assert len(results) > 0
    assert "document_id" in results.columns
    assert "page_number" in results.columns
    assert "page_text" in results.columns


def test_search_grouped_by_document(con):
    """Each document appears at most once in results."""
    from explorer.queries import search_documents

    results = search_documents(con, "collective action", limit=50)
    assert results["document_id"].is_unique


def test_document_detail(con):
    from explorer.queries import get_document_detail

    # Get a known document_id
    row = con.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
    assert row is not None
    detail = get_document_detail(con, row[0])
    assert detail is not None
    assert "document_id" in detail
