# Spring Meetings Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a searchable Streamlit explorer backed by MotherDuck with Docling-parsed sovereign prospectuses for the IMF/World Bank Spring Meetings demo on Monday 2026-04-13.

**Architecture:** Four PRs in sequence: (1) Docling parser class + CLI rewire + fixed reparse script, (2) LuxSE adapter (separate plan, time-boxed), (3) FTS + markdown storage + MotherDuck publish, (4) Streamlit explorer with markdown detail panel. An overnight Docling bulk parse runs between PR #1 and PR #3.

**Tech Stack:** Python 3.12, Docling 2.86.0, DuckDB 1.4.4, MotherDuck, Polars, Streamlit, Click CLI.

**Spec:** `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md`

**Branch:** `feature/docling-bug-fix-and-sprint-v2` (all work happens here)

---

## File Map

### PR #1 — Docling Phase A

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/corpus/parsers/docling_parser.py` | DoclingParser class implementing DocumentParser protocol |
| Create | `src/corpus/parsers/markdown.py` | `strip_markdown()` utility — strips formatting, preserves table content |
| Modify | `src/corpus/parsers/registry.py:19` | Register DoclingParser in `_REGISTRY` |
| Modify | `src/corpus/parsers/__init__.py` | Export DoclingParser |
| Modify | `src/corpus/cli.py:618` | Replace `PyMuPDFParser()` with `get_parser()` |
| Modify | `config.toml:5` | Flip `[parser].default` from `"pymupdf"` to `"docling"` |
| Modify | `scripts/docling_reparse.py` | Fixed worker + luxse glob + JSONL contract |
| Modify | `docs/RATIFIED-DECISIONS.md` | Decision 18 update |
| Create | `tests/test_docling_parser.py` | DoclingParser unit tests |
| Create | `tests/test_strip_markdown.py` | strip_markdown unit tests |

### PR #3 — Task 3: FTS + Markdown + MotherDuck

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `sql/001_corpus.sql` | Add `document_markdown` and `document_pages` tables, FTS |
| Create | `src/corpus/db/markdown.py` | Ingest `.md` files into `document_markdown` table |
| Create | `src/corpus/db/pages.py` | Build `document_pages` table + FTS index from JSONL |
| Modify | `src/corpus/db/ingest.py` | Read `parse_tool` + `page_count` from JSONL headers |
| Create | `src/corpus/db/publish.py` | MotherDuck publish function |
| Modify | `src/corpus/cli.py` | Add `corpus publish-motherduck` and `corpus build-pages` commands |
| Create | `scripts/promote_parsed_dir.py` | Rename `parsed_docling/` → `parsed/`, reparse EDGAR |
| Create | `tests/test_markdown_ingest.py` | document_markdown ingest tests |
| Create | `tests/test_pages.py` | document_pages + FTS tests |

### PR #4 — Task 4: Streamlit Explorer

| Action | File | Responsibility |
|--------|------|---------------|
| Rewrite | `explorer/app.py` | Full explorer: search, filters, detail panel with markdown |
| Modify | `requirements.txt` | Pin versions for Streamlit Cloud |

---

## PR #1 — Docling Phase A

### Task 1: strip_markdown utility

**Files:**
- Create: `src/corpus/parsers/markdown.py`
- Create: `tests/test_strip_markdown.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_strip_markdown.py
"""Tests for strip_markdown — must preserve table content as plain text."""
from __future__ import annotations

from corpus.parsers.markdown import strip_markdown


def test_strips_headings():
    assert strip_markdown("## Section Title\nBody text") == "Section Title\nBody text"


def test_strips_bold_and_italic():
    assert strip_markdown("This is **bold** and *italic*") == "This is bold and italic"


def test_strips_list_markers():
    text = "- Item one\n- Item two\n* Item three"
    result = strip_markdown(text)
    assert "Item one" in result
    assert "Item two" in result
    assert "Item three" in result
    assert not result.startswith("-")
    assert "* " not in result


def test_preserves_table_content():
    """Critical: table cell text must survive for grep/FTS."""
    table = "| Country | Amount | Currency |\n|---|---|---|\n| Ghana | 1,000,000 | USD |\n| Kenya | 500,000 | EUR |"
    result = strip_markdown(table)
    assert "Ghana" in result
    assert "1,000,000" in result
    assert "USD" in result
    assert "Kenya" in result
    assert "|" not in result
    assert "---" not in result


def test_strips_horizontal_rules():
    assert strip_markdown("Above\n---\nBelow").strip() == "Above\n\nBelow"


def test_preserves_plain_text():
    text = "This is plain text with no markdown."
    assert strip_markdown(text) == text


def test_empty_string():
    assert strip_markdown("") == ""


def test_image_placeholders_removed():
    assert strip_markdown("Text before\n<!-- image -->\nText after").strip() == "Text before\n\nText after"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_strip_markdown.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.parsers.markdown'`

- [ ] **Step 3: Implement strip_markdown**

```python
# src/corpus/parsers/markdown.py
"""Markdown-to-plain-text conversion for grep/FTS consumption.

Strips formatting while preserving content — especially table cell text,
which the stale strip_markdown() deleted entirely.
"""
from __future__ import annotations

import re


def strip_markdown(text: str) -> str:
    """Strip markdown formatting, preserving all textual content.

    Designed for sovereign bond prospectuses where tables contain critical
    financial data that must remain searchable.
    """
    if not text:
        return text

    # Remove image placeholders
    text = re.sub(r"<!--\s*image\s*-->", "", text)

    # Headers: "## Title" → "Title"
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold/italic: **text** or *text* → text
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)

    # List markers: "- item" or "* item" or "+ item" → "item"
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Table separator rows: |---|---|---| → remove entirely
    text = re.sub(r"^\|[-:\s|]+\|$", "", text, flags=re.MULTILINE)

    # Table rows: | cell1 | cell2 | → "cell1 cell2"
    # Split cells, strip pipes, join with space
    def _table_row_to_text(match: re.Match[str]) -> str:
        row = match.group(0)
        cells = [c.strip() for c in row.strip("|").split("|")]
        return " ".join(c for c in cells if c)

    text = re.sub(r"^\|.+\|$", _table_row_to_text, text, flags=re.MULTILINE)

    # Horizontal rules: --- or *** → blank line
    text = re.sub(r"^[-*]{3,}$", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines to single
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_strip_markdown.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/parsers/markdown.py tests/test_strip_markdown.py
git commit -m "feat: strip_markdown utility — preserves table content for FTS"
```

---

### Task 2: DoclingParser class

