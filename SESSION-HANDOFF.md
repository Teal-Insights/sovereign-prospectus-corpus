# SESSION-HANDOFF.md — Current Task

**Last updated:** 2026-03-26
**Status:** Phase 1 tasks 1-5 complete. NSM + EDGAR downloading done. Ready for Task 6 (PDIP).

## Completed

- **Task 1:** Project scaffold, DuckDB schema, parser protocol ✅
- **Task 2:** Core utilities (safe_write, logging, HTTP client) ✅
- **Task 3:** Click CLI, JSONL manifest ingest, Makefile orchestration ✅
- **Task 4:** NSM source adapter — sovereign discovery + download ✅
  - 899 sovereign filings discovered, 642 PDFs downloaded (591 MB)
  - Two-phase: `corpus discover nsm` → `corpus download nsm`
- **Task 5:** EDGAR source adapter — sovereign discovery + download ✅
  - 3,306 filings discovered from 27 sovereign CIKs, 3,301 downloaded (587 MB)
  - Two-phase: `corpus discover edgar` → `corpus download edgar`
  - PR #10: `feature/source-edgar`

## Next Tasks

See `planning/specs/2026-03-25_clean-architecture/TASKS.md` for full task list.

**Phase 1 remaining:**
- **Task 6:** PDIP source adapter + migration (PARALLEL)

**Phase 2:**
- **Task 7:** Grep-first CAC extraction
- **Task 8:** CAC visualization notebook
- **Task 9:** Integration test + overnight run

**Before starting a new source adapter:** Read "Lessons Learned from NSM Adapter" in CLAUDE.md. Key patterns: two-phase discover/download, sovereign-scoped queries, explicit telemetry logging, circuit breaker testing.

## Quick Reference

- Architecture decisions: `docs/RATIFIED-DECISIONS.md`
- Domain context: `docs/DOMAIN.md`
- Directory structure: `docs/ARCHITECTURE.md`
- NSM API: `docs/nsm_api_reference.md`
- PDIP API: `docs/pdip_data_extraction_assessment.md`
- NSM design spec: `docs/superpowers/specs/2026-03-26-nsm-sovereign-discovery-design.md`
- NSM implementation plan: `docs/superpowers/plans/2026-03-26-nsm-sovereign-discovery.md`

## Do Not

- Use Pandas (use Polars)
- Put country in file paths
- Filter countries or doc types at download time
- Use Docling before Monday (PyMuPDF only)
- Use Prefect/Dagster/Luigi (Makefile only)
- Copy Phase 1 scripts directly — rewrite them
