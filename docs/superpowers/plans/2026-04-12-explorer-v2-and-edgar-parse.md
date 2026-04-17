# Explorer V2 + EDGAR HTML Parse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a searchable document explorer with ~8,000+ sovereign bond prospectuses and parse EDGAR HTML filings with Docling, all before the IMF Spring Meetings demo on Monday April 13.

**Architecture:** Three parallel workstreams: (1) EDGAR HTML parse script with SGML stripping and page splitting on Mac Mini, chained after the running PDF parse; (2) Streamlit explorer with FTS search and page-by-page detail view on MacBook Air; (3) Congo manual ingest on either machine. Council of Experts reviews at plan, EDGAR script, and explorer stages.

**Tech Stack:** Python 3.12, Docling (HTML SimplePipeline), DuckDB FTS, MotherDuck, Streamlit, BeautifulSoup

**Spec:** `docs/superpowers/specs/2026-04-12-explorer-v2-and-edgar-parse-design.md`

**Machine assignments:**
- Tasks 1-4: Mac Mini (EDGAR parse + chain)
- Tasks 5-8: MacBook Air (explorer UI)
- Task 9: Either machine (Congo ingest)
- Task 10: Council reviews (dispatched from whichever machine is active)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/docling_reparse_edgar.py` | Create | EDGAR HTML/text parser with SGML stripping, page splitting, Docling markdown |
| `scripts/chain_overnight.sh` | Create | Auto-chain PDF → EDGAR → validation with telemetry |
| `tests/test_edgar_parse.py` | Create | Tests for SGML stripping, page splitting, Docling HTML conversion |
| `explorer/app.py` | Rewrite | Search, page-by-page detail, landing page, filters |
| `explorer/requirements.txt` | Modify | Add any new deps |

---

### Task 1: EDGAR SGML stripping and page splitting (Mac Mini)

**Files:**
- Create: `scripts/docling_reparse_edgar.py`
- Create: `tests/test_edgar_parse.py`
- Reference: `src/corpus/parsers/html_parser.py`, `src/corpus/parsers/text_parser.py`

- [ ] **Step 1: Write test for SGML stripping**

Create `tests/test_edgar_parse.py`:

```python
"""Tests for EDGAR HTML/text parsing with SGML stripping."""

from __future__ import annotations


def test_strip_sgml_wrapper_htm():
    """SGML envelope is stripped, HTML content extracted."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = (
        "<DOCUMENT>\n<TYPE>424B3\n<SEQUENCE>1\n"
        "<FILENAME>test.htm\n<TEXT>\n"
        "<html><body><h1>Republic of Peru</h1></body></html>\n"
        "</TEXT>\n</DOCUMENT>"
    )
    content, is_html = strip_sgml_wrapper(raw)
    assert "<h1>Republic of Peru</h1>" in content
    assert "<DOCUMENT>" not in content
    assert "<TYPE>" not in content
    assert is_html is True


def test_strip_sgml_wrapper_txt():
    """Plain text .txt files: SGML stripped, detected as non-HTML."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = (
        "<DOCUMENT>\n<TYPE>424B5\n<SEQUENCE>1\n"
        "<FILENAME>test.txt\n<TEXT>\n"
        "                    Filed Pursuant to Rule 424(b)(5)\n"
        "                    Republic of Peru\n"
        "<PAGE>\n"
        "                    9 1/8% Bonds due 2008\n"
        "</TEXT>\n</DOCUMENT>"
    )
    content, is_html = strip_sgml_wrapper(raw)
    assert "Republic of Peru" in content
    assert "<DOCUMENT>" not in content
    assert is_html is False


def test_strip_sgml_wrapper_no_wrapper():
    """Files without SGML wrapper are returned as-is."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = "<html><body><h1>Hello</h1></body></html>"
    content, is_html = strip_sgml_wrapper(raw)
    assert content == raw
    assert is_html is True


def test_split_htm_pages_with_css_breaks():
    """HTML files split on page-break CSS."""
    from scripts.docling_reparse_edgar import split_htm_pages

    html = (
        '<div>Page 1 content</div>'
        '<div style="page-break-before: always">Page 2 content</div>'
        '<div style="page-break-before: always">Page 3 content</div>'
    )
    pages = split_htm_pages(html)
    assert len(pages) >= 2  # At least 2 pages from the breaks


def test_split_htm_pages_no_breaks():
    """HTML without page breaks becomes one page."""
    from scripts.docling_reparse_edgar import split_htm_pages

    html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
    pages = split_htm_pages(html)
    assert len(pages) == 1


def test_split_txt_pages():
    """Text files split on <PAGE> markers."""
    from scripts.docling_reparse_edgar import split_txt_pages

    text = "Page one content\n<PAGE>\nPage two content\n<PAGE>\nPage three"
    pages = split_txt_pages(text)
    assert len(pages) == 3
    assert "Page one" in pages[0]
    assert "Page three" in pages[2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_edgar_parse.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement SGML stripping and page splitting**

Create `scripts/docling_reparse_edgar.py` with the core functions:

```python
#!/usr/bin/env python3
"""EDGAR HTML/text re-parse — SGML stripping + Docling markdown.

