# S3 Explorer Core Parity (TEA-903) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. THIS RUN: executed inline per CLAUDE.md Phase 3 (plan is transcription-grade; context already cached), with code-reviewer gates after major components.

**Goal:** Bring explorer-web/ to v1 Shiny parity (P1-P22 checklist in the spec) plus shareable filter URLs, working back/forward, instant filtering, and a sensible mobile layout, verified against the full snapshot with Lighthouse 90+ on browse.

**Architecture:** All new logic lands in pure, DOM-free lib modules (`doc-view.ts` segment/search math, `url-state.ts` codec, extended `queries.ts` SQL, `format.ts` copy, `build-data.ts` aggregations); the two client scripts are rewritten wholesale as thin consumers (their disposable-by-contract status). Static shell (stats, About, filter options, labels) is baked at build time; DuckDB init stays deferred past first paint.

**Tech Stack:** Astro 6.4.8 (pinned), @duckdb/duckdb-wasm 1.32.0 (exact), hyparquet (build-time), vitest, Playwright smoke via scripts/smoke.mjs, @axe-core/playwright (NEW dev dep).

**Spec:** `docs/superpowers/specs/2026-07-04-explorer-core-parity-design.md` (council-gated; its Disposition section is binding).

## Global Constraints

- Node >= 22.12; run all npm commands from `explorer-web/`.
- No em-dash characters anywhere (user-facing copy is test-guarded; also none in code comments, docs, commits).
- Every style value is a `--ew-*` custom property in `tokens.css`; base.css and components consume tokens only. No Teal Insights brand/fonts.
- `lib/queries.ts` owns ALL SQL. Client scripts: zero SQL, zero fetch, zero URL assembly.
- Only `toc[].offset_utf16` is ever consumed; never code-point `offset`, never `pages[]`.
- Thresholds (single source: constants in `doc-view.ts` / `doc-text.ts`): full-render max 1,000,000 UTF-16 units; segment target 500,000; click-gate 5,000,000 bytes (existing); min query length 2; match compute cap 20,000; rendered highlight cap 2,000/segment; TOC filter input appears over 100 entries; page size 50.
- URL params: `country`/`region`/`income`/`source` repeated keys; `hi=1`; `scope=all`; `page` 1-based (omitted at 1); doc `q`. Unknown params pass through verbatim on every write.
- History: interactions pushState then render from URL; corrections replaceState; popstate never writes; debounced writes cancelled on popstate/pagehide; no-op writes skipped; history calls try/catch (WebKit: 100 writes/10 s).
- The word "Part" never appears in segment UI copy ("Segment k of n").
- CI runs against the committed fixture; full snapshot runs are local (`SNAPSHOT_DIR=../data/snapshot`). Never run `parse --source all`.
- Long builds: nohup + Monitor on a file condition (the harness kills long shells).

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `explorer-web/scripts/make_fixture.py` | Modify | Add synthetic shapes: inflated text_bytes, astral-before-TOC doc, >1M-unit segmented doc (issue #88) |
| `explorer-web/tests/fixtures/snapshot/*` | Regenerate | Committed fixture |
| `explorer-web/src/lib/format.ts` | Modify | All new user-facing copy + sourceDisplay + status matrix templates |
| `explorer-web/src/lib/build-data.ts` | Modify | computeStats + computeFilterOptions (pure over DocRow[]) |
| `explorer-web/src/lib/queries.ts` | Modify | New BrowseFilters, WHERE builder with interplay + COALESCE, status-counts SQL; drop now-unused builders |
| `explorer-web/src/lib/url-state.ts` | Create | Pure URL codec (browse state + doc q), unknown-param passthrough |
| `explorer-web/src/lib/doc-view.ts` | Create | Pure segment math + search-match math |
| `explorer-web/src/styles/tokens.css` | Modify | New tokens + ::highlight rules (literal var() fallbacks) |
| `explorer-web/src/styles/base.css` | Modify | Chips, filter row, accent-color, border-strong, tap targets, mobile rules, overflow rails |
| `explorer-web/src/pages/index.astro` | Rewrite | Static shell: subtitle, stats, About, filters (baked options), toggles, vintage note, table, pagination |
| `explorer-web/src/scripts/browse.ts` | Rewrite | Browse client: chips, history discipline, status matrix, focus rules |
| `explorer-web/src/pages/doc/[slug].astro` | Modify | Back-link, pass text_source/page_count to DocText |
| `explorer-web/src/components/DocText.astro` | Rewrite | Search UI, TOC details + filter, segment nav, live region, notes |
| `explorer-web/src/scripts/doc-text.ts` | Rewrite | Doc client: modes, gate, TOC, search, highlights, navigation, q param |
| `explorer-web/src/env.d.ts` | Modify | __ewDoc contract + new window metric fields |
| `explorer-web/scripts/smoke.mjs` | Extend | Filter/URL/back-forward/doc/search/segment/gate scenarios + axe |
| `explorer-web/package.json` | Modify | Add `@axe-core/playwright` dev dep |
| `explorer-web/ARCHITECTURE.md` | Modify | S3 decisions, __ewDoc contract, token inventory note |
| `explorer-web/tests/unit/{format,build-data,queries}.test.ts` | Extend/rewrite | Match new interfaces |
| `explorer-web/tests/unit/{url-state,doc-view,fixture-shapes}.test.ts` | Create | New pure-logic tests |

Execution order: Task 1 (fixture) first per issue #88; then pure libs (2-6), styles (7), browse page (8), doc page (9), smoke (10), docs (11), full-snapshot verification (12), parity pass (13).

---

### Task 1: Fixture text-scale shapes (issue #88)

**Files:**
- Modify: `explorer-web/scripts/make_fixture.py`
- Create: `explorer-web/tests/unit/fixture-shapes.test.ts`
- Regenerate: `explorer-web/tests/fixtures/snapshot/`

**Interfaces:**
- Produces fixture docs with stable slugs: `synthetic-gate` (inflated text_bytes > 5,000,000, tiny real JSON), `synthetic-astral` (astral char before a TOC entry, `offset != offset_utf16`), `synthetic-large` (> 1,000,000 UTF-16 units, >= 8 TOC entries incl. one section > 500,000 units, so segmented mode and oversized-cut are CI-reachable). MANIFEST `document_count`/`text_file_count` consistent.

- [ ] **Step 1: Write failing test** `tests/unit/fixture-shapes.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';
import { describe, expect, it } from 'vitest';

const FIX = new URL('../fixtures/snapshot/', import.meta.url).pathname;
const readDoc = (slug: string) =>
  JSON.parse(readFileSync(`${FIX}text/${slug}.json`, 'utf8'));

async function rows() {
  const file = await asyncBufferFromFile(`${FIX}documents.parquet`);
  return (await parquetReadObjects({ file })) as Record<string, unknown>[];
}

it('has a gate-scale row with inflated text_bytes and a small file', async () => {
  const r = (await rows()).find((x) => x.slug === 'synthetic-gate');
  expect(Number(r!.text_bytes)).toBeGreaterThan(5_000_000);
  expect(readDoc('synthetic-gate').text.length).toBeLessThan(10_000);
});

it('has an astral doc where a toc offset diverges from offset_utf16', () => {
  const doc = readDoc('synthetic-astral');
  const diverging = doc.toc.find((e: any) => e.offset !== e.offset_utf16);
  expect(diverging).toBeDefined();
  // the utf16 offset must point at the heading text in JS string space
  expect(doc.text.slice(diverging.offset_utf16, diverging.offset_utf16 + 2)).toBe('##');
});

it('has a segment-scale doc (>1M units, one oversized section)', () => {
  const doc = readDoc('synthetic-large');
  expect(doc.text.length).toBeGreaterThan(1_000_000);
  expect(doc.toc.length).toBeGreaterThanOrEqual(8);
  const offs = doc.toc.map((e: any) => e.offset_utf16);
  const gaps = offs.slice(1).map((o: number, i: number) => o - offs[i]);
  expect(Math.max(...gaps, doc.text.length - offs[offs.length - 1])).toBeGreaterThan(500_000);
});
```

- [ ] **Step 2: Run** `npm test -- fixture-shapes` from `explorer-web/`. Expected: FAIL (files missing).

- [ ] **Step 3: Implement in `make_fixture.py`.** Add a `SYNTHETIC_DOCS` section after the real-doc copy: three dicts built in Python and written as both parquet rows (append via a second DuckDB `INSERT ... VALUES` into a temp table unioned before COPY, `source='synthetic'`, `is_sovereign=NULL`, `country_name='Synthetic'`, all synthetic rows clearly marked via `doc_type='SYNTHETIC FIXTURE'`) and text JSONs matching the snapshot text schema (`schema_version, slug, text, toc, pages: [], text_source: 'markdown', ...metadata`). Shapes:
  - `synthetic-gate`: text `"gate fixture\n" * 20`, parquet `text_bytes=6_000_000` (metadata deliberately inflated; comment says the gate reads only metadata), `has_text=true`.
  - `synthetic-astral`: text `"intro \U0001F4C4 emoji front matter\n\n## Heading A\nbody a\n\n## Heading B\nbody b\n"`; toc entries computed in Python with `offset` = code-point index of each `##` and `offset_utf16` = index + count of astral chars before it (mirrors `src/corpus/snapshot.py` logic).
  - `synthetic-large`: sections built from a repeated sentence; 7 sections of ~90K units + one 600K-unit section + 100K tail; toc entries at each `## Section N` with correct offsets; total ~1.05M units. Repetitive text compresses well in git.
  - MANIFEST counts updated to include synthetics; bump `MAX_FIXTURE_BYTES` to `4_500_000` with a comment (synthetic-large is ~1.05 MB raw).

- [ ] **Step 4: Regenerate + verify.** Run from repo root: `uv run python explorer-web/scripts/make_fixture.py` then `npm test -- fixture-shapes` (PASS) and the full `npm test` (existing snapshot-client/build-data tests must still pass against the regenerated fixture).

- [ ] **Step 5: Commit** `feat(explorer-web): fixture text-scale shapes (gate, astral, segment) closes #88 groundwork`

### Task 2: format.ts copy + sourceDisplay + status matrix

**Files:**
- Modify: `explorer-web/src/lib/format.ts`
- Test: `explorer-web/tests/unit/format.test.ts` (extend)

**Interfaces (produced, exact):**

```ts
export const SOURCE_DISPLAY_NAMES: Record<string, string>; // edgar/nsm/luxse/pdip -> SEC EDGAR / FCA NSM / Luxembourg Stock Exchange / #PublicDebtIsPublic
export function sourceDisplay(key: string | null | undefined): string; // falls back to key or 'n/a'
export interface StatusLineArgs { matching: number; shownFrom: number; shownTo: number; page: number; pages: number; hiddenScope: number | null; hiddenHi: number | null; hiOverride: boolean; }
export function statusLine(a: StatusLineArgs): string;
export const EMPTY_STATE: string; // 'No documents match these filters.'
export function browseSubtitle(sovereign: number, related: number): string; // 'Browse S sovereign bond prospectuses and R related filings.'
export const STATS_CAPTION: string; // 'Full corpus.'
export function segmentLabel(k: number, n: number): string; // 'Segment k of n'
export const SEGMENTS_NOTICE: string; // display convenience, not document structure, do not cite
export function matchCountCopy(total: number, capped: boolean, query: string): string; // '128 matches for "x".' / '20,000+ matches for "x"; refine your search.'
export function matchPositionCopy(i: number, n: number, snippet: string): string; // 'Match 3 of 128: ...snippet...'
export function absenceCopy(query: string): string; // soft literal-search wording per spec
export const MIN_QUERY_HINT: string; // 'Enter at least 2 characters to search.'
export const DROPPED_PARAM_NOTICE: string;
export const PAGES_NOT_DISPLAYED_NOTE: string;
export const HIGHLIGHT_SUPPORT_NOTE: string;
export const HI_OVERRIDE_HINT: string; // 'Overridden by the income filter selection.'
export const HI_TOGGLE_LABEL: string; // 'Include high-income countries'
export function chipRemoveLabel(name: string): string; // 'Remove Kenya'
export function highlightCapNote(cap: number): string; // 'Showing the first 2,000 highlights in this segment.'
export const TOC_FILTER_PLACEHOLDER: string; // 'Filter contents...'
export const FRONT_MATTER_LABEL: string; // '(Front matter)'
```

Existing exports stay (WB_VINTAGE_NOTE, PROVENANCE_NOTE, NO_PAGE_ANCHORS_NOTE, formatDate, formatBytes, orNA, sovereignBadge, loadGateLabel, citeAs, scopeToggleLabel). `scopeStatus`/`scopeAllStatus`/`filteredStatus` are DELETED (replaced by statusLine); their tests are replaced.

- [ ] **Step 1: Write failing tests** covering: statusLine composition for the four scope states + override sentence + range text ("N documents match, newest first (showing A to B). Page k of n." + optional sentences per spec matrix); EMPTY_STATE exact string; sourceDisplay mapping and fallback; segmentLabel/matchCountCopy capped and uncapped; absenceCopy contains the query and the word 'literal'; and extend the existing em-dash guard to scan EVERY exported string constant and every function output exercised in tests (loop over module exports).
- [ ] **Step 2: Run** `npm test -- format` FAIL.
- [ ] **Step 3: Implement.** Pure string templates, `toLocaleString('en-US')` for counts, no em-dashes.
- [ ] **Step 4: Run** PASS.
- [ ] **Step 5: Commit** `feat(explorer-web): S3 copy layer (source names, status matrix, segment/search strings)`

### Task 3: build-data.ts aggregations

**Files:**
- Modify: `explorer-web/src/lib/build-data.ts`
- Test: `explorer-web/tests/unit/build-data.test.ts` (extend)

**Interfaces (produced):**

```ts
export interface CorpusStats { docs: number; sources: number; issuers: number; sovereign: number; related: number; }
export function computeStats(rows: DocRow[]): CorpusStats; // issuers = distinct non-null issuer_name; sovereign = is_sovereign === true; related = docs - sovereign
export interface CountryOption { code: string; name: string; }
export interface FilterOptions { countries: CountryOption[]; regions: string[]; incomes: string[]; sources: string[]; }
export function computeFilterOptions(rows: DocRow[]): FilterOptions;
// countries: distinct non-null code+name pairs sorted by name; regions/incomes: distinct with null -> 'Unknown', sorted; sources: distinct sorted keys
```

- [ ] **Step 1: Failing tests** with hand-built DocRow arrays (nulls, duplicates, Unknown materialization, sort order) + one test loading the real fixture parquet asserting synthetic rows are included in counts (docs count matches MANIFEST document_count).
- [ ] **Step 2:** FAIL. **Step 3:** Implement (pure, no I/O; callers pass `await loadDocuments()`). **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): build-time stats and filter options`

### Task 4: queries.ts filter model

**Files:**
- Modify: `explorer-web/src/lib/queries.ts`
- Test: `explorer-web/tests/unit/queries.test.ts` (rewrite affected tests)

**Interfaces (produced):**

```ts
export interface BrowseFilters {
  countries: string[]; regions: string[]; incomes: string[]; sources: string[];
  includeNonSovereign: boolean; includeHighIncome: boolean;
  page: number; pageSize: number; // page 0-based internally
}
export function highIncomeExclusionActive(f: Pick<BrowseFilters,'includeHighIncome'|'incomes'>): boolean; // !includeHighIncome && incomes.length === 0
export function buildListSql(f: BrowseFilters): string;
export function buildStatusCountsSql(f: BrowseFilters): string; // -> { matching, hidden_scope, hidden_hi } ::INTEGER
```

`createDocsViewSql`, `sqlQuote`, `runQuery` stay. `buildCountSql`, `buildScopeCountsSql`, `buildDistinctSql` are DELETED (options baked at build; counts come from buildStatusCountsSql).

Predicates (exact):
- countries: `country_code IN (...)`; sources: `source IN (...)`
- regions: `COALESCE(region, 'Unknown') IN (...)`; incomes: `COALESCE(income_group, 'Unknown') IN (...)`
- scope: `is_sovereign = true` when NOT includeNonSovereign
- high-income exclusion (only when `highIncomeExclusionActive`): `COALESCE(income_group, 'Unknown') != 'High income'`

buildStatusCountsSql shape:

```sql
SELECT
  count(*) FILTER (WHERE <scopeP> AND <hiP>)::INTEGER AS matching,
  count(*) FILTER (WHERE <hiP> AND <notScope>)::INTEGER AS hidden_scope,
  count(*) FILTER (WHERE <scopeP> AND <isHi>)::INTEGER AS hidden_hi
