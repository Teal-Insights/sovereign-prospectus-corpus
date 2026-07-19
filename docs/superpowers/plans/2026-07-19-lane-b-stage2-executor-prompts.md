# Lane B Stage 2: Paste-Ready Executor Prompts (LB0-LB11 + OPS-A/OPS-B)

Stage 2 contract artifacts per the Project Shell Runbook v0.2. One prompt
per branch, each self-contained: paste it into a FRESH session of the named
venue and walk away. The plan with full task detail:
`docs/superpowers/plans/2026-07-19-lane-b-stage2-batch-plan.md` ("the
plan"). The spec:
`docs/superpowers/specs/2026-07-18-self-running-corpus-design.md` v3.1
(signed; the plan implements it; on any contradiction the executor stops).
Council PLAN review: round 1 (Codex xhigh NOT SOUND + Claude external
SOUND WITH CHANGES) fully triaged and applied; dispositions in plan
section 12.

Shared conflict rules: docs/build-metrics.md conflicts keep both lines;
docs/refresh-runbook.md conflicts keep both sections under their own
stable headings.

**Dispatch schedule:**

| Wave | Branches | Venue | Notes |
|---|---|---|---|
| 0, now, parallel | LB1 (TEA-1032), LB2 (TEA-1059), LB3 (TEA-1060), LB4 (TEA-1061), LB5 (TEA-1062) | Claude Code, Opus 4.8 max | Separate worktrees, separate sessions |
| 0, now | LB0 (TEA-1058) | Codex, gpt-5.6-sol xhigh, `codex exec -s danger-full-access` | Spike; TDD waived; must finish before OPS-B |
| 1, after LB4 merges | LB6 (TEA-1033) | Claude Code, Opus 4.8 max | Rebase over LB3 if it lands later |
| 1, anytime | LB9 (TEA-1063) | Codex, gpt-5.6-sol xhigh, `codex exec -s danger-full-access` | Wrapper repo only |
| 2, after LB1+LB2+LB3+LB4+LB5+LB6 ALL merged | LB7 (TEA-1042) | Claude Code, Opus 4.8 max | The L branch |
| 2, after LB4+LB6 (merges after LB7) | LB8 (TEA-1064) | Claude Code, Opus 4.8 max | Builds parallel to LB7 against plan section 2 contracts |
| 3, after LB7+LB8 | LB10 (TEA-1065), LB11 (TEA-1067) | Claude Code, Opus 4.8 max | Parallel with each other |
| OPS-A, after LB4 + Teal handoff items 1-2 | TEA-1066 | Claude Code, Opus 4.8 max | Operational; no new code |
| OPS-B, after LB0+LB7+LB8+LB9+LB10+LB11 ALL merged + OPS-A + Teal items 3-7 | TEA-1068 | Claude Code, Opus 4.8 max | Operational; Teal gates inline |

Every branch merges via the Stage 4 review gate (fresh session, council
code review with Codex xhigh), never by the executor. Teal handoff items
are plan section 10; executors treat them as stop-and-report boundaries.

---

## LB0 (TEA-1058) LuxSE hosted-runner spike. CODEX gpt-5.6-sol xhigh. Wave 0. TDD WAIVED (declared spike).

```
You are the EXECUTOR for branch LB0 (TEA-1058): the LuxSE hosted-runner
spike of the Lane B self-running-corpus batch. This is a DECLARED SPIKE
under the Project Shell Runbook: TDD is waived, the output is evidence,
and the disposition gates only cron-on. You are not the architect; the
probe list is fixed. Load operating context from AGENTS.md in the repo
root.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Create an isolated worktree: from the repo root,
  git worktree add .claude/worktrees/lb0-luxse-spike -b lte/lb0-luxse-runner-spike origin/main
and work there. Before EVERY commit run `git rev-parse --abbrev-ref HEAD`
and confirm you are on lte/lb0-luxse-runner-spike.

Read YOUR plan section "LB0: LuxSE hosted-runner spike" in
docs/superpowers/plans/2026-07-19-lane-b-stage2-batch-plan.md and spec
section 18. Build exactly: .github/workflows/luxse-spike.yml
(workflow_dispatch ONLY, SHA-pinned actions, ubuntu-latest) running (a)
LuxSE discovery with production headers/delays from config.toml, (b)
download of exactly TWO discovered documents (add a --limit N option to
`corpus download luxse` if absent; default behavior unchanged; same for a
--max-queries option on discover if trivial, else run full discovery),
(c) one Docling PDF parse COLD then WARM with wall times, (d) the Gate 0
HTML offline-conversion assertion IF LB1 (TEA-1032) has merged by
dispatch time, else the evidence JSON notes it skipped, (e) evidence
JSON uploaded as a workflow artifact via scripts/luxse_spike_report.py.

Dispatch ordering: workflow_dispatch is only available once the workflow
file exists on the default branch, so this branch merges the (inert,
dispatch-only) workflow FIRST via the review gate, THEN you dispatch
with `gh workflow run luxse-spike.yml` and record results. If waiting
for the merge stalls your session, end it with the handoff noting
"dispatch after merge" as the named next step.

HARD BOUNDARIES: no adapter changes beyond the two small CLI options; no
`scheduled` config flips (OPS-B owns that); no edits to docs/sources.md;
no schedule trigger on the workflow.

DEFINITION OF DONE (verbatim from the plan):
- Workflow merged and dispatched; run URL and evidence artifact linked on
  TEA-1058.
- Both downloads validated %PDF or the failure mode documented verbatim.
- Cold and warm Docling parse times recorded.
- Disposition sentence recorded on TEA-1058: "LuxSE enters the daily
  list" or "LuxSE stays manual with feeder pending row".
- A one-line LuxSE ToS conclusion DRAFTED in the issue comment (flagged
  for Teal confirmation; do not edit any repo file with it).

STOP AND REPORT (comment on TEA-1058, end session) if: LuxSE blocks the
runner IP class entirely (that IS a valid disposition; record evidence
and say so); anything suggests a headless browser is required; the
workflow needs permissions beyond contents: read. Standing rule: same DoD
check fails twice, escalate reasoning once, retry once; still failing,
STOP with a blocker report.

Self-review before handoff: fresh command output for each DoD line; diff
read end to end; no em-dashes anywhere. Push, PR "LB0: LuxSE
hosted-runner spike (TEA-1058)". Handoff comment on TEA-1058:
Did / Why / Next (dispatch or disposition; OPS-B consumes it) / Pointer
(PR + run URL). Append to docs/build-metrics.md (a conflict there is
mechanical, keep both lines):
| LB0 | gpt-5.6-sol xhigh | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB1 (TEA-1032) Gate 0 parse path. Claude Code, Opus 4.8 max. Wave 0.

```
You are the EXECUTOR for branch LB1 (TEA-1032): Gate 0, the EDGAR
parse-path fix, first correctness gate of the Lane B self-running-corpus
batch. You are not the architect. Use superpowers:executing-plans. Load
operating context from AGENTS.md in the repo root.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Work in a git worktree (superpowers:using-git-worktrees), branch
lte/tea-1032-lb1-parse-path-gate0, based on current origin/main. Symlink
the data tree into the worktree for the real-file check:
  ln -sfn /Users/teal_emery/code/sovereign-prospectus-corpus/data <worktree>/data
(the symlink is gitignored; NEVER commit it). Before EVERY commit run
`git rev-parse --abbrev-ref HEAD` and confirm the branch.

Read YOUR plan section "LB1: Gate 0, the parse-path fix" in
docs/superpowers/plans/2026-07-19-lane-b-stage2-batch-plan.md and spec
section 6. Follow the tasks IN ORDER, test-first
(superpowers:test-driven-development). The plan fixes the behavior
matrix (.pdf unchanged; .htm/.html = HTMLParser pages JSONL PLUS Docling
HTML markdown sidecar with dual-lane provenance; Docling failure =
pages-only degradation, never quarantine; .txt byte-identical). If you
find yourself making a design decision the plan does not make, that is a
stop-and-report, not a judgment call.

HARD BOUNDARIES: no workflow files; no changes to the 51-document
backfill (TEA-1036, Lane A); no source_file_hash or skip-semantics work
(LB2 owns those); no edits to data/parsed_docling/; the canonical
data/db/corpus.duckdb is READ-ONLY to you.

DEFINITION OF DONE (verbatim from the plan):
- uv run pytest tests/test_docling_html.py
  tests/test_cli_parse_html_sidecar.py tests/test_snapshot_html_docs.py
  -v green, including: test_convert_produces_heading_markdown,
  test_convert_offline, test_htm_writes_pages_and_sidecar,
  test_docling_failure_degrades, test_txt_unchanged,
  test_snapshot_serves_markdown.
- Full uv run pytest, ruff check, ruff format --check, pyright green (no
  NEW pyright errors beyond the tracked verify.py set).
- ci.yml pytest step carries HF_HUB_OFFLINE: "1" (bare-runner no-model
  proof).
- One REAL EDGAR .htm from data/original/ parsed end to end locally,
  sidecar inspected, text_source='markdown' confirmed via a --limit
  snapshot build; evidence pasted in the PR body.
- Spec section 6 acceptance bullets each mapped to a named test in the PR
  body.

STOP AND REPORT (verbatim from the plan): Docling 2.86's HTML conversion
cannot run without model downloads (report the observed import or
download attempt verbatim); HTMLParser page segmentation would need to
change to keep page citations. Standing rule: same DoD check fails twice,
escalate thinking once, retry once; still failing, STOP: post a blocker
report on TEA-1032 (what you tried, what broke, the smallest question the
architect must answer), end the session. Do not redesign.

Self-review before handoff: fresh test output shown
(superpowers:verification-before-completion; no claims without command
output); diff read end to end; no stray files; no em-dashes. Push, PR
"LB1: Gate 0 parse path, Docling HTML sidecar (TEA-1032)". Handoff on
TEA-1032: Did / Why / Next (review gate; LB7 consumes) / Pointer (PR).
Append to docs/build-metrics.md (conflict = keep both lines):
| LB1 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB2 (TEA-1059) Gate 1 incremental-content correctness. Claude Code, Opus 4.8 max. Wave 0.

```
You are the EXECUTOR for branch LB2 (TEA-1059): Gate 1,
incremental-content correctness (update-in-place, hash-keyed parse skip,
slug quarantine, skip-FTS), of the Lane B batch. You are not the
architect. Use superpowers:executing-plans. Load operating context from
AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb2-incremental-content-gate1, based on current origin/main. Symlink
data/ as in the plan's worktree note; the canonical DB is read-only: your
real-data check runs against a COPY in the session scratch dir, deleted
after. Verify HEAD before every commit.

Read YOUR plan section "LB2: Gate 1, incremental-content correctness" and
spec section 7. Follow tasks in order, test-first. The plan decides
everything; four points are load-bearing and council-hardened:
(1) LATEST-RECORD-WINS: ingest and the parse manifest scan collapse each
manifest to a dict keyed by storage_key keeping the LAST occurrence
before processing, so appended correction records are idempotent.
(2) The update transaction's SET list is built from the plan's fixed
candidate list FILTERED by information_schema.columns (the markdown pair
is LB1's parallel migration; your code must be correct with and without
those columns).
(3) `corpus parse invalidate --storage-key K` deletes the parsed outputs;
every update path invalidates before reparse, which is what makes the
missing-source_file_hash grandfather rule safe.
(4) Slug-collision quarantine at ingest; parse-failure quarantine via
`corpus quarantine sync` with the attempts counter; `--assert-derived`
as the publishing-boundary invariant check.

HARD BOUNDARIES: no FTS rebuild scheduling and no retry ENFORCEMENT
(LB10); no revalidation sampler (LB10); no incoming/ work (LB7); no
workflow files; never mutate the canonical DB or canonical manifests.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_ingest_update.py
  (test_hash_change_updates_in_place,
  test_derived_rows_replaced_and_grep_stale, test_same_hash_skips,
  test_update_is_transactional, test_latest_manifest_record_wins,
  test_update_with_and_without_markdown_columns),
  test_ingest_quarantine.py (test_slug_collision_quarantines_second,
  test_quarantine_sync_and_clear,
  test_assert_derived_flags_missing_pages), test_parse_skip.py
  (test_skip_keyed_on_hash_not_disk,
  test_budget_counts_only_new_or_changed, test_backlog_reported,
  test_invalidate_forces_reparse, test_parse_scan_latest_record_wins),
  test_pages.py::test_skip_fts_flag.
- Full pytest, ruff check + format, pyright green (no NEW errors).
- Spec section 7 acceptance bullets mapped to tests in the PR body.
- The scratch-copy real-data check (one real manifest line, synthetically
  bumped hash, invariants verified, copy deleted) pasted in the PR body.

STOP AND REPORT (verbatim): DuckDB transactional semantics behave
unexpectedly for the multi-statement transaction (minimal repro);
slugify-collision memoization needs more than one startup query for
correctness. Standing rule: same DoD check fails twice, escalate thinking
once, retry once; still failing, STOP with a blocker report on TEA-1059.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push, PR
"LB2: Gate 1 incremental-content correctness (TEA-1059)". Handoff on
TEA-1059: Did / Why / Next (review gate; LB7 consumes) / Pointer.
Append to docs/build-metrics.md (conflict = keep both lines):
| LB2 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB3 (TEA-1060) Gate 2 generation-addressed data contract. Claude Code, Opus 4.8 max. Wave 0. TWO REPOS.

```
You are the EXECUTOR for branch LB3 (TEA-1060): Gate 2, the
generation-addressed data contract (MANIFEST generation/data_base/
suppression_epoch fields, suppression-aware snapshot build, explorer
data_base resolution, AND the wrapper build.sh acquisition half), of the
Lane B batch. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb3-generation-data-contract, based on current origin/main.
Second repo (ONE block of ONE file plus a small test harness):
~/Code/prospectus-web-ti, scripts/build.sh snapshot-acquisition block,
on branch lte/lb3-build-data-base there. Verify HEAD before every commit
in BOTH repos.

Read YOUR plan section "LB3: Gate 2, generation-addressed data contract"
and spec section 8 (which names BOTH halves: the snapshot client and
wrapper build.sh resolve from data_base). Follow tasks in order,
test-first. The plan pins: additive MANIFEST keys always written
(generation, data_base, suppression_epoch; SCHEMA_VERSION stays 1);
build_snapshot params (data_base, generation, suppressed_keys,
suppression_epoch); the suppressions-ledger read shape (plan 2.8); the
client rule `const dataBase = manifest.data_base ?? PUBLIC_DATA_BASE_URL`
applied at exactly browse.ts:491/504 and doc-text.ts:117/806 with
loadManifest always on the stable base; the wrapper rule: build.sh
fetches MANIFEST from FETCH_BASE, then fetches documents.parquet from
the MANIFEST's data_base when non-null, else from FETCH_BASE
(BUILD_DATA_FETCH_BASE override behavior unchanged; CI's SNAPSHOT_DIR
preset path untouched); scripts/build_snapshot.py unchanged behavior.

HARD BOUNDARIES: do NOT edit the SCHEMA_VERSION policy comment in
snapshot.py (the source-onboarding build owns that reconciliation); no
UI changes; no suppressions WRITING (LB11); wrapper changes limited to
the build.sh acquisition block plus the small test harness; the
no-data_base client path must stay byte-identical.

DEFINITION OF DONE (verbatim from the plan):
- Python: test_snapshot_manifest.py
  (test_manifest_carries_generation_fields, test_suppressed_keys_excluded,
  test_suppression_epoch_recorded) plus the `corpus snapshot build`
  CliRunner suppressions test, green.
- explorer-web: extended snapshot-client.test.ts green (data_base routes
  parquet and text fetches, absent behaves as today, unknown keys
  ignored); npx vitest run green; npx astro check clean.
- smoke.mjs scenario(s) green covering BOTH manifest variants (with and
  without data_base), and the ci.yml explorer job exercises both paths.
- Wrapper: the scripts/test-build-fetch.sh fixture harness output pasted
  in the PR (parquet fetched from data_base when present, from
  FETCH_BASE when absent).
- Full uv run pytest green.
- Spec section 8 acceptance mapped in the PR body, both halves.

STOP AND REPORT (verbatim): the client change cannot keep the
no-data_base path byte-identical; any need to change urls.ts signatures
beyond passing a different base; the build.sh change cannot keep CI's
SNAPSHOT_DIR preset path untouched. Standing rule: same DoD check fails
twice, escalate thinking once, retry once; still failing, STOP with a
blocker report on TEA-1060.

Self-review: fresh output per DoD line; diff read in both repos; no
em-dashes. Push both branches, PRs "LB3: Gate 2 generation-addressed
data contract (TEA-1060)" and (wrapper) "LB3: build.sh data_base
acquisition (TEA-1060)". Handoff on TEA-1060: Did / Why / Next (review
gate; LB6/LB7/LB8 consume) / Pointer (both PRs). Append to
docs/build-metrics.md (conflict = keep both lines):
| LB3 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB4 (TEA-1061) State shuttle, fenced lock, cutover tooling. Claude Code, Opus 4.8 max. Wave 0.

