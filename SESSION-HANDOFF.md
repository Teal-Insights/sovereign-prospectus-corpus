# SESSION-HANDOFF.md — Current Sprint

**Last updated:** 2026-04-10
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Sprint spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md`
**Status:** Task 1 merged. Next up: Task 2 (Provenance URLs + Schema).

## Live artifacts

- **Explorer URL:** https://sovereign-prospectus-corpus.streamlit.app
- **MotherDuck database:** `sovereign_corpus` (4,769 documents, duckdb 1.4.4 client/server)
- **V1 Georgetown demo:** tagged `v1-georgetown-2026-03-30` (Quarto book on `gh-pages` branch — do NOT modify)

## Sprint Tasks

- [x] Task 1: Deployment Spike (Streamlit Cloud + MotherDuck) — PR #61 merged
- [ ] **Task 2: Provenance URLs + Schema** ← NEXT
- [ ] Task 3: Search Index + Parsed Text Loading
- [ ] Task 4: Streamlit Document Explorer
- [ ] Task 5: LSE RNS Adapter + Congo Ingest (gated)
- [ ] Task 6: LuxSE Adapter (gated, overflow)
- [ ] Task 7: Clause Family Display (overflow)
- [ ] Task 8: ESMA Adapter (overflow)
- [ ] Task 9: Demo Polish (overflow)

Sprint GitHub issues: #51-#59 with label `sprint:spring-meetings-2026`.

## Task 2 — what's ready

**Spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md` lines 183-227. Issue #52.
**Branch:** not yet created. Use `feature/provenance-urls`.

**Research already done** (saved at `docs/superpowers/specs/2026-04-10-task2-manifest-research.md`):
- EDGAR manifest already has `cik` + `accession_number` in `source_metadata` → can construct filing-index URLs directly
- NSM manifest's `download_url` IS already the artefact URL → just classify by extension
- PDIP has no per-document deep links → use `search_page` kind only
- Schema changes: add 2 columns to `sql/001_corpus.sql`, add 2 fields to `_DOCUMENT_COLUMNS` in `src/corpus/db/ingest.py`

## Task 1 recap (what shipped)

- `explorer/app.py` with MotherDuck connection (`read_only=True`, `ttl=3600` cache)
- Root `requirements.txt` (streamlit==1.45.1, duckdb==1.4.4, pandas>=2.0)
- Pipeline DuckDB upgraded 1.2.2 → 1.4.4 in pyproject.toml (361/361 tests pass)
- MotherDuck `documents` table populated from local DB via 1.4.4 client
- Sprint spec updated with 5 Streamlit Cloud deployment gotchas

## Phase 1 (Complete, reference only)

All Phase 1 planning docs archived in `archive/phase-1/`.

- NSM: 642 PDFs (591 MB), 899 sovereign filings discovered
- EDGAR: 3,301 PDFs (587 MB), 3,306 filings from 27 CIKs
- PDIP: 823 documents (5 GB), zero download failures
- PDIP annotations: 162/162 processed (122 success, 40 zero-clause)

## Open Pre-Existing Issues

Carried from Phase 1: #5, #6, #7, #8, #9, #11, #12, #13, #16, #18, #19, #24,
#25, #30, #33-#42. Don't block on these unless directly relevant to current task.
