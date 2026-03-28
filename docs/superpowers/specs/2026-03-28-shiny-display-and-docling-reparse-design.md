# Design Spec: Shiny Display Fixes + Docling PDF Re-parse

**Two parallel workstreams to improve clause candidate quality for the Monday roundtable.**

**Review feedback applied:** Incorporates feedback from 3 external reviews on robustness, reflow heuristics, page display strategy, markdown vs plain text, and process supervision.

---

## Problem

The current Shiny eval explorer shows poor-quality clause candidates:

1. **Broken text** — PyMuPDF extracts multi-column PDFs word-by-word, producing single-word lines: `"The\nBonds\ncontain\n\"collective\naction\nclauses.\""` instead of flowing prose.
2. **Fixed context windows** — The grep runner captures 500 characters before/after the match, cutting mid-sentence with no sense of clause boundaries.
3. **Duplicate matches** — The same document/page appears multiple times for different casings or pattern alternatives of the same match.

EDGAR HTML extraction is clean (flowing paragraphs). The problem is specifically PyMuPDF on PDFs (823 PDIP + 645 NSM = 1,468 documents).

---

## Workstream A: Quick-Fix Shiny Display

**Issue:** #29 — Quick-fix Shiny app display — reflow text, deduplicate matches, expand context
**Branch:** `feature/29-shiny-display-fixes` (runs on MacBook Air)
**Goal:** Make the current data presentable for Monday without re-parsing anything.

### Fix 1: Reflow broken text

Post-process context strings in `demo/data/export_data.py` (during export, not at Shiny runtime). Heuristic to join broken lines:

- If a line is short AND doesn't end with sentence-terminal punctuation (`.`, `:`, `;`), join it with the next line using a space.
- Very short lines (< 15 chars) are joined regardless of next-line case (catches single-word fragments like `"The"`).
- Preserve intentional paragraph breaks: blank lines stay as paragraph separators.
- Pre-process: `text.replace('-\n', '')` to handle hyphenation across lines.
- **Only apply to PyMuPDF-parsed documents** (check `storage_key` prefix — `pdip__` and `nsm__` are PDFs, `edgar__` is HTML). Do not reflow EDGAR HTML text.

**Important:** Do NOT reflow `matched_text` — keep the raw match for provenance. Apply reflow only to the display context. Store both raw and reflowed versions if needed.

### Fix 2: Deduplicate matches

In `demo/data/export_data.py`, after loading grep candidates from DuckDB:

- Group by `(storage_key, page_number, pattern_name)`
- Keep only the first match per group (longest `matched_text`)
- This eliminates the 6 near-identical "Indonesia / page 7 / collective action" rows

### Fix 3: Show full page text

Replace the 500-char context window with full page text from the parsed JSONL files:

- At export time, for each grep match, read the corresponding page from `data/parsed/{storage_key}.jsonl`
- Apply the reflow heuristic (Fix 1) to the full page text for PDF sources
- In the Shiny app, display the full page text with a scrollable container and the match region highlighted
- **For PDF sources (PDIP, NSM):** show full page text — these are real pages, bounded by physical page breaks, typically 3,000-5,000 chars
- **For EDGAR HTML:** not applicable for Monday (current export is PDIP-only), but if added later, expand to paragraph boundaries (`\n\n` before/after match) capped at 5,000 chars, since HTML "pages" can be the entire filing

**Highlighting:** Normalize whitespace in the match text before searching for it in the page text, and highlight all occurrences (not just the first).

### Shiny app improvements

- Add a callout note: "In a production version, each candidate would link to the original source document."
- Use proportional font (Georgia/serif) with proper paragraph spacing
- Scrollable context panel for long pages

---

## Workstream B: Docling PDF Re-parse

**Issue:** #30 — Docling PDF re-parse — parallel extraction to data/parsed_docling/
**Branch:** `feature/30-docling-reparse` (runs on Mac Mini)
**Goal:** Replace PyMuPDF extraction with Docling for all PDFs, producing clean flowing text with document structure.

### Architecture

A standalone script `scripts/docling_reparse.py` that:

1. Reads all PDFs from `data/pdfs/pdip/` (823 files) and `data/original/nsm__*.pdf` (645 files)
2. Uses a supervised process pool that restarts on worker death (see Process Supervision below)
3. Each worker creates its own `DocumentConverter` instance (models loaded once per worker, ~500MB each)
4. Prewarms on one document before starting the full run (catches bootstrap failures early)
5. For each PDF, produces two outputs:
   - `data/parsed_docling/{storage_key}.md` — Docling markdown (preserves headers, tables, structure for human/LLM reading)
   - `data/parsed_docling/{storage_key}.jsonl` — **plain text** (NOT markdown), same format as existing parsed output (header line + per-page records) so the grep pipeline can consume it without changes
6. Outputs are written atomically (`.part` → `os.replace()`)
7. Progress tracked via file-system presence (skip if output `.jsonl` already exists) + advisory `_progress.jsonl` append log
8. Per-document timeout of 300 seconds with hard process kill
9. Produces a summary at the end: successes, failures, skipped, total time

### Dual output format

- **`.md` file:** Full Docling markdown via `result.document.export_to_markdown()`. Preserves headers, tables, structure. For human reading and future LLM consumption.
- **`.jsonl` file:** Plain text via `result.document.export_to_text()` (or markdown with formatting stripped). Split by page. This is what the grep pipeline reads. No `##`, `**`, `|`, or other markdown syntax that would interfere with regex patterns.

### Process supervision (critical for unattended execution)

