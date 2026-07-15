# Coverage Feedback Patch Batch Implementation Plan

**Spec:** `docs/superpowers/specs/2026-07-15-coverage-feedback-patch-batch-design.md`
**Issue order:** TEA-1004, TEA-1003, TEA-1006, TEA-1005
**Accepted release unit:** one post-ingest snapshot and one production deploy

## Environment and branch posture

The workspace source tree is writable but its `.git` directory is read-only in
this session. Preserve the user's three pre-existing untracked `demo/data/*.csv`
files. Create a writable `/tmp` clone from the current `origin/main` before code
work and use it as the canonical code worktree, with explicit paths to the
workspace data. Transfer only an enumerated task-file patch between trees and
never stage the pre-existing CSVs. Re-fetch and rebase the branch before PR
review and before merge.

Prefix every `uv` command with `UV_CACHE_DIR=/tmp/sovereign-uv-cache` so uv does
not touch its sandbox-inaccessible default cache.

## Task 1: TEA-1004 code, red to green

Files:

- `tests/test_edgar.py`
- `tests/test_cli.py` or a focused new CLI test module
- `tests/test_snapshot.py`
- `src/corpus/sources/edgar.py`
- `src/corpus/cli.py`
- `src/corpus/reference/issuer_country_map.py`

1. Re-read TEA-1004, its comments, and the project status; confirm the issue is
   assigned and In Progress; post the verified implementation pointer.
2. Write failing tests that require:
   - 28 sovereign CIK entries and a unique Venezuela entry with CIK
     `0000103198`.
   - `corpus discover edgar --cik 0000103198` to select only that known entry.
   - repeatable `corpus parse run --storage-key ...` filtering before parse.
   - SEC issuer spelling `BOLIVARIAN REPUBLIC OF VENEZUELA` to resolve to
     `VEN`, Venezuela, sovereign.
3. Run the focused tests and record the expected failures.
4. Add Venezuela to the Latin America EDGAR tier. Keep `PROSPECTUS_FORMS`
   unchanged.
5. Add a repeatable EDGAR `--cik` selector. Reject unknown CIKs with a clear
   Click error. Preserve tier behavior when no CIK is provided.
6. Add repeatable parse `--storage-key` selection and extend the source choice
   with `luxse` and `lse`. Reject keys that are absent from the selected source
   rather than silently parsing zero documents.
7. Add the exact SEC issuer alias to the country map.
8. Make EDGAR manifest reconciliation an atomic upsert by `storage_key`:
   validate and enrich existing files, use relative paths, reject hash
   conflicts, and make identical reruns idempotent. Add crash-resume and
   second-run tests.
9. Make targeted parse fail closed: selected unique key count must equal the
   successful nonempty parse count, and missing files, empty text, or parser
   failures must exit nonzero.
10. Run focused tests green, then the whole EDGAR/CLI/snapshot subset.

## Task 2: TEA-1004 network run and evidence

Use run ID `coverage-20260715-edgar-venezuela` and an isolated discovery path.

1. Record the pre-run database and snapshot Venezuela counts by source as
   distinct storage keys. Baseline: 99 total, 60 LuxSE and 39 PDIP.
2. Run targeted EDGAR discovery with `--cik 0000103198`.
3. Assert discovery contains exactly the expected eight `424B3`/`424B5`
   accessions and no unresolved pagination failures. Record that `S-B` and
   `POS AM` remain excluded.
4. Download to `data/original` and reconcile each accession into the canonical
   EDGAR manifest. Verify relative paths, byte sizes, hashes, provenance, and a
   byte-identical idempotent second run.
5. Parse exactly the eight new storage keys. Require eight successful nonempty
   parses with valid headers and positive page counts; any selected failure is
   a hard stop.
6. Run canonical ingest, then build pages and markdown only as required for the
   new documents. Do not build the snapshot.
7. Assert the database contains the eight new SEC rows and the country resolver
   makes them default-visible in a candidate Parquet smoke build under `/tmp`.