Parses SEC EDGAR .htm and .txt filings:
1. Strip SGML wrapper (<DOCUMENT><TEXT>...</TEXT></DOCUMENT>)
2. Split into pages (CSS page-breaks for HTML, <PAGE> for text)
3. Generate structured markdown via Docling HTML pipeline (no ML models)

Usage:
    uv run python scripts/docling_reparse_edgar.py [--limit N] [--timeout 120]
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from corpus.parsers.markdown import strip_markdown

# ── Configuration ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "parsed_docling"
ERRORS_LOG = OUTPUT_DIR / "_errors.log"
PROGRESS_LOG = OUTPUT_DIR / "_progress.jsonl"

_ENCODINGS = ("utf-8", "cp1252", "latin-1")
_SGML_TEXT_RE = re.compile(
    r"<TEXT>\s*(.*?)\s*</TEXT>", re.DOTALL | re.IGNORECASE
)
_PAGE_BREAK_RE = re.compile(r"page-break-(?:before|after)\s*:\s*always", re.IGNORECASE)
_PAGE_MARKER = "<PAGE>"
_HTML_TAG_RE = re.compile(r"<(?:html|body|div|table|p|h[1-6])\b", re.IGNORECASE)


# ── SGML stripping ────────────────────────────────────────────────


def strip_sgml_wrapper(raw: str) -> tuple[str, bool]:
    """Extract content from EDGAR SGML envelope.

    Returns (content, is_html) where is_html indicates whether the
    extracted content appears to be HTML (vs plain text).
    """
    match = _SGML_TEXT_RE.search(raw)
    if match:
        content = match.group(1)
    else:
        content = raw

    # Determine if content is HTML or plain text
    is_html = bool(_HTML_TAG_RE.search(content[:2000]))
    return content, is_html


# ── Page splitting ────────────────────────────────────────────────


