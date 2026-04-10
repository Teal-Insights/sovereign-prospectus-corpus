# SESSION-HANDOFF.md — Current Sprint

**Last updated:** 2026-04-10
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Sprint spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md`
**Status:** Task 2 PR #69 open, awaiting external reviews. Next up: Task 3 (Search Index + Parsed Text Loading).

## Live artifacts

- **Explorer URL:** https://sovereign-prospectus-corpus.streamlit.app
- **MotherDuck database:** `sovereign_corpus` (4,769 documents, duckdb 1.4.4 client/server) — still on the pre-Task-2 schema. Task 3 publishes the new columns.
- **V1 Georgetown demo:** tagged `v1-georgetown-2026-03-30` (Quarto book on `gh-pages` branch — do NOT modify)

## Sprint Tasks

- [x] Task 1: Deployment Spike (Streamlit Cloud + MotherDuck) — PR #61 merged
- [x] Task 2: Provenance URLs + Schema — PR #69 open
- [ ] **Task 3: Search Index + Parsed Text Loading** ← NEXT
- [ ] Task 4: Streamlit Document Explorer
- [ ] Task 5: LSE RNS Adapter + Congo Ingest (gated)
- [ ] Task 6: LuxSE Adapter (gated, overflow)
- [ ] Task 7: Clause Family Display (overflow)
- [ ] Task 8: ESMA Adapter (overflow)
- [ ] Task 9: Demo Polish (overflow)

Sprint GitHub issues: #51-#59 with label `sprint:spring-meetings-2026`.

## Task 2 recap (what shipped in PR #69)

**Plan:** `docs/superpowers/plans/2026-04-10-task2-provenance-urls.md` (went through 3 external reviews + 1 internal pre-push review before merging).

- `documents.source_page_url` and `documents.source_page_kind` columns added
- Per-source resolvers in `src/corpus/sources/provenance.py`:
  - EDGAR: constructs SEC filing-index URL from `cik` + `accession_number`
  - NSM: uses `download_url` as-is, classifies by extension via `urllib.parse.urlparse` so query strings can't defeat it
  - PDIP: static Georgetown search page (no per-doc deep links exist)
  - Dispatcher returns `(None, "none")` for unknown sources — safe for future adapters
- `scripts/regenerate_pdip_manifest.py` — one-off bridge that regenerates `pdip_manifest.jsonl` from current DB + inventory CSV, normalizing free-text dates to ISO via a small parser (`"January 20, 2017"`, `"24 September 2025"`, `"July 6th, 2018"` all handled)
- `scripts/backfill_provenance_urls.py` — atomic rewrite of all three manifests, idempotent including for unknown-source records (gates on key presence, not truthiness)
- Local DB rebuilt: 4,769 docs with non-null `source_page_url`, `pdip_clauses` (6,251) and `grep_matches` (106,229) preserved via `ATTACH` + `INSERT` with `storage_key`-based FK remap
- `.pre-commit-config.yaml:26` YAML bug fixed (pre-existing, blocked every invocation of `pre-commit run`)

## Follow-up issues filed during Task 2

- **#66** — PDIP ingest bypasses manifest-canonical pipeline. Worked around, not fixed. Scripts/inventory/file-paths should eventually migrate.
- **#67** — Pre-commit was broken on main (163 ruff errors in `scripts/`, 9 format violations, and the YAML parse error). YAML fixed in this PR; the rest is tech debt.
- **#68** — DB rebuild preservation (`pdip_clauses` + `grep_matches` ATTACH + INSERT) should be promoted from an ad-hoc heredoc to a committed script before Task 3's `make publish-motherduck` runs.

## Task 3 — what's ready

**Spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md` lines 242-332. Issue #53.
**Branch:** not yet created. Use `feature/search-index`.

Task 3 is five subtasks:
- 3A: `documents_search` denormalized view/table
- 3B: `document_pages` table from `data/parsed/*.jsonl` + FTS index
- 3C: `country_classifications` from World Bank data
- 3D: Heuristic country backfill for EDGAR/NSM rows
- 3E: Makefile targets `make build-search-index` + `make publish-motherduck`

**Pre-flight reminders for Task 3:**
- Resolve #68 (DB preservation script) before the first `make publish-motherduck` runs, or re-derive the ATTACH + INSERT block from the Task 2 plan (`docs/superpowers/plans/2026-04-10-task2-provenance-urls.md`, Task 7 Step 9).
- `data/parsed/` contents should be checked for per-source / per-document coverage before loading — counts of parsed documents should roughly match the `documents` counts (4,769 expected).
- MotherDuck publish needs the same `MOTHERDUCK_TOKEN` in `.env` that Task 1 used. Token is not committed.
- The live explorer currently reads from MotherDuck without the new provenance columns. After Task 3 runs `publish-motherduck`, the explorer needs a restart (Streamlit Cloud auto-redeploys on git push; no-op push might be needed).

## Phase 1 (Complete, reference only)

All Phase 1 planning docs archived in `archive/phase-1/`.

- NSM: 642 PDFs (591 MB), 899 sovereign filings discovered
- EDGAR: 3,301 PDFs (587 MB), 3,306 filings from 27 CIKs
- PDIP: 823 documents (5 GB), zero download failures
- PDIP annotations: 162/162 processed (122 success, 40 zero-clause)

## Open Pre-Existing Issues

Carried from Phase 1: #5, #6, #7, #8, #9, #11, #12, #13, #16, #18, #19, #24, #25, #30, #33-#42. Don't block on these unless directly relevant to current task.

Task-2-discovered: #66 (PDIP tech debt), #67 (pre-commit tech debt), #68 (DB preservation script).
