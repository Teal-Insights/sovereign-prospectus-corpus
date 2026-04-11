# Spring Meetings Sprint — v2: Confirmed Bug Fix + Revised Sequencing

**Date:** 2026-04-11 (v2)
**Sprint deadline:** 2026-04-13 (IMF/World Bank Spring Meetings, Monday morning)
**Replaces:** v1 at `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md`
**Related:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md`, issues #53, #54, #55, #56, #72
**Changes from v1:** All critical correctness fixes from three external reviews applied. Docling bug fix confirmed via smoke test. Revised time estimates. Reshaped LuxSE cliff. Deleted Gate A (DRC already verified). Deleted in-place merge strategy (full re-parse from scratch instead).
**v2 amendment (post-review):** Resolved 3 BLOCKERs and 6 CONCERNs from three additional external reviews: locked in parsed-dir promotion strategy, markdown-vs-plaintext split, `document_markdown` table, JSONL header contract, page numbering convention, branch execution rule, and resume semantics.

## Intent

Two things matter for Monday's demo, in this order:

1. **Coverage.** More sovereign prospectuses in the corpus is the single biggest lever for "is this tool useful to the people in the room." The audience is sovereign debt lawyers and economists from IMF Legal, World Bank debt teams, and the broader research community. They will judge the explorer by whether the documents they care about are in it — not by the elegance of the pipeline. That means **committing to the Luxembourg Stock Exchange adapter for this sprint**, not deferring it, and refreshing NSM + EDGAR to capture the last two weeks of new filings (notably the Democratic Republic of the Congo's April 2026 prospectus, confirmed present on NSM — disclosure ID `d7a0206a-b71e-4af1-bc6e-63976b122475`, submitted 2026-04-08).

2. **Correct PDF parsing.** The March 28 Docling outputs in `data/parsed_docling/` are confirmed broken — the worker function only captured `TextItem` and `SectionHeaderItem`, silently dropping pages that contain only tables, pictures, lists, or formulas. Confirmed impact: 47 of 58 pages dropped on `nsm__101126915_20200330172131895.pdf`, and Review C found >243 of 1,468 outputs show significant page drift. The fix is confirmed working (see Step 0 below). The entire corpus will be re-parsed from scratch overnight.

### A note on time estimates in this spec

Agentic AI systems consistently overestimate implementation time. **These estimates are upper bounds, not floors.** A realistic sprint budget is 50-70% of the wall-clock estimates below.

## What changed vs. the original sprint plan

### Four corrections to facts the sprint plan assumed

1. **EDGAR is not PDFs.** EDGAR is 2,947 `.htm` + 275 `.txt` + 84 `.paper` placeholders, parsed via `HTMLParser` (BeautifulSoup with CSS page-break splitting) and `PlainTextParser`. Docling does not apply to EDGAR. The "reparse all 4,769 documents" framing in issue #72 was wrong.

2. **NSM + PDIP Docling outputs exist but are broken.** `data/parsed_docling/` contains 1,468 files from the March 28 run. However, the page-drop bug means these outputs are unreliable. They will be deleted and re-parsed from scratch with the fixed worker.

3. **DRC is on NSM, confirmed via live API query.** Disclosure ID `d7a0206a-b71e-4af1-bc6e-63976b122475`, submitted `2026-04-08T11:57:24Z`, headline "Publication of a Base Offering Circular". No verification gate needed — DRC will come in via the NSM incremental automatically.

4. **LSE RNS dropped.** DRC is the only filing that motivated the LSE RNS adapter. With DRC confirmed on NSM, LSE RNS is a post-sprint follow-up.

### The Docling bug and its fix (confirmed in Step 0 smoke test)

**The bug** in `scripts/docling_reparse.py` on `feature/30-docling-reparse` (commit `47dfa8a9`), lines 157-164:

```python
pages: dict[int, list[str]] = {}
for item, _level in doc.iterate_items():
    if isinstance(item, (TextItem, SectionHeaderItem)):
        for prov in item.prov:
            pages.setdefault(prov.page_no, []).append(item.text)
            break
page_count = len(pages)  # BUG: counts pages with TextItems, not actual PDF pages
```

Only `TextItem` and `SectionHeaderItem` are recognized. Pages with only `TableItem`, `PictureItem`, `ListItem`, `FormulaItem`, etc. are silently dropped. In sovereign prospectuses, the statistical annexes, financial tables, and reserve-adequacy charts live on exactly those pages.

**The fix** uses Docling's native per-page markdown export (Docling 2.86.0), with a markdown-vs-plaintext split:

```python
page_count = doc.num_pages()        # Actual PDF page count
pages_md: dict[int, str] = {}       # Markdown (for .md sidecar / detail panel)
pages_text: dict[int, str] = {}     # Plain text (for JSONL / grep / FTS)
for page_no in sorted(doc.pages.keys()):
    md = doc.export_to_markdown(page_no=page_no)
    pages_md[page_no] = md
    pages_text[page_no] = strip_markdown(md)  # Preserves table content as plain text