FROM docs <WHERE explicit filters only>
```

where `<scopeP>` is the scope predicate or TRUE; `<hiP>` the exclusion predicate or TRUE; `<notScope>` is `is_sovereign IS DISTINCT FROM true` when scope is active else FALSE; `<isHi>` is `COALESCE(income_group,'Unknown') = 'High income'` when the exclusion is active else FALSE.

- [ ] **Step 1: Failing tests:** multi-value IN lists with quoting (Cote d'Ivoire), COALESCE guard present in region/income/hi predicates, interplay rule (incomes selected drops the hi clause; `highIncomeExclusionActive` truth table), scope on/off, ORDER BY pinned, LIMIT/OFFSET arithmetic, status-counts SQL contains the three FILTER clauses and flips to FALSE arms correctly.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS + `npx astro check` clean. **Step 5: Commit** `feat(explorer-web): filter model SQL (multi-select, interplay rule, status counts)`

### Task 5: url-state.ts codec

**Files:**
- Create: `explorer-web/src/lib/url-state.ts`
- Test: `explorer-web/tests/unit/url-state.test.ts`

**Interfaces (produced):**

```ts
export interface BrowseUrlState { countries: string[]; regions: string[]; incomes: string[]; sources: string[]; includeHighIncome: boolean; includeNonSovereign: boolean; page: number; } // page 0-based
export interface KnownOptions { countries: string[]; regions: string[]; incomes: string[]; sources: string[]; }
export function decodeBrowseState(search: string, known: KnownOptions): { state: BrowseUrlState; droppedAny: boolean };
export function encodeBrowseState(currentSearch: string, state: BrowseUrlState): string; // returns query string WITHOUT leading '?', '' if empty
export function decodeDocQuery(search: string): string;
export function encodeDocQuery(currentSearch: string, q: string): string;
```

Rules (exact): repeated keys via `getAll`; values not in `known` dropped (`droppedAny` true); `page` URL value is 1-based, invalid/absent -> 0 internal, `<1` or NaN counts as dropped; encode deletes only the known keys (`country,region,income,source,hi,scope,page` / `q`) from `currentSearch` then appends its own, so unknown params survive verbatim; `page` written as `page+1` only when `page > 0`; `hi=1` only when includeHighIncome; `scope=all` only when includeNonSovereign; empty q removes the key.

- [ ] **Step 1: Failing tests:** round-trip identity; unknown param (`utm=x`, `search=y`) survives encode after state change; invalid country dropped with flag; 1-based page mapping both directions; hi/scope booleans; doc q round-trip preserving unknowns; encode ordering stable (no-op detection: encoding an unchanged state over its own URL returns an equal query string).
- [ ] **Step 2:** FAIL. **Step 3:** Implement with `URLSearchParams` only. **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): URL state codec (repeated params, passthrough, 1-based page)`

