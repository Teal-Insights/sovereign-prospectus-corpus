# PDIP API Overnight Runbook

**Date:** 2026-03-26
**Status:** Ready for implementation on `feature/19-pdip-annotations-harvester`
**Issue:** `#19`
**Branch:** `feature/19-pdip-annotations-harvester`

## Objective

Build and launch a resumable PDIP annotations harvester over the `162` annotated PDIP documents using the verified HTTP details API, not Playwright.

This runbook is intentionally specific enough to execute tonight.

## Verified facts that change the plan

The live PDIP site supports direct HTTP acquisition of the annotation objects:

1. `GET /api/details/{doc_id}` returns the annotation payload when sent with a browser-style `User-Agent`.
2. No cookie bootstrap or browser session is required.
3. The payload includes the clause label, snippet text, and rectangle geometry used to draw the red box in the PDF UI.
4. A bounded sweep over all `162` annotated IDs returned:
   - `162/162` HTTP `200`
   - `122/162` with non-empty `clauses`
   - `40/162` with `clauses: []`
5. A raw serial probe over the full `162` completed in about `58` seconds, so throughput is not the overnight risk. Correct classification, checkpointing, and resumability are the real risks.

## What tonight must produce

By the end of the night, this branch should produce:

1. A new CLI command: `corpus scrape pdip-annotations`
2. A resumable inventory-driven harvester for the annotated PDIP set
3. One terminal JSONL record per attempted document
4. One raw API payload file per successful HTTP `200`
5. A run summary and a CAC-candidate export
6. A verified smoke run and a verified pilot run
7. A launched full annotated-set run

## What tonight must not include

Do not spend time on:

1. `parse`, `grep`, or `extract`
2. `make pipeline`
3. Playwright or any browser automation
4. DuckDB ingest
5. CAC subtype evaluation
6. Notebooks or dashboards

## Output contract

Write active run artifacts outside Dropbox during execution:

```text
/var/tmp/pdip_annotations/<run_id>/
  annotations.jsonl
  telemetry.jsonl
  summary.json
  cac_candidates.csv
  raw/
    <doc_id>.json
  artifacts/
    <doc_id>/
      attempt-1-response.json
      attempt-2-response.json
      attempt-3-response.json
      failure.txt
```

After the run is reviewed, copy the completed directory into `data/pdip_annotations/<run_id>/`.

`cac_candidates.csv` is an observed-positive PDIP export only. It is not subtype gold and must not be treated as a negative set for non-candidates.

`summary.json` should include at least:

- `selected_total`
- `new_attempted`
- `skipped_via_resume`
- `terminal_total`
- `status_counts`
- `retry_distribution`
- `zero_clause_on_annotated_count`
- `distinct_raw_labels`
- `unmapped_labels`
- `cac_candidate_count`

## Record schema

Each terminal JSONL record should include at least:

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
- `clause_count`
- `raw_clause_labels`
- `cac_modification_labels`
- `cac_acceleration_labels`
- `cac_candidate`
- `payload_sha256`
- `raw_payload_path`
- `tls_mode`
- `tls_verify`
- `tls_reason`
- `error_message`

Recommended CAC fields:

- `cac_modification_labels`: raw labels beginning with `VotingCollectiveActionModification_`
- `cac_acceleration_labels`: raw labels beginning with `VotingRequirementforAcceleration_`
- `cac_candidate`: `true` only if `cac_modification_labels` is non-empty

Acceleration labels should be reported separately. They are not a secondary confidence tier for CACs.

## Status taxonomy

Use terminal statuses that reflect what actually happened:

- `success`
- `annotated_zero_clauses`
- `failed_http`
- `failed_request`
- `invalid_json`
- `api_error`
- `not_found`

Important handling rule:

- `annotated_zero_clauses` is not a successful extraction, but it is also not a transport failure.
- It should be counted prominently in the summary and exported for review.
- It should not trip the circuit breaker by itself, because live reconnaissance already found `40` such documents.

## Resume contract

`annotations.jsonl` is the sole completion source of truth.

Resume behavior must explicitly handle crash recovery:

1. Read existing `annotations.jsonl` and tolerate a truncated trailing line.
2. Ignore any invalid trailing partial JSON object with a warning rather than failing the rerun.
3. Treat only valid terminal JSONL records as completed documents.
4. Never trust `raw/<doc_id>.json` alone as completion.
5. If `raw/<doc_id>.json` exists but there is no valid terminal record for that `doc_id`, overwrite the raw file on rerun.
6. Never emit duplicate terminal records for the same `doc_id` within one `run_id`.

Run-level counts must distinguish:

- `selected_total`
- `new_attempted`
- `skipped_via_resume`
- `terminal_total`

## Request policy