```

The reparse script emits two files per document:
- **`.jsonl`** — JSONL with plain text `text` field (stripped of markdown formatting). Used for grep pattern matching and FTS indexing. Page field is **0-indexed** (matching existing CLI convention).
- **`.md`** — Raw markdown from `doc.export_to_markdown()` (full document). Used for the Streamlit detail panel.

The `strip_markdown()` function must preserve table *content* as plain text (the stale version deleted table rows entirely, which would make table content unsearchable). Headings, emphasis, list markers, and table pipes are stripped; cell text is preserved as space-separated values.

Key API details (verified on Docling 2.86.0):
- `doc.pages` is a `dict[int, PageItem]` keyed by 1-indexed page number
- `doc.num_pages()` returns the actual PDF page count
- `doc.export_to_markdown(page_no=N)` exports a single page as markdown, including tables rendered as markdown tables, images as placeholders, lists, formulas, etc.

**Smoke test results (Mac Mini M4 Pro, 2026-04-11):**

| File | Actual pages | Stale logic | Fixed logic | Dropped by stale |
|------|-------------|-------------|-------------|------------------|
| `nsm__101126915_20200330172131895.pdf` | 58 | 11 | 58 (all with content) | 47 |
| `KAZ1.pdf` (PDIP, 185 pages) | 185 | 184 | 185 (all with content) | 1 |
| `nsm__4189777.pdf` (180 pages) | 180 | 29 | 180 (150 image-only) | 151 |

Per-page `export_to_markdown()` adds ~0.5s per document (negligible vs ~10s/doc conversion). Overnight run estimate unchanged at ~6 hours for 2,291 docs.

### JSONL output contract (mandatory for both code paths)

Both the `DoclingParser` class (used by `corpus parse`) and `scripts/docling_reparse.py` (used for bulk overnight runs) must write identical JSONL format. This is the contract:

**Header line (line 1):**
```json
{"storage_key": "nsm__101126915", "page_count": 58, "parse_tool": "docling", "parse_version": "2.86.0", "parse_status": "parse_ok", "parsed_at": "2026-04-12T02:15:00+00:00"}
```

Required fields: `storage_key`, `page_count` (from `doc.num_pages()`), `parse_tool`, `parse_version` (Docling package version), `parse_status` (`parse_ok` | `parse_empty`), `parsed_at` (ISO 8601 UTC).

**Page lines (line 2+):**
```json
{"page": 0, "text": "plain text content of page 1...", "char_count": 2263}
```

- **`page` is 0-indexed** (matching the existing CLI convention at `cli.py:726`). The reparse script converts from Docling's 1-indexed `doc.pages.keys()` with `page_no - 1`.
- **`text` is plain text**, not markdown. Markdown formatting is stripped via `strip_markdown()` to preserve grep/FTS compatibility with existing clause patterns.
- The `.md` sidecar file contains raw markdown for the Streamlit detail panel.

## Scope

### In scope

- **Docling Phase A (PR #1):** `DoclingParser` class + registry registration + `config.toml` default flip + **CLI rewire** (`src/corpus/cli.py:618` must call `get_parser()` instead of hardcoding `PyMuPDFParser()`) + fixed `scripts/docling_reparse.py` worker (from Step 0) + `luxse__*.pdf` glob addition to `discover_pdfs()` + Decision 18 doc update + unit tests.
- **NSM incremental** discover + download (DRC comes in automatically — no gate needed).
- **EDGAR incremental** discover + download.
- **LuxSE adapter (PR #2):** new source adapter, committed unconditionally, time-boxed (see cliff below).
- **Overnight Docling bulk parse:** delete `data/parsed_docling/` entirely, re-parse ALL 2,291 NSM+PDIP PDFs + new NSM + LuxSE from scratch using the fixed worker. No resume of broken March 28 outputs.
- **Re-run `grep_matches`** after the overnight parse (existing 106,229 matches reference PyMuPDF text offsets; after re-parse, those offsets are invalid). `corpus grep` is fast (~15-30 min).
- **Task 3 (PR #3):** FTS + country backfill + `documents.parse_tool` and `page_count` population (currently NULL for all 4,769 rows — must read JSONL header during rebuild) + markdown storage for Streamlit detail panel + MotherDuck publish.
- **Task 4 (PR #4):** Streamlit explorer with markdown rendering in the detail panel.
- **Task 9 polish:** demo script, smoke tests, warm-up for cold start.

### Out of scope

- LSE RNS adapter — DRC is on NSM, no remaining justification this sprint.
- ESMA adapter (Task 8).
- V1 Quarto book or V1 Shiny app (frozen).

## The sequence

### Step 0 — Docling bug fix smoke test (COMPLETE)

Completed 2026-04-11 on the Mac Mini M4 Pro:

- Confirmed Docling 2.86.0 installed
- Verified Docling API: `doc.pages` (dict[int, PageItem]), `doc.num_pages()`, `doc.export_to_markdown(page_no=N)`
- Reproduced the bug: stale logic emitted 11 of 58 pages for `nsm__101126915_20200330172131895.pdf`
- Wrote the fix: iterate `doc.pages.keys()`, call `export_to_markdown(page_no=N)` per page
- Verified fix: 58 of 58 pages emitted with content
- Spot-checked on KAZ1.pdf (185/185) and nsm__4189777.pdf (180/180)
- Performance: ~0.5s overhead per doc for the per-page export (negligible)

### Step 1 — Docling Phase A (PR #1)

**What ships:**

1. `DoclingParser` class implementing the `DocumentParser` protocol
2. Parser registry update: register `DoclingParser` for `.pdf`
3. `config.toml` default: `[parser].default = "docling"` (the actual config key used by `get_parser()`)
4. **CLI rewire** at `src/corpus/cli.py:618-623`: change from:
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
       ".pdf": get_parser(),  # Uses config default (Docling)
       ".txt": PlainTextParser(),
       ".htm": HTMLParser(),
       ".html": HTMLParser(),
   }
   ```