def split_htm_pages(html: str) -> list[str]:
    """Split HTML on CSS page-break markers. Returns list of HTML page strings.

    Reuses the same logic as src/corpus/parsers/html_parser.py.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Look for page-break CSS
    marker = "\x00PAGE_BREAK\x00"
    found = False
    for tag in soup.find_all(True):
        style = tag.get("style", "")
        if not isinstance(style, str):
            continue
        if _PAGE_BREAK_RE.search(style):
            tag.insert_before(marker)
            found = True

    if found:
        full_text = soup.get_text(separator="\n")
        raw_pages = full_text.split(marker)
        pages = []
        for page in raw_pages:
            lines = [line.strip() for line in page.splitlines()]
            cleaned = "\n".join(line for line in lines if line)
            if cleaned:
                pages.append(cleaned)
        return pages if pages else [soup.get_text(separator="\n")]
    else:
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return [cleaned] if cleaned else []


def split_txt_pages(text: str) -> list[str]:
    """Split plain text on <PAGE> markers.

    Reuses the same logic as src/corpus/parsers/text_parser.py.
    """
    if _PAGE_MARKER in text:
        # Strip SGML preamble if still present
        preamble_re = re.compile(
            r"\A\s*<DOCUMENT>.*?<TEXT>\s*", re.DOTALL | re.IGNORECASE
        )
        text = preamble_re.sub("", text)
        pages = [p.strip() for p in text.split(_PAGE_MARKER)]
        if pages and not pages[0]:
            pages.pop(0)
        if pages and not pages[-1]:
            pages.pop()
        return pages if pages else [text]
    else:
        return [text]


# ── Docling markdown conversion ───────────────────────────────────


def html_to_markdown(html_content: str) -> str:
    """Convert HTML string to structured markdown via Docling.

    Uses SimplePipeline (BeautifulSoup) — no ML models, no memory leak.
    """
    from docling.datamodel.document import DocumentStream
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    stream = DocumentStream(
        name="page.html",
        stream=io.BytesIO(html_content.encode("utf-8")),
    )
    result = converter.convert(stream)
    return result.document.export_to_markdown()


# ── Single-file processing ────────────────────────────────────────


def process_one_edgar(storage_key: str, file_path: Path) -> dict:
    """Process a single EDGAR file. Returns result dict."""
    start = time.monotonic()
    file_size_mb = round(file_path.stat().st_size / (1024 * 1024), 1)

    try:
        raw_bytes = file_path.read_bytes()
        # Decode with fallback
        raw_text = None
        for enc in _ENCODINGS:
            try:
                raw_text = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, ValueError):
                continue
        if raw_text is None:
            raw_text = raw_bytes.decode("latin-1")

        # Step 1: Strip SGML
        content, is_html = strip_sgml_wrapper(raw_text)

        # Step 2: Split pages
        if is_html:
            pages_text = split_htm_pages(content)
            parse_tool = "docling-html"
        else:
            pages_text = split_txt_pages(content)
            parse_tool = "text-passthrough"

        page_count = len(pages_text)

        # Step 3: Generate markdown
        if is_html and content.strip():
            # Full document through Docling for structured markdown
            full_markdown = html_to_markdown(content)
        else:
            # Plain text: use as-is
            full_markdown = "\n\n".join(pages_text)

        # Per-page plain text (strip markdown for JSONL)
        pages_plain = []
        for page_text in pages_text:
            if is_html:
                # Already plain text from get_text()
                pages_plain.append(page_text)
            else:
                pages_plain.append(page_text)

        elapsed = time.monotonic() - start
        from importlib.metadata import version as pkg_version
        docling_version = pkg_version("docling")

        # Determine parse status
        stripped_lengths = [len(p.strip()) for p in pages_plain]
        total_chars = sum(stripped_lengths)
        if page_count == 0 or total_chars == 0:
            parse_status = "parse_empty"
        else:
            empty_pages = sum(1 for sl in stripped_lengths if sl < 50)
            if empty_pages == page_count:
                parse_status = "parse_empty"
            elif empty_pages > page_count * 0.5:
                parse_status = "parse_partial"
            else:
                parse_status = "parse_ok"

        # Write markdown sidecar (atomic)
        md_path = OUTPUT_DIR / f"{storage_key}.md"
        md_part = md_path.with_suffix(".md.part")
        md_part.write_text(full_markdown)
        os.replace(str(md_part), str(md_path))

        # Write JSONL (atomic)
        jsonl_path = OUTPUT_DIR / f"{storage_key}.jsonl"
        jsonl_part = jsonl_path.with_suffix(".jsonl.part")
        with jsonl_part.open("w") as f:
            header = {
                "storage_key": storage_key,
                "page_count": page_count,
                "parse_tool": parse_tool,
                "parse_version": docling_version,
                "parse_status": parse_status,
                "parsed_at": datetime.now(UTC).isoformat(),
            }
            f.write(json.dumps(header) + "\n")
            for i, page_text in enumerate(pages_plain):
                f.write(json.dumps({
                    "page": i,
                    "text": page_text,
                    "char_count": len(page_text),
                }) + "\n")
        os.replace(str(jsonl_part), str(jsonl_path))

        return {
            "status": "success",
            "storage_key": storage_key,
            "page_count": page_count,
            "elapsed_s": round(elapsed, 1),
            "file_size_mb": file_size_mb,
            "error": None,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "status": "failed",
            "storage_key": storage_key,
            "page_count": 0,
            "elapsed_s": round(elapsed, 1),
            "file_size_mb": file_size_mb,
            "error": f"{type(exc).__name__}: {exc}",
        }


# ── Discovery ─────────────────────────────────────────────────────


def discover_edgar_files() -> list[tuple[str, Path]]:
    """Find all EDGAR .htm and .txt files. Skip .paper files."""
    original_dir = PROJECT_ROOT / "data" / "original"
    files: list[tuple[str, Path]] = []
    if original_dir.exists():
        for path in sorted(original_dir.iterdir()):
            if not path.name.startswith("edgar__"):
                continue
            if path.suffix in (".htm", ".html"):
                files.append((path.stem, path))
            elif path.suffix == ".txt":
                files.append((path.stem, path))
            # .paper files are skipped (empty stubs)
    return files


def filter_already_done(files: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """Skip files that already have both .jsonl and .md output."""
    remaining = []
    for storage_key, path in files:
        jsonl = OUTPUT_DIR / f"{storage_key}.jsonl"
        md = OUTPUT_DIR / f"{storage_key}.md"
        if jsonl.exists() and jsonl.stat().st_size > 0 and md.exists() and md.stat().st_size > 0:
            continue
        remaining.append((storage_key, path))
    return remaining


# ── Main ──────────────────────────────────────────────────────────


def write_progress(result: dict) -> None:
    """Append progress entry."""
    entry = {**result, "memory_gb": 0, "workers": 1, "timestamp": datetime.now(UTC).isoformat()}
    with PROGRESS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="EDGAR HTML/text re-parse")
    parser.add_argument("--limit", type=int, default=None, help="Max files to process")
    parser.add_argument("--timeout", type=int, default=120, help="Per-file timeout (seconds)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    error_handler = logging.FileHandler(str(ERRORS_LOG), mode="a")
    error_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(error_handler)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clean stale .part files
    for part_file in OUTPUT_DIR.glob("edgar__*.part"):
        logging.warning("Removing stale .part file: %s", part_file.name)
        part_file.unlink(missing_ok=True)

    # Discover and filter
    all_files = discover_edgar_files()
    remaining = filter_already_done(all_files)
    logging.info("Discovered %d EDGAR files, %d remaining after resume filter", len(all_files), len(remaining))

    if args.limit:
        remaining = remaining[:args.limit]

    if not remaining:
        logging.info("Nothing to process.")
        return

    # Smoke test: first 5 files
    logging.info("Smoke testing first 5 files...")
    smoke_failures = 0
    for sk, path in remaining[:5]:
        result = process_one_edgar(sk, path)
        if result["status"] != "success":
            logging.error("Smoke test FAILED: %s — %s", sk, result["error"])
            smoke_failures += 1
        else:
            logging.info("Smoke OK: %s — %d pages in %.1fs", sk, result["page_count"], result["elapsed_s"])
        write_progress(result)
    if smoke_failures > 2:
        logging.error("Too many smoke test failures (%d/5). Aborting.", smoke_failures)
        sys.exit(1)

    # Process remaining (skip smoke-tested files)
    remaining = remaining[5:]
    completed = 5 - smoke_failures
    failed = smoke_failures
    total = len(all_files) - (len(all_files) - len(remaining) - 5)
    start_time = time.monotonic()

    for i, (storage_key, path) in enumerate(remaining):
        result = process_one_edgar(storage_key, path)

        if result["status"] == "success":
            completed += 1
        else:
            failed += 1
            logging.error("FAILED: %s — %s", storage_key, result["error"])

        done = completed + failed
        if result["status"] == "success":
            logging.info(
                "[%d/%d] %s — %d pages — %.1fs — OK",
                done, len(all_files), storage_key, result["page_count"], result["elapsed_s"],
            )
        write_progress(result)

        # Periodic summary
        if done % 100 == 0:
            elapsed = time.monotonic() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(remaining) - i) / rate / 60 if rate > 0 else 0
            logging.info(
                "Progress: %d/%d — %d OK, %d failed — %.1f files/min — ETA %.0fm",
                done, len(all_files), completed, failed, rate * 60, eta,
            )

    elapsed_total = time.monotonic() - start_time
    summary = {
        "total": len(all_files),
        "completed": completed,
        "failed": failed,
        "elapsed_s": round(elapsed_total, 1),
        "elapsed_human": f"{elapsed_total / 3600:.1f}h",
        "finished_at": datetime.now(UTC).isoformat(),
    }
    summary_path = OUTPUT_DIR / "_edgar_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logging.info("Done. %s", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_edgar_parse.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check scripts/docling_reparse_edgar.py tests/test_edgar_parse.py`
Fix any issues.

- [ ] **Step 6: Commit**

```bash
git add scripts/docling_reparse_edgar.py tests/test_edgar_parse.py
git commit -m "feat: EDGAR HTML/text parser with SGML stripping and page splitting"
```

---

### Task 2: Smoke test on real EDGAR files (Mac Mini)

- [ ] **Step 1: Run on 10 real files**

```bash
uv run python scripts/docling_reparse_edgar.py --limit 10
```

Expected: 10 files processed, check output quality:

```bash
head -3 data/parsed_docling/edgar__*.jsonl | head -20
head -20 data/parsed_docling/edgar__*.md | head -40
```

Verify: page_count > 1 for files with page breaks, markdown has structure.

- [ ] **Step 2: Check a .txt file specifically**

```bash
ls data/parsed_docling/edgar__0000903423-02-000767.jsonl && echo "exists"
head -1 data/parsed_docling/edgar__0000903423-02-000767.jsonl | python3 -m json.tool
```

Verify: `parse_tool` is `"text-passthrough"`, `page_count` matches `<PAGE>` count.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u && git commit -m "fix: adjustments from EDGAR smoke test"
```

---

### Task 3: Chain overnight wrapper (Mac Mini)

**Files:**
- Create: `scripts/chain_overnight.sh`

- [ ] **Step 1: Create chain wrapper**

```bash
#!/bin/bash
# chain_overnight.sh — Wait for PDF parse, run EDGAR parse, validate.
# Usage: bash scripts/chain_overnight.sh &

set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PARSED="$DIR/data/parsed_docling"
CHAIN_LOG="$PARSED/_chain_log.jsonl"
CHAIN_COMPLETE="$PARSED/_chain_complete.json"
CHAIN_START=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)

log_stage() {
    local stage="$1" status="$2"
    shift 2
    echo "{\"stage\":\"$stage\",\"status\":\"$status\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"$@}" >> "$CHAIN_LOG"
}

echo "Chain started at $(date). Waiting for PDF parse to finish..."
log_stage "waiting_for_pdf" "started"

# Wait for PDF parse to finish by watching for _summary.json update
while true; do
    if [ -f "$PARSED/_summary.json" ]; then
        FINISHED_AT=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('finished_at',''))" 2>/dev/null || echo "")
        if [ -n "$FINISHED_AT" ] && [ "$FINISHED_AT" \> "$CHAIN_START" ]; then
            echo "PDF parse completed at $FINISHED_AT"
            break
        fi
    fi
    sleep 300
done

# Verify PDF parse succeeded
SHUTDOWN=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('shutdown_requested', True))" 2>/dev/null)
FAILED=$(python3 -c "import json; s=json.load(open('$PARSED/_summary.json')); print(s.get('failed',0))" 2>/dev/null)
TOTAL=$(python3 -c "import json; s=json.load(open('$PARSED/_summary.json')); print(s.get('total',0))" 2>/dev/null)

log_stage "pdf_complete" "checked" ",\"completed\":$((TOTAL-FAILED)),\"failed\":$FAILED"

if [ "$SHUTDOWN" = "True" ]; then
    echo "ERROR: PDF parse was shut down (memory ceiling or signal). Not starting EDGAR."
    log_stage "chain_aborted" "pdf_shutdown"
    echo "{\"status\":\"aborted\",\"reason\":\"pdf_shutdown\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"}" > "$CHAIN_COMPLETE"
    exit 1
fi

ERROR_RATE=$(python3 -c "print(round($FAILED / max($TOTAL, 1) * 100, 1))")
if [ "$(echo "$ERROR_RATE > 5" | bc)" -eq 1 ]; then
    echo "ERROR: PDF parse error rate too high ($ERROR_RATE%). Not starting EDGAR."
    log_stage "chain_aborted" "high_error_rate"
    echo "{\"status\":\"aborted\",\"reason\":\"high_error_rate\",\"error_rate\":$ERROR_RATE,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"}" > "$CHAIN_COMPLETE"
    exit 1
fi

# Start EDGAR parse
echo "Starting EDGAR HTML parse..."
log_stage "edgar_parse" "started"

cd "$DIR" && uv run python scripts/docling_reparse_edgar.py 2>&1 | tee -a /tmp/docling_edgar.log

log_stage "edgar_complete" "finished"

# Validate
echo "Running validation..."
log_stage "validation" "started"
cd "$DIR" && uv run python scripts/validate_parse_output.py 2>&1 || true
log_stage "validation" "finished"

# Write completion marker
CHAIN_END=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
echo "{\"status\":\"complete\",\"started\":\"$CHAIN_START\",\"finished\":\"$CHAIN_END\",\"timestamp\":\"$CHAIN_END\"}" > "$CHAIN_COMPLETE"
echo "Chain complete at $(date)."
log_stage "chain_complete" "done"
```

- [ ] **Step 2: Make executable and test syntax**

```bash
chmod +x scripts/chain_overnight.sh
bash -n scripts/chain_overnight.sh && echo "Syntax OK"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/chain_overnight.sh
git commit -m "feat: chain overnight wrapper with stage telemetry"
```

---

### Task 4: Council review + start chain (Mac Mini)

- [ ] **Step 1: Council review of EDGAR script + chain wrapper**

Dispatch to Claude, Gemini, and Codex:

```
Review scripts/docling_reparse_edgar.py and scripts/chain_overnight.sh.
These will run UNATTENDED OVERNIGHT on a Mac Mini.

Context: EDGAR files are SEC HTML filings wrapped in SGML. The script strips
the wrapper, splits pages, converts to Docling markdown. The chain wrapper
waits for the current PDF parse to finish, then runs the EDGAR parse.

Focus on:
1. Will SGML stripping work on all EDGAR file variants?
2. Will the page splitting produce correct page boundaries?
3. Can the chain wrapper miss a failed PDF parse and proceed anyway?
4. Any error handling gaps that could crash the overnight run?
5. Is the Docling HTML converter created once or per-file? (memory)

Report CRITICAL / IMPORTANT / SUGGESTION.
```

- [ ] **Step 2: Fix all findings**

- [ ] **Step 3: Start the chain**

```bash
nohup bash scripts/chain_overnight.sh >> /tmp/chain_overnight.log 2>&1 &
echo "Chain started PID $!"
```

- [ ] **Step 4: Verify chain is waiting**

```bash
tail -1 data/parsed_docling/_chain_log.jsonl
# Should show: {"stage":"waiting_for_pdf","status":"started",...}
```

---

### Task 5: Explorer landing page (MacBook Air)

**Files:**
- Modify: `explorer/app.py`

**Pre-requisite:** On the Air, create branch and rebuild DB:
```bash
git checkout main && git pull
git checkout -b feature/explorer-v2
rm -f data/db/corpus.duckdb
uv sync --all-extras
uv run corpus ingest --run-id explorer-dev-$(date +%Y%m%d)
uv run corpus build-pages --parsed-dir data/parsed_docling
uv run corpus build-markdown --parsed-dir data/parsed_docling
```

- [ ] **Step 1: Rewrite app.py with landing page**

Replace `explorer/app.py` with:

```python
"""Sovereign Bond Prospectus Explorer — V2.