### Task 6: doc-view.ts (segment math + search math)

**Files:**
- Create: `explorer-web/src/lib/doc-view.ts`
- Test: `explorer-web/tests/unit/doc-view.test.ts`

**Interfaces (produced, exact):**

```ts
export interface SegmentConfig { fullRenderMax: number; segmentTarget: number; }
export const DEFAULT_SEGMENT_CONFIG: SegmentConfig; // { fullRenderMax: 1_000_000, segmentTarget: 500_000 }
export interface TocEntryLike { level: number; title: string; offset_utf16: number; }
export interface Segment { start: number; end: number; } // [start, end) UTF-16
export function sanitizeToc(toc: TocEntryLike[], textLength: number): TocEntryLike[]; // sorted, deduped by offset, in-range only
export function needsSegments(textLength: number, cfg?: SegmentConfig): boolean;
export function computeSegments(text: string, toc: TocEntryLike[], cfg?: SegmentConfig): Segment[];
export function segmentForOffset(segments: Segment[], offset: number): number; // clamped index

export interface SearchLimits { minQueryLength: number; maxMatches: number; }
export const DEFAULT_SEARCH_LIMITS: SearchLimits; // { minQueryLength: 2, maxMatches: 20_000 }
export function buildSearchPattern(query: string, limits?: SearchLimits): RegExp | null; // null if trimmed too short
export interface SearchMatches { starts: number[]; ends: number[]; capped: boolean; }
export function findMatches(text: string, query: string, limits?: SearchLimits): SearchMatches | null;
export function countsByBins(starts: number[], binStarts: number[]): number[]; // binStarts sorted; bin i owns [binStarts[i], binStarts[i+1])
export function snippetAround(text: string, start: number, end: number, context?: number): string; // default 40 chars each side, whitespace collapsed
```

