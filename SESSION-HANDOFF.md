# SESSION-HANDOFF.md

**Last updated:** 2026-07-16 (coverage patch batch at final release gate)

## Session 2026-07-15/16: TEA-1003, TEA-1004, TEA-1005, and TEA-1006 release candidate

- **Canonical boundary cleared:** the `data/` symlink and Dropbox target were
  healthy. The earlier failure was the prior session's writable-root sandbox,
  not a filesystem or Dropbox defect. Atomic create/remove probes passed before
  any canonical mutation.
- **Canonical coverage promoted:** 8 Venezuela EDGAR documents with 590 pages,
  10 Bolivia LuxSE documents with 950 pages, and 3 Republic of Congo LSE
  documents with 539 pages. The database now has 9,795 documents and 176,968
  logical pages (`SUM(documents.page_count)`). Mapped counts are Venezuela 107,
  Bolivia 10, Republic of Congo 3, and
  Democratic Republic of the Congo 2.
- **Bolivia provenance repaired:** final exact discovery resolved issuer
  `29689`, returned the same 10 native IDs, and reconciled
  `issuer_resolution_method=exact_issuer_id` plus the queried issuer name into
  the canonical manifest and DuckDB rows.
- **TEA-1006 option a implemented:** only `luxse__2175370` and
  `luxse__2176190` receive the exact snapshot-level `BOLIVIAN` to `BOLIVARIAN`
  display/search correction. Canonical titles remain verbatim. The public
  snapshot carries nullable `raw_title` provenance, the detail page shows it
  when different, and CSV exports it without adding the raw typo to search.
- **TEA-1005 retrieved host-side:** official LSE/LSEG endpoints identified
  four issuance events and exposed three artifacts. All source ZIPs and PDFs
  were verified by hash, byte size, ZIP member identity, `%PDF`, PyMuPDF text,
  page count, issuer, ISIN, and event association before canonical ingest.
  XP53 had no artifact on the checked component, instrument-document, or
  programme API surfaces; this bounded result is not a claim of global
  nonexistence. Republic of Congo remains distinct from DRC.
- **Council corrections:** COG's official FY2027 World Bank lending category is
  `Blend`, not `IDA`; fresh EDGAR/LuxSE downloads are parser-validated before
  promotion; stale Markdown sidecars are removed on non-Markdown repair;
  configured exact LuxSE terms remain best effort in a normal broad run while
  explicit targeted runs fail closed; the one-off LSE helper pins the exact
  three artifacts/four events and preflights manifest conflicts.
- **Release state:** PR #126 is still draft and all four Linear issues remain In
  Progress until the single accepted snapshot, hosted data cutover, branded
  deploy, and target-specific live smoke pass. No accepted snapshot has yet
  been regenerated in this session.
- **Resume from here:** finish clean local gates and final review disposition,
  generate exactly one canonical snapshot, validate the 21-document delta and
  raw-title/search behavior, back up the hosted generation, deploy the
  backward-compatible candidate app before flipping data, run the full live
  acceptance matrix, then close the four issues, post one project status, and
  mark PR #126 ready.

## Session 2026-07-10 (latest): Stage 5 integration audit of the pre-Monday batch

- **Verdict:** the batch composed. Fresh-checkout suites all green (vitest
  163, astro check clean, two-origin smoke, pytest 471, production
  live-smoke 3/3); wrapper pin = corpus main; council seams (shared WHERE,
  active-text contract, frozen plain path) verified sound in code by four
  fresh-context reviewers plus chair spot-checks. Grades hold the A/A-
  baseline on all seven dimensions; no full council convened.
- **One real finding (fixed in this PR):** `#ew-doc-text`'s load-bearing
  `white-space: pre-wrap` inherited into `.ew-doc-rendered`, double-spacing
  every rendered doc (verified live: 5291px -> 3352px on a real EDGAR doc,
  tables ~2x). Fix is a two-declaration reset in the `.ew-doc-rendered`
  block plus a red-green computed-style smoke lock and the inverse raw-mode
  guard. Offsets and the search haystack are untouched (paint-only change).
