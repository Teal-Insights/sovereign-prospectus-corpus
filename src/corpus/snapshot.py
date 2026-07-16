"""Build the static snapshot consumed by the web explorer.

Reads corpus.duckdb (read-only) and writes three components:

- ``documents.parquet`` — one row per document with the metadata the
  explorer displays (issuer, country, region, income group, source,
  date, type, original-filing URL) plus a stable URL slug.
- ``text/<slug>.json`` — per-document full text plus table-of-contents
  structure derived from markdown headings. Plain JSON, gzip-friendly.
- ``MANIFEST.json`` — snapshot date, document counts, schema version,
  and component sizes. Written last: its presence marks a complete
  build, so it is removed at build start and a directory without it
  must be treated as torn and not deployed.

The snapshot is a read-only consumer of the pipeline database
(architecture decision 4: modular output layer).
"""

from __future__ import annotations

import bisect
import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypedDict

from corpus.io.safe_write import safe_write
from corpus.reference.issuer_country_map import ISSUER_TO_COUNTRY
from corpus.reference.wb_classifications import WORLD_BANK_CLASSIFICATIONS

if TYPE_CHECKING:
    from pathlib import Path

    import duckdb

# Bump for breaking consumer-visible shape changes. Additive nullable fields
# remain within v1 so the prior static app can read a candidate snapshot during
# a pointer-last rolling release.
SCHEMA_VERSION = 1

_SLUG_RE = re.compile(r"[^a-z0-9]+")
# h2-h3 covers Docling output (all sections are h2); the EDGAR HTML parser
# emits h5 for section headings, so capture through h5 with true levels.
# [ \t] (not \s) so a bare "##" line can't swallow its newline and turn
# the next line into a bogus heading title.
_HEADING_RE = re.compile(r"^(#{2,5})[ \t]+(.+)$", re.MULTILINE)
_ASTRAL_RE = re.compile(r"[\U00010000-\U0010FFFF]")

_LUXSE_VENEZUELA_RAW_TITLE = "Suspension - JHO - THE BOLIVIAN REPUBLIC OF VENEZUELA - 17.09.2014"
_LUXSE_VENEZUELA_CORRECTED_TITLE = (
    "Suspension - JHO - THE BOLIVARIAN REPUBLIC OF VENEZUELA - 17.09.2014"
)
_SNAPSHOT_TITLE_NORMALIZATIONS = {
    "luxse__2175370": (_LUXSE_VENEZUELA_RAW_TITLE, _LUXSE_VENEZUELA_CORRECTED_TITLE),
    "luxse__2176190": (_LUXSE_VENEZUELA_RAW_TITLE, _LUXSE_VENEZUELA_CORRECTED_TITLE),
}

# ToC quality gates: CID-font extraction garbage produces mojibake
# headings and pathological counts (worst corpus doc: 9,269 entries).
_TOC_MAX_ENTRIES = 2000
_TOC_MAX_TITLE_CHARS = 200
_TOC_MIN_ALNUM_FRACTION = 0.5


class TocEntry(TypedDict):
    level: int
    title: str
    offset: int
    offset_utf16: int


class PageOffset(TypedDict):
    page_number: int
    offset: int


class CountryMeta(TypedDict):
    country_code: str | None
    country_name: str
    is_sovereign: bool | None
    region: str
    income_group: str
    lending_category: str | None


class SnapshotComponents(TypedDict):
    documents_parquet_bytes: int
    text_bytes: int
    text_files: int


class SnapshotManifest(TypedDict):
    schema_version: int
    snapshot_date: str
    generated_at: str
    document_count: int
    text_file_count: int
    documents_by_source: dict[str, int]
    unmapped_issuers: list[str]
    sovereign_flag_conflicts: list[str]
    stale_text_files_removed: int
    components: SnapshotComponents


def slugify(storage_key: str) -> str:
    """Stable URL slug from a storage key (``nsm__123`` → ``nsm-123``)."""
    return _SLUG_RE.sub("-", storage_key.lower()).strip("-")


def _title_is_legible(title: str) -> bool:
    """Reject mojibake ToC titles from broken CID-font extraction."""
    if not title or len(title) > _TOC_MAX_TITLE_CHARS:
        return False
    legible = sum(1 for c in title if c.isalnum() or c.isspace())
    return legible / len(title) >= _TOC_MIN_ALNUM_FRACTION


def extract_toc(markdown_text: str) -> list[TocEntry]:
    """Extract ``##`` through ``#####`` headings with char offsets.

    Offsets are Unicode code point indices; ``offset_utf16`` carries the
    UTF-16 code unit equivalent for JavaScript consumers. Known limits:
    headings inside fenced code blocks are not excluded (none exist in
    the current corpus), h6 headings are ignored, and entries are capped
    at _TOC_MAX_ENTRIES after mojibake filtering.
    """
    astral_offsets = [m.start() for m in _ASTRAL_RE.finditer(markdown_text)]
    entries: list[TocEntry] = []
    for match in _HEADING_RE.finditer(markdown_text):
        title = match.group(2).strip()
        if not _title_is_legible(title):
            continue
        offset = match.start()
        entries.append(
            {
                "level": len(match.group(1)),
                "title": title,
                "offset": offset,
                # Each astral code point occupies two UTF-16 code units
                "offset_utf16": offset + bisect.bisect_left(astral_offsets, offset),
            }
        )
        if len(entries) >= _TOC_MAX_ENTRIES:
            break
    return entries


