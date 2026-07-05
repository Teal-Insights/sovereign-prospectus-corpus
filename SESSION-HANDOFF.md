# SESSION-HANDOFF.md

**Last updated:** 2026-07-04 (TEA-903: explorer-web parity build)

## Session 2026-07-04 (latest): TEA-903 (Explorer v2, S3)

Explorer core built to v1 Shiny parity on the S2 scaffold. PR pending
merge go-ahead; Linear TEA-903 has the full trail; spec + plan with all
council dispositions in docs/superpowers/.

- **What shipped:** multi-select filters (select+chips) with repeated
  query params and unknown-param passthrough; scope status matrix with
  marginal hidden counts; segment-by-TOC-offset rendering above 1M UTF-16
  units (620 docs; "Segment", never "Part"); in-document search (compute
  guards: min length 2, 20K cap, index-only) with CSS Custom Highlight
  paints, live-region announcements, and a q param that never bypasses
  the 5 MB gate; history discipline (pushState interactions, replaceState
  corrections, popstate never writes); baked static shell.
- **Gates:** spec 6 reviewers, plan 5, PR 5 + a 28-agent code-review
  workflow; every disposition recorded (spec/plan docs + PR comment).
  Lighthouse 100 perf / 100 a11y / CLS 0 (bare and parameterized browse;
  doc 98/100). P1-P22 parity verified side by side against v1 run on the
  deployed MotherDuck data path. Fixture: issue #88 shapes landed
  (synthetic-gate/astral/large).
- **Deferred/known:** #84 vintage footnote still hardcoded (comment links
  the issue); #86 pages[].offset_utf16 still unconsumed; VoiceOver
  listen-through optional for Teal (live-region text machine-verified).
- **Dev notes unchanged** (Node >= 22.12; smoke now needs the two-origin
  serve recipe in scripts/smoke.mjs header; CI runs it on the fixture).

## Session 2026-07-04 (later): TEA-902 (Explorer v2, S2)

explorer-web/ scaffolded (Astro 6.4.8 + DuckDB-WASM 1.32.0) and all three
spike risks proven with numbers. PR #87 (awaiting merge go-ahead); Linear
TEA-902 has the full trail; decisions + measurements in
explorer-web/ARCHITECTURE.md and explorer-web/measurements/NOTES.md.

- **Spike verdicts:** in-browser DuckDB-WASM over the snapshot parquet
  PASS (cold ~1.4-1.5 s to first rows, warm ~0.8 s, throttled 9.2 s,
  ~8.7 MB cold transfer); 10k-page pre-render PASS (9,775 pages in
  ~4.7 s, 683 MB peak RSS); config-driven data URLs PASS (astro:env
  fail-fast; CORS proven with a two-origin harness). Lighthouse 100 /
  CLS 0; bfcache genuinely restores (159 ms, measured with full Chrome
  after the council caught Playwright's default disabling bfcache).
- **Council gates ran at spec, plan, and PR** (6+4+4 fresh reviewers).
  Highest-value catches: wasm is 34 MB raw/5.9 MB brotli (hosting
  constraint), npm latest of duckdb-wasm is a dev build, 22.3% of
  snapshot rows are non-sovereign (browse now defaults to sovereign
  scope with live counts + badges), FY2027 classification vintage
  footnote, the invalid bfcache measurement.
- **Deferred issues:** #84 (classification_vintage in MANIFEST), #85
  (unmapped_issuers audit gap), #86 (pages[].offset_utf16), #88
  (fixture text-scale shapes), #89 (wasm fetch split via CDP worker
  auto-attach).
- **Dev notes:** explorer-web needs Node >= 22.12; npm run dev serves
  the repo snapshot at /data; astro preview does not (use
  scripts/serve-static.mjs); scripts/smoke.mjs is the browse smoke;
  scripts/measure.mjs is the spike harness (run from explorer-web/).
- **Next (S3, TEA-903):** parity build on these seams. Read
  ARCHITECTURE.md "Inputs for S3" first; the TEA-903 parity pointer
  should be shiny/app.py, not demo/shiny-app/ (noted on the issue).

## Session 2026-07-04: TEA-901 (Explorer v2, S1)

Corpus refreshed to present and static snapshot format defined. Linear
TEA-901 has the full trail; PR #78 has the code.

- **Corpus refresh (run id `refresh-20260704`):** EDGAR 30 new (current
  through 2026-06-30), NSM 15 new PDFs (current through 2026-06-03),
  0 download failures. Corpus: 9,729 to 9,774 documents. Derived tables
  (document_pages, document_markdown, FTS) refreshed.
- **Snapshot builder:** `uv run python scripts/build_snapshot.py` writes
  `data/snapshot/` (documents.parquet 1.1 MB, text/ 9,671 JSON files
  2.5 GB, MANIFEST.json). Schema version 1. See README.
- **Pipeline fix:** `corpus parse run` now writes the markdown sidecar
  that `build-markdown` consumes (was silently discarded before; only
  the bulk reparse scripts produced .md files).
- **Known state:** 103 documents have no text (84 EDGAR `.paper`
  placeholders + 19 unparseable). LuxSE has a separate backlog: only
  ~10 LuxSE parse outputs live in `data/parsed`; the full April set is
  in `data/parsed_docling` (DB tables are complete, but `parse run
  --source all` would try to re-parse 4,945 LuxSE PDFs — avoid).

---

# Archive: Spring Meetings Sprint (overnight parse)

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

# 3. DELETE old DB and rebuild from scratch (existing DB has 4,769 rows
#    with NULL parse_tool — ingest skips existing rows, so backfill won't
#    work without a fresh start)
rm -f data/db/corpus.duckdb
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
