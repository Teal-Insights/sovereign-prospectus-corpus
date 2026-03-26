# CLAUDE.md — Sovereign Bond Prospectus Corpus

## Task Execution Workflow (MANDATORY)

This is the end-to-end checklist for every task. Do not skip steps. Do not ask
the user which steps to use — just follow them. The user runs with
`--dangerously-skip-permissions` and expects autonomous execution.

### Phase 1: Understand (before writing any code)

- [ ] Read `SESSION-HANDOFF.md` for the current task
- [ ] Read the task spec and completion criteria
- [ ] Run `gh issue list` — incorporate any open issues that overlap with this task
- [ ] Read "Lessons Learned" section below if building a source adapter
- [ ] **Assess completeness of spec.** Do the completion criteria cover everything
  the task title implies? (e.g., "NSM downloader" must include actually running
  the download, not just building the code.) If anything is underspecified or
  ambiguous, **ask the user NOW** before proceeding.

### Phase 2: Plan (use superpowers)

- [ ] Use `superpowers:brainstorming` if this is creative/design work
- [ ] Use `superpowers:writing-plans` to create an implementation plan
- [ ] Verify the plan covers ALL completion criteria from the spec, including
  running the actual pipeline (not just building it)
- [ ] Save plan to `docs/superpowers/plans/`

### Phase 3: Execute (use superpowers)

- [ ] Use `superpowers:subagent-driven-development` to execute the plan
  (always use subagents — do not ask)
- [ ] Follow `superpowers:test-driven-development` within each task
- [ ] After each subagent task: spec review then code quality review
- [ ] Fix all issues before moving to next task

### Phase 4: Verify (before claiming done)

- [ ] `uv run ruff check src/ tests/` — no lint errors
- [ ] `uv run ruff format --check src/ tests/` — formatting OK
- [ ] `uv run pyright src/corpus/` — no type errors
- [ ] `uv run pytest -v` — all tests pass
- [ ] Actually run the pipeline/command end-to-end (not just tests)
- [ ] Use `superpowers:verification-before-completion`
- [ ] Use `superpowers:requesting-code-review` for final review
- [ ] Use `superpowers:receiving-code-review` to evaluate and fix feedback
- [ ] Fix all reasonable issues immediately. File GitHub issues for anything
  deferred (`gh issue create` with context about the feedback source)

### Phase 5: Ship

- [ ] Use `superpowers:finishing-a-development-branch`
- [ ] Push branch, create PR with `gh pr create`
- [ ] Request external reviews: comment `@codex review` and `@claude review` on the PR
- [ ] Wait ~3 minutes for external review comments to arrive
- [ ] Read PR comments with `gh api repos/{owner}/{repo}/pulls/{number}/comments`
- [ ] Use `superpowers:receiving-code-review` to evaluate external feedback
- [ ] Fix reasonable issues, push, reply to comments
- [ ] File GitHub issues for any deferred feedback
- [ ] Update `SESSION-HANDOFF.md` with what was completed
- [ ] Update `TASKS.md` completion status

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

## Lessons Learned from NSM Adapter (March 26, 2026)

These patterns were validated during the NSM source adapter build and should be followed for EDGAR/PDIP:

### Source adapter pattern
1. **Two-phase: discover then download.** Separate CLI commands (`corpus discover <source>` → `corpus download <source>`). Discovery is fast metadata-only queries (minutes). Download is slow PDF retrieval (hours). This lets you inspect discovery results before committing to downloads, and re-run downloads without re-querying.
2. **"Breadth over depth" means within sovereign issuers, not the entire exchange.** The NSM has 5.2M total filings but only ~900 are sovereign. Use sovereign-scoped queries (LEIs, name patterns), not unfiltered bulk queries.
3. **Query each LEI separately.** Phase 0 AND'd multiple LEIs in one query → missed results. One API call per LEI.
4. **Name searches produce false positives.** "Georgia" returned 3,366 corporate hits. Use specific strings like "Georgia(acting through MoF" or "Government of Canada" instead of bare country names.
5. **Many HTML filings have no PDF.** ~28% of NSM sovereign filings are HTML-only (tender offers, notices). Treat `no_pdf_link` as a skip, not a failure — don't let it trigger circuit breakers.
6. **Discovery file stores raw `_source` dicts.** Download phase re-wraps them as fake hits for `parse_hits`. This is intentional — keeps discovery output close to the API response for debugging.

### Telemetry
7. **Don't use `logger.timed()` when the function reports status via return values.** `logger.timed` logs "success" on any non-exception return, which is wrong for functions that return `(None, "failed_invalid_pdf")`. Use explicit `time.monotonic()` + `logger.log()` with the actual status.

### Testing
8. **Always test the circuit breaker.** It's a safety mechanism for overnight runs — verify it actually fires.
9. **Run the actual download in the task, not just the code.** Building the adapter without running it misses real-world issues (5.2M unfiltered results, HTML-only filings, Georgia false positives).

### Config
10. **Read config.toml in the CLI layer, not hardcode defaults.** Pass configured values (retries, delays, thresholds) to HTTP client and pipeline functions.
11. **Use relative file paths in manifests.** `str(target)` produces environment-specific absolute paths. Future work should normalize to relative paths under `data/`.

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