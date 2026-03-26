# CLAUDE.md — Sovereign Bond Prospectus Corpus

## Quick Start

1. Read `SESSION-HANDOFF.md` for the current task
2. Read the task spec linked from SESSION-HANDOFF.md
3. Confirm understanding before writing code
4. If stuck after 5 attempts: document the blocker, move on

## Project

Build a structured, searchable corpus of sovereign bond prospectuses that surfaces meaningful variation in contract terms across issuers and over time. Prospectuses are ~90% boilerplate; the ~10% that varies (CACs, events of default, governing law) is where the value lives.

**Who:** Teal Insights (open-source SovTech infrastructure for sovereign debt and climate finance).
**Why now:** Proof-of-concept for Georgetown Law roundtable, March 30, 2026.
**Sources:** FCA NSM, SEC EDGAR, World Bank PDIP.

## Architecture Decisions (Ratified March 25, 2026)

1. **DuckDB** as single source of truth. One unified `corpus.duckdb`. Pin version.
2. **Breadth over depth.** Get everything, filter later. No country/doc-type filters at download.
3. **No Selenium.** Accept two-hop latency.4. **Modular output layer.** Pipeline (download→parse→extract→store) separate from outputs (dashboard, email, exports). Outputs are read-only consumers.
5. **Atomic file writes.** `safe_write()` refuses overwrites. `.part` → rename pattern.
6. **Core table + JSON metadata.** No source-specific join tables.
7. **No country in file paths.** `{source}__{native_id}` as storage key. Country in DB only.
8. **Protocol-based parser swapping.** PyMuPDF now, Docling later. Module swap, not rewrite.
9. **Makefile orchestration.** Not Prefect/Dagster/Luigi. `RUN_ID` for traceability.
10. **Structured JSONL logging.** Append-only, run_id, document_id, step, duration_ms, status.
11. **Pre-commit hooks + CI.** ruff → pyright → pytest. Block commits to main. Block data/ from git.
12. **Grep-first clause finding.** Regex locates clause sections, then targeted LLM extraction.
13. **Verbatim extraction only.** `assert exact_quote in raw_pdf_text`. No paraphrasing.
14. **Start clean.** Phase 1 scripts are reference only. Rewrite from scratch.

Full rationale: `docs/RATIFIED-DECISIONS.md`

## Coding Standards

- **Python 3.12+**, PEP 8, managed by **uv**
- **Polars** (not Pandas), **DuckDB** (not SQLite), **Click** for CLI
- **ruff** for linting/formatting, **pyright** basic mode, **pytest**
- Trunk-based development, feature branches, small PRs

## Domain Rules

1. Every extraction shown at roundtable must be hand-verified. No exceptions.
2. "Not found" is valid output. Never force extractions.
3. Page citations are non-negotiable.
4. Silent LLM paraphrasing is the scariest failure mode. Enforce verbatim.
5. Document families matter (base prospectus + supplements + final terms).
Full domain context: `docs/DOMAIN.md`

## Source of Truth Hierarchy

1. Actual prospectus text (highest)
2. PDIP annotations (expert baseline)
3. NSM metadata
4. Pipeline architecture docs
5. Agent reasoning (lowest)

## Key References

- **Current task:** `SESSION-HANDOFF.md`
- **Task specs:** `planning/tasks/`
- **NSM API:** `docs/nsm_api_reference.md`
- **PDIP API:** `docs/pdip_data_extraction_assessment.md`
- **Council decisions:** `docs/RATIFIED-DECISIONS.md`
- **Domain context:** `docs/DOMAIN.md`
- **Directory structure:** `docs/ARCHITECTURE.md`
- **Reference scripts (bugs — do not copy directly):** `scripts/`

## Do Not

- Use Pandas (use Polars)
- Put country in file paths
- Filter countries or doc types at download time
- Use Docling before Monday (PyMuPDF only)
- Use Prefect/Dagster/Luigi (Makefile only)
- Carry forward tech debt from Phase 1 scripts
- Skip hand-verification of any demo extraction