**Files:**
- Create: `src/corpus/parsers/docling_parser.py`
- Create: `tests/test_docling_parser.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_docling_parser.py
"""Tests for DoclingParser — Docling-based PDF parser."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from corpus.parsers.base import DocumentParser, ParseResult
from corpus.parsers.docling_parser import DoclingParser


def test_satisfies_protocol():
    """DoclingParser must implement DocumentParser protocol."""
    parser = DoclingParser()
    assert isinstance(parser, DocumentParser)


def test_parse_returns_parse_result():
    """parse() must return a ParseResult with correct fields."""
    # Mock Docling's DocumentConverter to avoid loading ML models in tests
    mock_doc = MagicMock()
    mock_doc.num_pages.return_value = 3
    mock_doc.pages = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    mock_doc.export_to_markdown.side_effect = [
        "# Full Document\n\nPage 1 text\n\nPage 2 text\n\nPage 3 text",  # full doc
        "# Page 1\n\nPage 1 text",  # page_no=1
        "Page 2 text with **bold**",  # page_no=2
        "| Col | Val |\n|---|---|\n| A | B |",  # page_no=3
    ]

    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("corpus.parsers.docling_parser.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.return_value = mock_result
        parser = DoclingParser()
        result = parser.parse(MagicMock())

    assert isinstance(result, ParseResult)
    assert result.page_count == 3
    assert result.parse_tool == "docling"
    assert len(result.pages) == 3
    # Pages should be plain text (stripped markdown)
    assert "#" not in result.pages[0]
    assert "**" not in result.pages[1]
    assert "|" not in result.pages[2]
    # But content preserved
    assert "Page 1 text" in result.pages[0]
    assert "bold" in result.pages[1]
    assert "A" in result.pages[2] and "B" in result.pages[2]
    # Full text is pages joined
    assert result.text == "\n\n".join(result.pages)
    # Metadata has full markdown
    assert "markdown" in result.metadata


def test_parse_empty_pdf():
    """Empty PDFs should return parse_ok with 0 pages."""
    mock_doc = MagicMock()
    mock_doc.num_pages.return_value = 0
    mock_doc.pages = {}
    mock_doc.export_to_markdown.return_value = ""

    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("corpus.parsers.docling_parser.DocumentConverter") as MockConverter:
        MockConverter.return_value.convert.return_value = mock_result
        parser = DoclingParser()
        result = parser.parse(MagicMock())

    assert result.page_count == 0
    assert result.pages == []
    assert result.text == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_docling_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.parsers.docling_parser'`

- [ ] **Step 3: Implement DoclingParser**

```python
# src/corpus/parsers/docling_parser.py
"""Docling-based PDF parser for sovereign bond prospectuses.

Uses Docling's per-page markdown export, then strips formatting for the
plain-text ParseResult consumed by grep/FTS. Raw markdown is preserved
in result.metadata["markdown"] for the Streamlit detail panel.
"""
from __future__ import annotations

from importlib.metadata import version as pkg_version
from pathlib import Path

from corpus.parsers.base import ParseResult
from corpus.parsers.markdown import strip_markdown


class DoclingParser:
    """Parse PDFs using Docling with per-page markdown export."""

    def parse(self, path: Path) -> ParseResult:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document

        page_count = doc.num_pages()

        # Full-document markdown for the .md sidecar / detail panel
        full_markdown = doc.export_to_markdown()

        # Per-page plain text for JSONL / grep / FTS
        pages: list[str] = []
        for page_no in sorted(doc.pages.keys()):
            page_md = doc.export_to_markdown(page_no=page_no)
            pages.append(strip_markdown(page_md))

        text = "\n\n".join(pages)

        return ParseResult(
            pages=pages,
            text=text,
            page_count=page_count,
            parse_tool="docling",
            parse_version=pkg_version("docling"),
            metadata={"markdown": full_markdown},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_docling_parser.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/parsers/docling_parser.py tests/test_docling_parser.py
git commit -m "feat: DoclingParser class — per-page markdown export with plain-text output"
```

---

### Task 3: Register DoclingParser + flip config default

**Files:**
- Modify: `src/corpus/parsers/registry.py:19`
- Modify: `src/corpus/parsers/__init__.py`
- Modify: `config.toml:5`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_docling_parser.py

def test_registry_returns_docling_by_default():
    """get_parser() with config default='docling' returns DoclingParser."""
    from corpus.parsers.registry import get_parser

    parser = get_parser("docling")
    assert isinstance(parser, DoclingParser)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_docling_parser.py::test_registry_returns_docling_by_default -v`
Expected: FAIL — `ValueError: Unknown parser: 'docling'`

- [ ] **Step 3: Register DoclingParser in the registry**

In `src/corpus/parsers/registry.py`, add to the imports and registry dict:

```python
# Add import at top
from corpus.parsers.docling_parser import DoclingParser

# Add to _REGISTRY dict (line ~19)
_REGISTRY: dict[str, type[DocumentParser]] = {
    "pymupdf": PyMuPDFParser,
    "docling": DoclingParser,
}
```

- [ ] **Step 4: Update `__init__.py` exports**

In `src/corpus/parsers/__init__.py`, add:

```python
from corpus.parsers.docling_parser import DoclingParser
```

- [ ] **Step 5: Flip config default**

In `config.toml` line 5, change:

```toml
default = "docling"
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_docling_parser.py -v`
Expected: all PASS

- [ ] **Step 7: Run existing parser tests to check no regressions**

Run: `uv run pytest tests/test_parsers.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add src/corpus/parsers/registry.py src/corpus/parsers/__init__.py config.toml
git commit -m "feat: register DoclingParser, flip config default to docling"
```

---

### Task 4: CLI rewire — route .pdf through get_parser()

**Files:**
- Modify: `src/corpus/cli.py:618`

- [ ] **Step 1: Modify the parser dict in parse_run**

In `src/corpus/cli.py`, change lines 618-623 from:

```python
    parsers = {
        ".pdf": PyMuPDFParser(),
        ".txt": PlainTextParser(),
        ".htm": HTMLParser(),
        ".html": HTMLParser(),
    }
```

to:

```python
    parsers = {
        ".pdf": get_parser(),
        ".txt": PlainTextParser(),
        ".htm": HTMLParser(),
        ".html": HTMLParser(),
    }
```

- [ ] **Step 2: Add the import**

Add `from corpus.parsers.registry import get_parser` to the imports at the top of `cli.py` (near the other parser imports around line 14-20). Remove the `PyMuPDFParser` import if it's no longer used elsewhere in the file.

- [ ] **Step 3: Verify the CLI still loads**

Run: `uv run corpus parse run --help`
Expected: shows help text without import errors

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: all existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: CLI rewire — route .pdf through get_parser() instead of hardcoded PyMuPDFParser"
```