5. Fixed `scripts/docling_reparse.py` worker: replace `TextItem`/`SectionHeaderItem` filtering with `export_to_markdown(page_no=N)` per-page iteration. Update `page_count` to use `doc.num_pages()`. Emit two files per document: `.jsonl` (plain text, 0-indexed pages) and `.md` (raw markdown). Improved `strip_markdown()` that preserves table content. Must conform to the JSONL output contract above.
6. Add `data/original/luxse__*.pdf` to `discover_pdfs()` glob in `scripts/docling_reparse.py`
7. Unit tests for `DoclingParser`
8. Decision 18 doc update in `docs/RATIFIED-DECISIONS.md`

**Est. wall: 45-90 min** (incl. bot review)

### Step 2 — NSM + EDGAR incrementals

Commands (parallel shells, disjoint hosts):
```bash
corpus discover nsm && corpus download nsm
corpus discover edgar && corpus download edgar
```

DRC is confirmed present on NSM. No verification gate — the `"Republic of"` name pattern in `build_sovereign_queries` captures it automatically.

**Do not run `corpus parse`** between Step 2 and Step 4. New PDFs sit in `data/original/` until the overnight bulk parse processes them. Running `corpus parse` in this window would create PyMuPDF outputs that get overwritten anyway.

**Est. wall: 30-60 min**

### Step 3 — LuxSE adapter (PR #2)

Build a new source adapter against the Luxembourg Stock Exchange site.

**Cliff structure (reshaped from v1):**
- **90-minute soft checkpoint:** by T+90m from branch creation, the adapter must have fetched at least one PDF file from LuxSE for a known sovereign issuer, confirmed by `%PDF` magic bytes. A listing page or search-results page does not count — the checkpoint requires an actual document download. If not → abandon LuxSE, document in `docs/SOURCE_INTEGRATION_LOG.md`, ship the sprint without it.
- **4-hour hard cliff:** by T+4h active build time, the adapter must be discovering + downloading sovereign PDFs in a repeatable pipeline. If not → commit partial work, document the gap, move on.

Run full LuxSE download immediately when the adapter lands.

**Est. wall: 2-4 hr build + 0.5-1 hr download** (happy path); 90 min (abandon path)

### Step 4 — Overnight Docling bulk parse (Saturday night, Mac Mini)

**All Steps 1-4 execute from the `feature/docling-bug-fix-and-sprint-v2` branch.** PR #1 does not need to merge to `main` before the overnight run — the user runs the script from the feature branch directly. PR #1 merges after the overnight parse verifies clean output.