- **Fix list (full memo in the PCoS Drive folder,
  2026-07-10_Prospectus-Stage5-Integration-Audit.md):** (1) this PR, gate
  then final pin bump; (2) rollback drill BEFORE the freeze (its scheduled
  pre-B1-deploy moment vanished when cadence slots collapsed); (3) punch W3
  mobile pre-table chrome, dropped without trail, issue filed with
  paste-ready prompt; (4) wrapper privacy pre-commit hook still not
  installed (one command, Teal); (5) MINOR bundle issue (export ORDER BY
  parity test, smoke-header scenario letter, check() detail-on-PASS,
  axe-core caret pin).
- **Scoreboard:** 9/9 branches first-attempt, 0 escalations; post-audit
  residual 0 CRITICAL / 1 IMPORTANT (fixed); executor seats
  subscription-covered. Posted to ADM-153 and the project status update.

## Session 2026-07-06 (latest): Stage 2 for the pre-Monday batch

- **PR #101** (this branch): the batch plan (B0-B8 + gated CAC spike),
  paste-ready executor prompts, the private-blocklist loader in
  pre_commit_private_check.py (patterns in gitignored
  docs/private/blocklist.txt, populated locally; hook verified blocking),
  and pre-created docs/build-metrics.md. Spec = the 2026-07-06 ideation
  memo in the PCoS Drive folder (Stage 1 skipped on the record).
- **Council PLAN review ran before the PR** (Codex xhigh, Gemini via agy,
  Opus 4.8 max external, Fable chair); disposition with two rejected
  findings is in the plan doc. Key revisions: B1 skeleton proves rendered
  offset mapping on an EDGAR doc day one; active-text contract; B3 after
  B2; B8 after B3 with shared WHERE; B4 tries INSTALL FROM before SET and
  deploys alone with instant env revert; rollback drill BEFORE the B1
  deploy, not Sunday.
- **Linear:** TEA-928..938, one per branch + freeze/rehearsal, all under
  the Prospectus Explorer v2 project with plan pointers.
- **Dispatch:** paste prompts from
  docs/superpowers/plans/2026-07-06-premonday-batch-executor-prompts.md
  per its dispatch schedule (day one: B0, B5, B1, B2, B4). Merge PR #101
  first so executors branch off a main that has the plan and metrics file.
- **Pending Teal:** merge #101; run B0/B5 day-one dispatches; install the
  wrapper privacy hook (one command, script in the session summary;
  agent-side install was correctly blocked by permissions).

## Session 2026-07-05 (latest): TEA-904 live + TEA-905 (S5)

Site is LIVE and verified: https://prospectus.tealinsights.com (Let's
Encrypt TLS, snapshot 2026-07-04, 9,774 docs). TEA-904 closed with live
numbers: Lighthouse browse 92/100/CLS 0, parameterized 93/100/0 x3, doc
97/100/0; 27-check Playwright live pass, zero failures.

- **Launch postmortem (the one real fire):** managed SimpleCORS drops
  ACAO when the viewer sends Cache-Control/Pragma no-cache, which Chrome
  sends for fetch cache:'no-store' (the MANIFEST-first contract) and on
  every hard refresh. Site was dead in real browsers while every curl
  passed. Fix live: origin-emitted CORS (bucket CORS + CORS-S3Origin ORP
  + cache policy v2 db3070d4 with Origin in the key, RHP detached).
  Recorded in wrapper branch `infra/cors-origin-emitted` (unmerged; can
  ride the next wrapper deploy). Lesson now in the wrapper README:
  probe CORS with a real browser fetch, never only curl.