Core algorithm (complete, to transcribe):

```ts
function findCut(text: string, from: number, at: number): number {
  const nl = text.lastIndexOf('\n', at - 1);
  if (nl > from) return nl + 1;
  const c = text.charCodeAt(at - 1);
  return c >= 0xd800 && c <= 0xdbff ? at - 1 : at; // never split surrogate pair
}

export function computeSegments(text, toc, cfg = DEFAULT_SEGMENT_CONFIG): Segment[] {
  const len = text.length;
  const starts = [0, ...sanitizeToc(toc, len).map(e => e.offset_utf16).filter(o => o > 0)];
  const segs: Segment[] = [];
  let segStart = 0;
  for (let i = 1; i <= starts.length; i++) {
    const next = i < starts.length ? starts[i] : len; // end of section i-1
    if (next - segStart <= cfg.segmentTarget) continue; // keep packing
    const prev = starts[i - 1];
    if (prev > segStart) { segs.push({ start: segStart, end: prev }); segStart = prev; }
    while (next - segStart > cfg.segmentTarget) {
      const cut = findCut(text, segStart, segStart + cfg.segmentTarget);
      if (cut <= segStart) break; // safety: cannot advance
      segs.push({ start: segStart, end: cut });
      segStart = cut;
    }
  }
  if (segStart < len || segs.length === 0) segs.push({ start: segStart, end: len });
  return segs;
}
```

