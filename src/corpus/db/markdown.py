"""Load .md sidecar files into the document_markdown table.

Each Docling-parsed PDF produces a {storage_key}.md file containing
the full markdown representation. This module reads those files and
stores them in document_markdown for the Streamlit detail panel.

For EDGAR HTML documents, the parsed HTML can be stored directly
(Streamlit's st.markdown() handles basic HTML).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

log = logging.getLogger(__name__)


def build_markdown(
    conn: duckdb.DuckDBPyConnection,
    parsed_dir: Path,
) -> dict[str, Any]:
    """Read .md files from parsed_dir and insert into document_markdown.

    Returns stats dict with inserted, skipped, no_document.
    """
    inserted = 0
    skipped = 0
    no_document = 0

    # Build storage_key → document_id lookup
    rows = conn.execute("SELECT document_id, storage_key FROM documents").fetchall()
    sk_to_id: dict[str, int] = {row[1]: row[0] for row in rows}

    for md_path in sorted(parsed_dir.glob("*.md")):
        if md_path.name.startswith("_"):
            continue

        storage_key = md_path.stem
        doc_id = sk_to_id.get(storage_key)
        if doc_id is None:
            no_document += 1
            continue

        # Check if already exists
        existing = conn.execute(
            "SELECT 1 FROM document_markdown WHERE document_id = ? LIMIT 1", [doc_id]
        ).fetchone()
        if existing is not None:
            skipped += 1
            continue

        try:
            markdown_text = md_path.read_text()
        except OSError:
            log.warning("Failed to read %s", md_path)
            skipped += 1
            continue

        if not markdown_text.strip():
            skipped += 1
            continue

        conn.execute(
            "INSERT INTO document_markdown (document_id, markdown_text) VALUES (?, ?)",
            [doc_id, markdown_text],
        )
        inserted += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "no_document": no_document,
    }