def resolve_country(issuer_name: str | None) -> CountryMeta:
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


def _display_name(issuer_name: str | None, title: str | None, storage_key: str) -> str:
    """Issuer name as filed, lightly normalized for display only.

    Collapses whitespace and strips trailing separators (one NSM issuer
    is stored as 'National Investment Fund ...;'). Never applied to
    document text, which stays verbatim.
    """
    raw = issuer_name or title or storage_key
    return " ".join(raw.split()).rstrip(";,")


def _snapshot_title(storage_key: str, raw_title: str | None) -> str | None:
    """Correct verified source-title typos only in the derived snapshot.

    The database and source manifests retain ``raw_title`` verbatim as
    provenance. A changed source title for a listed key fails closed so this
    narrow exception cannot silently rewrite different future metadata.
    """
    normalization = _SNAPSHOT_TITLE_NORMALIZATIONS.get(storage_key)
    if normalization is None:
        return raw_title
    expected_raw, corrected = normalization
    if raw_title != expected_raw:
        raise ValueError(
            f"Snapshot title normalization precondition failed for {storage_key}: "
            f"expected {expected_raw!r}, found {raw_title!r}"
        )
    return corrected


def _fetch_text(
    conn: duckdb.DuckDBPyConnection, document_id: int
) -> tuple[str | None, str | None, list[PageOffset]]:
    """Return (text, text_source, page_offsets) for a document.

    Prefers the full markdown (no page anchors available); falls back to
    concatenated page text with exact page-boundary offsets so consumers
    can cite pages.
    """
    row = conn.execute(
        "SELECT markdown_text FROM document_markdown WHERE document_id = ?",
        [document_id],
    ).fetchone()
    if row is not None and row[0] and row[0].strip():
        return row[0], "markdown", []

    pages = conn.execute(
        "SELECT page_number, page_text FROM document_pages "
        "WHERE document_id = ? ORDER BY page_number",
        [document_id],
    ).fetchall()
    if pages:
        parts: list[str] = []
        offsets: list[PageOffset] = []
        position = 0
        for page_number, page_text in pages:
            text_part = page_text or ""
            offsets.append({"page_number": page_number, "offset": position})
            parts.append(text_part)
            position += len(text_part) + 2  # separator below
        text = "\n\n".join(parts)
        if text.strip():
            return text, "pages", offsets
    return None, None, []


def _no_text_reason(file_path: str | None) -> str:
    """Why a document has no text (for explorer messaging)."""
    if file_path and file_path.endswith(".paper"):
        return "paper_filing"  # EDGAR paper-filing placeholder, no e-doc
    return "not_parsed"