Pattern builder (complete):

```ts
export function buildSearchPattern(query, limits = DEFAULT_SEARCH_LIMITS): RegExp | null {
  const q = query.trim();
  if ([...q].length < limits.minQueryLength) return null;
  let src = '';
  for (const ch of q) {
    if (/\s/.test(ch)) { if (!src.endsWith('\\s+')) src += '\\s+'; }
    else if (ch === "'") src += "['\\u2018\\u2019]";
    else if (ch === '"') src += '["\\u201C\\u201D]';
    else src += ch.replace(/[.*+?^${}()|[\]\\\/]/, '\\$&');
  }
  return new RegExp(src, 'gi');
}
```

findMatches: exec loop, zero-length guard (`if (m[0].length === 0) { re.lastIndex++; continue; }`), push bare numbers, stop at `maxMatches` with `capped = true`.

- [ ] **Step 1: Failing tests (this is the largest test file; write all of these):**
  - packing: sections pack until target; segment closes at section boundary; oversized single section cut at newline; no-newline window hard-cuts; hard cut never splits a surrogate pair (text of repeated emoji); no-TOC text gets fixed cuts; empty toc + short text yields one segment; segments tile the text exactly (invariant: seg[0].start=0, seg[i].end=seg[i+1].start, last end=len) via a property-style loop over generated cases; front matter before first entry stays in segment 1; unsorted/duplicate/out-of-range toc offsets sanitized; tail after last entry cuttable.
  - segmentForOffset: exact boundaries, clamping.
  - search: case-insensitive; whitespace-flexible ("collective action clauses" matches "collective action\nclauses"); typographic apostrophe ("Noteholders' meetings" query with straight quote matches U+2019 text); regex metacharacters literal ("10.5%" matches only literally); min length (1 char -> null, whitespace-only -> null); cap honored with capped flag; zero-length safety; offsets are UTF-16-true on astral text (match after an emoji lands at the JS index: assert `text.slice(start, end)` equals the matched surface).
  - countsByBins sums to starts.length across bins including bin 0 (front matter); snippetAround collapses newlines and clips at text ends.
- [ ] **Step 2:** FAIL. **Step 3:** Implement per code above. **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): doc-view segment and search math (pure, DOM-free)`

### Task 7: Tokens and base styles

**Files:**
- Modify: `explorer-web/src/styles/tokens.css`, `explorer-web/src/styles/base.css`

**Interfaces:** New tokens (exact names; initial values, tuned visually in Task 12): `--ew-color-border-strong: #6b7684` (>= 3:1 on white, target ~4.5:1); `--ew-color-match-bg: #ffe08a`; `--ew-color-match-text: #1a2129`; `--ew-color-match-current-bg: #f0a84b`; `--ew-color-match-current-text: #1a2129`; `--ew-font-size-doc: 0.875rem` (media query in tokens.css raises to 0.9375rem under 640px); `--ew-filters-min-height: 8rem`; `--ew-chips-min-height: 2.25rem`; `--ew-tap-target: 44px`.