- **S5 QA (TEA-905, full checklist on the Linear issue):** two defects
  fixed in PR #99 (LuxSE ~350-char filing URLs blew doc pages to ~3,178px
  on phones making the 29 MB doc's gate un-tappable, also broke desktop;
  footer provenance now links the repo). Deferred with context: #92
  PDIP filing links all point at the generic search page, #93 one dead
  LuxSE signed URL + link-check, #94 page-count vs page-anchor
  dissonance, #95 image-comment noise, #96 browse copy math + silent
  page clamp, #97 self-host duckdb parquet extension, #98 chip-inject
  CLS on throttled deep links, #82 commented (search gap has a soft
  clock: the July 13 talking points promise corpus-wide search next).
- **Open-core front door (PR #100):** README explorer section with
  neutral screenshot + quickstart VERIFIED on a fresh clone (npm ci,
  two-file snapshot download, 9,776 pages in 5s), open-core statement
  (memo 2026-07-04 Section 1), new NOTICE (trademarks/fonts/provenance
  excluded from MIT), LuxSE added to the source list, logo paths fixed
  (had been 404ing on the repo front page).
- **Pending Teal:** merge PR #99 + #100 (codex/claude reviews
  requested); wrapper pin bump + push after merges (a main push
  triggers the Netlify build; that deploy carries the URL-wrap + footer
  fixes live and can carry `infra/cors-origin-emitted`); commit + deploy
  the SovTech card in tealinsights-site (staged on
  `feature/tea-905-sovtech-card`; the repo guard blocks agent commits
  there); rehearse Netlify rollback on that second deploy (TEA-904
  deferred item). Talking points are in the PCoS Drive folder as
  2026-07-13_Prospectus-Coffee-Talking-Points.md.

## Session 2026-07-04: TEA-904 (Explorer v2, S4)

Brand wrapper built and verified locally; everything that needs no
dashboard is done. Ship sequence is gated on Teal's handoff list
(TEA-904 comment has the numbered list; DNS-bearing items first).

- **Open repo:** PR #91 ("S4 seams") open on
  `lte/tea-904-s4-private-brand-wrapper-netlify-deploy`: brand slots in
  Base.astro, display tokens, optional PUBLIC_WASM_BASE_URL, 404 page,
  SNAPSHOT_DIR-aware assert-dist, error diagnostics, CI font tripwire.
  All neutral no-ops; empirically proven at the plan gate before
  application. Spec + plan + all council dispositions in
  docs/superpowers/ (same branch). Gemini review handled; codex had not
  responded at session end.
