"""Generate the committed explorer-web test fixture from a real snapshot.

Selects a small covering set of documents that exercises every pathological
shape the explorer must handle, writes a snappy parquet with DuckDB (same
writer as the real snapshot builder, so the type layout matches exactly),
copies the matching text JSONs, and writes a consistent MANIFEST.json.

Run from the repo root:
    uv run python explorer-web/scripts/make_fixture.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshot"
FIXTURE_DIR = REPO_ROOT / "explorer-web" / "tests" / "fixtures" / "snapshot"
MAX_FIXTURE_BYTES = 3_000_000

# shape name -> SQL predicate over the snapshot parquet. Small text_bytes
# preferred so the committed fixture stays tiny.
SHAPE_PREDICATES = {
    "pages_sourced": "text_source = 'pages'",
    "no_text": "has_text = false AND no_text_reason IS NOT NULL",
    "null_publication_date": "publication_date IS NULL",
    "unknown_country": "country_name = 'Unknown'",
    "not_sovereign": "is_sovereign = false",
    "null_sovereign": "is_sovereign IS NULL",
    "high_income": "income_group = 'High income'",
}


def markdown_doc_with_toc(con: duckdb.DuckDBPyConnection, parquet: Path) -> str:
    """toc lives only in the text JSON, so inspect candidates on disk."""
    candidates = con.execute(
        f"""
        SELECT slug FROM read_parquet('{parquet}')
        WHERE text_source = 'markdown' AND has_text AND text_bytes < 200_000
        ORDER BY text_bytes ASC LIMIT 200
        """
    ).fetchall()
    for (slug,) in candidates:
        text_path = SNAPSHOT_DIR / "text" / f"{slug}.json"
        if not text_path.exists():
            continue
        with open(text_path) as f:
            doc = json.load(f)
        if doc.get("toc"):
            return str(slug)
    print("ERROR: no small markdown doc with non-empty toc found", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parquet = SNAPSHOT_DIR / "documents.parquet"
    if not parquet.exists():
        print(f"ERROR: {parquet} not found", file=sys.stderr)
        sys.exit(1)

    con = duckdb.connect()
    slugs: dict[str, list[str]] = {}
    for shape, predicate in SHAPE_PREDICATES.items():
        rows = con.execute(
            f"""
            SELECT slug FROM read_parquet('{parquet}')
            WHERE {predicate}
            ORDER BY coalesce(text_bytes, 0) ASC, slug ASC LIMIT 3
            """
        ).fetchall()
        slugs[shape] = [str(r[0]) for r in rows]

    slugs["markdown_with_toc"] = [markdown_doc_with_toc(con, parquet)]

    missing = [shape for shape, found in slugs.items() if not found]
    if missing:
        print(f"ERROR: no rows found for shapes: {missing}", file=sys.stderr)
        sys.exit(1)

    selected = sorted({s for found in slugs.values() for s in found})
    slug_list = ", ".join(f"'{s}'" for s in selected)

    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR)
    (FIXTURE_DIR / "text").mkdir(parents=True)

    con.execute(
        f"""
        COPY (
            SELECT * FROM read_parquet('{parquet}')
            WHERE slug IN ({slug_list})
            ORDER BY slug
        ) TO '{FIXTURE_DIR / "documents.parquet"}' (FORMAT parquet, COMPRESSION snappy)
        """
    )

    rows = con.execute(
        f"""
        SELECT slug, has_text, source FROM read_parquet('{parquet}')
        WHERE slug IN ({slug_list})
        """
    ).fetchall()
    text_files = 0
    by_source: dict[str, int] = {}
    for slug, has_text, source in rows:
        by_source[source] = by_source.get(source, 0) + 1
        if has_text:
            src = SNAPSHOT_DIR / "text" / f"{slug}.json"
            if not src.exists():
                print(f"ERROR: has_text row {slug} missing text JSON", file=sys.stderr)
                sys.exit(1)
            shutil.copy(src, FIXTURE_DIR / "text" / f"{slug}.json")
            text_files += 1

    with open(SNAPSHOT_DIR / "MANIFEST.json") as f:
        real_manifest = json.load(f)
    manifest = {
        "schema_version": 1,
        "snapshot_date": real_manifest["snapshot_date"],
        "generated_at": real_manifest["generated_at"],
        "document_count": len(rows),
        "text_file_count": text_files,
        "documents_by_source": dict(sorted(by_source.items())),
        "fixture": True,
    }
    with open(FIXTURE_DIR / "MANIFEST.json", "w") as f:
        json.dump(manifest, f, indent=2)

    total = sum(p.stat().st_size for p in FIXTURE_DIR.rglob("*") if p.is_file())
    if total > MAX_FIXTURE_BYTES:
        print(f"ERROR: fixture is {total} bytes (> {MAX_FIXTURE_BYTES})", file=sys.stderr)
        sys.exit(1)

    print(f"Fixture: {len(rows)} docs, {text_files} text files, {total / 1000:.0f} KB")
    for shape, found in sorted(slugs.items()):
        print(f"  {shape}: {', '.join(found)}")


if __name__ == "__main__":
    main()