- [ ] **Step 1:** Add tokens + the `::highlight()` rules to tokens.css (they live here so S4's swap reaches them; literal fallbacks are the pre-Chrome-134 escape hatch):

```css
::highlight(ew-match) {
  background-color: var(--ew-color-match-bg, #ffe08a);
  color: var(--ew-color-match-text, #1a2129);
}
::highlight(ew-match-current) {
  background-color: var(--ew-color-match-current-bg, #f0a84b);
  color: var(--ew-color-match-current-text, #1a2129);
}
```

- [ ] **Step 2:** base.css additions, tokens only: `input, select, button { border-color: var(--ew-color-border-strong); }` (keep `--ew-color-border` for table row rules); `input[type='checkbox'] { accent-color: var(--ew-color-accent); }` (progressive enhancement per spec); `.ew-chip` row styles + `.ew-chip button` with min sizes; `.ew-filters` grid with `min-height: var(--ew-filters-min-height)`; `.ew-chips { min-height: var(--ew-chips-min-height); }`; `#ew-table-region { overflow-x: auto; }`; `@media (max-width: 640px)`: hide `.ew-col-type, .ew-col-source` (th and td), interactive controls `min-height: var(--ew-tap-target)`; `#ew-doc-text { overflow-wrap: anywhere; font-size: var(--ew-font-size-doc); }` (DocText inline style moves here).
- [ ] **Step 3:** `npx astro check` + `npm test` still green (no JS contract change). Visual check deferred to Task 8/9 dev runs.
- [ ] **Step 4: Commit** `feat(explorer-web): S3 tokens (contrast, highlights, reservations) and control styles`

### Task 8: Browse page (index.astro + browse.ts rewrite)

**Files:**
- Rewrite: `explorer-web/src/pages/index.astro`, `explorer-web/src/scripts/browse.ts`
- Modify: `explorer-web/src/env.d.ts` (metrics fields unchanged; keep)

**Interfaces:**
- Consumes: Task 2 copy, Task 3 aggregations, Task 4 SQL, Task 5 codec, existing duck/snapshot-client/urls/dom.
- Produces DOM contract (ids the smoke test uses): `#ew-filters` (form, submit-preventDefault), four groups each `#ew-filter-<key>-select` + `#ew-filter-<key>-chips` (key: country|region|income|source), `#ew-hi-toggle` + `#ew-hi-hint`, `#ew-scope-toggle` (label text build-stamped via `scopeToggleLabel(related)`), `#ew-status` (aria-live polite), `#ew-browse-notices`, `#ew-table`, `#ew-rows`, `#ew-prev`, `#ew-next` (aria-disabled pattern, never `disabled` once enabled).

index.astro static shell (build-time via `loadDocuments()` + `computeStats` + `computeFilterOptions` + format copy): h1 + `browseSubtitle(stats.sovereign, stats.related)`; three stat cards (Documents/Sources/Issuers values + `STATS_CAPTION`); `<details>` About (v1 content: intro with Teal Insights + NatureFinance + GitHub + MIT text links, "What's next?" list, "Help shape this tool" list, contact links; NO logos/fonts); filter row: four labeled selects with baked `<option>` lists (country options `value=code`, label=name; prompt option "Add country..." etc.) each preceded by an empty chips `<ul>`; the two toggle checkboxes with `HI_TOGGLE_LABEL` and build-stamped scope label; `WB_VINTAGE_NOTE` as `.ew-muted` directly beneath the filter row; table with `ew-col-*` classes on th/td for responsive hiding; Source column values rendered via `sourceDisplay`.

browse.ts structure (complete behavioral contract; ~250 lines):

```ts
// State lives in the URL. One render path for interactions and popstate.
let state = /* decodeBrowseState(location.search, optionsFromDom()) */;
let ready = false;            // DuckDB registered
let pendingPop = false;       // popstate before init -> queue one refresh
let generation = 0;           // stale-response guard (kept from S2)

function optionsFromDom(): KnownOptions // read option values from the four selects
function writeUrl(push: boolean): void  // encodeBrowseState; skip if unchanged; try/catch; push ? pushState : replaceState
function applyStateToControls(): void   // chips rebuilt, select disabled options, toggles, hi-hint visibility (highIncomeExclusionActive)
function onInteraction(mutate: () => void): void {
  mutate(); state.page = resetPageIfFilterChanged; writeUrl(true); void refresh(false);
}
async function refresh(fromCorrection: boolean): Promise<void> {
  // list + status counts via runQuery(buildListSql/buildStatusCountsSql)
  // clamp: if page > pages-1 -> state.page = pages-1; writeUrl(false) /*replaceState*/; return refresh(true)
  // renderRows (source via sourceDisplay, date, badge; link docPath(slug))
  // statusLine(...) into #ew-status; EMPTY_STATE when matching === 0
  // prev/next aria-disabled updates
}
window.addEventListener('popstate', () => {
  const decoded = decodeBrowseState(location.search, optionsFromDom());
  state = decoded.state;            // popstate NEVER writes history
  applyStateToControls();
  if (!ready) { pendingPop = true; return; }
  void refresh(false);
});
// chips: remove button focus -> next chip else that group's select
// dropped params on initial decode -> DROPPED_PARAM_NOTICE + writeUrl(false)
```

- [ ] **Step 1:** Rewrite index.astro; run `npm run dev` and verify static shell renders with baked options and zero JS errors before the script lands.
- [ ] **Step 2:** Rewrite browse.ts per contract. `npx astro check` clean.
- [ ] **Step 3:** Manual dev pass against fixture (`npm run dev`): filters produce chips + URL updates; back/forward walks states; `?utm=x` survives; `?page=99` clamps without history spam; hi toggle disables with hint when an income chip exists; empty state renders.
- [ ] **Step 4:** `npm test` green (libs unchanged). **Step 5: Commit** `feat(explorer-web): browse at parity (chips, status matrix, history discipline)`

### Task 9: Doc page (DocText.astro + doc-text.ts rewrite, [slug].astro back-link)

**Files:**
- Rewrite: `explorer-web/src/components/DocText.astro`, `explorer-web/src/scripts/doc-text.ts`
- Modify: `explorer-web/src/pages/doc/[slug].astro`, `explorer-web/src/env.d.ts`

**Interfaces:**
- Consumes: Task 6 doc-view math, Task 5 `decodeDocQuery`/`encodeDocQuery`, Task 2 copy, existing snapshot-client/format.
- Produces DOM contract: `#ew-back` (back link), `#ew-doc-live` (aria-live polite, visually-hidden class `.ew-sr-only` added to base.css), `#ew-doc-search-input|-prev|-next|-count|-hint`, `#ew-doc-toc-details` + `#ew-doc-toc-filter` (rendered only when toc.length > 100) + `#ew-doc-toc` (buttons via one DocumentFragment; `FRONT_MATTER_LABEL` row when first offset > 0), `#ew-seg-nav` (`#ew-seg-prev|-next|-label`, persistent DOM, hidden in full-render mode), `#ew-doc-text` (single text node, `data-seg-start` carries the rendered slice's start offset).
- `window.__ewDoc = { getRawText(): string | null }` unchanged semantics (full string once loaded, null pre-load/pre-gate); document the contract in env.d.ts comments.

doc-text.ts behavioral contract (complete; ~350 lines):

```ts
// modes: 'empty' | 'full' | 'segmented'; gate unchanged (GATE_BYTES)
interface DocState {
  raw: string | null; segments: Segment[]; segIndex: number;
  matches: SearchMatches | null; matchIndex: number; query: string;
}
const supportsHighlights = typeof CSS !== 'undefined' && 'highlights' in CSS; // note shown pre-typing when false
function renderSegment(i: number): void   // textContent = raw.slice(seg), data-seg-start, segmentLabel into #ew-seg-label, re-applyHighlights()
function applyHighlights(): void {
  // ranges only for matches intersecting current segment, cap 2_000 (highlightCapNote),
  // clamp range end to segment end (straddlers belong to start segment),
  // new Highlight(...) for ew-match, ew-match-current always includes current match (never capped out),
  // currentHighlight.priority = 2; matchHighlight.priority = 1;
  // fallback when !supportsHighlights: selection-paint the current match only
}
function jumpToOffset(off: number): void  // segment switch if needed, non-collapsed Range(off, off+1) -> getBoundingClientRect + scrollTo, then #ew-doc-text.focus({preventScroll:true})
function runSearch(q: string, announce: boolean): void
  // findMatches over raw; counts into #ew-doc-search-count, per-section counts updated IN PLACE on toc buttons (countsByBins over [0, ...tocOffsets]), MIN_QUERY_HINT / absenceCopy paths
function navigate(dir: 1 | -1): void      // wraps; jumpToOffset(starts[i]); live region matchPositionCopy with snippetAround
// q param: debounce 250ms -> encodeDocQuery + replaceState (skip no-op, try/catch);
// cancel pending timer on popstate AND pagehide; popstate re-reads q and re-runs search without writing
// gate: q never auto-loads; after gate click + load, stored q runs
// live region: one #ew-doc-live, updates replace textContent, 500ms idle debounce
// back link: click -> if document.referrer starts with location.origin + '/' (browse) history.back() else default
```

[slug].astro: back anchor gets `id="ew-back"`; pass `pageCount`/`textSource` so DocText renders `PAGES_NOT_DISPLAYED_NOTE` for `text_source === 'pages'` alongside existing notes.

- [ ] **Step 1:** Rewrite DocText.astro (static shell: notes, live region, search controls, TOC details, seg nav placeholders; inline style replaced by classes from Task 7).
- [ ] **Step 2:** Rewrite doc-text.ts per contract; `npx astro check` clean.
- [ ] **Step 3:** Manual dev pass on fixture docs: small doc full-renders with TOC jumps; `synthetic-large` enters segmented mode, TOC click crosses segments, search finds matches across segments and navigates with announcements; `synthetic-astral` search after the emoji lands on the right characters (visual check of highlight position); `synthetic-gate` shows the gate, `?q=` does not bypass it, search runs post-click; pages-sourced fixture doc shows the note.
- [ ] **Step 4:** `npm test` green. **Step 5: Commit** `feat(explorer-web): doc page parity (TOC jumps, segmented render, in-doc search with highlights)`

### Task 10: Smoke + axe extension

**Files:**
- Modify: `explorer-web/scripts/smoke.mjs`, `explorer-web/package.json` (add `@axe-core/playwright`)

- [ ] **Step 1:** `npm i -D @axe-core/playwright` (exact version recorded in lockfile).
- [ ] **Step 2:** Extend smoke.mjs (runs against a served build of the FIXTURE snapshot; keep existing browse smoke): scenarios asserting (a) country chip add updates URL + table and `?utm=x` survives; (b) back restores prior filter state, `?page=99` clamps with `history.length` unchanged by the correction; (c) doc page: text renders, TOC jump scrolls (scrollY > 0), search "section" yields count > 0, next-match updates `#ew-doc-search-count`, segmented fixture switches segments; (d) gate button present on `synthetic-gate`, no text fetch before click (page route intercept assertion); (e) axe run on browse + one doc page with zero serious/critical violations.
- [ ] **Step 3:** Build fixture site + run: from explorer-web/, `SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://localhost:8787/data npm run build && node scripts/serve-static.mjs & node scripts/smoke.mjs`. Expected: all scenarios pass. (Exact serve invocation per script header; adjust port flag to the script's interface.)
- [ ] **Step 4:** Wire the smoke invocation into `.github/workflows/ci.yml` explorer-web job if not already running it; keep CI on the fixture.
- [ ] **Step 5: Commit** `test(explorer-web): smoke coverage for filters, history, doc search, segments, gate + axe`

### Task 11: ARCHITECTURE.md + docs

**Files:**
- Modify: `explorer-web/ARCHITECTURE.md`

- [ ] **Step 1:** Add an "S3 (TEA-903)" section: the __ewDoc contract block from the spec verbatim; the token inventory addition rule; the history-write discipline; search compute guards; segment naming rationale; pointer to the spec's Disposition. Update the "Inputs for S3" heading to note completion. No em-dashes.
- [ ] **Step 2: Commit** `docs(explorer-web): record S3 contracts (window.__ewDoc, tokens, history discipline)`

### Task 12: Full-snapshot build + measurement

**Files:** none (verification); token value tweaks in `tokens.css` if contrast/visual checks demand.

- [ ] **Step 1:** Full build via nohup + Monitor (harness kills long shells): from explorer-web/, `nohup env SNAPSHOT_DIR=../data/snapshot PUBLIC_DATA_BASE_URL=http://localhost:8787/data npm run build > /tmp/ew-build.log 2>&1 &` with a Monitor on build completion markers in the log. Expected: ~9,777 pages (9,774 + synthetics excluded: full snapshot has no synthetics, so 9,775 incl. index) built in seconds-to-minutes.
- [ ] **Step 2:** Serve (`node scripts/serve-static.mjs` with the full snapshot as data root) and run `scripts/measure.mjs` for the S2 metric set (cold/warm browse, doc timings).
- [ ] **Step 3:** Lighthouse (system Chrome per measurements/NOTES.md; Playwright headless-shell cannot run it): browse bare URL AND parameterized URL (2+ countries, hi=1): performance >= 90, accessibility >= 95, CLS reported. One doc page run: accessibility >= 95.
- [ ] **Step 4:** Manual spot-checks on real corpus extremes: luxse-100387641 (29 MB, gate -> segmented, search responsive), a no-TOC large doc (fixed cuts), a pages-sourced doc (note visible), an undated PDIP doc.
- [ ] **Step 5:** Record numbers in `explorer-web/measurements/NOTES.md` (append S3 section). Commit `chore(explorer-web): S3 measurement record (Lighthouse, timings)`

### Task 13: Parity pass (P1-P22) + Firefox/Safari highlight check

- [ ] **Step 1:** Run v1 locally (`uv run shiny run shiny/app.py` from the Dropbox repo against local corpus.duckdb, or use the live Posit URL if reachable from a browser tab) side by side with the served S3 build. Walk the P1-P22 checklist from the spec; record each row pass/deviation-as-designed.
- [ ] **Step 2:** Firefox + Safari manual check: highlight painting (var() in ::highlight()), select+chips behavior, one segmented doc.
- [ ] **Step 3:** Keyboard + screen-reader script (VoiceOver): filter, open doc, search, navigate match, switch segment; live region announces counts/positions.
- [ ] **Step 4:** Save the completed checklist for the TEA-903 comment and PR body.

### Task 14: Ship

- [ ] Phase 4 checks: `npm test`, `npx astro check`, smoke on fixture; repo-level `uv run ruff check src/ tests/` etc. unaffected (make_fixture.py is under explorer-web/scripts/, run ruff on it: `uv run ruff check explorer-web/scripts/make_fixture.py` and format).
- [ ] Council PR gate (fresh reviewers on the diff) + code-reviewer skill; triage per receiving-code-review; disposition posted on the PR.
- [ ] Push branch, `gh pr create`, comment `@codex review` (the @claude workflow is not installed on this repo), wait, triage external feedback, fix, reply.
- [ ] Update SESSION-HANDOFF.md; comment TEA-903 with parity checklist + Lighthouse numbers; PR merge waits for Teal's explicit go-ahead; close TEA-903 after merge.

## Plan self-review (run before the council plan gate)

1. Spec coverage: P1-P22 all mapped (P1-P2, P7-P8 Task 8; P3-P6 Tasks 4/5/8; P9-P11 Task 8; P12-P13 existing; P14-P18 Tasks 6/9; P19 Tasks 2/8; P20 Task 7; P21 Task 2/8; P22 Task 9). Scope copy matrix Task 2/4/8; a11y commitments Tasks 7/9/10; measurement gates Task 12; parity Task 13.
2. No placeholders: every step names exact files, code, or enumerated behaviors.
3. Type consistency: BrowseFilters (queries) vs BrowseUrlState (url-state) are distinct on purpose (page semantics identical, both 0-based internal); doc-view TocEntryLike is structurally compatible with snapshot-client TocEntry.

## Council plan gate disposition

(recorded after the gate runs)