Full-text search across sovereign bond prospectuses with structured
document detail view. Built for the IMF/World Bank Spring Meetings.
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Sovereign Bond Prospectus Explorer",
    page_icon="📜",
    layout="wide",
)

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")


def _missing_db_error():
    st.error(
        "No database available. Set MOTHERDUCK_TOKEN in Streamlit secrets, "
        "or run locally with data/db/corpus.duckdb present."
    )
    st.stop()


@st.cache_resource(ttl=3600)
def get_connection():
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
    if LOCAL_DB_PATH.exists():
        con = duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
        con.execute("INSTALL fts; LOAD fts")
        return con
    _missing_db_error()


def landing_page(con):
    """Corpus overview and search entry point."""
    st.title("Sovereign Bond Prospectus Explorer")

    st.markdown(
        "_An open-source, searchable corpus of sovereign bond prospectuses. "
        "Built by [Teal Insights](https://tealinsights.com) as SovTech infrastructure "
        "for sovereign debt research and climate finance._"
    )

    # Stats
    stats = con.execute("""
        SELECT
            COUNT(*) AS docs,
            COUNT(DISTINCT source) AS sources,
            COUNT(DISTINCT issuer_name) AS issuers
        FROM documents
    """).fetchone()

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", f"{stats[0]:,}")
    col2.metric("Sources", stats[1])
    col3.metric("Issuers", stats[2])

    st.markdown("---")
    st.markdown(
        "**This is an early version.** We'd love your feedback on what would be "
        "most useful for your work. Please reach out to share ideas for features, "
        "sources, or analysis you'd like to see."
    )


