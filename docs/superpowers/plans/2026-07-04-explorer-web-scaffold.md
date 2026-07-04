# explorer-web scaffold + spike (TEA-902) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold `explorer-web/` (Astro 6 static + DuckDB-WASM) in the open repo and prove the three TEA-902 spike risks with measured numbers.

**Architecture:** Astro static site; browse page runs DuckDB-WASM 1.32.0 in a Web Worker over the 1.7 MB snapshot parquet fetched from a config-driven data URL; ~9,774 `/doc/<slug>/` pages pre-rendered at build time from the same parquet read via hyparquet; per-document text fetched client-side with MANIFEST-first versioning. Spec (authoritative, council-reviewed): `docs/superpowers/specs/2026-07-04-explorer-web-scaffold-design.md`.

**Tech Stack:** Astro 6.x, @duckdb/duckdb-wasm 1.32.0 (exact), hyparquet, vitest, Playwright + lighthouse (measurement only), Node 24.

## Global Constraints

- All work in `/Users/teal_emery/Code/sovereign-prospectus-corpus` on branch `lte/tea-902-s2-scaffold-explorer-web-astro-duckdb-wasm-and-prove-the`.
- Pin dependencies exactly (`npm install -E`). @duckdb/duckdb-wasm MUST be `1.32.0` (npm `latest` is a dev build).
- Neutral theme: every style value a `--ew-*` custom property in `src/styles/tokens.css`; system-ui font stack; no Teal Insights brand or fonts.
- No em-dashes in any copy, code comment, or commit message. Null display token is `n/a`.
- No data files committed except `explorer-web/tests/fixtures/snapshot/` (~20 rows + a few small text JSONs).
- Search: `SearchSlot.astro` placeholder only. No search code.
- `scripts/browse.ts` and `scripts/doc-text.ts` contain zero SQL, zero fetch logic, zero URL construction (all in lib modules).
- Data-credibility copy pinned in `src/lib/format.ts` (exact strings in Task 3).
- Long-running builds: nohup + Monitor pattern (never a raw foreground shell over ~2 min).
- Commit after every green task; conventional-commit style with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Package scaffold, config, theme, layout shell

**Files:**
- Create: `explorer-web/package.json`, `explorer-web/.gitignore`, `explorer-web/.env.example`, `explorer-web/README.md`, `explorer-web/tsconfig.json`, `explorer-web/astro.config.mjs`, `explorer-web/integrations/snapshot-dev-middleware.mjs`, `explorer-web/src/styles/tokens.css`, `explorer-web/src/styles/base.css`, `explorer-web/src/layouts/Base.astro`, `explorer-web/src/pages/index.astro` (placeholder), `explorer-web/src/env.d.ts`

**Interfaces:**
- Produces: `Base.astro` props `{ title: string; snapshotDate: string; generatedAt: string }`; stamps `data-build-generated-at` + `data-build-snapshot-date` on `<body>`, renders footer "Snapshot <date>". `astro.config.mjs` exports static config with `trailingSlash: 'always'`, astro:env schema for `PUBLIC_DATA_BASE_URL`, `vite.optimizeDeps.exclude: ['@duckdb/duckdb-wasm']`, dev middleware integration.

- [ ] **Step 1: package.json + install**

```json
{
  "name": "explorer-web",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22.12" },
  "scripts": {
    "dev": "PUBLIC_DATA_BASE_URL=/data astro dev",
    "build": "astro build",
    "check": "astro check",
    "test": "vitest run",
    "preview": "astro preview"
  }
}
```

Run (from `explorer-web/`): `npm install -E astro @duckdb/duckdb-wasm@1.32.0 hyparquet` then `npm install -E -D @astrojs/check typescript vitest playwright lighthouse`. Record the resolved exact versions in the task commit message. Expected: package-lock.json created; `npx astro --version` prints 6.x.

- [ ] **Step 2: .gitignore, .env.example, README**

`.gitignore`: `node_modules/`, `.astro/`, `dist/`, `.env`, `measurements/`.
`.env.example`:
```
# Client-side base URL for MANIFEST.json, documents.parquet, text/<slug>.json
# Dev default comes from the npm dev script (/data via dev middleware).
# Production builds fail without an explicit https URL.
PUBLIC_DATA_BASE_URL=https://data.example.org/snapshot

# Build-time path to the snapshot dir (getStaticPaths + dev middleware).
# NOTE: read via loadEnv/process.env in astro.config.mjs; .env files are
# NOT auto-loaded inside config files, so export it in your shell or rely
# on the default ../data/snapshot.
SNAPSHOT_DIR=../data/snapshot
```
`README.md`: quick start (npm install, npm run dev against the repo snapshot, npm test, build command with both env vars, pointer to ARCHITECTURE.md).

- [ ] **Step 3: tsconfig.json + env.d.ts**