- **Wrapper repo:** ~/Code/prospectus-web-ti (LOCAL ONLY; GitHub repo
  creation is Teal's handoff item 2). Submodule pin, branded tokens
  (all 36 names, ratios recomputed), Head/Header brand components,
  build.sh (staging build, tokenized snapshot fetch), netlify.toml
  (licence 301, /pipes proxy, font headers), CI, README (full licence
  rules), upload-snapshot.sh + provision-data-host.sh +
  iam-deploy-policy.json for the S3+CloudFront data host.
- **Verified locally (full snapshot, branded):** 9,776 pages; Lighthouse
  browse 96 / a11y 100 / CLS 0 (parameterized same; doc 99/100/0); axe
  zero serious/critical; fonts exactly one request per face, same-origin
  only; h1 = Tiempos 600.
- **Hosting decision:** pages on Netlify; snapshot + wasm on
  S3+CloudFront at data.tealinsights.com, pre-compressed at rest.
  R2 is blocked (tealinsights.com DNS is Google Cloud DNS; R2 custom
  domains need a Cloudflare zone). Full rationale in the spec.
- **Licence findings:** the MAIN SITE leaks Klim fonts at
  tealinsights.netlify.app today; fix PR open (tealinsights-site#1).
  Wrapper ships the same forced 301 + previews disabled; Klim order
  number redacted from public docs.
- **Ship sequence (Phase C of the plan):** Teal creates the private
  repo + AWS credential -> provision + upload -> DNS batches -> Netlify
  site (name MUST be prospectus-tealinsights) -> merge PR #91 -> bump
  wrapper pin to the merge SHA -> push -> first deploy -> live
  verification -> TEA-904 comment + close.

## Session 2026-07-04 (earlier): TEA-903 (Explorer v2, S3)

Explorer core built to v1 Shiny parity on the S2 scaffold. PR pending
merge go-ahead; Linear TEA-903 has the full trail; spec + plan with all
council dispositions in docs/superpowers/.

- **What shipped:** multi-select filters (select+chips) with repeated
  query params and unknown-param passthrough; scope status matrix with
  marginal hidden counts; segment-by-TOC-offset rendering above 1M UTF-16
  units (620 docs; "Segment", never "Part"); in-document search (compute
  guards: min length 2, 20K cap, index-only) with CSS Custom Highlight
  paints, live-region announcements, and a q param that never bypasses
  the 5 MB gate; history discipline (pushState interactions, replaceState
  corrections, popstate never writes); baked static shell.
- **Gates:** spec 6 reviewers, plan 5, PR 5 + a 28-agent code-review
  workflow; every disposition recorded (spec/plan docs + PR comment).
  Lighthouse 100 perf / 100 a11y / CLS 0 (bare and parameterized browse;
  doc 98/100). P1-P22 parity verified side by side against v1 run on the
  deployed MotherDuck data path. Fixture: issue #88 shapes landed
  (synthetic-gate/astral/large).
- **Deferred/known:** #84 vintage footnote still hardcoded (comment links
  the issue); #86 pages[].offset_utf16 still unconsumed; VoiceOver
  listen-through optional for Teal (live-region text machine-verified).
- **Dev notes unchanged** (Node >= 22.12; smoke now needs the two-origin
  serve recipe in scripts/smoke.mjs header; CI runs it on the fixture).

## Session 2026-07-04 (later): TEA-902 (Explorer v2, S2)

explorer-web/ scaffolded (Astro 6.4.8 + DuckDB-WASM 1.32.0) and all three
spike risks proven with numbers. PR #87 (awaiting merge go-ahead); Linear
TEA-902 has the full trail; decisions + measurements in
explorer-web/ARCHITECTURE.md and explorer-web/measurements/NOTES.md.

- **Spike verdicts:** in-browser DuckDB-WASM over the snapshot parquet
  PASS (cold ~1.4-1.5 s to first rows, warm ~0.8 s, throttled 9.2 s,
  ~8.7 MB cold transfer); 10k-page pre-render PASS (9,775 pages in
  ~4.7 s, 683 MB peak RSS); config-driven data URLs PASS (astro:env
  fail-fast; CORS proven with a two-origin harness). Lighthouse 100 /
  CLS 0; bfcache genuinely restores (159 ms, measured with full Chrome
  after the council caught Playwright's default disabling bfcache).
- **Council gates ran at spec, plan, and PR** (6+4+4 fresh reviewers).
  Highest-value catches: wasm is 34 MB raw/5.9 MB brotli (hosting
  constraint), npm latest of duckdb-wasm is a dev build, 22.3% of
  snapshot rows are non-sovereign (browse now defaults to sovereign
  scope with live counts + badges), FY2027 classification vintage
  footnote, the invalid bfcache measurement.
- **Deferred issues:** #84 (classification_vintage in MANIFEST), #85
  (unmapped_issuers audit gap), #86 (pages[].offset_utf16), #88
  (fixture text-scale shapes), #89 (wasm fetch split via CDP worker
  auto-attach).
- **Dev notes:** explorer-web needs Node >= 22.12; npm run dev serves
  the repo snapshot at /data; astro preview does not (use
  scripts/serve-static.mjs); scripts/smoke.mjs is the browse smoke;
  scripts/measure.mjs is the spike harness (run from explorer-web/).
- **Next (S3, TEA-903):** parity build on these seams. Read
  ARCHITECTURE.md "Inputs for S3" first; the TEA-903 parity pointer
  should be shiny/app.py, not demo/shiny-app/ (noted on the issue).

## Session 2026-07-04: TEA-901 (Explorer v2, S1)

Corpus refreshed to present and static snapshot format defined. Linear
TEA-901 has the full trail; PR #78 has the code.

- **Corpus refresh (run id `refresh-20260704`):** EDGAR 30 new (current
  through 2026-06-30), NSM 15 new PDFs (current through 2026-06-03),
  0 download failures. Corpus: 9,729 to 9,774 documents. Derived tables
  (document_pages, document_markdown, FTS) refreshed.
- **Snapshot builder:** `uv run python scripts/build_snapshot.py` writes
  `data/snapshot/` (documents.parquet 1.1 MB, text/ 9,671 JSON files
  2.5 GB, MANIFEST.json). Schema version 1. See README.
- **Pipeline fix:** `corpus parse run` now writes the markdown sidecar
  that `build-markdown` consumes (was silently discarded before; only
  the bulk reparse scripts produced .md files).
- **Known state:** 103 documents have no text (84 EDGAR `.paper`
  placeholders + 19 unparseable). LuxSE has a separate backlog: only
  ~10 LuxSE parse outputs live in `data/parsed`; the full April set is
  in `data/parsed_docling` (DB tables are complete, but `parse run
  --source all` would try to re-parse 4,945 LuxSE PDFs — avoid).

---

# Archive: Spring Meetings Sprint (overnight parse)

**Last updated:** 2026-04-11 evening (post-implementation, pre-overnight parse)
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Branch:** `feature/docling-bug-fix-and-sprint-v2`
**Spec:** `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md`
**Plan:** `docs/superpowers/plans/2026-04-11-spring-meetings-sprint.md`
**Tests:** 431 passing, 0 failing

## START HERE (Sunday morning)

The overnight Docling parse ran on the Mac Mini M4 Pro. All code for
Steps 1-3 and PR #3 pre-work is built, tested, and pushed. The morning
is operational — run commands, not build tasks.

### Morning Runbook

```bash
# 1. Validate overnight parse output
uv run python scripts/validate_parse_output.py

# 2. Promote parsed dir (backup PyMuPDF, promote Docling, re-parse EDGAR)
uv run python scripts/promote_parsed_dir.py

# 3. DELETE old DB and rebuild from scratch (existing DB has 4,769 rows
#    with NULL parse_tool — ingest skips existing rows, so backfill won't
#    work without a fresh start)
rm -f data/db/corpus.duckdb
uv run corpus ingest --run-id rebuild-$(date +%Y%m%d)

# 4. Build pages + FTS index
uv run corpus build-pages

# 5. Build markdown for detail panel
uv run corpus build-markdown

# 6. Re-run grep (existing matches reference PyMuPDF offsets — now invalid)
uv run corpus grep run --run-id grep-docling-$(date +%Y%m%d)

# 7. Publish to MotherDuck
export MOTHERDUCK_TOKEN=<token>
uv run corpus publish-motherduck

# 8. Build Streamlit explorer (PR #4 — Task 4)
# This is the main Sunday work item
```

### If the overnight parse had errors

```bash
# Check error details
cat data/parsed_docling/_errors.log

# Resume from where it stopped (script skips existing outputs)
caffeinate -d -i uv run python scripts/docling_reparse.py 2>&1 | tee /tmp/docling_resume.log

# Re-validate after resume
uv run python scripts/validate_parse_output.py
```

---

## What shipped (Saturday 2026-04-11)

### Step 0: Docling bug fix + smoke test — DONE
- Bug reproduced (11/58 pages on nsm__101126915)
- Fix verified (58/58 pages via export_to_markdown(page_no=N))
- Docling 2.86.0, DuckDB 1.4.4 confirmed

### Step 1 (PR #1): Docling Phase A — DONE (7 commits)
- `DoclingParser` class with lazy import, per-page markdown export
- `strip_markdown()` — preserves table content for FTS
- Registry registration, config default flipped to "docling"
- CLI rewire: `get_parser()` replaces hardcoded `PyMuPDFParser()`
- `scripts/docling_reparse.py` fixed: per-page export, JSONL contract, LuxSE glob
- Decision 18 doc updated
- 13 parser tests + 8 strip_markdown tests

### Step 2: NSM + EDGAR incrementals — DONE
- NSM: 913 discovered, 5 new PDFs downloaded (DRC confirmed)
- EDGAR: 3,307 discovered, all existing (no new filings)

### Step 3: LuxSE adapter — DONE (download still running)
- Reverse-engineered GraphQL API at `graphqlaz.luxse.com/v1/graphql`
- Discovery: 5,926 unique sovereign documents
- Download: confirmed %PDF magic bytes, ~800+ PDFs downloaded (still running)
- 10 adapter tests

### PR #3 pre-work: FTS, markdown, MotherDuck — DONE
- `document_markdown` + `document_pages` DDL (sql/001_corpus.sql)
- `build_pages()` + `create_fts_index()` (src/corpus/db/pages.py) — 4 tests
- `build_markdown()` (src/corpus/db/markdown.py) — 4 tests
- `publish_to_motherduck()` (src/corpus/db/publish.py)
- `read_jsonl_header()` for parse_tool/page_count backfill — 4 tests
- CLI: `corpus build-pages`, `build-markdown`, `publish-motherduck`
- `scripts/promote_parsed_dir.py` — directory promotion
- `scripts/validate_parse_output.py` — morning validation

### Overnight parse safeguards added
- Resume filter checks BOTH .jsonl AND .md (not just .jsonl)
- Pre-flight: disk space check (>5GB), stale .part cleanup
- Default timeout bumped 300s → 600s for large LuxSE PDFs
- Validation script for the morning

---

## Overnight parse command

```bash
# Delete broken March 28 outputs (ONE TIME — do not re-delete on crash/resume)
rm -rf data/parsed_docling/

# Run the fixed script
caffeinate -d -i uv run python scripts/docling_reparse.py 2>&1 | tee /tmp/docling_overnight.log

# Monitor from another terminal:
tail -f data/parsed_docling/_progress.jsonl
```

Expected: ~2,500+ docs (NSM 645 + PDIP 823 + LuxSE ~800+) at ~10s/doc = ~7hrs.

---

## What's left for Sunday

| Step | Task | Est. |
|------|------|------|
| Step 5 | Validate overnight parse | 15 min |
| Step 6 | Promotion + rebuild + pages + markdown + grep + MotherDuck | 1-2 hr (mostly runtime) |
| Step 7 | PR #4: Streamlit explorer | 3-6 hr |
| Step 8 | Polish + demo script | 30-60 min |

---

## Key file locations

| What | Where |
|------|-------|
| Spec v2 | `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md` |
| Implementation plan | `docs/superpowers/plans/2026-04-11-spring-meetings-sprint.md` |
| LuxSE spec | `docs/superpowers/specs/2026-04-11-luxse-adapter-design.md` |
| DoclingParser | `src/corpus/parsers/docling_parser.py` |
| strip_markdown | `src/corpus/parsers/markdown.py` |
| LuxSE adapter | `src/corpus/sources/luxse.py` |
| Page ingest + FTS | `src/corpus/db/pages.py` |
| Markdown ingest | `src/corpus/db/markdown.py` |
| MotherDuck publish | `src/corpus/db/publish.py` |
| JSONL header ingest | `src/corpus/db/ingest.py` (read_jsonl_header) |
| Reparse script (fixed) | `scripts/docling_reparse.py` |
| Validation script | `scripts/validate_parse_output.py` |
| Promotion script | `scripts/promote_parsed_dir.py` |