```
You are the EXECUTOR for branch LB4 (TEA-1061): the S3 state shuttle
(ObjectStore seam, CAS-lease lock, immutable revisions, parsed-tree
sync, cutover tooling, state-verify workflow) of the Lane B batch. You
are not the architect. Use superpowers:executing-plans. Load operating
context from AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch lte/lb4-state-shuttle,
based on current origin/main. Verify HEAD before every commit.

Read YOUR plan section "LB4: State shuttle, fenced lock, cutover tooling"
plus plan sections 2.2-2.5 (bucket layout, STATE.json, the CAS-lease
lock protocol, watermarks) and spec section 5. Follow tasks in order,
test-first. The plan pins the ObjectStore protocol verbatim (implement
it exactly; every later branch injects it; no other module may import
boto3) and the LOCK AS A CAS LEASE: acquire is If-None-Match or an
If-Match CAS over a released lease; release and stale-break are
If-Match CAS PUTs; the lock module NEVER deletes (S3 general-purpose
buckets have no conditional delete; the plan records this deviation).
Also pinned: revision commit/restore with sha-of-compressed-bytes; the
parsed-up-BEFORE-commit ordering; parsed sync change detection by
sha256-in-object-metadata (never size); compaction as a fresh-file
rebuild; state-verify.yml as a dispatch-only OIDC acceptance workflow.
FakeS3 in tests must implement REAL conditional-write semantics (etag
rotation, PreconditionFailed on If-None-Match and If-Match violations).

HARD BOUNDARIES: no EXECUTION of cutover (OPS-A, gated on the Teal
handoff); no Actions cache wiring (LB7); no refresh workflow steps; no
pruning (LB10); never create any AWS resource; the optional real-S3 test
is marked network and skipped without credentials.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_state_lock.py (test_acquire_free,
  test_acquire_contested, test_zombie_fence_blocks_commit,
  test_release_owner_checked, test_break_stale_checks_liveness,
  test_release_is_cas_put_not_delete,
  test_break_cas_fails_when_lease_changed_hands),
  test_state_revisions.py (test_round_trip, test_sha_mismatch_refuses,
  test_cas_conflict_raises, test_cancel_mid_push_leaves_pointer),
  test_state_sync.py (test_parsed_up_before_commit_order,
  test_parsed_up_detects_same_size_change, incremental cases incl. the
  touched fast path), test_state_cutover.py
  (test_compact_preserves_counts, test_originals_upload_idempotent).
- Full pytest, ruff, pyright green; pyproject gains boto3 + zstandard via
  uv (lockfile updated).
- state-verify.yml actionlint-clean, SHA-pinned, dispatch-only, inert.
- Runbook sections "State model", "State-revision recovery", "Local
  takeover", "Cutover" written in docs/refresh-runbook.md.
- Spec section 5 requirements mapped to a test or an OPS-A step in the PR
  body.

STOP AND REPORT (verbatim): boto3/S3 conditional-write parameters do not
behave as plan 2.3-2.4 assume on a live probe (record the exact API
error); compaction cannot recreate sequences faithfully. Standing rule:
same DoD check fails twice, escalate thinking once, retry once; still
failing, STOP with a blocker report on TEA-1061.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push, PR
"LB4: S3 state shuttle and CAS-lease lock (TEA-1061)". Handoff on
TEA-1061: Did / Why / Next (review gate; LB6 unblocks; OPS-A gated on
Teal items 1-2) / Pointer. Append to docs/build-metrics.md (conflict =
keep both lines):
| LB4 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB5 (TEA-1062) EDGAR/NSM incremental discovery + source config. Claude Code, Opus 4.8 max. Wave 0.

```
You are the EXECUTOR for branch LB5 (TEA-1062): EDGAR/NSM incremental
discovery (supports_since, seam delta 4), per-source watermarks with the
download-failure ledger (seam delta 2, local half), manifest-keyed
download skips, and registry-derived source lists (seam delta 1) of the
Lane B batch. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb5-incremental-discovery-source-config, based on current
origin/main. Symlink data/ (gitignored, never commit) for the live
probes; write probe outputs to the scratch dir, never to canonical
discovery paths. Verify HEAD before every commit.

