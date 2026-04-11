"""Build document_pages table and FTS index from parsed JSONL files.

Reads per-page text from JSONL files (line 2+), resolves document_id via
storage_key, and inserts into document_pages. Then creates a DuckDB FTS
index for full-text search.

Page numbers are stored 1-indexed (for display). JSONL page field is
0-indexed — we add 1 during ingest.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

log = logging.getLogger(__name__)


def build_pages(
    conn: duckdb.DuckDBPyConnection,
    parsed_dir: Path,
) -> dict[str, Any]:
    """Read JSONL files and populate document_pages table.

    Returns stats dict with pages_inserted, files_processed, files_skipped.
    """
    pages_inserted = 0
    files_processed = 0
    files_skipped = 0

    # Build storage_key → document_id lookup
    rows = conn.execute("SELECT document_id, storage_key FROM documents").fetchall()
    sk_to_id: dict[str, int] = {row[1]: row[0] for row in rows}

    for jsonl_path in sorted(parsed_dir.glob("*.jsonl")):
        if jsonl_path.name.startswith("_"):
            continue  # Skip _progress.jsonl, _errors.log, etc.

        storage_key = jsonl_path.stem
        doc_id = sk_to_id.get(storage_key)
        if doc_id is None:
            files_skipped += 1
            continue

        # Check if pages already exist for this document
        existing = conn.execute(
            "SELECT 1 FROM document_pages WHERE document_id = ? LIMIT 1", [doc_id]
        ).fetchone()
        if existing is not None:
            files_skipped += 1
            continue

        try:
            with jsonl_path.open() as f:
                lines = f.readlines()
        except OSError:
            log.warning("Failed to read %s", jsonl_path)
            files_skipped += 1
            continue

        # Skip header (line 0), process page lines (line 1+)
        batch: list[tuple[int, int, str, int]] = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            try:
                page = json.loads(line)
            except json.JSONDecodeError:
                continue
            page_number = page.get("page", 0) + 1  # 0-indexed → 1-indexed
            text = page.get("text", "")
            char_count = page.get("char_count", len(text))
            batch.append((doc_id, page_number, text, char_count))

        if batch:
            conn.executemany(
                "INSERT INTO document_pages (document_id, page_number, page_text, char_count) "
                "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                batch,
            )
            pages_inserted += len(batch)

        files_processed += 1

    return {
        "pages_inserted": pages_inserted,
        "files_processed": files_processed,
        "files_skipped": files_skipped,
    }


def create_fts_index(conn: duckdb.DuckDBPyConnection) -> None:
    """Create a DuckDB FTS index on document_pages.page_text.

    Uses DuckDB's built-in full-text search extension (fts).
    Drops and recreates if it already exists.
    """
    conn.execute("INSTALL fts")
    conn.execute("LOAD fts")

    # Drop existing index if present
    import contextlib

    with contextlib.suppress(Exception):
        conn.execute("PRAGMA drop_fts_index('document_pages')")

    conn.execute("PRAGMA create_fts_index('document_pages', 'page_id', 'page_text', overwrite=1)")
    log.info("FTS index created on document_pages.page_text")
