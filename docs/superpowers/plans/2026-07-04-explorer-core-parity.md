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
- URL params: `country`/`region`/`income`/`source` repeated keys (deduplicated); `hi=1`; `scope=all`; `page` 1-based (omitted at 1); doc `q`. Unknown params pass through verbatim on every write. Invalid VALUES of known params (including `hi`/`scope` values other than the canonical ones, and non-numeric or sub-1 `page`) are dropped with the notice.
- History: interactions pushState then render from URL; corrections replaceState; popstate never writes; debounced writes cancelled on popstate/pagehide; no-op writes skipped; history calls try/catch (WebKit: 100 writes/10 s).
- The word "Part" never appears in segment UI copy ("Segment k of n"); test-guarded.
- The two Lighthouse commitments are load-bearing in Tasks 7 and 8: DuckDB init starts only after the window load event (S2 bootstrap block transcribed verbatim), and `#ew-table-region` keeps `min-height: var(--ew-table-min-height)` (moving from inline style to base.css).
- `window.__ewMetrics` (browse) and `window.__ewDocMetrics` (doc) MUST be repopulated by the rewritten scripts with the S2 field sets (env.d.ts): measure.mjs and smoke gate on them.
- CI runs against the committed fixture; full snapshot runs are local (`SNAPSHOT_DIR=../data/snapshot`). Never run `parse --source all`.
- Long builds: nohup + Monitor on a file condition (the harness kills long shells).
- Sequencing note: legacy exports (`scopeStatus`, `scopeAllStatus`, `filteredStatus`, `buildCountSql`, `buildScopeCountsSql`, `buildDistinctSql`) and their tests are DELETED only in Task 8 together with the browse.ts rewrite that stops importing them; Tasks 2-7 are additive so `npx astro check` and `npm test` stay green after every commit.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `explorer-web/scripts/make_fixture.py` | Modify | Add synthetic shapes: inflated text_bytes, astral-before-TOC doc, >1M-unit segmented doc (issue #88) |
| `explorer-web/tests/fixtures/snapshot/*` | Regenerate | Committed fixture |
| `explorer-web/src/lib/format.ts` | Modify | All new user-facing copy + sourceDisplay + status matrix templates (legacy status fns deleted in Task 8) |
| `explorer-web/src/lib/build-data.ts` | Modify | computeStats + computeFilterOptions (pure over DocRow[]) |
| `explorer-web/src/lib/queries.ts` | Modify | New BrowseFilters, WHERE builder with interplay + COALESCE, status-counts SQL (legacy builders deleted in Task 8) |
| `explorer-web/src/lib/url-state.ts` | Create | Pure URL codec (browse state + doc q), unknown-param passthrough |
| `explorer-web/src/lib/doc-view.ts` | Create | Pure segment math + search-match math |
| `explorer-web/src/styles/tokens.css` | Modify | New tokens + ::highlight rules (literal var() fallbacks) |
| `explorer-web/src/styles/base.css` | Modify | Doc-text rules (pre-wrap kept), chips, filter row, accent-color, border-strong, .ew-sr-only, tap targets, mobile rules, overflow + table reservation |
| `explorer-web/src/pages/index.astro` | Rewrite | Static shell: subtitle, stats, About, filters (baked options), toggles, vintage note, table, pagination |
| `explorer-web/src/scripts/browse.ts` | Rewrite | Browse client: chips, history discipline, status matrix, focus rules, metrics |
| `explorer-web/src/pages/doc/[slug].astro` | Modify | Back-link id, sourceDisplay for the Source row, pass pageCount |
| `explorer-web/src/components/DocText.astro` | Rewrite | Search UI, TOC details + filter, segment nav, live region, notes, tabindex |
| `explorer-web/src/scripts/doc-text.ts` | Rewrite | Doc client: modes, gate, TOC, search, highlights, navigation, q param, metrics |
| `explorer-web/src/env.d.ts` | Modify | Document the __ewDoc contract (types unchanged) |
| `explorer-web/scripts/smoke.mjs` | Rewrite browse section + extend | New DOM contract scenarios + axe (old assertions target deleted copy/ids) |
| `explorer-web/package.json` | Modify | Add `@axe-core/playwright` dev dep |
| `explorer-web/ARCHITECTURE.md` | Modify | S3 decisions, __ewDoc contract, token inventory note |
| `.github/workflows/ci.yml` | Modify | Smoke job steps (playwright install, local-URL fixture build, servers) |
| `explorer-web/tests/unit/{format,build-data,queries}.test.ts` | Extend (legacy tests removed in Task 8) | Match new interfaces |
| `explorer-web/tests/unit/{url-state,doc-view,fixture-shapes}.test.ts` | Create | New pure-logic tests |

Execution order: Task 1 (fixture) first per issue #88; then pure libs (2-6), styles (7), browse page (8), doc page (9), smoke (10), docs (11), full-snapshot verification (12), parity pass (13).

---

### Task 1: Fixture text-scale shapes (issue #88)

**Files:**
- Modify: `explorer-web/scripts/make_fixture.py`
- Create: `explorer-web/tests/unit/fixture-shapes.test.ts`
- Regenerate: `explorer-web/tests/fixtures/snapshot/`

**Interfaces:**
- Produces fixture docs with stable slugs: `synthetic-gate` (parquet `text_bytes=6_000_000` inflated metadata, tiny real JSON), `synthetic-astral` (astral char before a TOC entry, `offset != offset_utf16`), `synthetic-large` (> 1,000,000 UTF-16 units, >= 8 TOC entries incl. one section > 500,000 units). ALL synthetic rows: `has_text=true`, `text_source='markdown'`, plausible `text_bytes` matching the JSON (except the deliberately inflated gate row), `country_code=NULL` and `country_name='Synthetic'` (NULL code keeps "Synthetic" OUT of the baked country options: computeFilterOptions drops null codes), `source='synthetic'`, `doc_type='SYNTHETIC FIXTURE'`, `is_sovereign=NULL`.
- Parquet writing recipe (pins types so hyparquet round-trips without BigInt widening): `CREATE TEMP TABLE synth AS SELECT * FROM read_parquet('<real>') WHERE false;` then `INSERT INTO synth (col, ...) VALUES (...)` per synthetic row (unlisted columns default NULL), then `COPY (SELECT * FROM read_parquet(...) WHERE slug IN (...) UNION ALL SELECT * FROM synth ORDER BY slug) TO ...`.
- `MAX_FIXTURE_BYTES` stays 3,000,000 (current fixture 72 KB + ~1.2 MB synthetics fits; the guard is not loosened).

- [ ] **Step 1: Write failing test** `tests/unit/fixture-shapes.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';
import { expect, it } from 'vitest';

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
  expect(r!.has_text).toBe(true);
  expect(readDoc('synthetic-gate').text.length).toBeLessThan(10_000);
});

it('keeps synthetic rows out of the country options (null country_code)', async () => {
  const synth = (await rows()).filter((x) => x.source === 'synthetic');
  expect(synth.length).toBeGreaterThanOrEqual(3);
  for (const r of synth) expect(r.country_code ?? null).toBeNull();
});

it('has an astral doc where a toc offset diverges from offset_utf16', () => {
  const doc = readDoc('synthetic-astral');
  const diverging = doc.toc.find((e: any) => e.offset !== e.offset_utf16);
  expect(diverging).toBeDefined();
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
- [ ] **Step 3: Implement in `make_fixture.py`** per the Interfaces recipe. Text shapes: `synthetic-gate` text `"gate fixture\n" * 20`; `synthetic-astral` text `"intro \U0001F4C4 emoji front matter\n\n## Heading A\nbody a\n\n## Heading B\nbody b\n"` with toc offsets computed in Python (offset = code-point index of each `##`, offset_utf16 = offset + astral count before it, mirroring `src/corpus/snapshot.py`); `synthetic-large` built from a repeated sentence: 7 sections ~90K units + one 600K section + 100K tail, `## Section N` headings with correct offsets, total ~1.05M units. Text JSONs follow the snapshot text schema (`schema_version, slug, text, toc, pages: [], text_source, ...metadata`). MANIFEST counts include synthetics.
- [ ] **Step 4: Regenerate + verify.** From repo root: `uv run python explorer-web/scripts/make_fixture.py`; then `npm test` (fixture-shapes PASS; existing suites still green against regenerated fixture; `assert-dist` needs no edits: it derives routes from the parquet).
- [ ] **Step 5: Commit** `feat(explorer-web): fixture text-scale shapes (gate, astral, segment) for #88`

### Task 2: format.ts copy + sourceDisplay + status matrix (ADDITIVE; legacy fns removed in Task 8)

**Files:**
- Modify: `explorer-web/src/lib/format.ts`
- Test: `explorer-web/tests/unit/format.test.ts` (extend)

**Interfaces (produced, exact):**

```ts
export const SOURCE_DISPLAY_NAMES: Record<string, string>; // edgar: SEC EDGAR, nsm: FCA NSM, luxse: Luxembourg Stock Exchange, pdip: #PublicDebtIsPublic
export function sourceDisplay(key: string | null | undefined): string; // mapped, else the key itself, else 'n/a'
export interface StatusLineArgs {
  matching: number; shownFrom: number; shownTo: number; page: number; pages: number;
  hiddenScope: number | null;  // null = scope inactive OR zero; sentence renders only for positive numbers
  hiddenHi: number | null;     // same rule
  hiOverride: boolean;         // true ONLY when 'High income' is among the selected incomes while includeHighIncome is false
}
export function statusLine(a: StatusLineArgs): string;
// base: "N documents match, newest first (showing A to B). Page k of n."
// + " Including non-sovereign or unverified documents would add M."   (hiddenScope > 0)
// + " Including high-income countries would add H."                    (hiddenHi > 0)
// + " High-income documents are included by the income filter."        (hiOverride)
export const EMPTY_STATE: string; // 'No documents match these filters.'
export function browseSubtitle(sovereign: number, related: number): string; // 'Browse S sovereign bond prospectuses and R related filings.'
export const STATS_CAPTION: string; // 'Full corpus.'
export function segmentLabel(k: number, n: number, matchCount?: number | null): string; // 'Segment k of n' | 'Segment k of n (14 matches in this segment)'; matchCount passed only when a search is active and NOT capped
export const SEGMENTS_NOTICE: string; // display convenience, not document structure, do not cite
export function matchCountCopy(total: number, capped: boolean, query: string): string; // '128 matches for "x".' / '20,000+ matches for "x"; refine your search.'
export function matchPositionCopy(i: number, n: number, capped: boolean, snippet: string): string; // 'Match 3 of 128: ...' / 'Match 3 of 20,000+: ...'
export const COUNTS_PAST_CAP_NOTE: string; // 'Per-section counts are unavailable past 20,000 matches.'
export function absenceCopy(query: string): string; // 'No exact matches for "q". Search is literal; machine-converted text can split phrases across line breaks.'
export const MIN_QUERY_HINT: string; // 'Enter at least 2 characters to search.'
export const DROPPED_PARAM_NOTICE: string; // 'A filter or page from this link is no longer valid and was removed.'
export const PAGES_NOT_DISPLAYED_NOTE: string;
export const HIGHLIGHT_SUPPORT_NOTE: string;
export const HI_OVERRIDE_HINT: string; // 'Overridden by the income filter selection.'
export const HI_TOGGLE_LABEL: string; // 'Include high-income countries'
export function chipRemoveLabel(name: string): string; // 'Remove Kenya'
export function highlightCapNote(cap: number): string; // 'Showing the first 2,000 highlights in this segment.'
export const TOC_FILTER_PLACEHOLDER: string; // 'Filter contents...'
export const FRONT_MATTER_LABEL: string; // '(Front matter)'
```

Existing exports stay untouched in this task (including `scopeStatus`/`scopeAllStatus`/`filteredStatus`, still imported by the not-yet-rewritten browse.ts; they die in Task 8).

- [ ] **Step 1: Write failing tests:** statusLine for: base only; base+scope sentence; base+hi sentence; base+both; override sentence; zero/null suppression (hiddenScope 0 or null renders no sentence); exact EMPTY_STATE; sourceDisplay mapping + fallbacks; segmentLabel with and without matchCount; matchCountCopy and matchPositionCopy capped forms ("20,000+"); absenceCopy exact string. Extend the guard test to scan every exported string constant and every exercised function output for BOTH em-dashes AND the standalone word "Part" (segment-copy ban).
- [ ] **Step 2:** `npm test -- format` FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): S3 copy layer (source names, status matrix, segment/search strings)`

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
// countries: distinct non-null code+name pairs sorted by name (null codes dropped, which keeps synthetics out);
// regions/incomes: distinct with null -> 'Unknown', sorted; sources: distinct sorted keys
```

