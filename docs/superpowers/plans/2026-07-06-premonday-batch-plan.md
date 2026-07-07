# Pre-Monday Change Batch Implementation Plan (B0-B8 + SPIKE)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement YOUR BRANCH ONLY, task by task. Steps use checkbox (`- [ ]`) syntax. Each branch runs in a fresh executor session with its own worktree; paste-ready prompts live in `docs/superpowers/plans/2026-07-06-premonday-batch-executor-prompts.md`.

**Goal:** Ship the ideation memo's MUST list (readable rendered documents, find-the-document search, credibility polish, extension self-host, design pass) plus early insurance (live smoke, headers) to prospectus.tealinsights.com before the Saturday 2026-07-11 night freeze, as small deltas that never regenerate the snapshot.

**Spec:** The Stage 0 ideation memo stands in as the spec (Stage 1 deliberately skipped):
`/Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My Drive/01-PROJECTS/_Personal/Personal Chief of Staff/2026-07-06_Prospectus-PreMonday-Ideation-Memo.md`
Standing vision: same folder, `2026-07-06_Prospectus-Vision-Voice-Dump.md`. Design rubric: `~/Dropbox/lte-workbench/docs/explainers/interface-design-for-small-data-tools.md` (ISO 9241-110 seven principles).

**Architecture:** All UI logic lands in the open repo (`sovereign-prospectus-corpus/explorer-web/`, Astro 6 + DuckDB-WASM, static). Brand, deploy config, and ops land in the private wrapper (`~/Code/prospectus-web-ti`: netlify.toml, brand/, scripts/, GitHub Actions). The wrapper pins upstream as a git submodule; a wrapper main push triggers the Netlify production build. Document text is fetched client-side as JSON from the data host; B1 renders its existing markdown client-side. Nothing regenerates the snapshot, and nothing touches the data host except B4's extension upload.

**Tech Stack:** TypeScript, Astro 6.4.8, @duckdb/duckdb-wasm 1.32.0, vitest, Playwright (installed), marked (new, exact-pinned), GitHub Actions (wrapper).

## Global Constraints

- **Deltas only, never regeneration.** No snapshot rebuild, no pipeline changes, no data-host changes except B4's extension upload. (Memo section 4.)
- **Deploy freeze Saturday 2026-07-11 night.** Sunday is rehearsal only; Sunday ships nothing but reverts. (Memo M7.)
- **PRIVACY:** Monday attendee names and firms appear NOWHERE in either repo, in commits, branches, issues, PRs, or prompts. Audience is described publicly as "practitioners in sovereign debt restructuring." Enforcement is mechanical: `scripts/pre_commit_private_check.py` reads extra patterns from gitignored `docs/private/blocklist.txt` (task A0, done by the architect).
- **No em-dashes** in any code copy, docs, commit messages, or comments (repo rule; `format.ts` is test-guarded).
- **Repo routing:** logic upstream (open repo), brand and deploy in the wrapper. When in doubt, stop and report.
- **Copy is verbatim from this plan.** Executors paste the copy blocks exactly; they do not write user-facing prose.
- **Exact-pin new dependencies** in package.json (repo convention: `"astro": "6.4.8"` style).
- **Verification is LOCAL, not Netlify previews.** Wrapper deploy previews are disabled (font-licence rule: the netlify.app hostname is unlicensed). The memo's "Netlify preview branch" phrasing is corrected to: local build + `scripts/serve-static.mjs` two-origin serve + `scripts/smoke.mjs`, and `npm run dev` with the full snapshot for eyeball checks. Production deploys happen only via wrapper submodule pin bumps on merge days.
- **Metrics:** every branch appends one line to `docs/build-metrics.md`. The file is pre-created with its header row in the batch PR (A0), so no branch creates it. A rebase conflict on this file is DECLARED MECHANICAL: keep both lines, continue. Header: `| branch | model+effort | attempts | escalations | council C/I post-exec | wall time |`.
- **Worktrees:** every executor works in a git worktree (superpowers:using-git-worktrees), branch named `lte/tea-NNN-<slug>` after its Linear issue.

## Branch graph, routing, merge order

