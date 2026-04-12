"""Publish local DuckDB tables to MotherDuck.

Connects to MotherDuck using the MOTHERDUCK_TOKEN env var, creates
the remote database if needed, and copies tables from the local
corpus.duckdb.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)

_TABLES_TO_PUBLISH = [
    "documents",
    "document_countries",
    "document_markdown",
    "document_pages",
    "grep_matches",
    "pdip_clauses",
]


def publish_to_motherduck(
    local_db_path: Path,
    *,
    remote_db: str = "sovereign_corpus",
) -> dict[str, Any]:
    """Copy tables from local DuckDB to MotherDuck.

    Requires MOTHERDUCK_TOKEN environment variable.
    Returns stats dict with tables_published and rows per table.
    """
    import duckdb

    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise RuntimeError(
            "MOTHERDUCK_TOKEN not set. Get a token at https://app.motherduck.com/token"
        )

    stats: dict[str, Any] = {"tables_published": 0, "table_rows": {}}

    # Connect to local DB first, then attach MotherDuck
    conn = duckdb.connect(str(local_db_path))
    try:
        conn.execute(f"ATTACH 'md:{remote_db}' AS remote")

        for table in _TABLES_TO_PUBLISH:
            # Check if local table exists and has rows
            try:
                count_row = conn.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()
            except duckdb.CatalogException:
                log.info("Skipping %s — not in local DB", table)
                continue

            row_count = count_row[0] if count_row else 0
            if row_count == 0:
                log.info("Skipping %s — empty", table)
                continue

            # Drop and recreate in remote
            conn.execute(f"DROP TABLE IF EXISTS remote.{table}")
            conn.execute(f"CREATE TABLE remote.{table} AS SELECT * FROM main.{table}")

            stats["tables_published"] += 1
            stats["table_rows"][table] = row_count
            log.info("Published %s: %d rows", table, row_count)

        # Recreate FTS index on remote document_pages.
        # PRAGMA create_fts_index doesn't work with schema-qualified names,
        # so we switch the active schema to remote first.
        if "document_pages" in stats["table_rows"]:
            log.info("Creating FTS index on remote document_pages...")
            conn.execute("INSTALL fts")
            conn.execute("LOAD fts")
            conn.execute(f"USE {remote_db}")
            conn.execute(
                "PRAGMA create_fts_index('document_pages', 'page_id', 'page_text', overwrite=1)"
            )
            log.info("FTS index created on MotherDuck")

    finally:
        conn.close()

    return stats
