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
from concurrent.futures import ProcessPoolExecutor
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
    """Skip PDFs that already have completed output (resume support).

    Both .jsonl AND .md must exist — if one is missing (crash between
    the two atomic writes), the document is re-processed.
    """
    remaining: list[tuple[str, Path]] = []
    for storage_key, pdf_path in pdfs:
        output_jsonl = OUTPUT_DIR / f"{storage_key}.jsonl"
        output_md = OUTPUT_DIR / f"{storage_key}.md"
        if (
            output_jsonl.exists()
            and output_jsonl.stat().st_size > 0
            and output_md.exists()
            and output_md.stat().st_size > 0
        ):
            continue  # Both outputs present
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
        # Iterate range(1, page_count+1) to guarantee contiguous output
        # even if doc.pages has gaps (Docling sometimes skips empty pages)
        pages_text: dict[int, str] = {}
        for page_no in range(1, page_count + 1):
            if page_no in doc.pages:
                page_md = doc.export_to_markdown(page_no=page_no)
                pages_text[page_no] = strip_markdown(page_md)
            else:
                pages_text[page_no] = ""

        elapsed = time.monotonic() - start
        docling_version = pkg_version("docling")

        # Determine parse_status — must match cli.py:830 logic exactly
        stripped_lengths = [len(t.strip()) for t in pages_text.values()]
        total_chars = sum(stripped_lengths)
        if page_count == 0 or total_chars == 0:
            parse_status = "parse_empty"
        else:
            empty_pages = sum(1 for sl in stripped_lengths if sl < 50)
            parse_status = (
                "parse_empty"
                if empty_pages == page_count
                else "parse_partial"
                if empty_pages > page_count * 0.5
                else "parse_ok"
            )

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
    """Process all PDFs with batched submission and automatic pool restart.

    Key design decisions (from Codex/Gemini code reviews):
    - Submit in small batches (max_workers * 2), NOT the entire queue.
      This prevents a pool crash from removing thousands of queued items.
    - Use concurrent.futures.wait() with a timeout to detect hung workers,
      since as_completed + future.result(timeout) is ineffective.
    - On BrokenProcessPool, re-check output files to distinguish completed
      items from truly crashed ones.
    """
    from concurrent.futures import FIRST_COMPLETED, wait

    global shutdown_requested
    total = len(pdf_list)
    remaining = [(sk, str(p)) for sk, p in pdf_list]
    completed = 0
    failed = 0
    skipped = 0
    mps_errors = 0
    pool_restarts = 0
    start_time = time.monotonic()
    batch_size = max_workers * 2

    logging.info("Starting Docling re-parse: %d documents, %d workers", total, max_workers)

    while remaining and not shutdown_requested:
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                # Submit in batches to limit blast radius on pool crash
                futures: dict[object, tuple[str, str]] = {}

                while (remaining or futures) and not shutdown_requested:
                    # Top up the futures pool to batch_size
                    while remaining and len(futures) < batch_size:
                        args = remaining.pop(0)
                        fut = pool.submit(process_one_pdf, args)
                        futures[fut] = args

                    if not futures:
                        break

                    # Wait for at least one future with a global timeout
                    done_set, _pending = wait(
                        futures.keys(), timeout=timeout, return_when=FIRST_COMPLETED
                    )

                    if not done_set:
                        # Timeout: no future completed within timeout period.
                        # Cancel all pending and log as timeouts.
                        for fut, args in list(futures.items()):
                            fut.cancel()
                            sk = args[0]
                            skipped += 1
                            logging.warning("TIMEOUT: %s (no progress in %ds)", sk, timeout)
                            write_progress(
                                {
                                    "status": "timeout",
                                    "storage_key": sk,
                                    "page_count": 0,
                                    "elapsed_s": timeout,
                                    "error": f"Exceeded {timeout}s timeout",
                                }
                            )
                        futures.clear()
                        continue

                    for future in done_set:
                        args = futures.pop(future)
                        storage_key = args[0]

                        try:
                            result = future.result()
                        except Exception as exc:
                            result = {
                                "status": "failed",
                                "storage_key": storage_key,
                                "page_count": 0,
                                "elapsed_s": 0,
                                "error": f"{type(exc).__name__}: {exc}",
                            }

                        # Track results
                        if result["status"] == "success":
                            completed += 1
                        elif result["status"] == "mps_error":
                            mps_errors += 1
                            failed += 1
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
                                "FAILED: %s — %s", result["storage_key"], result.get("error", "")
                            )

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
                            usage = shutil.disk_usage(str(OUTPUT_DIR))
                            free_gb = usage.free / (1024**3)
                            if free_gb < 1.0:
                                logging.error("Low disk space: %.1f GB free. Stopping.", free_gb)
                                shutdown_requested = True

                        if mps_errors >= 3:
                            logging.warning(
                                "%d MPS errors. Setting DOCLING_DEVICE=cpu.", mps_errors
                            )
                            os.environ["DOCLING_DEVICE"] = "cpu"
                            mps_errors = -999

        except BrokenProcessPool:
            pool_restarts += 1
            # Only the small batch was in-flight. Re-check which actually
            # completed (have output files) vs truly crashed.
            crashed_keys = []
            for args in futures.values():
                sk = args[0]
                jsonl_out = OUTPUT_DIR / f"{sk}.jsonl"
                md_out = OUTPUT_DIR / f"{sk}.md"
                if jsonl_out.exists() and md_out.exists():
                    completed += 1  # Actually finished before crash
                else:
                    crashed_keys.append(sk)
                    failed += 1
            # Don't put crashed items back in remaining — they caused the crash
            futures.clear()
            logging.warning(
                "Pool crashed (restart #%d). %d in-flight, %d crashed: %s. %d remaining.",
                pool_restarts,
                len(crashed_keys) + (completed - completed),
                len(crashed_keys),
                crashed_keys[:5],
                len(remaining),
            )
            for sk in crashed_keys:
                logging.error("CRASHED (pool death): %s", sk)
                write_progress(
                    {
                        "status": "pool_crash",
                        "storage_key": sk,
                        "page_count": 0,
                        "elapsed_s": 0,
                        "error": "BrokenProcessPool",
                    }
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
    parser.add_argument("--timeout", type=int, default=600, help="Per-document timeout in seconds")
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

    # Pre-flight checks
    usage = shutil.disk_usage(str(PROJECT_ROOT))
    free_gb = usage.free / (1024**3)
    logging.info("  Disk free: %.1f GB", free_gb)
    if free_gb < 5.0:
        logging.error("Less than 5 GB free disk space. Aborting.")
        sys.exit(1)

    # Clean up stale .part files from previous crashed runs
    for part_file in OUTPUT_DIR.glob("*.part"):
        logging.warning("Removing stale .part file: %s", part_file.name)
        part_file.unlink()

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
