# SESSION-HANDOFF.md — Current Task

**Last updated:** 2026-03-25 (post council round 3)
**Status:** Council reviewed. Tasks revised. Ready for implementation.

## Current Task

Implement the clean architecture rebuild:
- **Spec:** `planning/specs/2026-03-25_clean-architecture/SPEC.md`
- **Tasks:** `planning/specs/2026-03-25_clean-architecture/TASKS.md`
- **Council synthesis:** `planning/council-of-experts/round-3/2026-03-25_synthesis.md`

**Phase 1 (tonight):** Tasks 1-4. Scaffold → core utils → CLI → NSM downloading overnight.
**Phase 2 (later):** Gold corpus, CAC extraction, visualization. Separate planning needed.

**Critical:** Adapters write JSONL manifests, NOT directly to DuckDB. Serial
`ingest` step loads manifests into DuckDB (avoids single-writer conflicts).

## Quick Reference

- Architecture decisions: `docs/RATIFIED-DECISIONS.md`
- Domain context: `docs/DOMAIN.md`
- Directory structure: `docs/ARCHITECTURE.md`
- NSM API: `docs/nsm_api_reference.md`
- PDIP API: `docs/pdip_data_extraction_assessment.md`

## Do Not

- Use Pandas (use Polars)
- Put country in file paths
- Filter countries or doc types at download time
- Use Docling before Monday (PyMuPDF only)
- Use Prefect/Dagster/Luigi (Makefile only)
- Copy Phase 1 scripts directly — rewrite them