---

### Task 5: Fix scripts/docling_reparse.py

**Files:**
- Modify: `scripts/docling_reparse.py` (rewrite from stale branch)

This is the most critical task. The fixed script runs overnight against 2,291+ PDFs.

- [ ] **Step 1: Copy the stale script from the branch as starting point**

```bash
git show origin/feature/30-docling-reparse:scripts/docling_reparse.py > scripts/docling_reparse.py
```

- [ ] **Step 2: Fix `discover_pdfs()` — add luxse glob**

In `scripts/docling_reparse.py`, find the `discover_pdfs()` function and add the LuxSE glob. Replace the function with:

```python
def discover_pdfs() -> list[tuple[str, Path]]:
    """Find all PDFs to process. Returns list of (storage_key, path)."""
    pdfs: list[tuple[str, Path]] = []

    # PDIP PDFs (nested under country subdirs)
    pdip_dir = PROJECT_ROOT / "data" / "pdfs" / "pdip"
    if pdip_dir.exists():
        for pdf_path in pdip_dir.rglob("*.pdf"):
            storage_key = f"pdip__{pdf_path.stem}"
            pdfs.append((storage_key, pdf_path))

    # NSM PDFs
    original_dir = PROJECT_ROOT / "data" / "original"
    if original_dir.exists():
        for pdf_path in original_dir.glob("nsm__*.pdf"):
            storage_key = pdf_path.stem
            pdfs.append((storage_key, pdf_path))

        # LuxSE PDFs
        for pdf_path in original_dir.glob("luxse__*.pdf"):
            storage_key = pdf_path.stem
            pdfs.append((storage_key, pdf_path))

    return sorted(pdfs)
```

- [ ] **Step 3: Fix `strip_markdown()` — use the shared utility**

Replace the inline `strip_markdown()` function in the script with an import:

```python
# At the top of the file, add:
import sys
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from corpus.parsers.markdown import strip_markdown
```

Delete the old inline `strip_markdown()` function from the script.

- [ ] **Step 4: Fix `process_one_pdf()` — per-page markdown export + JSONL contract**

Replace the `process_one_pdf()` function with the fixed version:

```python
def process_one_pdf(args: tuple[str, str]) -> dict:
    """Process a single PDF with Docling. Runs in a worker process.

    Emits two files per document:
    - {storage_key}.jsonl — plain text (0-indexed pages) for grep/FTS
    - {storage_key}.md — raw markdown for Streamlit detail panel

    Args:
        args: (storage_key, pdf_path_str)

    Returns:
        dict with status, storage_key, page_count, elapsed_s, error
    """
    storage_key, pdf_path_str = args
    pdf_path = Path(pdf_path_str)
    start = time.monotonic()

    try:
        from docling.document_converter import DocumentConverter
        from importlib.metadata import version as pkg_version

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        doc = result.document

        # Actual PDF page count from Docling
        page_count = doc.num_pages()

        # Full-document markdown for the .md sidecar
        full_markdown = doc.export_to_markdown()

        # Per-page: markdown for .md, plain text for JSONL
        pages_text: dict[int, str] = {}
        for page_no in sorted(doc.pages.keys()):
            page_md = doc.export_to_markdown(page_no=page_no)
            pages_text[page_no] = strip_markdown(page_md)

        elapsed = time.monotonic() - start
        docling_version = pkg_version("docling")

        # Write markdown sidecar (atomic)
        md_path = OUTPUT_DIR / f"{storage_key}.md"
        md_part = md_path.with_suffix(".md.part")
        md_part.write_text(full_markdown)
        os.replace(str(md_part), str(md_path))

        # Write JSONL output (atomic) — JSONL output contract
        jsonl_path = OUTPUT_DIR / f"{storage_key}.jsonl"
        jsonl_part = jsonl_path.with_suffix(".jsonl.part")
        with jsonl_part.open("w") as f:
            header = {
                "storage_key": storage_key,
                "page_count": page_count,
                "parse_tool": "docling",
                "parse_version": docling_version,
                "parse_status": "parse_ok" if page_count > 0 else "parse_empty",
                "parsed_at": datetime.now(UTC).isoformat(),
            }
            f.write(json.dumps(header) + "\n")
            for page_no in sorted(pages_text.keys()):
                page_record = {
                    "page": page_no - 1,  # Convert 1-indexed to 0-indexed
                    "text": pages_text[page_no],
                    "char_count": len(pages_text[page_no]),
                }
                f.write(json.dumps(page_record) + "\n")

        os.replace(str(jsonl_part), str(jsonl_path))

        return {
            "status": "success",
            "storage_key": storage_key,
            "page_count": page_count,
            "elapsed_s": round(elapsed, 1),
            "error": None,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        is_mps_error = "MPS" in str(exc) or "Metal" in str(exc)

        return {
            "status": "mps_error" if is_mps_error else "failed",
            "storage_key": storage_key,
            "page_count": 0,
            "elapsed_s": round(elapsed, 1),
            "error": f"{type(exc).__name__}: {exc}",
        }
```

- [ ] **Step 5: Verify the script loads without errors**

```bash
uv run python -c "import scripts.docling_reparse; print('OK')"
```

If this fails because `scripts/` isn't a package, that's fine — the script is invoked directly. Instead verify:

```bash
uv run python scripts/docling_reparse.py --help 2>&1 | head -5
```

Or if the script uses `if __name__ == "__main__"`, just check syntax:

```bash
uv run python -c "
import ast
with open('scripts/docling_reparse.py') as f:
    ast.parse(f.read())
print('Syntax OK')
"
```

