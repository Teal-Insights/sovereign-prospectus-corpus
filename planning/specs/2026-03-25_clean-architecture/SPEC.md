# SPEC: Clean Architecture Rebuild

**Date:** 2026-03-25
**Status:** Ready for implementation
**Deadline:** March 30, 2026 (Georgetown Law roundtable)
**Time budget:** ~15-20 hours across March 25-29

## Problem Statement

Phase 0 scripts proved the concept but accumulated tech debt (wrong database, country
in paths, filtering bugs, no tests). We need a clean rewrite with sturdy foundations
that can support long-term monitoring, multi-output delivery, and community contribution.

## MVP for Monday

A large-scale corpus with CAC (Collective Action Clause) analysis:
- Thousands of documents across dozens of countries in DuckDB
- CAC variations extracted and structured (no CAC → single-limb → double-limb → aggregated)
- At least one visualization showing CAC evolution over time
- Proper metadata, logging, and provenance from the start

**Stretch goal:** Analysis of recent restructuring cases (Zambia, Ghana, Senegal).

## Design Principles

1. **Foundations first.** Get the database schema, logging, and safe_write() right
   before bulk processing. Phase 0 was a learning round — this is the real build.
2. **Migrate existing data where possible.** ~5,400 PDFs from Phase 0 should be
   transferred into the new path structure with proper metadata. Re-download only
   if migration can't capture the right metadata/logging format.
3. **Parallel worktrees.** Source adapters (NSM, EDGAR, PDIP) can be built in
   parallel using git worktrees and separate Claude Code sessions.4. **Separation of concerns.** The corpus/database is the core asset. Outputs
   (email digests, dashboards, exports, notebooks) are read-only consumers that
   can be added modularly without touching the pipeline.
5. **Test-driven development.** Superpowers enforces TDD. Testing strategy to be
   informed by council of experts (known failure modes of agentic coding tests).
6. **Overnight autonomous execution.** Tasks must be well-defined enough to run
   with `--dangerously-skip-permissions` on a Mac Mini overnight.

## Scope Boundaries

**In scope for Monday:**
- DuckDB schema with proper metadata and provenance columns
- Structured JSONL logging from the start
- safe_write() with atomic .part → rename pattern
- NSM source adapter (fixed: multi-LEI bug, Canada pollution, no filters)
- EDGAR source adapter
- PDIP source adapter (or migration of existing PDFs)
- PyMuPDF text extraction
- Grep-first CAC pattern matching
- CAC classification and visualization
- Makefile orchestration
- Pre-commit hooks (ruff + pyright + pytest)
- Migration script for Phase 0 data

**Out of scope for Monday (but architecture must not preclude):**
- Docling parser (swap in after Monday)
- Full clause extraction beyond CACs (events of default, governing law, pari passu)
- Real-time monitoring / cron jobs
- Email digest output
- Dashboard output
- Document family linking (base + supplements + final terms)
- PDIP comparison / eval framework
- Academic paper analysis
## Strategic Context

The roundtable audience are leading sovereign debt legal scholars and practitioners.
They are experts in depth — reading individual documents closely. The value
proposition is demonstrating a different paradigm: AI-powered breadth at scale.

Key messages for the demo:
- Existing expert-annotated corpus has ~900 docs (subset annotated). This pipeline
  produces 5,000+ with structured extraction in days, not years.
- Structured rectangular data enables policy-relevant analysis (trends over time,
  by region, by law firm, by legal jurisdiction) that PDF-by-PDF review cannot.
- The grep → LLM → eval pipeline means domain experts' corrections (marking
  extractions as wrong) directly improve future accuracy via few-shot prompts.
- This is offered as open-source infrastructure to complement existing efforts.

## Technical Architecture

See `docs/RATIFIED-DECISIONS.md` for the full 20 ratified decisions.
See `docs/ARCHITECTURE.md` for the target directory structure.
See `docs/DOMAIN.md` for source details and clause types.

Key technical choices:
- DuckDB (not SQLite), Polars (not Pandas), Click CLI, uv
- `{source}__{native_id}` storage keys (no country in paths)
- Protocol-based parser: PyMuPDF now, Docling after Monday
- Makefile orchestration with RUN_ID traceability
- Structured JSONL logging (run_id, document_id, step, duration_ms, status)
- Verbatim extraction: `assert exact_quote in raw_pdf_text`

## Open Questions for Council

- What is the most important testing strategy for an agentic coding pipeline?
- What are the known failure modes of AI-generated tests, and how to avoid them?
- What's the right granularity for golden master tests?