def search_page(con):
    """Full-text search with BM25 scoring."""
    query = st.text_input("Search prospectus text", placeholder="e.g., collective action clause, governing law, contingent liabilities")

    if not query:
        st.info("Enter a search term to search across all prospectus pages.")
        return

    # Source filter
    sources = con.execute("SELECT DISTINCT source FROM documents ORDER BY source").fetchdf()
    selected_sources = st.multiselect("Filter by source", sources["source"].tolist())

    source_filter = ""
    params = [query]
    if selected_sources:
        placeholders = ",".join(["?"] * len(selected_sources))
        source_filter = f"AND d.source IN ({placeholders})"
        params.extend(selected_sources)

    results = con.execute(f"""
        SELECT
            d.document_id,
            d.title,
            d.issuer_name,
            d.source,
            d.publication_date,
            dp.page_number,
            dp.page_text,
            fts_main_document_pages.match_bm25(dp.page_id, ?) AS score
        FROM document_pages dp
        JOIN documents d ON dp.document_id = d.document_id
        WHERE score IS NOT NULL
        {source_filter}
        ORDER BY score DESC
        LIMIT 50
    """, params).fetchdf()

    if results.empty:
        st.warning(f"No results for '{query}'")
        return

    st.markdown(f"**{len(results)} results** for _{query}_")

    for _, row in results.iterrows():
        with st.expander(
            f"**{row['issuer_name'] or row['title'] or row['document_id']}** "
            f"— {row['source']} — p.{row['page_number']} "
            f"— {row['publication_date'] or 'undated'}"
        ):
            # Show snippet with search term context
            text = row["page_text"] or ""
            # Find query in text for snippet
            lower_text = text.lower()
            query_lower = query.lower()
            idx = lower_text.find(query_lower)
            if idx >= 0:
                start = max(0, idx - 200)
                end = min(len(text), idx + len(query) + 200)
                snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")
                st.markdown(f"```\n{snippet}\n```")
            else:
                st.markdown(f"```\n{text[:400]}...\n```")

            if st.button("View full document", key=f"view_{row['document_id']}_{row['page_number']}"):
                st.session_state["view_doc_id"] = row["document_id"]
                st.session_state["view_page"] = row["page_number"]
                st.rerun()


