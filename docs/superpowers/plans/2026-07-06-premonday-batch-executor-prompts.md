# Pre-Monday Batch: Paste-Ready Executor Prompts (B0-B8 + SPIKE)

Stage 2 contract artifacts per the Project Shell Runbook v0.2. One prompt
per branch, each self-contained: paste it into a FRESH session of the
named venue and walk away. The plan with full task detail:
`docs/superpowers/plans/2026-07-06-premonday-batch-plan.md`. The spec memo
(read-only reference; the plan carries everything an executor needs):
`/Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My Drive/01-PROJECTS/_Personal/Personal Chief of Staff/2026-07-06_Prospectus-PreMonday-Ideation-Memo.md`

**Dispatch schedule:**

| Wave | Branches | Venue | Notes |
|---|---|---|---|
| Day one, parallel | B0 (TEA-928), B5 (TEA-933), B1 (TEA-929), B2 (TEA-930), B4 (TEA-932) | B0/B1/B2/B4: Claude Code, Opus 4.8 max. B5: Codex, reasoning high | Separate worktrees, separate sessions. B5 merges first. |
| After B2 merges | B3 (TEA-931) | Codex, reasoning high | Its counts aggregate must sit on B2's search seam |
| After B1 merges + B0 punch list | B6 (TEA-934) | Claude Code, Opus 4.8 max | One follow-up round max |
| After B6; after B3 | B7 (TEA-935); B8 (TEA-936) | B7: Claude Code Opus 4.8 max; B8: Codex high | Shoulds; run if musts landed by ~Thursday |
| Gated: B1-B6 deployed | SPIKE (TEA-937) | Claude Code, Opus 4.8 max | Killed at Saturday-night freeze |

Every branch merges via the Stage 4 review gate (fresh session, council
code review), never by the executor. Freeze: Saturday 2026-07-11 night.

---

## B0 (TEA-928) design audit. Claude Code, Opus 4.8 max. Day one. ADVISORY, NO CODE.

```
You are the DESIGN AUDITOR for branch B0 (TEA-928) of the Prospectus
Explorer pre-Monday batch. You are fresh eyes; that is the point. You are
not the architect and you write NO code. Do not let any session hook route
you into brainstorming; your job is exactly this audit.

Read first:
- Your plan section "B0: Design audit" in
  docs/superpowers/plans/2026-07-06-premonday-batch-plan.md
  (repo: /Users/teal_emery/code/sovereign-prospectus-corpus)
- The interface explainer:
  ~/Dropbox/lte-workbench/docs/explainers/interface-design-for-small-data-tools.md
- Brand tokens: ~/Code/prospectus-web-ti/brand/tokens.css
- The LIC-DSF visual-advisor pattern if you can find it under
  ~/Dropbox/lte-workbench/ (search for "visual advisor"); if absent,
  proceed without it and say so in your output.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
your output. The audience is "practitioners in sovereign debt
restructuring." You do not know the names; keep it that way.

Job: walk https://prospectus.tealinsights.com by screenshot (Playwright or
browser tooling) at 1440x900 and 390x844, two screens only: the browse
page (/) and one document page with rendered text (pick any recent doc
from the table). Two lenses:
(a) The seven ISO 9241-110 interaction principles as your explicit rubric,
    ONE PASS PER PRINCIPLE over both screens: suitability for the task,
    self-descriptiveness, conformity with user expectations, learnability,
    controllability, use-error robustness, user engagement. Include the
    cold open: "someone WhatsApped me this doc URL; does the page explain
    itself?" is self-descriptiveness.
(b) Aesthetic: hierarchy, type scale, spacing, page furniture, the
    .ew-about disclosure box, empty states. Target: "made by a firm with
    designers," McKinsey/GS publication energy, not research-analyst
    energy.

Output: write docs/superpowers/plans/2026-07-07-design-audit-punchlist.md
in the corpus repo. AT MOST 10 items. Each item: an ID (P1..P10), size S
or M only, a CONCRETE change spec (exact CSS/markup/copy change, exact
file when knowable; upstream style files are explorer-web/src/styles/
base.css and tokens.css; brand values live in the wrapper's
brand/tokens.css), and a route to exactly ONE of: B1 (doc-page reading
typography: type scale, measure, line-height, table styling for rendered
text), B3 (cheap copy/CSS wins), B6 (everything else). Anything L-sized
goes to a WAIT list at the bottom, not the 10. End with "What I checked
that came back sound."

Then: commit ONLY that file on branch
lte/tea-928-b0-design-audit-punchlist, push, open a PR titled
"B0 design audit punch list (TEA-928)". Post a handoff comment on TEA-928:
Did / Why / Next (which items routed where) / Pointer (PR + file path).
Append to docs/build-metrics.md: | B0 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT (comment on TEA-928, end session) if: the live site is
down or errors during the walk (do not debug it); you cannot produce
screenshots at both widths.
```