| Branch | Memo | Size | Executor | Depends on | Parallel-safe |
|---|---|---|---|---|---|
| A0 privacy blocklist | memo privacy note | S | Architect (this session) | none | n/a |
| B0 design audit | M8 step 1 | M | Opus 4.8 max (advisory, no code) | live site only | yes, day one |
| B1 markdown renderer | M1 | L | Opus 4.8 max | none (B0 typography folds in before its styling task) | yes |
| B2 browse search | M2 | M | Opus 4.8 max | none | yes |
| B3 polish batch | M3+M4+M5 + B0 cheap wins | M | Codex high | B2 MERGED (its counts aggregate must inherit B2's search clauses) + B0 punch list for its copy/CSS items | starts after B2 lands |
| B4 extension self-host | M6 | M | Opus 4.8 max | none | yes |
| B5 live smoke + headers | S2+S3 | S | Codex high | none; do FIRST (insurance) | yes |
| B6 design implementation | M8 step 2 | M | Opus 4.8 max | B1 merged + B0 punch list | no |
| B7 mobile pass | S1 | M | Opus 4.8 max | B6 merged | no |
| B8 CSV export | S4 | S | Codex high | B2 AND B3 merged (export WHERE must match browse WHERE including the M4 override) | after B3 |
| SPIKE CAC eval | stretch | spike | Opus 4.8 max (TDD waived) | MUSTS DEPLOYED (B1-B6 live) | no |

**Merge order (rebase before merge; conflicts expected trivial):** B5, then B2, then B3, then B1 and B4 as they finish, then B6, then B7 and B8. B2 merges BEFORE B3 starts: B3's new counts aggregate sits over the same WHERE assembly B2 extends with search clauses, and a parallel build would compose silently wrong (council finding, 2-model). A rebase with non-mechanical conflicts is a stop-and-report, not a judgment call; a conflict on `docs/build-metrics.md` is declared mechanical (keep both lines).

**Deploy cadence (wrapper pin bumps, each one verified; revised per council):** (1) B5, early week; (2) B2+B3 (small, low-risk); (3) B1 ALONE, so any production-only regression in the riskiest branch is attributable and cleanly revertable; THE NETLIFY ROLLBACK IS REHEARSED ONCE BEFORE THIS DEPLOY, not first on Sunday; (4) B4 ALONE (the env flip is the change; revert is `netlify env:unset PUBLIC_EXTENSION_BASE_URL` + redeploy; run live-smoke immediately); (5) B6; (6) final, B7+B8, no later than Saturday daytime. After each deploy: run `node scripts/live-smoke.mjs` (from B5) against production and click the demo path once. Freeze Saturday night.

**Cross-branch file conflict surface (council; know it before you rebase):** `format.ts` (B1, B2, B3, B8), `scripts/smoke.mjs` (B1, B2, B3, B4, B8), `index.astro` (B2, B3, B8), `browse.ts` (B2, B3, B8), `DocText.astro` (B1, B3), `base.css` (B1, B6, B7). All are append-only zones for this batch: add your constants, scenarios, and rules at the END of the relevant section (including the `format.test.ts` em-dash guard array), and rebase conflicts there are mechanical (keep both sides). Non-mechanical conflicts remain stop-and-report.

**B0 punch list access (council):** B0's PR is doc-only and the operator merges it SAME DAY, ahead of the queue. B1 (before its styling task), B3 (before its cheap-wins commits), and B6 rebase onto main to pick it up; if it has not merged when needed, read the punch list from the B0 PR branch and say so in the handoff.

**Review gates:** per Project Shell Runbook Stage 4, each branch gets a thin fresh review-gate session (never the executor's own session) before merge. That is outside these executor prompts; executors end at the handoff comment.

---

## A0: Privacy blocklist (architect-owned, this session)

**Files:**
- Modify: `scripts/pre_commit_private_check.py`
- Create (gitignored, never committed): `docs/private/blocklist.txt`

**Design:** The public script gains a loader for extra patterns from `docs/private/blocklist.txt` (one pattern per line, `#` comments and blank lines skipped, case-insensitive matching like the built-ins). The names themselves live only in the gitignored file, so the mechanical check never publishes what it protects. The script also checks the current branch name against the private patterns (belt and suspenders for the "no names in branches" rule). Names sourced from Teal's 2026-07-13 calendar entries.

**DoD:** staging a file containing a blocklisted name makes `uv run python3 scripts/pre_commit_private_check.py` exit 1; unstaging it returns exit 0; `uv run pytest -v` still green; script change committed to main directly (tiny, no branch ceremony), names file NOT in `git status`.

---

## B0: Design audit (advisory dispatch, day one, NO CODE)

**Executor:** fresh-context designer-agent session (Opus 4.8 max) with browser/screenshot tooling. Advisory only: its output is a punch list, not commits.

**Inputs to load:** the live site https://prospectus.tealinsights.com (browse page `/` and one doc page, e.g. any recent document with rendered text); the interface explainer `~/Dropbox/lte-workbench/docs/explainers/interface-design-for-small-data-tools.md`; brand tokens `~/Code/prospectus-web-ti/brand/tokens.css`; the LIC-DSF visual-advisor pattern if findable under `~/Dropbox/lte-workbench/` (search for "visual advisor"; if absent, proceed without and say so).

**Method (from memo M8, verbatim intent):** walk the live site by screenshot at desktop (1440x900) and phone (390x844) widths through two lenses:
(a) human-centered flow audited AGAINST THE ISO 9241-110 INTERACTION PRINCIPLES as the explicit rubric: suitability for the task, self-descriptiveness, conformity with user expectations, learnability, controllability, use-error robustness, user engagement. One pass per principle over the two demo screens, including the cold open: "someone WhatsApped me this doc URL; does the page explain itself?" is self-descriptiveness.
(b) aesthetic: hierarchy, type scale, spacing, page furniture, the ugly disclosure box (`.ew-about`), empty states.
Target: "made by a firm with designers," McKinsey/GS publication energy, not research-analyst energy. Pragmatic fulfillment of the ISO principles as audit checklist, not certification. User-evaluation leg deferred to Monday by design (ISO 9241-210 posture).

**Output contract:** `docs/superpowers/plans/2026-07-07-design-audit-punchlist.md` in the open repo. AT MOST 10 items. Each item: sized S or M; a concrete change spec (exact CSS/markup/copy change, exact file when knowable: `explorer-web/src/styles/base.css`, `tokens.css`, page templates upstream; `brand/tokens.css`, `brand/Header.astro` in the wrapper); routed to exactly one of B1 (doc-page typography and reading layout: type scale, measure, line-height, table styling for rendered text), B3 (cheap copy/CSS wins), or B6 (everything else). Anything L-sized goes to a WAIT list at the bottom. Also: an explicit "what I checked that came back sound" list. No Monday attendee references of any kind (public repo).

**DoD:** punch list file exists with <= 10 items, every item sized + routed + concretely specified, WAIT list present, sound-list present, screenshots archived to the session (not the repo).

**Stop-and-report:** the live site is down or errors during the walk (do not debug it; report).

---

## B1: Markdown document renderer (M1, THE L BRANCH, riskiest first)

**Goal:** Docs whose `text_source === 'markdown'` render as real HTML (headings, bold, tables) in a two-mode viewer; in-doc search, highlighting, TOC jumps, and section counts work against the rendered view; a "View raw text" toggle switches to the existing plaintext mode; `pages`-source and very large docs keep the current plaintext path unchanged.

**Executor:** Opus 4.8 max. Worktree off `main`.

**Files:**
- Create: `explorer-web/src/lib/md-render.ts`
- Create: `explorer-web/tests/unit/md-render.test.ts`
- Modify: `explorer-web/src/lib/doc-view.ts` (add `locateSpan`, `FORCE_PLAIN_SLUGS`)
- Modify: `explorer-web/tests/unit/doc-view.test.ts`
- Modify: `explorer-web/src/lib/format.ts` (view-toggle copy)
- Modify: `explorer-web/tests/unit/format.test.ts`
- Modify: `explorer-web/src/scripts/doc-text.ts` (mode state, mode-aware helpers)
- Modify: `explorer-web/src/components/DocText.astro` (toggle button, `data-text-source`)
- Modify: `explorer-web/src/env.d.ts` and `explorer-web/ARCHITECTURE.md` (council: the documented `#ew-doc-text` "exactly one text node + data-seg-start" invariant becomes mode-scoped; amend it to: in rendered mode the container holds a rendered HTML tree and `window.__ewDoc.getRawText()` still returns the full raw markdown string; the single-text-node/`data-seg-start` invariant holds only in plain/segmented modes. Updating this contract is AUTHORIZED and required; leaving it stale misleads the TEA-907 search consumers it exists for)
- Modify: `explorer-web/src/styles/base.css` (`.ew-doc-rendered` typography per B0)
- Modify: `explorer-web/scripts/smoke.mjs` (rendered-mode scenarios)
- Modify: `explorer-web/package.json` (add `marked`, exact pin)
- Possibly modify: `explorer-web/tests/fixtures/snapshot/*` via `scripts/make_fixture.py` (add one markdown-rich fixture doc with a table if none exists; fixtures are test assets, NOT the production snapshot; regenerating fixtures is allowed)

**Interfaces:**
- Produces `renderDocMarkdown(raw: string): string` in `md-render.ts`: marked (exact pin `18.0.5`) with GFM tables; raw HTML tokens (block and inline, including `<!-- image -->` Docling comments) dropped via renderer overrides, never passed through and never regex-stripped; images render as their alt text or nothing; links become anchors only for http/https hrefs (with `rel="noopener"`), otherwise render as plain text. `md-render.ts` stays pure string-to-string (node-testable). DEFENSE IN DEPTH: the injection site in `doc-text.ts` additionally pipes through `DOMPurify.sanitize()` (dompurify, exact pin `3.4.11`, browser call site only, default config plus `ADD_ATTR: ['rel']` if needed) before assignment, so a renderer regression can never become live XSS on untrusted filing text. Both layers are required; tests pin the first, smoke exercises the second.
- Produces `locateSpan(starts: number[], lengths: number[], start: number, end: number): { startNode: number; startOffset: number; endNode: number; endOffset: number } | null` in `doc-view.ts`: pure mapping from a global UTF-16 span over the concatenated text-node string to per-node positions; `end` clamps to total length; returns null when `start` is at or past total length or the span is empty after clamping.
- Produces `FORCE_PLAIN_SLUGS: ReadonlySet<string>` in `doc-view.ts` (empty by default; escape hatch if sampling flags a bad doc).
- Produces in `format.ts`: `VIEW_RAW_LABEL = 'View raw text'`, `VIEW_FORMATTED_LABEL = 'View formatted text'`, `viewModeAnnouncement(formatted: boolean): string` returning `'Showing formatted text.'` or `'Showing raw converted text.'`, and `highlightCapNoteWhole(cap: number): string` returning `Showing the first ${num(cap)} highlights.` (council: the existing `highlightCapNote` says "in this segment", which is wrong in rendered mode where no segments exist).
- Rendered-mode highlight paint semantics (council; the existing cap loop is segment-windowed): paint matches in match order from index 0, capped at `HIGHLIGHT_CAP` (2,000) across the WHOLE document; the current match is always painted regardless of the cap; the cap note uses `highlightCapNoteWhole`.
- Consumes: existing `findMatches`, `countsByBins`, `sanitizeToc`, `needsSegments` (unchanged), `fetchDocText` (unchanged).

**Mode rules (decide nothing mid-flight; this is the decision):**
- Rendered mode is used iff `textSource === 'markdown'` AND `!needsSegments(rawText.length)` AND `!FORCE_PLAIN_SLUGS.has(slug)`. Everything else (pages-source docs, docs over 1,000,000 UTF-16 units including the 29 MB worst case, force-listed slugs) uses the existing plain path with zero behavior change.
- In rendered mode there is NO segmentation; the whole rendered document is one DOM tree inside `#ew-doc-text` wrapped in `<div class="ew-doc-rendered">`.
- The search haystack in rendered mode is the concatenation of the rendered text nodes (markdown syntax stripped, which means phrases broken by `**` in raw now match). Build once after injection: TreeWalker over ALL text nodes of the container, INCLUDING whitespace-only nodes (the newlines marked emits between block elements become natural word separators in the haystack), collecting `nodes: Text[]`, `starts: number[]`, `lengths: number[]`, and the concatenated string. NEVER inject synthetic characters into the concatenation: offsets must map 1:1 onto the DOM text nodes or every Range breaks. Known accepted limitation: a phrase spanning two DOM positions with no whitespace-bearing node between them (rare; adjacent table cells in some renderers) will not match a spaced query; do not engineer around it. Matches can span node boundaries; `Range` supports that.
- ACTIVE-TEXT CONTRACT (all offsets agree or nothing works): a single `active` object `{ text: string; mode: 'plain' | 'rendered' }` plus the node index in rendered mode. EVERY consumer (findMatches haystack, snippetAround, scrollToOffset, jumpToOffset bounds, TOC row offsets, countsByBins bins, highlight ranges, selection fallback) reads offsets in `active.text` space for the current mode. In plain mode `active.text === rawText`. Mixing raw-text offsets with rendered-text offsets anywhere is a defect; the smoke suite asserts the live-region snippet quotes RENDERED text for a match on a phrase that is bold-split in the raw markdown.
- TOC in rendered mode is derived FROM THE RENDERED HEADINGS, not the snapshot toc JSON: after injection, walk `h1..h6` inside the container, assign `id="ew-h-{i}"`, and build rows `{ title: heading.textContent, level, offset }` where offset is the heading's first text node's global start (headings with no text node use the next text node's start). Front-matter row exactly when the first heading offset > 0. `countsByBins` then works unchanged. Plain mode keeps the snapshot-toc offset path exactly as today.
- The toggle (`#ew-view-toggle`) shows only when rendered mode is eligible; label is `VIEW_RAW_LABEL` while formatted, `VIEW_FORMATTED_LABEL` while raw. Toggling re-renders the container in the other mode, rebuilds the TOC, re-runs the last executed query if any (typing-path semantics: no scroll, no focus steal), resets match navigation to un-navigated, and announces via `viewModeAnnouncement`. The toggle state is session-local; it is NOT written to the URL.
- `?q=` deep links work in both modes (restore runs against whichever mode rendered).

**Tasks (TDD order):**

- [ ] 1. WALKING SKELETON, redefined per council (2-model convergent): the skeleton must prove the RISK (rendered-DOM offset mapping), not markdown parsing. `npm install --save-exact marked@18.0.5 dompurify@3.4.11`; minimal `renderDocMarkdown` (GFM on, html dropped); inject (through DOMPurify) for ONE markdown-rich EDGAR doc (council: the memo's pre-mortem names EDGAR as the source that kills the pitch; the skeleton doc must come from the feared source, not a hand-picked pretty one; find it with `SELECT slug, text_bytes FROM read_parquet('<snapshot>/documents.parquet') WHERE source='edgar' AND text_source='markdown' AND text_chars < 1000000 ORDER BY text_bytes DESC LIMIT 5` and pick one with tables); build the text-node index; implement `locateSpan` + `spanRange`; then on that doc, END TO END: (a) a search for a phrase that is bold-split in the raw markdown paints a CSS Custom Highlight across node boundaries, (b) one rendered-heading TOC jump scrolls and focuses correctly, (c) render the LARGEST eligible markdown doc in the snapshot once (`... WHERE text_source='markdown' AND text_chars <= 1000000 ORDER BY text_chars DESC LIMIT 3`) and record renderMs as a viability sniff (if it is wildly over 3000 ms, stop and report NOW, not at task 9). Run dev against the full snapshot (`SNAPSHOT_DIR=../data/snapshot npm run dev` from explorer-web/, or the README's snapshot-fetch quickstart if data/ is absent). Commit.
- [ ] 2. SAMPLING GATE (day one, before generalizing). Query the snapshot parquet for 5 docs per source with `text_source='markdown'` (DuckDB CLI or a throwaway node script; read-only), open each through the renderer, record a verdict table (slug, source, verdict, notes) in the branch notes/PR body. Also open 2 `pages`-source docs to confirm the untouched plain path. If any SOURCE renders systematically badly: STOP AND REPORT with the verdict table. Individual bad docs go to `FORCE_PLAIN_SLUGS`.
- [ ] 3. `md-render.test.ts` first, then finish `renderDocMarkdown`: headings map to h1..h6; GFM table emits `<table>`; `**bold**` emits `<strong>`; `<script>alert(1)</script>` and `<!-- image -->` produce no HTML passthrough; `[x](javascript:alert(1))` renders as text not anchor; `[x](https://example.org)` renders as anchor with `rel="noopener"`; image syntax renders alt text only. Run, green, commit.
- [ ] 4. `locateSpan` tests first (span within one node; spanning two nodes; end clamps to total; start past total returns null; empty span null), then implement in doc-view.ts. Run, green, commit.
- [ ] 5. Mode-aware doc-text.ts: introduce the ACTIVE-TEXT CONTRACT (`active.text` per mode), and generalize the seams (`textNode()`-based range building becomes mode-aware `spanRange(start, end)`; `scrollToOffset`; `tocRows`; segment UI suppressed in rendered mode). Every haystack and offset consumer switches to `active.text`: `runSearch` calls `findMatches(active.text, q)`, `goToMatch` calls `snippetAround(active.text, ...)`, `jumpToOffset` bounds check against `active.text.length`, `updateTocCounts` bins in active space, `applyHighlights` uses the rendered paint semantics above. The match STATE machine (indices, wrap, navigated flag), Enter/Prev/Next wiring, debounce, and the 5 MB gate stay shared, but nothing that touches text or offsets is exempt from the contract (council: "stays untouched" phrasing caused a raw/rendered offset mix in review; the contract wins over sharing). Search + highlight + TOC jump verified in dev on the skeleton doc AND on one pages-source doc (plain path regression).
- [ ] 6. Toggle button (DocText.astro + format.ts copy + wiring), `data-text-source` attribute, `viewModeAnnouncement`. format.test.ts additions green. Commit.
- [ ] 7. `.ew-doc-rendered` styles per the B0 punch list items routed to B1 (type scale, measure, line-height, table borders + `overflow-x: auto` on tables, spacing). If B0 has not delivered by the time you reach this task, apply the defaults: max-width 72ch on rendered text, table cells padded var(--ew-space-2) with 1px var(--ew-color-border) borders, and STOP AND REPORT for the rest rather than inventing typography. Commit.
- [ ] 8. Smoke scenarios in `scripts/smoke.mjs` (fixture snapshot; append at the end, this file is a multi-branch append-only zone): rendered doc search finds a phrase split across bold in raw markdown AND the live-region announcement quotes the RENDERED snippet (not raw markdown with `**` in it); TOC jump from a rendered heading; toggle to raw and back re-runs the query; `?q=` deep link on a rendered doc; pages-source doc still passes the existing scenarios. Add a markdown-rich fixture doc via `make_fixture.py` if the fixture lacks one. Full smoke green.
- [ ] 9. PERFORMANCE BUDGET (DoD-blocking). Against the full snapshot, on the 3 largest eligible markdown docs: `window.__ewDocMetrics.renderMs` (extended to cover parse + inject + index build) <= 3000 ms in desktop Chrome; a search for "the" completes <= 500 ms; the 29 MB doc still loads via gate + segments + plain path exactly as before (existing smoke asserts it). Record numbers in `explorer-web/measurements/NOTES.md`. If a budget fails: try marked's async/lexer fast paths ONCE; if still failing, STOP AND REPORT (candidate responses: raise the plain-mode threshold, not yours to decide).
- [ ] 10. Full `npm test`, `npx astro check`, smoke, handoff.

**Edge cases (enumerated):** doc with zero headings in markdown (empty TOC, `NO_TOC_LABEL`, no front-matter row); heading with inline formatting (`textContent` strips it, fine); match spanning a table cell boundary (two text nodes, one Range); query typed before toggle then toggled (lastRanQuery re-run in new mode); highlight-unsupported browsers (selection fallback must use `spanRange`, works across nodes); doc eligible for rendered mode but `FORCE_PLAIN_SLUGS` lists it (plain, toggle hidden); empty markdown text (renders empty container, search disabled state unchanged from plain semantics).

**Definition of done (verbatim for the executor prompt):**
- `npm test` green including new `md-render.test.ts`, `doc-view.test.ts` (locateSpan), `format.test.ts` (labels + announcement).
- `npx astro check` clean; `npm run build` succeeds on the fixture snapshot.
- `scripts/smoke.mjs` green including the 5 new rendered-mode scenarios and all pre-existing scenarios (plain path unregressed).
- Sampling verdict table for 5 docs x 4 sources recorded; no source-level failure outstanding.
- Performance numbers recorded in `measurements/NOTES.md`; all three budgets met (renderMs <= 3000 ms on top-3 eligible docs, search <= 500 ms, 29 MB doc unchanged behavior).
- Raw-text toggle works both directions with search re-run, verified in smoke.
- The documented container contract in `env.d.ts` and `ARCHITECTURE.md` is amended to be mode-scoped (see Files).
- No change to: snapshot pipeline, `snapshot-client.ts` fetch contract, plain-mode behavior for pages-source and segmented docs, URL schema.

**Out of scope:** corpus-wide search; page anchors; markdown rendering for segmented (>1M unit) docs; persisting the toggle in the URL; restyling anything outside `.ew-doc-rendered` (B6's job); snapshot text cleanup (#95 upstream fix stays open; rendered mode merely stops displaying comment noise).

**Stop-and-report triggers:** a whole source renders badly at the sampling gate; performance budget fails after one bounded attempt; the fixture tooling cannot produce a markdown-rich fixture doc; any need to touch snapshot-client.ts beyond reading `text_source`; rebase conflicts that are not mechanical.

---

## B2: Find-the-document search on browse (M2)

**Goal:** A search box on the browse page live-filters the table over issuer, title, and country, client-side against the parquet already in the browser. "Philippines 2031" narrows in two words.

**Executor:** Opus 4.8 max. Worktree off `main`.

**Files:**
- Modify: `explorer-web/src/lib/queries.ts` (+`q` in `BrowseFilters`, `likeEscape`, term clauses)
- Modify: `explorer-web/tests/unit/queries.test.ts`
- Modify: `explorer-web/src/lib/url-state.ts` (+`q` in `BrowseUrlState` + codec)
- Modify: `explorer-web/tests/unit/url-state.test.ts`
- Modify: `explorer-web/src/pages/index.astro` (input markup above the filter groups)
- Modify: `explorer-web/src/scripts/browse.ts` (debounced wiring, popstate restore)
- Modify: `explorer-web/src/lib/format.ts` (label/placeholder constants)
- Modify: `explorer-web/scripts/smoke.mjs` (one scenario)

**Interfaces:**
- `BrowseFilters` gains `q: string` (default `''`). `BrowseUrlState` gains `q: string`.
- Produces in queries.ts: `likeEscape(v: string): string` escaping `\`, `%`, `_` (backslash escape), used with `ESCAPE '\'`; internal `searchConditions(q: string): string[]`: split trimmed `q` on `/\s+/`, take at most 8 terms, each term becomes `(display_name ILIKE '%t%' ESCAPE '\' OR issuer_name ILIKE ... OR title ILIKE ... OR country_name ILIKE ...)` with `t = likeEscape(term)` passed through `sqlQuote`; terms AND together; empty/whitespace `q` contributes no clause. SINGLE SEAM (council finding): the search clauses are appended INSIDE `explicitConditions(f)`, not separately in each builder, so `buildListSql`, `buildStatusCountsSql` (including any FILTER aggregates layered over its WHERE later), and any future builder inherit them by construction. A test asserts the counts SQL carries the q clauses.
- URL param `q` (shared param-name space with the doc page codec is fine; different pages). Decode: trim, cap at 200 chars (silent truncation, no dropped-param notice; free text is not a validated enum). Encode: omit when empty; mechanism (council): add `'q'` to `OWN_KEYS` in `url-state.ts` so the existing delete-then-append loop in `encodeBrowseState` owns it (a stale `q` must not survive when the search clears). `q` changes write history via `replaceState` (typing granularity must not spam the back stack; this is a deliberate exception to the pushState-per-interaction pattern, matching the doc page's `?q=` behavior). Page resets to 0 on `q` change.
- Produces in format.ts: `SEARCH_LABEL = 'Search documents'`, `SEARCH_PLACEHOLDER = 'Issuer, title, or country...'`.
- Input id: `ew-search-input`, wired like the other controls (debounce 250 ms, popstate restores the input value, no-op writes skipped).

**Tasks:** (1) queries tests first: single term hits all four columns; two terms AND; apostrophe in term (`O'Higgins`) escaped by sqlQuote; `%` and `_` neutralized by likeEscape; 9 terms truncate to 8; whitespace-only q adds no clause; counts SQL carries the same clauses. (2) implement queries.ts. (3) url-state tests (round trip, truncation at 200, empty omitted, unknown params still pass through), implement. (4) markup + browse.ts wiring + format constants. (5) smoke scenario: type "Philippines" into `#ew-search-input`, expect row count drops and status line reflects it; reload the resulting URL, state restores. (6) full suite + handoff.

**Edge cases:** q with only `%` (escaped, matches literal percent, zero rows fine); q while country chips active (clauses AND together); popstate to a q-bearing URL before engine ready (existing pendingPop path covers it; verify); IME composition (debounce handles it; no special casing).

**DoD:** `npm test` green with new cases; smoke scenario green; `npx astro check` clean; status line counts match the filtered set (spot-check "Philippines" against a manual DuckDB count on the fixture); URL round-trips.

**Out of scope:** fuzzy matching, ranking, highlighting in the table, corpus-wide full-text search (TEA-907/issue #82), searching document text.

**Stop-and-report:** any need to change the parquet or snapshot; DuckDB ILIKE ESCAPE syntax not behaving as specified (report the observed error verbatim).

---

## B3: Polish batch (M3 + M4 + M5 + B0 cheap wins)

**Goal:** Kill the credibility leaks: placeholder caption, off-voice About copy, wrong link target, Pages "n/a" noise, the high-income dead end, and the PDIP provenance mislabel.

**Executor:** Codex high. Worktree off `main`. Rebase after B2 merges if needed.

**Files:**
- Modify: `explorer-web/src/lib/format.ts` (statsCaption, filingLinkLabel, hint copy, status sentence)
- Modify: `explorer-web/tests/unit/format.test.ts`
- Modify: `explorer-web/src/lib/queries.ts` (`highIncomeExclusionActive` countries-aware; 4th aggregate)
- Modify: `explorer-web/tests/unit/queries.test.ts`
- Modify: `explorer-web/src/scripts/browse.ts` (hint text per cause; new status arg)
- Modify: `explorer-web/src/pages/index.astro` (About copy block, caption, link target)
- Modify: `explorer-web/src/pages/doc/[slug].astro` (Pages row omission, filing label)
- Modify: `explorer-web/src/components/DocText.astro` (+`source` prop, filing label)
- Wrapper: Modify `~/Code/prospectus-web-ti/brand/Header.astro` (logo link split)
- Modify: `explorer-web/scripts/smoke.mjs` (M4 scenario)

**The M4 decision (memo: Teal's decided behavior):** selecting a specific country always shows that country's documents regardless of the high-income exclusion toggle, with a one-line note.
- `highIncomeExclusionActive(f)` becomes: `!f.includeHighIncome && f.incomes.length === 0 && f.countries.length === 0` (signature widens to include `countries` in the Pick).
- `buildStatusCountsSql` adds a 4th aggregate `included_hi_override`: when `!includeHighIncome && countries.length > 0 && incomes.length === 0`, `count(*) FILTER (WHERE <scopeP> AND <IS_HI>)`, else literal `0` (IS_HI constant already exists).
- `statusLine` gains `includedHiByCountry: number | null`; when non-null and > 0 append exactly: ` Showing ${num(n)} high-income documents because their countries are selected.`
- The hi toggle disables with a hint whenever it is overridden; hint copy becomes cause-specific: `HI_OVERRIDE_HINT_INCOME = 'Overridden by the income filter selection.'` (existing copy, renamed) and `HI_OVERRIDE_HINT_COUNTRY = 'Overridden by the country selection.'`; income cause wins when both apply; `applyStateToControls` sets the hint textContent by cause and the disable condition becomes `incomes.length > 0 || countries.length > 0`.

**The copy (paste verbatim):**
- `STATS_CAPTION` is deleted; replaced by `statsCaption(snapshotDate: string): string` returning `Snapshot ${snapshotDate}. Counts cover the full corpus before filters.` `index.astro` passes `stamp.snapshot_date`.
- `filingLinkLabel(source: string | null | undefined): string` returns `'Via PDIP archive'` when `source === 'pdip'`, else `'Original filing'`. Used in `DocText.astro` (new `source` prop, passed from `[slug].astro`) and in the `[slug].astro` metadata row header (row `<th>` uses the same label).
- Pages metadata row: render the row ONLY when `doc.page_count` is a positive number; otherwise omit the row entirely (no more `Pages: n/a`).
- About link fix: `https://tealemery.com` becomes `https://tealinsights.com` (label stays Teal Insights).
- Wrapper `Header.astro`: split the single anchor: the logo `<img>` wraps in `<a href="https://tealinsights.com" rel="noopener" aria-label="Teal Insights home">`; the wordmark keeps `<a href="/" aria-label="Sovereign Prospectus Explorer home">`. Styles keep the flex row.
- CONSEQUENTIAL EDITS the renames force (council; all verified against current code, none optional): (a) `index.astro` line ~7 imports `HI_OVERRIDE_HINT` and renders it at line ~159: the static hint text is now set by `browse.ts` per cause, so the markup keeps an empty `<span id="ew-hi-hint"></span>` and the import goes away; (b) `index.astro` imports `STATS_CAPTION`: becomes `statsCaption` called with `stamp.snapshot_date`; (c) dropping the Q-CRAFT/prototype links orphans the `PROTOTYPE_URL` and `QCRAFT_URL` consts in `index.astro`: delete both; (d) `format.test.ts` references `STATS_CAPTION` and `HI_OVERRIDE_HINT` directly (including in the em-dash guard arrays): update to the new symbols and APPEND the new constants to the guard arrays; (e) `queries.test.ts` calls `highIncomeExclusionActive({includeHighIncome, incomes})` without `countries`: widening the Pick makes those calls type errors; add `countries: []` to the existing calls.
- About block replacement in `index.astro` (the two `<p>`s, the What's next list, and the Help section are replaced with EXACTLY this; `GITHUB_URL` is the existing const):

```astro
<p>
  The Sovereign Prospectus Explorer is an open corpus of sovereign bond
  prospectuses and related filings, collected from the FCA National Storage
  Mechanism, SEC EDGAR, the Luxembourg Stock Exchange, and the Sovereign
  Debt Forum's #PublicDebtIsPublic dataset. Every document links back to its
  source. Built by
  <a href="https://tealinsights.com" target="_blank" rel="noopener noreferrer">Teal Insights</a>
  with support from
  <a href="https://naturefinance.net" target="_blank" rel="noopener noreferrer">NatureFinance</a>.
  <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a> |
  <a href={`${GITHUB_URL}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer">MIT License</a>.
</p>
<p>
  These are public documents, but working with them is not easy: they sit
  scattered across venues, behind slow search interfaces, in inconsistent
  formats. The explorer puts them in one place with fast filtering, readable
  text, and in-document search, so the ten pages that matter in a
  300-page document take minutes to reach, not hours.
</p>
<h3>What's next</h3>
<ul>
  <li>Search across the full text of every document in the corpus</li>
  <li>Automated updates as new prospectuses are filed</li>
  <li>Document-type filters (base prospectus, supplement, final terms)</li>
  <li>
    Clause identification with expert validation, measured against
    expert-annotated baselines before any claim ships
  </li>
</ul>
<h3>Help shape this tool</h3>
<p>
  This is built with and for the people who work with sovereign debt:
  lawyers, investors, officials, and researchers. If it could work better
  for you, <a href="mailto:lte@tealinsights.com">tell us</a> or open an
  issue on
  <a href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer">GitHub</a>.
</p>
```
(The Q-CRAFT and prototype links are dropped deliberately: fewer outbound links, tighter story.)
- Plus any B0 punch list items routed to B3 (each is its own commit; if B0 has not delivered when other items are done, ship without them and note it in the handoff).

**Tasks:** (1) format tests first (statsCaption, filingLinkLabel both arms, both hint constants, statusLine new sentence including suppression when null/0), implement. (2) queries tests (exclusion inactive when countries selected; 4th aggregate present exactly when the condition holds, literal 0 otherwise; AND one test that the counts SQL with BOTH `q: 'bond'` and a selected country carries the search clauses in the WHERE the aggregate sits over, so the override count respects the search; this branch builds ON TOP of merged B2), implement. (3) browse.ts wiring + hint-by-cause + disable condition. (4) Astro templates (About, caption, Pages row, provenance labels, source prop). (5) wrapper Header.astro (separate commit in the wrapper repo). (6) smoke scenario: select a high-income country with the toggle off, rows appear, status contains "because their countries are selected", hi toggle disabled with country hint. (7) full suite + handoff.

**Edge cases:** country selected that is NOT high income (aggregate returns 0, no sentence, toggle still disabled with country hint: acceptable, the override is real even when it changes nothing); countries AND incomes both selected (income hint wins); `page_count === 0` (omit row); source null (label 'Original filing').

**DoD:** `npm test` green including every new format/queries case; smoke green including the M4 scenario; `npx astro check` clean; no `Full corpus.` string anywhere in `explorer-web/src`; `Original filing` appears for a non-PDIP doc and `Via PDIP archive` for a PDIP doc in built HTML (grep the dist fixture build); wrapper Header change builds via `bash scripts/build.sh` with `SNAPSHOT_DIR` pointed at the upstream fixture.

**Out of scope:** fixing PDIP `filing_url` targets themselves (issue #92, data-side, post-Monday); the browse copy-math reconciliation of issue #96 beyond what M4 adds; any About restyling beyond copy (B6 owns the disclosure-box look).

**Stop-and-report:** the wrapper build fails for reasons unrelated to Header.astro; B0 items routed here that require judgment beyond their written spec.

---

## B4: Self-host the DuckDB parquet extension (M6, closes GitHub #97)

**Goal:** The first browse query stops fetching `parquet.duckdb_extension.wasm` from extensions.duckdb.org (availability SPOF, institutional-proxy killer; audit finding 1, 3/3). The extension serves from our own data host.

**Executor:** Opus 4.8 max. Worktree off `main`. This is the ONLY branch allowed to touch the data host, and only to ADD objects.

**Files:**
- Modify: `explorer-web/astro.config.mjs` (env schema: `PUBLIC_EXTENSION_BASE_URL` optional string + the same https validation as PUBLIC_WASM_BASE_URL)
- Modify: `explorer-web/src/lib/config.ts` (export it)
- Modify: `explorer-web/src/lib/duck.ts` (apply the setting)
- Modify: `explorer-web/ARCHITECTURE.md` (update the self-noted item at line ~174)
- Wrapper: Create `~/Code/prospectus-web-ti/scripts/upload-extension.sh`; Modify `README.md` (runbook step); Netlify env var `PUBLIC_EXTENSION_BASE_URL` (set via `netlify env:set`, document in README)
- Modify: `explorer-web/scripts/smoke.mjs` OR a new check: blocked-origin scenario

**Design (mechanism order revised per council; the SET-redirects-autoload behavior is NOT confirmed for duckdb-wasm 1.32.0):** In `duck.ts` `boot()`, immediately after `db.connect()`, if `PUBLIC_EXTENSION_BASE_URL` is set, attempt IN THIS ORDER and keep whichever the local proof (task 3) verifies:
1. PREFERRED, documented for duckdb-wasm: `await conn.query("INSTALL parquet FROM " + sqlQuote(PUBLIC_EXTENSION_BASE_URL)); await conn.query("LOAD parquet")` before the handle returns; deterministic, no reliance on autoload resolution.
2. FALLBACK: `await conn.query("SET custom_extension_repository=" + sqlQuote(PUBLIC_EXTENSION_BASE_URL))` and let `read_parquet` autoload resolve against it.
Import `sqlQuote` from queries.ts (no cycle: queries.ts never imports duck.ts). Default (env unset) behavior is byte-identical to today for open-repo forks. Note for task 1: the extension key is versioned by the DuckDB CORE version inside the wasm build plus the wasm platform (`wasm_eh`/`wasm_mvp`), NOT by the npm package version string; read the exact segments off the observed request URL.

**Tasks:**
- [ ] 1. DISCOVER THE EXACT PATH empirically: run the dev server, open browse with devtools network tab (or a Playwright request log), record the full URL duckdb-wasm 1.32.0 requests from extensions.duckdb.org (shape: `/duckdb-wasm/<duckdb-version>/<bundle>/parquet.duckdb_extension.wasm`). CAUTION (council): DuckDB appends its own `<version>/<platform>/<name>` suffix to whatever base you SET; choose `PUBLIC_EXTENSION_BASE_URL` so that base + the appended suffix equals the mirrored S3 key exactly, or you get a double-path 404. Write the observed URL and the derived base into the branch notes AND into upload-extension.sh as the mirrored key layout. Both `mvp` and `eh` bundle paths if both exist.
- [ ] 2. duck.ts + config + env schema change; `npx astro check` clean; existing tests untouched.
- [ ] 3. LOCAL PROOF (tightened per council, false-positive guard): serve the extension file(s) locally under the mirrored path next to the fixture data server; point `PUBLIC_EXTENSION_BASE_URL` at it; the smoke scenario must use CONTEXT-LEVEL route interception installed BEFORE page creation (worker fetches can escape page-scoped routing) and assert BOTH: zero requests reached `extensions.duckdb.org`, AND at least one `parquet.duckdb_extension.wasm` request hit the `PUBLIC_EXTENSION_BASE_URL` origin, AND rows rendered. Scenario guarded by env var (`SMOKE_EXT_BASE`), skipped when unset.
- [ ] 4. `upload-extension.sh`: downloads the exact extension file(s) from extensions.duckdb.org (curl, checksum echoed), uploads to the data-host S3 bucket under the mirrored layout beneath the existing wasm prefix, `--content-type application/wasm --cache-control "public, max-age=31536000, immutable"`, using the same credential pattern as `upload-snapshot.sh`. Idempotent (`aws s3 cp` overwrite is fine; content is version-keyed).
- [ ] 5. Run the upload for real (this is the sanctioned data-host touch). Set the Netlify env var. Document both in the wrapper README deploy runbook.
- [ ] 6. PRODUCTION PROOF (deploy cadence slot 4: B4 deploys ALONE; the env flip is the change; the pre-agreed revert is `netlify env:unset PUBLIC_EXTENSION_BASE_URL` + redeploy, and live-smoke runs immediately after the deploy): load https://prospectus.tealinsights.com with extensions.duckdb.org blocked in devtools; rows render. Record in the Linear issue. If the deploy happens after your session ends, hand this step to the deploy checklist in your handoff comment.

**Edge cases:** duckdb-wasm requests a bundle-specific path per selected bundle (mirror both mvp and eh); the setting must be applied per-database not per-connection (verify empirically; if a second connection ever appears this is a landmine, note it in ARCHITECTURE.md); extension version must match `@duckdb/duckdb-wasm` 1.32.0 exactly (the build.sh wasm version drift guard pattern is the precedent; add the same guard idea as a comment in upload-extension.sh: re-run the script whenever the duckdb-wasm pin changes).

**DoD:** local blocked-origin smoke green with the env var set; `npm test` + `npx astro check` green; upload executed with the object URL(s) echoed and fetchable (curl 200, content-type application/wasm); Netlify env var set; ARCHITECTURE.md updated; GitHub #97 referenced in the PR body ("Closes #97").

**Out of scope:** self-hosting anything else; changing PUBLIC_WASM_BASE_URL handling; CloudFront config changes; IAM changes (audit finding 6 stays deferred).

**Stop-and-report:** `SET custom_extension_repository` does not redirect the fetch in duckdb-wasm 1.32.0 (report the observed request URLs; do NOT try LOAD/INSTALL rewrites or duckdb-wasm patches); the S3 upload credentials lack PutObject on the required key prefix.

---

## B5: Live smoke + security headers (S2 + S3, EARLY INSURANCE)

**Goal:** A scheduled check that fails loudly if the production origin pair stops rendering rows (the 7/5 CORS incident class), plus security headers that cost nothing and cannot break the site this week.

**Executor:** Codex high. Wrapper repo primarily; worktree there.

**Files:**
- Wrapper: Create `.github/workflows/live-smoke.yml`, `scripts/live-smoke.mjs`; Modify `netlify.toml`, `README.md`

**live-smoke.mjs (node + playwright, no framework):** (1) chromium launches, goto `https://prospectus.tealinsights.com/`, wait up to 120 s for `window.__ewMetrics?.rowsRendered > 0`, assert. (2) CORS regression assertion, exactly the incident class: browser-context `fetch` of `https://data.tealinsights.com/<manifest path as used by the app>` with `cache: 'no-store'` from the page origin must resolve (this is the request shape managed SimpleCORS broke). (3) one doc page loads and `window.__ewDocMetrics` appears. Exit non-zero on any failure with the failed check named. Base URLs from env with these production defaults (`SMOKE_ORIGIN`, `SMOKE_DATA_ORIGIN`).

**live-smoke.yml:** `schedule: cron '17 */6 * * *'` + `workflow_dispatch`; ubuntu-latest; `npm i playwright@1.61.1 && npx playwright install --with-deps chromium`; run the script; no secrets needed. Failure notifies via GitHub's default workflow-failure email.

**netlify.toml headers (verbatim; enforced set is deliberately boring, CSP is REPORT-ONLY this week because wrapper deploy previews are disabled and an enforced-CSP typo would hit production with no rehearsal lane):**

```toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
    X-Frame-Options = "DENY"
    Permissions-Policy = "camera=(), microphone=(), geolocation=()"
    Content-Security-Policy-Report-Only = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://data.tealinsights.com; img-src 'self' data:; font-src 'self'; worker-src 'self' blob:; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
```
A follow-up Linear issue flips CSP to enforced after a clean Report-Only week (checked in the Sunday rehearsal devtools console and post-Monday). Council note for that flip, recorded now: before enforcing, confirm `connect-src` covers the hosts actually configured in `PUBLIC_WASM_BASE_URL` and (post-B4) `PUBLIC_EXTENSION_BASE_URL`; today both are data.tealinsights.com, and an enforce-flip that misses a changed host would undo B4's self-host.

**Tasks:** (1) live-smoke.mjs, run locally against production, all three checks pass (this is the DoD proof; production is live today). (2) Workflow file. (3) Headers block. (4) README runbook note ("live smoke: what it checks, how to run locally, what a failure means"). (5) Handoff. After merge + deploy: `gh workflow run live-smoke.yml` once, confirm green; curl -sI the production origin and confirm the enforced headers present (this lands on the first deploy checklist; note it in the handoff comment).

**Edge cases:** data-host manifest path must match what the app actually fetches (read `upstream/explorer-web/src/lib/snapshot-client.ts` for the exact path; do not guess); Actions runner cold-start flakiness (retry: the workflow uses `timeout-minutes: 15` and the script's own 120 s waits; no auto-retry loops that would mask real failures).

**DoD:** local run against production passes 3/3 checks with output pasted in the PR; workflow YAML lints (actionlint if available, else `gh workflow view` after push); headers block present in netlify.toml exactly as above; README updated.

**Out of scope:** enforced CSP (follow-up issue); SRI; upstream repo changes of any kind; monitoring beyond GitHub's failure email.

**Stop-and-report:** the local run against production fails any check TODAY (that is a live incident, not a branch problem: report immediately, do not fix the site); netlify.toml already contains a conflicting headers block after some other merge.

---

## B6: Design implementation (M8 step 2)

**Goal:** Implement the B0 punch list items routed to B6; re-screenshot both widths; one bounded follow-up round; done. "Made by a firm with designers."

**Executor:** Opus 4.8 max. Worktree off `main` AFTER B1 merges (it restyles the doc page B1 rebuilt).

**Files (expected, final list comes from the punch list):** `explorer-web/src/styles/base.css`, `tokens.css`, `src/pages/index.astro`, `src/pages/doc/[slug].astro`, `src/components/DocText.astro`; wrapper `brand/tokens.css` for brand-token values only. Logic files are off-limits.

**Method:** one commit per punch list item, carrying the item's ID from the punch list doc. After all items: re-screenshot browse + doc at 1440x900 and 390x844 (Playwright), compare against B0's originals, run ONE bounded follow-up round (fixes to items that did not land visually; no new items), stop.

**DoD:** every B6-routed punch list item implemented or explicitly reported back as blocked (no silent drops); `npm test` + `npx astro check` + full smoke green (no logic regressions); Lighthouse accessibility stays 100 and axe reports zero serious/critical on browse + one doc page (local, fixture snapshot, the documented two-origin serve); before/after screenshots at both widths attached to the Linear issue; wrapper token changes (if any) pass `bash scripts/build.sh` token-inventory assert.

**Out of scope:** new punch list items invented mid-branch; anything the punch list routed to WAIT; markup restructuring that changes element ids or the DOM contract of browse.ts/doc-text.ts (those ids are load-bearing; if an item seems to require it, stop and report).

**Stop-and-report:** a punch list item requires changing a load-bearing element id or client-script behavior; a second follow-up round seems needed (the memo caps at one).

---

## B7: Mobile pass (S1)

**Goal:** The two demo screens (browse, doc) work beautifully at phone width; WhatsApp first impressions are mobile.

**Executor:** Opus 4.8 max. After B6 merges.

**Files:** `explorer-web/src/styles/base.css` (media queries), possibly `DocText.astro`/`index.astro` for order/wrap tweaks. No logic files.

**Checklist to satisfy at 390x844 (Playwright emulation, plus one real-phone eyeball noted in the handoff):** no horizontal page scroll on browse or a rendered doc (tables inside `.ew-doc-rendered` scroll within their own container); filter selects and chips wrap cleanly; table remains readable (the existing column set stacks or scrolls gracefully; pick the punch-list-consistent treatment, default: horizontal scroll within `#ew-table-region` with `-webkit-overflow-scrolling: touch`); doc search controls and toggle reachable and tappable (all interactive targets >= 44px in either dimension); TOC usable; 29 MB gate button tappable (regression: the S5 QA fix must survive).

**DoD:** Playwright screenshot set at 390x844 for browse, a rendered doc, and the 29 MB doc attached to the issue; no horizontal scroll assertions added to smoke (viewport-set scenario checking `document.documentElement.scrollWidth <= window.innerWidth` on both pages); full suite + smoke green; axe zero serious/critical at mobile viewport.

**Out of scope:** full responsive redesign; hamburger navigation; touch gestures; anything beyond the two demo screens plus the gate regression.

**Stop-and-report:** a fix requires DOM restructuring of the filter form or table (report with a mockup description instead of doing it).

---

## B8: CSV export of the filtered table (S4)

**Goal:** A "Download CSV" button serializes the CURRENT filtered result set (not just the visible page) with document URLs; analysts live in spreadsheets.

**Executor:** Codex high. After B2 AND B3 merge (export must include the `q` filter and the M4 high-income country override; a CSV that silently omits rows the table shows breaks the S4 promise).

**Files:**
- Create: `explorer-web/src/lib/csv.ts`; `explorer-web/tests/unit/csv.test.ts`
- Modify: `explorer-web/src/lib/queries.ts` (`buildExportSql`), `queries.test.ts`
- Modify: `explorer-web/src/scripts/browse.ts` (button wiring), `src/pages/index.astro` (button markup), `src/lib/format.ts` (labels)

**Interfaces:**
- `buildExportSql(f: BrowseFilters): string`: IDENTICAL WHERE to `buildListSql`, enforced structurally (council finding): first extract the WHERE assembly from `buildListSql` into a shared `listWhereClause(f: BrowseFilters): string` (explicit conditions + search conditions + scope predicate + high-income predicate), make `buildListSql` use it, then `buildExportSql` uses the SAME function. A test asserts the two builders emit byte-identical WHERE clauses for a filter set exercising countries + q + toggles. ORDER BY same as list, NO OFFSET, `LIMIT 10001` (hard cap; the 10,001st row signals truncation). Columns: `slug, display_name, issuer_name, title, strftime(publication_date,'%Y-%m-%d') AS publication_date, country_name, region, income_group, doc_type, source, is_sovereign, filing_url`.
- `toCsv(rows: ExportRow[], siteOrigin: string): { csv: string; truncated: boolean }` in csv.ts: RFC 4180 (CRLF line endings, quote fields containing comma/quote/CR/LF, double embedded quotes); header row `publication_date,issuer,display_name,title,country,region,income_group,doc_type,source,is_sovereign,document_url,filing_url`; `document_url = siteOrigin + '/doc/' + slug + '/'`; if rows.length === 10001, drop the extra row and set `truncated: true`. Prepend nothing (no BOM).
- Button `#ew-export`, label in format.ts: `EXPORT_LABEL = 'Download CSV'`; disabled until `ready`; on click runs the export query, serializes, triggers a Blob download named `prospectus-explorer-export-<snapshotDate>.csv` (snapshotDate from `document.body.dataset.buildSnapshotDate`), announces via `#ew-status`... no: status is the query live region; instead append a transient note via the existing `renderNotice` when truncated: `EXPORT_TRUNCATED_NOTE = 'Export capped at 10,000 rows; narrow the filters for a complete set.'`

**Tasks:** (1) csv.test.ts first: plain row; comma field; quote field; newline field; null handling (empty string); truncation flag at 10001; document_url shape. (2) implement csv.ts. (3) queries test for buildExportSql (cap present, q clauses included, no offset), implement. (4) markup + wiring + labels. (5) smoke scenario: filter to one country, click export... Playwright download capture, parse header + row count > 0. (6) full suite + handoff.

**Edge cases:** zero matching rows (button still works, header-only file); values containing CRLF from titles (quoted); is_sovereign null (empty cell, not "null"); export during in-flight refresh (button uses the current `state`, a stale export is acceptable and unobservable).

**DoD:** all new unit tests green; smoke download scenario green; full suite + `npx astro check` green; manual check: exported file opens in a spreadsheet with correct columns (note it in the PR).

**Out of scope:** Excel-specific BOM/encoding pampering; export of document text; server-side anything.

**Stop-and-report:** Blob download capture proves flaky in the smoke harness after one bounded attempt (ship with unit tests + manual verification noted, report the gap).

---

## SPIKE: CAC identification eval (declared spike, TDD waived, PRIVATE artifact)

**Gate:** starts ONLY when B1-B6 are merged and deployed to production. Killed at the Saturday 2026-07-11 night freeze wherever it stands; no exceptions. If the gate never opens, the spike never runs and the coffee script's "coming next" covers it.

**Executor:** Opus 4.8 max, read-only against the corpus. Approach is designed here; the executor runs it, measures, and writes it up.

**Privacy and placement:** the artifact is a PRIVATE one-pager for the breakfast conversation. It goes to the PCoS Drive folder (`.../Personal Chief of Staff/2026-07-11_CAC-Spike-Eval-OnePager.md`), NEVER to either repo. Working code lives in a local worktree branch that is never pushed; paste any keeper snippets into the one-pager appendix. Nothing references Monday attendees.

**The approach (designed now, not by the executor):**
1. GOLD: locate the PDIP expert annotations in the corpus DuckDB (`corpus.duckdb`; PDIP adapter tables; see `docs/pdip_data_extraction_assessment.md`). Identify the CAC-relevant annotation field(s). Build the gold slice: PDIP documents where the expert annotation marks CAC presence/type AND the document has extracted text in the corpus. Target slice: 30 documents (or all available if fewer). If no usable CAC field exists in the PDIP data: STOP, report what fields DO exist, and end the spike (that finding is itself the artifact).
2. GREP-FIRST CANDIDATES: regex families over document text: "collective action", "modification of the (notes|bonds|conditions)", "meetings of (note|bond)holders", "written resolution", "cross-series modification", "aggregat" + "voting", "reserved matter". Document heuristics: a hit inside the TOC region (before the first heading's offset, or matching a toc entry title) is a TITLE not a clause; risk-factor-section mentions are references, not operative clauses (flag by nearest preceding heading title containing "risk").
3. TARGETED EXTRACTION: for each candidate window (hit +/- 3000 chars), one LLM call (claude-sonnet-5, temperature 0) asking: is an operative CAC clause present; if yes return the verbatim quote of its lead sentence and the classification (single-series / two-limb aggregated / single-limb aggregated / none). ENFORCE `assert exact_quote in raw_text` (domain rule 13: verbatim or it does not count). Page citation via `pages[].offset` where the doc has page offsets; otherwise cite the nearest heading.
4. SCORE: precision/recall vs gold on presence; agreement table on type where gold has type. Report honestly including the confusion cases.
5. ONE-PAGER: BLUF; method in five lines; the P/R table; ONE worked example with verbatim quote, citation, and a live explorer URL; limitations paragraph (initial results framed as initial, small slice, one annotation source); "we measure against expert gold before we ship claims" as the closing line.

**DoD (spike-grade):** the one-pager exists in the PCoS folder with real measured numbers; every quoted extraction passes the exact-substring assert; zero commits to either repo; a fresh-context review session has read the one-pager against the corpus before it is shown at breakfast (runbook rule: spike outputs get fresh-context review).

**Stop-and-report:** no usable gold field (see step 1); the slice assembly exceeds half a day (report and shrink scope to presence-only); ANY temptation to put results in the site UI (hard no per the memo).

---

## M7: Freeze + Sunday rehearsal (Teal, not an executor branch)

Saturday 2026-07-11 night: last wrapper pin bump; tag wrapper + upstream states. Sunday: full demo path on the actual laptop AND phone over the actual hotspot: open site, filter to a coverage country, open a doc, TOC jump, search "pari passu", click the provenance link; WhatsApp the URL to a second phone and open it cold; check devtools console for CSP Report-Only violations (feeds the post-Monday enforce flip); rehearse the Netlify rollback once (deferred TEA-904 item). Sunday ships nothing but reverts.

---

## Council PLAN review disposition (chair: Fable, 2026-07-06 night)

Council as fielded: Codex xhigh (read-only, repo access), Gemini 3.1 Pro High via agy, Opus 4.8 max (fresh external, repo access), chair Fable. Same packet to all (memo + plan, authorship anonymized); focus split: execution breakage / live-site risk / memo coverage + executor-judgment gaps.

**Convergent, fixed:**
- Walking skeleton proved the easy part (marked injection), not the risk (rendered-DOM offset mapping, cross-node highlight, TOC jump). 3/3. Task 1 redefined as a true vertical slice on an EDGAR doc (the pre-mortem's feared source), with a largest-doc render viability sniff pulled forward.
- Raw vs rendered offset mixing (findMatches/snippetAround on rawText while ranges use rendered space). Codex + Opus, independently, with the same failure scenario. Fixed with the ACTIVE-TEXT CONTRACT; task 5 no longer exempts "shared" code from it; smoke asserts the announced snippet quotes rendered text.
- Cross-branch semantic drift: B3's counts aggregate must sit over B2's search seam (Gemini), and B8's export WHERE must match browse including the M4 override (Codex). Fixed: B2 puts search clauses inside `explicitConditions` (single seam); B3 starts after B2 merges with a pinning test; B8 after B2+B3 with a shared `listWhereClause` and a byte-identical-WHERE test.

**Accepted singletons (chair-verified):**
- B4 mechanism unverified as originally specified (Opus, checked against duckdb-wasm docs): design now tries documented `INSTALL parquet FROM ... ; LOAD parquet` first, `SET custom_extension_repository` as fallback, local proof decides; B4 deploys ALONE with a named instant revert (`netlify env:unset`); extension keying corrected to DuckDB core version + wasm platform.
- Stale documented contract (Opus): `env.d.ts`/`ARCHITECTURE.md` single-text-node invariant becomes mode-scoped; B1 authorized and required to amend it.
- Rendered-mode highlight cap semantics and "in this segment" copy (Opus): specified; `highlightCapNoteWhole` added.
- B3 consequential edits (Opus, all five verified against current code) and a genuinely paste-ready About block with exact hrefs.
- Metrics-file merge conflicts (Codex): file pre-created in the batch PR; conflicts on it declared mechanical.
- Blocked-origin proof false positive (Codex): context-level interception before page creation, plus positive assertion on the new origin.
- Conflict-surface table and append-only zones (Opus); B0 punch-list access mechanism (Opus); deploy cadence isolating B1 with the rollback drill moved before it (Opus); `q` in OWN_KEYS (Opus); marked/dompurify pinned exactly at 18.0.5/3.4.11 (Codex).
- Wrapper privacy gap (Opus): accepted in principle; a local wrapper pre-commit hook (grep staged diff + branch name against the same gitignored blocklist) is STAGED FOR TEAL'S HANDS, not installed by the agent (installing executable git hooks is beyond the sanctioned blocklist edit; the exact script and one-command install are in the session handoff). Until installed, the wrapper is covered by discipline, not mechanics.

**Rejected, with reasons on the record:**
- "Missing `data-build-snapshot-date` attribute" (Gemini): the attribute exists at `Base.astro:31`; verified by chair and independently by the Opus seat. No change; B8's prompt notes it exists so nobody re-adds it.
- Inject separator characters into the rendered-text concatenation (Gemini): breaks the 1:1 offset-to-DOM mapping that every Range depends on. Whitespace-only text nodes are included instead (marked emits inter-block newlines), and the residual cross-boundary phrase limitation is documented as accepted.
- Display-time "cleaning" of pages-source plaintext (Opus suggestion, from the memo's "cleaned plaintext view" phrasing): stripping characters at display time desynchronizes every stored TOC/segment offset and violates the verbatim-display principle. Real cleanup is snapshot-side (#95), post-Monday. The demo path is markdown docs, where rendered mode already suppresses the noise.

**Deferred, filed:** CSP enforce flip with the connect-src host check (post-Monday follow-up, noted in B5); #95 pages-text cleanup stays open upstream.