- [ ] **Step 1: Failing tests** with hand-built DocRow arrays (nulls, duplicates, Unknown materialization, sort order, null-code dropping) + one test on the real fixture parquet (docs count equals MANIFEST document_count).
- [ ] **Step 2:** FAIL. **Step 3:** Implement (pure, no I/O). **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): build-time stats and filter options`

### Task 4: queries.ts filter model (ADDITIVE; legacy builders removed in Task 8)

**Files:**
- Modify: `explorer-web/src/lib/queries.ts`
- Test: `explorer-web/tests/unit/queries.test.ts` (extend)

**Interfaces (produced):**

```ts
export interface BrowseFilters {
  countries: string[]; regions: string[]; incomes: string[]; sources: string[];
  includeNonSovereign: boolean; includeHighIncome: boolean;
  page: number; pageSize: number; // page 0-based internally
}
export function highIncomeExclusionActive(f: Pick<BrowseFilters,'includeHighIncome'|'incomes'>): boolean; // !includeHighIncome && incomes.length === 0
export function buildListSql(f: BrowseFilters): string;
export function buildStatusCountsSql(f: BrowseFilters): string; // -> { matching, hidden_scope, hidden_hi } all ::INTEGER
```

Predicates (exact): countries `country_code IN (...)`; sources `source IN (...)`; regions `COALESCE(region, 'Unknown') IN (...)`; incomes `COALESCE(income_group, 'Unknown') IN (...)`; scope `is_sovereign = true` when NOT includeNonSovereign; high-income exclusion (only when `highIncomeExclusionActive`): `COALESCE(income_group, 'Unknown') != 'High income'`.

buildStatusCountsSql shape:

```sql
SELECT
  count(*) FILTER (WHERE <scopeP> AND <hiP>)::INTEGER AS matching,
  count(*) FILTER (WHERE <hiP> AND <notScope>)::INTEGER AS hidden_scope,
  count(*) FILTER (WHERE <scopeP> AND <isHi>)::INTEGER AS hidden_hi