---

## B1 (TEA-929) markdown renderer. Claude Code, Opus 4.8 max. Day one. THE L BRANCH.

```
You are the EXECUTOR for branch B1 (TEA-929): markdown document renderer,
the L branch of the Prospectus Explorer pre-Monday batch. You are not the
architect. Use superpowers:executing-plans. Load operating context from
AGENTS.md in the repo root.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Work in a git worktree (superpowers:using-git-worktrees), branch
lte/tea-929-b1-markdown-renderer, based on current main.
Read YOUR plan section "B1: Markdown document renderer" in
docs/superpowers/plans/2026-07-06-premonday-batch-plan.md and follow its
tasks IN ORDER, test-first (superpowers:test-driven-development). The plan
decides everything: mode rules, the active-text offset contract, interface
signatures, pinned versions (marked 18.0.5, dompurify 3.4.11), edge cases.
If you find yourself making a design decision the plan does not make, that
is a stop-and-report, not a judgment call.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branch names, PRs, or comments. The pre-commit hook
enforces this mechanically; if it blocks you, remove the content. Never
edit docs/private/blocklist.txt and never commit it.

HARD BOUNDARIES: deltas only. Never regenerate the production snapshot,
never touch the data host, the snapshot pipeline (src/corpus/), or
snapshot-client.ts's fetch contract. Plain-mode behavior for pages-source
and segmented docs must be byte-for-byte unchanged. Test fixtures under
explorer-web/tests/fixtures/ MAY be extended via scripts/make_fixture.py.

DEFINITION OF DONE (verbatim from the plan; all of it):
- npm test green including new md-render.test.ts, doc-view.test.ts
  (locateSpan), format.test.ts (labels + announcement).
- npx astro check clean; npm run build succeeds on the fixture snapshot.
- scripts/smoke.mjs green including the new rendered-mode scenarios (among
  them: the live-region announcement quotes the RENDERED snippet for a
  bold-split phrase) and all pre-existing scenarios (plain path
  unregressed).
- Sampling verdict table for 5 docs x 4 sources recorded; no source-level
  failure outstanding.
- Performance numbers recorded in measurements/NOTES.md; all three budgets
  met (renderMs <= 3000 ms on top-3 eligible docs, search <= 500 ms, 29 MB
  doc unchanged behavior).
- Raw-text toggle works both directions with search re-run, verified in
  smoke.
- The documented container contract in env.d.ts and ARCHITECTURE.md is
  amended to be mode-scoped (authorized and required; see the plan's B1
  Files list).
- No change to: snapshot pipeline, snapshot-client.ts fetch contract,
  plain-mode behavior for pages-source and segmented docs, URL schema.

STOP AND REPORT (verbatim from the plan): a whole source renders badly at
the sampling gate; performance budget fails after one bounded attempt (or
the task-1 viability sniff on the largest eligible doc is wildly over
budget); the fixture tooling cannot produce a markdown-rich fixture doc;
any need to touch snapshot-client.ts beyond reading text_source; rebase
conflicts that are not mechanical. Also the standing rule: fail the same
DoD check twice, escalate thinking once, retry once; still failing, STOP.
To stop: post a blocker report on TEA-929 (what you tried, what broke, the
smallest question the architect must answer), end the session. Do not
redesign, do not work around the plan.

Before handoff, self-review: full test suite + smoke output shown fresh
(superpowers:verification-before-completion; no claims without command
output); diff read end to end; no stray files, no console.log, no
em-dashes in any copy or comment; copy strings match the plan verbatim;
plain-mode diff surface is zero outside doc-text.ts's shared seams.
Then: push, open a PR titled "B1: markdown renderer, two-mode doc viewer
(TEA-929)" with the sampling verdict table and performance numbers in the
body. Post on TEA-929: Did / Why / Next (review gate) / Pointer (PR).
Append to docs/build-metrics.md (a conflict there is mechanical, keep both
lines): | B1 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## B2 (TEA-930) find-the-document search. Claude Code, Opus 4.8 max. Day one.

```
You are the EXECUTOR for branch B2 (TEA-930): find-the-document search on
the browse page. You are not the architect. Use
superpowers:executing-plans. Load operating context from AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-930-b2-browse-search, based on current main.
Read YOUR plan section "B2: Find-the-document search on browse" in
docs/superpowers/plans/2026-07-06-premonday-batch-plan.md. Follow its
tasks in order, test-first (superpowers:test-driven-development). The
SINGLE SEAM rule is load-bearing: search clauses go INSIDE
explicitConditions(f) so every SQL builder inherits them; a later branch
builds an aggregate on that seam.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branch names, PRs, or comments. The pre-commit hook
enforces this; if it blocks you, remove the content. Never edit or commit
docs/private/blocklist.txt.

