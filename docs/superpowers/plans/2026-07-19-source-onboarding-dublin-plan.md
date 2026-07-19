# Source Onboarding Pattern + Dublin: Stage 2 Branch Plan (D0-D11)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement YOUR BRANCH ONLY, task by task. Steps use checkbox (`- [ ]`) syntax. Each branch runs in a fresh executor session with its own worktree; paste-ready prompts live in `docs/superpowers/plans/2026-07-19-source-onboarding-dublin-executor-prompts.md`.

**Goal:** Land the adapter contract (registry + runner + two-tier shims + contract suite + toysource proof), the corpus-wide dedup pass with its one-time audit, the three one-time platform refactors, and the Euronext Dublin source end to end (spike, allowlist, adapter, walking skeleton, executed backfill), per the signed Stage 1 spec.

**Spec (NORMATIVE):** `docs/superpowers/specs/2026-07-19-source-onboarding-dublin-design.md` (v3.1 + Stage 2 hygiene edits; Teal-signed, merged as PR #129). The spec decides mechanisms; this plan decomposes them into branches and pins the file-level and cross-branch interfaces the spec leaves open. Where plan and spec appear to disagree, the spec wins and the disagreement is a stop-and-report.

**Architecture:** One protocol module boundary (`src/corpus/sources/base.py`), a registry resolving `config.toml` `active_sources` against a package list, a shared runner owning writes/hashes/manifests/breaker/telemetry, and a parametrized contract suite that picks up every registered source. Dedup is ingest-side: SHA-256 hard key, `document_listings` attach, advisory-only near-dup lane. Dublin is the first Tier A source; the four legacy adapters ride Tier B shims.

**Tech stack:** Python 3.12 + uv, Click, DuckDB, Polars, pytest, ruff, pyright. One explorer-web touch (D6 fixture test: vitest).

**Linear:** every branch trails on TEA-1035 (handoff comment per branch: Did / Why / Next / Pointer). TEA-1053 (ESMA) and TEA-1055 (SGX) get pointer comments from the architect, not from executors.

## Global constraints

- **The spec is normative.** Executors read their branch section here AND the spec sections it names. A design decision neither document makes is a stop-and-report, not a judgment call.
- **No em-dashes** anywhere: code, docs, commits, comments, PR bodies.
- **Worktrees:** every executor works in a git worktree (superpowers:using-git-worktrees), branch named `lte/tea-1035-d<N>-<slug>`, based on current `origin/main`. Verify `git rev-parse --abbrev-ref HEAD` before every commit. Diff against `origin/main`, not local `main`.
- **Verification per CI:** `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run pyright src/ tests/` (no NEW errors; verify.py preexisting errors are tracked separately), `uv run pytest -v`, plus each branch's end-to-end run. superpowers:verification-before-completion before any done claim.
- **Data mount (council, 2-seat convergent):** fresh worktrees contain NO `data/` (gitignored), and DuckDB silently auto-creates a missing DB file. Before ANY step that reads or writes runtime data, symlink it from the canonical checkout: `ln -s /Users/teal_emery/code/sovereign-prospectus-corpus/data data`. Then run the identity guard: `SELECT count(*) FROM documents` against `data/db/corpus.duckdb` must return roughly 9,795 (plus any documents merged since); ANY other number (especially 0) is a STOP, not a proceed. D1, D3, D4, D5, D7, and D10 all depend on this.
- **Data safety:** `data/` is never committed. Any branch that alters the DuckDB schema or runs UPDATE/INSERT against `data/db/corpus.duckdb` rehearses on a copy first (unique per-branch path: `cp data/db/corpus.duckdb /tmp/corpus-rehearsal-d<N>.duckdb`, after confirming no writer holds the source DB; spec risk 6) and says so in the PR. Real-DB mutations run only where a branch's tasks explicitly say so. The production snapshot is never regenerated in this batch; local snapshot builds go to an alternate output dir via the existing `--output-dir` flag on `scripts/build_snapshot.py`.
- **Canonical-state gate (council):** if Lane B's S3-canonical state cutover has happened by the time a branch reaches a real-DB mutation (check: a state revision / STATE.json mechanism exists per the Lane B build, TEA-1042), STOP-and-report instead of mutating local state. A git merge is not a dependency edge for untracked database state, and a local mutation after cutover can be silently reverted by the next hosted refresh. Pre-cutover (the expected case for this batch), the canonical Dropbox corpus is the target.
- **Forward-only:** no retroactive merging of existing documents, no published URL changes, `scope_status='excluded'` never used for dedup (spec s3.3, s5.8).
- **Registration is not activation:** Dublin merges `scheduled = false`. The only `scheduled = true` values in this batch are the spec s6 assignments (nsm, edgar, pdip; luxse false).
- **Config append discipline:** `config.toml`, `sql/001_corpus.sql`, and `docs/build-metrics.md` are multi-branch append zones. Add at the end of the relevant section; rebase conflicts there are declared mechanical (keep both sides). Non-mechanical conflicts are stop-and-report.
- **Metrics:** every branch appends one line to `docs/build-metrics.md`: `| D<N> | <model+effort> | <attempts> | <escalations> | <council C/I post-exec> | <wall time> |`. Fold the line into the pre-merge commit (a self-authored follow-up PR cannot be auto-merged).
- **Review gates:** per Project Shell Runbook Stage 4, each branch gets a thin fresh review-gate session (never the executor's own session) before merge; rebased review-gate branches land via merge-forward + plain push (force-push is permission-gated). Executors end at the handoff comment.
- **Coexistence:** the 2026-07-15 coverage-feedback patch batch may be in flight in the same repo. Rebase before merge; the conflict surface below is within THIS batch only, so treat any cross-batch conflict as stop-and-report.

## Branch graph, routing, merge order

| Branch | Spec sections owned | Size | Executor | Depends on | Wave |
|---|---|---|---|---|---|
| D0 spike | s7.1 (all seven burn-downs), Dublin ToS line (s5.9) | spike | Claude Code, Opus 4.8 max | none | 1 (day one) |
| D1 PDIP hash backfill | s5.8 hash-coverage precondition, AC 16 | S/M | Codex, reasoning high | none | 1 (day one) |
| D2 contract core | s5.1-5.7, s5.9-5.13 declarations, AC 1/2/8/11/12/13/19 + s5.4 test half of AC 14 | L | Claude Code, Fable 5 xhigh | none | 1 (day one) |
| D4 country refactor | s5.14 refactor 1, obligor role migration (s7.3), AC 15 | M | Claude Code, Opus 4.8 max | none | 1 (day one) |
| D6 parquet policy | s5.14 refactor 3, AC 20 | S | Codex, reasoning high | none | 1 (day one) |
| D3 Tier B shims + parity | s6, s5.11 parity matrix, live smoke (s14), LuxSE mini-spike (s5.14 refactor 2 note) | M/L | Codex, reasoning high | D2 merged | 2 |
| D5 filing_url fallback | s5.14 refactor 2, snapshot half of AC 14 | S | Codex, reasoning high | D2 merged | 2 |
| D7 dedup pass + audit | s5.8 (all), AC 3/4/5/6/7/18; audit run needs D1 | L | Claude Code, Fable 5 xhigh | D6 merged; D1 merged AND rebased over before the audit run task (the audit reads D1's report + hashes) | 2 |
| D8 allowlist sweep | s7.2 allowlist + pilot-table proposals | M | Claude Code, Opus 4.8 max | D0 MERGED (its worktree reads D0's committed findings file) | 2 |
| D9 Dublin adapter | s7.2 discovery, s7.3, s7.5, s5.13 checklist, AC 9 | M | Claude Code, Opus 4.8 max | D2 + D3 + D8 merged (D3 is a mandatory base: D9 rides the generic dispatch and the tightened tier validation) | 3 |
| D10 skeleton + backfill | s13, s7.4, AC 10, DoD backfill lines | M (operational) | Claude Code, Opus 4.8 max | D1, D3, D4, D5, D6, D7, D9 all merged | 4 |
| D11 how-to + paper re-check | s10, s8/s9 revisit (s14 DoD line) | S/M | Claude Code, Opus 4.8 max | D10 done | 5 |

**Merge order:** D2 first among wave 1 code branches (it unblocks D3/D5/D9); D1/D4/D6 merge as they finish; then D3, D5, D7, D8; then D9; then D10; then D11. D0 is a docs+evidence PR (spike findings + Dublin ToS section) and merges as soon as dispositioned.

**Cross-branch file conflict surface (know it before you rebase):** `config.toml` (D2 rewrites source blocks and sets landing_url values; D3 adds `cli_options` blocks; D5 corrects landing_url values it fails to verify; D9 adds `[dublin]`), `sql/001_corpus.sql` (D4 role comment; D7 table + columns), `src/corpus/cli.py` (D2 generic commands + source list; D3 legacy dispatch swap; D7 dedup commands), `src/corpus/sources/base.py` (D2 types; D3 LegacyShim append), `src/corpus/sources/runner.py` (D2 creates; D7 adds the listings skip-set leg), `src/corpus/snapshot.py` (D4, D5, D6, D7 additive column), `tests/sources/test_contract.py` (D2 creates; D3 Tier B rows; D7 dedup cases), `docs/build-metrics.md` (all). Append-only discipline per the global constraint; D5 and D7 rebase onto merged D2/D6 rather than pre-merging each other's edits.

**Architect follow-through (this session and batch close, not executor branches):**
1. REOPEN TEA-1035 to In Progress (PR #129's merge auto-closed it, but its own Done-when checklist is this batch's work) and post the trail comment with the plan pointer and dispatch schedule.
2. Pointer comments on TEA-1053/TEA-1055 (the pattern they reuse is now planned); at batch close, post D11's ESMA/SGX re-check outcome to the same two issues (an s14 DoD line, owned here, not by the D11 executor).
3. Record on TEA-1042 (refresh.yml v1, the standing Lane B build issue) NOW: the five s4 seam deltas AND the four plan-level pins Lane B consumes: (a) `documents.suppressed_at` and `suppression_records` are synchronized PROJECTIONS of the platform's canonical suppressions ledger (state/suppressions.jsonl + epoch); takedown.yml MUST apply ledger and projection in the same commit, via D7's `apply_suppressions()`; (b) review-lane items live in the promoted state tree as `review_lane.jsonl` with the `{key, issuer_name, first_detected, evidence}` schema for `review_pending_days` evaluation; (c) `[alarm_defaults.<class>]` config tables + `effective_alarms()` are the alarm read API; (d) the download-quarantine list lives in `data/config/source_state/<source>.json` and the register renders its count. Also record there that advisory refresh-PR-body wiring (AC 6's second surface) is Lane B's consumption of D7's `render_advisory_section()`.
4. Update the spec header status line (signed, merged as PR #129) and SESSION-HANDOFF.md in this session's PR.

---

## D0: Spike (s7.1). First implementation task, before any adapter code.

**Goal:** All seven burn-downs of spec s7.1 answered with recorded evidence on TEA-1035, or a STOP-and-report naming what is blocked. Timebox one session.

**Executor:** Claude Code, Opus 4.8 max. Browser tooling allowed for observation; plain HTTP fetches for anything the adapter would later do (no bot-wall circumvention, no Selenium in any recorded mechanism).

**Files:**
- Create: `docs/superpowers/specs/2026-07-19-dublin-spike-findings.md` (evidence per burn-down: request shapes, response excerpts, native_id candidate, URL templates, volume counts, date-field semantics)
- Create: `docs/sources.md` Dublin section DRAFT inside the findings doc (the committed `docs/sources.md` section itself lands in D2's file; the spike PR carries the drafted line + terms-page link + date + "pending Teal confirmation" marker, and D9 may not merge until Teal has confirmed it)

**The seven burn-downs are spec s7.1 items 1-7 verbatim.** Answer every one with evidence, including:
- Burn-down 1: whether the bulk-download endpoint (`/en/markets/dublin/bonds/list/download?product_data=`) returns the full securities directory to a plain scripted request; if not, capture the ONE data endpoint behind the `#dublin-issuer-list` widget. A headless-browser requirement is a STOP-and-report.
- Burn-down 2: issuer/security row to document PDFs; the stable `native_id` candidate; S3 URL shape; metadata fields; confirm S3 fetch from a datacenter-shaped client.
- Burn-down 3: DOL URL/date behavior (weekends, publication hour, the observed 403-for-one-date), required headers, hosted-runner access; if DOL stays brittle, the fallback is the daily directory diff and say so explicitly.
- Burn-down 4: which date the metadata carries (document date vs venue posting date), recorded explicitly.
- Burn-down 5: `govbonds/list` one look.
- Burn-down 6: volume bound for two allowlist-shaped issuers (one sovereign, one sukuk SPV).
- Burn-down 7: ToS read; draft the one-line conclusion; flag anything constraining public rehosting.

**Decision output (feeds D9):** the incremental signal choice (DOL parse vs directory diff) with rationale, the native_id definition, and the discovery mechanism (bulk endpoint vs data endpoint), each stated as a single unambiguous sentence in the findings doc under a "Decisions for the adapter" heading.

**DoD:** findings doc committed on branch `lte/tea-1035-d0-spike`; all seven burn-downs answered with evidence or an explicit STOP; decisions section present; comment on TEA-1035 summarizing all seven answers with a pointer to the doc; metrics line.

**Stop-and-report:** the documents tab needs a real browser (spec risk 2); the directory has no scriptable endpoint; ToS reads as prohibiting the corpus's use (park is an acceptable conclusion, per spec s9's SGX language).

---

## D1: PDIP hash backfill (precondition branch; runs BEFORE the Dublin backfill and before D7's audit run)

**Goal:** Every PDIP document row with an on-disk original carries `file_hash`; rows whose originals are genuinely absent are listed, not silently skipped (AC 16). Today: pdip 0/823 hashed (spec s5.8).

**Executor:** Codex, reasoning high.

**Files:**
- Create: `scripts/backfill_pdip_hashes.py`
- Create: `tests/test_backfill_pdip_hashes.py`
- Create: `docs/coverage/pdip-hash-backfill-2026-07.md` (the run report; D7's audit references it)

**Design:** Resolve each PDIP row's original from the DB `file_path` value (legacy paths predate ratified decision 7 and contain country directories; resolve relative to the repo data root, tolerating both absolute legacy values and relative values). For each resolved file: stream SHA-256 (64 KB chunks), `UPDATE documents SET file_hash = ? WHERE document_id = ?`. Missing files go to the absent list with their storage_key and recorded path. The `documents` table has NO `file_size_bytes` column today (chair-verified): do not record sizes and do not add columns; this branch touches exactly one column. Idempotent: rows with non-null `file_hash` are skipped on re-run.

**Interfaces:**
- Produces: `resolve_pdip_original(file_path: str, data_root: Path) -> Path | None` and `backfill_hashes(conn, data_root, dry_run: bool) -> BackfillReport` (dataclass: `hashed: int, skipped_existing: int, absent: list[tuple[str, str]]`), both importable from the script for tests.
- Consumes: nothing from other branches.

**Tasks:**
- [ ] 1. Tests first: path resolution (country-dir legacy path resolves; absolute legacy path under a different HOME resolves by suffix match under `data/original`; missing file returns None); backfill on a fixture DuckDB (three rows: one hashable, one already-hashed, one absent) asserting counts and that the absent row's hash stays NULL. Run, red.
- [ ] 2. Implement; tests green; commit.
- [ ] 3. Mount `data/` per the global constraint and run the identity guard; dry-run against the rehearsal copy (`/tmp/corpus-rehearsal-d1.duckdb`); eyeball counts (expect ~823 candidates); then the REAL RUN against `data/db/corpus.duckdb` with the JSONL logging pattern (run id `pdip-hash-backfill-<date>`). Commit the report doc with: hashed count, absent list, the coverage query and its output:
  `SELECT source, count(*) FILTER (WHERE file_hash IS NULL) AS missing, count(*) AS total FROM documents GROUP BY source ORDER BY source;`
  Expected: pdip missing == absent-list length, every other source unchanged.
- [ ] 4. Full CI suite; handoff comment on TEA-1035 with the counts; metrics line.

**Edge cases:** duplicate file_path values across PDIP rows (hash both; report notes it); zero-byte file (hash it, flag in report); file present but unreadable (absent list with reason).

**DoD:** coverage query shows pdip missing == absent count (target: absent list is short; if more than ~5% of 823 are absent, stop and report before the real run); report committed; tests green; re-run is a no-op (proven in the report).

**Out of scope:** fixing PDIP ingest generally (issue #66 stays open; reference it in the PR body); touching manifests.

**Stop-and-report:** more than ~5% of originals unresolvable; any hash collision with an existing non-PDIP row surfacing mid-run (do not attach anything; that is D7's mechanism, not this branch's).

---

## D2: Adapter contract core (registry + types + runner + toysource + contract suite + ToS gate). THE L BRANCH.

**Goal:** Spec s5.1-5.7 and s5.9-5.13 exist in code with the toysource proving AC 1 end to end: a new source is one module + one config block + one ToS section + fixtures, zero edits elsewhere.

**Executor:** Claude Code, Fable 5 xhigh.

**Files:**
- Create: `src/corpus/sources/base.py` (protocol + types + status vocabulary)
- Create: `src/corpus/sources/registry.py`
- Create: `src/corpus/sources/runner.py`
- Create: `tests/sources/__init__.py`, `tests/sources/test_contract.py`, `tests/sources/test_registry.py`, `tests/sources/test_runner.py`
- Create: `tests/fixtures/toy_sources/__init__.py`, `tests/fixtures/toy_sources/toysource.py`, plus its discovery/download fixtures under `tests/fixtures/toy_sources/data/` and a fixture ToS doc `tests/fixtures/toy_sources/sources.md`
- Create: `docs/sources.md` (five existing sources' one-line ToS conclusions, drafted from primary terms pages with links and dates, marked "wording pending Teal confirmation at PR review"; Dublin's section arrives from D0's draft when D9 ships)
- Modify: `config.toml` (active_sources, per-source descriptor fields, alarm_defaults, dormant `[esma]` block)
- Modify: `src/corpus/cli.py` (generic `corpus discover <source>` / `corpus download <source>` subcommand construction from the registry for TIER A sources only in this branch; `corpus source list`; existing legacy commands untouched until D3)

**Config (append to existing blocks; exact keys, spec s5.1):** every source block gains `display_name`, `cadence_class`, `execution_venue`, `feed_routing`, `scheduled`, `adapter_status` (default "active"; lse "pending"), `tier` ("a" | "b", DEFAULT "a" when absent; the four legacy blocks set "b" explicitly; pending/planned descriptors omit it and validation ignores it since they never import), `landing_url` (D2 SETS real values for all five registered names, drafted and cited; D5 curl-200 VERIFIES and corrects with a note). Spec s6 assignments verbatim: nsm active-feed/true, edgar active-feed/true, luxse active-feed/false, pdip archive/true, lse pending. **Tiered validation (council):** `Registry.load()` protocol-validates tier "a" active sources at startup; tier "b" sources are importability-checked ONLY in this branch (their protocol shims do not exist until D3; D3 tightens tier-b validation to shim shape). Without this, `corpus source list` could not boot against the real config. The `[lse]` block, verbatim (no `[lse]` exists in config.toml today, chair-verified):

```toml
[lse]
display_name = "London Stock Exchange (RNS)"
cadence_class = "active-feed"
execution_venue = "gha"
feed_routing = "new-feed-eligible"
scheduled = false
adapter_status = "pending"   # TEA-1008 flips to active with an ordinary adapter build
landing_url = "https://www.londonstockexchange.com/news"
# tier omitted deliberately: pending never imports, and tier defaults to "a"
```

(Executor verifies the LSE landing_url resolves; if not, substitute the RNS news-explorer landing page and note it.) Add:

```toml
[corpus]
active_sources = ["nsm", "edgar", "pdip", "luxse", "lse"]

[alarm_defaults.active-feed]
discovery_stale_days = 3
zero_finds_days = 21

[alarm_defaults.archive]
discovery_stale_days = 10

[alarm_defaults.feeder-staged]
incoming_age_days = 7

[esma]
display_name = "ESMA Prospectus Register (PRIII)"
cadence_class = "archive"
execution_venue = "gha"
feed_routing = "archive-only"
scheduled = false
adapter_status = "planned"
```

(`dublin` joins `active_sources` in D9. The `[esma]` block is dormant: NOT in active_sources, never registry-resolved, never shown by `corpus source list`; it exists so AC 12's "config values exist and the ESMA descriptor is locked archive-only" is a config test. `adapter_status` is the closed enum `{active, pending, planned}`: the spec names active/pending; "planned" is a plan-level extension for catalogued-without-holdings sources, flagged for Teal in the PR. `[pdip_annotations]` is not a source and is untouched.)

**Interfaces (later branches rely on these exact names):**
- `base.py` produces: `SourceAdapter` (Protocol, spec s5.1 verbatim: `name`, `discover(ctx) -> DiscoveryResult`, `fetch(record, ctx) -> FetchResult`, `source_page(record) -> tuple[str | None, str]`, `incremental: IncrementalSpec`); `DocRecord` (TypedDict, spec s5.1 field list verbatim); `DiscoveryContext` (dataclass: `http`, `config: dict`, `mode: Literal["incremental","full"]`, `since: str | None`, `state_dir: Path`, `reference: ReferenceData`); `DiscoveryResult` (dataclass: `records: list[DocRecord]`, `stats: dict`, `watermark: str | None`, `outcome: Literal["ok","partial","failed"]`, `notes: str`); `FetchContext` (dataclass: `http`, `config: dict`); `FetchResult` (dataclass: `status: str`, `content: bytes | Iterator[bytes] | None`, `ext: str | None`); `IncrementalSpec` (dataclass: `signal: str`, `supports_since: bool`, `reconcile: str`); `STATUS_VOCABULARY: frozenset[str]` (the closed s5.1 set, verbatim).
- `registry.py` produces: `CliOption` (dataclass: `param, type, default, help, multiple, phase`); `SourceDescriptor` (dataclass: `name, display_name, cadence_class, execution_venue, feed_routing, scheduled, adapter_status: Literal["active","pending","planned"], tier: Literal["a","b"], landing_url, alarms: dict, cli_options: list[CliOption], raw: dict`); `Registry` with `Registry.load(config: dict, packages: Sequence[str] = ("corpus.sources",)) -> Registry`, `.descriptors -> list[SourceDescriptor]` (config order = display order), `.get(name) -> SourceDescriptor`, `.adapter(name) -> SourceAdapter` (import `<package>.<name>`; full protocol validation for `adapter_status == "active"` AND `tier == "a"`; tier "b" importability-only until D3 tightens; "pending" never imports); `effective_alarms(descriptor, config) -> dict` (class defaults overlaid with `[<source>.alarms]`, plus `exempt: true` when `scheduled` is false); `ReferenceData` with `ReferenceData.table(name: str) -> polars.DataFrame` (read-only loader over `src/corpus/reference/data/<name>.csv`, KeyError on unknown name; this is how D9 reaches `dublin_issuers.csv` with zero D2 edits, the s5.13 bar).
- `runner.py` produces: `run_discovery(descriptor, adapter, ctx, out_dir, run_id) -> DiscoveryResult` (persists DocRecord JSONL + envelope `<source>_discovery.meta.json` with run id, window, mode, outcome, stats, candidate watermark, staged-state refs, and the SHA-256 of the JSONL); `run_download(descriptor, adapter, records, ctx, run_id) -> dict` (Tier A path: existence via recorded manifests + `documents.storage_key` in this branch, with the `document_listings` leg added by D7 through an injectable skip-set provider, stated so nobody drops it silently; content validation `%PDF` for pdf ext and non-empty for html/txt; hashing; safe_write; manifest append with relative `file_path` + `file_hash`; telemetry with real statuses; breaker on failures never skips; `rate_limit_sleep` + one same-record retry); `load_bound_discovery(source, discovery_file) -> tuple[list[DocRecord], Envelope]` (validates run id + digest, refuses a mismatched pair); `advance_watermark(source, envelope, download_stats) -> bool` (advances and promotes staged state only together, only when every window record is terminal non-failure, three-strike download-quarantine list persisted INSIDE the pointer file under a `download_quarantine` key so it rides the state revision, atomic rename of `data/config/source_state/<source>.json`; `partial` never advances).
- **Review-lane channel (council, 2-seat convergent; supersedes any live-state write):** review-lane items are part of the STAGED state tree, honoring spec s5.2's read-only rule: during discovery the adapter reads the live `review_lane.jsonl` (read-only, for date stability), merges append-if-absent keyed on normalized issuer key, and writes the merged file to `state_dir/staged/<run-id>/review_lane.jsonl`; promotion via the atomic pointer rename carries it. Schema per item: `{key, issuer_name, first_detected, evidence}`. A partial run therefore never changes the live review lane (register discipline holds). The Tier A no-write contract assertion is scoped accordingly: adapters write NOTHING outside `state_dir/staged/<run-id>/`.
- Consumes: nothing from other branches. `toysource.py` implements the full protocol against local fixtures with at least one record that yields each terminal status.

**Contract suite (`tests/sources/test_contract.py`, parametrized over the registry, tier-aware per s5.12):** discovery fixtures parse to schema-valid DocRecords; stats complete (available vs captured); status vocabulary respected at the reporting boundary; breaker fires and skips never count; `source_page()` URL carries no credential or expiry query material (assert no `Expires=`, `Signature=`, `X-Amz-`, `token=` in query); `file_hash` non-null on every ingested record; ToS section present for every registered source (docs path is a test parameter; toysource points at its fixture doc); envelope digest binding (download refuses a tampered JSONL); watermark advancement rules (green advances; one failed record blocks; partial never advances; three-strike quarantine unblocks); `adapter_status="pending"` rows are listed, never imported, never schedulable; venue flip gha/feeder leaves discover/fetch behavior identical (AC 13); alarm config assertions (AC 11: class defaults match the s5.7 table, per-source override wins, unscheduled exemption, archive zero-finds exemption); ESMA descriptor locked archive-only (AC 12 config half). Tier A runner assertions (no adapter writes, no adapter sleeps, hash-keyed skips) run against toysource now, Dublin when D9 lands; Tier B assertions arrive with D3.

**Tasks (TDD order; commit at each green):**
- [ ] 1. `base.py` types + status vocabulary with schema-validation tests for DocRecord (valid record passes; missing required key fails; countries list shape matches `_insert_countries` expectations chair-verified in the spec).
- [ ] 2. `registry.py` + tests: loads the six-name active list from a config dict; package-list injection resolves toysource from `tests.fixtures.toy_sources`; pending never imports; unknown name fails at startup with a clear error; display order preserved; `effective_alarms` table-driven test against the s5.7 table.
- [ ] 3. `runner.py` discovery half + envelope + state pointer: fixture adapter, tmp dirs; digest binding test (tamper the JSONL, expect refusal); watermark advancement matrix test (green / one-failed / partial / three-strike).
- [ ] 4. `runner.py` download half: statuses, breaker, rate-limit retry, disk-present-manifest-absent repair (bytes on disk, no manifest record: runner hashes, appends, reports `skipped_exists` with repair note).
- [ ] 5. `toysource.py` + fixtures; generic CLI construction for Tier A sources + `corpus source list` (prints name, cadence, venue, scheduled, routing, adapter status, ToS present yes/no); the AC 1 test: run the real CLI (`CliRunner`) end to end discover then download then ingest against fixtures, asserting zero edits outside the toysource module + config + ToS fixture.
- [ ] 6. `docs/sources.md` with the five existing sources' sections (each: one-line conclusion, date, "concluded by: D2 executor draft, pending Teal confirmation", terms-page link); wire the ToS contract test at the real docs path for real sources. The PR body EXPLICITLY requests Teal's wording confirmation; markers drop in this PR if Teal confirms during review, else clearing them is D11's named close-out check (the s14 "Teal-confirmed" line must not silently pass).
- [ ] 7. Full CI suite + an end-to-end smoke: `uv run corpus source list` against the real config prints FIVE rows (nsm, edgar, pdip, luxse active tier-b + lse pending; dormant esma never prints; toysource exists only under tests). PR body records issue relationships: whether the toysource end-to-end fixture path satisfies #6 (close or overlap, say which) and that #18's Tier B debt (absolute paths, empty discovery on error) stays open until tier migration. Handoff + metrics line.

**Edge cases:** config block missing a descriptor key (fail at startup, name the key); `active_sources` naming a section that does not exist (fail at startup); toysource fixture package must not ship in the wheel (it lives under tests/, never `src/`); NSM's `delay_api`/`delay_download` split survives untouched in `raw` (the parity matrix in D3 owns translation; the descriptor does not force a generic `delay`).

**DoD:** AC 1 test green; contract suite green for toysource and (shape/ToS/registry rows only) the four legacy names + lse; `corpus source list` works against the real config; docs/sources.md complete for five sources; all CI checks green; no legacy download/discover behavior changed (their commands untouched this branch).

**Out of scope:** legacy shims and the generic dispatch of legacy sources (D3); dedup (D7); any snapshot change (D4/D5/D6); refresh.yml or any Lane B evaluation.

**Stop-and-report:** the protocol cannot express something a legacy source's shim will need (check s6 before working around); Click cannot build subcommands from the registry at import time without breaking existing commands.

---

## D3: Tier B shims + generic dispatch + parity matrix + live smoke + LuxSE mini-spike

**Goal:** The four legacy adapters become Tier B citizens of the registry (spec s6): protocol shims for discover/source_page/incremental, `legacy_batch` retrieval via `to_legacy_records()`, generic CLI dispatch replacing the four near-identical command bodies, an explicit parity matrix locked by new parity tests, and a live smoke proving the moved production paths.

**Executor:** Codex, reasoning high. After D2 merges.

**Files:**
- Modify: `src/corpus/sources/{nsm,edgar,pdip,luxse}.py` (shim classes + `to_legacy_records()`; `run_*` bodies accept records instead of re-reading files, the three-line refactor the spec names)
- Modify: `src/corpus/sources/base.py` (the `LegacyShim` protocol addition; append seam shared with D2's types, append at end)
- Modify: `src/corpus/sources/registry.py` (tighten tier "b" validation from importability-only to shim shape, removing D2's temporary deferral)
- Modify: `config.toml` (the `[<source>.cli_options]` declarations this branch introduces: NSM `--reference-csv`, EDGAR `--tiers`, discover `--output`; hardcoding them in cli.py would violate the new-source bar)
- Modify: `src/corpus/cli.py` (legacy discover/download subcommands now built from the registry with the declared `cli_options` plus the existing shared flags; abort exit codes preserved exactly: nsm/edgar exit 0 with warning, pdip/luxse exit 1)
- Modify: `src/corpus/sources/provenance.py` (thin dispatcher over the registry; legacy functions kept)
- Create: `docs/parity-matrix-sources.md` (flags and defaults per source, NSM delay split vs generic delay, EDGAR CONTACT_EMAIL User-Agent plumbing and 660s rate-limit sleep, exit codes, stats-key translation table, status translation table: `no_pdf_link -> skipped_no_document`, `failed_invalid_pdf -> failed_invalid_content`, and every other legacy status observed in the four modules)
- Create: `tests/sources/test_parity.py` (locks the matrix: option inventory per command via Click introspection, defaults, exit codes on simulated abort, status translation at the reporting boundary)
- Modify: `tests/sources/test_contract.py` (Tier B rows join: shim shape, provenance, ToS, registry membership, boundary status vocabulary, exactly-one-retrieval-path assertion; the suite drives the ACTUAL persisted generic DocRecord file through each legacy dispatch on fixtures)
- Modify: `tests/test_cli.py` and per-source tests (assertions updated deliberately where stats keys unify; manifest FORMAT unchanged)

**Interfaces:**
- Consumes from D2: `Registry`, `base.py` types, `run_discovery`, `load_bound_discovery`.
- Produces: `LegacyShim` protocol addition in `base.py` (`legacy_batch(ctx, records) -> dict`), each legacy module's `to_legacy_records(records: list[DocRecord]) -> list[<legacy shape>]`, and `IncrementalSpec(supports_since=False)` on all four shims (`--mode incremental` runs full with a logged notice, never an error).
- LuxSE mini-spike output: a short section in the PR body + a line in `docs/parity-matrix-sources.md`: does a stable per-document page scheme exist on luxse.com? If yes: mint a follow-up GitHub issue for a LuxSE resolver + provenance backfill and reference issue #93; if no: record landing-page fallback as the end state, issue #93's link-check stays open.

**Tasks:**
- [ ] 1. Read all four legacy modules end to end; write the parity matrix doc FIRST (it is the spec for this branch's tests); commit it.
- [ ] 2. Parity tests red, then shims + `to_legacy_records()` + run-body refactors until green, one source per commit (order: pdip, nsm, edgar, luxse).
- [ ] 3. Generic dispatch in cli.py behind the registry; delete the four per-source command bodies only after the parity suite passes against the generic ones; legacy discovery-file formats declared void (regeneration is cheap; the generic download reads the new format only, spec s5.2).
- [ ] 4. Contract suite Tier B rows green.
- [ ] 5. LIVE SMOKE (DoD-blocking, spec s14): mount `data/` per the global constraint and run the identity guard FIRST (Tier B skips are disk-keyed; an empty worktree would re-download the window instead of skipping). Then run ONE migrated source's discover + download for real, smallest first (`uv run corpus discover nsm ...` then `uv run corpus download nsm ...` with a current window). Expected: mass `skipped_exists`, zero new downloads unless the source genuinely has new filings, manifests unchanged in format. Paste the stats block into the PR body.
- [ ] 6. LuxSE mini-spike (timebox ~30 min): probe 3 known LuxSE docs for a stable per-document page URL scheme; record the disposition.
- [ ] 7. Full CI + handoff + metrics.

**Edge cases:** NSM discovery stores raw `_source` dicts (lesson 6) and PDIP rows are un-enriched: `to_legacy_records` owns the conversion, chair-verified as the format boundary; EDGAR's User-Agent from CONTACT_EMAIL must survive verbatim; `make download-all` chain behavior unchanged (exit codes).

**DoD:** parity tests + contract Tier B green; live smoke pasted; four command bodies collapsed; mini-spike dispositioned; all CI green; no manifest format change.

**Out of scope:** Tier A migration of any legacy source (EDGAR/NSM ride Lane B Stage 2, handed delta 4); implementing incremental for legacy sources; touching their internals beyond the named three-line run-body refactor.

**Stop-and-report:** any legacy behavior that cannot be preserved through the generic dispatch (name it in parity-matrix terms); the live smoke downloads something unexpected (abort, do not re-run, report).

---

## D4: Platform refactor 1: snapshot country from document_countries with obligor precedence (+ obligor role migration)

**Goal:** Spec s5.14 refactor 1 + AC 15: display country prefers the `obligor` role row, then `issuer`, then the legacy `ISSUER_TO_COUNTRY` map; no `document_countries` rows means byte-identical legacy behavior; the three LSE Congo rows flip from Unknown to Congo as the disclosed, audited delta. The `obligor` role value joins the vocabulary (spec s7.3).

**Executor:** Claude Code, Opus 4.8 max.

**Files:**
- Modify: `src/corpus/snapshot.py` (country resolution at the chair-verified sites: ISSUER_TO_COUNTRY usage at lines ~28/139/287)
- Modify: `sql/001_corpus.sql` (role comment becomes `issuer | guarantor | obligor | related`)
- Modify: `src/corpus/db/ingest.py` ONLY IF a role validation list exists there (chair-verified `_insert_countries` already consumes `{country_code, country_name, role}` lists; if no validation list exists, no ingest change)
- Create: `tests/test_snapshot_country.py`

**Interfaces:**
- Produces: `resolve_display_country(conn_row_or_struct) -> tuple[str | None, str | None]` (code, name) as a pure function over (document_countries rows for the doc, issuer_name), exact precedence: obligor row, else issuer row, else legacy map, else None/Unknown. D7's snapshot column work and D10's skeleton check consume the behavior, not the function.
- Consumes: nothing from other branches (lands in wave 1).

**Tasks:**
- [ ] 1. Fixture tests three ways (AC 15 verbatim): obligor+issuer rows prefer obligor; issuer-only row used; no rows fall back to legacy map byte-identically (assert against the current function's output for 3 real issuer names); Congo case: an LSE fixture row with document_countries issuer row resolves Congo.
- [ ] 2. Implement in snapshot.py. Mechanism pinned (council): ONE bulk query preloads `document_id -> list[(role, country_code, country_name)]` for all documents (a single `SELECT document_id, role, country_code, country_name FROM document_countries`), then resolution is a pure in-memory function; never a per-document query (roughly 10,000 round trips otherwise). Tests green; commit.
- [ ] 3. Role comment migration line in sql/001_corpus.sql; grep src/ for any hardcoded role enumeration and extend it; commit.
- [ ] 4. AUDITED DELTA RUN: mount `data/` per the global constraint, run the identity guard, then a local snapshot build to an alternate dir via the EXISTING flag (`uv run python scripts/build_snapshot.py --output-dir /tmp/snapshot-d4`; the flag exists with a partial-build guard, chair-verified); diff country fields vs the current snapshot: expected delta is EXACTLY the three LSE Congo rows. Paste the diff into the PR body. Do not touch `data/snapshot/`.
- [ ] 5. Full CI + handoff + metrics.

**Edge cases:** multiple obligor rows (deterministic pick: lowest country_code alphabetically, note in code comment); document_countries row with a code the name-map lacks (use the row's country_name; never invent).

**DoD:** three-way fixture tests green; delta run shows exactly the three disclosed rows changing; all CI green; issue #80 referenced in the PR body (this reduces the drift surface).

**Out of scope:** touching the legacy map's contents; snapshot filing_url (D5); any explorer change.

**Stop-and-report:** the delta run shows ANY row beyond the three disclosed Congo rows changing.

---

## D5: Platform refactor 2: filing_url landing-page fallback

**Goal:** Spec s5.14 refactor 2 + AC 14 snapshot half: for registry sources, `filing_url` resolves `source_page_url`, then the descriptor's `landing_url`, then `download_url`. LuxSE's 4,965 rows flip from dead signed URLs to the landing page: a deliberate, called-out data improvement.

**Executor:** Codex, reasoning high. After D2 merges (descriptors carry landing_url).

**Files:**
- Modify: `src/corpus/snapshot.py` (the COALESCE at the chair-verified line ~250)
- Modify: `config.toml` (real landing_url values for all registered sources, drafted and link-checked: each URL curl-200s at build time of this branch; cite each in the PR body)
- Create: `tests/test_snapshot_filing_url.py`

**Interfaces:**
- Consumes from D2: descriptor `landing_url`, read via `Registry.load()` + `.get(name).landing_url` (DECIDED, council: config-parsing bypasses would fork the platform read path; the registry is the one accessor). D2 set the values; this branch curl-200 VERIFIES each and corrects with a PR note where needed.
- Produces: the resolution rule other branches rely on implicitly (D10's skeleton checks a Dublin doc's filing_url resolves to a live.euronext.com page or the Dublin landing_url, never an S3 URL).

**Tasks:**
- [ ] 1. Fixture tests: source_page_url present wins; null source_page_url + registry source falls back to landing_url; both null falls back to download_url; NON-registry source (a name absent from active_sources, simulating an old snapshot row) keeps today's COALESCE behavior. Signed-URL guard: a download_url containing `Expires=` never becomes filing_url for a registry source. Red.
- [ ] 2. Implement; green; commit.
- [ ] 3. Delta audit against a DB copy to an alternate output dir: count filing_url changes by source. Expected: luxse ~4,965 changed to its landing page; other sources unchanged (edgar/nsm/pdip have source_page_url via provenance). Paste counts into the PR body; reference issue #93.
- [ ] 4. Full CI + handoff + metrics.

**Edge cases:** LSE (adapter pending, 3 docs): registered, so the rule applies; verify its landing_url is sane; PDIP (issue #92: source pages point at the generic search page) is explicitly NOT fixed here.

**DoD:** tests green; delta counts pasted and match expectation; every landing_url curl-200 verified; CI green.

**Out of scope:** LuxSE per-document resolver (D3's mini-spike owns the disposition); provenance.py changes (D3).

**Stop-and-report:** delta shows edgar/nsm/pdip rows changing.

---

## D6: Platform refactor 3: parquet additive-within-version policy reconciliation

**Goal:** Spec s5.14 refactor 3 + AC 20: the snapshot producer's version-policy comment states the ratified additive-within-version contract; SCHEMA_VERSION stays 1; a fixture test in explorer-web proves the deployed client path reads a version-1 parquet CARRYING an extra column.

**Executor:** Codex, reasoning high. Wave 1 (independent).

**Files:**
- Modify: `src/corpus/snapshot.py` (the SCHEMA_VERSION comment block only; no behavior change)
- Create: `explorer-web/tests/fixtures/snapshot-extra-column/documents.parquet` (a copy of the existing fixture parquet with one added VARCHAR column `duplicate_of`, generated by a committed script step, not by hand)
- Create or extend: `explorer-web/tests/unit/snapshot-extra-column.test.ts` (through the same code path the deployed client uses: snapshot-client + a DuckDB-WASM query selecting the named standard columns from the widened parquet; asserts normal reads and that the unknown column is invisible to named-column selection)
- Possibly modify: `explorer-web/scripts/make_fixture.py` or a small `explorer-web/scripts/widen_fixture_parquet.py` (whichever is lighter; committed either way)

**Interfaces:**
- Consumes: nothing from other branches. D7's additive `duplicate_of` column RELIES on this landing first (merge order).
- Produces: the reconciled producer comment text (verbatim): `Schema versioning: columns are additive-only within a schema version; consumers select named columns and MUST tolerate unknown columns. Bump SCHEMA_VERSION only for breaking shape changes (column removal, rename, or type change), per the ratified parquet-as-API contract.`

**Tasks:**
- [ ] 1. Fixture generation step + the vitest red (fixture absent), then generate, then green: client hard-check `SUPPORTED_SCHEMA_VERSION = 1` still passes against MANIFEST, standard queries return identical rows on the widened parquet.
- [ ] 2. Producer comment rewrite; commit.
- [ ] 3. `npm test` in explorer-web + `npx astro check` + repo CI (Python untouched but run it anyway); handoff + metrics.

**Edge cases:** the fixture widening must not disturb row order or types of existing columns (assert equality of the standard-column projection between original and widened fixture in the test).

**DoD:** AC 20 demonstrated by the green fixture test; comment states the additive-within-version policy; both test suites green.

**Out of scope:** actually adding `duplicate_of` to the producer (D7); any UI change; MANIFEST changes.

**Stop-and-report:** the deployed client path genuinely fails on the widened parquet (that would falsify the ratified contract's assumption; escalate to the architect, do not patch the client).

---

## D7: The dedup pass + one-time cross-source audit. THE OTHER L BRANCH.

**Goal:** Spec s5.8 in full: `document_listings`, transactional document+original-listing insert, the ingest attach rule (root eligibility, basis integrity, suppressed handling with the P2 idempotency third leg), batch anti-join lookup, deterministic ordering, near-dup advisory over the pilot tables with final_terms-only suppression, committed decisions file + idempotent `corpus dedup apply` with its refusal set, the shared fixed-point equivalence-class query, the additive snapshot `duplicate_of` column, and the committed one-time audit report. ACs 3, 4, 5, 6, 7, 18.

**Executor:** Claude Code, Fable 5 xhigh. After D6 merges; the audit RUN task additionally waits for D1 to merge.

**Files:**
- Modify: `sql/001_corpus.sql`: append the spec s5.8 `document_listings` DDL in the FILE'S IDEMPOTENT CONVENTION (Codex PR-130 P2: the spec block reads `CREATE TABLE`, but 001_corpus.sql is applied repeatedly, so write `CREATE SEQUENCE IF NOT EXISTS document_listings_seq;` FIRST, then `CREATE TABLE IF NOT EXISTS document_listings (...)` with the spec's columns verbatim) and the additive columns:
  `ALTER TABLE documents ADD COLUMN IF NOT EXISTS duplicate_of_document_id INTEGER;`
  `ALTER TABLE documents ADD COLUMN IF NOT EXISTS suppressed_at TIMESTAMP;`
- Create: `src/corpus/db/dedup.py` (all dedup logic; ingest calls into it)
- Modify: `src/corpus/db/ingest.py` (skip set becomes documents UNION listings UNION suppression records; insert becomes one explicit transaction with the original listing; attach path calls dedup)
- Create: `src/corpus/db/suppression.py` OR fold into dedup.py (executor's call; one place only): the durable suppression-record store
- Create: `docs/coverage/dedup-decisions.jsonl` (empty, committed) + `docs/coverage/README.md` (one paragraph: file format per spec s5.8, append-only, dispositions batched)
- Create: `scripts/duplicate_audit.py` (writes `docs/coverage/duplicate-audit-<date>.md`)
- Modify: `src/corpus/cli.py` (`corpus dedup apply`, `corpus dedup audit`)
- Modify: `src/corpus/snapshot.py` (emit additive `duplicate_of` slug column, null for non-demoted rows; SCHEMA_VERSION stays 1 per D6)
- Create: `tests/test_dedup.py`, `tests/test_dedup_apply.py`, `tests/test_dedup_advisory.py`
- Modify: `tests/sources/test_contract.py` (spec s5.12 places dedup attach + idempotent re-ingest IN the contract suite: parametrized fixture-hash-collision cases run through every registered source's ingest path)
- Modify: `src/corpus/sources/runner.py` (the skip-set provider gains its `document_listings` leg, completing D2's declared deferral)
- Backfill migration (in dedup.py, invoked once by a migration entry point): every existing non-demoted document gains its `original` listing via one INSERT..SELECT transaction batch. REHEARSAL-ONLY in this branch (council): the real-DB migration + backfill execute as D10's task 0, after this branch clears its review gate; a new table plus a ~9.8k-row backfill is not a pre-gate mutation (contrast D1's single-column precedent).

**Design pins the spec leaves open (council-reviewed):**
- **Suppression authority (council, 2-seat convergent; one truth, projected):** the CANONICAL suppression authority is the platform's suppressions ledger (`state/suppressions.jsonl` + monotonic epoch, Lane B's signed spec). This build's `documents.suppressed_at` column is an explicitly SYNCHRONIZED PROJECTION of that ledger: the local predicate ingest reads (`suppressed_at IS NOT NULL`), never an independent truth. D7 ships `apply_suppressions(conn, ledger_records) -> int` (idempotent upsert of the projection from ledger entries) so takedown.yml has a ready sync call; the handed obligation (recorded on TEA-1042 by the architect) is that takedown.yml applies ledger and projection in the same commit. Nothing in this batch suppresses anything outside tests; tests exercise the projection via `apply_suppressions` on fixture ledgers.
- **Suppression records (the P2 mechanism):** table `suppression_records (storage_key VARCHAR PRIMARY KEY, file_hash VARCHAR NOT NULL, suppressed_target_storage_key VARCHAR NOT NULL, recorded_at TIMESTAMP DEFAULT current_timestamp)` in sql/001_corpus.sql. Ingest writes it when a hash match resolves to a suppressed root; the register's takedown section renders from it; its storage_key set is the skip set's third leg (spec s5.8 idempotency, AC 4). It is likewise a local projection (rebuildable from manifests + the ledger), not a second authority.
- **Advisory output:** `near_dup_advisories(conn, reference) -> list[Advisory]` (dataclass: `pair: tuple[str, str]`, `issuer_key: str`, `doc_class: str | None`, `confidence: Literal["normal","lower"]`, `isin_disjoint: bool`, `suppressed: bool`) plus `render_advisory_section(advisories) -> str` (markdown). Lane B wires it into refresh PR bodies later; `corpus dedup audit` includes the current advisory section now.
- **Equivalence class:** `equivalence_class(conn, storage_key) -> set[str]` (storage keys; fixed-point closure over duplicate_of edges both directions AND same-SHA-256 edges across documents and listings, spec s5.8). Shared: takedown.yml (Lane B) and tests both call it.

**Interfaces:**
- Consumes from D6: the additive-column policy (merge order only). Consumes reference tables from main (PR #128): `issuer_canonical.csv`, `doc_class_map.csv`, title rules via `src/corpus/reference/`.
- Produces for D9/D10: the attach behavior at ingest (Dublin needs zero dedup-specific code; its records flow through the same ingest path), `corpus dedup apply`, the audit script.

**Tasks (TDD; commit each green; rehearse every schema/data step on the DB copy first):**
- [ ] 1. Schema: DDL appended; migration idempotence test (apply 001_corpus.sql twice on a fresh tmp DB).
- [ ] 2. Original-listing invariant: transactional insert + backfill INSERT..SELECT; tests: fresh mint creates document + original listing atomically (crash between the two is impossible by transaction; simulate by asserting both-or-neither on a forced failure); backfill on a fixture DB gives every non-demoted document exactly one original listing (the DoD assertion query, spec s14).
- [ ] 3. Attach rule: fixture hash collisions per AC 3: match attaches exact-hash to oldest eligible root; demoted match resolves one hop with basis integrity (equal bytes exact-hash, different bytes curated); quarantined-only match mints normally; suppressed match attaches nothing, writes a suppression record, excluded from snapshot; metadata snapshot + transactional country merge; canonical fields never overwritten.
- [ ] 4. Idempotency + determinism (ACs 4, 5): re-ingest same manifest lines reports skipped_exists across all three skip-set legs, no double-attach, no UNIQUE violation, no re-recorded suppression; in-batch ordering ascending publication_date nulls last then storage_key, deterministic across re-runs; batch anti-join (no per-record point lookups; assert one query per batch via a query counter or plan inspection).
- [ ] 5. `dedup apply` (AC 7): whole-listing migration with basis re-derivation, duplicate_of set, row stays in_scope, re-apply no-op, refusal set (self-demotion, cycles, chains not naming the final canonical, canonical not in_scope or suppressed).
- [ ] 6. Advisory lane (AC 6): pilot-table soft key with raw-normalized fallback and class-relaxed lower-confidence pairs; suppression ONLY both-sides-final_terms + both-ISIN-sets-non-empty-and-disjoint; supplements annotate; dispositioned pairs silenced via the decisions file. Plus the register-counter test (AC 3 tail): a query-level test that an attached listing increments the attaching source's listings count and NOT its documents count. AC 6's register-section surface is demonstrated here via `render_advisory_section`; the refresh-PR-body surface is Lane B's consumption (recorded on TEA-1042), stated in the PR body so the AC's split ownership is explicit.
- [ ] 7. Equivalence class (AC 18): fixture graph with duplicate_of chain + unmerged same-hash peer + listings; closure reaches all; ingest-vs-suppressed test rides task 3.
- [ ] 8. Snapshot additive column: `duplicate_of` emitted (slug of the canonical) for demoted rows, null otherwise; snapshot fixture test; SCHEMA_VERSION untouched.
- [ ] 9. THE AUDIT RUN (needs D1 merged; rebase over it first so the report and hashes are present): mount `data/` per the global constraint, run the identity guard, rehearse `scripts/duplicate_audit.py` on the copy (`/tmp/corpus-rehearsal-d7.duckdb`), then run for real (READ-ONLY against the production DB): exact-hash clusters by source pair, counts, the five-plus cross-source clusters called out, PDIP-absent list referenced from D1's report. Commit `docs/coverage/duplicate-audit-2026-07.md`. No merging, no demotion: informational, forward-only.
- [ ] 10. Full CI + rehearsal evidence pasted into the PR: the invariant query AND the cardinality assertions (post-backfill listings count equals non-demoted documents count, roughly 9,795; documents count unchanged from pre-migration) from the REHEARSAL DB, so the proof cannot pass vacuously on an empty database. Handoff + metrics.

**Edge cases:** two identical-hash records in ONE batch (AC 5 ordering picks canonical; second attaches); a hash match where the incumbent lacks file_hash (not a match; hard key only sees hashed rows, spec s5.8); listing UNIQUE(source, native_id) collision on re-attach (skip set catches it first; a genuine conflict is a loud failure, not a silent update); decisions entry naming an unknown storage_key (apply refuses with a named error).

**DoD:** all listed ACs demonstrated by named tests; invariant query (every non-demoted, non-suppressed document has exactly one original listing) plus the cardinality assertions return clean on the migrated REHEARSAL DB (the real-DB run is D10 task 0, post-review-gate); audit report committed (read-only real-DB run); rehearsal-first noted in the PR; CI green.

**Out of scope:** takedown.yml and the takedown drill (Lane B, handed delta 5); browse hiding or any Lane A consumption of duplicate_of; retroactive merges; listing revalidation (handed delta 3).

**Stop-and-report:** the backfill rehearsal shows any existing document that would gain zero or two original listings; DuckDB transaction semantics prevent the document+listing atomic insert as designed; the audit run mutates anything (it must be read-only).

---

## D8: Dublin issuer allowlist sweep (review-then-commit reference data)

**Goal:** Spec s7.2: one full directory sweep enumerates issuers; a classification pass produces `src/corpus/reference/data/dublin_issuers.csv` with the exact spec columns; every SPV row hand-checked with a cover-page-cited obligor; proposed rows land across the three pilot tables plus Dublin doc_class_map rows. Teal's PR review is the governance gate.

**Executor:** Claude Code, Opus 4.8 max. After D0 dispositions the discovery mechanism.

**Files:**
- Create: `src/corpus/reference/data/dublin_issuers.csv` (columns verbatim from s7.2: issuer name as listed, normalized key, issuer_type sovereign|quasi-sovereign, incorporation_country, obligor_country, spv_of, status active|review|excluded, evidence note)
- Create: `scripts/dublin_allowlist_sweep.py` (the sweep, committed for reproducibility; uses the D0-recorded mechanism; polite delays)
- Modify: `src/corpus/reference/data/doc_class_map.csv` (+ title rules file if routing needs them): rows for every observed Dublin source code, `needs_review`/`unclassified` acceptable, never forced
- Modify: `src/corpus/reference/data/issuer_canonical.csv`, `issuer_entities.csv`, `issuer_entity_members.csv`: proposed rows (`status=proposed`), sukuk SPVs as DISTINCT entities linked via allowlist spv_of/obligor_country, never merged into the sovereign
- Create: `tests/test_dublin_allowlist.py` (schema validation: columns, enum values, spv_of implies obligor_country, every SPV row has a non-empty evidence note citing a cover page; normalized keys unique)

**Interfaces:**
- Consumes from D0: the directory discovery mechanism and volume bounds.
- Produces for D9: the committed allowlist (D9's crawl perimeter is exactly `status=active` rows) and the classification columns D9 copies into DocRecords (`issuer_type`, countries with obligor role from `obligor_country`).

**Tasks:**
- [ ] 1. Sweep script + run: enumerate the full directory (all letters); commit the raw sweep output as `docs/coverage/dublin-directory-sweep-2026-07.csv` (committed evidence, the audit-home convention; never under data/); commit script.
- [ ] 2. Classification pass: name heuristics + LLM assist for candidate typing; every SPV row hand-checked by fetching the actual prospectus cover page and citing the obligor in the evidence note (the Aramco-class trap is the test: sovereign-sounding corporate vehicles classify corporate and stay OUT). Sub-sovereigns: quasi-sovereign with obligor_country = their sovereign's code. Uncertain rows: `status=review`, never guessed active.
- [ ] 3. Pilot-table proposals + Dublin doc_class_map rows per the observed source codes.
- [ ] 4. Schema tests green; full CI; PR body carries the classification evidence summary (counts by type/status, the hand-check list) and states plainly: rows are proposed; Teal's review flips them (the pilots' governance gate); handoff + metrics.

**Edge cases:** issuers listed under multiple name spellings (one row per listed spelling, same normalized key); an issuer on `govbonds/list` absent from `bonds/list` (include, note provenance); zero sukuk SPVs found (say so; do not manufacture).

**DoD:** allowlist committed with every column populated per spec; all SPV rows evidence-cited; proposals in all three pilot tables; tests green; the PR is explicitly review-then-commit (merge waits for Teal).

**Out of scope:** crawling documents (D9); activating review-status issuers; editing approved pilot rows.

**Stop-and-report:** the sweep cannot enumerate the full directory with the D0 mechanism; classification confidence is low for a large fraction (report the fraction, do not guess).

---

## D9: Dublin adapter module (Tier A; merges scheduled=false)

**Goal:** `src/corpus/sources/dublin.py` implementing the full protocol against the D0-recorded mechanisms, within the D8 allowlist perimeter, passing the contract suite with recorded fixtures. Registration is not activation: `[dublin]` merges with `scheduled = false`.

**Executor:** Claude Code, Opus 4.8 max. After D2 + D3 + D8 all merge (D3 is a mandatory base, not an optional mid-branch rebase: D9 rides the generic dispatch and the tier-b-tightened registry).

**Files:**
- Create: `src/corpus/sources/dublin.py`
- Create: `tests/sources/test_dublin.py` + recorded fixtures under `tests/fixtures/dublin/`
- Modify: `config.toml` (the spec s5.1 `[dublin]` block verbatim, `scheduled = false`, plus `dublin` appended to `active_sources`)
- Modify: `docs/sources.md` (Dublin section from D0's Teal-confirmed draft)

**Interfaces:**
- Consumes: D2 protocol/runner/registry; D8 allowlist via `DiscoveryContext.reference`; D0 decisions (native_id, incremental signal, endpoints).
- Produces: DocRecords with `issuer_type` and `countries` from the allowlist (SPV paper: incorporation country role `issuer`, obligor sovereign role `obligor`); `source_page()` returning the live.euronext.com issuer/security page (`filing_index`), never the S3 object; `IncrementalSpec(signal="dublin-dol-or-directory-diff" per D0, supports_since=True, reconcile="weekly full directory sweep + full document re-list for allowlisted issuers")`; review-lane items for unknown sovereign-shaped issuers via the STAGED channel D2 pinned (read live `review_lane.jsonl` read-only, merge append-if-absent keyed on normalized name so `first_detected` stays stable, write the merged file to `state_dir/staged/<run-id>/review_lane.jsonl`; promotion carries it), spec s5.2 + s7.2 + AC 9. Never write live state.
- The five-artifact bar (spec s5.13): if this branch needs to edit cli.py, the runner, the snapshot builder, refresh anything, or the schema, THE CONTRACT FAILED: stop-and-report the defect rather than working around it.

**Tasks:**
- [ ] 1. Record fixtures from live responses (directory page/endpoint, one issuer's securities, one security's documents, one DOL or diff basis per D0's signal choice, one document HEAD/first-KB for `%PDF`).
- [ ] 2. TDD the adapter: discover full mode (allowlist-scoped, stats available-vs-captured per query, structured DiscoveryResult, staged directory snapshot to `state_dir/staged/<run-id>/`); discover incremental (signal-driven, cheap, review-lane flagging for unknown sovereign-shaped issuers, no crawl until allowlist active); fetch (S3 GET, ext, no writes, no sleeps: runner owns both); source_page (stable, no expiry material).
- [ ] 3. Contract suite picks Dublin up (registry-parametrized: zero test-file edits beyond the new per-source file); Tier A runner assertions now bind to a real source.
- [ ] 4. End-to-end fixture run through the REAL CLI: discover then download then ingest, envelope-bound, watermark advancing; `corpus source list` shows dublin enrolled-not-scheduled with ToS recorded.
- [ ] 5. Full CI + handoff + metrics. The PR body restates: zero edits outside the s5.13 artifact list (diff proves it).

**Edge cases:** an allowlisted issuer with zero documents (valid, stats say so); a security row with multiple ISINs (isins list per record, spec s7.3); a document listed under two securities of one issuer (one DocRecord, ISINs unioned; native_id keeps it single); unknown issuer_type at discovery time (record it as review-lane, never guess).

**DoD:** contract suite green including Dublin; AC 9's discovery/review-lane halves demonstrated on fixtures; the s5.13 zero-edit bar proven by the diff; `scheduled = false` in the merged config; docs/sources.md Dublin section Teal-confirmed (from D0) before merge; CI green.

**Out of scope:** the backfill run and the skeleton (D10); dedup code (D7 owns it; Dublin flows through ingest untouched); flipping scheduled.

**Stop-and-report:** any s5.13 bar violation; the D0-chosen signal fails on live data during fixture recording; S3 fetches blocked from this network (record the evidence; spec risk 3's venue flip is config, but that decision is the architect's).

---

## D10: Walking skeleton + executed Dublin backfill (operational branch)

**Goal:** Spec s13 executed with a real document and a real cross-source attestation, then the full Dublin backfill actually run (spec s14): counts by issuer_type and country, minted vs attested vs advisories (raised and suppressed) report, recorded run id, and the zero-cross-source-pairs STOP-and-assess check (AC 10).

**Executor:** Claude Code, Opus 4.8 max. After D1, D3, D4, D5, D6, D7, D9 all merged. Runs locally (Mac/Mini), politeness delay 1.0s, `caffeinate` for the long run.

**Files:**
- Create: `docs/coverage/dublin-backfill-2026-07.md` (the report)
- No product code. Any code fix discovered here routes back as a stop-and-report or a tiny PR against the owning branch's files, never a workaround inside this branch.

**The skeleton slice (spec s13 verbatim, executed in order):** one allowlisted issuer end to end: incremental signal fetched and parsed (or full-mode fallback if the signal is still under spike), documents discovered with native ids/ISINs/countries, PDFs fetched from S3 and validated, manifest written, ingest mints documents WITH original listings in one transaction, at least one real cross-source exact-hash pair attaches as a listing instead of a new document, re-running the same ingest is a clean no-op, the near-dup advisory section renders, `corpus source list` shows dublin enrolled-not-scheduled with ToS recorded, a local snapshot build (alternate output dir) serves the new document's text with country resolved from document_countries, and the duplicate audit report regenerates. **Attestation timing (council):** the cross-source-pair clause may legitimately close only after the backfill (nobody knows Dublin's hashes in advance); run the read-only overlap scout first, and if the scouted issuer yields no pair, the clause closes at task 3 on the backfill's first attested pair, with the skeleton assertion re-run there.

**Tasks:**
- [ ] 0. REAL-DB MIGRATION + LISTINGS BACKFILL (D7's rehearsed steps, executed post-gate): mount `data/` per the global constraint, run the identity guard, apply the canonical-state gate, take a dated backup copy of `corpus.duckdb`, apply the schema migration, run the original-listing backfill, and paste the invariant query + cardinality assertions (listings == non-demoted documents, roughly 9,795; documents count unchanged) into the report doc. Any violation is a STOP.
- [ ] 1. Read-only overlap scout, then the skeleton slice per above: pick the issuer whose Dublin holdings most plausibly overlap the post-D1 corpus (metadata-level: issuer + title + date against PDIP/LuxSE/EDGAR holdings; spec s7.4 names Dublin-vs-PDIP as the likelier pair). Every assertion pasted as command + output into the report doc; links on TEA-1035.
- [ ] 2. THE BACKFILL: full document crawl for every `active` allowlist issuer, breadth within the perimeter, run id `dublin-backfill-<date>`, circuit breaker armed, volume per D0 burn-down 6. Monitor via telemetry JSONL.
- [ ] 3. Report: counts by issuer_type and country; minted vs listings-attached vs advisories raised vs advisories suppressed-by-ISIN-disjointness; failure/quarantine list; the cross-source pair check. **If ZERO cross-source exact pairs: STOP-and-assess per spec s7.4: write the assessment section (what byte-identity under-detection means for the register's limitations language and the advisory volume), post it to TEA-1035, and DO NOT proceed to D11 or any scheduled=true talk until the architect/Teal disposition it.**
- [ ] 4. Idempotency proof: re-run the same ingest; paste the all-skipped stats.
- [ ] 5. Local snapshot build check (alternate dir): the new documents render with allowlist countries; spot-check one SPV document shows the obligor country.
- [ ] 6. Handoff + metrics; evidence links on TEA-1035.

**DoD:** every s13 skeleton clause demonstrated with pasted evidence; the real-DB migration + backfill evidence (task 0) pasted; backfill executed and reported. A ZERO-cross-source-pairs outcome leaves this branch BLOCKED and incomplete pending the architect/Teal disposition (AC 10 requires a real attestation; recording the stop is not DoD-complete). No product-code edits in the branch.

**Out of scope:** scheduled=true (a later config-only change after clean runs, spec s4); ESMA/SGX anything; publishing a new production snapshot.

**Stop-and-report:** breaker aborts the backfill (report the telemetry, do not loosen the breaker); any ingest defect surfaces (route to D7's owner path); volume wildly exceeds D0's bound.

---

## D11: How-to doc + ESMA/SGX paper re-check

**Goal:** `docs/how-to/add-a-source.md` written against the REAL Dublin build (spec s10's checklist: ToS gate first, spike shape, the five s5.13 artifacts, contract hooks with Dublin code pointers, fixture recording, contract suite, register/alarm declarations, dedup expectations, backfill etiquette, enrollment, ship checklist), plus the s14 DoD line: ESMA and SGX paper checks revisited post-Dublin, friction recorded or "holds as specified".

**Executor:** Claude Code, Opus 4.8 max. After D10.

**Files:**
- Create: `docs/how-to/add-a-source.md`
- No code.

**Tasks:**
- [ ] 1. Write the how-to with Dublin as the worked example end to end; every step cites the real Dublin artifact (file path or PR) that instantiates it; skim-test headings; BLUF.
- [ ] 2. Re-walk spec s8 (ESMA) and s9 (SGX) against the contract AS BUILT: any friction (a hook that did not exist, a config key that means something else now) recorded as an explicit delta list in the PR body; otherwise the sentence "holds as specified" with the checked items enumerated. The architect posts the outcome to TEA-1053 and TEA-1055.
- [ ] 3. CI (docs-only, run anyway) + handoff + metrics.

**DoD:** how-to merged, written from real artifacts (no hypothetical code blocks); paper re-check recorded; `docs/sources.md` carries ZERO "pending Teal confirmation" markers (the named close-out for spec s14's "Teal-confirmed" line: if any remain from D2/D9, obtain Teal's confirmation via the PR and clear them here); Lane C ingestion needs nothing (plain repo markdown).

**Stop-and-report:** the re-check finds contract friction that would change ESMA or SGX from config-plus-one-module (that is a pivot memo trigger, spec risk 11: architect decides, not this branch).

---

## Self-review against the spec (architect, pre-council)

- **DoD coverage (s14):** contract/registry/runner/shims/suite/toysource/parity D2+D3; three refactors D4/D5/D6; live smoke D3; sources.md D2 (+D0/D9 Dublin); spike D0; adapter+allowlist+obligor D9/D8/D4; skeleton+backfill D10; dedup live D7+D1; declarations consumed-or-testable D2; five seam deltas recorded: architect follow-through; how-to D11; paper re-check D11; metrics line: global constraint. No gap found.
- **AC coverage (s15):** 1 D2; 2 D2; 3-7 D7; 8 D2; 9 D9(+D10 evidence); 10 D10; 11 D2; 12 D2 (dormant `[esma]` block: an interpretation, flagged for council); 13 D2; 14 D2 (source_page test) + D5 (snapshot rule); 15 D4; 16 D1; 17 every branch; 18 D7; 19 D2; 20 D6.
- **Plan-level pins the spec leaves open (all council-reviewed, revised where the council found defects):** the `[esma]` dormant block with the `{active, pending, planned}` enum; `documents.suppressed_at` + `suppression_records` as synchronized projections of the platform's canonical suppressions ledger, with `apply_suppressions()` as the sync call; review-lane items in the STAGED state tree (`state_dir/staged/<run-id>/review_lane.jsonl`, promoted with the pointer); alarm defaults as `[alarm_defaults.<class>]` config tables; the descriptor `tier` field with tiered registry validation (tier-b importability-only in D2, shim-shape from D3); `ReferenceData.table()` as the reference-data accessor; the download-quarantine list inside the source-state pointer file.

## Council PLAN review disposition (chair: this session, 2026-07-19)

**Council as fielded:** Codex gpt-5.6-sol xhigh, read-only, mechanism/seams lens: **NOT SOUND** (4 CRITICAL, 7 IMPORTANT, 3 SUGGESTION). One fresh-context Claude external seat, consumer/executor-sufficiency lens: **SOUND WITH CHANGES** (2 CRITICAL, 6 IMPORTANT, 10 SUGGESTIONS). Same anonymized packet (spec + plan + prompts + repo read-only). Triage by convergence; every code-level claim chair-verified before edit.

**Convergent (both seats), all accepted:**
| Finding | Fix applied |
|---|---|
| Fresh worktrees contain no `data/`; DuckDB auto-creates a missing DB, so operational branches could vacuously pass their acceptance evidence against an empty corpus (Codex C3, Claude C2) | Data-mount global constraint (symlink from the canonical checkout + count identity guard, STOP on mismatch); echoed in D1/D3/D4/D7/D10 tasks and prompts |
| D9's live `state_dir/review_lane.jsonl` write violates spec s5.2's read-only discovery rule and the Tier A no-write assertion (Codex I5, Claude C1) | Review lane moved into the staged state tree, merged from live read-only, promoted atomically with the pointer; no-write assertion scoped to outside `staged/<run-id>/`; the DiscoveryResult-field alternative was not taken (no protocol change to the signed shape) |
| `suppressed_at`/`suppression_records` created a second suppression authority incompatible with Lane B's signed suppressions ledger; after a takedown, ingest could attach to taken-down bytes, breaking AC 18 (Codex C2, Claude I1) | Both pinned as synchronized PROJECTIONS of the canonical ledger; D7 ships `apply_suppressions()`; the ledger+projection same-commit obligation handed to Lane B on TEA-1042 |
| `corpus source list` row arithmetic wrong (six vs five) (Codex C1 tail, Claude I2) | Five rows; dormant esma never prints |
| D8's raw sweep artifact destination unnamed (Codex S13, Claude S6) | Pinned: `docs/coverage/dublin-directory-sweep-2026-07.csv` |

**Codex singletons, accepted (chair-verified):** C1 D2 cannot boot: registry protocol-validation of active legacy sources would fail before D3's shims exist (fix: descriptor `tier` field; tier-b importability-only validation in D2, tightened to shim shape in D3); C4 no canonical-state gate if Lane B's S3 cutover lands mid-batch (fix: global gate, STOP-and-report post-cutover rather than improvising the lock protocol); I6 s14/s15 coverage gaps (fixes: ToS Teal-confirmation named close-out in D2 PR + D11 DoD; seam deltas + pins posted to TEA-1042 NOW by the architect; D11's Linear record owned in the architect follow-through; dedup attach/idempotency added to the contract suite via D7; AC 6's split surfaces stated explicitly); I7 TEA-1035 sits Done while the build has not started (fix: architect reopens it In Progress; the mint-per-branch-issues alternative was not taken: the session mandate is a single-issue trail); I8 three weak dependency edges (fixes: D8 needs D0 MERGED; D7 rebases over D1 before the audit; D3 is a mandatory D9 base); I9 D10 skeleton could need a pair only the later backfill finds, and "recorded either way" under-enforced AC 10 (fixes: read-only overlap scout task; attestation clause may close post-backfill; zero pairs leaves D10 BLOCKED, not complete); I10 prompts not self-contained (fixes: `ReferenceData.table()` pinned; D5 must use the registry accessor; D3 file list gains config.toml for `cli_options`; enum pinned); I11 shared rehearsal DB path collides under the parallel schedule (fix: unique per-branch paths + no-writer check; real migrations post-gate); S12 D4 bulk mechanism pinned (one preload query, no N+1); S14 GitHub issue dispositions (#6 relationship recorded in D2's PR; #18 noted open for Tier B).

**Claude-seat singletons, accepted (chair-verified):** I3 LSE descriptor pinned verbatim (no `[lse]` block exists today) and the status enum stated; I4 `ReferenceData` shape pinned; I5 the runner skip-set's listings leg now explicitly lands in D7 (runner.py added to D7's files, injectable provider); I6 ToS confirmation gate (folded with Codex I6); S1 cardinality assertions added to D7/D10 evidence; S2 base.py added to D3's files; S4 landing_url ownership split (D2 sets, D5 verifies); S7 quarantine list home pinned (inside the source-state pointer); S8 D1's file_size_bytes phrasing corrected (column absent; do not add); S9 register-counter test named in D7; S10 D7's real-DB migration+backfill moved post-gate to D10 task 0 (convergent with Codex I11's tail).

**Refuted, with evidence:** Claude S3's first half claimed `make_fixture.py` lives at `explorer-web/tests/`; verified `ls`: it is at `explorer-web/scripts/make_fixture.py` and the plan's path stands. The same finding's second half (the snapshot `--output-dir` flag already exists with a partial-build guard) was verified correct and adopted in D4.

**Not adopted, with reasons:** minting per-branch Linear issues (Codex I7 alternative): the session mandate is a single-issue trail on TEA-1035, and reopening the issue resolves the board contradiction the finding targets. Adding a `review_items` field to DiscoveryResult (Claude C1 alternative): the staged-tree channel achieves the same isolation inside the signed protocol without amending a spec-fixed dataclass shape. Building the post-cutover lock/restore/upload flow into this batch (Codex C4's fuller remedy): that is Lane B's state machinery; the gate STOPs instead so the two lanes cannot silently diverge.