FROM docs <WHERE explicit filters only>
```

`<scopeP>` = scope predicate or TRUE; `<hiP>` = exclusion predicate or TRUE; `<notScope>` = `is_sovereign IS DISTINCT FROM true` when scope active else FALSE; `<isHi>` = `COALESCE(income_group,'Unknown') = 'High income'` when the exclusion is active else FALSE. The mapping of these three integers to `StatusLineArgs` (positive-or-null, hiOverride) is pinned in Task 8.

- [ ] **Step 1: Failing tests:** multi-value IN lists with quoting (Cote d'Ivoire), COALESCE guard present in region/income/hi predicates, `highIncomeExclusionActive` truth table (toggle on -> false; incomes selected -> false; both off/empty -> true), scope on/off, ORDER BY pinned, LIMIT/OFFSET arithmetic, status-counts SQL FILTER arms flip to TRUE/FALSE correctly.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS + `npx astro check` clean (nothing deleted yet). **Step 5: Commit** `feat(explorer-web): filter model SQL (multi-select, interplay rule, status counts)`

### Task 5: url-state.ts codec

**Files:**
- Create: `explorer-web/src/lib/url-state.ts`
- Test: `explorer-web/tests/unit/url-state.test.ts`

**Interfaces (produced):**

```ts
export interface BrowseUrlState { countries: string[]; regions: string[]; incomes: string[]; sources: string[]; includeHighIncome: boolean; includeNonSovereign: boolean; page: number; } // page 0-based
export interface KnownOptions { countries: string[]; regions: string[]; incomes: string[]; sources: string[]; }
export function decodeBrowseState(search: string, known: KnownOptions): { state: BrowseUrlState; droppedAny: boolean };
export function encodeBrowseState(currentSearch: string, state: BrowseUrlState): string; // query string WITHOUT leading '?', '' if empty
export function decodeDocQuery(search: string): string;
export function encodeDocQuery(currentSearch: string, q: string): string;
```

Rules (exact): repeated keys via `getAll`, values DEDUPLICATED preserving first occurrence, empty-string values dropped as invalid; values not in `known` dropped (`droppedAny` true); `hi` accepts only `1` and `scope` only `all` (any other value = dropped-with-flag); `page` 1-based in URL, absent -> 0, non-numeric or < 1 -> 0 + flag; encode deletes only its own keys from `currentSearch` then appends, so unknown params survive verbatim; `page` written as `page+1` only when `page > 0`; empty q removes the key. No-op detection: encoding an unchanged state over its own canonical URL returns an identical string (guaranteed for canonical inputs; the first write canonicalizes).

- [ ] **Step 1: Failing tests:** round-trip identity; unknown params (`utm=x`, `search=y`) survive a state change; invalid country dropped with flag; duplicates deduped; `hi=0` and `scope=none` dropped with flag; 1-based page mapping both ways; `?page=abc` -> 0 + flag; doc q round-trip preserving unknowns; canonical no-op stability.
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
export function countsByBins(starts: number[], binStarts: number[]): number[]; // binStarts sorted DEDUPED; bin i owns [binStarts[i], binStarts[i+1])
export function snippetAround(text: string, start: number, end: number, context?: number): string; // 40 chars each side, whitespace collapsed
```