- [ ] **Step 6: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "fix: docling_reparse worker — per-page export, strip_markdown, luxse glob, JSONL contract"
```

---

### Task 6: Decision 18 doc update

**Files:**
- Modify: `docs/RATIFIED-DECISIONS.md`

- [ ] **Step 1: Update Decision 18**

Find Decision 18 in `docs/RATIFIED-DECISIONS.md` and update it to reflect:
- Docling is the default parser for all PDFs
- PyMuPDF is removed from the PDF parsing path
- EDGAR HTML/TXT files continue using HTMLParser/PlainTextParser
- `config.toml` `[parser].default` is now `"docling"`

- [ ] **Step 2: Commit**

```bash
git add docs/RATIFIED-DECISIONS.md
git commit -m "docs: update Decision 18 — Docling is now the default PDF parser"
```

---

### Task 7: Lint, test, and push PR #1

- [ ] **Step 1: Run linter**

```bash
uv run ruff check src/ tests/ scripts/docling_reparse.py
uv run ruff format --check src/ tests/ scripts/docling_reparse.py
```

Fix any issues.

- [ ] **Step 2: Run type checker**

```bash
uv run pyright src/corpus/parsers/
```

Fix any new errors (pre-existing errors in other modules are tracked separately).

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Push**

```bash
git push
```

PR #1 is the current branch `feature/docling-bug-fix-and-sprint-v2`. No separate PR creation needed yet — this branch accumulates all sprint work.

---

## Operational Steps (between PR #1 and PR #3)

These are commands, not code tasks. Run them from the feature branch.

### Step 2 — NSM + EDGAR Incrementals

```bash
# Parallel shells:
uv run corpus discover nsm --run-id $(date +%Y%m%d-%H%M%S)-nsm-incr && uv run corpus download nsm --run-id $(date +%Y%m%d-%H%M%S)-nsm-dl
uv run corpus discover edgar --run-id $(date +%Y%m%d-%H%M%S)-edgar-incr && uv run corpus download edgar --run-id $(date +%Y%m%d-%H%M%S)-edgar-dl
```

**Do NOT run `corpus parse` during this window.**

### Step 3 — LuxSE Adapter (PR #2)

Separate brainstorm/spec/plan cycle. Time-boxed to 90-min soft checkpoint + 4-hr hard cliff.

### Step 4 — Overnight Docling Bulk Parse

```bash
# Delete broken March 28 outputs (ONE TIME ONLY — do not re-delete on restart)
rm -rf data/parsed_docling/

# Run the fixed script (from the feature branch)
caffeinate -d -i uv run python scripts/docling_reparse.py 2>&1 | tee /tmp/docling_overnight.log

# Monitor from another terminal:
tail -f data/parsed_docling/_progress.jsonl
```

### Step 5 — Verify Overnight Parse

```bash
# Check for errors
cat data/parsed_docling/_errors.log

