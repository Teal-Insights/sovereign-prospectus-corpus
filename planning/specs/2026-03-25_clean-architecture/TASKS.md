# TASKS: Clean Architecture Rebuild (Revised per Council Round 3)

**Spec:** `planning/specs/2026-03-25_clean-architecture/SPEC.md`
**Council synthesis:** `planning/council-of-experts/round-3/2026-03-25_synthesis.md`
**Execution mode:** Parallel worktrees where possible, `--dangerously-skip-permissions`

## Phases

**Phase 1 (tonight): Download infrastructure.** Get documents downloading correctly.
Priority: scaffold → core utils → CLI → NSM adapter running overnight.

**Phase 2 (after downloads work): Extraction + analysis.**
Gold corpus, CAC patterns, visualization. Requires separate planning.

## Task Order

Foundation tasks (1-4) are sequential. Source adapters (5-7) run in parallel
worktrees after foundations merge.

**Cut order if behind:** 9 (viz) → 7 (PDIP migration) → 6 (EDGAR) → keep 5 (NSM) as minimum.
**Tonight's target:** Tasks 1 → 2 → 3 → 4 (NSM downloading overnight).

**Status (2026-03-26):** Tasks 1-4 COMPLETE. NSM: 899 sovereign filings discovered, 642 PDFs downloaded. See CLAUDE.md "Lessons Learned from NSM Adapter" before starting Tasks 5-6.

**Key architectural change (council consensus):** Adapters do NOT write directly
to DuckDB. They download files and produce `{source}_manifest.jsonl`. A serial
`ingest` step loads all manifests into DuckDB. This avoids DuckDB's single-writer
limitation during parallel execution.

---

### Task 1: Project Scaffold + DuckDB Schema + Parser Protocol
**Branch:** `feature/scaffold`
**Issue title:** Set up project structure, DuckDB schema, and parser protocol

Create `src/corpus/` package structure, DuckDB schema with all tables
(documents, document_countries, grep_matches, source_events, pipeline_runs),
schema creation script, parser Protocol class, and PyMuPDF adapter. Pin DuckDB
version. (Merges original Tasks 1+3 per council recommendation — parser protocol
is small and gives adapters something to test against immediately.)

**Completion criteria:**
- [ ] `src/corpus/__init__.py` exists with version
- [ ] `src/corpus/db/schema.py` creates all tables
- [ ] `sql/001_corpus.sql` has DDL matching RATIFIED-DECISIONS
- [ ] `src/corpus/parsers/base.py` — Protocol class with `parse(path) -> ParseResult`
- [ ] `src/corpus/parsers/pymupdf_parser.py` — extracts text, returns pages
- [ ] `src/corpus/parsers/registry.py` — factory, reads `config.toml [parser] default`
- [ ] `uv run pytest tests/test_schema.py` — schema round-trips: create → inspect → matches spec
- [ ] `uv run pytest tests/test_parsers.py` — tests with fixture PDF
- [ ] Swapping parser in config.toml does not require code changes
- [ ] ruff + pyright pass

### Task 2: Core Utilities (safe_write, logging, HTTP)
**Branch:** `feature/core-utils`
**Issue title:** Implement safe_write, structured logging, and HTTP client

**Completion criteria:**
- [ ] `src/corpus/io/safe_write.py` — atomic .part → rename, refuses overwrites
- [ ] `src/corpus/logging.py` — JSONL with run_id, document_id, step, duration_ms, status
- [ ] `src/corpus/io/http.py` — retry, backoff, User-Agent from .env
- [ ] `uv run pytest tests/test_safe_write.py` — tests overwrite refusal, partial cleanup on error
- [ ] `uv run pytest tests/test_logging.py` — tests JSONL format, required fields
- [ ] ruff + pyright pass

### Task 3: CLI + Makefile Orchestration
**Branch:** `feature/cli`
**Issue title:** Click CLI entry point and Makefile targets with JSONL ingest

Includes the JSONL manifest → DuckDB ingest pattern. Each adapter writes a
manifest; `corpus ingest` reads all manifests and writes to DuckDB serially.

**Completion criteria:**
- [ ] `src/corpus/cli.py` — Click groups: download, parse, grep, extract, ingest
- [ ] `src/corpus/db/ingest.py` — reads `{source}_manifest.jsonl`, writes to DuckDB
- [ ] `Makefile` — targets for each pipeline step, RUN_ID generation
- [ ] `make ingest` target runs serial DuckDB loading from JSONL manifests
- [ ] `uv run corpus --help` works
- [ ] `make download-nsm` invokes CLI correctly
- [ ] ruff + pyright pass