Core algorithms (complete, transcribe as written):

```ts
function findCut(text: string, from: number, at: number): number {
  const nl = text.lastIndexOf('\n', at - 1);
  if (nl > from) return nl + 1;
  const c = text.charCodeAt(at - 1);
  return c >= 0xd800 && c <= 0xdbff ? at - 1 : at; // never split a surrogate pair
}

export function computeSegments(text, toc, cfg = DEFAULT_SEGMENT_CONFIG): Segment[] {
  const len = text.length;
  const starts = [0, ...sanitizeToc(toc, len).map(e => e.offset_utf16).filter(o => o > 0)];
  const segs: Segment[] = [];
  let segStart = 0;
  for (let i = 1; i <= starts.length; i++) {
    const next = i < starts.length ? starts[i] : len;
    if (next - segStart <= cfg.segmentTarget) continue;
    const prev = starts[i - 1];
    if (prev > segStart) { segs.push({ start: segStart, end: prev }); segStart = prev; }
    while (next - segStart > cfg.segmentTarget) {
      const cut = findCut(text, segStart, segStart + cfg.segmentTarget);
      if (cut <= segStart) break;
      segs.push({ start: segStart, end: cut });
      segStart = cut;
    }
  }
  if (segStart < len || segs.length === 0) segs.push({ start: segStart, end: len });
  return segs;
}

export function buildSearchPattern(query, limits = DEFAULT_SEARCH_LIMITS): RegExp | null {
  const q = query.trim();
  if ([...q].length < limits.minQueryLength) return null;
  let src = '';
  for (const ch of q) {
    if (/\s/.test(ch)) { if (!src.endsWith('\\s+')) src += '\\s+'; }
    else if (ch === "'" || ch === '‘' || ch === '’') src += "['\\u2018\\u2019]";
    else if (ch === '"' || ch === '“' || ch === '”') src += '["\\u201C\\u201D]';
    else src += ch.replace(/[.*+?^${}()|[\]\\\/]/, '\\$&');
  }
  return new RegExp(src, 'gi');
}
```

Quote tolerance is SYMMETRIC (straight or typographic quotes in the query match both forms; the likeliest user flow is copy-from-doc, paste-into-search). findMatches: exec loop, zero-length guard (`if (m[0].length === 0) { re.lastIndex++; continue; }`), push bare numbers; on reaching `maxMatches`, LOOK AHEAD ONE exec: `capped = true` only if another match exists (exactly 20,000 matches is not "20,000+").

Accepted behaviors (recorded, do NOT "fix"): tiny segments can occur (a 100-char front matter before an oversized section becomes its own segment; a near-end final TOC entry yields a short final segment); empty text produces a single `{start: 0, end: 0}` segment; the tiling property test asserts `end > start` for all segments EXCEPT the empty-text case.

- [ ] **Step 1: Failing tests (write all):** packing to section boundaries; oversized single section cut at newline; no-newline window hard-cuts; surrogate-pair-safe hard cut (all-emoji text); no-TOC fixed cuts; tiling invariant property loop (start 0, contiguous, end = len) over generated cases including the tiny-segment shapes above; unsorted/duplicate/out-of-range toc sanitized; tail after last entry cuttable; segmentForOffset boundaries + clamping; search: case-insensitivity; whitespace-flex ("collective action clauses" matches across "\n"); symmetric quotes both directions; metacharacters literal ("10.5%"); min length (1 char, whitespace-only -> null); cap with look-ahead (exactly-at-cap not capped; cap+1 capped); zero-length safety; astral offset truth (`text.slice(start, end)` equals matched surface after an emoji); countsByBins sums to starts.length incl. bin 0; snippetAround collapses newlines and clips at ends.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. **Step 5: Commit** `feat(explorer-web): doc-view segment and search math (pure, DOM-free)`

### Task 7: Tokens and base styles

**Files:**
- Modify: `explorer-web/src/styles/tokens.css`, `explorer-web/src/styles/base.css`

New tokens (council-computed contrast: border-strong 4.62:1 on white; match pair 12.59:1; current pair 8.05:1; the two highlight backgrounds sit at 1.56:1 / delta-L* ~16 from each other, acceptable because the match-position UI and live region are the state channel; do not shrink this step when tuning): `--ew-color-border-strong: #6b7684`; `--ew-color-match-bg: #ffe08a`; `--ew-color-match-text: #1a2129`; `--ew-color-match-current-bg: #f0a84b`; `--ew-color-match-current-text: #1a2129`; `--ew-font-size-doc: 0.875rem` (0.9375rem under 640px, media query beside it in tokens.css); `--ew-filters-min-height: 8rem`; `--ew-chips-min-height: 2.25rem`; `--ew-tap-target-min: 24px`; `--ew-tap-target: 44px`.