```json
{ "extends": "astro/tsconfigs/strict", "include": [".astro/types.d.ts", "src/**/*"], "exclude": ["dist"] }
```
`src/env.d.ts`: `/// <reference types="astro/client" />`

- [ ] **Step 4: astro.config.mjs + dev middleware**

```js
// astro.config.mjs
import { defineConfig, envField } from 'astro/config';
import { loadEnv } from 'vite';
import { snapshotDevMiddleware } from './integrations/snapshot-dev-middleware.mjs';
import path from 'node:path';

const env = { ...loadEnv('', process.cwd(), ''), ...process.env };
const SNAPSHOT_DIR = path.resolve(process.cwd(), env.SNAPSHOT_DIR ?? '../data/snapshot');

const isBuild = process.argv.includes('build');
const dataUrl = env.PUBLIC_DATA_BASE_URL;
if (isBuild) {
  if (!dataUrl) {
    throw new Error('PUBLIC_DATA_BASE_URL must be set explicitly for production builds (e.g. https://data.example.org/snapshot)');
  }
  const u = new URL(dataUrl);
  const isLocal = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
  if (u.protocol !== 'https:' && !isLocal) {
    throw new Error(`PUBLIC_DATA_BASE_URL must be https (mixed content); got ${dataUrl}`);
  }
}

export default defineConfig({
  output: 'static',
  trailingSlash: 'always',
  env: {
    schema: {
      PUBLIC_DATA_BASE_URL: envField.string({ context: 'client', access: 'public' }),
    },
  },
  integrations: [snapshotDevMiddleware(SNAPSHOT_DIR)],
  vite: { optimizeDeps: { exclude: ['@duckdb/duckdb-wasm'] } },
});
```

```js
// integrations/snapshot-dev-middleware.mjs
import fs from 'node:fs';
import path from 'node:path';

const TYPES = { '.json': 'application/json', '.parquet': 'application/octet-stream' };

export function snapshotDevMiddleware(snapshotDir) {
  return {
    name: 'snapshot-dev-middleware',
    hooks: {
      'astro:server:setup': ({ server }) => {
        server.middlewares.use('/data', (req, res) => {
          const urlPath = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
          const filePath = path.resolve(snapshotDir, '.' + urlPath);
          if (!filePath.startsWith(snapshotDir) || !fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
            res.statusCode = 404;
            res.end('not found');
            return;
          }
          res.setHeader('Content-Type', TYPES[path.extname(filePath)] ?? 'application/octet-stream');
          fs.createReadStream(filePath).pipe(res);
        });
      },
    },
  };
}
```

Real 404s, no SPA fallback (spec requirement).

- [ ] **Step 5: tokens.css + base.css + Base.astro + placeholder index**

`tokens.css`: `--ew-color-bg/-surface/-text/-text-muted/-accent/-border/-badge-sovereign/-badge-nonsovereign/-badge-unverified/-error-bg/-error-text`, `--ew-font-body: system-ui, -apple-system, 'Segoe UI', sans-serif`, `--ew-font-mono`, `--ew-space-1..5`, `--ew-radius`, `--ew-table-min-height: 32rem` (reserved layout for Lighthouse). Neutral palette (slate/blue-gray accents), light only.

`base.css`: element defaults consuming tokens only (body, headings, tables, links, buttons, selects, `.ew-badge--*`, `.ew-error`, `.ew-notice`).

`Base.astro`:
```astro
---
interface Props { title: string; snapshotDate: string; generatedAt: string }
const { title, snapshotDate, generatedAt } = Astro.props;
import '../styles/tokens.css';
import '../styles/base.css';
---
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>{title}</title></head>
  <body data-build-generated-at={generatedAt} data-build-snapshot-date={snapshotDate}>
    <header class="ew-header"><a href="/">Sovereign Prospectus Explorer</a></header>
    <main><slot /></main>
    <footer class="ew-footer">Snapshot {snapshotDate}. Data and code: sovereign-prospectus-corpus.</footer>
  </body>
</html>
```

Placeholder `index.astro` renders Base with static strings for now (replaced in Task 7).

- [ ] **Step 6: verify + commit**

Run: `npx astro check` → 0 errors. `PUBLIC_DATA_BASE_URL=https://x.example astro build`? No: build requires pages; placeholder suffices, run `npm run build` with env vars set, expect success; then `npm run build` WITHOUT `PUBLIC_DATA_BASE_URL` and expect the config error message (fail-fast proof; record output). Commit: `feat(explorer-web): Astro 6 scaffold, neutral tokens, env fail-fast, dev data middleware`.

---

### Task 2: Committed test fixture (make_fixture.py)