Use a single `requests.Session()` with:

- `User-Agent: Mozilla/5.0`
- explicit request timeout
- append-only structured logging

Read request and circuit-breaker defaults from `config.toml`, not hardcode them.

Use the existing secure PDIP CA-bundle path from [pdip.py](/Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus/src/corpus/sources/pdip.py) first.

TLS policy:

1. First smoke test with the existing PDIP CA-bundle verification path.
2. If the environment still reproduces the observed Python TLS problem, rerun with `--insecure`.
3. When `--insecure` is set, skip `_build_ca_bundle()` entirely and set `session.verify = False`.
4. Record `tls_mode`, `tls_verify`, and `tls_reason` in each terminal record.

## Telemetry contract

Write per-attempt telemetry to:

```text
/var/tmp/pdip_annotations/<run_id>/telemetry.jsonl
```

Minimum per-attempt event fields:

- `run_id`
- `doc_id`
- `attempt`
- `phase`
- `status`
- `started_at`
- `ended_at`
- `duration_ms`
- `http_status`
- `exception_class`
- `tls_mode`
- `response_path`
- `note`

## Mandatory preflight

Before any network requests, prove the run inputs are sane:

1. Confirm inventory path exists.
2. Confirm the inventory headers exactly match:
   - `id`
   - `document_title`
   - `tag_status`
   - `country`
   - `instrument_type`
   - `creditor_country`
   - `creditor_type`
   - `entity_type`
   - `document_date`
   - `maturity_date`
3. Confirm `selected_total = 162` for annotated rows.
4. Confirm `annotated_bond_total = 58`.
5. Confirm the smoke-test IDs exist in the selected set:
   - `VEN85`
   - `NLD21`
   - `KEN68`
   - `JAM22`
   - `VEN59`
6. Define ordering explicitly: preserve inventory CSV order after filtering, and apply `--limit` against that stable order.

## Retry policy

Per document:

1. Attempt 1: normal request
2. Attempt 2: retry only for transport failures, `5xx`, `429`, or invalid JSON
3. Attempt 3: final retry after brief backoff for the same transient bucket

Do not burn retries on stable content states:

- If the API returns HTTP `200` with `clauses: []` for an inventory-annotated document, retry once at most.
- If the second response is still empty, mark `annotated_zero_clauses` and continue.

## Circuit breaker

Use a circuit breaker only for transport/API instability:

1. After `3` consecutive terminal transport/API failures:
   - sleep `60` seconds
   - rebuild the session
2. After `8` consecutive terminal transport/API failures:
   - abort the run
   - write `summary.json`
   - exit non-zero

Do not count `annotated_zero_clauses` toward the circuit breaker.

## Zero-clause anomaly gate

Known reconnaissance baseline:

- `40/162` annotated documents returned `clauses: []` during verification
- baseline rate: about `24.7%`

Because this bucket is common but not dominant, treat spikes as a data-quality anomaly:

1. During the smoke test, `VEN59` is the only expected `annotated_zero_clauses` result.
2. During the pilot, stop and review if more than `6/20` documents land in `annotated_zero_clauses`.
3. During the full run, abort for review if:
   - more than `10` of the first `20` documents land in `annotated_zero_clauses`, or
   - after at least `50` documents, the cumulative zero-clause rate exceeds `40%`

This gate protects against a silent API regression that would otherwise produce a formally complete but substantively useless run.

## Smoke test set

Use these five documents before any pilot or full run:

1. `VEN85` - annotated bond, known CAC box in UI
2. `NLD21` - annotated bond, CAC incorporated by reference edge case
3. `KEN68` - annotated bond, modern aggregated-style CAC language
4. `JAM22` - annotated bond, multiple CAC hits
5. `VEN59` - annotated document with known zero-clause API response

Smoke test command target:

```bash
uv run corpus scrape pdip-annotations \
  --run-id 2026-03-26-smoke \
  --annotated-only \
  --doc-id VEN85 \
  --doc-id NLD21 \
  --doc-id KEN68 \
  --doc-id JAM22 \
  --doc-id VEN59 \
  --output-dir /var/tmp/pdip_annotations/2026-03-26-smoke
```

If TLS verification fails in Python, rerun with:

```bash
uv run corpus scrape pdip-annotations \
  --run-id 2026-03-26-smoke \
  --annotated-only \
  --doc-id VEN85 \
  --doc-id NLD21 \
  --doc-id KEN68 \
  --doc-id JAM22 \
  --doc-id VEN59 \
  --output-dir /var/tmp/pdip_annotations/2026-03-26-smoke \
  --insecure
```

Smoke test pass criteria:

