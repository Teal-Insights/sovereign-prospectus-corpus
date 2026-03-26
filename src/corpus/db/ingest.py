"""Load JSONL manifests into DuckDB.

Each source adapter produces a ``{source}_manifest.jsonl`` file.
This module reads all manifests from a directory and inserts records
into the ``documents`` (and optionally ``document_countries``) tables.

Designed to run serially — avoids DuckDB's single-writer limitation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb

log = logging.getLogger(__name__)

# Columns in the documents table that we map directly from manifest records.
_DOCUMENT_COLUMNS = frozenset(
    {
        "source",
        "native_id",
        "storage_key",
        "family_id",
        "doc_type",
        "title",
        "issuer_name",
        "lei",
        "publication_date",
        "submitted_date",
        "download_url",
        "file_path",
        "file_hash",
        "page_count",
        "parse_tool",
        "parse_version",
        "is_sovereign",
        "issuer_type",
        "scope_status",
    }
)

# Keys that are handled specially (not stored directly or in source_metadata).
_SPECIAL_KEYS = frozenset({"countries", "source_metadata"})


def ingest_manifests(
    conn: duckdb.DuckDBPyConnection,
    manifest_dir: Path,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Read ``*_manifest.jsonl`` files and insert into DuckDB.

    Returns a stats dict with ``documents_inserted``, ``documents_skipped``,
    and ``run_id``.
    """
    if run_id is None:
        run_id = f"ingest-{uuid.uuid4().hex[:12]}"

    manifest_dir = Path(manifest_dir)
    manifests = sorted(manifest_dir.glob("*_manifest.jsonl"))

    inserted = 0
    skipped = 0
    errors = 0

    # Record pipeline run start
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, step, started_at, status) "
        "VALUES (?, 'ingest', ?, 'running')",
        [run_id, datetime.now(UTC)],
    )

    try:
        for manifest_path in manifests:
            with manifest_path.open() as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning(
                            "Skipping malformed JSON at %s:%d", manifest_path.name, line_num
                        )
                        errors += 1
                        continue
                    ok = _insert_document(conn, record)
                    if ok:
                        inserted += 1
                    else:
                        skipped += 1

        status = "completed"
        error_msg = None
    except Exception as exc:
        status = "failed"
        error_msg = str(exc)
        raise
    finally:
        conn.execute(
            "UPDATE pipeline_runs SET ended_at = ?, status = ?, doc_count = ?, error_msg = ? "
            "WHERE run_id = ? AND step = 'ingest'",
            [datetime.now(UTC), status, inserted, error_msg, run_id],
        )

    return {
        "documents_inserted": inserted,
        "documents_skipped": skipped,
        "errors": errors,
        "run_id": run_id,
    }


def _insert_document(conn: duckdb.DuckDBPyConnection, record: dict) -> bool:
    """Insert a single document record. Returns True if inserted, False if skipped."""
    storage_key = record.get("storage_key")
    if storage_key is None:
        return False

    # Check if already exists (skip duplicates)
    existing = conn.execute(
        "SELECT document_id FROM documents WHERE storage_key = ?", [storage_key]
    ).fetchone()
    if existing is not None:
        return False

    # Separate known columns from extra metadata
    doc_values: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}

    for key, value in record.items():
        if key in _SPECIAL_KEYS:
            continue
        elif key in _DOCUMENT_COLUMNS:
            doc_values[key] = value
        else:
            extra_metadata[key] = value

    # Merge explicit source_metadata with extra fields
    if "source_metadata" in record:
        existing_meta = record["source_metadata"]
        if isinstance(existing_meta, str):
            existing_meta = json.loads(existing_meta)
        extra_metadata.update(existing_meta)

    if extra_metadata:
        doc_values["source_metadata"] = json.dumps(extra_metadata)

    # Insert
    columns = list(doc_values.keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    conn.execute(
        f"INSERT INTO documents ({col_names}) VALUES ({placeholders})",
        list(doc_values.values()),
    )

    # Handle countries if present
    if "countries" in record:
        doc_id = conn.execute(
            "SELECT document_id FROM documents WHERE storage_key = ?", [storage_key]
        ).fetchone()
        if doc_id:
            _insert_countries(conn, doc_id[0], record["countries"])

    return True


def _insert_countries(
    conn: duckdb.DuckDBPyConnection,
    document_id: int,
    countries: list[dict],
) -> None:
    """Insert country associations for a document."""
    for country in countries:
        code = country.get("country_code")
        if not code:
            continue
        conn.execute(
            "INSERT INTO document_countries (document_id, country_code, country_name, role) "
            "VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
            [
                document_id,
                code,
                country.get("country_name"),
                country.get("role", "issuer"),
            ],
        )