8. Comment the run trail and before/after database counts on TEA-1004. Leave the
   issue In Progress until the final production evidence is available.
9. Comment TEA-1007 with the bounded observation: the list now has 28 verified
   CIKs, while its own seed universe is roughly 80 international-bond issuers;
   this is evidence the CIK list is not a coverage universe, not a claim that
   all remaining issuers have SEC CIKs.

## Task 3: TEA-1003 code, red to green

Files:

- `tests/test_luxse.py`
- focused CLI tests
- `tests/test_snapshot.py`
- `config.toml`
- `src/corpus/sources/luxse.py`
- `src/corpus/cli.py`
- `src/corpus/reference/issuer_country_map.py`
- `src/corpus/reference/wb_classifications.py`

1. Write failing tests that require:
   - an explicit LuxSE search-term list to override the generic defaults.
   - configured additional terms to include
     `BOLIVIA (PLURINATIONAL STATE OF)` on normal discovery.
   - targeted CLI `--search-term` behavior and isolated output.
   - exact Bolivia issuer mapping to `BOL`, Bolivia, sovereign.
   - official FY2027 classification: Latin America & Caribbean, lower middle
     income, IBRD.
2. Run the focused tests red.
3. Parameterize `discover_luxse(search_terms=...)`, preserving the six generic
   defaults when no terms are supplied. Report stats per actual term.
4. Add repeatable CLI `--search-term`. When absent, combine the generic terms
   with `luxse.additional_search_terms` from config; when present, use only the
   explicit terms.
5. Add structured per-term and per-page failure telemetry. Targeted discovery
   must fail if any page remains unresolved. Pagination must advance by the
   effective returned page size after a smaller-page fallback. Test total retry
   failure and reduced-page fallback.
6. Make LuxSE manifest reconciliation an atomic, idempotent upsert by
   `storage_key`, with existing-file validation, relative paths, byte sizes,
   hashes, provenance, crash-resume coverage, and loud same-key hash conflicts.
7. Add the primary-source issuer alias and World Bank classification.
8. Run focused tests green, then the full LuxSE/CLI/snapshot subset.

## Task 4: TEA-1003 network run and evidence

Use run ID `coverage-20260715-luxse-bolivia` and an isolated discovery path.

1. Claim TEA-1003 only after TEA-1004's implementation and ingest trail is
   complete.
2. Record the pre-run Bolivia count: zero canonical Bolivia rows. Separately
   record the two Venezuela rows whose raw title contains `BOLIVIAN`.
3. Discover only `BOLIVIA (PLURINATIONAL STATE OF)`.
4. Hard-assert offering IDs `105422819` and `3138724`, their anchor ISINs, exact
   issuer, and absence of Venezuelan attribution. Download all breadth-first
   results returned for that exact issuer. Any unresolved query, pagination,
   rate-limit, invalid-PDF, download, or reconciliation failure is a hard stop.
5. Reconcile downloaded records into the canonical LuxSE manifest and prove a
   byte-identical idempotent second run. Parse only the new storage keys; every
   selected file must have a valid header, positive page count, nonempty text,
   and `has_text=true` after ingest.
6. Assert both anchor documents at discovery, manifest, file, parse, database,
   and `/tmp` candidate-Parquet stages. Assert no target unmapped issuer and no
   Venezuela-to-Bolivia contamination.
7. Post the run trail and before/after counts on TEA-1003. Leave it In Progress
   until production evidence.

## Task 5: TEA-1006 production reproduction gate

1. Claim TEA-1006 after TEA-1003's ingest trail is complete.
2. With a controllable browser, search `Bolivia` on production before changing
   search code. Record snapshot date and every returned slug, source, raw title,
   issuer, and country.
3. If the live bug does not reproduce, post the evidence and close TEA-1006 as
   not reproducible. Make no search/data-normalization change.
