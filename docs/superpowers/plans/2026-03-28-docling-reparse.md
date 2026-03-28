# Docling PDF Re-parse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-parse all 1,468 PDF documents (823 PDIP + 645 NSM) using Docling instead of PyMuPDF, producing clean flowing text with document structure. Output to `data/parsed_docling/` without touching existing parsed data.

**Architecture:** A standalone script `scripts/docling_reparse.py` with a supervised process pool (4 workers). Each worker runs Docling's DocumentConverter with Metal/MPS acceleration. Outputs both markdown (`.md` for human reading) and plain text JSONL (`.jsonl` for the grep pipeline). Checkpointed via file-system presence (atomic writes). Robust to worker crashes, OOM, MPS errors, and corrupt PDFs.

**Tech Stack:** Python 3.12, Docling, concurrent.futures, PyTorch with MPS/Metal

**IMPORTANT: This script runs unattended on a Mac Mini M4 Pro (64GB RAM) via Claude Code with `--dangerously-skip-permissions`. It must be robust enough to run for 4-5 hours without human intervention.**

**Spec:** `docs/superpowers/specs/2026-03-28-shiny-display-and-docling-reparse-design.md` (Workstream B)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `scripts/docling_reparse.py` | Standalone re-parse script with supervised pool |

### Output (gitignored)

| Path | Content |
|------|---------|
| `data/parsed_docling/{storage_key}.md` | Docling markdown output |
| `data/parsed_docling/{storage_key}.jsonl` | Plain text JSONL (same format as data/parsed/) |
| `data/parsed_docling/_progress.jsonl` | Advisory progress log |
| `data/parsed_docling/_errors.log` | Error tracebacks |
| `data/parsed_docling/_summary.json` | Final run summary |

---

## Task 1: Create the Docling Re-parse Script

**Files:**
- Create: `scripts/docling_reparse.py`

- [ ] **Step 1: Create the script**

Create `scripts/docling_reparse.py`:

```python
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
import re
import shutil
import signal
import sys
import time
from concurrent.futures import BrokenProcessPool, ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

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
    global shutdown_requested  # noqa: PLW0603
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
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
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


# ── Markdown to plain text ─────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """Strip markdown formatting for grep consumption."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)  # bold/italic
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # list markers
    text = re.sub(r"^\|.*\|$", "", text, flags=re.MULTILINE)  # table rows
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)  # horizontal rules
    return text


# ── Single-document worker ─────────────────────────────────────────

def process_one_pdf(args: tuple[str, str]) -> dict:
    """Process a single PDF with Docling. Runs in a worker process.

    Args:
        args: (storage_key, pdf_path_str)

    Returns:
        dict with status, storage_key, page_count, elapsed_s, error
    """
    storage_key, pdf_path_str = args
    pdf_path = Path(pdf_path_str)
    start = time.monotonic()

    try:
        # Import inside worker so each process loads its own models
        from docling.document_converter import DocumentConverter
        from docling_core.types.doc import SectionHeaderItem, TextItem

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        doc = result.document

        # Get markdown output
        markdown = doc.export_to_markdown()

        # Get per-page plain text
        pages: dict[int, list[str]] = {}
        for item, _level in doc.iterate_items():
            if isinstance(item, (TextItem, SectionHeaderItem)):
                for prov in item.prov:
                    pages.setdefault(prov.page_no, []).append(item.text)
                    break

        page_count = len(pages)
        elapsed = time.monotonic() - start

        # Write markdown output (atomic)
        md_path = OUTPUT_DIR / f"{storage_key}.md"
        md_part = md_path.with_suffix(".md.part")
        md_part.write_text(markdown)
        os.replace(str(md_part), str(md_path))

        # Write JSONL output (atomic) — plain text, not markdown
        jsonl_path = OUTPUT_DIR / f"{storage_key}.jsonl"
        jsonl_part = jsonl_path.with_suffix(".jsonl.part")
        with jsonl_part.open("w") as f:
            header = {
                "storage_key": storage_key,
                "page_count": page_count,
                "parse_tool": "docling",
                "parse_version": "2.0",
                "parse_status": "parse_ok" if page_count > 0 else "parse_empty",
                "parsed_at": datetime.now(UTC).isoformat(),
            }
            f.write(json.dumps(header) + "\n")
            for page_no in sorted(pages.keys()):
                page_text = "\n".join(pages[page_no])
                # Strip any markdown from individual text items
                page_text = strip_markdown(page_text)
                page_record = {
                    "page": page_no - 1,  # Convert to 0-indexed
                    "text": page_text,
                    "char_count": len(page_text),
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

        # If MPS error, flag it
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
        batch_start = len(remaining)
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
                            done, total, result["storage_key"],
                            result["page_count"], result["elapsed_s"],
                        )
                    else:
                        logging.warning(
                            "[%d/%d] %s — %s — %.1fs — %s",
                            done, total, result["storage_key"],
                            result["status"], result["elapsed_s"],
                            result.get("error", ""),
                        )
                        logging.error(
                            "FAILED: %s — %s", result["storage_key"], result.get("error", ""),
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
                            done, total, 100 * done / total,
                            completed, failed, skipped,
                            eta / 60, pool_restarts,
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
                pool_restarts, len(remaining),
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
    logging.info("After resume filter: %d remaining (%d already done)", len(remaining), len(all_pdfs) - len(remaining))

    if args.limit:
        remaining = remaining[:args.limit]
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
    logging.info("Prewarm OK: %s — %d pages in %.1fs", prewarm_result["storage_key"], prewarm_result["page_count"], prewarm_result["elapsed_s"])
    write_progress(prewarm_result)

    # Remove prewarmed doc from remaining
    remaining = remaining[1:]

    # Run supervised
    run_supervised(remaining, args.workers, args.timeout)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with a small batch**

```bash
export DOCLING_DEVICE=auto
export DOCLING_NUM_THREADS=3
uv run python3 scripts/docling_reparse.py --workers 2 --limit 5
```

Expected: 5 documents processed, output in `data/parsed_docling/`. Check one output:

```bash
ls data/parsed_docling/*.jsonl | head -5
head -2 data/parsed_docling/pdip__*.jsonl | head -10
cat data/parsed_docling/_summary.json
```

- [ ] **Step 3: Verify output format matches existing parsed JSONL**

```bash
uv run python3 -c "
import json
from pathlib import Path

# Check a Docling output
docling_files = sorted(Path('data/parsed_docling').glob('*.jsonl'))
if docling_files:
    with docling_files[0].open() as f:
        header = json.loads(f.readline())
        page = json.loads(f.readline())
    print('Docling header:', header)
    print('Docling page keys:', list(page.keys()))
    print('Page text sample:', page['text'][:200])
    print()

# Compare with existing PyMuPDF output
key = docling_files[0].stem
pymupdf = Path(f'data/parsed/{key}.jsonl')
if pymupdf.exists():
    with pymupdf.open() as f:
        header2 = json.loads(f.readline())
        page2 = json.loads(f.readline())
    print('PyMuPDF header:', header2)
    print('PyMuPDF page text sample:', page2['text'][:200])
"
```

Verify: same JSONL structure (header with `storage_key`, `page_count`, `parse_tool`; pages with `page`, `text`, `char_count`).

- [ ] **Step 4: Verify resume works**

```bash
# Run again — should skip already-done docs
uv run python3 scripts/docling_reparse.py --workers 2 --limit 5
# Should see "After resume filter: 0 remaining (5 already done)"
```

- [ ] **Step 5: Run ruff check**

```bash
uv run ruff check scripts/docling_reparse.py
uv run ruff format --check scripts/docling_reparse.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "feat: Docling re-parse script with supervised pool and resume support"
```

---

## Task 2: Run Full Re-parse (Unattended)

**No new files — operational task.**

- [ ] **Step 1: Start the full re-parse**

```bash
export DOCLING_DEVICE=auto
export DOCLING_NUM_THREADS=3
nohup uv run python3 scripts/docling_reparse.py --workers 4 > data/parsed_docling/_stdout.log 2>&1 &
echo $! > data/parsed_docling/_pid.txt
echo "Started PID $(cat data/parsed_docling/_pid.txt). Tail log with: tail -f data/parsed_docling/_stdout.log"
```

- [ ] **Step 2: Verify it's running**

```bash
tail -20 data/parsed_docling/_stdout.log
ls data/parsed_docling/*.jsonl | wc -l
```

- [ ] **Step 3: Monitor periodically**

Check on it every hour or so:

```bash
# Quick status
tail -5 data/parsed_docling/_stdout.log
ls data/parsed_docling/*.jsonl | wc -l

# Or check summary of progress so far
grep -c '"success"' data/parsed_docling/_progress.jsonl 2>/dev/null
grep -c '"failed"' data/parsed_docling/_progress.jsonl 2>/dev/null
```

---

## Mac Mini Setup Instructions

**Copy-paste these commands on the Mac Mini to set up and start the Docling re-parse:**

```bash
# 1. Navigate to the project (synced via Dropbox)
cd ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus

# 2. Ensure you're on the right branch
git checkout feature/30-docling-reparse

# 3. Install docling if not already installed
uv add docling

# 4. Create output directory
mkdir -p data/parsed_docling

# 5. Test with one document first
export DOCLING_DEVICE=auto
export DOCLING_NUM_THREADS=3
uv run python3 scripts/docling_reparse.py --workers 1 --limit 1

# 6. If test passed, start the full run
nohup uv run python3 scripts/docling_reparse.py --workers 4 > data/parsed_docling/_stdout.log 2>&1 &
echo "Started PID $!. Monitor with: tail -f data/parsed_docling/_stdout.log"

# 7. Check it's running
sleep 30 && tail -10 data/parsed_docling/_stdout.log
```

**To check on it later:**
```bash
tail -20 ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/parsed_docling/_stdout.log
```

**If it needs to be stopped:**
```bash
kill $(cat ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/parsed_docling/_pid.txt)
# It will finish current documents gracefully
```

**If it died and needs restarting:**
```bash
cd ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus
export DOCLING_DEVICE=auto
export DOCLING_NUM_THREADS=3
nohup uv run python3 scripts/docling_reparse.py --workers 4 > data/parsed_docling/_stdout.log 2>&1 &
# It will automatically resume from where it left off
```

---

## Self-Review

**Spec coverage:**
- [x] 4 worker processes → configurable via --workers
- [x] Supervised pool with restart on BrokenProcessPool → run_supervised()
- [x] Graceful SIGINT/SIGTERM → handle_signal()
- [x] Per-document timeout 300s → configurable via --timeout
- [x] Atomic writes (.part → rename) → process_one_pdf()
- [x] File-system presence for resume → filter_already_done()
- [x] Advisory progress log → write_progress()
- [x] Prewarm on one document → main()
- [x] MPS error tracking with CPU fallback → mps_errors counter
- [x] Disk space check → every 50 docs
- [x] Markdown output (.md) → process_one_pdf()
- [x] Plain text JSONL (not markdown) → strip_markdown() applied to JSONL
- [x] Per-page splitting via Docling pages API → iterate_items() with prov.page_no
- [x] Logging: per-doc, every 50 docs summary, errors to file → throughout
- [x] Summary JSON → _summary.json

**Placeholder scan:** No TBDs. All code is complete.

**Type consistency:** process_one_pdf takes tuple[str, str], returns dict. Storage key and path types consistent throughout.