def detail_page(con, doc_id, start_page=1):
    """Page-by-page document detail view."""
    if st.button("← Back to search"):
        del st.session_state["view_doc_id"]
        st.rerun()

    # Document metadata
    meta = con.execute("""
        SELECT document_id, title, issuer_name, source, publication_date,
               source_page_url, download_url, doc_type
        FROM documents WHERE document_id = ?
    """, [doc_id]).fetchone()

    if meta is None:
        st.error(f"Document {doc_id} not found")
        return

    st.title(meta[2] or meta[1] or f"Document {doc_id}")

    # Metadata sidebar
    col1, col2 = st.columns([3, 1])

    with col2:
        st.markdown("**Metadata**")
        st.markdown(f"**Source:** {meta[3]}")
        if meta[4]:
            st.markdown(f"**Date:** {meta[4]}")
        if meta[7]:
            st.markdown(f"**Type:** {meta[7]}")
        if meta[5]:
            st.markdown(f"[View original filing]({meta[5]})")
        if meta[6]:
            st.markdown(f"[Download PDF]({meta[6]})")

    with col1:
        # Page navigation
        page_count = con.execute(
            "SELECT MAX(page_number) FROM document_pages WHERE document_id = ?",
            [doc_id],
        ).fetchone()
        max_page = page_count[0] if page_count and page_count[0] else 1

        if max_page > 1:
            page_num = st.number_input(
                f"Page (1-{max_page})", min_value=1, max_value=max_page,
                value=min(start_page, max_page),
            )
        else:
            page_num = 1

        # Try markdown first (nicer rendering)
        md_row = con.execute(
            "SELECT markdown_text FROM document_markdown WHERE document_id = ?",
            [doc_id],
        ).fetchone()

        if md_row and max_page == 1:
            # Single-page doc with markdown: render directly (with size guard)
            md_text = md_row[0]
            if len(md_text) > 50000:
                st.markdown(md_text[:50000] + "\n\n*[Truncated — document too large for inline display]*")
            else:
                st.markdown(md_text)
        else:
            # Multi-page: show page text
            page_text = con.execute(
                "SELECT page_text FROM document_pages WHERE document_id = ? AND page_number = ?",
                [doc_id, page_num],
            ).fetchone()

            if page_text and page_text[0]:
                st.markdown(f"**Page {page_num} of {max_page}**")
                st.text(page_text[0])
            else:
                st.info(f"No text available for page {page_num}")