### Task 4: NSM Source Adapter — Re-download
**Branch:** `feature/source-nsm`
**Issue title:** NSM downloader — fix bugs, remove filters, re-download all

Re-downloads everything fresh (Phase 0 NSM data is invalid due to bugs).
Writes files + `nsm_manifest.jsonl`, does NOT write to DuckDB directly.

**Completion criteria:**
- [ ] `src/corpus/sources/nsm.py` — downloads all documents, no country/type filters
- [ ] Multi-LEI bug fixed (OR, not AND)
- [ ] Canada name-search pollution handled
- [ ] Uses safe_write() for PDF downloads
- [ ] Produces `nsm_manifest.jsonl` (one record per document with metadata)
- [ ] Logs to JSONL structured log
- [ ] `uv run pytest tests/test_nsm.py` — tests with recorded API responses
- [ ] ruff + pyright pass

### Task 5: EDGAR Source Adapter + Migration (PARALLEL)
**Branch:** `feature/source-edgar`
**Issue title:** EDGAR downloader + migrate existing Phase 0 EDGAR files

EDGAR Phase 0 data is clean — migrate existing files into new path structure
and produce manifest. New downloads for any missing docs use SEC-compliant
rate limiting.

**Completion criteria:**
- [ ] `src/corpus/sources/edgar.py` — SEC-compliant User-Agent from .env
- [ ] Rate-limited (10 req/sec), circuit breaker
- [ ] Migration script restructures existing EDGAR PDFs into `{source}__{native_id}` paths
- [ ] Produces `edgar_manifest.jsonl`
- [ ] Uses safe_write(), logs to JSONL
- [ ] `uv run pytest tests/test_edgar.py` — tests with recorded responses
- [ ] ruff + pyright pass

### Task 6: PDIP Source Adapter + Migration (PARALLEL)
**Branch:** `feature/source-pdip`
**Issue title:** PDIP adapter — keep hand-downloads, download API-available fresh

Hand-downloaded PDIP files stay as-is with metadata backfill. API-available
documents downloaded fresh. Produces manifest for ingest.

**Completion criteria:**
- [ ] `src/corpus/sources/pdip.py` — downloads API-available docs with correct headers
- [ ] Migration script for hand-downloaded Phase 0 PDFs: restructure paths, backfill metadata
- [ ] Produces `pdip_manifest.jsonl`
- [ ] Uses safe_write(), logs to JSONL
- [ ] `uv run pytest tests/test_pdip.py` — tests with recorded responses
- [ ] ruff + pyright pass

### Task 7: Grep-First CAC Extraction (Phase 2)
**Branch:** `feature/cac-extraction`
**Issue title:** CAC pattern matching and classification

Phase 2 — requires separate planning. Uses gold corpus + downloaded docs.

**Completion criteria:**
- [ ] `src/corpus/extraction/grep_patterns.py` — versioned CAC regex patterns
- [ ] Classifies: no CAC / single-limb / double-limb / aggregated
- [ ] `grep_matches` table populated with page numbers and matched text
- [ ] `assert exact_quote in raw_pdf_text` passes for all extractions
- [ ] Golden master tests pass against hand-verified fixture docs
- [ ] `uv run pytest tests/test_grep_patterns.py` — tests against fixture docs
- [ ] ruff + pyright pass

### Task 8: CAC Visualization Notebook (Phase 2)
**Branch:** `feature/cac-viz`
**Issue title:** CAC evolution visualization for roundtable demo

Deliverable is a notebook in `notebooks/`, not pipeline code. Exploratory
analysis that can be iterated on presentation day.

**Completion criteria:**
- [ ] `notebooks/cac_evolution.ipynb` (or `.py` Marimo notebook)
- [ ] Chart: CAC type × country × year showing evolution over time
- [ ] Uses Polars for data manipulation, reads from DuckDB
- [ ] Output suitable for presentation (exportable image or interactive)

### Task 9: Integration Test + Overnight Run
**Branch:** `feature/integration`
**Issue title:** End-to-end pipeline test and overnight execution prep

**Completion criteria:**
- [ ] `make all` runs full pipeline: download → parse → ingest → grep → extract
- [ ] Integration test with gold corpus documents end-to-end
- [ ] All pre-commit hooks pass (ruff + pyright + pytest)
- [ ] Pipeline can run unattended with `--dangerously-skip-permissions`
- [ ] DuckDB contains expected tables with non-zero row counts
- [ ] Golden master assertions pass on ingested data
- [ ] Text quality sanity check flags garbled PyMuPDF output (multi-column risk)
