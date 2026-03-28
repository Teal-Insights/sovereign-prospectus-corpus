# Design Spec: Shiny Display Fixes + Docling PDF Re-parse

**Two parallel workstreams to improve clause candidate quality for the Monday roundtable.**

---

## Problem

The current Shiny eval explorer shows poor-quality clause candidates:

1. **Broken text** — PyMuPDF extracts multi-column PDFs word-by-word, producing single-word lines: `"The\nBonds\ncontain\n\"collective\naction\nclauses.\""` instead of flowing prose.
2. **Fixed context windows** — The grep runner captures 500 characters before/after the match, cutting mid-sentence with no sense of clause boundaries.
3. **Duplicate matches** — The same document/page appears multiple times for different casings or pattern alternatives of the same match.

EDGAR HTML extraction is clean (flowing paragraphs). The problem is specifically PyMuPDF on PDFs (823 PDIP + 645 NSM = 1,468 documents).

---

## Workstream A: Quick-Fix Shiny Display

**Issue:** Quick-fix Shiny app display — reflow text, deduplicate matches, expand context
**Branch:** `feature/XX-shiny-display-fixes` (runs on MacBook Air)
**Goal:** Make the current data presentable for Monday without re-parsing anything.

### Fix 1: Reflow broken text

Post-process context strings in `demo/data/export_data.py` (during export, not at Shiny runtime). Detect single-word lines and join them:

- If a line is shorter than ~60 characters and the next line starts with a lowercase letter or is also short, join with a space instead of a newline.
- Preserve intentional line breaks: lines ending with a period/colon followed by a blank line stay as paragraph breaks.
- This is a heuristic, not perfect. But it turns `"The\nBonds\ncontain"` into `"The Bonds contain"` which is dramatically better.

Apply to both `context_before` and `context_after` fields, and to `matched_text`.

### Fix 2: Deduplicate matches

In `demo/data/export_data.py`, after loading grep candidates from DuckDB, deduplicate:

- Group by `(storage_key, page_number, pattern_name)`
- Keep only the first match per group (longest matched_text, or first encountered)
- This eliminates the 6 near-identical "Indonesia / page 7 / collective action" rows

### Fix 3: Show full page text

Change the Shiny app to load and display full page text instead of the 500-char context window:

- Add a new export: for each grep match, include the full page text from the parsed JSONL file
- In the Shiny app, display the full page text with the matched phrase highlighted (search for the matched_text substring within the page text and wrap it in a highlight span)
- This gives the reviewer natural context — the whole page — instead of an arbitrary character window

Alternatively, if full page text makes the CSV too large: increase context to 2000 chars and expand to paragraph boundaries (find the nearest `\n\n` before the match start and after the match end).

### Shiny app improvements

- Add a callout note: "In a production version, each candidate would link to the original source document."
- Fix the display to use proportional font (Georgia/serif) with proper paragraph spacing instead of monospace with broken lines

---

## Workstream B: Docling PDF Re-parse

**Issue:** Docling PDF re-parse — parallel extraction to data/parsed_docling/
**Branch:** `feature/YY-docling-reparse` (runs on Mac Mini)
**Goal:** Replace PyMuPDF extraction with Docling for all PDFs, producing clean flowing text with document structure.

### Architecture

A standalone script `scripts/docling_reparse.py` that:

1. Reads all PDFs from `data/pdfs/pdip/` (823 files) and `data/original/nsm__*.pdf` (645 files)
2. Runs 4 worker processes via `concurrent.futures.ProcessPoolExecutor`
3. Each worker creates its own `DocumentConverter` instance (models loaded once per worker, ~500MB each)
4. For each PDF, produces two outputs:
   - `data/parsed_docling/{storage_key}.md` — Docling markdown (preserves headers, tables, structure)
   - `data/parsed_docling/{storage_key}.jsonl` — same format as existing parsed output (header line + per-page records) so the grep pipeline can consume it without changes
5. Checkpoints progress to `data/parsed_docling/_progress.jsonl` after each document
6. Per-document timeout of 300 seconds — skip and log if exceeded
7. Produces a summary at the end: successes, failures, skipped, total time

### Environment

```bash
export DOCLING_DEVICE=auto        # Enable Metal/MPS for layout model (3x speedup)
export DOCLING_NUM_THREADS=3      # PyTorch threads per worker
```

### Resource budget

- 4 workers × ~1.7GB peak = ~7GB RAM (well within 64GB)
- 4 workers × 3 PyTorch threads = 12 inference threads + ~20 pipeline threads
- Leaves headroom for other work on the Mac Mini
- Estimated runtime: 4-5 hours

### Page splitting

Docling outputs a single document, not per-page. For the JSONL output:

- Use Docling's internal page tracking (`result.document.pages`) to split content by page
- Each page's content goes into a separate JSONL record with `{"page": N, "text": "..."}`
- If page detection is unreliable for a document, store the entire text as page 0

### What it doesn't touch

- `data/parsed/` — PyMuPDF output stays as fallback
- Pipeline code — grep runner, CLI, export scripts unchanged
- HTML/TXT files — EDGAR HTML extraction is already clean, not re-processed

### Swap-in procedure (after Docling finishes)

1. For each PDF document: if `data/parsed_docling/{key}.jsonl` exists and is non-empty, copy it over `data/parsed/{key}.jsonl`
2. Re-run `corpus grep run --run-id grep-docling`
3. Re-run `demo/data/export_data.py grep-docling`
4. Copy updated CSVs to `demo/shiny-app/data/`
5. Re-deploy Shiny app and Quarto book

### Fallback

If Docling doesn't finish by Sunday evening:
- Monday demo uses Workstream A's quick-fix display (reflowed text, deduped matches, expanded context)
- Docling re-parse continues running and is swapped in post-roundtable

---

## Execution order

1. **Now (Saturday morning):** Create both issues. Start Workstream B on Mac Mini (kick off the Docling job, let it run). Switch to MacBook Air for Workstream A.
2. **Saturday afternoon:** Workstream A merges — Shiny app display is improved with current data.
3. **Saturday evening / Sunday morning:** If Docling finishes, do the swap-in: re-grep, re-export, re-deploy.
4. **Sunday afternoon:** Final polish, test deployed site, prepare Monday morning checklist.

---

## What this is NOT

- Not changing the grep runner or pattern logic (that was done in the previous branch)
- Not adding new clause patterns
- Not redesigning the pipeline architecture
- Not integrating Docling into the CLI (that's post-roundtable — Decision #8 says "module swap, not rewrite")
