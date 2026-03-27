# PDIP Annotations Harvest Plan

**Date:** 2026-03-26
**Status:** Ready to execute after issue + branch creation
**Issue:** `#19` — Build a resumable PDIP annotations harvester from `/api/details`
**Branch:** `feature/19-pdip-annotations-harvester`
**Executable runbook:** `docs/superpowers/plans/2026-03-26-pdip-api-overnight-runbook.md`
**Primary goal:** Build a reproducible, resumable PDIP annotations harvester that identifies CAC-positive candidate documents across the annotated PDIP set without overstating what PDIP can validate.

## Basis

This plan supersedes the earlier Playwright-first overnight draft.

It is based on:
- the Round 5 council synthesis in `planning/council-of-experts/round-5/2026-03-26_synthesis.md`
- current repo state in this workspace
- supplementary verification that PDIP exposes `/api/details/{doc_id}` and returns structured JSON with browser-like headers

## Repo-grounded facts

1. `parse`, `grep`, and `extract` are still CLI stubs in `src/corpus/cli.py`.
2. `make pipeline` still advertises those unfinished stages in `Makefile`.
3. `data/pdip/pdip_document_inventory.csv` exists and is trustworthy.
4. The local inventory contains:
   - `823` total documents
   - `162` annotated documents
   - `58` annotated bonds
5. `data/pdip_discovery.jsonl` and `data/manifests/pdip_manifest.jsonl` are absent in this workspace.
6. The local PDIP PDFs are legacy files under `data/pdfs/pdip/`, not the new manifest-backed layout.
7. `data/db/corpus.db` exists locally, but the configured path is `data/db/corpus.duckdb`, and the database should not be part of tonight's critical path.

## Confirmed acquisition path

Supplementary verification established:

1. `GET /pdf/{doc_id}/` serves a Next.js document page.
2. The page bundle calls `fetch("/api/details/{doc_id}")`.
3. `GET /api/details/{doc_id}` with browser-like headers returns structured JSON including:
   - `document_title`
   - `source_url`
   - `metadata`
   - `clauses`
   - raw clause labels

**Decision:** Build the overnight harvester against the HTTP details API, not Playwright.

## Methodology boundaries

### What PDIP can support

Tonight's harvest can support:
- document-level observed-positive labels for clause-family presence
- CAC-positive candidate identification based on PDIP clause labels
- a reproducible annotation acquisition methodology

Tonight's harvest cannot support by itself:
- CAC subtype accuracy claims
- safe negative labels for CAC absence
- corpus-wide accuracy metrics for grep/subtype extraction

### Gold-standard separation

There are two distinct layers:

1. **Presence layer**
   - question: did PDIP display a CAC-related annotation for this document?
   - source of truth: PDIP annotation payload plus manual spot checks

2. **Subtype layer**
   - question: what subtype does the actual clause text support?
   - source of truth: human review of the underlying bond text

## Scope for This Branch

### In scope

1. Build an inventory-driven PDIP annotations harvester over the `162` annotated docs.
2. Use the verified HTTP details API as the acquisition path.
3. Produce resumable, append-mode JSONL output with one terminal record per attempted document.
4. Save raw per-document API payloads for reuse.
5. Write structured telemetry and a run-end summary.
6. Export the subset of CAC-positive candidate documents for next-step gold-corpus selection.
7. Run a smoke test and a small pilot before any full run.

### Explicitly out of scope

1. Implementing `corpus parse`, `corpus grep`, or `corpus extract`
2. Running `make pipeline`
3. Regex tuning for CAC extraction
4. CAC subtype evaluation
5. DuckDB ingest of harvested annotations
6. Notebook/dashboard work

## Deliverables

### 1. Harvester module

Add a new source module for PDIP annotations harvesting.

Recommended location:
- `src/corpus/sources/pdip_annotations.py`

Recommended responsibilities:
- load inventory CSV
- filter to annotated docs by default
- call `/api/details/{doc_id}`
- normalize label summaries for downstream use
- persist JSONL output and raw payloads
- support resume by processed doc ID
- emit telemetry and run summary
- reuse the existing secure PDIP CA-bundle path by default
- read timeout/retry defaults from `config.toml` in the CLI layer rather than hardcoding

### 2. CLI entry point

Add a dedicated command rather than overloading `download`.

Recommended shape:
- `corpus scrape pdip-annotations`

Recommended options:
- `--run-id`
- `--inventory-file`
- `--output-dir`
- `--log-dir`
- `--limit`
- `--doc-id` (repeatable)
- `--annotated-only` (default and only recommended mode tonight)
- `--insecure` (emergency TLS override only)

### 3. Run outputs

Recommended run layout:

```text
data/pdip_annotations/<run_id>/
  annotations.jsonl
  telemetry.jsonl
  cac_candidates.csv
  summary.json
  raw/
    <doc_id>.json
  artifacts/
    <doc_id>/
      attempt-1-response.json
      attempt-2-response.json
      attempt-3-response.json
      failure.txt
```

Primary output:
- `annotations.jsonl`