1. Delete `data/parsed_docling/` entirely **once** (fresh start — March 28 outputs are confirmed broken). **Do not delete it again if the run crashes and needs to restart.**
2. Run `scripts/docling_reparse.py` (with the fixed worker from Step 1) against ALL 2,291 NSM+PDIP PDFs + new NSM incrementals + LuxSE PDFs
3. ~6 hours on M4 Pro (2,291+ docs at ~10s/doc)
4. Monitor via `tail -f data/parsed_docling/_progress.jsonl` from another terminal
5. User kicks off before bed; Claude is paused for the night

**Resume semantics:** The fixed `process_one_pdf` must skip files whose output `.jsonl` already exists in the target directory, enabling crash-resume without re-processing. If the run crashes at doc 1,500 at 3 AM, restart the script — it resumes from doc 1,501, not from scratch.

**Gate: Parse error budget.** If `_errors.log` has >5% error rate: inspect errors, decide per-doc. Expected: near-zero errors (March 28 had 0 errors).

### Step 5 — Verify overnight parse (Sunday morning)

1. Check `_errors.log` is empty (or has only known-bad PDFs like `nsm__4189777.pdf` which is image-only)
2. Spot check 5 random files: page counts match `doc.num_pages()`, content present on every page
3. Verify total output count matches total input count
4. If issues: diagnose + partial re-parse
5. If clean: proceed

**Est. wall: 15-30 min**

### Step 6 — Task 3: FTS + markdown + grep rerun + MotherDuck (PR #3)

1. **Parsed dir promotion (single directory strategy):** Rename `data/parsed/` → `data/parsed.pymupdf.bak/` (backup). Rename `data/parsed_docling/` → `data/parsed/` (promotion). Then re-run `corpus parse --source edgar` to regenerate EDGAR's `.htm`/`.txt`/`.paper` outputs in the new `data/parsed/`. Result: **one authoritative `data/parsed/` directory** containing Docling outputs for all PDFs and HTMLParser outputs for EDGAR. All downstream tools (`corpus grep`, `corpus build-db`, etc.) work unchanged — no multi-directory routing patches needed.
2. **`documents.parse_tool` + `page_count` population:** currently NULL for all 4,769 rows. Read from JSONL header during the Task 3 rebuild. This is new code in `src/corpus/db/ingest.py`, not just a config flip — `ingest.py:26` currently only copies `parse_tool` from manifests, which don't carry it. Must read the header fields defined in the JSONL output contract above.
3. **Re-run `grep_matches`:** `corpus grep` against the promoted `data/parsed/` (now containing Docling plain text). The existing 106,229 matches reference PyMuPDF text offsets that are now invalid. With the bug fix, Docling's page numbers are no longer sparse, so grep citations will be correct. (~15-30 min runtime.)
4. **Markdown storage in `document_markdown` table:** Create a new `document_markdown` table keyed by `document_id` with a `markdown_text` column. Populated from the `.md` files Docling emits alongside the JSONL. This keeps the `documents` table metadata-light — multi-MB markdown blobs are only JOINed when the Streamlit detail panel needs them. For EDGAR HTML docs, convert the parsed HTML to markdown at ingest time (or store the raw HTML and let Streamlit render it). The `document_markdown` table is published to MotherDuck alongside `documents`.
5. **Country classifications** table (WB API pull, ~200 rows)
6. **Country backfill** for EDGAR/NSM documents
7. **`document_pages` + FTS index** (plain text from JSONL as source text for FTS, not raw markdown)
8. **publish-motherduck** — MotherDuck schema will need republishing to add `document_markdown` table + new columns

**Est. wall: 4-6 hr** (includes grep rerun + parse_tool/page_count backfill + markdown storage + EDGAR reparse)

### Step 7 — Task 4: Streamlit explorer (PR #4)

Per sprint plan:
- Landing page with corpus stats
- Full-text search powered by DuckDB FTS
- Filters: source, country, document type
- **Detail panel with markdown rendering** (reads `document_markdown` table via `JOIN` on `document_id`; renders via `st.markdown()`)
- Deep-linkable state (query params)
- Deploy to Streamlit Cloud (Task 1 already de-risked this path)
- Smoke tests: DRC, Ghana, Argentina, collective action clause, pari passu, New York law, contingent liabilities

**Est. wall: 3-6 hr**

### Step 8 — Task 9 polish (Monday morning)

- Demo script / walkthrough
- Cold-start warm-up ping (Streamlit Cloud spins down after inactivity)
- Final smoke tests against the live deployment
- Any last-minute fixes from Sunday evening review

**Est. wall: 30-60 min**

## Saturday-to-Sunday-to-Monday sequencing