HARD BOUNDARIES: deltas only; no snapshot, pipeline, or data-host changes;
no fuzzy matching, no ranking, no corpus-wide full-text search (that is
TEA-907); URL codec changes limited to the q param exactly as specified
(replaceState for typing, 200-char cap, omitted when empty, page resets
to 0).

DEFINITION OF DONE (verbatim from the plan):
- npm test green with the new cases: single term hits all four columns;
  two terms AND; apostrophe in term escaped; % and _ neutralized by
  likeEscape; 9 terms truncate to 8; whitespace-only q adds no clause;
  counts SQL carries the q clauses; url-state round trip, truncation at
  200, empty omitted, unknown params pass through.
- Smoke scenario green: type "Philippines" into #ew-search-input, row
  count drops and the status line reflects it; reload the resulting URL,
  state restores.
- npx astro check clean.
- Status line counts match the filtered set (spot-check "Philippines"
  against a manual DuckDB count on the fixture).

STOP AND REPORT (verbatim): any need to change the parquet or snapshot;
DuckDB ILIKE ESCAPE syntax not behaving as specified (report the observed
error verbatim). Standing rule: same DoD check fails twice, escalate
thinking once, retry once; still failing, STOP. Blocker report on TEA-930,
end session. No redesigns.

Self-review before handoff: fresh test + smoke output shown
(superpowers:verification-before-completion); diff read; labels and
placeholder match the plan verbatim (SEARCH_LABEL 'Search documents',
SEARCH_PLACEHOLDER 'Issuer, title, or country...'); no em-dashes.
Push, PR "B2: browse search box (TEA-930)". Post on TEA-930:
Did / Why / Next (review gate; B3 unblocks when this merges) / Pointer.
Append to docs/build-metrics.md (conflict = keep both lines):
| B2 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## B3 (TEA-931) polish batch. CODEX, reasoning high. STARTS AFTER B2 MERGES.