1. `annotations.jsonl` contains `5` terminal records
2. Raw payload JSON exists for all HTTP `200` responses
3. `VEN85`, `NLD21`, `KEN68`, and `JAM22` show non-empty `clauses`
4. `VEN85` includes `VotingCollectiveActionModification_AmendmentandWaiver`
5. `JAM22` includes at least `2` primary CAC hits
6. `VEN59` lands in `annotated_zero_clauses`
7. `summary.json` totals reconcile exactly

## Pilot run

Run a `20`-document pilot after the smoke test:

```bash
uv run corpus scrape pdip-annotations \
  --run-id 2026-03-26-pilot \
  --annotated-only \
  --limit 20 \
  --output-dir /var/tmp/pdip_annotations/2026-03-26-pilot
```

Pilot pass criteria:

1. `20` terminal records written
2. Resume works cleanly on rerun with the same `run_id`
3. No malformed JSON payloads
4. Summary counts add up
5. Raw payloads and JSONL records are sufficient to identify CAC candidates without opening a browser

## Full run

If smoke and pilot pass, launch the full annotated-set run:

```bash
caffeinate -s \
  uv run corpus scrape pdip-annotations \
  --run-id 2026-03-26-full \
  --annotated-only \
  --output-dir /var/tmp/pdip_annotations/2026-03-26-full
```

Use `--insecure` only if the smoke test confirmed the TLS verification problem persists in Python.

Expected runtime:

- raw API sweep: about `1` minute
- full end-to-end run with writes, retries, and summary generation: comfortably under `15` minutes unless the endpoint becomes unstable

## Implementation sequence

### 0-20 minutes

Wire the new module and CLI surface:

1. Add `src/corpus/sources/pdip_annotations.py`
2. Add `corpus scrape pdip-annotations` to `src/corpus/cli.py`
3. Define a small typed config object for:
   - timeout
   - retries
   - TLS verify
   - annotated-only filter
   - output directory
4. Read defaults from `config.toml` via the CLI layer, not hardcode them.

### 20-45 minutes

Implement the harvester core:

1. load inventory rows
2. run mandatory preflight checks and fix ordering
3. filter target docs
4. recover resumable state from `annotations.jsonl`
5. tolerate a truncated trailing JSONL line
6. overwrite orphaned raw payloads when no terminal record exists
7. fetch `/api/details/{doc_id}`
8. write raw payloads
9. compute raw labels and CAC buckets
10. append terminal JSONL records
11. write per-attempt telemetry
12. support resume from existing `annotations.jsonl`

### 45-65 minutes

Implement summary and export:

1. `summary.json`
2. `cac_candidates.csv`
3. failure artifact writing
4. status buckets and retry accounting
5. selected versus resumed totals
6. distinct raw labels and unmapped labels

### 65-85 minutes

Add focused tests:

1. inventory filtering
2. label extraction and CAC bucketing
3. terminal record writing
4. resume skip logic
5. summary generation
6. CLI wiring

### 85-100 minutes

Run verification:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pyright src/corpus/
uv run pytest -v
```

### 100-115 minutes

Run the 5-document smoke test and inspect outputs.

### 115-130 minutes

Run the 20-document pilot and rerun it once to confirm resume.

### 130+ minutes

Launch the full annotated-set run and watch the first several documents.

## Go/no-go rules

Launch the full run only if all of the following are true:

1. The CLI runs without manual intervention
2. Smoke test pass criteria are all met
3. Pilot pass criteria are all met
4. `annotated_zero_clauses` stays within the anomaly threshold
5. No repeated transport/API failures are occurring

Do not launch the full run if:

1. The command still requires browser automation
2. Raw payloads are not being saved
3. Resume is not working
4. JSONL records are missing required fields
5. The circuit breaker logic has not been exercised at least once in tests

## Morning review checklist

After the run:

1. Inspect `summary.json`
2. Confirm `selected_total = 162`
3. Confirm `status_counts`
4. Confirm `terminal_total = 162` across resumed state
5. Inspect the `annotated_zero_clauses` bucket separately
6. Inspect `cac_candidates.csv`
7. Inspect `distinct_raw_labels` and `unmapped_labels`
8. Do not present success count as a validation count. It is an API response count, not a CAC-truth count.
9. Copy the completed run directory from `/var/tmp/pdip_annotations/<run_id>/` to `data/pdip_annotations/<run_id>/`
10. Update `SESSION-HANDOFF.md` with:
   - command run
   - runtime
   - terminal counts
   - CAC-candidate count
   - whether secure CA-bundle mode or `--insecure` was used

## Key decision

The overnight job is now an HTTP annotation harvester, not a Playwright scraper.

That is the correct scope because the API already exposes the PDIP annotation label, snippet text, and red-box geometry needed for defensible acquisition of PDIP annotations.