| When | What | Blocking? |
|------|------|-----------|
| **Saturday afternoon** | Step 1 (PR #1: Docling Phase A + CLI rewire + fixed worker) | Yes — Step 4 depends on the fixed worker |
| **Saturday afternoon** | Step 2 (NSM + EDGAR incrementals, parallel with Step 1 review) | Partially — Step 4 needs the new PDFs |
| **Saturday afternoon/evening** | Step 3 (LuxSE adapter, up to 4h hard cliff) | Soft — Step 4 runs with whatever coverage exists |
| **Saturday evening** | Step 4 (overnight bulk Docling parse — user kicks off before bed) | Yes — Step 6 needs the outputs |
| **Sunday morning** | Step 5 (verify overnight parse) | Yes — must pass before Step 6 |
| **Sunday** | Step 6 (Task 3: FTS + markdown + grep + MotherDuck) | Yes — Step 7 reads the DB |
| **Sunday** | Step 7 (Task 4: Streamlit explorer) | Yes — must deploy before Monday |
| **Monday morning** | Step 8 (polish, smoke tests, demo) | No — demo-day cleanup |

**Total active wall-clock: ~12-18 hours** (spread across Saturday afternoon → Sunday → Monday morning). The overnight parse (~6h) runs unattended.

## Deliverables

- **PR #1** — Docling Phase A (parser class, CLI rewire, fixed worker, `luxse__*.pdf` glob, registry, config default, tests, Decision 18 update)
- **PR #2** — LuxSE adapter (source adapter, tests, sovereign query config, manifest pipeline integration)
- **PR #3** — Task 3: FTS + parsed-dir promotion + EDGAR reparse + grep rerun + parse_tool/page_count backfill + `document_markdown` table + country classifications + MotherDuck publish
- **PR #4** — Task 4: Streamlit explorer with markdown detail panel, deployed to Streamlit Cloud
- **(optional) PR #5** — Task 9 polish

## Resolved decisions (from v1's "Open decisions" section)

All four open decisions from v1 are now resolved, plus five additional decisions locked in during v2 review:

1. **LuxSE cliff:** reshaped to 90-min soft checkpoint + 4-hour hard cliff (was 5h flat). Checkpoint requires an actual PDF download with `%PDF` magic bytes, not just a listing page.
2. **DRC verification gate:** deleted. DRC is confirmed on NSM via live API query. No gate needed.
3. **Merge strategy:** parsed-dir promotion. Rename `data/parsed_docling/` → `data/parsed/`, re-run `corpus parse --source edgar` to regenerate EDGAR outputs. Single authoritative directory — no multi-directory routing.
4. **Docling Phase A ships independently of the parse.** Yes — Phase A ships the parser class and fixed worker; the actual bulk parse runs later. All steps execute from the feature branch; PR #1 merges after the overnight parse verifies clean output.
5. **Markdown storage:** separate `document_markdown` table keyed by `document_id`. Not a column on `documents` — avoids bloating metadata queries and MotherDuck sync.
6. **JSONL text field:** plain text (stripped markdown), not raw markdown. Preserves grep/FTS compatibility with existing clause patterns. Raw markdown lives in `.md` sidecar files only.
7. **Page numbering:** 0-indexed `page` field in all JSONL (matching existing CLI convention). Reparse script converts from Docling's 1-indexed pages.
8. **JSONL header contract:** both `DoclingParser` and `scripts/docling_reparse.py` must write identical header schema (see contract section above).
9. **Resume semantics:** `data/parsed_docling/` is deleted once at the start of Step 4. If the overnight run crashes, restart without re-deleting — per-file skip logic resumes from where it left off.

## Risks

- **LuxSE site is a JS SPA.** Mitigation: 90-min soft checkpoint catches this early.
- **Docling takes longer than expected on large/complex LuxSE PDFs.** If LuxSE returns 500 PDFs at 100+ pages each, parse could extend to 8-10h. Mitigation: the overnight slot is elastic; user can let it run into Sunday morning.
- **Streamlit Cloud deploy friction.** Mitigation: Task 1 (PR #61) already de-risked this. Follow gotchas in `reference_streamlit_cloud_deploy.md`.
- **Streamlit cold-start latency.** The free tier spins down after inactivity. Mitigation: warm-up ping in Step 8.
- **Time budget overrun on Task 4.** Mitigation: ship thin — landing page + search + filters + detail panel is enough. Deep-linkable state can slip to Monday morning polish.

## Non-goals

- Perfect coverage. LuxSE may come in at 50% or 100%. "Here's what we've got, here's what's coming" is fine for a working demo.
- Perfect text quality. Docling is better than PyMuPDF but not infallible. Hand-verification of demo extractions is the roundtable-level discipline.
- Zero tech debt. Follow-up issues get filed for anything that must slip.