```
You are the EXECUTOR for branch B3 (TEA-931): the polish batch (M3+M4+M5)
of the Prospectus Explorer pre-Monday batch. You are not the architect:
implement exactly what the plan says, decide nothing. Load operating
context from AGENTS.md in the repo root. Work test-first: for every
behavior change, write the failing test, see it fail, implement, see it
pass, commit.

PRECONDITION: verify B2 (TEA-930) is merged into main (`git log --oneline
-10 | grep -i "B2"` or check that src/lib/queries.ts contains
searchConditions). If it is not merged, STOP and report on TEA-931.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Create an isolated worktree: from the repo root,
  git worktree add ../spc-wt-tea-931 -b lte/tea-931-b3-polish-batch origin/main
and work there. Second repo (ONE file only): ~/Code/prospectus-web-ti,
brand/Header.astro, on branch lte/tea-931-b3-header-link there.
Read YOUR plan section "B3: Polish batch" in
docs/superpowers/plans/2026-07-06-premonday-batch-plan.md. It contains the
exact copy blocks with full hrefs (paste VERBATIM, character for
character), the exact M4 predicate change, the 4th aggregate spec, the
hint-by-cause wiring, and the enumerated CONSEQUENTIAL EDITS (a)-(e) the
renames force in index.astro, format.test.ts, and queries.test.ts; do all
five, they are not optional.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branch names, PRs, or comments. The pre-commit hook
enforces this; if it blocks you, remove the content. Never edit or commit
docs/private/blocklist.txt.

HARD BOUNDARIES: deltas only; no snapshot/pipeline/data-host changes; do
NOT fix PDIP filing_url targets (issue #92, data-side, post-Monday); do
NOT restyle the About box (B6's job); wrapper changes limited to
brand/Header.astro exactly as specified.

DEFINITION OF DONE (verbatim from the plan):
- npm test green including every new format/queries case (statsCaption,
  filingLinkLabel both arms, both hint constants, statusLine new sentence
  including suppression when null/0; exclusion inactive when countries
  selected; 4th aggregate present exactly when the condition holds,
  literal 0 otherwise; counts SQL with BOTH q and a selected country
  carries the search clauses in the WHERE the aggregate sits over).
- Smoke green including the M4 scenario: select a high-income country with
  the toggle off, rows appear, status contains "because their countries
  are selected", hi toggle disabled with country hint.
- npx astro check clean.
- No "Full corpus." string anywhere in explorer-web/src.
- "Original filing" appears for a non-PDIP doc and "Via PDIP archive" for
  a PDIP doc in built HTML (grep the dist fixture build).
- Wrapper Header change builds via bash scripts/build.sh with SNAPSHOT_DIR
  pointed at the upstream fixture.

STOP AND REPORT (verbatim): the wrapper build fails for reasons unrelated
to Header.astro; B0 punch list items routed here require judgment beyond
their written spec; B2 is not merged. Standing rule: same DoD check fails
twice, escalate reasoning once, retry once; still failing, STOP. Post a
blocker report on TEA-931 (what you tried, what broke, the smallest
question for the architect), end the session. Never redesign.

Self-review: fresh test + smoke + build output shown, no claims without
output; diff read; all copy verbatim against the plan; no em-dashes
anywhere. Push both branches, open PRs "B3: polish batch (TEA-931)" and
(wrapper) "B3: header logo link (TEA-931)". Handoff comment on TEA-931:
Did / Why / Next (review gate) / Pointer (both PRs). Append to
docs/build-metrics.md (conflict there = keep both lines):
| B3 | codex high | <attempts> | <escalations> | pending | <wall time> |
```

---

## B4 (TEA-932) extension self-host. Claude Code, Opus 4.8 max. Day one.