def main():
    con = get_connection()

    # Route based on session state
    if "view_doc_id" in st.session_state:
        detail_page(
            con,
            st.session_state["view_doc_id"],
            st.session_state.get("view_page", 1),
        )
    else:
        landing_page(con)
        st.markdown("---")
        search_page(con)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test locally**

```bash
cd explorer && uv run streamlit run app.py
```

Open in browser. Verify:
- Landing page shows stats
- Search works (try "collective action")
- Click through to detail page
- Back button works

- [ ] **Step 3: Commit**

```bash
git add explorer/app.py
git commit -m "feat: explorer v2 with FTS search and page-by-page detail"
```

---

### Task 6: Explorer polish (MacBook Air)

- [ ] **Step 1: Add Teal Insights branding**

Add to the top of `landing_page()`, after the title:

```python
    # Logo (if available)
    logo_path = Path(__file__).parent / "assets" / "teal-insights-logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=200)
```

Create `explorer/assets/` directory and add logo if available.

- [ ] **Step 2: Test on phone/different device**

Run Streamlit with `--server.address 0.0.0.0`:
```bash
uv run streamlit run explorer/app.py --server.address 0.0.0.0
```

Open on phone via `http://<air-ip>:8501`. Verify layout works on mobile.

- [ ] **Step 3: Commit**

```bash
git add explorer/
git commit -m "feat: explorer polish — branding, mobile layout"
```