def build_snapshot(
    db_path: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
) -> SnapshotManifest:
    """Generate the full snapshot. Returns the manifest (also on disk)."""
    import duckdb
    import polars as pl

    text_dir = output_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    # Remove the completion marker first: a dir without MANIFEST.json is
    # a torn build and must not be deployed
    (output_dir / "MANIFEST.json").unlink(missing_ok=True)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        sql = """
            SELECT
                document_id,
                storage_key,
                source,
                native_id,
                issuer_name,
                title,
                doc_type,
                publication_date,
                COALESCE(source_page_url, download_url) AS filing_url,
                page_count,
                is_sovereign AS db_is_sovereign,
                file_path
            FROM documents
            WHERE scope_status = 'in_scope'
            ORDER BY document_id
        """
        params: list[Any] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        cursor = conn.execute(sql, params)
        columns = [d[0] for d in cursor.description]
        docs = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

        parquet_rows: list[dict[str, Any]] = []
        text_files = 0
        text_bytes_total = 0
        by_source: dict[str, int] = {}
        slug_owners: dict[str, str] = {}
        unmapped_issuers: set[str] = set()
        flag_conflicts: set[str] = set()

        for doc in docs:
            slug = slugify(doc["storage_key"])
            source_only = slugify(doc["source"])
            if not slug or slug == source_only:
                raise ValueError(
                    f"Degenerate slug {slug!r} from storage_key {doc['storage_key']!r}: "
                    "the native id contributed no slug characters"
                )
            owner = slug_owners.setdefault(slug, doc["storage_key"])
            if owner != doc["storage_key"]:
                raise ValueError(
                    f"Slug collision: {owner!r} and {doc['storage_key']!r} both map to {slug!r}"
                )
            country = resolve_country(doc["issuer_name"])
            if doc["issuer_name"]:
                if country["country_code"] is None:
                    unmapped_issuers.add(doc["issuer_name"])
                elif (
                    doc["db_is_sovereign"] is not None
                    and country["is_sovereign"] is not None
                    and doc["db_is_sovereign"] != country["is_sovereign"]
                ):
                    flag_conflicts.add(doc["issuer_name"])
            text, text_source, page_offsets = _fetch_text(conn, doc["document_id"])
            by_source[doc["source"]] = by_source.get(doc["source"], 0) + 1
            snapshot_title = _snapshot_title(doc["storage_key"], doc["title"])
            raw_title = doc["title"] if snapshot_title != doc["title"] else None
            display_name = _display_name(doc["issuer_name"], snapshot_title, doc["storage_key"])

            pub_date = doc["publication_date"]
            doc_text_bytes = 0
            if text is not None:
                toc = extract_toc(text) if text_source == "markdown" else []
                payload = {
                    "schema_version": SCHEMA_VERSION,
                    "slug": slug,
                    "storage_key": doc["storage_key"],
                    "source": doc["source"],
                    "display_name": display_name,
                    "title": snapshot_title,
                    "raw_title": raw_title,
                    "doc_type": doc["doc_type"],
                    "publication_date": pub_date.isoformat() if pub_date else None,
                    "country_name": country["country_name"],
                    "region": country["region"],
                    "income_group": country["income_group"],
                    "filing_url": doc["filing_url"],
                    "page_count": doc["page_count"],
                    "text_source": text_source,
                    "toc": toc,
                    "pages": page_offsets,
                    "text": text,
                }
                encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
                safe_write(text_dir / f"{slug}.json", encoded, overwrite=True)
                text_files += 1
                doc_text_bytes = len(encoded)
                text_bytes_total += doc_text_bytes

            parquet_rows.append(
                {
                    "slug": slug,
                    "document_id": doc["document_id"],
                    "storage_key": doc["storage_key"],
                    "source": doc["source"],
                    "native_id": doc["native_id"],
                    "display_name": display_name,
                    "issuer_name": doc["issuer_name"],
                    "title": snapshot_title,
                    "raw_title": raw_title,
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
                    "text_bytes": doc_text_bytes,
                    "no_text_reason": None
                    if text is not None
                    else _no_text_reason(doc["file_path"]),
                }
            )
    finally:
        conn.close()

    # Int32 (not Int64) for JS parquet readers: Int64 decodes to BigInt.
    # Snappy (not zstd): supported by hyparquet without an add-on.
    schema = {
        "slug": pl.Utf8,
        "document_id": pl.Int32,
        "storage_key": pl.Utf8,
        "source": pl.Utf8,
        "native_id": pl.Utf8,
        "display_name": pl.Utf8,
        "issuer_name": pl.Utf8,
        "title": pl.Utf8,
        "raw_title": pl.Utf8,
        "doc_type": pl.Utf8,
        "publication_date": pl.Date,
        "country_code": pl.Utf8,
        "country_name": pl.Utf8,
        "region": pl.Utf8,
        "income_group": pl.Utf8,
        "lending_category": pl.Utf8,
        "is_sovereign": pl.Boolean,
        "filing_url": pl.Utf8,
        "page_count": pl.Int32,
        "has_text": pl.Boolean,
        "text_source": pl.Utf8,
        "text_chars": pl.Int32,
        "text_bytes": pl.Int32,
        "no_text_reason": pl.Utf8,
    }
    frame = pl.DataFrame(parquet_rows, schema=schema)
    parquet_path = output_dir / "documents.parquet"
    parquet_part = parquet_path.with_suffix(".parquet.part")
    try:
        frame.write_parquet(parquet_part, compression="snappy")
        parquet_part.replace(parquet_path)
    except Exception:
        parquet_part.unlink(missing_ok=True)
        raise

    # Full builds own the text dir: drop files for slugs no longer in the
    # corpus so a synced snapshot can't serve deleted documents, and any
    # .part orphans from hard kills. Partial (--limit) builds skip the
    # slug sweep, since most slugs are legitimately absent.
    stale_removed = 0
    for orphan in text_dir.glob("*.part"):
        orphan.unlink()
    if limit is None:
        current_slugs = set(slug_owners)
        for stale in text_dir.glob("*.json"):
            if stale.stem not in current_slugs:
                stale.unlink()
                stale_removed += 1

    now = datetime.now(UTC)
    manifest: SnapshotManifest = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_date": now.date().isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "document_count": len(parquet_rows),
        "text_file_count": text_files,
        "documents_by_source": dict(sorted(by_source.items())),
        "unmapped_issuers": sorted(unmapped_issuers),
        "sovereign_flag_conflicts": sorted(flag_conflicts),
        "stale_text_files_removed": stale_removed,
        "components": {
            "documents_parquet_bytes": parquet_path.stat().st_size,
            "text_bytes": text_bytes_total,
            "text_files": text_files,
        },
    }
    encoded_manifest = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    safe_write(output_dir / "MANIFEST.json", encoded_manifest, overwrite=True)
    return manifest