```
You are the EXECUTOR for branch B4 (TEA-932): self-host the DuckDB parquet
extension. You are not the architect. Use superpowers:executing-plans.
Load operating context from AGENTS.md.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-932-b4-extension-self-host, based on current main.
Wrapper repo: ~/Code/prospectus-web-ti (upload-extension.sh, README,
Netlify env), branch lte/tea-932-b4-extension-upload there.
Read YOUR plan section "B4: Self-host the DuckDB parquet extension" in
docs/superpowers/plans/2026-07-06-premonday-batch-plan.md and follow its
tasks in order. Two things the plan decides that you must not re-decide:
(1) MECHANISM ORDER: try the documented
`INSTALL parquet FROM '<base>'; LOAD parquet;` in boot() first;
`SET custom_extension_repository` is the fallback; the local blocked-origin
proof decides which ships. (2) Task 1's CAUTION: DuckDB appends its own
<core-version>/<wasm-platform>/<name> suffix (keyed by the DuckDB CORE
version inside the wasm build, not the npm version string); derive the
base so base + suffix equals the mirrored S3 key exactly.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branches, PRs, or comments. The pre-commit hook enforces
this. Never edit or commit docs/private/blocklist.txt.

HARD BOUNDARIES: this is the ONLY branch allowed to touch the data host,
and only to ADD objects (aws s3 cp of the extension file(s)). No deletes,
no overwrites of existing keys, no CloudFront config changes, no IAM
changes, no changes to PUBLIC_WASM_BASE_URL handling. Default behavior
with the env var unset must remain exactly today's (open-repo forks).

DEFINITION OF DONE (verbatim from the plan):
- Local blocked-origin smoke green with SMOKE_EXT_BASE set: context-level
  route interception installed BEFORE page creation, asserting zero
  requests reached extensions.duckdb.org AND at least one
  parquet.duckdb_extension.wasm request hit the PUBLIC_EXTENSION_BASE_URL
  origin AND rows rendered.
- npm test + npx astro check green.
- Upload executed with the object URL(s) echoed and fetchable (curl 200,
  content-type application/wasm).
- Netlify env var PUBLIC_EXTENSION_BASE_URL set (netlify env:set),
  documented in the wrapper README deploy runbook.
- ARCHITECTURE.md updated (the self-noted extension item).
- PR body says "Closes #97".
- Production proof is a DEPLOY-DAY step on cadence slot 4 (B4 deploys
  ALONE; revert is netlify env:unset PUBLIC_EXTENSION_BASE_URL +
  redeploy, live-smoke runs immediately): if that deploy happens after
  your session, write it into your handoff as the named next step (load
  the live site with extensions.duckdb.org blocked; rows render).

STOP AND REPORT (verbatim): SET custom_extension_repository does not
redirect the fetch in duckdb-wasm 1.32.0 (report the observed request
URLs; do NOT try LOAD/INSTALL rewrites or duckdb-wasm patches); the S3
upload credentials lack PutObject on the required key prefix. Standing
rule: same DoD check fails twice, escalate thinking once, retry once;
still failing, STOP. Blocker report on TEA-932, end session.

Self-review: fresh command output for every DoD line
(superpowers:verification-before-completion); diff read; no em-dashes.
Push both branches, PRs "B4: self-host parquet extension (TEA-932)" and
wrapper "B4: extension upload script + env (TEA-932)". Handoff on
TEA-932: Did / Why / Next (deploy-day production proof + review gate) /
Pointer. Append to docs/build-metrics.md (conflict = keep both lines):
| B4 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## B5 (TEA-933) live smoke + headers. CODEX, reasoning high. FIRST IN.

```
You are the EXECUTOR for branch B5 (TEA-933): scheduled live smoke plus
security headers, the insurance branch that protects every deploy this
week. You are not the architect: implement exactly what the plan says.
Wrapper repo ONLY: ~/Code/prospectus-web-ti. Load its README first.

Create branch lte/tea-933-b5-live-smoke off the wrapper's main (worktree
optional for a single-repo S branch: git worktree add
../pwti-wt-tea-933 -b lte/tea-933-b5-live-smoke).
Read YOUR plan section "B5: Live smoke + security headers" in
/Users/teal_emery/code/sovereign-prospectus-corpus/docs/superpowers/plans/2026-07-06-premonday-batch-plan.md.
It contains the exact three checks, the exact workflow triggers, and the
headers block to paste VERBATIM into netlify.toml (the CSP is
Report-Only ON PURPOSE; do not "improve" it to enforced).

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branches, PRs, or comments.

HARD BOUNDARIES: wrapper repo only; no upstream changes; no enforced CSP;
no SRI; do not touch the existing redirects or font headers in
netlify.toml; the manifest path in the CORS check comes from READING
upstream/explorer-web/src/lib/snapshot-client.ts, not guessing.

DEFINITION OF DONE (verbatim from the plan):
- Local run of scripts/live-smoke.mjs against production passes 3/3 checks
  (rows render via window.__ewMetrics.rowsRendered > 0 within 120 s;
  browser-context fetch of the data-host manifest with cache: 'no-store'
  resolves; one doc page loads with window.__ewDocMetrics present), output
  pasted in the PR body.
