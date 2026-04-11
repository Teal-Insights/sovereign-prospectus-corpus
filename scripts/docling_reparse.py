#!/usr/bin/env python3
"""Docling PDF re-parse — parallel extraction with supervised process pool.

Converts all PDF documents from PyMuPDF format to Docling, producing
clean flowing text with document structure.

Outputs:
  data/parsed_docling/{storage_key}.md    — Docling markdown
  data/parsed_docling/{storage_key}.jsonl — plain text, same format as data/parsed/

Usage:
  export DOCLING_DEVICE=auto
  export DOCLING_NUM_THREADS=3
  python scripts/docling_reparse.py [--workers 4] [--timeout 300]

Designed to run unattended for 4-5 hours on a Mac Mini M4 Pro.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, datetime
from pathlib import Path

from corpus.parsers.markdown import strip_markdown

# ── Configuration ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "parsed_docling"
ERRORS_LOG = OUTPUT_DIR / "_errors.log"
PROGRESS_LOG = OUTPUT_DIR / "_progress.jsonl"
SUMMARY_PATH = OUTPUT_DIR / "_summary.json"

# Global shutdown flag
shutdown_requested = False


def handle_signal(signum: int, _frame: object) -> None:
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    global shutdown_requested
    shutdown_requested = True
    logging.warning("Shutdown requested (signal %d). Finishing current documents...", signum)


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


# ── Logging setup ──────────────────────────────────────────────────


def setup_logging() -> None:
    """Configure logging to stdout and error file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Error-only file handler
    error_handler = logging.FileHandler(str(ERRORS_LOG), mode="a")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(error_handler)


# ── PDF discovery ──────────────────────────────────────────────────


def discover_pdfs() -> list[tuple[str, Path]]:
    """Find all PDFs to process. Returns list of (storage_key, path)."""
    pdfs: list[tuple[str, Path]] = []

    # PDIP PDFs
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


def filter_already_done(pdfs: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """Skip PDFs that already have completed output (resume support)."""
    remaining: list[tuple[str, Path]] = []
    for storage_key, pdf_path in pdfs:
        output_jsonl = OUTPUT_DIR / f"{storage_key}.jsonl"
        if output_jsonl.exists() and output_jsonl.stat().st_size > 0:
            continue  # Already done
        remaining.append((storage_key, pdf_path))
    return remaining


# ── Single-document worker ─────────────────────────────────────────


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
        from importlib.metadata import version as pkg_version

        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        doc = result.document

        # Actual PDF page count from Docling
        page_count = doc.num_pages()

        # Full-document markdown for the .md sidecar
        full_markdown = doc.export_to_markdown()

        # Per-page: markdown → plain text for JSONL
        pages_text: dict[int, str] = {}
        for page_no in sorted(doc.pages.keys()):
            page_md = doc.export_to_markdown(page_no=page_no)
            pages_text[page_no] = strip_markdown(page_md)

        elapsed = time.monotonic() - start
        docling_version = pkg_version("docling")

        # Determine parse_status using the same heuristic as cli.py
        total_chars = sum(len(t) for t in pages_text.values())
        if page_count == 0 or total_chars == 0:
            parse_status = "parse_empty"
        else:
            thin_pages = sum(1 for t in pages_text.values() if len(t) < 50)
            parse_status = "parse_partial" if thin_pages > page_count * 0.5 else "parse_ok"

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
                "parse_status": parse_status,
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


# ── Supervised execution ───────────────────────────────────────────


def run_supervised(
    pdf_list: list[tuple[str, Path]],
    max_workers: int,
    timeout: int,
) -> dict:
    """Process all PDFs with automatic pool restart on worker death."""
    global shutdown_requested
    total = len(pdf_list)
    remaining = [(sk, str(p)) for sk, p in pdf_list]
    completed = 0
    failed = 0
    skipped = 0
    mps_errors = 0
    pool_restarts = 0
    start_time = time.monotonic()

    logging.info("Starting Docling re-parse: %d documents, %d workers", total, max_workers)

    while remaining and not shutdown_requested:
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for args in remaining[:]:
                    if shutdown_requested:
                        break
                    futures[pool.submit(process_one_pdf, args)] = args

                for future in as_completed(futures):
                    if shutdown_requested:
                        break

                    args = futures[future]
                    storage_key = args[0]

                    try:
                        result = future.result(timeout=timeout)
                    except TimeoutError:
                        result = {
                            "status": "timeout",
                            "storage_key": storage_key,
                            "page_count": 0,
                            "elapsed_s": timeout,
                            "error": f"Exceeded {timeout}s timeout",
                        }
                    except Exception as exc:
                        result = {
                            "status": "failed",
                            "storage_key": storage_key,
                            "page_count": 0,
                            "elapsed_s": 0,
                            "error": f"{type(exc).__name__}: {exc}",
                        }

                    # Remove from remaining
                    if args in remaining:
                        remaining.remove(args)

                    # Track results
                    if result["status"] == "success":
                        completed += 1
                    elif result["status"] == "mps_error":
                        mps_errors += 1
                        failed += 1
                    elif result["status"] == "timeout":
                        skipped += 1
                    else:
                        failed += 1

                    # Log progress
                    done = completed + failed + skipped
                    if result["status"] == "success":
                        logging.info(
                            "[%d/%d] %s — %d pages — %.1fs — OK",
                            done,
                            total,
                            result["storage_key"],
                            result["page_count"],
                            result["elapsed_s"],
                        )
                    else:
                        logging.warning(
                            "[%d/%d] %s — %s — %.1fs — %s",
                            done,
                            total,
                            result["storage_key"],
                            result["status"],
                            result["elapsed_s"],
                            result.get("error", ""),
                        )
                        logging.error(
                            "FAILED: %s — %s",
                            result["storage_key"],
                            result.get("error", ""),
                        )

                    # Write progress
                    write_progress(result)

                    # Periodic summary
                    if done % 50 == 0 and done > 0:
                        elapsed = time.monotonic() - start_time
                        rate = done / elapsed if elapsed > 0 else 0
                        eta = (total - done) / rate if rate > 0 else 0
                        logging.info(
                            "Progress: %d/%d (%.1f%%) — %d OK, %d failed, %d skipped — "
                            "ETA %.0fm — pool restarts: %d",
                            done,
                            total,
                            100 * done / total,
                            completed,
                            failed,
                            skipped,
                            eta / 60,
                            pool_restarts,
                        )

                        # Check disk space
                        usage = shutil.disk_usage(str(OUTPUT_DIR))
                        free_gb = usage.free / (1024**3)
                        if free_gb < 1.0:
                            logging.error("Low disk space: %.1f GB free. Stopping.", free_gb)
                            shutdown_requested = True

                    # MPS fallback
                    if mps_errors >= 3:
                        logging.warning(
                            "%d MPS errors. Setting DOCLING_DEVICE=cpu for remaining docs.",
                            mps_errors,
                        )
                        os.environ["DOCLING_DEVICE"] = "cpu"
                        mps_errors = -999  # Don't trigger again

        except BrokenProcessPool:
            pool_restarts += 1
            logging.warning(
                "Pool crashed (restart #%d). %d documents remaining.",
                pool_restarts,
                len(remaining),
            )
            if pool_restarts > 10:
                logging.error("Too many pool restarts. Stopping.")
                break
            continue

    elapsed_total = time.monotonic() - start_time

    summary = {
        "total": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "pool_restarts": pool_restarts,
        "elapsed_s": round(elapsed_total, 1),
        "elapsed_human": f"{elapsed_total / 3600:.1f}h",
        "shutdown_requested": shutdown_requested,
        "finished_at": datetime.now(UTC).isoformat(),
    }

    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))
    logging.info("Done. %s", json.dumps(summary, indent=2))

    return summary