Each terminal record should include at least:
- `run_id`
- `doc_id`
- `document_url`
- `api_url`
- `attempts_used`
- `status`
- `started_at`
- `ended_at`
- `duration_ms`
- `inventory_tag_status`
- `country`
- `instrument_type`
- `document_title`
- `source_url`
- `raw_clause_labels`
- `normalized_families`
- `cac_modification_labels`
- `cac_acceleration_labels`
- `cac_candidate`
- `clause_count`
- `payload_sha256`
- `raw_payload_path`
- `tls_mode`
- `tls_verify`
- `error_message` when applicable

### 4. Summary artifacts

At run end, write:
- `summary.json`
- `cac_candidates.csv`

Minimum summary fields:
- selected_total
- new_attempted
- succeeded
- failed
- skipped via resume
- terminal_total
- retry distribution
- latency percentiles
- failure buckets
- zero-clause-on-annotated count
- distinct raw labels observed
- unmapped labels
- CAC-candidate count
- counts by country
- counts by country and instrument type

## Harvester behavior

### Selection

Default target set:
- all `162` inventory rows where `tag_status == "Annotated"`

Optional filters:
- specific `doc_id`s for smoke tests
- `--limit` for pilot runs, applied in stable inventory CSV order

### Preflight

Before any network requests:
- confirm inventory headers exactly match the current CSV schema
- confirm `selected_total = 162`
- confirm `annotated_bond_total = 58`
- confirm smoke-test IDs exist in the selected set
- define ordering explicitly as filtered inventory CSV order

### Resume

Resume behavior:
- read existing `annotations.jsonl`
- tolerate a truncated trailing line in `annotations.jsonl`
- collect terminal `doc_id`s already processed
- skip them on rerun
- never treat `raw/<doc_id>.json` alone as completion
- if a raw payload exists for a `doc_id` without a valid terminal record, overwrite it on rerun

### Retries

Per document:
- max `3` attempts
- explicit retry backoff
- retry on transient HTTP errors and parse errors
- retry at most once on zero-clause annotated responses

### Failure handling

Failure statuses should distinguish:
- `failed_http`
- `failed_request`
- `invalid_json`
- `api_error`
- `annotated_zero_clauses`
- `not_found`

For annotated docs, zero extracted clauses is a special non-success anomaly bucket. It must be counted prominently and exported for review, but it should not count as a transport failure.

### Circuit breaker

Recommended initial policy:
- pause and rebuild session after `3` consecutive terminal transport/API failures
- abort after `8` consecutive terminal transport/API failures

Do not count `annotated_zero_clauses` toward the circuit breaker.

### Zero-clause anomaly gate

Use the verified baseline as a quality gate:
- reconnaissance baseline: `40/162` annotated docs with `clauses: []`
- stop and review if the pilot exceeds `6/20` zero-clause responses
- abort the full run if more than `10` of the first `20` docs or more than `40%` after `50` docs land in `annotated_zero_clauses`

## Testing plan

### Unit tests

Add focused tests for:
- inventory loading and annotated-only filtering
- preflight schema validation
- response parsing and label normalization
- CAC-candidate identification
- resume behavior
- terminal-record writing
 - trailing-JSONL-line recovery
- summary generation
- CLI wiring

### Smoke test before full run

Run a 5-document smoke test before any full harvest.

Required mix:
- at least 3 annotated documents
- at least 1 bond
- at least 1 likely troublemaker such as `NLD21` or `KEN68`

Smoke-test checks:
- terminal JSONL records written
- raw payloads saved
- CAC labels visible where expected
- retries behave correctly
- summary generated cleanly

### Pilot before full run

Run a `15-20` document pilot to verify:
- resume behavior
- retry behavior
- failure bucket quality
- output usefulness for next-step gold selection

## Verification before launch

Before a full run:

1. `uv run ruff check src/ tests/`
2. `uv run ruff format --check src/ tests/`
3. `uv run pyright src/corpus/`
4. `uv run pytest -v`
5. Run the 5-document smoke test
6. Run the 15-20 document pilot
7. Confirm the output JSONL and raw payloads look defensible
8. Confirm `cac_candidates.csv` is clearly framed as observed-positive PDIP evidence only, not subtype gold and not a negative set

## Gold corpus next step

This branch should only prepare the candidate pool, not hand-label the gold set.

Next-step gold corpus guidance:
- use the `58` annotated bonds only
- target `15-18` docs over the next 48 hours
- keep a holdout split
- cap any single country/family concentration
- record exact quote, page span, subtype, ambiguity flag, and reviewer metadata

## Success criteria

This plan is complete when:

1. A scoped issue exists for the PDIP annotations harvester.
2. Work proceeds on a dedicated feature branch.
3. The branch implements an HTTP-based, resumable harvester.
4. A smoke test and pilot both succeed.
5. The branch produces CAC-positive candidate outputs without making subtype claims.

## Non-goals for tonight

Do not:
- present grep/subtype metrics as validation against PDIP
- claim PDIP provides subtype gold
- treat missing PDIP tags as negative labels
- fold DuckDB work into the acquisition branch
- spend the night on Playwright unless the verified HTTP path proves insufficient