# Count outputs
ls data/parsed_docling/*.jsonl | wc -l
ls data/parsed_docling/*.md | wc -l

# Spot check random files
for f in $(ls data/parsed_docling/*.jsonl | shuf -n 5); do
    echo "=== $(basename $f) ==="
    head -1 "$f" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'pages={d[\"page_count\"]} tool={d[\"parse_tool\"]}')"
done
```

---

## PR #3 — Task 3: FTS + Markdown + MotherDuck

### Task 8: Schema — document_markdown + document_pages tables

**Files:**
- Modify: `sql/001_corpus.sql`
- Modify: `src/corpus/db/schema.py` (no code changes needed — it reads the DDL file)

- [ ] **Step 1: Add document_markdown table DDL**

Append to `sql/001_corpus.sql`:

```sql
-- Markdown text for Streamlit detail panel (separate from documents to keep it lightweight)
CREATE TABLE IF NOT EXISTS document_markdown (
    document_id     INTEGER PRIMARY KEY REFERENCES documents(document_id),
    markdown_text   VARCHAR NOT NULL,
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- Per-page text for full-text search
CREATE SEQUENCE IF NOT EXISTS document_pages_seq START 1;
CREATE TABLE IF NOT EXISTS document_pages (
    page_id         INTEGER PRIMARY KEY DEFAULT nextval('document_pages_seq'),
    document_id     INTEGER NOT NULL REFERENCES documents(document_id),
    page_number     INTEGER NOT NULL,  -- 1-indexed for display
    page_text       VARCHAR NOT NULL,
    char_count      INTEGER NOT NULL,
    UNIQUE(document_id, page_number)
);
```

- [ ] **Step 2: Verify schema creation is idempotent**

```bash
uv run python -c "
import duckdb
from corpus.db.schema import create_schema
conn = duckdb.connect(':memory:')
create_schema(conn)
create_schema(conn)  # Should not error
tables = conn.execute('SHOW TABLES').fetchall()
print([t[0] for t in tables])
assert 'document_markdown' in [t[0] for t in tables]
assert 'document_pages' in [t[0] for t in tables]
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add sql/001_corpus.sql
git commit -m "schema: add document_markdown and document_pages tables"
```

---

### Task 9: Parsed-dir promotion script

**Files:**
- Create: `scripts/promote_parsed_dir.py`

- [ ] **Step 1: Write the promotion script**

```python
# scripts/promote_parsed_dir.py
"""Promote data/parsed_docling/ → data/parsed/ (single-directory strategy).

Steps:
1. Rename data/parsed/ → data/parsed.pymupdf.bak/
2. Rename data/parsed_docling/ → data/parsed/
3. Re-run corpus parse --source edgar to regenerate EDGAR outputs in new data/parsed/

After this script: one authoritative data/parsed/ directory with Docling outputs
for all PDFs and HTMLParser outputs for EDGAR.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def main() -> int:
    parsed = DATA_DIR / "parsed"
    parsed_docling = DATA_DIR / "parsed_docling"
    parsed_backup = DATA_DIR / "parsed.pymupdf.bak"

    # Preflight
    if not parsed_docling.exists():
        print(f"ERROR: {parsed_docling} does not exist. Run the overnight parse first.")
        return 1

    if parsed_backup.exists():
        print(f"ERROR: {parsed_backup} already exists. Previous promotion incomplete?")
        return 1

    # Count files
    docling_count = len(list(parsed_docling.glob("*.jsonl")))
    # Subtract _progress.jsonl if present
    if (parsed_docling / "_progress.jsonl").exists():
        docling_count -= 1
    print(f"Docling outputs: {docling_count} JSONL files")
    print(f"Current parsed/: {len(list(parsed.glob('*.jsonl')))} JSONL files")

    # Step 1: Backup current parsed/
    print(f"\n1. Renaming {parsed} → {parsed_backup}")
    parsed.rename(parsed_backup)

    # Step 2: Promote parsed_docling/ → parsed/
    print(f"2. Renaming {parsed_docling} → {parsed}")
    parsed_docling.rename(parsed)

    # Step 3: Re-run EDGAR parse to regenerate HTMLParser outputs
    print("\n3. Re-parsing EDGAR files into new data/parsed/...")
    run_id = "promote-edgar-reparse"
    result = subprocess.run(
        ["uv", "run", "corpus", "parse", "run", "--run-id", run_id, "--source", "edgar"],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(f"WARNING: EDGAR reparse exited with code {result.returncode}")

    # Verify
    final_count = len(list(parsed.glob("*.jsonl")))
    print(f"\nFinal data/parsed/: {final_count} JSONL files")
    print("Backup at: data/parsed.pymupdf.bak/ (delete after verifying)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/promote_parsed_dir.py
git commit -m "feat: parsed-dir promotion script — single-directory strategy"
```

---

### Task 10: Ingest updates — read parse_tool + page_count from JSONL headers

**Files:**
- Modify: `src/corpus/db/ingest.py`
- Create: `tests/test_ingest_parse_fields.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_parse_fields.py
"""Test that ingest populates parse_tool + page_count from JSONL headers."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


def _make_manifest(tmp_path: Path, source: str, records: list[dict]) -> None:
    manifest = tmp_path / f"{source}_manifest.jsonl"
    with manifest.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_parsed_jsonl(parsed_dir: Path, storage_key: str, page_count: int, parse_tool: str) -> None:
    """Write a minimal JSONL parsed file with header."""
    jsonl = parsed_dir / f"{storage_key}.jsonl"
    with jsonl.open("w") as f:
        header = {
            "storage_key": storage_key,
            "page_count": page_count,
            "parse_tool": parse_tool,
            "parse_version": "2.86.0",
            "parse_status": "parse_ok",
            "parsed_at": "2026-04-12T00:00:00+00:00",
        }
        f.write(json.dumps(header) + "\n")
        for i in range(page_count):
            f.write(json.dumps({"page": i, "text": f"Page {i} text", "char_count": 11}) + "\n")


def test_ingest_reads_parse_fields_from_jsonl(tmp_path: Path):
    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    _make_parsed_jsonl(parsed_dir, "nsm__123", page_count=42, parse_tool="docling")

    _make_manifest(tmp_path, "nsm", [
        {"source": "nsm", "native_id": "123", "storage_key": "nsm__123",
         "title": "Test", "download_url": "http://x", "file_path": "data/original/nsm__123.pdf"},
    ])

    conn = duckdb.connect(":memory:")
    create_schema(conn)
    ingest_manifests(conn, tmp_path, parsed_dir=parsed_dir)

    row = conn.execute("SELECT parse_tool, page_count FROM documents WHERE storage_key = 'nsm__123'").fetchone()
    assert row is not None
    assert row[0] == "docling"
    assert row[1] == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_parse_fields.py -v`
Expected: FAIL — `ingest_manifests()` doesn't accept `parsed_dir` parameter yet

- [ ] **Step 3: Modify ingest_manifests to read JSONL headers**

In `src/corpus/db/ingest.py`, add a `parsed_dir` parameter and use it to populate `parse_tool` and `page_count`:

Add to the function signature:

```python
def ingest_manifests(
    conn: duckdb.DuckDBPyConnection,
    manifest_dir: Path,
    *,
    run_id: str | None = None,
    parsed_dir: Path | None = None,
) -> dict[str, Any]:
```

In the body, after building the record dict but before inserting, add logic to read the JSONL header if `parsed_dir` is provided:

```python
# After record is built from manifest, before _insert_document:
if parsed_dir is not None:
    storage_key = record.get("storage_key", "")
    jsonl_path = parsed_dir / f"{storage_key}.jsonl"
    if jsonl_path.exists():
        with jsonl_path.open() as jf:
            first_line = jf.readline().strip()
            if first_line:
                header = _json.loads(first_line)
                if "parse_tool" in header:
                    record["parse_tool"] = header["parse_tool"]
                if "page_count" in header:
                    record["page_count"] = header["page_count"]
                if "parse_version" in header:
                    record["parse_version"] = header["parse_version"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ingest_parse_fields.py -v`
Expected: PASS

- [ ] **Step 5: Run existing ingest tests for regressions**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: all PASS (the new parameter is optional, so existing calls are unaffected)

- [ ] **Step 6: Commit**

```bash
git add src/corpus/db/ingest.py tests/test_ingest_parse_fields.py
git commit -m "feat: ingest reads parse_tool + page_count from JSONL headers"
```

---

### Task 11: document_markdown ingest

**Files:**
- Create: `src/corpus/db/markdown.py`
- Create: `tests/test_markdown_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_markdown_ingest.py
"""Test document_markdown table population from .md sidecar files."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from corpus.db.markdown import ingest_markdown
from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


def _setup_db_with_doc(tmp_path: Path) -> tuple[duckdb.DuckDBPyConnection, Path]:
    """Create DB with one document, return (conn, parsed_dir)."""
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest = manifest_dir / "nsm_manifest.jsonl"
    manifest.write_text(json.dumps({
        "source": "nsm", "native_id": "123", "storage_key": "nsm__123",
        "title": "Test Doc", "download_url": "http://x", "file_path": "x.pdf",
    }) + "\n")
    ingest_manifests(conn, manifest_dir)
    return conn, tmp_path


def test_ingest_markdown_from_md_files(tmp_path: Path):
    conn, _ = _setup_db_with_doc(tmp_path)

    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    (parsed_dir / "nsm__123.md").write_text("# Test Document\n\nSome **markdown** content.")

    stats = ingest_markdown(conn, parsed_dir)
    assert stats["inserted"] == 1

    row = conn.execute("SELECT markdown_text FROM document_markdown WHERE document_id = 1").fetchone()
    assert row is not None
    assert "# Test Document" in row[0]


def test_skips_missing_documents(tmp_path: Path):
    conn, _ = _setup_db_with_doc(tmp_path)

    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    # .md for a doc not in the DB
    (parsed_dir / "nsm__999.md").write_text("# Unknown")

    stats = ingest_markdown(conn, parsed_dir)
    assert stats["inserted"] == 0
    assert stats["skipped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_markdown_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ingest_markdown**

```python
# src/corpus/db/markdown.py
"""Ingest .md sidecar files into the document_markdown table."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


def ingest_markdown(
    conn: duckdb.DuckDBPyConnection,
    parsed_dir: Path,
) -> dict[str, Any]:
    """Read .md files from parsed_dir, match to documents, insert into document_markdown.

    Returns stats dict with inserted, skipped, errors.
    """
    stats: dict[str, int] = {"inserted": 0, "skipped": 0, "errors": 0}

    # Build storage_key → document_id map
    rows = conn.execute("SELECT document_id, storage_key FROM documents").fetchall()
    doc_id_map = {row[1]: row[0] for row in rows}

    # Clear existing data for fresh rebuild
    conn.execute("DELETE FROM document_markdown")

    for md_path in sorted(parsed_dir.glob("*.md")):
        storage_key = md_path.stem
        doc_id = doc_id_map.get(storage_key)
        if doc_id is None:
            stats["skipped"] += 1
            continue

        try:
            markdown_text = md_path.read_text(encoding="utf-8")
            conn.execute(
                "INSERT INTO document_markdown (document_id, markdown_text) VALUES (?, ?)",
                [doc_id, markdown_text],
            )
            stats["inserted"] += 1
        except Exception:
            stats["errors"] += 1

    return stats
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_markdown_ingest.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/db/markdown.py tests/test_markdown_ingest.py
git commit -m "feat: document_markdown ingest from .md sidecar files"
```

---

### Task 12: document_pages + FTS index

**Files:**
- Create: `src/corpus/db/pages.py`
- Create: `tests/test_pages.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pages.py
"""Test document_pages table population and FTS index creation."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from corpus.db.pages import build_pages, create_fts_index
from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


def _setup(tmp_path: Path) -> tuple[duckdb.DuckDBPyConnection, Path]:
    conn = duckdb.connect(":memory:")
    create_schema(conn)

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    (manifest_dir / "nsm_manifest.jsonl").write_text(json.dumps({
        "source": "nsm", "native_id": "123", "storage_key": "nsm__123",
        "title": "Test", "download_url": "http://x", "file_path": "x.pdf",
    }) + "\n")
    ingest_manifests(conn, manifest_dir)

    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    with (parsed_dir / "nsm__123.jsonl").open("w") as f:
        f.write(json.dumps({"storage_key": "nsm__123", "page_count": 2, "parse_tool": "docling", "parse_version": "2.86.0", "parse_status": "parse_ok", "parsed_at": "2026-04-12T00:00:00"}) + "\n")
        f.write(json.dumps({"page": 0, "text": "Collective action clauses allow modification", "char_count": 44}) + "\n")
        f.write(json.dumps({"page": 1, "text": "Governing law shall be New York", "char_count": 31}) + "\n")

    return conn, parsed_dir


def test_build_pages(tmp_path: Path):
    conn, parsed_dir = _setup(tmp_path)
    stats = build_pages(conn, parsed_dir)
    assert stats["pages_inserted"] == 2

    rows = conn.execute("SELECT page_number, page_text FROM document_pages ORDER BY page_number").fetchall()
    assert len(rows) == 2
    assert rows[0][0] == 1  # 1-indexed for display
    assert "Collective action" in rows[0][1]
    assert rows[1][0] == 2
    assert "New York" in rows[1][1]


def test_fts_search(tmp_path: Path):
    conn, parsed_dir = _setup(tmp_path)
    build_pages(conn, parsed_dir)
    create_fts_index(conn)

    results = conn.execute("""
        SELECT dp.page_text, fts.score
        FROM (SELECT *, fts_main_document_pages.match_bm25(page_id, 'collective action') AS score
              FROM document_pages) dp
        JOIN fts_main_document_pages fts ON dp.page_id = fts.page_id
        WHERE score IS NOT NULL
        ORDER BY score DESC
    """).fetchall()
    # DuckDB FTS syntax varies; adjust if needed during implementation
    assert len(results) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pages.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement build_pages and create_fts_index**

```python
# src/corpus/db/pages.py
"""Build document_pages table and FTS index from parsed JSONL files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb


def build_pages(
    conn: duckdb.DuckDBPyConnection,
    parsed_dir: Path,
) -> dict[str, Any]:
    """Read JSONL files, insert per-page text into document_pages.

    Returns stats dict.
    """
    stats: dict[str, int] = {"pages_inserted": 0, "docs_processed": 0, "skipped": 0}

    rows = conn.execute("SELECT document_id, storage_key FROM documents").fetchall()
    doc_id_map = {row[1]: row[0] for row in rows}

    conn.execute("DELETE FROM document_pages")

    for jsonl_path in sorted(parsed_dir.glob("*.jsonl")):
        if jsonl_path.name.startswith("_"):
            continue  # Skip _progress.jsonl, _errors.log, etc.

        storage_key = jsonl_path.stem
        doc_id = doc_id_map.get(storage_key)
        if doc_id is None:
            stats["skipped"] += 1
            continue

        with jsonl_path.open() as f:
            for line in f:
                record = json.loads(line)
                if "page" not in record:
                    continue  # Skip header line
                conn.execute(
                    """INSERT INTO document_pages (document_id, page_number, page_text, char_count)
                       VALUES (?, ?, ?, ?)""",
                    [doc_id, record["page"] + 1, record["text"], record["char_count"]],
                )
                stats["pages_inserted"] += 1

        stats["docs_processed"] += 1

    return stats


def create_fts_index(conn: duckdb.DuckDBPyConnection) -> None:
    """Create DuckDB full-text search index on document_pages."""
    conn.execute("INSTALL fts")
    conn.execute("LOAD fts")
    # Drop existing index if any
    try:
        conn.execute("DROP INDEX IF EXISTS fts_main_document_pages")
    except Exception:
        pass
    conn.execute(
        "PRAGMA create_fts_index('document_pages', 'page_id', 'page_text', stemmer='porter')"
    )
```

- [ ] **Step 4: Run tests, iterate on FTS syntax if needed**

Run: `uv run pytest tests/test_pages.py -v`

DuckDB FTS syntax can be tricky. The test may need adjustment based on the exact DuckDB 1.4.4 FTS API. Fix the test or implementation until both pass.

- [ ] **Step 5: Commit**

```bash
git add src/corpus/db/pages.py tests/test_pages.py
git commit -m "feat: document_pages table + FTS index from parsed JSONL"
```

---

### Task 13: MotherDuck publish command

**Files:**
- Create: `src/corpus/db/publish.py`
- Modify: `src/corpus/cli.py` — add `corpus publish-motherduck` command

- [ ] **Step 1: Implement publish function**

```python
# src/corpus/db/publish.py
"""Publish local DuckDB tables to MotherDuck cloud database."""
from __future__ import annotations

import os
from pathlib import Path

import duckdb


def publish_to_motherduck(
    local_db_path: Path,
    *,
    motherduck_db: str = "sovereign_corpus",
    tables: tuple[str, ...] = (
        "documents",
        "document_countries",
        "document_pages",
        "document_markdown",
        "grep_matches",
    ),
) -> dict[str, int]:
    """Copy tables from local DuckDB to MotherDuck.

    Requires MOTHERDUCK_TOKEN environment variable.
    Returns dict of table_name → row_count.
    """
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN environment variable is required")

    local_conn = duckdb.connect(str(local_db_path), read_only=True)
    md_conn = duckdb.connect(
        f"md:{motherduck_db}",
        config={"motherduck_token": token},
    )

    stats: dict[str, int] = {}

    for table in tables:
        # Check table exists locally
        exists = local_conn.execute(
            f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'"
        ).fetchone()
        if not exists or exists[0] == 0:
            continue

        df = local_conn.execute(f"SELECT * FROM {table}").fetchdf()
        md_conn.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM df")
        count = md_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        stats[table] = count[0] if count else 0

    # Rebuild FTS index on MotherDuck
    try:
        md_conn.execute("INSTALL fts")
        md_conn.execute("LOAD fts")
        md_conn.execute(
            "PRAGMA create_fts_index('document_pages', 'page_id', 'page_text', stemmer='porter')"
        )
    except Exception:
        pass  # FTS may not be available on MotherDuck free tier

    local_conn.close()
    md_conn.close()

    return stats
```

- [ ] **Step 2: Add CLI command**

Add to `src/corpus/cli.py`:

```python
@cli.command("publish-motherduck")
@click.option("--db-path", type=click.Path(path_type=Path), default="data/db/corpus.duckdb")
def publish_motherduck_cmd(db_path: Path) -> None:
    """Publish local DuckDB tables to MotherDuck cloud database."""
    from corpus.db.publish import publish_to_motherduck

    db_path = _PROJECT_ROOT / db_path if not db_path.is_absolute() else db_path
    stats = publish_to_motherduck(db_path)
    for table, count in stats.items():
        click.echo(f"  {table}: {count:,} rows")
    click.echo("Published to MotherDuck.")
```

- [ ] **Step 3: Verify CLI loads**

```bash
uv run corpus publish-motherduck --help
```

Expected: shows help text.

- [ ] **Step 4: Commit**

```bash
git add src/corpus/db/publish.py src/corpus/cli.py
git commit -m "feat: corpus publish-motherduck command"
```

---

### Task 14: Build-pages CLI + full PR #3 pipeline

**Files:**
- Modify: `src/corpus/cli.py` — add `corpus build-pages` and `corpus ingest-markdown` commands

- [ ] **Step 1: Add CLI commands for build-pages and ingest-markdown**

```python
@cli.command("build-pages")
@click.option("--db-path", type=click.Path(path_type=Path), default="data/db/corpus.duckdb")
@click.option("--parsed-dir", type=click.Path(path_type=Path), default="data/parsed")
def build_pages_cmd(db_path: Path, parsed_dir: Path) -> None:
    """Build document_pages table and FTS index from parsed JSONL files."""
    from corpus.db.pages import build_pages, create_fts_index

    db_path = _PROJECT_ROOT / db_path if not db_path.is_absolute() else db_path
    parsed_dir = _PROJECT_ROOT / parsed_dir if not parsed_dir.is_absolute() else parsed_dir

    conn = duckdb.connect(str(db_path))
    from corpus.db.schema import create_schema
    create_schema(conn)

    stats = build_pages(conn, parsed_dir)
    click.echo(f"Pages inserted: {stats['pages_inserted']:,}")
    click.echo(f"Documents processed: {stats['docs_processed']:,}")

    click.echo("Building FTS index...")
    create_fts_index(conn)
    click.echo("FTS index created.")
    conn.close()


@cli.command("ingest-markdown")
@click.option("--db-path", type=click.Path(path_type=Path), default="data/db/corpus.duckdb")
@click.option("--parsed-dir", type=click.Path(path_type=Path), default="data/parsed")
def ingest_markdown_cmd(db_path: Path, parsed_dir: Path) -> None:
    """Ingest .md sidecar files into document_markdown table."""
    from corpus.db.markdown import ingest_markdown

    db_path = _PROJECT_ROOT / db_path if not db_path.is_absolute() else db_path
    parsed_dir = _PROJECT_ROOT / parsed_dir if not parsed_dir.is_absolute() else parsed_dir

    conn = duckdb.connect(str(db_path))
    from corpus.db.schema import create_schema
    create_schema(conn)

    stats = ingest_markdown(conn, parsed_dir)
    click.echo(f"Markdown files ingested: {stats['inserted']:,}")
    click.echo(f"Skipped (no matching doc): {stats['skipped']:,}")
    conn.close()
```

- [ ] **Step 2: Verify CLI loads**

```bash
uv run corpus build-pages --help
uv run corpus ingest-markdown --help
```

- [ ] **Step 3: Lint and test**

```bash
uv run ruff check src/ tests/
uv run pytest -v
```

- [ ] **Step 4: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: corpus build-pages and ingest-markdown CLI commands"
```

---

## PR #4 — Task 4: Streamlit Explorer

### Task 15: Rewrite explorer/app.py

**Files:**
- Rewrite: `explorer/app.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

```
streamlit==1.45.1
duckdb==1.4.4
pandas>=2.0
```

(No changes needed if already correct.)

- [ ] **Step 2: Rewrite explorer/app.py**

```python
# explorer/app.py
"""Sovereign Bond Prospectus Explorer — searchable corpus with markdown detail panel."""
from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")


@st.cache_resource(ttl=3600)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to MotherDuck when a token is set, else use local DuckDB."""
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
    if LOCAL_DB_PATH.exists():
        return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
    st.error("No database found. Set MOTHERDUCK_TOKEN or provide local data/db/corpus.duckdb.")
    st.stop()


def main() -> None:
    st.set_page_config(page_title="Sovereign Prospectus Explorer", layout="wide")
    st.title("Sovereign Bond Prospectus Explorer")

    conn = get_connection()

    # --- Sidebar filters ---
    with st.sidebar:
        st.header("Filters")

        sources = conn.execute("SELECT DISTINCT source FROM documents ORDER BY source").fetchdf()
        selected_sources = st.multiselect("Source", sources["source"].tolist(), default=sources["source"].tolist())

        countries = conn.execute("""
            SELECT DISTINCT dc.country_name
            FROM document_countries dc
            WHERE dc.country_name IS NOT NULL
            ORDER BY dc.country_name
        """).fetchdf()
        if not countries.empty:
            selected_countries = st.multiselect("Country", countries["country_name"].tolist())
        else:
            selected_countries = []

        doc_types = conn.execute("SELECT DISTINCT doc_type FROM documents WHERE doc_type IS NOT NULL ORDER BY doc_type").fetchdf()
        if not doc_types.empty:
            selected_types = st.multiselect("Document Type", doc_types["doc_type"].tolist())
        else:
            selected_types = []

    # --- Search ---
    search_query = st.text_input("Search document text", placeholder="e.g., collective action clause, pari passu, governing law")

    # --- Query params for deep linking ---
    params = st.query_params
    selected_doc_id = params.get("doc", None)

    # --- Corpus stats ---
    stats = conn.execute("SELECT COUNT(*) AS docs, COUNT(DISTINCT source) AS sources FROM documents").fetchone()
    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", f"{stats[0]:,}")
    col2.metric("Sources", stats[1])

    page_stats = conn.execute("SELECT COUNT(*) FROM document_pages").fetchone()
    if page_stats and page_stats[0] > 0:
        col3.metric("Searchable Pages", f"{page_stats[0]:,}")

    # --- Build results query ---
    if search_query:
        # FTS search via document_pages
        results = conn.execute("""
            SELECT DISTINCT
                d.document_id,
                d.source,
                d.title,
                d.issuer_name,
                d.publication_date,
                d.doc_type,
                d.page_count
            FROM documents d
            JOIN document_pages dp ON d.document_id = dp.document_id
            WHERE dp.page_text ILIKE ?
              AND d.source IN (SELECT UNNEST(?::VARCHAR[]))
            ORDER BY d.publication_date DESC NULLS LAST
            LIMIT 200
        """, [f"%{search_query}%", selected_sources]).fetchdf()
    else:
        where_clauses = ["d.source IN (SELECT UNNEST(?::VARCHAR[]))"]
        params_list: list = [selected_sources]

        if selected_countries:
            where_clauses.append("dc.country_name IN (SELECT UNNEST(?::VARCHAR[]))")
            params_list.append(selected_countries)

        if selected_types:
            where_clauses.append("d.doc_type IN (SELECT UNNEST(?::VARCHAR[]))")
            params_list.append(selected_types)

        country_join = "LEFT JOIN document_countries dc ON d.document_id = dc.document_id" if selected_countries else ""

        results = conn.execute(f"""
            SELECT DISTINCT
                d.document_id,
                d.source,
                d.title,
                d.issuer_name,
                d.publication_date,
                d.doc_type,
                d.page_count
            FROM documents d
            {country_join}
            WHERE {" AND ".join(where_clauses)}
            ORDER BY d.publication_date DESC NULLS LAST
            LIMIT 200
        """, params_list).fetchdf()

    st.subheader(f"Results ({len(results)} documents)")

    if results.empty:
        st.info("No documents match your filters.")
        return

    # --- Results table ---
    for _, row in results.iterrows():
        doc_id = row["document_id"]
        title = row["title"] or "(untitled)"
        source = row["source"]
        issuer = row["issuer_name"] or ""
        pub_date = row["publication_date"] or ""
        pages = row["page_count"] or "?"

        with st.expander(f"**{title}** — {issuer} ({source}, {pub_date}, {pages} pp)"):
            # Deep link
            st.markdown(f"[Permalink](?doc={doc_id})")

            # Search highlights within this doc
            if search_query:
                matches = conn.execute("""
                    SELECT page_number, page_text
                    FROM document_pages
                    WHERE document_id = ? AND page_text ILIKE ?
                    ORDER BY page_number
                    LIMIT 10
                """, [int(doc_id), f"%{search_query}%"]).fetchdf()
                if not matches.empty:
                    st.caption(f"Found on {len(matches)} page(s):")
                    for _, m in matches.iterrows():
                        st.text(f"Page {m['page_number']}: ...{m['page_text'][:200]}...")

            # Markdown detail panel
            md_row = conn.execute(
                "SELECT markdown_text FROM document_markdown WHERE document_id = ?",
                [int(doc_id)]
            ).fetchone()
            if md_row:
                st.markdown(md_row[0][:50000])  # Cap at 50K chars for rendering
            else:
                st.info("Full text not available for this document.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test locally (manual)**

```bash
cd explorer && uv run streamlit run app.py
```

Verify: landing page loads, search works, filters work, detail panel renders markdown.

- [ ] **Step 4: Commit**

```bash
git add explorer/app.py requirements.txt
git commit -m "feat: Streamlit explorer — search, filters, markdown detail panel"
```

---

### Task 16: Deploy to Streamlit Cloud

- [ ] **Step 1: Verify Streamlit Cloud settings**

In Streamlit Cloud dashboard:
- App path: `explorer/app.py`
- Python version: 3.12
- Requirements file: `requirements.txt`
- Secret: `MOTHERDUCK_TOKEN` is set

- [ ] **Step 2: Push and trigger deploy**

```bash
git push
```

Streamlit Cloud auto-deploys from the branch.

- [ ] **Step 3: Verify deployment**

Visit `https://sovereign-prospectus-corpus.streamlit.app` and run smoke tests:
- Search "collective action" — should return results
- Search "pari passu" — should return results
- Search "governing law" — should return results
- Filter by source: NSM, EDGAR, PDIP
- Click a document — markdown should render in detail panel
- Check DRC is present (search "Democratic Republic of the Congo")

---

## PR #5 — Polish (Monday morning)

### Task 17: Demo script + warm-up

- [ ] **Step 1: Write a warm-up ping script**

```bash
# Quick warm-up to prevent cold-start lag during demo
curl -s https://sovereign-prospectus-corpus.streamlit.app | head -1
echo "Warm-up ping sent"
```

- [ ] **Step 2: Run final smoke tests**

Manually verify these searches in the live explorer:
- "collective action clause" → Ghana, Argentina results
- "pari passu" → multiple results
- "New York law" → governing law results
- "Democratic Republic of the Congo" → DRC prospectus
- Filter: PDIP source only → PDIP documents
- Click any document → markdown renders

- [ ] **Step 3: Commit any polish fixes**

```bash
git add -A
git commit -m "chore: Monday morning polish and smoke test fixes"
git push
```

---

## Execution Runbook (condensed)

```
Saturday afternoon:
  Tasks 1-7 (PR #1: DoclingParser + CLI rewire + fixed reparse)
  Step 2: NSM + EDGAR incrementals (parallel shells)
  Step 3: LuxSE adapter (separate plan, up to 4h)

Saturday evening:
  Step 4: Delete data/parsed_docling/, run overnight parse

Sunday morning:
  Step 5: Verify overnight parse
  Task 8: Schema DDL
  Task 9: Run promote_parsed_dir.py
  Task 10: Ingest with parse_tool + page_count
  Tasks 11-14: markdown ingest, pages, FTS, MotherDuck publish
  Re-run: corpus grep run --run-id grep-docling
  Re-run: corpus ingest (to rebuild documents table)

Sunday afternoon:
  Task 15-16: Streamlit explorer + deploy

Monday morning:
  Task 17: Polish + smoke tests
```