- [ ] **Step 1: tokens.css:** add tokens + the ::highlight rules (they live HERE so S4's swap reaches them; literal fallbacks cover pre-134 Chromium):

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

- [ ] **Step 2: base.css**, tokens only:
  - `#ew-doc-text { white-space: pre-wrap; overflow-wrap: anywhere; font-family: var(--ew-font-mono); font-size: var(--ew-font-size-doc); }` (REPLACES the DocText inline style; pre-wrap and the mono font MUST survive the move: the raw-text design depends on pre-wrap).
  - `#ew-table-region { min-height: var(--ew-table-min-height); overflow-x: auto; }` (the reservation moves here from index.astro's inline style; second Lighthouse commitment).
  - `.ew-sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }` (the live-region class; NEVER display:none/visibility:hidden, which silence announcements).
  - `input, select, button { border-color: var(--ew-color-border-strong); }` (`--ew-color-border` stays for decorative rules only); `input[type='checkbox'] { accent-color: var(--ew-color-accent); }` (progressive enhancement).
  - Chips: `.ew-chips { min-height: var(--ew-chips-min-height); }` list styles, `.ew-chip` inline-flex, `.ew-chip button` close affordance.
  - `.ew-filters { min-height: var(--ew-filters-min-height); }` layout; `#ew-hi-hint { visibility: hidden; }` with a shown modifier class (hint is ALWAYS rendered, space reserved; visibility toggles so it cannot shift layout).
  - Target sizes: `.ew-chip button, #ew-prev, #ew-next, #ew-seg-prev, #ew-seg-next, #ew-doc-search-prev, #ew-doc-search-next, #ew-doc-toc button, .ew-check-row { min-height: var(--ew-tap-target-min); }` and the same selector list gets `min-height: var(--ew-tap-target)` under 640px (`.ew-check-row` is the checkbox LABEL row so the clickable area grows, not the input).
  - `@media (max-width: 640px)`: hide `.ew-col-type, .ew-col-source` (th and td).
- [ ] **Step 3:** `npx astro check` + `npm test` green (additive CSS only; the DocText inline style is removed in Task 9 when the component is rewritten, briefly redundant not conflicting).
- [ ] **Step 4: Commit** `feat(explorer-web): S3 tokens (contrast, highlights, reservations) and control styles`

### Task 8: Browse page (index.astro + browse.ts rewrite; legacy exports die here)

**Files:**
- Rewrite: `explorer-web/src/pages/index.astro`, `explorer-web/src/scripts/browse.ts`
- Modify: `explorer-web/src/lib/format.ts` + `queries.ts` (DELETE `scopeStatus`/`scopeAllStatus`/`filteredStatus`/`buildCountSql`/`buildScopeCountsSql`/`buildDistinctSql`), their tests in `format.test.ts`/`queries.test.ts`

**Interfaces:**
- Consumes: Tasks 2-5 exports; existing duck/snapshot-client/urls/dom.
- Produces DOM contract (smoke targets): `#ew-filters` (form, submit preventDefault), four groups each `<label>`-wrapped `#ew-filter-<key>-select` + `#ew-filter-<key>-chips` (`<ul aria-label="Selected countries">` etc., chips as `<li>`); `#ew-hi-toggle` (native disabled when overridden + `aria-describedby="ew-hi-hint"`) + `#ew-hi-hint` (always rendered, visibility-toggled); `#ew-scope-toggle` (label build-stamped via `scopeToggleLabel(stats.related)`); `#ew-status` (aria-live polite; the status update is ALSO the chip-add announcement channel); `#ew-browse-notices`; `#ew-table`; `#ew-rows`; `#ew-prev`/`#ew-next` (aria-disabled pattern once enabled, never `disabled`).

index.astro static shell (build-time: `loadDocuments()` -> `computeStats`/`computeFilterOptions` + format copy): h1 + `browseSubtitle`; three stat cards + `STATS_CAPTION`; `<details>` About with v1 content COPIED from the Dropbox repo's `shiny/app.py` `_about_content()` (text links incl. Teal Insights/NatureFinance/GitHub/MIT/prototype/Q-CRAFT/mailto; NO logos, NO brand fonts); filter row with baked `<option>` lists (country `value=code` label=name name-sorted; prompt option value="" "Add country..." etc.); the two toggles; `WB_VINTAGE_NOTE` directly beneath the filter row; table with `ew-col-*` classes; the old inline `min-height` style on `#ew-table-region` is dropped (base.css owns it since Task 7).

browse.ts contract (transcribe; ~280 lines):

```ts
// ---- module eval (runs pre-load; options are baked so no await needed) ----
const known = optionsFromDom();          // reads option values; EXCLUDES empty prompt values
let decoded = decodeBrowseState(location.search, known);
let state = decoded.state;
applyStateToControls();                   // chips, select disabled options, toggles, hint visibility
if (decoded.droppedAny) { renderNotice(notices, DROPPED_PARAM_NOTICE); writeUrl(false); }

// ---- rules ----
// Hint/disable predicate: const overridden = state.incomes.length > 0;
//   hiToggle.disabled = overridden; hint shown iff overridden.  (NOT highIncomeExclusionActive)
// StatusLineArgs mapping (THE pinned mapping):
//   hiddenScope = !state.includeNonSovereign && counts.hidden_scope > 0 ? counts.hidden_scope : null;
//   hiddenHi   = highIncomeExclusionActive(state) && counts.hidden_hi > 0 ? counts.hidden_hi : null;
//   hiOverride = !state.includeHighIncome && state.incomes.includes('High income');
// Every filter/toggle interaction resets state.page = 0; page nav does not.
// onInteraction(mutate): mutate(); writeUrl(true); applyStateToControls(); void refresh();
// writeUrl(push): const qs = encodeBrowseState(location.search, state); skip if identical; try/catch;
//   push ? history.pushState(null,'',url) : history.replaceState(null,'',url)
// refresh(): generation token as in S2 (check BEFORE any DOM or history write);
//   one query pair (buildListSql + buildStatusCountsSql);
//   clamp: if state.page > pages-1 { state.page = pages-1; writeUrl(false); return refresh(); } // terminates by construction
//   EMPTY_STATE when matching === 0; else renderRows (sourceDisplay in Source cells) + statusLine(...);
//   prev/next aria-disabled updates; populate window.__ewMetrics fields exactly as S2 did.
// popstate: decoded = decodeBrowseState(...); state = decoded.state; applyStateToControls();
//   if (!ready) { pendingPop = true; return; }  void refresh();   // NEVER writes history
// chip remove: focus -> next chip in that group, else that group's select.
// form submit: e.preventDefault().

// ---- bootstrap (VERBATIM S2 commitment; DuckDB starts only after load) ----
if (document.readyState === 'complete') { void main(); }
else { window.addEventListener('load', () => void main()); }
// main(): manifest -> initDuckDB -> fetchParquetBytes -> register -> ready = true;
//   if (pendingPop) { pendingPop = false; }   // state already current; fall through
//   await refresh();                          // reads live `state` at call time
```

- [ ] **Step 1:** Rewrite index.astro; `SNAPSHOT_DIR=tests/fixtures/snapshot npm run dev`: static shell renders baked options, no JS errors.
- [ ] **Step 2:** Rewrite browse.ts per contract; delete the six legacy exports + their tests; `npx astro check` + `npm test` green.
- [ ] **Step 3:** Manual dev pass (fixture): chips + URL round-trip; back/forward walks states; `?utm=x` survives; `?page=99` clamps without history spam; income chip disables hi toggle + shows hint + override sentence only with 'High income' selected; empty state; `__ewMetrics` populated (check in console).
- [ ] **Step 4: Commit** `feat(explorer-web): browse at parity (chips, status matrix, history discipline)`

### Task 9: Doc page (DocText.astro + doc-text.ts rewrite, [slug].astro)

**Files:**
- Rewrite: `explorer-web/src/components/DocText.astro`, `explorer-web/src/scripts/doc-text.ts`
- Modify: `explorer-web/src/pages/doc/[slug].astro`, `explorer-web/src/env.d.ts` (comment-document the __ewDoc contract; types unchanged)

**Interfaces:**
- Consumes: Task 6 math, Task 5 doc-q codec, Task 2 copy, existing snapshot-client/format.
- Produces DOM contract: `#ew-back`; `#ew-doc-live` (`class="ew-sr-only"` aria-live polite, present in static shell); `#ew-doc-search-input` (aria-label "Search within this document") + `-prev`/`-next` (aria-disabled at ends is NOT needed: match navigation WRAPS, position announcements cover it) + `-count` + `-hint`; `#ew-doc-toc-details` (closed) + `#ew-doc-toc-filter` (STATICALLY RENDERED, `hidden`, aria-label "Filter table of contents"; doc-text.ts reveals it when toc.length > 100; filtering hides non-matching `<li>` via the hidden attribute, case-insensitive substring on title, never rebuilds) + `#ew-doc-toc` (buttons via one DocumentFragment; `FRONT_MATTER_LABEL` row only when first toc offset > 0); `#ew-seg-nav` (`#ew-seg-prev`/`-next` persistent DOM, aria-disabled at segment ends, hidden in full mode; `#ew-seg-label`); `#ew-doc-text` (`tabindex="-1"` REQUIRED in the static shell or every focus() call is a silent no-op; single text node; `data-seg-start`).

[slug].astro: back anchor gets `id="ew-back"`; Source row renders `sourceDisplay(doc.source)` (P19); pass `pageCount` (textSource already passed); DocText renders `PAGES_NOT_DISPLAYED_NOTE` when `textSource === 'pages'`.

doc-text.ts contract (transcribe; ~380 lines):

```ts
// state: { raw, segments, segIndex, matches, matchIndex, query }
// __ewDoc: getRawText() -> raw (full string in every mode once loaded; null pre-load/pre-gate)
const supportsHighlights = typeof CSS !== 'undefined' && 'highlights' in CSS;
// if !supportsHighlights: show HIGHLIGHT_SUPPORT_NOTE near the input BEFORE the user types;
//   current match painted via window.getSelection() range instead (cleared by taps: accepted)
// gate: unchanged threshold; on gate click announce `Loading X...` via #ew-doc-live, and after
//   render focus #ew-doc-text (never leave focus on the removed button)
// renderSegment(i): textContent = raw.slice(seg) (guaranteed single Text node), data-seg-start,
//   #ew-seg-label = segmentLabel(i+1, n, activeUncappedCount), seg buttons aria-disabled at ends,
//   applyHighlights()
// segment prev/next: renderSegment; announce segmentLabel via #ew-doc-live; scroll to segment top;
//   focus #ew-doc-text ({preventScroll:true})
// jumpToOffset(off): switch segment if needed; non-collapsed Range(off,off+1) on the text node
//   (node offset = off - segStart); range.getBoundingClientRect() + window.scrollTo; focus container.
//   Unresolvable target (offset outside text): render segment 1 + visible notice.
// input handler: ONE 250 ms debounce timer fires BOTH runSearch(q) and the q URL write
//   (encodeDocQuery + replaceState, skip no-op, try/catch); timer cancelled on popstate AND pagehide.
// popstate: cancel timer; read q; set input value; runSearch without writing history.
// runSearch(q): findMatches over raw; matchIndex = 0;
//   counts: matchCountCopy into #ew-doc-search-count; per-section TOC counts (countsByBins over
//   deduped [0?, ...tocOffsets]: NO leading 0 duplicate when toc[0].offset_utf16 === 0, front-matter
//   bin/row only when first offset > 0) updated IN PLACE on buttons; per-segment count via
//   segmentLabel arg; WHEN capped: suppress per-section and per-segment counts, show COUNTS_PAST_CAP_NOTE;
//   MIN_QUERY_HINT / absenceCopy to the visible hint AND #ew-doc-live;
//   then applyHighlights(); then IF matches: navigate to match 1 (announce).
// applyHighlights(): only over a rendered text node (never Loading/error states);
//   ranges for matches intersecting current segment via binary search on starts;
//   cap 2,000/segment + highlightCapNote; straddlers clamped to segment end;
//   current match EXCLUDED from ew-match (its Range lives only in ew-match-current: no overlap,
//   no priority variance); Highlight.priority still set (current 2, match 1).
// navigate(dir): wraps; cross-segment renders target segment first; jumpToOffset(starts[i]);
//   #ew-doc-live gets matchPositionCopy(i+1, total, capped, snippetAround(raw, s, e)).
// live region: ONE #ew-doc-live; updates replace textContent; 500 ms idle debounce for announcements.
// q from URL: restores after text load; on gated docs only after the gate click (never auto-load).
// failed text load: search input disabled, error visible (existing renderError path).
// back link: on click, if referrer is same-origin AND its pathname === '/', history.back(); else default.
// metrics: populate window.__ewDocMetrics { fetchMs, parseMs, renderMs, stringLength } as S2 did.
```

- [ ] **Step 1:** Rewrite DocText.astro (static shell incl. tabindex, live region, hidden TOC filter, notes).
- [ ] **Step 2:** Rewrite doc-text.ts per contract; [slug].astro + env.d.ts edits; `npx astro check` + `npm test` green.
- [ ] **Step 3:** Manual dev pass (`SNAPSHOT_DIR=tests/fixtures/snapshot npm run dev`): small doc full render + TOC jump; `synthetic-large` segments, cross-segment TOC click, search + navigation + announcements (inspect #ew-doc-live text), per-segment count in label; `synthetic-astral` highlight lands on the right characters after the emoji; `synthetic-gate` gate + `?q=` no auto-load + search runs post-click; pages-sourced doc shows the note; `__ewDocMetrics` populated.
- [ ] **Step 4: Commit** `feat(explorer-web): doc page parity (TOC jumps, segmented render, in-doc search with highlights)`

### Task 10: Smoke rewrite + axe + CI wiring

**Files:**
- Rewrite browse section + extend: `explorer-web/scripts/smoke.mjs`
- Modify: `explorer-web/package.json` (add `@axe-core/playwright`), `.github/workflows/ci.yml`

The existing browse smoke CANNOT be kept (it asserts deleted copy, old ids, `selectOption` semantics, and `disabled` pagination); rewrite it against the new DOM contract.

Serving recipe (two origins, mirrors measure.mjs; `serve-static.mjs` serves ONE dir at root, so `/data` paths do not exist):
- Build: `SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 npx astro build`
- Serve: `node scripts/serve-static.mjs --dir dist --port 8080 &` and `node scripts/serve-static.mjs --dir tests/fixtures/snapshot --port 8081 --cors &` (match measure.mjs's exact flags)
- Run: `SMOKE_BASE=http://127.0.0.1:8080 node scripts/smoke.mjs`

- [ ] **Step 1:** `npm i -D @axe-core/playwright`.
- [ ] **Step 2:** Scenarios: (a) add country chip -> table + URL update, `?utm=x` survives the interaction; (b) back restores prior state; `?page=99` clamps via replaceState (history.length unchanged); dropped-param notice shows for `?country=ZZ`; (c) income chip -> hi toggle disabled + hint visible; override sentence only when 'High income' chip added; (d) doc page: text renders; TOC jump to a LATE entry (scrollY > 0 AND `document.activeElement === #ew-doc-text`); search count > 0; next-match updates count + live region text; `synthetic-large` segment switch; (e) `synthetic-gate`: gate button present, `?q=` triggers NO text fetch pre-click (route intercept), post-click search runs; (f) one scenario with `CSS.highlights` deleted via addInitScript: counts + navigation still work, support note visible; (g) axe on browse + one doc page: zero serious/critical.
- [ ] **Step 3:** Run the full recipe locally against the fixture; all scenarios pass.
- [ ] **Step 4:** CI wiring (real steps): in the explorer-web job add `npx playwright install --with-deps chromium`, the fixture build with the local data URL, background servers with teardown (`kill %1 %2` or a wrapper script), then the smoke run.
- [ ] **Step 5: Commit** `test(explorer-web): smoke against S3 contract (filters, history, doc search, segments, gate, axe) + CI wiring`

### Task 11: ARCHITECTURE.md + docs

- [ ] **Step 1:** Add an "S3 (TEA-903)" section: the __ewDoc contract block from the spec verbatim; token inventory rule (tokens.css stays the complete inventory; PR lists additions); history-write discipline; search compute guards; segment naming rationale; pointer to the spec Disposition. Mark "Inputs for S3" as consumed. No em-dashes.
- [ ] **Step 2: Commit** `docs(explorer-web): record S3 contracts (window.__ewDoc, tokens, history discipline)`

### Task 12: Full-snapshot build + measurement

- [ ] **Step 1:** Full build baked for the measurement harness's data origin (measure.mjs hardcodes pages 127.0.0.1:8080 / data 127.0.0.1:8081): `nohup env SNAPSHOT_DIR=../data/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 npx astro build > /tmp/ew-build.log 2>&1 &` + Monitor on the log for completion/error markers. Expected: 9,775 pages (9,774 docs + index; the full snapshot contains no synthetics).
- [ ] **Step 2:** Run `scripts/measure.mjs` (its own two-origin spawn harness) for the S2 metric set; `__ewMetrics`/`__ewDocMetrics` must populate or every scenario times out at 180 s.
- [ ] **Step 3:** Lighthouse via system Chrome, same invocation as the S2 baseline (see measurements/NOTES.md; headless-shell cannot run it): browse BARE URL: performance >= 90, accessibility >= 95, CLS <= 0.02 asserted (a 90 perf score alone tolerates CLS ~0.25 and cannot backstop the reservation commitments); browse PARAMETERIZED URL (2+ countries AND an income param so the hint renders): performance >= 90, accessibility >= 95, CLS recorded as the honesty number; one doc page: accessibility >= 95.
- [ ] **Step 4:** Real-corpus extremes: luxse-100387641 (29 MB gate -> segmented, search responsive), a no-TOC large doc, a pages-sourced doc, an undated PDIP doc.
- [ ] **Step 5:** Append an S3 section to `measurements/NOTES.md`; commit `chore(explorer-web): S3 measurement record (Lighthouse, timings)`

### Task 13: Parity pass (P1-P22) + cross-browser + SR script

- [ ] **Step 1:** v1 side by side (local `uv run shiny run shiny/app.py` from the Dropbox repo, or the live Posit URL if at hand); walk P1-P22, record pass/deviation-as-designed per row.
- [ ] **Step 2:** Firefox + Safari: highlight painting (var() in ::highlight()), select+chips, one segmented doc.
- [ ] **Step 3:** Keyboard + VoiceOver script: filter, open doc, search, navigate match, switch segment; announcements audible for counts, positions, segments, absence.
- [ ] **Step 4:** Save the checklist for the TEA-903 comment and PR body.

### Task 14: Ship

- [ ] Phase 4 checks: `npm test`, `npx astro check`, smoke recipe; `uv run ruff check explorer-web/scripts/make_fixture.py` + `uv run ruff format --check` on it; repo suites untouched.
- [ ] Council PR gate (fresh reviewers on the diff) + code-reviewer skill; triage; disposition posted on the PR.
- [ ] PR description MUST list every token added to tokens.css (S4 acceptance) and the P1-P22 outcomes.
- [ ] Push, `gh pr create`, `@codex review` comment (no @claude workflow on this repo), wait, triage, fix, reply.
- [ ] SESSION-HANDOFF.md update; TEA-903 comment (parity checklist + Lighthouse numbers); merge only on Teal's explicit go-ahead; close TEA-903 after merge.

## Plan self-review

1. Spec coverage: P1-P22 mapped (incl. P19 on the doc page and P22 back-link); status matrix Tasks 2/4/8; per-segment counts in segmentLabel (Task 9); a11y commitments Tasks 7/9/10 (incl. tabindex, sr-only recipe, gate focus, segment announcements, 24px floor); error-handling bullets homed (failed-load disable, unresolvable jump fallback, sanitized part math); measurement gates Task 12 (CLS asserted); parity Task 13.
2. No placeholders; the glue that reviewers flagged as hand-waved is now pinned (style move, smoke serving, init sequencing, metrics).
3. Type consistency: statusLine/StatusLineArgs (Task 2) match the Task 8 mapping; segmentLabel arity matches Task 9's call; matchPositionCopy carries `capped`; TocEntryLike is structurally satisfied by snapshot-client's TocEntry.

## Council plan gate disposition (2026-07-04)

Five fresh reviewers (independent generalist, frontend implementer, researcher, accessibility, performance). Both core algorithms were executed empirically by two reviewers independently and confirmed correct (tiling invariant, surrogate safety, no infinite loops, escape/collapse correctness); SQL, codec, copy architecture, task interfaces, and council-disposition fidelity all came back sound. Findings clustered in glue-level pinning, all adopted:

- Researcher: hint-predicate inversion fixed (`incomes.length > 0`); SQL-to-StatusLineArgs mapping pinned; hiOverride narrowed to 'High income' membership; capped scans suppress per-section/per-segment counts (COUNTS_PAST_CAP_NOTE); marginal-count copy reworded ("would add N"); matchPositionCopy carries capped; "Part" ban test; dropped-notice wording covers page.
- Accessibility: tabindex="-1" pinned in the shell + smoke focus assertion; gate-click focus + announcement (pre-existing S2 violation fixed rather than grandfathered); .ew-sr-only recipe homed in Task 7; segment-nav announcements + focus + aria-disabled; 24px floor token with enumerated selectors; label wrapping, chips aria-labels, aria-describedby on the toggle, input aria-labels; absence copy routed to the live region. Contrast values verified by computation and recorded.
- Performance: S2 window-load bootstrap transcribed verbatim into the Task 8 contract; table min-height re-homed to base.css; runSearch debounced on the same 250 ms timer as the URL write; CLS <= 0.02 asserted (bare) + income param added to the parameterized run; hi-hint reserved via visibility; TOC filter hides rather than rebuilds; clamp/generation ordering pinned.
- Frontend implementer: pre-wrap + mono font survive the style move; smoke serving corrected to the two-origin recipe with pinned ports; fixture INSERT pinned to a schema-cloned temp table (BigInt widening trap) with full synthetic-row column values (has_text, text_source, NULL country_code); TOC filter statically rendered + revealed; symmetric quote tolerance; current match excluded from ew-match; auto-navigate-to-first pinned; micro-behaviors pinned (page reset, dedup, empty-value exclusion, announce semantics).
- Generalist: deletion sequencing moved to Task 8 so every commit passes astro check; Task 12 build URL matched to the measure.mjs harness (prevents redoing the expensive full build); __ewMetrics/__ewDocMetrics repopulation made a global constraint; per-segment counts homed in segmentLabel; P19 doc-page slice homed; CI smoke wiring given real steps; MAX_FIXTURE_BYTES kept at 3 MB; look-ahead-one cap honesty; countsByBins duplicate-zero edge pinned; no-highlights fallback + gated-`?q=` given smoke coverage.

Rejected: none. Deviations recorded in the spec (cut-snap direction unified to backward-snap; symmetric quotes; segment-label match counts).