def write_progress(result: dict) -> None:
    """Append a progress entry (advisory, not for correctness)."""
    entry = {**result, "timestamp": datetime.now(UTC).isoformat()}
    line = json.dumps(entry) + "\n"
    with PROGRESS_LOG.open("a") as f:
        f.write(line)
        f.flush()


# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Docling PDF re-parse")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--timeout", type=int, default=300, help="Per-document timeout in seconds")
    parser.add_argument("--limit", type=int, default=None, help="Max documents to process")
    args = parser.parse_args()

    setup_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Log startup config
    logging.info("Docling re-parse starting")
    logging.info("  DOCLING_DEVICE=%s", os.environ.get("DOCLING_DEVICE", "not set"))
    logging.info("  DOCLING_NUM_THREADS=%s", os.environ.get("DOCLING_NUM_THREADS", "not set"))
    logging.info("  Workers: %d", args.workers)
    logging.info("  Timeout: %ds", args.timeout)
    logging.info("  Output: %s", OUTPUT_DIR)

    # Discover and filter
    all_pdfs = discover_pdfs()
    logging.info("Discovered %d PDFs", len(all_pdfs))

    remaining = filter_already_done(all_pdfs)
    logging.info(
        "After resume filter: %d remaining (%d already done)",
        len(remaining),
        len(all_pdfs) - len(remaining),
    )

    if args.limit:
        remaining = remaining[: args.limit]
        logging.info("Limited to %d documents", len(remaining))

    if not remaining:
        logging.info("Nothing to process. Exiting.")
        return

    # Prewarm: test one document first to catch bootstrap failures
    logging.info("Prewarming on first document...")
    prewarm_result = process_one_pdf((remaining[0][0], str(remaining[0][1])))
    if prewarm_result["status"] != "success":
        logging.error("Prewarm failed: %s. Check Docling installation.", prewarm_result["error"])
        sys.exit(1)
    logging.info(
        "Prewarm OK: %s — %d pages in %.1fs",
        prewarm_result["storage_key"],
        prewarm_result["page_count"],
        prewarm_result["elapsed_s"],
    )
    write_progress(prewarm_result)

    # Remove prewarmed doc from remaining
    remaining = remaining[1:]

    # Run supervised
    run_supervised(remaining, args.workers, args.timeout)


if __name__ == "__main__":
    main()
