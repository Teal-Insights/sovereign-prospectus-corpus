"""Build the static snapshot consumed by the web explorer.

Reads corpus.duckdb (read-only) and writes three components:

- ``documents.parquet`` — one row per document with the metadata the
  explorer displays (issuer, country, region, income group, source,
  date, type, original-filing URL) plus a stable URL slug.
- ``text/<slug>.json`` — per-document full text plus table-of-contents
  structure derived from markdown headings. Plain JSON, gzip-friendly.
- ``MANIFEST.json`` — snapshot date, document counts, schema version,
  and component sizes.

The snapshot is a read-only consumer of the pipeline database
(architecture decision 4: modular output layer).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from corpus.io.safe_write import safe_write
from corpus.reference.issuer_country_map import ISSUER_TO_COUNTRY
from corpus.reference.wb_classifications import WORLD_BANK_CLASSIFICATIONS

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

SCHEMA_VERSION = 1

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# h2-h3 covers Docling output (all sections are h2); the EDGAR HTML parser
# emits h5 for section headings, so capture through h5 with true levels.
# [ \t] (not \s) so a bare "##" line can't swallow its newline and turn
# the next line into a bogus heading title.
_HEADING_RE = re.compile(r"^(#{2,5})[ \t]+(.+)$", re.MULTILINE)


def slugify(storage_key: str) -> str:
    """Stable URL slug from a storage key (``nsm__123`` → ``nsm-123``)."""
    return _SLUG_RE.sub("-", storage_key.lower()).strip("-")


def extract_toc(markdown_text: str) -> list[dict[str, Any]]:
    """Extract ``##`` through ``#####`` headings with char offsets into the text."""
    return [
        {
            "level": len(match.group(1)),
            "title": match.group(2).strip(),
            "offset": match.start(),
        }
        for match in _HEADING_RE.finditer(markdown_text)
    ]


def resolve_country(issuer_name: str | None) -> dict[str, Any]:
    """Map an issuer name to country/region/income metadata.

    Mirrors the explorer's sovereign_issuers join: unmapped issuers get
    'Unknown' names and NULL classification fields.
    """
    mapped = ISSUER_TO_COUNTRY.get(issuer_name or "")
    if mapped is None:
        return {
            "country_code": None,
            "country_name": "Unknown",
            "is_sovereign": None,
            "region": "Unknown",
            "income_group": "Unknown",
            "lending_category": None,
        }
    code, country_name, is_sovereign = mapped
    wb = WORLD_BANK_CLASSIFICATIONS.get(code)
    region, income, lending = wb if wb is not None else ("Unknown", "Unknown", None)
    return {
        "country_code": code,
        "country_name": country_name,
        "is_sovereign": is_sovereign,
        "region": region,
        "income_group": income,
        "lending_category": lending,
    }


def _fetch_text(
    conn: duckdb.DuckDBPyConnection, document_id: int
) -> tuple[str | None, str | None]:
    """Return (text, text_source) for a document.

    Prefers the full markdown; falls back to concatenated page text.
    """
    row = conn.execute(
        "SELECT markdown_text FROM document_markdown WHERE document_id = ?",
        [document_id],
    ).fetchone()
    if row is not None and row[0]:
        return row[0], "markdown"

    pages = conn.execute(
        "SELECT page_text FROM document_pages WHERE document_id = ? ORDER BY page_number",
        [document_id],
    ).fetchall()
    if pages:
        text = "\n\n".join(p[0] or "" for p in pages)
        if text.strip():
            return text, "pages"
    return None, None