- Workflow YAML lints (actionlint if available, else push and
  gh workflow view).
- Headers block present in netlify.toml exactly as the plan specifies.
- README updated: what the smoke checks, how to run locally, what a
  failure means.
- Post-merge steps named in the handoff (they land on the deploy
  checklist): gh workflow run live-smoke.yml once, confirm green; curl -sI
  production and confirm the enforced headers.

STOP AND REPORT (verbatim): the local run against production fails any
check TODAY: that is a LIVE INCIDENT, not a branch problem; report
immediately on TEA-933 and touch nothing. Also: netlify.toml already
contains a conflicting headers block. Standing rule: same DoD check fails
twice, escalate reasoning once, retry once; still failing, STOP with a
blocker report on TEA-933.

Self-review: fresh command output for each DoD line; diff read; headers
byte-identical to the plan block; no em-dashes. Push, PR "B5: live smoke +
security headers (TEA-933)". Handoff on TEA-933: Did / Why / Next
(post-merge workflow run + header curl) / Pointer. Append to the corpus
repo's docs/build-metrics.md (conflict = keep both lines):
| B5 | codex high | <attempts> | <escalations> | pending | <wall time> |
```

---

## B6 (TEA-934) design implementation. Claude Code, Opus 4.8 max. AFTER B1 MERGES.

```
You are the EXECUTOR for branch B6 (TEA-934): implement the B0 design
punch list. You are not the architect and not the auditor: the punch list
is your spec, item by item. Use superpowers:executing-plans. Load
operating context from AGENTS.md.

PRECONDITIONS: B1 (TEA-929) merged to main;
docs/superpowers/plans/2026-07-07-design-audit-punchlist.md exists on
main. If either is missing, STOP and report on TEA-934.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-934-b6-design-implementation, based on current main.
Read YOUR plan section "B6: Design implementation" and the punch list.
Implement ONLY the items routed to B6, ONE COMMIT PER ITEM, commit message
carrying the item ID (e.g. "design: P4 ..."). Then re-screenshot browse +
doc at 1440x900 and 390x844, compare against B0's descriptions, run ONE
bounded follow-up round (fixes to items that did not land visually; no new
items), stop.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branches, PRs, or comments.

HARD BOUNDARIES: styles and template markup only (base.css, tokens.css,
index.astro, doc/[slug].astro, DocText.astro; wrapper brand/tokens.css for
brand token VALUES only, and only if an item says so). The element ids
consumed by browse.ts and doc-text.ts are load-bearing: changing any id or
the DOM contract is out of scope. No logic files. No new punch list items.
Anything the punch list routed to WAIT stays waited.

DEFINITION OF DONE (verbatim from the plan):
- Every B6-routed punch list item implemented or explicitly reported back
  as blocked (no silent drops).
- npm test + npx astro check + full smoke green (no logic regressions).
- Lighthouse accessibility stays 100 and axe reports zero serious/critical
  on browse + one doc page (local, fixture snapshot, the documented
  two-origin serve).
- Before/after screenshots at both widths attached to TEA-934.
- Wrapper token changes (if any) pass bash scripts/build.sh
  token-inventory assert.

STOP AND REPORT (verbatim): a punch list item requires changing a
load-bearing element id or client-script behavior; a second follow-up
round seems needed (the memo caps at one). Standing rule: same DoD check
fails twice, escalate thinking once, retry once; still failing, STOP with
a blocker report on TEA-934.

Self-review: fresh test/smoke/axe output; diff read; per-item commits
clean; no em-dashes. Push, PR "B6: design implementation (TEA-934)" with
the before/after screenshots. Handoff on TEA-934: Did / Why / Next (review
gate; B7 unblocks) / Pointer. Append to docs/build-metrics.md (conflict =
keep both lines):
| B6 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## B7 (TEA-935) mobile pass. Claude Code, Opus 4.8 max. AFTER B6 MERGES.

