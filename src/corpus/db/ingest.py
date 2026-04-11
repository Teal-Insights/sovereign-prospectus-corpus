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

from corpus.sources.provenance import resolve_source_page

if TYPE_CHECKING:
    import duckdb

log = logging.getLogger(__name__)

_JSONL_HEADER_FIELDS = frozenset({"parse_tool", "parse_version", "page_count"})


def read_jsonl_header(parsed_dir: Path, storage_key: str) -> dict[str, Any]:
    """Read the header line from a parsed JSONL file.

    Returns a dict with parse_tool, parse_version, page_count (if found),
    or an empty dict if the file doesn't exist.
    """
    jsonl_path = parsed_dir / f"{storage_key}.jsonl"
    if not jsonl_path.exists():
        return {}
    try:
        with jsonl_path.open() as f:
            first_line = f.readline().strip()
            if not first_line:
                return {}
            header = json.loads(first_line)
            return {k: v for k, v in header.items() if k in _JSONL_HEADER_FIELDS}
    except (json.JSONDecodeError, OSError):
        log.warning("Failed to read JSONL header for %s", storage_key)
        return {}


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
        "source_page_url",
        "source_page_kind",
    }
)

# Keys that are handled specially (not stored directly or in source_metadata).
_SPECIAL_KEYS = frozenset({"countries", "source_metadata"})


def ingest_manifests(
    conn: duckdb.DuckDBPyConnection,
    manifest_dir: Path,
    *,
    run_id: str | None = None,
    parsed_dir: Path | None = None,
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
                    ok = _insert_document(conn, record, parsed_dir=parsed_dir)
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


def _insert_document(
    conn: duckdb.DuckDBPyConnection,
    record: dict,
    *,
    parsed_dir: Path | None = None,
) -> bool:
    """Insert a single document record. Returns True if inserted, False if skipped.

    If parsed_dir is given and the manifest record lacks parse_tool/page_count,
    reads them from the corresponding JSONL header in parsed_dir.
    """
    storage_key = record.get("storage_key")
    if storage_key is None:
        return False

    # Check if already exists (skip duplicates)
    existing = conn.execute(
        "SELECT document_id FROM documents WHERE storage_key = ?", [storage_key]
    ).fetchone()
    if existing is not None:
        return False

    # Backfill parse_tool/page_count from JSONL header if missing
    if parsed_dir is not None:
        needs_backfill = any(record.get(f) is None for f in _JSONL_HEADER_FIELDS)
        if needs_backfill:
            header = read_jsonl_header(parsed_dir, storage_key)
            for field in _JSONL_HEADER_FIELDS:
                if record.get(field) is None and field in header:
                    record[field] = header[field]

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
            try:
                existing_meta = json.loads(existing_meta)
            except json.JSONDecodeError:
                log.warning(
                    "Failed to parse source_metadata JSON for storage_key=%s, "
                    "preserving raw string",
                    storage_key,
                )
                existing_meta = {"_raw_source_metadata": existing_meta}
        if isinstance(existing_meta, dict):
            extra_metadata.update(existing_meta)

    if extra_metadata:
        # ensure_ascii=False mirrors the backfill + regenerate scripts so
        # non-ASCII characters in titles, country names, etc. land as their
        # native UTF-8 bytes in the DuckDB VARCHAR column rather than as
        # \uXXXX escape sequences. DuckDB's JSON functions parse both forms
        # correctly, but human SQL inspection is much easier with the
        # non-escaped form.
        doc_values["source_metadata"] = json.dumps(extra_metadata, ensure_ascii=False)

    # Derive provenance URL fields atomically. The pair (source_page_url,
    # source_page_kind) is "canonical" if BOTH values are present and
    # non-null — otherwise we re-derive both and overwrite both. This
    # prevents three failure modes:
    #   (a) the manifest omits the fields entirely (current source adapters
    #       don't write them), producing NULL columns on new downloads
    #   (b) a manifest writes `"source_page_url": null` thinking the
    #       system will derive it, and the system doesn't
    #   (c) a manifest has one field but not the other, and a partial
    #       fallback mixes a manual URL with a derived kind that doesn't
    #       match it
    # The resolver is deterministic and idempotent for unknown sources
    # (returns (None, "none") every time), so re-running this on an
    # already-null record produces the same output.
    existing_url = doc_values.get("source_page_url")
    existing_kind = doc_values.get("source_page_kind")
    if existing_url is None or existing_kind is None:
        url, kind = resolve_source_page(record)
        doc_values["source_page_url"] = url
        doc_values["source_page_kind"] = kind

    # Insert and get the new document_id via RETURNING
    columns = list(doc_values.keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)
    result = conn.execute(
        f"INSERT INTO documents ({col_names}) VALUES ({placeholders}) RETURNING document_id",
        list(doc_values.values()),
    )
    row = result.fetchone()

    # Handle countries if present
    if row and "countries" in record:
        _insert_countries(conn, row[0], record["countries"])

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
