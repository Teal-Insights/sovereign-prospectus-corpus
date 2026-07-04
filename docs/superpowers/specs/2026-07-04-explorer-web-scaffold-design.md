# explorer-web scaffold + spike (TEA-902, S2) — design

**Date:** 2026-07-04
**Issue:** TEA-902 (Explorer v2 project)
**Status:** Draft for council spec gate

## Problem

The Explorer v2 sprint replaces the Streamlit/Shiny explorers with a static
web explorer served from the snapshot contract built in S1 (PR #78). Before
building features (S3 parity, S4 private wrapper), three architectural risks
need proving with numbers:

1. **In-browser DuckDB-WASM** querying `data/snapshot/documents.parquet`
   (1.7 MB, 9,774 rows). Does init + query fit an acceptable load budget?
2. **Pre-rendered build at 10k-page scale.** Astro generating one static
   page per document (9,774 routes). Does build time / memory hold up?
3. **Config-driven data URLs.** The 2.46 GB `text/` tree cannot live with
   the pages (rules out GitHub Pages for data); the data host must be
   swappable without code changes (TEA-906).

If any spike step fails badly, reporting the failure with numbers and the
best alternative is a valid outcome (per issue).

## Constraints

- **Neutral theme only.** All styling through CSS custom properties in one
  tokens file. No Teal Insights fonts or brand (font licence forbids use in
  the open repo; the private wrapper re-themes in S4).
- **Search is out of scope.** Issue #82 (static prebuilt index) and TEA-907
  (MotherDuck BYO-token) point different ways; S2 must not foreclose either.
  Deliverable: a componentized slot, nothing more.
- **Snapshot contract is authoritative** (README "Static snapshot for the
  web explorer"): slug identity, MANIFEST-first versioning with
  `generated_at` as cache-busting token, UTF-16 offsets for JS, documented
  nullability, text provenance caveat.
- **Open repo.** No secrets, no data files committed (root `.gitignore`
  already blocks `/data` and `dist/`).

## Approaches considered

**A. Astro static + DuckDB-WASM browse island + client-fetched text
(recommended).** Matches the issue's named stack. Browse page runs
DuckDB-WASM in a Web Worker over the parquet; doc pages are pre-rendered
from the parquet at build time with text fetched client-side from the data
URL. Pros: proves exactly the risks named in TEA-902; SQL gives S3 its
filter/aggregation engine for free; per-doc static pages give shareable
URLs. Cons: DuckDB-WASM wasm payload is heavy (several MB; measured in the
spike); worker + wasm asset wiring is the fiddly part.

**B. Astro static + hyparquet in the browser.** A pure-JS parquet reader
(tens of KB) replaces DuckDB-WASM for browse; filtering in plain JS. Pros:
tiny bundle. Cons: no SQL (S3 filters/aggregations hand-rolled), does not
answer the question TEA-902 asks. Kept as the documented fallback if the
DuckDB-WASM numbers are unacceptable.

**C. SPA (Vite + framework) with client-side routing.** One HTML shell,
`/doc/<slug>` resolved client-side. Pros: no 10k-page build. Cons: no
pre-rendered document pages (worse sharing/SEO/first-paint), contradicts
the issue's pre-render spike. Rejected; noted as fallback if the 10k build
fails badly.

Approach A is the spec below.

## Architecture

```
explorer-web/                  # standalone npm package, not a workspace
  package.json                 # exact-pinned deps, npm + package-lock.json
  astro.config.mjs             # static output, trailingSlash 'always',
                               # dev-only middleware serving SNAPSHOT_DIR at /data
  tsconfig.json                # astro/tsconfigs/strict
  .env.example                 # documents both config values
  README.md                    # dev quick start
  ARCHITECTURE.md              # decisions + spike measurements (issue deliverable)
  src/
    lib/config.ts              # THE config module (see Config)
    lib/snapshot-client.ts     # MANIFEST-first client data access
    lib/duck.ts                # DuckDB-WASM init (worker, self-hosted assets)
    lib/queries.ts             # SQL for browse (framework-agnostic, S3 reuses)
    lib/build-data.ts          # build-time parquet read (getStaticPaths source)
    styles/tokens.css          # ALL custom properties (colors, type, space)
    styles/base.css            # element defaults consuming tokens
    layouts/Base.astro         # shell: header, footer (snapshot date), slot
    components/SearchSlot.astro# empty componentized slot + pointer to #82/TEA-907
    components/DocText.astro   # island: fetch text JSON, render, show provenance
    components/BrowseTable.ts  # vanilla-TS island driving the browse table
    pages/index.astro          # '/' browse: DuckDB-WASM table + filters
    pages/doc/[slug].astro     # pre-rendered per-document page
  tests/
    fixtures/snapshot/         # committed tiny fixture (~20 rows parquet,
                               # 3 text JSONs, MANIFEST.json) for CI + vitest
    unit/*.test.ts             # vitest
  scripts/
    make-fixture.mjs           # regenerates tests/fixtures from a snapshot dir
    measure.mjs                # Playwright spike measurements (load timings)
```

### Data flow

- **Build time:** `lib/build-data.ts` reads `documents.parquet` from
  `SNAPSHOT_DIR` with **hyparquet** (pure JS; snappy via
  hyparquet-compressors). `getStaticPaths` yields one route per row; page
  pre-renders all metadata columns (issuer, country, region, income group,
  source, doc type, publication date, page count, filing_url link,
  nullability handled per contract). Text is NOT inlined (2.46 GB).
- **Runtime browse (`/`):** `lib/duck.ts` boots DuckDB-WASM in a worker
  (assets self-hosted through Vite `?url` imports, not jsDelivr — no
  third-party CDN dependency). The parquet is fetched once as an
  ArrayBuffer from `PUBLIC_DATA_BASE_URL` and registered as a buffer
  (deterministic single fetch; HTTP cacheable). `lib/queries.ts` provides
  the SQL (list newest-first with LIMIT/OFFSET, distinct filter values,
  counts). `BrowseTable.ts` renders a paginated table, a couple of working
  filters (country, source) to prove the query path, and row links to
  `/doc/<slug>/`. Full filter parity is S3.
- **Runtime doc page:** island fetches
  `${PUBLIC_DATA_BASE_URL}/text/<slug>.json?v=<generated_at>` after a
  MANIFEST-first read, renders text in `white-space: pre-wrap` (markdown
  rendering is S3), TOC list when present, provenance note, filing link.
  `has_text = false` documents render the `no_text_reason` instead.
- **MANIFEST-first (contract):** `snapshot-client.ts` fetches
  `MANIFEST.json` with `cache: 'no-store'` before any data read, validates
  `schema_version === 1` (hard error page state otherwise), exposes
  `generated_at` for cache-busting text fetches. Footer shows snapshot date.

### Config (spike risk #3)

One module, `src/lib/config.ts`, is the only place env is read:

- `PUBLIC_DATA_BASE_URL` — client-side base for MANIFEST, parquet, text.
  Dev default: `/data` (served by a dev-only Vite middleware from
  `SNAPSHOT_DIR`; nothing is copied into `public/`, so the 2.46 GB tree
  never enters the build). Production builds REQUIRE it set explicitly;
  build fails fast with a clear message if missing.
- `SNAPSHOT_DIR` — build-time path to the snapshot for `getStaticPaths`
  and the dev middleware. Default `../data/snapshot`; CI sets it to
  `tests/fixtures/snapshot`.

Swapping the data host (TEA-906) is one env var at build time. No URLs in
components.

### Staleness model (documented in ARCHITECTURE.md)

Pages are built from snapshot N; the client reads the live parquet at the
data URL. If the data host advances to N+1 before a rebuild, browse can
list docs whose pages 404 until the next build (TEA-906's build hook
closes the gap). Slug stability makes this benign; the footer's snapshot
date + manifest `generated_at` make drift visible. Recorded, not solved.

### Search slot

`SearchSlot.astro` renders a placeholder region on the browse page with a
code comment stating the contract: implementations may be a static
prebuilt index (issue #82) or MotherDuck BYO-token (TEA-907); both are
client-side and mount here. No search code, no index emission.

### Theme

`tokens.css` defines every color, font stack (system-ui), size, space, and
radius as `--ew-*` custom properties; `base.css` and components consume
tokens only. Light theme only in S2. Re-theming (S4) = swapping the tokens
file.

## Spike measurements (issue deliverable)

Recorded in `explorer-web/ARCHITECTURE.md` and commented on TEA-902:

1. **Load time (browse):** Playwright script (`scripts/measure.mjs`)
   against a locally served `dist/` + data host: DuckDB-WASM
   init ms, parquet fetch+register ms, first query ms, and page
   `load`/first-render timings. Cold (no cache) and warm.
2. **Bundle size:** total dist JS + wasm bytes; bytes actually transferred
   for `/` (the wasm bundle dominates; report gzip/br where the server
   reports it); per-doc-page HTML size.
3. **Build time:** `astro build` wall-clock + peak RSS at full scale
   (9,774 doc routes, real snapshot via `SNAPSHOT_DIR`), run via
   nohup + Monitor (harness kills long shells). Also recorded for the
   100-doc sample.
4. **100-doc sample end-to-end:** sample built with the existing builder
   (`uv run python scripts/build_snapshot.py --limit 100 --output-dir
   data/snapshot_sample`); build + serve + browse → filter → open doc →
   text loads (including the largest doc in the sample). This is the
   "spike works on 100 sample documents" checkbox.

Pass/fail is honest reporting; no target is defined in the issue, so
ARCHITECTURE.md states the numbers and a judgement with reasoning, and bad
numbers go to the issue with the best alternative (B or C above).

## Testing

- **vitest:** `config.ts` resolution rules (defaults, explicit-URL
  requirement for prod builds), `snapshot-client.ts` (manifest validation,
  version-token URL building, schema_version mismatch), `build-data.ts`
  against the committed fixture (row count, slug set, null handling).
- **CI (additive job in `.github/workflows/ci.yml`):** Node 24, `npm ci`,
  `astro check` (type/template errors), `vitest run`,
  `SNAPSHOT_DIR=tests/fixtures/snapshot astro build`, assert expected
  routes exist in `dist/`. Python jobs untouched.
- **Playwright measurement script** is the spike harness, not a CI test
  (numbers are machine-dependent).
- TDD applies to the three lib modules; Astro templates and the vanilla
  island are verified by the CI build + spike run.

## Out of scope (explicit)

- Search implementation (slot only) — issue #82 / TEA-907
- Filter parity, in-document search, markdown rendering, mobile polish,
  Lighthouse target — S3 (TEA-903)
- Theming beyond neutral tokens, brand — S4
- Deploying pages or data to a real host; hosting decision — TEA-906
  (ARCHITECTURE.md records constraints: 2.46 GB data needs an object
  store/CDN; pages fit any static host)
- Incremental/CI data refresh — TEA-906

## Definition of done (mirrors TEA-902)

- Spike works on 100 sample documents; load time, bundle size, build time
  measured and recorded
- Routing: `/` browse, `/doc/<slug>/`; data URL is a config value
- `explorer-web/ARCHITECTURE.md` records decisions and measurements
- If a spike step fails badly: failure + best alternative posted on TEA-902
- CI green; PR through external reviews + council PR gate with disposition
