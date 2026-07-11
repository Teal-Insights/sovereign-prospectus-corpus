"""Generate the committed explorer-web test fixture from a real snapshot.

Selects a small covering set of documents that exercises every pathological
shape the explorer must handle, writes a snappy parquet with DuckDB (same
writer as the real snapshot builder, so the type layout matches exactly),
copies the matching text JSONs, and writes a consistent MANIFEST.json.

Also emits three clearly synthetic documents (issue #88) so text-scale
pathologies are CI-reachable: an inflated-metadata row for the 5 MB
click-gate branch, an astral-character doc whose toc offsets diverge
between code points and UTF-16, and a >1M-unit doc for segmented mode.

Run from the repo root:
    uv run python explorer-web/scripts/make_fixture.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

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
        with open(text_path, encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("toc"):
            return str(slug)
    print("ERROR: no small markdown doc with non-empty toc found", file=sys.stderr)
    sys.exit(1)


def _utf16_offset(text: str, cp_offset: int) -> int:
    """Convert a code-point offset to a UTF-16 offset (mirrors snapshot.py)."""
    return cp_offset + sum(1 for ch in text[:cp_offset] if ord(ch) > 0xFFFF)


def _toc_entry(text: str, heading: str, level: int) -> dict[str, Any]:
    offset = text.index(heading)
    return {
        "level": level,
        "title": heading.lstrip("#").strip(),
        "offset": offset,
        "offset_utf16": _utf16_offset(text, offset),
    }


def _large_text() -> tuple[str, list[dict[str, Any]]]:
    """>1M UTF-16 units with 8 headings; one section exceeds 500K units."""
    line = "The issuer will pay principal and interest when due. " * 3 + "\n"
    parts: list[str] = []
    headings: list[str] = []

    def add_section(n: int, target_chars: int) -> None:
        heading = f"## Section {n}\n"
        headings.append(heading)
        parts.append(heading)
        body_lines = target_chars // len(line) + 1
        parts.append(line * body_lines)

    for n in range(1, 8):
        add_section(n, 60_000)
    add_section(8, 600_000)  # the oversized section
    parts.append(line * (100_000 // len(line)))  # tail after the last heading
    text = "".join(parts)
    toc = [_toc_entry(text, h.rstrip("\n"), 2) for h in headings]
    return text, toc


def _rich_text() -> tuple[str, list[dict[str, Any]]]:
    """Markdown-rich doc for B1 rendered mode (TEA-929): headings, a phrase
    split across bold, a GFM table, an https link, and a Docling image
    comment, with filler so a jump to the last heading scrolls. The bold-split
    phrase 'collective **action** clauses' matches a spaced query only after
    rendering strips the asterisks, exercising the active-text contract."""
    filler = "The issuer shall pay principal and interest when due. " * 20 + "\n\n"
    parts = [
        "# Rich Fixture Prospectus\n\n",
        "Front matter before the first heading is optional here.\n\n",
        "## Terms and Conditions\n\n",
        "The notes contain collective **action** clauses that bind every holder.\n\n",
        "| Series | Rate | Maturity |\n",
        "| --- | --- | --- |\n",
        "| 2031 | 4.50% | 2031-06-15 |\n",
        "| 2041 | 5.25% | 2041-06-15 |\n\n",
        "See the [official filing](https://example.org/filing) for the full terms.\n\n",
        "<!-- image -->\n\n",
        filler,
        "## Events of Default\n\n",
        "An event of default occurs if any scheduled payment is missed.\n\n",
        filler,
        # Intentionally EMPTY trailing heading: the committed fixture carries
        # it so smoke can assert empty headings are skipped in the rendered
        # TOC (council PR gate, TEA-929). It was hand-added after generation
        # and is back-ported here so regeneration keeps the coverage (TEA-989).
        "## \n",
    ]
    text = "".join(parts)
    toc = [
        _toc_entry(text, "# Rich Fixture Prospectus", 1),
        _toc_entry(text, "## Terms and Conditions", 2),
        _toc_entry(text, "## Events of Default", 2),
    ]
    return text, toc


def _seg_rich_text() -> tuple[str, list[dict[str, Any]]]:
    """>1M-unit markdown doc for per-segment rendered mode (TEA-989): a ~20K
    GFM table straddling the 500K default cut, a fenced code block straddling
    the second cut, a bold-split phrase plus a small table in segment 1, and a
    needle sentence + final heading in the last segment. Placements are
    validated against DEFAULT_SEGMENT_CONFIG by fixture-shapes.test.ts. The
    filler must stay free of '#', '|', backticks, and the needle words."""
    para = (
        "The issuer shall duly and punctually pay principal of and interest on "
        "the notes when and as the same become due and payable. " * 3
    ).strip() + "\n\n"

    parts: list[str] = [
        "# Segmented Rich Fixture\n\n",
        "## Alpha Terms\n\n",
        "The notes contain collective **action** clauses that bind every holder.\n\n",
        "| Series | Rate |\n| --- | --- |\n| 2031 | 4.50% |\n\n",
    ]

    def pad_to(target: int) -> None:
        need = target - sum(len(p) for p in parts)
        if need > 0:
            parts.append(para * (need // len(para) + 1))

    pad_to(495_000)
    tranche_rows = "\n".join(
        f"| T{i:04d} | {4 + i % 3}.{i % 100:02d}% | 20{30 + i % 20} | {'x' * 24} |"
        for i in range(400)
    )
    parts.append(
        f"| Tranche | Coupon | Maturity | Note |\n| --- | --- | --- | --- |\n{tranche_rows}\n\n"
    )
    pad_to(988_000)
    fence_body = "\n".join(f"schedule line {i}: {'y' * 40}" for i in range(300))
    parts.append(f"```\n{fence_body}\n```\n\n")
    pad_to(1_020_000)
    parts.append("## Final Provisions\n\n")
    parts.append("The quantum sovereign covenant appears here and nowhere else.\n\n")
    pad_to(1_040_000)
    text = "".join(parts)
    # Alpha Terms stays OUT of the toc on purpose: a toc offset that close to
    # the start would become a section boundary and produce a tiny first
    # segment; the rendered segment still shows it as a heading.
    toc = [
        _toc_entry(text, "# Segmented Rich Fixture", 1),
        _toc_entry(text, "## Final Provisions", 2),
    ]
    return text, toc


def _synthetic_docs() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(parquet row, text JSON) pairs. country_code stays NULL on purpose:
    computeFilterOptions drops null codes, keeping 'Synthetic' out of the
    baked country options on every CI-built page."""
    gate_text = "gate fixture\n" * 20
    astral_text = (
        "intro \U0001f4c4 emoji front matter\n\n## Heading A\nbody a\n\n## Heading B\nbody b\n"
    )
    astral_toc = [
        _toc_entry(astral_text, "## Heading A", 2),
        _toc_entry(astral_text, "## Heading B", 2),
    ]
    large_text, large_toc = _large_text()
    rich_text, rich_toc = _rich_text()
    seg_rich_text, seg_rich_toc = _seg_rich_text()

    def row(slug: str, title: str, text: str, text_bytes: int | None = None) -> dict[str, Any]:
        return {
            "slug": slug,
            "source": "synthetic",
            "display_name": title,
            "title": title,
            "doc_type": "SYNTHETIC FIXTURE",
            "country_name": "Synthetic",
            "region": "Unknown",
            "income_group": "Unknown",
            "has_text": True,
            "text_source": "markdown",
            "text_chars": len(text),
            "text_bytes": text_bytes if text_bytes is not None else len(text.encode("utf-8")),
        }

    def text_json(slug: str, title: str, text: str, toc: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "slug": slug,
            "storage_key": None,
            "source": "synthetic",
            "display_name": title,
            "title": title,
            "doc_type": "SYNTHETIC FIXTURE",
            "publication_date": None,
            "country_name": "Synthetic",
            "region": "Unknown",
            "income_group": "Unknown",
            "filing_url": None,
            "page_count": None,
            "text_source": "markdown",
            "text": text,
            "toc": toc,
            "pages": [],
        }

    return [
        (
            # text_bytes deliberately inflated: the click-gate reads only the
            # metadata, so the branch is testable with a tiny real file.
            row("synthetic-gate", "Synthetic Gate Fixture", gate_text, text_bytes=6_000_000),
            text_json("synthetic-gate", "Synthetic Gate Fixture", gate_text, []),
        ),
        (
            row("synthetic-astral", "Synthetic Astral Fixture", astral_text),
            text_json("synthetic-astral", "Synthetic Astral Fixture", astral_text, astral_toc),
        ),
        (
            row("synthetic-large", "Synthetic Segment Fixture", large_text),
            text_json("synthetic-large", "Synthetic Segment Fixture", large_text, large_toc),
        ),
        (
            row("synthetic-rich", "Synthetic Rich Fixture", rich_text),
            text_json("synthetic-rich", "Synthetic Rich Fixture", rich_text, rich_toc),
        ),
        (
            row("synthetic-seg-rich", "Synthetic Segmented Rich Fixture", seg_rich_text),
            text_json(
                "synthetic-seg-rich",
                "Synthetic Segmented Rich Fixture",
                seg_rich_text,
                seg_rich_toc,
            ),
        ),
    ]


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

    # Schema-cloned temp table pins column types exactly (a hand-declared
    # table would widen e.g. text_bytes to BIGINT, which hyparquet then
    # reads back as BigInt and breaks the JS consumers).
    synthetics = _synthetic_docs()
    con.execute(f"CREATE TEMP TABLE synth AS SELECT * FROM read_parquet('{parquet}') WHERE false")
    for row, _ in synthetics:
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        con.execute(f"INSERT INTO synth ({cols}) VALUES ({placeholders})", list(row.values()))

    fixture_parquet = FIXTURE_DIR / "documents.parquet"
    con.execute(
        f"""
        COPY (
            SELECT * FROM read_parquet('{parquet}')
            WHERE slug IN ({slug_list})
            UNION ALL
            SELECT * FROM synth
            ORDER BY slug
        ) TO '{fixture_parquet}' (FORMAT parquet, COMPRESSION snappy)
        """
    )

    rows = con.execute(
        f"""
        SELECT slug, has_text, source FROM read_parquet('{fixture_parquet}')
        """
    ).fetchall()
    synthetic_texts = {slug: doc for (row, doc) in synthetics for slug in [row["slug"]]}
    text_files = 0
    by_source: dict[str, int] = {}
    for slug, has_text, source in rows:
        by_source[source] = by_source.get(source, 0) + 1
        if not has_text:
            continue
        if slug in synthetic_texts:
            with open(FIXTURE_DIR / "text" / f"{slug}.json", "w", encoding="utf-8") as f:
                json.dump(synthetic_texts[slug], f, ensure_ascii=False)
        else:
            src = SNAPSHOT_DIR / "text" / f"{slug}.json"
            if not src.exists():
                print(f"ERROR: has_text row {slug} missing text JSON", file=sys.stderr)
                sys.exit(1)
            shutil.copy(src, FIXTURE_DIR / "text" / f"{slug}.json")
        text_files += 1

    with open(SNAPSHOT_DIR / "MANIFEST.json", encoding="utf-8") as f:
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
    with open(FIXTURE_DIR / "MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    total = sum(p.stat().st_size for p in FIXTURE_DIR.rglob("*") if p.is_file())
    if total > MAX_FIXTURE_BYTES:
        print(f"ERROR: fixture is {total} bytes (> {MAX_FIXTURE_BYTES})", file=sys.stderr)
        sys.exit(1)

    print(f"Fixture: {len(rows)} docs, {text_files} text files, {total / 1000:.0f} KB")
    for shape, found in sorted(slugs.items()):
        print(f"  {shape}: {', '.join(found)}")
    print(f"  synthetic: {', '.join(sorted(synthetic_texts))}")


if __name__ == "__main__":
    main()