---

### Task 7: Council review of explorer (MacBook Air)

- [ ] **Step 1: Dispatch council review**

Same pattern as previous reviews. Focus on:
1. Can `st.markdown()` on large documents crash Streamlit?
2. Is the FTS query SQL-injection safe? (parameterized?)
3. Will the MotherDuck connection work from Streamlit Cloud?
4. Any UX issues for the demo audience?

- [ ] **Step 2: Fix findings**

- [ ] **Step 3: Publish to MotherDuck**

```bash
export MOTHERDUCK_TOKEN=<token>
uv run corpus publish-motherduck
```

- [ ] **Step 4: Deploy to Streamlit Cloud and test**

Push branch, configure Streamlit Cloud, set secrets, verify shareable URL.

- [ ] **Step 5: Warm up — ping URL 5 minutes before any demo**

---

### Task 8: Congo manual ingest (either machine)

- [ ] **Step 1: Download Congo prospectus**

Find and download the Republic of the Congo April 2026 Eurobond prospectus
from LSE RNS. Save to `data/original/lse_rns__congo_2026.pdf`.

- [ ] **Step 2: Create manifest entry**

Add to `data/manifests/lse_rns_manifest.jsonl`:
```json
{"storage_key": "lse_rns__congo_2026", "source": "lse_rns", "title": "Republic of the Congo - Eurobond 2026", "issuer_name": "Republic of the Congo", "doc_type": "prospectus", "publication_date": "2026-04-08", "source_page_url": "<RNS URL>", "download_url": "<PDF URL>"}
```

- [ ] **Step 3: Parse, ingest, verify**

```bash
# Parse the single PDF
uv run python -c "
from scripts.docling_reparse import process_one_pdf
result = process_one_pdf(('lse_rns__congo_2026', 'data/original/lse_rns__congo_2026.pdf'))
print(result)
"

# Re-ingest
uv run corpus ingest --run-id congo-manual
uv run corpus build-pages --parsed-dir data/parsed_docling
uv run corpus build-markdown --parsed-dir data/parsed_docling

# Verify search
uv run python -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb')
r = con.execute(\"\"\"
    SELECT d.issuer_name, dp.page_number
    FROM document_pages dp JOIN documents d ON dp.document_id = d.document_id
    WHERE dp.page_text LIKE '%contingent liabilities%' AND d.issuer_name LIKE '%Congo%'
\"\"\").fetchall()
print(r)
"
```

Expected: returns Congo on pages ~103-104.

- [ ] **Step 4: Republish to MotherDuck**

```bash
export MOTHERDUCK_TOKEN=<token>
uv run corpus publish-motherduck
```

---

### Task 9: Monday morning pipeline (Mac Mini or Air)

- [ ] **Step 1: Verify chain completed**

```bash
cat data/parsed_docling/_chain_complete.json
tail -5 data/parsed_docling/_chain_log.jsonl
```

- [ ] **Step 2: Verify Dropbox sync (if running from Air)**

```bash
ls data/parsed_docling/edgar__*.jsonl | wc -l  # expect ~3100+
ls data/parsed_docling/*.jsonl | wc -l          # expect ~9500+
```

- [ ] **Step 3: Rebuild full corpus DB**

```bash
rm -f data/db/corpus.duckdb
uv run corpus ingest --run-id final-$(date +%Y%m%d)
uv run corpus build-pages --parsed-dir data/parsed_docling
uv run corpus build-markdown --parsed-dir data/parsed_docling
```

- [ ] **Step 4: Publish to MotherDuck**

```bash
export MOTHERDUCK_TOKEN=<token>
uv run corpus publish-motherduck
```

- [ ] **Step 5: Warm up Streamlit and verify**

Ping the Streamlit Cloud URL. Search "contingent liabilities" — verify Congo
shows up. Search "collective action" — verify results from multiple sources.
Test from phone in incognito.

---

### Task 10: Merge branches

- [ ] **Step 1: Merge Mac Mini branch to main**

```bash
# On Mac Mini
git checkout main && git pull
git merge feature/docling-bug-fix-and-sprint-v2
git push
```

- [ ] **Step 2: Rebase explorer branch**

```bash
# On MacBook Air
git checkout feature/explorer-v2
git fetch origin && git rebase origin/main
# Resolve any conflicts (likely SESSION-HANDOFF.md)
git push -u origin feature/explorer-v2
```

- [ ] **Step 3: Create PR and merge**

```bash
gh pr create --title "Explorer V2 with FTS search" --body "..."
# Get review if time, or merge directly given time pressure
```