`ProcessPoolExecutor` does NOT restart dead workers. A single segfault (common with native ML code) puts the pool in `BrokenProcessPool` state and all subsequent work fails.

**Pattern:** Supervised pool with automatic restart:

```python
def run_with_supervision(pdf_paths, max_workers=4):
    remaining = list(pdf_paths)
    while remaining and not shutdown_requested:
        try:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for path in remaining[:]:  # copy to allow removal
                    futures[pool.submit(process_one, path)] = path
                for future in as_completed(futures):
                    path = futures[future]
                    try:
                        future.result(timeout=300)
                    except (TimeoutError, Exception) as e:
                        log_failure(path, e)
                    remaining.remove(path)
        except BrokenProcessPool:
            logger.warning(f"Pool crashed. {len(remaining)} remaining. Restarting...")
            continue
```

**Graceful shutdown:** Catch `SIGTERM` and `SIGINT`. Set a `shutdown_requested` flag. Finish current documents, then exit cleanly.

**Timeout enforcement:** `concurrent.futures` timeout doesn't kill the underlying worker process. After timeout, call `process.terminate()` on the worker or accept that zombie workers accumulate (acceptable for a one-off job if total count is small).

### Failure handling

| Failure Mode | What Happens | Mitigation |
|---|---|---|
| Docling segfault / crash | Worker dies, BrokenProcessPool | Supervised pool restarts (see above) |
| OOM kill | macOS kills worker | Same as crash — pool restart |
| Metal/MPS driver error | Python RuntimeError | Catch per-document. After 3+ MPS errors, set `DOCLING_DEVICE=cpu` for remaining docs |
| Corrupt PDF / infinite loop | 300s timeout fires | Log failure, skip document, continue |
| Disk space exhaustion | OSError on write | Check `shutil.disk_usage()` every 50 docs. If < 1GB free, pause and log |

### Checkpoint and resume

- **Primary:** File-system presence. On startup, scan `data/parsed_docling/` for existing `.jsonl` files and skip those documents. This makes the script inherently resumable.
- **Advisory:** Append to `_progress.jsonl` after each successful document (for observability, not correctness). On resume, tolerate a truncated last line.
- **Atomic writes:** Write output to `{key}.jsonl.part`, then `os.replace()` to `{key}.jsonl`. A crash mid-write leaves only a `.part` file which is ignored on resume.

### Page splitting

- Use Docling's per-page content tracking (`result.document.pages`) to split plain text by page
- Each page goes into a JSONL record: `{"page": N, "text": "..."}`
- If Docling's page count differs significantly from PyMuPDF's (stored in the existing parsed JSONL header), log a warning but use Docling's numbering
- **Do NOT fall back to "store everything as page 0"** — this breaks page citations. If page detection is unreliable for a document, keep the PyMuPDF output for that document (don't swap it in)

### Logging and observability

For a 4-5 hour unattended run:

- **Per document:** `[347/1468] pdip__BRA42 — 53 pages — 12.3s — OK`
- **Every 50 documents:** `Progress: 347/1468 (23.6%) — 12 failed — 3 skipped — ETA 3h 12m`
- **Startup:** Log config (device, threads, workers, Docling version, output path)
- **Errors:** Full traceback to `data/parsed_docling/_errors.log`
- **Final:** `_summary.json` with counts, timings, failure list

### Environment

```bash
export DOCLING_DEVICE=auto        # Enable Metal/MPS for layout model (3x speedup)
export DOCLING_NUM_THREADS=3      # PyTorch threads per worker
```

### Resource budget

- 4 workers × ~1.7GB peak = ~7GB RAM (well within 64GB)
- 4 workers × 3 PyTorch threads = 12 inference threads + ~20 pipeline threads
- Estimated runtime: 4-5 hours

### What it doesn't touch

- `data/parsed/` — PyMuPDF output stays as fallback
- Pipeline code — grep runner, CLI, export scripts unchanged
- HTML/TXT files — EDGAR HTML extraction is already clean, not re-processed

### Swap-in procedure (after Docling finishes)

1. For each PDF document: if `data/parsed_docling/{key}.jsonl` exists, is non-empty, and has reasonable page count (within ±2 of PyMuPDF), copy over `data/parsed/{key}.jsonl`
2. Spot-check 10 documents: compare a known clause match against the original PDF to verify text and page number
3. Re-run `corpus grep run --run-id grep-docling`
4. Re-run validation, compare match counts per pattern — expect matches to go UP (better text extraction = more regex hits)
5. Re-export: `demo/data/export_data.py grep-docling`
6. Copy CSVs to `demo/shiny-app/data/`
7. Re-deploy Shiny app and Quarto book

### Fallback

If Docling doesn't finish by Sunday evening:
- Monday demo uses Workstream A's quick-fix display (reflowed text, deduped matches, full page context)
- Docling re-parse continues and is swapped in post-roundtable

---

## Execution order

1. **Now (Saturday morning):** Start Workstream B on Mac Mini (kick off Docling, let it run). Switch to MacBook Air for Workstream A.
2. **Saturday afternoon:** Workstream A merges — Shiny app display is improved with current data.
3. **Saturday evening / Sunday morning:** If Docling finishes, do the swap-in: spot-check, re-grep, re-export, re-deploy.
4. **Sunday afternoon:** Final polish, test deployed site, prepare Monday morning checklist.

---

## What this is NOT

- Not changing the grep runner or pattern logic (that was done in the previous branch)
- Not adding new clause patterns
- Not redesigning the pipeline architecture
- Not integrating Docling into the CLI (that's post-roundtable — Decision #8 says "module swap, not rewrite")