```
You are the EXECUTOR for branch B7 (TEA-935): the mobile pass on the two
demo screens. You are not the architect. Use superpowers:executing-plans.
Load operating context from AGENTS.md.

PRECONDITION: B6 (TEA-934) merged. If not, STOP and report on TEA-935.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree (superpowers:using-git-worktrees), branch
lte/tea-935-b7-mobile-pass, based on current main.
Read YOUR plan section "B7: Mobile pass". The checklist to satisfy at
390x844: no horizontal page scroll on browse or a rendered doc (tables
inside .ew-doc-rendered scroll within their own container; the browse
table scrolls within #ew-table-region with -webkit-overflow-scrolling:
touch); filter selects and chips wrap cleanly; doc search controls and
view toggle reachable and tappable; all interactive targets on the demo
path >= 44px in at least one dimension; TOC usable; the 29 MB gate button
tappable (the S5 QA regression must survive).

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branches, PRs, or comments.

HARD BOUNDARIES: media queries and CSS in base.css, plus minimal
order/wrap tweaks in DocText.astro or index.astro markup ONLY if CSS
cannot do it. No logic files, no DOM restructuring of the filter form or
table, no element id changes, nothing beyond the two demo screens plus the
gate regression.

DEFINITION OF DONE (verbatim from the plan):
- Playwright screenshot set at 390x844 for browse, a rendered doc, and the
  29 MB doc, attached to TEA-935.
- Smoke gains viewport scenarios asserting
  document.documentElement.scrollWidth <= window.innerWidth on both pages
  at 390x844; full suite + smoke green.
- axe zero serious/critical at the mobile viewport.
- One real-phone eyeball noted in the handoff (or explicitly flagged for
  Teal's Sunday rehearsal if no device available).

STOP AND REPORT (verbatim): a fix requires DOM restructuring of the filter
form or table (report with a mockup description instead of doing it).
Standing rule: same DoD check fails twice, escalate thinking once, retry
once; still failing, STOP with a blocker report on TEA-935.

Self-review: fresh output for each DoD line; diff read; no em-dashes.
Push, PR "B7: mobile pass (TEA-935)". Handoff on TEA-935: Did / Why /
Next (review gate) / Pointer. Append to docs/build-metrics.md (conflict =
keep both lines):
| B7 | opus-4.8 max | <attempts> | <escalations> | pending | <wall time> |
```

---

## B8 (TEA-936) CSV export. CODEX, reasoning high. AFTER B2 AND B3 MERGE.

```
You are the EXECUTOR for branch B8 (TEA-936): CSV export of the current
filtered table. You are not the architect: implement exactly what the plan
says, test-first (failing test, watch it fail, implement, watch it pass,
commit). Load operating context from AGENTS.md in the repo root.

PRECONDITION: B2 (TEA-930) AND B3 (TEA-931) merged into main (check that
src/lib/queries.ts contains searchConditions AND the included_hi_override
aggregate). If not, STOP and report on TEA-936.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree: git worktree add ../spc-wt-tea-936 -b lte/tea-936-b8-csv-export origin/main
Read YOUR plan section "B8: CSV export of the filtered table". The
structural rule is the point: extract the WHERE assembly into a shared
listWhereClause(f) used by buildListSql AND buildExportSql, with a test
asserting byte-identical WHERE output for a filter set exercising
countries + q + toggles. The export can never diverge from what the table
shows.

PRIVACY RULE (hard): Monday attendee names and firms appear nowhere in
code, commits, branches, PRs, or comments.

HARD BOUNDARIES: no BOM or Excel-specific encoding; no export of document
text; no server-side anything; cap LIMIT 10001 with the truncation notice
exactly as specified; filename
prospectus-explorer-export-<snapshotDate>.csv with snapshotDate from
document.body.dataset.buildSnapshotDate (the attribute exists in
Base.astro line 31; do not add it again).

DEFINITION OF DONE (verbatim from the plan):
- All new unit tests green: csv.test.ts (plain row; comma field; quote
  field; newline field; null handling as empty string; truncation flag at
  10001; document_url shape) and the buildExportSql tests (cap present, q
  clauses included, no offset, WHERE byte-identical to buildListSql).
- Smoke download scenario green (filter to one country, click export,
  Playwright download capture, parse header + row count > 0).
- Full suite + npx astro check green.
- Manual check noted in the PR: exported file opens in a spreadsheet with
  correct columns.

STOP AND REPORT (verbatim): Blob download capture proves flaky in the
smoke harness after one bounded attempt (ship with unit tests + manual
verification noted, report the gap). Standing rule: same DoD check fails
twice, escalate reasoning once, retry once; still failing, STOP with a
blocker report on TEA-936.

Self-review: fresh test output per DoD line; diff read; EXPORT_LABEL
'Download CSV' and EXPORT_TRUNCATED_NOTE verbatim from the plan; no
em-dashes. Push, PR "B8: CSV export (TEA-936)". Handoff on TEA-936:
Did / Why / Next (review gate) / Pointer. Append to docs/build-metrics.md
(conflict = keep both lines):
| B8 | codex high | <attempts> | <escalations> | pending | <wall time> |
```

