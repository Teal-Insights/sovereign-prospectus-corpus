"""DuckDB schema creation for the sovereign prospectus corpus.

Tables:
    documents           — One row per downloaded document.
    document_countries  — Many-to-many: documents <-> country codes.
    grep_matches        — Pattern matches found via grep-first extraction.
    source_events       — Dedup log for monitoring (new filings detected).
    pipeline_runs       — Provenance: which pipeline step ran when.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

_DDL_FILE = Path(__file__).resolve().parents[3] / "sql" / "001_corpus.sql"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all corpus tables. Idempotent (IF NOT EXISTS).

    DuckDB's execute() handles one statement at a time, so we split
    the DDL file on semicolons and run each statement separately.
    """
    ddl = _DDL_FILE.read_text()
    # Strip SQL comments, then split on semicolons
    lines = [line for line in ddl.splitlines() if not line.strip().startswith("--")]
    cleaned = "\n".join(lines)
    for statement in cleaned.split(";"):
        stripped = statement.strip()
        if stripped:
            conn.execute(stripped)