def build_snapshot(
    db_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Generate the full snapshot. Returns a stats dict (also in MANIFEST.json)."""
    import duckdb
    import polars as pl

    text_dir = output_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sql = """
            SELECT
                document_id,
                storage_key,
                source,
                native_id,
                COALESCE(issuer_name, title, storage_key) AS display_name,
                issuer_name,
                title,
                doc_type,
                publication_date,
                COALESCE(source_page_url, download_url) AS filing_url,
                page_count
            FROM documents
            WHERE scope_status = 'in_scope'
            ORDER BY document_id
        """
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description]
        docs = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        parquet_rows: list[dict[str, Any]] = []
        text_files = 0
        text_bytes = 0
        by_source: dict[str, int] = {}
        slug_owners: dict[str, str] = {}
        unmapped_issuers: set[str] = set()

        for doc in docs:
            slug = slugify(doc["storage_key"])
            owner = slug_owners.setdefault(slug, doc["storage_key"])
            if owner != doc["storage_key"]:
                raise ValueError(
                    f"Slug collision: {owner!r} and {doc['storage_key']!r} both map to {slug!r}"
                )
            country = resolve_country(doc["issuer_name"])
            if doc["issuer_name"] and country["country_code"] is None:
                unmapped_issuers.add(doc["issuer_name"])
            text, text_source = _fetch_text(conn, doc["document_id"])
            by_source[doc["source"]] = by_source.get(doc["source"], 0) + 1

            pub_date = doc["publication_date"]
            if text is not None:
                toc = extract_toc(text) if text_source == "markdown" else []
                payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slug": slug,
                    "storage_key": doc["storage_key"],
                    "source": doc["source"],
                    "display_name": doc["display_name"],
                    "title": doc["title"],
                    "doc_type": doc["doc_type"],
                    "publication_date": pub_date.isoformat() if pub_date else None,
                    "country_name": country["country_name"],
                    "region": country["region"],
                    "income_group": country["income_group"],
                    "filing_url": doc["filing_url"],
                    "page_count": doc["page_count"],
                    "text_source": text_source,
                    "toc": toc,
                    "text": text,
                }
                encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
                safe_write(text_dir / f"{slug}.json", encoded, overwrite=True)
                text_files += 1
                text_bytes += len(encoded)

            parquet_rows.append(
                {
                    "slug": slug,
                    "document_id": doc["document_id"],
                    "storage_key": doc["storage_key"],
                    "source": doc["source"],
                    "native_id": doc["native_id"],
                    "display_name": doc["display_name"],
                    "issuer_name": doc["issuer_name"],
                    "title": doc["title"],
                    "doc_type": doc["doc_type"],
                    "publication_date": pub_date,
                    "country_code": country["country_code"],
                    "country_name": country["country_name"],
                    "region": country["region"],
                    "income_group": country["income_group"],
                    "lending_category": country["lending_category"],
                    "is_sovereign": country["is_sovereign"],
                    "filing_url": doc["filing_url"],
                    "page_count": doc["page_count"],
                    "has_text": text is not None,
                    "text_source": text_source,
                    "text_chars": len(text) if text is not None else 0,
                }
            )
    finally:
        conn.close()

    schema = {
        "slug": pl.Utf8,
        "document_id": pl.Int64,
        "storage_key": pl.Utf8,
        "source": pl.Utf8,
        "native_id": pl.Utf8,
        "display_name": pl.Utf8,
        "issuer_name": pl.Utf8,
        "title": pl.Utf8,
        "doc_type": pl.Utf8,
        "publication_date": pl.Date,
        "country_code": pl.Utf8,
        "country_name": pl.Utf8,
        "region": pl.Utf8,
        "income_group": pl.Utf8,
        "lending_category": pl.Utf8,
        "is_sovereign": pl.Boolean,
        "filing_url": pl.Utf8,
        "page_count": pl.Int64,
        "has_text": pl.Boolean,
        "text_source": pl.Utf8,
        "text_chars": pl.Int64,
    }
    frame = pl.DataFrame(parquet_rows, schema=schema)
    parquet_path = output_dir / "documents.parquet"
    parquet_part = parquet_path.with_suffix(".parquet.part")
    frame.write_parquet(parquet_part)
    parquet_part.replace(parquet_path)

    # Full builds own the text dir: drop files for slugs no longer in the
    # corpus so a synced snapshot can't serve deleted documents. Partial
    # (--limit) builds skip this, since most slugs are legitimately absent.
    stale_removed = 0
    if limit is None:
        current_slugs = set(slug_owners)
        for stale in text_dir.glob("*.json"):
            if stale.stem not in current_slugs:
                stale.unlink()
                stale_removed += 1

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": date.today().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "document_count": len(parquet_rows),
        "text_file_count": text_files,
        "documents_by_source": dict(sorted(by_source.items())),
        "unmapped_issuers": sorted(unmapped_issuers),
        "stale_text_files_removed": stale_removed,
        "components": {
            "documents_parquet_bytes": parquet_path.stat().st_size,
            "text_bytes": text_bytes,
            "text_files": text_files,
        },
    }
    encoded_manifest = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    safe_write(output_dir / "MANIFEST.json", encoded_manifest, overwrite=True)
    return manifest