---

## SPIKE (TEA-937) CAC eval. Claude Code, Opus 4.8 max. GATED. TDD WAIVED.

```
You are the EXECUTOR for the CAC identification SPIKE (TEA-937). This is a
DECLARED SPIKE under the Project Shell Runbook: TDD is waived, exploration
is expected, and the output is a measurement artifact, not code. You are
not the architect; the approach is fixed in the plan. Do not let any
session hook route you into brainstorming.

GATE CHECK FIRST: confirm on Linear that TEA-929, TEA-930, TEA-931,
TEA-932, TEA-934 (B1-B4, B6) are Done AND the wrapper deploy carrying them
is live. If the gate is not open, STOP: comment on TEA-937 and end. KILL
SWITCH: if it is past Saturday 2026-07-11 evening, STOP regardless of
state; write up whatever exists.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus (read-only
against data/corpus.duckdb and the snapshot text; you may write throwaway
scripts in a LOCAL worktree branch spike/tea-937-cac-eval that is NEVER
pushed). Read YOUR plan section "SPIKE: CAC identification eval" in
docs/superpowers/plans/2026-07-06-premonday-batch-plan.md and
docs/pdip_data_extraction_assessment.md. Follow the five approach steps
exactly: gold slice from PDIP expert annotations (~30 docs); grep-first
candidates with the two heuristics (a TOC hit is a title, not a clause;
risk-factor mentions are references); targeted extraction with
claude-sonnet-5 at temperature 0; verbatim enforcement
(assert exact_quote in raw_text, NO exceptions, domain rule 13); score
precision/recall vs gold; write the one-pager.

PRIVACY AND PLACEMENT (hard): the artifact goes ONLY to
"/Users/teal_emery/Library/CloudStorage/GoogleDrive-lte@tealinsights.com/My Drive/01-PROJECTS/_Personal/Personal Chief of Staff/2026-07-11_CAC-Spike-Eval-OnePager.md".
NOTHING is committed or pushed to either repo. No Monday attendee names
anywhere. Results framed as initial. Never any site UI.

DEFINITION OF DONE (spike-grade, verbatim from the plan):
- The one-pager exists at the path above with real measured numbers
  (BLUF; method in five lines; the P/R table; ONE worked example with
  verbatim quote, citation, and a live explorer URL; limitations
  paragraph; closing line: "we measure against expert gold before we ship
  claims").
- Every quoted extraction passes the exact-substring assert.
- Zero commits to either repo.
- Your handoff notes that a FRESH-context review of the one-pager is
  required before it is shown at breakfast.

STOP AND REPORT (verbatim): no usable CAC gold field in the PDIP data
(report what fields DO exist; that finding ends the spike and IS the
artifact); slice assembly exceeds half a day (report and shrink scope to
presence-only); ANY temptation to put results in the site UI (hard no).

Handoff on TEA-937: Did / Why (including honest limitations) / Next
(fresh-context review before breakfast) / Pointer (Drive path). Append to
docs/build-metrics.md ON MAIN via a note in the handoff comment instead of
a commit (this branch never pushes):
| SPIKE | opus-4.8 max | <attempts> | <escalations> | n/a | <wall time> |
```