4. If it reproduces, add a failing row-level regression around LuxSE native IDs
   `2175370` and `2176190`. Preserve raw titles. Correct only the derived
   searchable/display field at the shared snapshot or query seam, with an
   explicit reason and affected-ID list. Prohibit broad title replacement.
5. Run unit and two-origin explorer smoke green. Post the chosen layer and why.
6. Keep final post-deploy assertions for both `Bolivia` and `Venezuela`, even if
   the initial issue is closed as not reproducible.

If no controllable browser is available, stop here. Do not generate or publish
the final snapshot and do not claim TEA-1005.

## Task 6: TEA-1005 manual LSE lane and browser ingest

Files depend on the source-returned document schema, but the expected code
surface is:

- focused tests for manual-manifest validation
- `scripts/build_lse_manual_manifest.py` or an equivalently bounded helper
- `src/corpus/cli.py` parse-source support already landed in Task 1
- `src/corpus/reference/issuer_country_map.py` if the exact LSE spelling is new
- `explorer-web/src/lib/format.ts` and tests for the friendly source name
- `explorer-web/src/pages/index.astro`
- `explorer-web/src/layouts/Base.astro`
- README/About source-copy locations and tests

1. Claim TEA-1005 last.
2. Use a real browser on XZ57. Inventory the official LSE entity and document
   records for the four issuance dates. Retrieve each unique offering artifact.
3. For every artifact, verify `%PDF`, parser open, nonzero pages, nonempty text,
   SHA-256, and cover-page issuer/title/role/ISIN/date by hand.
4. Use hashes as identity evidence, not automatic legal equivalence. Hand-
   adjudicate duplicates, retain every official source URL, and write a durable
   association ledger from the four issuance events to unique legal artifacts,
   including any base circular shared by the December tap.
5. Write failing validation tests, then build the bounded atomic helper that
   creates `lse_manifest.jsonl` with `source="lse"`, stable document IDs,
   relative paths, full provenance, XZ57/ISIN/role/issuance metadata, and
   resume-safe reconciliation.
6. Add the exact issuer mapping if required and the friendly source display.
7. Parse only the LSE storage keys and require an exact successful/nonempty
   count. Ingest and assert `has_text=true`. Assert Republic of Congo and DRC
   remain separate.
8. Post unique-document and four-issuance coverage counts on TEA-1005. Leave it
   In Progress until production evidence.

## Task 7: One accepted snapshot and production transaction

1. Run deterministic gates:
   - `UV_CACHE_DIR=/tmp/sovereign-uv-cache uv run ruff check src/ tests/`
   - `UV_CACHE_DIR=/tmp/sovereign-uv-cache uv run ruff format --check src/ tests/`
   - `UV_CACHE_DIR=/tmp/sovereign-uv-cache uv run pyright src/ tests/`
   - `UV_CACHE_DIR=/tmp/sovereign-uv-cache uv run pytest -v`
   - explorer `npm test`, `npx astro check`, build, and two-origin smoke.
2. Run the issue-specific end-to-end assertions again against the database.
   A disposable `/tmp` snapshot may be used only for smoke tests.
3. In the canonical writable clone, rebase on current `origin/main`, rerun
   deterministic gates, commit intentionally, push, and open a draft PR.
4. Run the mandatory fresh-context PR council and external `@codex review` and
   `@claude review` loop. Fix reasonable findings, record pushback, and file
   deferred items. After every review-driven change, rerun deterministic and
   issue-specific gates, push, wait for required CI on that exact SHA, and
   record `PR_HEAD_SHA`. Require the branch current with `main` before merge.
