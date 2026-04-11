# SESSION-HANDOFF.md — Spring Meetings Sprint (overnight parse)

**Last updated:** 2026-04-11 evening (post-implementation, pre-overnight parse)
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Branch:** `feature/docling-bug-fix-and-sprint-v2`
**Spec:** `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md`
**Plan:** `docs/superpowers/plans/2026-04-11-spring-meetings-sprint.md`
**Tests:** 431 passing, 0 failing

## START HERE (Sunday morning)

The overnight Docling parse ran on the Mac Mini M4 Pro. All code for
Steps 1-3 and PR #3 pre-work is built, tested, and pushed. The morning
is operational — run commands, not build tasks.

### Morning Runbook

```bash
# 1. Validate overnight parse output
uv run python scripts/validate_parse_output.py

# 2. Promote parsed dir (backup PyMuPDF, promote Docling, re-parse EDGAR)
uv run python scripts/promote_parsed_dir.py

# 3. Rebuild DB (reads JSONL headers for parse_tool/page_count)
uv run corpus ingest --run-id rebuild-$(date +%Y%m%d)

# 4. Build pages + FTS index
uv run corpus build-pages

# 5. Build markdown for detail panel
uv run corpus build-markdown

# 6. Re-run grep (existing matches reference PyMuPDF offsets — now invalid)
uv run corpus grep run --run-id grep-docling-$(date +%Y%m%d)

# 7. Publish to MotherDuck
export MOTHERDUCK_TOKEN=<token>
uv run corpus publish-motherduck

# 8. Build Streamlit explorer (PR #4 — Task 4)
# This is the main Sunday work item
```

### If the overnight parse had errors

```bash
# Check error details
cat data/parsed_docling/_errors.log

# Resume from where it stopped (script skips existing outputs)
caffeinate -d -i uv run python scripts/docling_reparse.py 2>&1 | tee /tmp/docling_resume.log

# Re-validate after resume
uv run python scripts/validate_parse_output.py
```

---

## What shipped (Saturday 2026-04-11)

### Step 0: Docling bug fix + smoke test — DONE
- Bug reproduced (11/58 pages on nsm__101126915)
- Fix verified (58/58 pages via export_to_markdown(page_no=N))
- Docling 2.86.0, DuckDB 1.4.4 confirmed

### Step 1 (PR #1): Docling Phase A — DONE (7 commits)
- `DoclingParser` class with lazy import, per-page markdown export
- `strip_markdown()` — preserves table content for FTS
- Registry registration, config default flipped to "docling"
- CLI rewire: `get_parser()` replaces hardcoded `PyMuPDFParser()`
- `scripts/docling_reparse.py` fixed: per-page export, JSONL contract, LuxSE glob
- Decision 18 doc updated
- 13 parser tests + 8 strip_markdown tests

### Step 2: NSM + EDGAR incrementals — DONE
- NSM: 913 discovered, 5 new PDFs downloaded (DRC confirmed)
- EDGAR: 3,307 discovered, all existing (no new filings)

### Step 3: LuxSE adapter — DONE (download still running)
- Reverse-engineered GraphQL API at `graphqlaz.luxse.com/v1/graphql`
- Discovery: 5,926 unique sovereign documents
- Download: confirmed %PDF magic bytes, ~800+ PDFs downloaded (still running)
- 10 adapter tests

### PR #3 pre-work: FTS, markdown, MotherDuck — DONE
- `document_markdown` + `document_pages` DDL (sql/001_corpus.sql)
- `build_pages()` + `create_fts_index()` (src/corpus/db/pages.py) — 4 tests
- `build_markdown()` (src/corpus/db/markdown.py) — 4 tests
- `publish_to_motherduck()` (src/corpus/db/publish.py)
- `read_jsonl_header()` for parse_tool/page_count backfill — 4 tests
- CLI: `corpus build-pages`, `build-markdown`, `publish-motherduck`
- `scripts/promote_parsed_dir.py` — directory promotion
- `scripts/validate_parse_output.py` — morning validation

### Overnight parse safeguards added
- Resume filter checks BOTH .jsonl AND .md (not just .jsonl)
- Pre-flight: disk space check (>5GB), stale .part cleanup
- Default timeout bumped 300s → 600s for large LuxSE PDFs
- Validation script for the morning

---

## Overnight parse command

```bash
# Delete broken March 28 outputs (ONE TIME — do not re-delete on crash/resume)
rm -rf data/parsed_docling/

# Run the fixed script
caffeinate -d -i uv run python scripts/docling_reparse.py 2>&1 | tee /tmp/docling_overnight.log

# Monitor from another terminal:
tail -f data/parsed_docling/_progress.jsonl
```

Expected: ~2,500+ docs (NSM 645 + PDIP 823 + LuxSE ~800+) at ~10s/doc = ~7hrs.

---

## What's left for Sunday

| Step | Task | Est. |
|------|------|------|
| Step 5 | Validate overnight parse | 15 min |
| Step 6 | Promotion + rebuild + pages + markdown + grep + MotherDuck | 1-2 hr (mostly runtime) |
| Step 7 | PR #4: Streamlit explorer | 3-6 hr |
| Step 8 | Polish + demo script | 30-60 min |

---

## Key file locations

| What | Where |
|------|-------|
| Spec v2 | `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md` |
| Implementation plan | `docs/superpowers/plans/2026-04-11-spring-meetings-sprint.md` |
| LuxSE spec | `docs/superpowers/specs/2026-04-11-luxse-adapter-design.md` |
| DoclingParser | `src/corpus/parsers/docling_parser.py` |
| strip_markdown | `src/corpus/parsers/markdown.py` |
| LuxSE adapter | `src/corpus/sources/luxse.py` |
| Page ingest + FTS | `src/corpus/db/pages.py` |
| Markdown ingest | `src/corpus/db/markdown.py` |
| MotherDuck publish | `src/corpus/db/publish.py` |
| JSONL header ingest | `src/corpus/db/ingest.py` (read_jsonl_header) |
| Reparse script (fixed) | `scripts/docling_reparse.py` |
| Validation script | `scripts/validate_parse_output.py` |
| Promotion script | `scripts/promote_parsed_dir.py` |