Read YOUR plan section "LB5: EDGAR/NSM incremental discovery +
registry-derived source lists" plus plan 2.5 and 2.10, spec section 9
step 4, and the source-onboarding spec section 5.5 (you implement its
EDGAR/NSM supports_since=true commitment; signal strings "EDGAR
submissions recency" and "NSM dated query" verbatim). Follow tasks in
order, test-first. The plan pins: EDGAR since-filter + skip older-page
pagination in incremental mode (full mode byte-identical); the NSM
dateCriteria payload exactly per docs/nsm_api_reference.md:168-171;
incremental on unsupported sources runs FULL with a logged notice; the
watermark file schema WITH the failed_records/download_quarantine
ledger (three failures = download quarantine, watermark unblocks,
register/health surface it) and `watermarks.record_outcomes` called by
the download CLI at the end of every run (your CLI wiring; LB7 needs no
extra step); MANIFEST-KEYED download skips for
edgar/nsm (skip when the storage_key is already in the restored
manifest with a recorded file_hash; a stateless runner has no local
originals, and full Tier A runner migration explicitly stays with the
source-onboarding build per plan section 12); config.toml descriptor
keys byte-matching plan 2.10; `corpus source list` (the onboarding
spec's own verb name, which its build later extends; never a second
verb).

HARD BOUNDARIES: no source-onboarding registry/shim/envelope/runner work
(the Dublin build owns those); no watermark PROMOTION wiring in any
workflow; no luxse/pdip incremental code; no workflow files.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_incremental_discovery.py
  (test_edgar_since_filters_and_skips_older_pages,
  test_edgar_full_unchanged, test_nsm_date_criteria_payload,
  test_nsm_full_unchanged,
  test_incremental_on_unsupported_source_runs_full_with_notice,
  test_download_skip_keyed_on_manifest_not_disk),
  test_watermarks.py (test_stage_then_promote_atomic,
  test_candidate_blocked_by_failures,
  test_three_strikes_quarantine_unblocks,
  test_success_clears_failed_record, test_download_outcomes_recorded,
  test_overlap_window),
  test_source_config.py (test_descriptors_parse,
  test_scheduled_sources_matrix, the source-list CliRunner case).
- Full pytest, ruff, pyright green.
- Config descriptor keys byte-match plan 2.10 (nsm/edgar/pdip/luxse/lse
  values exactly as pinned).
- One RECORDED live probe each for EDGAR and NSM incremental (--since 7
  days ago, counts + one sample record pasted in the PR; marked network,
  excluded from CI).

STOP AND REPORT (verbatim): the NSM production API rejects dateCriteria
(paste request and response verbatim; the fallback decision is the
architect's); EDGAR recent-window semantics cannot cover a 3-day
overlap. Standing rule: same DoD check fails twice, escalate thinking
once, retry once; still failing, STOP with a blocker report on TEA-1062.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push,
PR "LB5: EDGAR/NSM incremental discovery + source config (TEA-1062)".
Handoff on TEA-1062: Did / Why / Next (review gate; LB7 consumes) /
Pointer. Append to docs/build-metrics.md (conflict = keep both lines):
| LB5 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB6 (TEA-1033) Candidate staging, ledger, incremental upload, role policies. Claude Code, Opus 4.8 max. AFTER LB4 MERGES.

```
You are the EXECUTOR for branch LB6 (TEA-1033): the generation ledger,
private candidate staging with incremental upload, and the four OIDC role
policy documents, of the Lane B batch. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

PRECONDITION: LB4 (TEA-1061) is merged into main (check that
src/corpus/state/store.py exists with the ObjectStore protocol). If not,
STOP and report on TEA-1033. If LB3 (TEA-1060) has also merged, build on
it; if not, note in your handoff that a rebase check is owed when it
lands.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-1033-lb6-staging-ledger, based on current origin/main. Verify
HEAD before every commit.

Read YOUR plan section "LB6: Candidate staging, generation ledger,
incremental upload, role policies" plus plan 2.2, 2.7, 2.12 and spec
sections 9 (steps 11-12) and 13. Follow tasks in order, test-first.
Task 1 is the parquet byte-determinism measurement (build the fixture
snapshot twice, compare shas); the plan pre-decides both outcomes (file
sha, or the named logical-hash fallback field). The plan pins the LEDGER
schema, the empty-delta rule (generated_at never participates), the
legacy-manifest first-run rule (fetch_active returns None, full upload),
staging mechanics (changed uploaded gzip-per-2.2, unchanged SERVER-SIDE
COPIED from the active public generation, completeness assertion,
re-stage idempotent), and the four role policy/trust JSON scopes
INCLUDING the council-hardened positive permissions (plan 2.12: refresh
and reconcile read the public generations prefix; takedown gets lock,
suppressions, candidates, and journal scopes). test_role_policies.py
must assert required-operation coverage per role, not only scoping.

HARD BOUNDARIES: no workflow calls this yet (LB7/LB8); no public
generation copy (publish's phase 3); no pruning; never create any AWS
resource; policies are documents plus tests, nothing more.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_ledger.py (test_compute_deterministic,
  test_diff_empty_when_identical, test_diff_detects_text_change,
  test_legacy_manifest_full_upload), test_staging.py
  (test_changed_uploaded_unchanged_copied,
  test_completeness_assertion_fires, test_restage_idempotent),
  test_role_policies.py (per-role scoping AND required-operation
  coverage; no wildcard resources except the documented CloudFront ARN
  placeholder).
- Full pytest, ruff, pyright green.
- Determinism measurement recorded in the PR AND on TEA-1033, with the
  chosen ledger mechanism named.
- Before/after upload-size numbers for a fixture delta posted on
  TEA-1033 (the issue's own DoD line).
- infra/pipeline/ contains the four policy + four trust JSONs and the
  README with Teal's exact creation commands.
- Supersession note posted on TEA-1033: the original "deploy policy"
  framing is realized as the four-role model per spec section 13.

STOP AND REPORT (verbatim): server-side copy across buckets fails under
the planned role scopes on a live probe (paste the error; the policy fix
is the architect's); parquet proves nondeterministic AND the
logical-hash query exceeds 60 seconds on the real corpus. Standing rule:
same DoD check fails twice, escalate thinking once, retry once; still
failing, STOP with a blocker report on TEA-1033.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push,
PR "LB6: candidate staging, generation ledger, role policies
(TEA-1033)". Handoff on TEA-1033: Did / Why / Next (review gate; LB7/LB8
consume; Teal handoff items 1-2 use infra/pipeline/README.md) / Pointer.
Append to docs/build-metrics.md (conflict = keep both lines):
| LB6 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB7 (TEA-1042) refresh.yml walking-skeleton workflow. Claude Code, Opus 4.8 max. AFTER LB1+LB2+LB3+LB4+LB5+LB6 ALL MERGED.

```
You are the EXECUTOR for branch LB7 (TEA-1042): refresh.yml and the ops
verbs (health beacon, holdings register, RUN.json keepalive, PR upsert,
alarms, originals archival), the L branch of the Lane B batch. You are
not the architect. Use superpowers:executing-plans. Load operating
context from AGENTS.md.

PRECONDITION: verify ALL of LB1 (TEA-1032), LB2 (TEA-1059), LB3
(TEA-1060), LB4 (TEA-1061), LB5 (TEA-1062), LB6 (TEA-1033) are merged
into main (check for: docling_html.py, quarantine.py, `corpus snapshot
build --suppressions` in cli.py, state/store.py, sources/source_config.py,
publish/staging.py). Any missing: STOP and report on TEA-1042.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-1042-lb7-refresh-workflow, based on current origin/main. Verify
HEAD before every commit.

Read YOUR plan section "LB7: refresh.yml, the walking-skeleton workflow"
plus plan 2.6, 2.9, 2.11 and spec sections 9, 14, 15. Follow tasks in
order, test-first. The plan pins the workflow skeleton YAML (triggers,
inputs incl. the fail_at drill hook, concurrency group refresh with
cancel-in-progress false, explicit permissions, cron COMMENTED OUT) and
the exact step order; transcribe it, including the council-hardened
steps: Docling weights cache restore AND save; actions/cache/save for
the DB keyed on the new sha (without it cache-first restore never
materializes); the incoming/ step as list-warn-continue (never consume,
never fail); `corpus ops archive-originals`; health-write with
daily-lane-only sources, per-row freshness_red_days from config,
pending_since preserved across candidate supersedes,
consecutive_zero_days, download_quarantine_count, and db_bytes; the
`alarm: state size` self-check; RUN.json with the metrics block; the
failure path firing the alarm AND a best-effort health-write outcome
failed. Also pinned: the 2.9 alarm helper contract, the PR body content
(three sampled source URLs with excerpts, no candidate links, the exact
rollback command), supersede-not-stack PR upsert, the keepalive push
assertion, and the ci.yml delta (workflow_dispatch trigger + SHA-pin the
four existing action tags, nothing else) plus .github/dependabot.yml.

HARD BOUNDARIES: NEVER dispatch refresh.yml against production state
(the first real dispatch is OPS-B's walking skeleton, by spec section 19
ordering); cron stays commented; no publish.yml (LB8); no
reconcile/takedown; no luxse or pdip in the daily source derivation.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_ops_register.py
  (test_no_change_day_byte_identical, test_holdings_change_updates,
  test_onboarding_fields_render_when_stores_exist),
  test_ops_run_json.py::test_candidate_null_contract,
  test_ops_alarms.py (test_find_or_create_by_exact_title,
  test_green_resolves_only_own_signal),
  test_ops_pr_body.py::test_body_contains_counts_samples_rollback,
  test_ops_health.py (test_beacon_fields_and_no_store_metadata,
  test_pending_since_survives_candidate_supersede,
  test_daily_lane_sources_only, test_consecutive_zero_days_counter),
  test_refresh_workflow_static.py (concurrency, permissions, SHA pins,
  cron absent-or-commented, fail_at only for workflow_dispatch, cache
  save steps present).
- actionlint clean on refresh.yml and the modified ci.yml.
- Full pytest, ruff, pyright green.
- .github/dependabot.yml present (github-actions ecosystem, weekly).
- Spec section 9 steps 1-17 each traceable to a workflow step or named
  verb in a PR-body table.
- Supersession note posted on TEA-1042 for its issue-body deltas vs the
  spec (preview-build language; MANIFEST-age wording replaced by the
  pending-candidate lag signal), citing spec sections 9, 10, 14.

STOP AND REPORT (verbatim): any verb from LB1-LB6 proves missing or
misshapen for a step (name it; NEVER reimplement inline); the keepalive
assertion cannot be made from within the run. Standing rule: same DoD
check fails twice, escalate thinking once, retry once; still failing,
STOP with a blocker report on TEA-1042.

Self-review: fresh output per DoD line; diff read; workflow YAML
re-read line by line against the plan skeleton; no em-dashes. Push, PR
"LB7: refresh.yml daily PR-gated refresh (TEA-1042)". Handoff on
TEA-1042: Did / Why / Next (review gate; OPS-B runs the skeleton) /
Pointer. Append to docs/build-metrics.md (conflict = keep both lines):
| LB7 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB8 (TEA-1064) publish.yml journaled deploy-first activation. Claude Code, Opus 4.8 max. BUILDS AFTER LB4+LB6; MERGES AFTER LB7.

```
You are the EXECUTOR for branch LB8 (TEA-1064): publish.yml and the
journaled deploy-first activation verbs (epoch fencing, Netlify
deploy-by-id, CAS MANIFEST flip, delta-typed smoke incl. the new-slug
and removal-only variants, paired fenced rollback) of the Lane B batch.
You are not the architect. Use superpowers:executing-plans. Load
operating context from AGENTS.md.

PRECONDITION: LB4 (TEA-1061) and LB6 (TEA-1033) merged (state/store.py,
publish/ledger.py exist). If LB7 has not merged yet you may still build
(your contracts are plan 2.6-2.8), but your PR merges only after LB7's.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb8-publish-workflow, based on current origin/main. Verify HEAD
before every commit.

Read YOUR plan section "LB8: publish.yml, journaled deploy-first
activation" plus plan 2.7-2.8 and spec section 10. Follow tasks in
order, test-first. The plan pins: the trigger (push to main on
docs/refresh/RUN.json + workflow_dispatch inputs `gen` (explicit
generation to publish or resume; empty = read RUN.json), rollback_to,
and kill_after; kill_after supports BOTH `activate` and `activate-mid`,
the second killing between the CAS PUT and the journal done_at write,
and is ALSO honored from the repo variable DRILL_KILL_AFTER so the
merge-triggered run of a drill day can be killed deterministically); the
SHARED activation concurrency group; the null-candidate green exit; the
eight phases with journal-before-execute and resume-from-journal
INCLUDING the mid-activation tear rule (the activate intent records
target_gen + expected_prev_etag; resume recognizes an already-won CAS by
generation equality and STILL runs the smoke; a third generation live
aborts with an alarm); both epoch checks; the always()-restored
BUILD_DATA_FETCH_BASE; the fenced deploy restore; the DELTA-TYPED smoke
(changed-slugs case with the id="ew-doc-text" new-slug assertion;
removal-only case asserting a sampled retained doc; MANIFEST parity
always; the browser-level rendered assertion is the wrapper
live-smoke's, not yours) and the `--absence-check <slugs-file>` helper
LB11 consumes; and `corpus publish rollback`.

HARD BOUNDARIES: no takedown chaining (LB11 calls your verbs); no
wrapper repo changes; no candidate creation; NEVER dispatch against
production (OPS-B owns first execution and the drills).

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_publish_journal.py
  (test_resume_skips_done_phases, test_never_green_without_smoke,
  test_resume_after_mid_activation_crash),
  test_publish_activate.py (test_epoch_stale_aborts_before_any_write,
  test_pre_flip_epoch_recheck, test_cas_conflict_aborts),
  test_publish_netlify.py (test_env_always_restored,
  test_deploy_restore_fenced), test_publish_smoke.py
  (test_markdown_day_assertions, test_txt_only_day_assertions,
  test_new_slug_render_assertion, test_removal_only_day_assertions,
  test_absence_check_all_members),
  test_publish_workflow_static.py (trigger paths, shared activation
  group, SHA pins, null-candidate exit, gen dispatch input present,
  DRILL_KILL_AFTER variable honored).
- actionlint clean; full pytest, ruff, pyright green.
- Runbook sections "Publish anatomy", "Rollback", "Torn-publish resume",
  and "Secret rotation" (NETLIFY_AUTH_TOKEN scope/expiry/rotation; the
  OIDC immutable owner/repo-ID hardening note from spec s13) written.
- Spec section 10 phases 1-8 and acceptance criteria 4, 8, 9 mapped in
  the PR body.

STOP AND REPORT (verbatim): netlify-cli lacks any listed API call under
the pinned version (paste which); the doc container marker cannot be
found in built page HTML. Standing rule: same DoD check fails twice,
escalate thinking once, retry once; still failing, STOP with a blocker
report on TEA-1064.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push,
PR "LB8: publish.yml journaled deploy-first activation (TEA-1064)".
Handoff on TEA-1064: Did / Why / Next (review gate after LB7 merges;
OPS-B drills consume kill_after) / Pointer. Append to
docs/build-metrics.md (conflict = keep both lines):
| LB8 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB9 (TEA-1063) Wrapper live-smoke freshness + per-signal alarms. CODEX gpt-5.6-sol xhigh. WRAPPER REPO ONLY. Anytime after the plan merges.

```
You are the EXECUTOR for branch LB9 (TEA-1063): freshness signals and
per-signal alarm issues in the wrapper live-smoke. You are not the
architect: implement exactly what the plan says, decide nothing. Work
test-first where a test exists to write. Wrapper repo ONLY:
~/Code/prospectus-web-ti. Read its README first.

Create an isolated worktree: from the wrapper repo root,
  git worktree add ../pwti-wt-lb9 -b lte/lb9-live-smoke-freshness
and work there. Before EVERY commit run `git rev-parse --abbrev-ref
HEAD` and confirm the branch.

Read YOUR plan section "LB9: Wrapper live-smoke freshness + per-signal
alarms" plus plan sections 2.6 (health beacon schema) and 2.9 (signal
titles and thresholds, exact) in
/Users/teal_emery/code/sovereign-prospectus-corpus/docs/superpowers/plans/2026-07-19-lane-b-stage2-batch-plan.md,
and spec section 14. The plan pins: the freshness evaluation gated
behind env SMOKE_FRESHNESS=on, DEFAULT OFF (the beacon does not exist
until OPS-B; production must stay green today); the exact issue titles
and thresholds (liveness > 2 days red; publication lag keyed on
pending_candidate.pending_since, > 4 days nudge comment without
failing, > 8 days red; per-source last_discovery_success older than
that row's OWN freshness_red_days = red; the beacon carries only
daily-lane sources, so archive sources can never false-alarm; missing
beacon = liveness red); each signal independently opening and closing
its own issue via scripts/alarm.mjs (find-or-create by exact title,
REST + GITHUB_TOKEN); the drill hook: live-smoke.yml gains a
workflow_dispatch input `drill` (default empty) mapped to env
SMOKE_DRILL on the script step, so `gh workflow run live-smoke.yml -f
drill=liveness_red` swaps in the named fixture while exercising the
REAL issue path (OPS-B's wrapper alarm drill); workflow permissions
gaining issues: write; all three action tags SHA-pinned; the four
self-test fixtures.

HARD BOUNDARIES: wrapper repo only; do not touch the standing 3 smoke
checks' logic; no corpus repo changes; the incoming-age signal code path
ships but is exercised by fixture only (no feeder exists).

DEFINITION OF DONE (verbatim from the plan):
- node --test scripts/live-smoke.test.mjs green with the four named
  fixture cases: green_all, liveness_red, lag_nudge_then_red,
  source_stale.
- node scripts/live-smoke.mjs against production still passes its
  standing 3 checks TODAY (freshness off by default), output pasted in
  the PR body.
- live-smoke.yml: permissions {contents: read, issues: write}, SHA
  pins, GITHUB_TOKEN passed to the script step; lints (actionlint if
  available, else push and gh workflow view).
- README updated: each signal, its threshold, how to self-test, the
  SMOKE_DRILL hook, and that OPS-B enables SMOKE_FRESHNESS.

STOP AND REPORT (verbatim): production live-smoke fails its standing
checks today (LIVE INCIDENT: report immediately on TEA-1063 and touch
nothing); GITHUB_TOKEN cannot create issues in the private wrapper repo
(paste the API error). Standing rule: same DoD check fails twice,
escalate reasoning once, retry once; still failing, STOP with a blocker
report on TEA-1063.

Self-review: fresh command output per DoD line; diff read; thresholds
byte-checked against plan 2.9; no em-dashes. Push, PR "LB9: live-smoke
freshness signals + per-signal alarms (TEA-1063)". Handoff on TEA-1063:
Did / Why / Next (review gate; OPS-B flips SMOKE_FRESHNESS and runs the
SMOKE_DRILL alarm drill) / Pointer. Append to the CORPUS repo's
docs/build-metrics.md via your handoff comment if you cannot commit
there (conflict = keep both lines):
| LB9 | gpt-5.6-sol xhigh | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB10 (TEA-1065) reconcile.yml weekly/monthly hygiene. Claude Code, Opus 4.8 max. AFTER LB7 MERGES.

```
You are the EXECUTOR for branch LB10 (TEA-1065): reconcile.yml (weekly
full-window rediscovery, PDIP cycle, quarantine retry, FTS rebuild,
integrity audit, pinned pruning, monthly deep sweep + two-pool
revalidation) of the Lane B batch. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

PRECONDITION: LB7 (TEA-1042) merged (src/corpus/ops/ exists with alarms
and health verbs). If not, STOP and report on TEA-1065.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb10-reconcile-workflow, based on current origin/main. Verify HEAD
before every commit.

Read YOUR plan section "LB10: reconcile.yml, weekly and monthly
hygiene" and spec section 11. Follow tasks in order, test-first. The
plan pins: everything under the fenced lock; the pin set for pruning
(active gen, its predecessor from the journal, the open PR's candidate
from refresh/daily's RUN.json, the candidate named by RUN.json at
origin/main HEAD, unclosed journal targets) and the keep windows;
quarantine three-strike with --dequarantine override; the WEEKLY
download-quarantine retry (one attempt per entry during the full-window
pass; success removes the entry, failure leaves it); the TWO-POOL
revalidation with DIFFERENT consequences: primary document URLs run the
inline Gate 1 update (invalidate parsed outputs first, new
content-addressed original, appended manifest record under
latest-record-wins), while LISTING URLs record divergence to the
advisory lane with an alarm and NEVER mutate the canonical document
(the onboarding spec 5.8 rule); the _reconcile.json quarantine-growth
baseline; zero-finds consuming the beacon's consecutive_zero_days AND
this run's full-window result; the seam-delta-3 listing extension and
the `alarm: review pending <source>` evaluation both behind schema/file
existence checks; cron COMMENTED until OPS-B.

HARD BOUNDARIES: cron stays commented; no takedown deletion scopes; no
feeder consumption (the daily incoming/ step is not yours and
revalidation does not route through it); NEVER dispatch against
production state (OPS-B runs the pre-flight).

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_prune_pins.py (test_pin_set_never_deleted,
  test_keep_policy_window, test_merged_unpublished_candidate_pinned),
  test_reconcile_quarantine.py (test_three_strikes_permanent,
  test_dequarantine_forces, test_download_quarantine_weekly_retry),
  test_revalidate.py
  (test_changed_bytes_alarm_and_inline_update,
  test_listing_divergence_advisory_never_updates_canonical,
  test_quarantine_growth_fires_and_resolves),
  test_integrity_audit.py::test_seeded_mismatch_detected,
  test_reconcile_workflow_static.py (cron commented, lock steps, deep
  monthly guard, SHA pins).
- actionlint clean; full pytest, ruff, pyright green.
- Runbook section "Weekly reconcile and pruning" written.
- Spec section 11 items each mapped in the PR body.

STOP AND REPORT (verbatim): the pin-set computation cannot determine
either candidate pin without new plumbing (name the gap); DuckDB FTS
rebuild fails on restored state. Standing rule: same DoD check fails
twice, escalate thinking once, retry once; still failing, STOP with a
blocker report on TEA-1065.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push,
PR "LB10: reconcile.yml weekly/monthly hygiene (TEA-1065)". Handoff on
TEA-1065: Did / Why / Next (review gate; OPS-B pre-flight + cron-on) /
Pointer. Append to docs/build-metrics.md (conflict = keep both lines):
| LB10 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## LB11 (TEA-1067) takedown.yml epoch-fenced complete takedown. Claude Code, Opus 4.8 max. AFTER LB7+LB8 MERGE.

```
You are the EXECUTOR for branch LB11 (TEA-1067): takedown.yml
(environment-gated, epoch-fenced, equivalence-class-complete takedown
with sanitized republish and absence smoke; seam delta 5) of the Lane B
batch. These are legal documents; the mechanism must be complete and
exactly as planned. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

PRECONDITION: LB7 (TEA-1042) and LB8 (TEA-1064) merged (ops verbs and
publish/activate.py with --absence-check exist). If not, STOP and report
on TEA-1067.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/lb11-takedown-workflow, based on current origin/main. Verify HEAD
before every commit.

Read YOUR plan section "LB11: takedown.yml, epoch-fenced complete
takedown" plus plan 2.8 and spec section 12, and the source-onboarding
spec's handed delta 5 (its section 4). Follow tasks in order,
test-first. FIRST check whether the source-onboarding build's shared
fixed-point equivalence query has landed (grep src/corpus/db/ for it);
if present IMPORT AND USE IT; if absent implement
suppress.equivalence_class with the plan's identical semantics
(fixed-point over duplicate_of edges both directions AND same-file_hash
peers across documents and, when present, document_listings;
schema-checked degradation) and file the unification follow-up issue.
The plan pins the rest: the workflow_dispatch inputs and `environment:
takedown`; the five ordered steps under the state lock; one epoch bump
per takedown action covering all members; scoped generation text
deletes + one CloudFront invalidation; candidate retirement; the
sanitized republish INSIDE the same dispatch via `corpus snapshot build
--suppressions` + stage + `corpus publish run --gen <sanitized>
--absence-check <class-slugs-file>` under the SHARED activation
concurrency group with the PR gate skipped (the Environment approval
WAS the human gate); LB8's removal-only smoke variant applies.

HARD BOUNDARIES: no IAM or Environment creation (Teal handoff item 3);
no drill execution (OPS-B step 10); no un-suppress automation (runbook
procedure only); NEVER dispatch against production.

DEFINITION OF DONE (verbatim from the plan):
- Named tests green: test_suppress_class.py
  (test_fixed_point_over_duplicate_of_and_hash,
  test_absent_tables_degrade, test_one_epoch_per_action),
  test_takedown.py (test_ledger_append_and_epoch_bump,
  test_generation_deletes_scoped, test_open_candidate_retired,
  test_absence_smoke_asserts_all_members),
  test_takedown_workflow_static.py (environment name, shared activation
  group on the republish job, SHA pins, permissions).
- actionlint clean; full pytest, ruff, pyright green.
- Runbook section "Takedown" written (mechanism, drill pointer, the
  documented un-suppress procedure).
- Spec section 12 and acceptance criterion 13 mapped in the PR body;
  the drill is explicitly named as OPS-B's.

STOP AND REPORT (verbatim): the shared activation concurrency group
cannot span the two workflows as specified (record the observed Actions
limitation); CloudFront invalidation ARN scoping rejects the wildcard
path form. Standing rule: same DoD check fails twice, escalate thinking
once, retry once; still failing, STOP with a blocker report on
TEA-1067.

Self-review: fresh output per DoD line; diff read; no em-dashes. Push,
PR "LB11: takedown.yml epoch-fenced takedown (TEA-1067)". Handoff on
TEA-1067: Did / Why / Next (review gate; OPS-B drill) / Pointer. Append
to docs/build-metrics.md (conflict = keep both lines):
| LB11 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## OPS-A (TEA-1066) Cutover execution. Claude Code, Opus 4.8 max. AFTER LB4 MERGES + TEAL HANDOFF ITEMS 1-2.

```
You are the OPERATOR for OPS-A (TEA-1066): executing the one-time state
cutover to the private pipeline bucket. This session runs commands and
records evidence; it writes NO new code (a single small PR committing
docs/refresh/cutover-baseline.json and runbook edits is the only repo
change). Load operating context from AGENTS.md. Use
superpowers:verification-before-completion for every claim.

PRECONDITIONS (verify each; ANY failure is a stop-and-report on
TEA-1066, never an improvisation): LB4 (TEA-1061) merged; bucket
ti-sovtech-pipeline exists with Block Public Access + versioning (aws
s3api commands from infra/pipeline/README.md); role
ti-sovtech-gha-refresh exists; repo variables set (plan 2.12). You run
on Teal's Mac with the existing local AWS profile; if any credential or
console action is needed, STOP and hand the exact item to Teal.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus, main checkout,
current main. Read the plan sections "OPS-A" and 2.2-2.4, spec section 5
(cutover paragraph), and docs/refresh-runbook.md "Cutover".

Sequence (each step's output pasted into the TEA-1066 trail as you go):
1. `uv run corpus state cutover --dry-run` and review the plan it
   prints.
2. Real run under caffeinate: compaction (record before/after DB bytes;
   the FTS drop is the predicted bulk), revision 0 upload, parsed-tree
   sync, source_state seed (watermarks seeded from current holdings max
   dates), content-addressed originals upload (hours; resumable;
   re-runs are idempotent), STATE.json created via If-None-Match.
3. Commit docs/refresh/cutover-baseline.json via a small PR (counts by
   source, pages, markdown rows, manifest line counts).
4. After that PR merges, dispatch state-verify.yml on the hosted runner
   (gh workflow run state-verify.yml) and confirm EXACT count match and
   the OIDC assume-role success (this is the first trust-policy proof).
5. Record wall times, sizes, and the public-access check result on
   TEA-1066 and in the runbook Cutover section.

STOP AND REPORT: any AWS permission error (never widen a policy
yourself); any count mismatch between Mac baseline and hosted restore;
any need to touch the AWS console. Standing rule applies.

Handoff on TEA-1066: Did / Why / Next (OPS-B unblocked once LB0, LB7,
LB8, LB9, LB10, LB11 are merged and Teal items 3-7 done) / Pointer (run
URLs, baseline PR). Append to docs/build-metrics.md:
| OPS-A | opus-4.8 max | <attempts> | <escalations> | n/a | <wall time> |
```

---

## OPS-B (TEA-1068) Walking skeleton, drills, spike disposition, cron-on. Claude Code, Opus 4.8 max. FINAL GATE.

```
You are the OPERATOR for OPS-B (TEA-1068): the walking skeleton, the
drills (alarm both legs, rollback, torn-publish, takedown), the LuxSE
disposition, the reconcile pre-flight, and cron-on. This is the spec's
section 19 executed against production, with Teal in the loop at named
gates. You write no new code; the only commits are the small config PRs
named below PLUS the close-out documentation PR (runbook sections,
SESSION-HANDOFF.md). Load operating context from AGENTS.md. Use
superpowers:verification-before-completion throughout: no claim without
fresh command output.

PRECONDITIONS (verify; any miss is a stop-and-report on TEA-1068): LB0
(TEA-1058), LB7 (TEA-1042), LB8 (TEA-1064), LB9 (TEA-1063), LB10
(TEA-1065), LB11 (TEA-1067) ALL merged (step 10 dispatches takedown.yml
and step 11 dispatches reconcile.yml, so neither may be missing);
OPS-A (TEA-1066) complete with state-verify green; Teal handoff items
3-7 done (takedown Environment; NETLIFY_AUTH_TOKEN + NETLIFY_SITE_ID +
CLOUDFRONT_DISTRIBUTION_ID; repo watch settings; the Actions
"create and approve pull requests" setting + refresh/daily ruleset
check).

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus. Read the plan
sections "OPS-B", 2.6-2.9, and spec sections 19-20; keep spec section
19's checklist open and verify it item by item.

Sequence (STOP at each [TEAL] gate; post the evidence trail on TEA-1068
as you go):
1. Dispatch refresh.yml: sources=edgar, since chosen to guarantee at
   least one real new filing. Verify: fenced lock, sha-verified restore,
   incremental discovery, content-addressed original, Gate 0 parse,
   Gate 1 ingest, register + health beacon, ledger delta, private
   candidate (transfer log: few uploads, thousands of server-side
   copies), state revision + CAS commit, RUN.json on refresh/daily,
   exactly one PR, dispatched CI green on the PR head.
2. [TEAL] Merge the refresh PR.
3. Verify publish end to end: journal phases, epoch check, generation
   copy, deploy-first with exact deploy id polling, CAS flip, smoke
   green; the new document's live page returns 200 with
   text_source='markdown' and renders correctly in a real browser (eye
   check). Then trigger one ORDINARY wrapper deploy and verify it
   builds against the new generation via the MANIFEST data_base (the
   LB3 build.sh half proven in production; page count matches).
4. One-line wrapper PR setting SMOKE_FRESHNESS=on in live-smoke.yml env;
   after merge, dispatch live-smoke and confirm all signals green.
5. Alarm drill, corpus side: dispatch refresh.yml with fail_at=discover.
   Confirm the "alarm: refresh failure" issue opens with evidence and
   the email reaches lte@tealinsights.com [TEAL confirms receipt]. Next
   green dispatch closes it; confirm.
5b. Alarm drill, wrapper side: gh workflow run live-smoke.yml -f
   drill=liveness_red. Confirm the wrapper "alarm: pipeline liveness"
   issue opens and its email arrives [TEAL confirms]. A normal dispatch
   closes it; confirm. The independent dead-man's own notification path
   is now proven (spec s14).
6. Rollback drill: gh workflow run publish.yml -f rollback_to=<previous
   generation>. Verify pointer + deploy pair restored, site coherent;
   then re-activate the current generation the same way and verify.
7. Torn-publish drill: before merging the next real candidate's PR,
   set the repo variable: gh variable set DRILL_KILL_AFTER
   --body activate-mid. [TEAL] merges; the merge-triggered publish run
   dies between the CAS PUT and the journal done_at write (the torn
   window). Clear the variable (gh variable delete DRILL_KILL_AFTER),
   then resume: gh workflow run publish.yml -f gen=<candidate>. Verify
   the resume recognizes the landed flip, completes the smoke, and only
   then reports green.
8. NSM joins: dispatch refresh.yml with sources=edgar,nsm; verify both
   sources' beacon rows and the register.
9. LuxSE disposition from TEA-1058's recorded outcome: config PR
   flipping luxse.scheduled=true, OR mint the Mini feeder issue and
   confirm the register shows the feeder-pending row. [TEAL] merges.
   Write the runbook "Spike outcomes" section either way.
10. Takedown drill: inject the synthetic drill document via the
    documented local-takeover procedure (title "Synthetic takedown
    drill artifact, not a filing", source edgar, native id
    TEST-TAKEDOWN-DRILL-1; the runbook recipe is itself under test
    here). Dispatch refresh.yml (sources=edgar) to build the candidate
    carrying it; [TEAL] merges that drill PR; after publish, run
    takedown.yml on it ([TEAL] approves the environment gate). Verify:
    epoch bump, generation deletes + invalidation, candidate
    retirement, sanitized republish, absence smoke green (parquet row
    absent, text 404, site page 404), register takedown count.
11. Reconcile pre-flight, THEN cron-on: dispatch reconcile.yml once
    (deep=false); verify the reconcile OIDC role assumes (the last of
    the four trust assertions), FTS rebuild + integrity audit green,
    pruning pin set logged correctly. Then the cron-on PR: uncomment
    both schedules (refresh.yml, reconcile.yml). [TEAL] merges. Close
    TEA-906 as superseded by TEA-1042 with a pointer comment.
12. Close-out: post on TEA-1042 the five-clean-runs watch checklist
    (the build's DoD closes ONLY when five consecutive scheduled runs
    with zero manual intervention besides merges are recorded there, at
    least one publishing a real new document; each day marked by Teal
    or a 10-minute check-in session), the Netlify build-minutes budget
    line, and the per-run metrics note (spec s24). Link the skeleton
    run on TEA-1031 (its own DoD line). Write the runbook "Accepted
    residual risks" section (lock CAS deviation, mid-window wrapper
    build, torn-sync determinism argument). Update SESSION-HANDOFF.md
    and post the closing trail on TEA-1068.

STOP AND REPORT: ANY deviation from the spec section 19 checklist; any
alarm that does not fire or does not resolve as designed; any Teal gate.
Never work around a failed drill; a failed drill is a finding, not an
obstacle. Standing rule applies.

Handoff on TEA-1068: Did / Why / Next (five-clean-runs watch to
completion on TEA-1042; TEA-1054 flip stays gated on TEA-1034's e2e
suite + the recorded clean cycles) / Pointer (run URLs, drill
evidence). Append to docs/build-metrics.md:
| OPS-B | opus-4.8 max | <attempts> | <escalations> | n/a | <wall time> |
```