5. Merge the reviewed open-repo PR. From that exact merge SHA, generate the one
   accepted `data/snapshot/` candidate. Record generated-at, schema version,
   merge commit, source/country counts, four-event/unique-artifact coverage,
   verification-ledger location, MANIFEST SHA-256, and Parquet SHA-256. Validate
   new slugs, classifications, default visibility, `has_text`, hashes,
   provenance, unmapped audit, and source-to-file-to-parse-to-row evidence.
   First freeze a release-input bundle and record hashes for canonical
   manifests, config, a logical database digest, parsed-output ledger,
   verification ledger, and run IDs. Build from that frozen bundle in a clean
   merge-SHA checkout and assert inputs remain unchanged through upload. Verify
   the merge contains the reviewed `PR_HEAD_SHA` and rerun all release gates.
   Any later code, manifest, parsed-output, or database change invalidates the
   candidate and requires regeneration and every release assertion again.
6. Clone/use the private wrapper from a writable `/tmp` path, pin the open repo
   merge SHA if explorer code changed, and build it against the exact candidate.
   Run a clean-checkout gate with frozen Python dependencies, the full configured
   lint/type/test scope including changed scripts, `npm ci`, recorded tool
   versions, and clean-tree/unchanged-lockfile assertions. Run branded
   two-origin smoke and both compatibility directions: current production app
   with the candidate and new app with the prior hosted generation.
7. Before upload, create and verify a complete immutable backup of the current
   hosted text, Parquet, wasm, and MANIFEST objects under a generation prefix,
   or record every relevant S3 version ID if versioning is enabled. Restore that
   backup to a disposable prefix as a preflight. Publish immutable
   generation-prefixed candidate artifacts, verify every hosted hash, and switch
   the generation pointer/MANIFEST last with
   `BUCKET=ti-sovtech-data SNAPSHOT=<candidate> bash scripts/upload-snapshot.sh`.
   Verify hosted generation and artifact identity.
8. Trigger and await the attended production deploy. Confirm build-stamp parity
   and no drift notice. Run `node scripts/live-smoke.mjs`, then target-specific
   production assertions from a machine-readable matrix: Bolivia anchors present
   and Venezuela false-positive IDs absent; eight Venezuela EDGAR keys visible;
   all four XZ57 events covered by verified artifacts; friendly LSE label; Congo
   and DRC distinct; expected filters, text, and slugs. Archive the output. On
   failure restore text, Parquet, and wasm followed by
   MANIFEST last; verify hosted identities; restore the prior Netlify deploy;
   then verify stamp parity and rerun live smoke.

## Task 8: Linear close and handoff

1. Post final evidence to each issue and move TEA-1004, TEA-1003, TEA-1006, and
   TEA-1005 to Done only after matching production checks pass.
2. Update `SESSION-HANDOFF.md` and `TASKS.md` if present. This repo has no
   `TASKS.md` at plan time, so do not invent one solely for the checklist.
3. Post one project status update: what shipped, final country/source counts,
   and next work in order, TEA-1007 coverage ledger then TEA-1008 LSE adapter.

## Plan council disposition

Four fresh-context reviewers cover generalist, sovereign-debt/data credibility,
pipeline/DuckDB, and downstream consumer/release lenses. Accepted changes:

- Move the accepted snapshot after review and merge; smoke snapshots are disposable.
- Add resume-safe, hash-conflict-detecting manifest upserts and fail-closed targeted parse.
- Make LuxSE targeted pagination/query failures observable and fatal.
- Create an LSE issuance-to-artifact association and hand-verification ledger.
- Expand LSE consumer copy and make rollback preserve the prior hosted data objects.
- Start from current `origin/main` in a writable clone and rebase at review gates.
- Tie every review and CI gate to an exact SHA, freeze mutable data inputs, and
  archive a machine-readable production acceptance matrix.
- Verify both app/data compatibility directions and use immutable generation
  objects with a pointer-last cutover and tested restore path.

Pushback and deferrals:

- GitHub #84's manifest-level classification-vintage field remains separately
  tracked. The explorer already labels the classification as World Bank FY2027;
  this batch verifies that visible label and records the official workbook in
  release evidence instead of expanding the schema.
- A file hash is retained as an identity signal only. Legal-document equivalence
  requires the manual association and verification record.
- Broader LuxSE and LSE adapter debt remains outside this patch batch and is
  routed to the already named follow-up work.
