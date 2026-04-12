#!/usr/bin/env python3
"""EDGAR HTML/text re-parse — SGML stripping + Docling markdown.

Parses SEC EDGAR .htm and .txt filings:
1. Strip SGML wrapper (<DOCUMENT><TEXT>...</TEXT></DOCUMENT>)
2. Split into pages (CSS page-breaks for HTML, <PAGE> for text)
3. Generate structured markdown via Docling HTML pipeline (no ML models)

Usage:
    uv run python scripts/docling_reparse_edgar.py [--limit N]
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

# ── Configuration ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "parsed_docling"
ERRORS_LOG = OUTPUT_DIR / "_errors.log"
PROGRESS_LOG = OUTPUT_DIR / "_progress.jsonl"

_ENCODINGS = ("utf-8", "cp1252", "latin-1")
_SGML_TEXT_RE = re.compile(r"<TEXT>\s*(.*?)\s*</TEXT>", re.DOTALL | re.IGNORECASE)
_PAGE_BREAK_BEFORE_RE = re.compile(r"page-break-before\s*:\s*always", re.IGNORECASE)
_PAGE_BREAK_AFTER_RE = re.compile(r"page-break-after\s*:\s*always", re.IGNORECASE)
_PAGE_MARKER = "<PAGE>"
_HTML_TAG_RE = re.compile(r"<(?:html|body|div|table|p|h[1-6])\b", re.IGNORECASE)


# ── SGML stripping ────────────────────────────────────────────────


def strip_sgml_wrapper(raw: str) -> tuple[str, bool]:
    """Extract content from EDGAR SGML envelope.

    Returns (content, is_html) where is_html indicates whether the
    extracted content appears to be HTML (vs plain text).
    """
    # Warn on multi-document filings
    text_count = raw.upper().count("<TEXT>")
    if text_count > 1:
        logging.warning("Multi-<TEXT> filing detected (%d blocks). Using first block.", text_count)

    match = _SGML_TEXT_RE.search(raw)
    content = match.group(1) if match else raw

    # Determine if content is HTML or plain text
    is_html = bool(_HTML_TAG_RE.search(content[:2000]))
    return content, is_html


# ── Page splitting ────────────────────────────────────────────────


def split_htm_pages(html: str) -> list[str]:
    """Split HTML on CSS page-break markers. Returns list of plain text pages.

    Matches the logic in src/corpus/parsers/html_parser.py exactly:
    - page-break-before: insert marker BEFORE the element
    - page-break-after: insert marker AFTER the element
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Insert page-break markers (separate handling for before/after)
    marker = "\x00PAGE_BREAK\x00"
    found = False
    for tag in soup.find_all(True):
        style = tag.get("style", "")
        if not isinstance(style, str):
            continue
        if _PAGE_BREAK_BEFORE_RE.search(style):
            tag.insert_before(marker)
            found = True
        elif _PAGE_BREAK_AFTER_RE.search(style):
            tag.insert_after(marker)
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

    Matches the logic in src/corpus/parsers/text_parser.py.
    """
    if _PAGE_MARKER in text:
        pages = [p.strip() for p in text.split(_PAGE_MARKER)]
        if pages and not pages[0]:
            pages.pop(0)
        if pages and not pages[-1]:
            pages.pop()
        return pages if pages else [text]
    else:
        return [text]


# ── Docling markdown conversion ───────────────────────────────────


def create_html_converter():
    """Create a Docling converter restricted to HTML format.

    Returns a singleton-like converter. Called once in main(), passed to
    all processing functions. Using allowed_formats=[InputFormat.HTML]
    ensures SimplePipeline (BeautifulSoup) is used, NOT StandardPdfPipeline
    (ML models).
    """
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter

    return DocumentConverter(allowed_formats=[InputFormat.HTML])


def html_to_markdown(converter, html_content: str) -> str:
    """Convert HTML string to structured markdown via Docling.

    Uses SimplePipeline (BeautifulSoup) — no ML models, no memory leak.
    Converter must be passed in (not created per-call).
    """
    from docling.datamodel.document import DocumentStream

    stream = DocumentStream(
        name="page.html",
        stream=io.BytesIO(html_content.encode("utf-8")),
    )
    result = converter.convert(stream)
    return result.document.export_to_markdown()


# ── Single-file processing ────────────────────────────────────────


def process_one_edgar(storage_key: str, file_path: Path, converter) -> dict:
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

        # Step 3: Generate full-document markdown
        if is_html and content.strip():
            full_markdown = html_to_markdown(converter, content)
        else:
            full_markdown = "\n\n".join(pages_text)

        elapsed = time.monotonic() - start
        from importlib.metadata import version as pkg_version

        docling_version = pkg_version("docling")

        # Determine parse status
        stripped_lengths = [len(p.strip()) for p in pages_text]
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
            for i, page_text in enumerate(pages_text):
                f.write(
                    json.dumps(
                        {
                            "page": i,
                            "text": page_text,
                            "char_count": len(page_text),
                        }
                    )
                    + "\n"
                )
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
            if path.suffix in (".htm", ".html") or path.suffix == ".txt":
                files.append((path.stem, path))
            # .paper files skipped (empty stubs)
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


# ── Progress logging ──────────────────────────────────────────────


def write_progress(result: dict) -> None:
    """Append progress entry."""
    entry = {
        **result,
        "memory_gb": 0,
        "workers": 1,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    with PROGRESS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()


# ── Main ──────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="EDGAR HTML/text re-parse")
    parser.add_argument("--limit", type=int, default=None, help="Max files to process")
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

    # Clean stale .part files for EDGAR
    for part_file in OUTPUT_DIR.glob("edgar__*.jsonl.part"):
        part_file.unlink(missing_ok=True)
    for part_file in OUTPUT_DIR.glob("edgar__*.md.part"):
        part_file.unlink(missing_ok=True)

    # Discover and filter
    all_files = discover_edgar_files()
    remaining = filter_already_done(all_files)
    logging.info(
        "Discovered %d EDGAR files, %d remaining after resume filter",
        len(all_files),
        len(remaining),
    )

    if args.limit:
        remaining = remaining[: args.limit]

    if not remaining:
        logging.info("Nothing to process.")
        return

    # Create Docling converter ONCE (singleton for entire run)
    # allowed_formats=[InputFormat.HTML] ensures SimplePipeline, not StandardPdfPipeline
    logging.info("Creating Docling HTML converter (SimplePipeline, no ML models)...")
    converter = create_html_converter()

    # Smoke test: first 5 files
    logging.info("Smoke testing first %d files...", min(5, len(remaining)))
    smoke_failures = 0
    smoke_count = min(5, len(remaining))
    for sk, path in remaining[:smoke_count]:
        result = process_one_edgar(sk, path, converter)
        if result["status"] != "success":
            logging.error("Smoke test FAILED: %s — %s", sk, result["error"])
            smoke_failures += 1
        else:
            logging.info(
                "Smoke OK: %s — %d pages in %.1fs",
                sk,
                result["page_count"],
                result["elapsed_s"],
            )
        write_progress(result)

    if smoke_failures > 2:
        logging.error(
            "Too many smoke test failures (%d/%d). Aborting.", smoke_failures, smoke_count
        )
        sys.exit(1)

    # Process remaining (skip smoke-tested files)
    remaining = remaining[smoke_count:]
    completed = smoke_count - smoke_failures
    failed = smoke_failures
    start_time = time.monotonic()
    total = len(all_files)

    for _i, (storage_key, path) in enumerate(remaining):
        result = process_one_edgar(storage_key, path, converter)

        if result["status"] == "success":
            completed += 1
        else:
            failed += 1
            logging.error("FAILED: %s — %s", storage_key, result["error"])

        done = completed + failed
        if result["status"] == "success":
            logging.info(
                "[%d/%d] %s — %d pages — %.1fs — OK",
                done,
                total,
                storage_key,
                result["page_count"],
                result["elapsed_s"],
            )
        write_progress(result)

        # Periodic summary
        if done % 100 == 0:
            elapsed = time.monotonic() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            remaining_count = total - done
            eta = remaining_count / rate / 60 if rate > 0 else 0
            logging.info(
                "Progress: %d/%d — %d OK, %d failed — %.1f files/min — ETA %.0fm",
                done,
                total,
                completed,
                failed,
                rate * 60,
                eta,
            )

    elapsed_total = time.monotonic() - start_time
    summary = {
        "total": total,
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