**Files:**
- Create: `explorer-web/scripts/make_fixture.py`, `explorer-web/tests/fixtures/snapshot/` (generated, committed)
- Modify: `docs/superpowers/specs/2026-07-04-explorer-web-scaffold-design.md` (tree line: make-fixture.mjs becomes make_fixture.py; reason: fixture parquet must reproduce DuckDB's exact type layout: DATE, Int32, nullable BOOLEAN; Python duckdb is already a repo dep and is the same writer the real builder uses)

**Interfaces:**
- Produces: `tests/fixtures/snapshot/{documents.parquet, MANIFEST.json, text/<slug>.json...}` satisfying the spec's "Fixture requirements": >= 1 row each of: markdown doc with non-empty toc; pages-sourced doc; has_text=false with no_text_reason; null publication_date; Unknown country/region/income; is_sovereign=false; is_sovereign null; High income. Invariant: every has_text=true row has its text JSON present; MANIFEST counts match.

- [ ] **Step 1: write make_fixture.py**

Python (run via `uv run python explorer-web/scripts/make_fixture.py` from repo root). Logic: open `data/snapshot/documents.parquet` with duckdb; select a covering set with one query per required shape (LIMIT 3 each, prefer small `text_bytes < 200_000`), union + dedupe by slug; `COPY (SELECT * FROM sel) TO 'explorer-web/tests/fixtures/snapshot/documents.parquet' (FORMAT parquet, COMPRESSION snappy)`; copy each has_text row's `data/snapshot/text/<slug>.json`; write MANIFEST.json with schema_version 1, snapshot_date/generated_at copied from the real MANIFEST, counts computed from the selection; print a shape-coverage report and exit nonzero if any required shape is missing.

- [ ] **Step 2: run it, inspect, assert coverage report all-present**

Run: `uv run python explorer-web/scripts/make_fixture.py`. Expected: report lists every required shape with a slug; fixture < 1.5 MB total (guard: script fails if > 3 MB).

- [ ] **Step 3: lint the new Python + commit**

Run: `uv run ruff check explorer-web/scripts/make_fixture.py && uv run ruff format explorer-web/scripts/make_fixture.py`. Commit fixture + script + spec amendment: `feat(explorer-web): committed snapshot fixture with pathological shapes`.

---

### Task 3: format.ts (TDD)

**Files:**
- Create: `explorer-web/src/lib/format.ts`, `explorer-web/tests/unit/format.test.ts`, `explorer-web/vitest.config.ts`

**Interfaces:**
- Produces:
  - `formatDate(v: number | Date | string | null | undefined): string` (UTC, 'YYYY-MM-DD', null/undefined -> 'undated')
  - `formatBytes(n: number | null | undefined): string` ('40 KB', '2.3 MB', null -> 'n/a')
  - `orNA(v: string | number | null | undefined): string` (null/undefined/'' -> 'n/a')
  - `sovereignBadge(v: boolean | null | undefined): { label: 'Sovereign' | 'Non-sovereign' | 'Unverified'; cls: string }`
  - `WB_VINTAGE_NOTE`, `PROVENANCE_NOTE`, `NO_PAGE_ANCHORS_NOTE`, `citeAs(snapshotDate: string, slug: string): string`

- [ ] **Step 1: vitest.config.ts**

```ts
import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['tests/unit/**/*.test.ts'] } });
```

- [ ] **Step 2: failing tests**

```ts
import { describe, expect, it } from 'vitest';
import { formatDate, formatBytes, orNA, sovereignBadge, citeAs, WB_VINTAGE_NOTE, PROVENANCE_NOTE } from '../../src/lib/format';

it('formats epoch-ms (Arrow Date32) in UTC', () => expect(formatDate(1786752000000)).toBe('2026-08-14'));
it('formats JS Date (hyparquet) in UTC', () => expect(formatDate(new Date('2002-11-27T00:00:00Z'))).toBe('2002-11-27'));
it('passes through ISO strings', () => expect(formatDate('2002-11-27')).toBe('2002-11-27'));
it('renders null date as undated', () => expect(formatDate(null)).toBe('undated'));
it('formats bytes', () => { expect(formatBytes(41588)).toBe('41 KB'); expect(formatBytes(29031849)).toBe('27.7 MB'); expect(formatBytes(null)).toBe('n/a'); });
it('orNA', () => { expect(orNA(null)).toBe('n/a'); expect(orNA('424B5')).toBe('424B5'); expect(orNA(18)).toBe('18'); });
it('three-state badge', () => {
  expect(sovereignBadge(true).label).toBe('Sovereign');
  expect(sovereignBadge(false).label).toBe('Non-sovereign');
  expect(sovereignBadge(null).label).toBe('Unverified');
});
it('pinned copy has no em-dash', () => { for (const s of [WB_VINTAGE_NOTE, PROVENANCE_NOTE]) expect(s.includes('—')).toBe(false); });
it('cite line', () => expect(citeAs('2026-07-04', 'nsm-101126915')).toBe('Cite as: Sovereign Prospectus Corpus snapshot 2026-07-04, nsm-101126915'));
```

- [ ] **Step 3: run, verify FAIL** (`npx vitest run` -> module not found)

- [ ] **Step 4: implement**

```ts
export const WB_VINTAGE_NOTE =
  'World Bank FY2027 classification (July 2026); reflects current status, not status at filing date.';
export const PROVENANCE_NOTE =
  'Text is machine-converted (Docling markdown or extracted page text), not a facsimile of the filed PDF. Verify quotes against the original filing.';
export const NO_PAGE_ANCHORS_NOTE =
  'This text was converted from markdown and carries no page anchors; page citations must be checked against the original filing.';

export function formatDate(v: number | Date | string | null | undefined): string {
  if (v === null || v === undefined) return 'undated';
  if (typeof v === 'string') return v.slice(0, 10);
  const d = typeof v === 'number' ? new Date(v) : v;
  return d.toISOString().slice(0, 10);
}
export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return 'n/a';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
export function orNA(v: string | number | null | undefined): string {
  return v === null || v === undefined || v === '' ? 'n/a' : String(v);
}
export function sovereignBadge(v: boolean | null | undefined) {
  if (v === true) return { label: 'Sovereign' as const, cls: 'ew-badge--sovereign' };
  if (v === false) return { label: 'Non-sovereign' as const, cls: 'ew-badge--nonsovereign' };
  return { label: 'Unverified' as const, cls: 'ew-badge--unverified' };
}
export function citeAs(snapshotDate: string, slug: string): string {
  return `Cite as: Sovereign Prospectus Corpus snapshot ${snapshotDate}, ${slug}`;
}
```

- [ ] **Step 5: run tests green, commit** `feat(explorer-web): shared formatters and pinned data-credibility copy`

---

### Task 4: urls.ts + snapshot-client.ts (TDD)

**Files:**
- Create: `explorer-web/src/lib/urls.ts`, `explorer-web/src/lib/snapshot-client.ts`, `explorer-web/src/lib/config.ts`, `explorer-web/tests/unit/urls.test.ts`, `explorer-web/tests/unit/snapshot-client.test.ts`

**Interfaces:**
- Produces:
  - `joinUrl(base: string, path: string): string` (exactly one slash at the seam)
  - `manifestUrl(base)`, `parquetUrl(base, generatedAt)`, `textUrl(base, slug, generatedAt)` (both `?v=${encodeURIComponent(generatedAt)}`)
  - `interface Manifest { schema_version: number; snapshot_date: string; generated_at: string; document_count: number }`
  - `loadManifest(base: string, fetchFn?: typeof fetch): Promise<Manifest>` (cache: 'no-store'; throws `SnapshotError` with user-renderable `.userMessage` on HTTP error, invalid JSON, or `schema_version !== 1`)
  - `config.ts`: `export { PUBLIC_DATA_BASE_URL } from 'astro:env/client'` (thin; only file importing astro:env)

- [ ] **Step 1: failing tests** (urls: join semantics with/without trailing slash, token encoding of `+`/`:` in generated_at; snapshot-client: injected fake fetch returning good manifest -> resolves; schema_version 2 -> throws SnapshotError; 500 -> throws; verifies no-store passed)

```ts
it('joins with exactly one slash', () => {
  expect(joinUrl('https://d.example/snap', 'MANIFEST.json')).toBe('https://d.example/snap/MANIFEST.json');
  expect(joinUrl('https://d.example/snap/', '/MANIFEST.json')).toBe('https://d.example/snap/MANIFEST.json');
});
it('version tokens are encoded', () => {
  expect(textUrl('/data', 'nsm-1', '2026-07-04T17:04:09+00:00')).toBe('/data/text/nsm-1.json?v=2026-07-04T17%3A04%3A09%2B00%3A00');
});
it('rejects wrong schema_version', async () => {
  const fake = async () => new Response(JSON.stringify({ schema_version: 2, snapshot_date: 'x', generated_at: 'y', document_count: 1 }));
  await expect(loadManifest('/data', fake as typeof fetch)).rejects.toMatchObject({ name: 'SnapshotError' });
});
it('passes no-store', async () => {
  let init: RequestInit | undefined;
  const fake = async (_: unknown, i?: RequestInit) => { init = i; return new Response(JSON.stringify({ schema_version: 1, snapshot_date: 's', generated_at: 'g', document_count: 1 })); };
  await loadManifest('/data', fake as typeof fetch);
  expect(init?.cache).toBe('no-store');
});
```

- [ ] **Step 2: run, FAIL** - [ ] **Step 3: implement** (straightforward; SnapshotError extends Error with `userMessage`) - [ ] **Step 4: green** - [ ] **Step 5: commit** `feat(explorer-web): MANIFEST-first snapshot client with versioned URLs`

---

### Task 5: build-data.ts (TDD against fixture)

**Files:**
- Create: `explorer-web/src/lib/build-data.ts`, `explorer-web/tests/unit/build-data.test.ts`

**Interfaces:**
- Produces:
  - `interface DocRow` (all 23 parquet columns; publication_date normalized to `string | null` ISO; page_count/text_chars/text_bytes/document_id `number | null`; is_sovereign/has_text `boolean | null`; strings `string | null`)
  - `loadDocuments(): Promise<DocRow[]>` (module-level cache; reads `${SNAPSHOT_DIR}/documents.parquet` once per process; SNAPSHOT_DIR = `process.env.SNAPSHOT_DIR ?? '../data/snapshot'` resolved from cwd)
  - `loadSnapshotManifest(): Promise<{ snapshot_date: string; generated_at: string }>` (reads MANIFEST.json from SNAPSHOT_DIR)

- [ ] **Step 1: failing tests** (with `process.env.SNAPSHOT_DIR = 'tests/fixtures/snapshot'` set in the test file before import): row count matches fixture MANIFEST document_count; slug set unique; a null publication_date row is `null` not Invalid Date; dates are 'YYYY-MM-DD' strings; has_text=false row carries no_text_reason; BigInt-free (`typeof text_bytes === 'number'`); second call returns the cached array (same reference).
- [ ] **Step 2: FAIL** - [ ] **Step 3: implement** with `asyncBufferFromFile` + `parquetReadObjects` from hyparquet; normalize Date -> ISO string via `formatDate`-style UTC slice; `Number()` any bigint; `undefined` -> null.
- [ ] **Step 4: green** - [ ] **Step 5: commit** `feat(explorer-web): build-time parquet reader (hyparquet) with type normalization`

---

### Task 6: queries.ts + duck.ts

**Files:**
- Create: `explorer-web/src/lib/queries.ts`, `explorer-web/src/lib/duck.ts`, `explorer-web/tests/unit/queries.test.ts`

**Interfaces:**
- Produces (queries.ts, pure SQL assembly tested in vitest + thin exec wrappers):
  - `interface BrowseFilters { country?: string; source?: string; includeNonSovereign: boolean; page: number; pageSize: number }`
  - `buildListSql(f: BrowseFilters): string` (SELECT the render columns FROM docs; WHERE `is_sovereign = true` unless includeNonSovereign; `country_name = '<escaped>'`/`source = '<escaped>'`; `ORDER BY publication_date DESC NULLS LAST, slug DESC`; `LIMIT <pageSize> OFFSET <page*pageSize>`)
  - `buildCountSql(f)`: `count(*)::INTEGER AS n`; `buildScopeCountsSql()`: total/sovereign/other as ::INTEGER; `buildDistinctSql(col: 'country_name' | 'source')`
  - `sqlQuote(v: string): string` (doubles single quotes)
  - `runQuery(conn: AsyncDuckDBConnection, sql: string): Promise<Record<string, unknown>[]>` (`(await conn.query(sql)).toArray().map(r => r.toJSON())`)
- Produces (duck.ts, DOM-free, browser-only, exercised by the spike not vitest):
  - `initDuckDB(): Promise<{ db: AsyncDuckDB; conn: AsyncDuckDBConnection; bundleName: 'mvp' | 'eh'; timings: DuckTimings }>` (selectBundle over mvp+eh `?url` imports only, never coi; performance.now timings for worker+instantiate)
  - `registerDocumentsParquet(db, conn, bytes: Uint8Array): Promise<void>` (`db.dropFile('documents.parquet').catch(() => {})` guard, then registerFileBuffer, then `CREATE OR REPLACE VIEW docs AS SELECT * FROM read_parquet('documents.parquet')`)
  - `interface DuckTimings { workerMs: number; instantiateMs: number }`

- [ ] **Step 1: failing tests for SQL assembly** (asserts: NULLS LAST present; `slug DESC` tiebreak present; default scope contains `is_sovereign = true`; includeNonSovereign drops it; sqlQuote doubles quotes: `sqlQuote("Cote d'Ivoire")` -> `'Cote d''Ivoire'`; LIMIT/OFFSET arithmetic; distinct sql sorted + NULLS handled via `WHERE col IS NOT NULL`)
- [ ] **Step 2: FAIL** - [ ] **Step 3: implement queries.ts** - [ ] **Step 4: green**
- [ ] **Step 5: implement duck.ts** exactly per the documented duckdb.org Vite pattern:

```ts
import * as duckdb from '@duckdb/duckdb-wasm';
import wasmMvp from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import workerMvp from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import wasmEh from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import workerEh from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';

const BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: wasmMvp, mainWorker: workerMvp },
  eh: { mainModule: wasmEh, mainWorker: workerEh },
};
let cached: ReturnType<typeof boot> | null = null;
async function boot() {
  const t0 = performance.now();
  const bundle = await duckdb.selectBundle(BUNDLES);
  const worker = new Worker(bundle.mainWorker!);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  const t1 = performance.now();
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  const t2 = performance.now();
  const conn = await db.connect();
  const bundleName = bundle.mainModule === wasmEh ? 'eh' as const : 'mvp' as const;
  return { db, conn, bundleName, timings: { workerMs: t1 - t0, instantiateMs: t2 - t1 } };
}
export function initDuckDB() { return (cached ??= boot()); }
```

- [ ] **Step 6: `npx astro check` green (types), commit** `feat(explorer-web): duckdb-wasm boot (mvp+eh self-hosted) and browse SQL with pinned null order`

---

### Task 7: Doc pages (/doc/<slug>/) + DocText

**Files:**
- Create: `explorer-web/src/pages/doc/[slug].astro`, `explorer-web/src/components/DocText.astro`, `explorer-web/src/scripts/doc-text.ts`, `explorer-web/src/components/SearchSlot.astro`
- Modify: `explorer-web/src/pages/index.astro` (still placeholder link list? No: Task 8 owns browse; here add nothing)

**Interfaces:**
- Consumes: `loadDocuments`, `loadSnapshotManifest`, format.ts, snapshot-client (textUrl, loadManifest), config.ts.
- Produces: pre-rendered metadata page per slug. DocText contract for S3: raw fetched text kept at module state (`getRawText(): string | null` exported for tests/measure via `window.__ewDoc`), rendered into `#ew-doc-text` (single container, re-renderable in slices), click-gate for `text_bytes > 5_000_000` ("Load full text (N MB)"), loading state with size, visible error state on fetch failure. Static (server-rendered) elements: provenance block with PROVENANCE_NOTE + filing_url link + text_source + NO_PAGE_ANCHORS_NOTE when text_source === 'markdown'; sovereign badge; WB_VINTAGE_NOTE footnote under region/income/lending rows; citeAs line; TOC `<ol>` placeholder filled client-side after text load (toc lives in the text JSON).

Page metadata table rows (all via orNA/formatDate): issuer_name, display_name, title, doc_type, publication_date, country_name, region (+vintage note), income_group (+vintage note), lending_category (+vintage note), source, page_count, text size (formatBytes(text_bytes)), filing link. has_text=false renders no_text_reason instead of the DocText region.

`window.__ewDocMetrics = { fetchMs, parseMs, renderMs, bytes }` set by doc-text.ts after load (measure.mjs contract).

- [ ] **Step 1: implement [slug].astro** (getStaticPaths from loadDocuments, props = row; trailing-slash URLs `/doc/${slug}/`)
- [ ] **Step 2: implement DocText.astro + doc-text.ts** per contract above (fetch via textUrl with generatedAt from loadManifest at runtime; JSON.parse timing split via performance.now around fetch/text()/parse/DOM append)
- [ ] **Step 3: SearchSlot.astro**

```astro
---
// Componentized slot for corpus-wide search. Intentionally empty in S2.
// Two candidate architectures must both remain mountable here:
//   - static prebuilt index (GitHub issue #82)
//   - MotherDuck BYO-token (Linear TEA-907)
// Both are client-side; the search spec (not S2) reconciles them.
---
<div id="ew-search-slot" data-search-slot></div>
```

- [ ] **Step 4: dev smoke** Run `npm run dev` (SNAPSHOT_DIR defaulting to `../data/snapshot`), open `/doc/edgar-0000903423-02-000767/` with Playwright or curl the dev URL: metadata present, provenance text in static HTML (curl grep proves no-JS visibility), text loads. Also curl a `has_text=false` slug page: no_text_reason shown.
- [ ] **Step 5: `npx astro check` + vitest green; commit** `feat(explorer-web): pre-rendered document pages with provenance-honest text loading`

---

### Task 8: Browse page + browse.ts

**Files:**
- Create: `explorer-web/src/scripts/browse.ts`
- Modify: `explorer-web/src/pages/index.astro` (real browse UI)

**Interfaces:**
- Consumes: initDuckDB, registerDocumentsParquet, runQuery, build*Sql, snapshot-client (loadManifest, parquetUrl), format.ts, SearchSlot.
- Produces: browse table (columns: date, issuer/display name linked to `/doc/<slug>/`, country, doc_type, source, sovereign badge), filters country + source (selects fed by DISTINCT), sovereign scope checkbox labeled from live counts ("Include N non-sovereign or unverified documents"), prev/next pagination with total count, status line, drift notice when runtime generated_at differs from `document.body.dataset.buildGeneratedAt`. URL state: reads `?country=&source=&scope=all&page=` on mount, writes via `history.replaceState` on change. Deferred boot: static shell paints first; module starts data work without blocking render; table region styled `min-height: var(--ew-table-min-height)`.
- Produces (measure.mjs contract): `window.__ewMetrics = { bundleName, workerMs, instantiateMs, parquetFetchMs, registerMs, firstQueryMs, secondQueryMs, rowsRendered, manifestMs, totalToFirstRenderMs }`.

- [ ] **Step 1: index.astro markup** (filters/table/pagination skeleton + SearchSlot + noscript note "Browsing requires JavaScript; document pages are static")
- [ ] **Step 2: browse.ts** per contract; zero SQL/fetch/URL-building inline (imports only); explicit first and second query timed separately (first = scope counts, second = page 1 list)
- [ ] **Step 3: dev smoke via Playwright** (playwright-skill pattern): load `/`, assert rows render, toggle scope checkbox changes counts, filter by country=Argentina narrows, link navigates to doc page, URL carries state, back returns with state.
- [ ] **Step 4: `npx astro check` + vitest green; commit** `feat(explorer-web): duckdb-wasm browse with sovereign scope, URL state, drift notice`

---

### Task 9: CI job + route assertion

**Files:**
- Create: `explorer-web/scripts/assert-dist.mjs`
- Modify: `.github/workflows/ci.yml` (additive job only)

- [ ] **Step 1: assert-dist.mjs** (reads fixture parquet slug list via hyparquet, asserts `dist/index.html` and `dist/doc/<slug>/index.html` exist for every fixture slug, exits nonzero listing missing)
- [ ] **Step 2: CI job**

```yaml
  explorer-web:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: explorer-web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24, cache: npm, cache-dependency-path: explorer-web/package-lock.json }
      - run: npm ci
      - run: npx astro check
      - run: npx vitest run
      - name: Fixture build
        run: npx astro build
        env:
          SNAPSHOT_DIR: tests/fixtures/snapshot
          PUBLIC_DATA_BASE_URL: https://data.example.invalid
      - run: node scripts/assert-dist.mjs
```

- [ ] **Step 3: run the same sequence locally with the fixture env; green; commit** `ci: explorer-web check + tests + fixture build`

---

### Task 10: Measurement harness (serve-static.mjs + measure.mjs)

**Files:**
- Create: `explorer-web/scripts/serve-static.mjs`, `explorer-web/scripts/measure.mjs`

**Interfaces:**
- serve-static.mjs: `node scripts/serve-static.mjs --dir <path> --port <n> [--cors]`. Behavior: correct MIME map (`.wasm` -> application/wasm, `.json` -> application/json, `.parquet` -> application/octet-stream, html/js/css); if `<file>.br` exists and Accept-Encoding includes br, serve it with `Content-Encoding: br` (same for .gz/gzip); otherwise on-the-fly gzip for compressible types (json, html, js, css, parquet); `--cors` adds `Access-Control-Allow-Origin: *`; real 404s. Also a `--precompress <glob-dir>` one-shot mode that writes `.br` files for `*.wasm` and `*.js` in dist (zlib brotliCompressSync, quality 9).
- measure.mjs: orchestrates the whole spike run; each scenario appends a JSON record to `explorer-web/measurements/results.json` and prints a summary table. Scenarios: (1) cold browse (fresh context, CDP Network for per-request encodedDataLength, window.__ewMetrics); (2) warm browse (second goto); (3) throttled browse (CDP `Emulation.setCPUThrottlingRate(4)` + `Network.emulateNetworkConditions` ~8 Mbps/40 ms RTT); (4) doc page p50-ish sample doc; (5) worst case `/doc/luxse-100387641/` incl. click-gate, __ewDocMetrics; (6) bfcache browse -> doc -> goBack with notRestoredReasons; (7) heap after init (`performance.memory.usedJSHeapSize`). Pages origin 127.0.0.1:8080 (dist, no CORS header needed), data origin 127.0.0.1:8081 (`--cors`), genuinely cross-origin.

- [ ] **Step 1: serve-static.mjs** (+ manual curl checks: MIME, br negotiation, ACAO header present, 404)
- [ ] **Step 2: measure.mjs** per contract
- [ ] **Step 3: commit** `feat(explorer-web): cross-origin compressed measurement harness`

---

### Task 11: Spike run 1 - 100-doc sample end-to-end

- [ ] **Step 1: build against the sample** `SNAPSHOT_DIR=../data/snapshot_sample PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 npm run build` (time it; localhost http allowed by config). Precompress dist wasm.
- [ ] **Step 2: run measure.mjs** with data origin serving `data/snapshot_sample`. Record: sample build time, cold/warm/throttled browse metrics, doc-page load, bundle bytes (artifact + transferred).
- [ ] **Step 3: judge against pre-registered budgets; note results in a running `explorer-web/measurements/NOTES.md`; commit** `test(explorer-web): spike run on 100-doc sample with measurements`

### Task 12: Spike run 2 - full-scale build (9,774 routes) + worst case

- [ ] **Step 1: full build via nohup + Monitor** (harness kills long shells):
`cd explorer-web && SNAPSHOT_DIR=../data/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 nohup /usr/bin/time -l npx astro build > /tmp/.../full_build.log 2>&1 &` then a background `until [ done-marker ] ...` watcher on the log tail + `dist/doc` count. Record wall-clock and `maximum resident set size` from time -l.
- [ ] **Step 2: measure against the FULL snapshot data origin**: browse cold/warm/throttled, worst-case doc `/doc/luxse-100387641/`, bfcache scenario, Lighthouse run (`npx lighthouse http://127.0.0.1:8080/ --output=json --output-path=measurements/lighthouse.json --chrome-flags='--headless=new'`), record score/LCP/TBT/CLS.
- [ ] **Step 3: spot-check 3 doc pages against source metadata (hand-verification rule): one EDGAR, one NSM, one LuxSE; confirm rendered metadata matches parquet row and filing link resolves.**
- [ ] **Step 4: commit measurements** `test(explorer-web): full-scale spike measurements (build, load, worst case, lighthouse, bfcache)`

### Task 13: ARCHITECTURE.md + README polish

**Files:**
- Create: `explorer-web/ARCHITECTURE.md`
- Modify: `explorer-web/README.md`, root `README.md` (one pointer line under the snapshot section)

- [ ] **Step 1: write ARCHITECTURE.md** with sections: Decisions (stack, versions + why 1.32.0 pin, client scripts not islands, mvp+eh not coi, hyparquet at build, parquet-as-buffer rationale); Data contract consumption (MANIFEST-first, ?v= tokens incl. parquet, staleness model both directions, drift notice); Data credibility (sovereign scope default, vintage footnote + issue #84, provenance block, undated/n-a tokens, cite-as); Measurements (all numbers from Tasks 11-12 with date, machine, conditions, compression encodings, budgets vs actuals, judgement with reasoning); Hosting constraints for TEA-906 (CORS contract, Cache-Control per object class + query-string cache-key requirement, precompressed wasm requirement, application/json content-type requirement, per-host caps: Cloudflare Pages 25 MiB asset veto, GitHub Pages no headers, Netlify credit math; R2 default recommendation; wasm-on-data-host escape hatch); S3 inputs (markdown has no page anchors, slice-addressable DocText + raw text access, TOC-after-fetch + build-time TOC option, stats-cards-at-build recommendation, Lighthouse baseline + bfcache result, pages[].offset_utf16 gap issue #86); Search slot pointer (#82 / TEA-907, non-foreclosure statement).
- [ ] **Step 2: commit** `docs(explorer-web): ARCHITECTURE.md with decisions, measurements, hosting constraints`

### Task 14: Verify phase (repo gates) + council PR gate prep

- [ ] `uv run ruff check src/ tests/ scripts/build_snapshot.py` + format check (must be untouched-green) and `uv run ruff check explorer-web/scripts/make_fixture.py`
- [ ] `uv run pyright src/ tests/ scripts/build_snapshot.py` (no NEW errors)
- [ ] `uv run pytest tests/ -v -m "not network"` green
- [ ] `cd explorer-web && npx astro check && npx vitest run` green; fixture build green
- [ ] superpowers:verification-before-completion checklist
- [ ] Push branch, open PR (gh pr create) with spike numbers in the body; comment `@codex review` + `@claude review`
- [ ] Council PR gate: 4-6 fresh reviewers over the diff (generalist, frontend/Astro, DuckDB-WASM, S3 consumer, researcher, CI/deploy), sound-lists required, disposition posted as PR comment
- [ ] superpowers:receiving-code-review triage for council + external feedback; fix or file issues
- [ ] Update SESSION-HANDOFF.md; comment metrics on TEA-902; state plainly the PR is ready (merge needs Teal's explicit go-ahead; close TEA-902 after)

## Plan self-review notes

Spec coverage: every spec section maps to a task (config -> 1; fixture -> 2; credibility copy -> 3, 7, 8; MANIFEST-first + tokens -> 4; build read -> 5; SQL/null order/duck boot -> 6; doc page + DocText promises -> 7; browse + URL state + drift -> 8; CI -> 9; harness incl. CORS/compression -> 10; measurements 1-7 incl. worst case, Lighthouse, bfcache, throttle -> 11-12; ARCHITECTURE.md incl. hosting constraints + S3 inputs -> 13; DoD/gates -> 14). Type consistency: DocRow (T5) consumed by T7/T8; Manifest (T4) by T7/T8; DuckTimings/__ewMetrics names match between T6/T8/T10. No placeholders: T7/T8 UI markup is specified by exact element/behavior contract rather than full literal HTML; acceptable because the executor is the plan author (inline execution) and the behavior contracts are complete. Fixture generator language changed from mjs to Python with reasoning recorded in Task 2 (spec amended there).
