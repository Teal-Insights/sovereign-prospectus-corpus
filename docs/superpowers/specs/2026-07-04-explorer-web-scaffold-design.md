# explorer-web scaffold + spike (TEA-902, S2) — design

**Date:** 2026-07-04 (v2, post council spec gate)
**Issue:** TEA-902 (Explorer v2 project)
**Status:** Council-reviewed; disposition at end of this doc

## Problem

The Explorer v2 sprint replaces the Streamlit/Shiny explorers with a static
web explorer served from the snapshot contract built in S1 (PR #78). Before
building features (S3 parity, S4 private wrapper), three architectural risks
need proving with numbers:

1. **In-browser DuckDB-WASM** querying `data/snapshot/documents.parquet`
   (1.7 MB, 9,774 rows). Does init + query fit an acceptable load budget?
   Note the asymmetry the council quantified: the query engine is ~34 MB
   raw wasm (5.9-7.6 MB compressed) for a 1.7 MB dataset.
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
  `generated_at` as cache-busting token, documented nullability, text
  provenance caveat. Offsets: `toc[].offset_utf16` exists for JS indexing;
  `pages[].offset` is code-point only (no UTF-16 variant — recorded as a
  contract follow-up issue, S3 input).
- **Open repo.** No secrets, no data files committed (root `.gitignore`
  blocks `/data` and `dist/`; this task adds `explorer-web/.gitignore` for
  `node_modules/`, `.astro/`, `dist/`, `.env`).

## Approaches considered

**A. Astro static + DuckDB-WASM browse page + client-fetched text
(recommended).** Matches the issue's named stack. Browse page runs
DuckDB-WASM in a Web Worker over the parquet; doc pages are pre-rendered
from the parquet at build time with text fetched client-side from the data
URL. Pros: proves exactly the risks named in TEA-902; SQL gives S3 its
filter/aggregation engine for free; per-doc static pages give shareable
URLs. Cons: the wasm engine is ~34 MB raw / ~6-7.6 MB compressed —
measured honestly in the spike against pre-registered budgets (below).

**B. Astro static + hyparquet in the browser.** A pure-JS parquet reader
(~10 KB class) replaces DuckDB-WASM; filtering in plain JS. The council's
empirical check (full-table hyparquet read of a same-shape 9,774-row file:
17 ms) makes this a credible fallback, not a strawman. Cons: no SQL (S3
filters/aggregations hand-rolled). Trigger conditions below.

**C. SPA (Vite + framework) with client-side routing.** One HTML shell,
`/doc/<slug>` resolved client-side. Pros: no 10k-page build. Cons: no
pre-rendered document pages (worse sharing/SEO/first-paint), contradicts
the issue's pre-render spike. Fallback only if the 10k build fails badly.

Approach A is the spec below.

## Versions (pin exactly in package.json)

- **Astro 6.x** (requires Node >= 22.12, even-numbered; Node 24 LTS is the
  toolchain locally and in CI)
- **@duckdb/duckdb-wasm 1.32.0** — newest STABLE. npm's `latest` dist-tag
  currently points at a dev build (1.33.1-dev57.0); `npm i` without an
  exact version pins a snapshot the DuckDB team never released.
- **hyparquet** (current 1.26.x) — snappy support is built in; the
  `hyparquet-compressors` package is NOT needed (council verified
  empirically against a DuckDB-written snappy file).
- **@astrojs/check + typescript ^5** as devDependencies (`astro check`
  errors in CI without them).
- vitest, playwright (measurement harness) as devDependencies.

## Architecture

```
explorer-web/                  # standalone npm package, not a workspace
  package.json                 # exact-pinned deps + package-lock.json
  astro.config.mjs             # static output, trailingSlash 'always',
                               # astro:env schema, dev-only /data middleware,
                               # vite.optimizeDeps.exclude duckdb-wasm
  tsconfig.json                # extends astro/tsconfigs/strict
  .gitignore                   # node_modules/, .astro/, dist/, .env
  .env.example                 # documents both config values
  README.md                    # dev quick start
  ARCHITECTURE.md              # decisions + spike measurements (issue deliverable)
  src/
    lib/config.ts              # single config consumer surface (see Config)
    lib/snapshot-client.ts     # MANIFEST-first client data access
    lib/duck.ts                # DuckDB-WASM init (worker, self-hosted assets)
    lib/queries.ts             # SQL for browse (framework-agnostic, S3 reuses)
    lib/format.ts              # shared formatters (dates, sizes, null tokens)
    lib/build-data.ts          # build-time parquet read (getStaticPaths source)
    styles/tokens.css          # ALL custom properties (--ew-*)
    styles/base.css            # element defaults consuming tokens
    layouts/Base.astro         # shell: header, footer (static snapshot date), slot
    components/SearchSlot.astro# empty componentized slot + pointer to #82/TEA-907
    components/DocText.astro   # doc text region: static caveat + client script
    scripts/browse.ts          # client script driving the browse table
    scripts/doc-text.ts        # client script fetching/rendering text JSON
    pages/index.astro          # '/' browse
    pages/doc/[slug].astro     # pre-rendered per-document page
  tests/
    fixtures/snapshot/         # committed fixture (see Fixture requirements)
    unit/*.test.ts             # vitest
  scripts/
    make_fixture.py            # regenerates tests/fixtures from a snapshot dir
                               # (Python + duckdb: the same writer as the real
                               # builder, so the parquet type layout matches)
    serve-static.mjs           # CORS + compression static server (measurement + manual use)
    measure.mjs                # Playwright spike measurements
```

Terminology note: `browse.ts`/`doc-text.ts` are plain client scripts loaded
from `<script>` in `.astro` pages — not Astro islands (no framework, no
hydration directives). ARCHITECTURE.md uses this vocabulary so S3 doesn't
go looking for `client:*` directives.

### Data flow

- **Build time:** `lib/build-data.ts` reads `documents.parquet` from
  `SNAPSHOT_DIR` with hyparquet, **once at module level** (not per-route).
  `getStaticPaths` yields one route per row (slug params are strings —
  Astro 6 rejects numeric params); page pre-renders all metadata columns.
  hyparquet returns DATE as JS `Date` and metadata counts as BigInt —
  normalized at the `build-data.ts` boundary. Text is NOT inlined.
- **Runtime browse (`/`):** `lib/duck.ts` boots DuckDB-WASM in a Web
  Worker; assets self-hosted via Vite `?url` imports (documented duckdb.org
  pattern), `selectBundle` restricted to **mvp + eh only** (never coi — no
  cross-origin-isolation requirement; ~74 MB of wasm sits in `dist/` but a
  browser downloads exactly one bundle; per-host artifact caps recorded in
  ARCHITECTURE.md). Init is **deferred until after first paint** and the
  table region reserves fixed-height layout (S3 inherits a Lighthouse 90+
  target; don't bake in a bad loading sequence). The parquet is fetched as
  `documents.parquet?v=<generated_at>` (MANIFEST is read first, so the
  token is in hand; `encodeURIComponent` it), converted
  `new Uint8Array(await resp.arrayBuffer())`, registered via
  `registerFileBuffer` (guard against re-registration on HMR/remount).
  `lib/queries.ts` owns ALL SQL: newest-first list with explicit
  `ORDER BY publication_date DESC NULLS LAST, slug DESC` (pin the null
  order; don't rely on engine defaults; tiebreak by slug, never
  document_id, which is rebuild-unstable), LIMIT/OFFSET pagination,
  DISTINCT filter values, counts cast `::INTEGER` (COUNT(*) returns BigInt
  which throws in JS arithmetic/JSON), rows materialized via `.toJSON()`
  (Arrow StructRow proxies), DATE columns arrive as epoch-ms numbers
  (Arrow JS) — one shared UTC formatter in `format.ts` accepts
  `number | Date | null` so build-time and runtime render identically.
- **Browse spike UI:** paginated table + two working filters (country,
  source) + an is_sovereign scope control (below), reading initial state
  from `location.search` and writing filter changes back via
  `history.replaceState` — proves the URL-state pattern S3 needs (TEA-903
  "filters in query params"). `scripts/browse.ts` is disposable by
  contract: zero SQL, zero URL construction, zero fetch logic inside it —
  all in `queries.ts`/`snapshot-client.ts`/`duck.ts`, which expose DOM-free
  async APIs callable from any future framework island.
- **Runtime doc page:** `scripts/doc-text.ts` fetches
  `text/<slug>.json?v=<generated_at>` MANIFEST-first. Size affordance:
  `text_bytes` is pre-rendered into the page; loads show "Loading N MB…";
  documents over 5 MB load only on explicit click (15 docs exceed 5 MB;
  max 29 MB). Text renders `white-space: pre-wrap` into a single container
  that can be re-rendered in offset-addressed slices, and the raw fetched
  string stays accessible on the script's state (S3's large-doc
  chunk-by-TOC-offset strategy and highlighting depend on both). TOC list
  when present. `has_text = false` renders `no_text_reason`.
- **MANIFEST-first (contract):** `snapshot-client.ts` fetches
  `MANIFEST.json` with `cache: 'no-store'` before any data read, validates
  `schema_version === 1` (visible error state otherwise), exposes
  `generated_at`. No custom request headers on any data fetch — everything
  stays a CORS "simple request" (no preflight).
- **Error states:** every failure mode gets a visible error state, not a
  blank region: manifest fetch/validation failure, parquet fetch failure,
  wasm init failure, text fetch failure. One shared error-rendering helper.

### Data credibility (from the researcher lens — S2 scope, not deferred)

- **is_sovereign:** 2,178 rows (22.3%) are `is_sovereign = false` (the 50
  MANIFEST conflict issuers), 215 null. Browse defaults to
  `is_sovereign = true` with a visible scope control: "Showing 7,381
  sovereign documents. Include 2,393 non-sovereign or unverified" (counts
  from SQL, not hardcoded). Doc pages and the browse table render a
  three-state badge: Sovereign / Non-sovereign / Unverified (null).
  A tool billed as a sovereign corpus must not present UniCredit shelf
  filings as Republic of Cyprus paper to an IMF audience.
- **Classification vintage:** region / income group / lending category are
  the vendored World Bank FY2027 edition applied to 1990-2026 filings.
  Everywhere they render (doc page, browse column headers), a static
  footnote: "World Bank FY2027 classification (July 2026); reflects
  current status, not status at filing date." Constant in `format.ts` for
  S2; a GitHub issue moves the vintage into MANIFEST (S1 contract).
- **Text provenance:** pinned wording rendered STATICALLY in the
  pre-rendered doc-page HTML above the text region (survives JS failure,
  printing, archiving): "Text is machine-converted (Docling markdown or
  extracted page text), not a facsimile of the filed PDF. Verify quotes
  against the original filing." with the filing_url link and the
  `text_source` value shown. Markdown-sourced text has no page anchors —
  stated on the page (page citations are non-negotiable in this domain;
  the tool must say when it cannot supply one).
- **Null honesty:** null `publication_date` renders as "undated" (814
  docs, 99% of the PDIP set — never blank, never a fake date); null
  `doc_type`/`issuer_name`/etc. render as an explicit em-dash-free "—"
  token via `format.ts`. "Unknown" country/region/income appear as real
  filter values.
- **Citability:** the build-time `snapshot_date` is stamped statically
  into every page footer; doc pages carry "Cite as: Sovereign Prospectus
  Corpus snapshot <date>, <slug>". The client compares the runtime
  MANIFEST `generated_at` against the build-stamped value and shows a
  small "data is newer than this page" notice on drift.

### Config (spike risk #3)

`astro.config.mjs` declares the `astro:env` schema:
`PUBLIC_DATA_BASE_URL` as `envField.string({ context: 'client', access:
'public' })` — **no default in production builds**, so a missing value
aborts the build with `EnvInvalidVariables` (this is the fail-fast
mechanism; `import.meta.env` inlining alone would silently bake
`undefined`). Dev default `/data`. `src/lib/config.ts` re-exports from
`astro:env/client` and is the only import surface components use; it also
rejects non-https values in production builds (mixed-content) and owns
URL-join semantics (tested).

`SNAPSHOT_DIR` is read in `astro.config.mjs` via Vite `loadEnv()` —
`.env` files are NOT auto-loaded inside config files (Astro documented
behavior), and `.env.example` documents this. Default `../data/snapshot`;
CI sets `tests/fixtures/snapshot`.

The dev-only middleware (Astro integration `astro:server:setup`) serves
`SNAPSHOT_DIR` at `/data` during `astro dev` only — real 404s for missing
files (no SPA fallback), correct Content-Types (`application/json`,
`application/octet-stream` for parquet). It does NOT exist in
`astro preview` — the measurement harness brings its own servers (below).

CI builds set `PUBLIC_DATA_BASE_URL=https://data.example.invalid` (any
https dummy) alongside the fixture `SNAPSHOT_DIR`.

### Staleness model (documented in ARCHITECTURE.md)

Pages are built from snapshot N; the client reads the live parquet at the
data URL. Both drift directions are handled: build-vs-data drift (browse
lists docs whose pages 404 until TEA-906's build hook rebuilds — benign,
made visible by the drift notice) and client-cache drift (solved: parquet
and text both carry `?v=<generated_at>`, so long-max-age caching is safe).

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

Recorded in `explorer-web/ARCHITECTURE.md` and commented on TEA-902.

**Harness:** `scripts/serve-static.mjs` runs TWO instances on different
ports — pages origin serving `dist/`, data origin serving the snapshot —
so every fetch is genuinely cross-origin (CORS proven, not assumed). The
data origin sends `Access-Control-Allow-Origin: *`; both serve compressed
responses (brotli/gzip: wasm precompressed at measure time, JSON/parquet
compressed on the fly) with correct MIME types (`application/wasm` — also
required for `instantiateStreaming`). Encodings and transfer sizes are
recorded per object class. Playwright drives Chromium; cold = fresh
browser context, warm = second navigation in the same context.

1. **Load time (browse):** DuckDB-WASM wasm fetch ms vs compile+
   instantiate ms (split), which bundle `selectBundle` chose, parquet
   fetch+register ms, **first query ms and second query ms separately**
   (council measured ~800 ms one-time warm-up vs 4-7 ms steady-state —
   conflating them would misjudge the architecture), first table render.
   Cold and warm. One additional run with Playwright CPU 4x + slow-network
   throttling (the budget judgement must not be calibrated on an M-series
   Mac). Record JS heap / wasm memory after init.
2. **Bundle size:** total dist JS + wasm bytes (artifact), bytes
   TRANSFERRED for `/` cold (compressed — the primary number), per-doc-page
   HTML size.
3. **Build time:** `astro build` wall-clock + peak RSS at full scale
   (9,774 routes, real snapshot), via nohup + Monitor. Also the 100-doc
   sample build.
4. **100-doc sample end-to-end:** browse → filter → open doc → text loads,
   against `data/snapshot_sample` (already built). This is the "spike
   works on 100 sample documents" checkbox.
5. **Worst-case document:** fetch+parse+render of `luxse-100387641`
   (29,031,849 bytes, the global max) from the full snapshot — the sample
   maxes at 2.3 MB, 12x below reality; the spike must see the real worst
   case. Record fetch, JSON parse, and render/layout ms, and that the
   over-5 MB click-gate engaged.
6. **Lighthouse:** one `lighthouse` run against the built browse page
   (record performance score, LCP element, TBT, CLS) — S3 inherits a 90+
   target and needs the S2 baseline.
7. **bfcache:** browse → doc → back; record restore vs full reload via
   `performance.getEntriesByType('navigation')[0].notRestoredReasons` and
   warm back-nav time (S3 inherits "working back/forward"; a dedicated
   worker may block bfcache — measure, don't guess).

### Pre-registered soft budgets (judgement anchors, not hard gates)

- Browse cold, broadband, compressed: interactive (first rendered rows)
  **< 5 s**; warm **< 2 s**; throttled cold **< 15 s**.
- Compressed critical-path transfer for `/` cold: **< 10 MB**.
- Full build: **< 15 min** wall, peak RSS **< 4 GB**.
- Doc page p50 text (40 KB): visible **< 1 s** broadband.
- **Fallback-B recommendation triggers** (pre-declared so the post-hoc
  judgement is falsifiable): cold broadband interactive > 8 s, or
  compressed critical-path transfer > 12 MB, or full build > 30 min or
  OOM (that last one triggers fallback C discussion instead). Numbers
  between budget and trigger: report, judge with reasoning.

## Hosting constraints (recorded in ARCHITECTURE.md for TEA-906; no
hosting decision in S2)

- **CORS contract for the data host:** `Access-Control-Allow-Origin: *`
  (public data; avoids Vary: Origin cache fragmentation), GET/HEAD.
  Client sends no custom headers (no preflight). R2 caveat: CORS changes
  don't apply to already-cached assets until purge.
- **Cache-Control per object class:** MANIFEST `no-store` (or
  `max-age=0, must-revalidate`); parquet + text
  `public, max-age=31536000, immutable` (safe: version-tokened). Hard
  requirement: the data host's cache key MUST include the query string
  (Cloudflare default yes; CloudFront's default CachingOptimized policy
  strips it — which would also silently disable the `?v=` scheme — use a
  query-string-aware policy).
- **Compression is a stated requirement, not a provider accident:** text
  must be uploaded/served as `application/json` (compression is
  content-type-gated on Cloudflare and CloudFront; octet-stream silently
  disables it → the 29 MB doc ships uncompressed). Wasm must be served
  precompressed (~6.8 MB br) — CloudFront auto-compresses only objects
  under 10 MB, so the 34 MB wasm ships raw unless precompressed at
  origin. Verification step: `curl -H 'Accept-Encoding: br,gzip'` against
  the largest text object on the real host. Measured: the 2.46 GB corpus
  is ~490 MB over-the-wire gzipped (5.06x on a 200-file sample); the
  29 MB worst case gzips 10.6x to 2.7 MB.
- **Per-host caps that veto or constrain:** Cloudflare Pages caps single
  assets at 25 MiB — a dist containing the 34 MB wasm cannot deploy there
  (escape hatch: serve the .wasm from the data host via plain fetch+CORS;
  the Worker() constructor is same-origin-restricted but the wasm binary
  is not). GitHub Pages: no custom headers at all. Netlify post-2025
  credit-model free tier: 300 credits/month (bandwidth 20 credits/GB —
  wasm on the pages host burns it fast; record which plan the org account
  is on).
- **Concrete viable default (recommendation only):** Cloudflare R2 public
  bucket behind a custom domain — $0/month at current size, zero egress,
  per-bucket CORS, edge compression for application/json; `r2.dev` URLs
  are rate-limited and non-production.
- **COOP/COEP:** not required (mvp/eh bundles only; coi excluded). If
  ever revisited, header configurability varies by host and COEP forces
  CORS-cleanliness on every subresource.

## Fixture requirements

`tests/fixtures/snapshot/` is generated by `scripts/make-fixture.mjs` from
a real snapshot dir and committed (~20 rows). It MUST include: a markdown
doc with non-empty toc; a pages-sourced doc; a `has_text=false` doc with
`no_text_reason`; a null `publication_date` row; an "Unknown"
country/region/income row; an `is_sovereign=false` row; an
`is_sovereign` null row; a High income row. Invariant: `has_text`/
`text_bytes` stay consistent with the shipped JSON files (every
`has_text=true` fixture row has its text JSON present). MANIFEST.json
included with correct counts.

## Testing

- **vitest:** `config.ts` (URL join, https requirement, defaults),
  `snapshot-client.ts` (manifest validation, version-token URL building,
  schema mismatch error), `build-data.ts` against the fixture (row count,
  slug set, null handling, Date/BigInt normalization), `format.ts` (UTC
  date rendering for number|Date|null, size formatting, null tokens),
  `queries.ts` SQL-string assembly (null order + tiebreak present).
- **CI (additive job in `.github/workflows/ci.yml`):** Node 24, `npm ci`,
  `astro check`, `vitest run`, fixture build
  (`SNAPSHOT_DIR=tests/fixtures/snapshot`,
  `PUBLIC_DATA_BASE_URL=https://data.example.invalid`), assert expected
  routes exist in `dist/`. Python jobs untouched.
- **Smoke both modes:** the spike exercises `astro dev` AND the built
  output (duckdb-wasm's Vite dev-mode pre-bundling issues differ from
  build; `optimizeDeps.exclude: ['@duckdb/duckdb-wasm']` set from the
  start).
- **Playwright measurement script** is the spike harness, not a CI test.
- TDD applies to the lib modules; Astro templates and client scripts are
  verified by the CI build + spike run.

## Out of scope (explicit)

- Search implementation (slot only) — issue #82 / TEA-907
- Full filter parity, in-document search/highlighting, markdown rendering,
  mobile polish, meeting the Lighthouse 90+ target (S2 records the
  baseline), doc_type glossary/tooltips — S3 (TEA-903)
- Build-time stats cards (recommended to S3 in ARCHITECTURE.md — the
  `build-data.ts` seam supports it; not implemented in S2)
- Theming beyond neutral tokens, brand — S4
- Deploying pages or data to a real host; the hosting decision — TEA-906
  (constraints recorded above)
- Snapshot-contract changes (classification vintage in MANIFEST,
  unmapped_issuers audit gap, pages[].offset_utf16) — filed as GitHub
  issues against the snapshot builder

## Definition of done (mirrors TEA-902)

- Spike works on 100 sample documents; load time, bundle size, build time
  measured and recorded
- Routing: `/` browse, `/doc/<slug>/`; data URL is a config value
- `explorer-web/ARCHITECTURE.md` records decisions and measurements
- If a spike step fails badly: failure + best alternative posted on TEA-902
- CI green; PR through external reviews + council PR gate with disposition

## Council spec-gate disposition (2026-07-04)

Six fresh-context reviewers: independent generalist, Astro/static-build,
DuckDB-WASM/Arrow, S3 consumer (TEA-903), sovereign-debt researcher,
deploy/hosting. All findings web-verified by the finding reviewer against
primary docs (duckdb.org, docs.astro.build, npm registry tarballs, World
Bank OGHIST, provider docs) or measured empirically against the real
snapshot. High convergence: parquet cache-busting, CORS-in-harness, the
unmeasured 29 MB worst case, and the hyparquet-snappy error were each
found independently by 3 reviewers; wasm sizes measured independently by
2 with matching numbers.

**Accepted (incorporated above):** is_sovereign surfacing with default
sovereign scope + badge; FY2027 classification vintage footnote; static
pinned provenance caveat + text_source; NULLS LAST + slug tiebreak +
"undated" token; 29 MB worst-case measurement + over-5 MB click-gate +
slice-addressable text container; wasm size corrected to 34 MB raw /
6-7.6 MB compressed + compression as a stated host requirement +
fallback-B empirical grounding; parquet `?v=` token + per-class
Cache-Control + query-string-in-cache-key requirement; CORS contract +
cross-origin measurement harness; `astro:env` schema as the fail-fast
mechanism; `loadEnv` for SNAPSHOT_DIR in config; CI dummy data URL; pins
(Astro 6.x, duckdb-wasm 1.32.0 stable not npm-latest, @astrojs/check +
typescript); hyparquet-compressors dropped; DATE-as-number / BigInt type
adapters + shared UTC formatter; first-vs-second query split + wasm
fetch/compile split + memory + throttled run + bundle-choice logging;
Lighthouse baseline + deferred init + reserved layout; bfcache
measurement; URL-state on the spike filters; disposability promises
(browse.ts has no SQL/fetch/URL logic; duck.ts DOM-free API);
explorer-web/.gitignore; optimizeDeps.exclude + dev-and-build smoke;
registerFileBuffer Uint8Array + re-register guard; dev middleware real
404s; https-only prod data URL; URL-join tests; fixture required shapes +
has_text invariant; visible error states for all four failure modes;
pre-registered soft budgets; snapshot date stamped statically + drift
notice + cite-as line; "client scripts" not "islands" terminology;
`pages[].offset` UTF-16 wording fix.

**Modified with reasoning:** (1) eh-only bundle pin (Astro reviewer)
rejected in favor of selectBundle over mvp+eh: browser vintage on
IMF/WB-managed laptops is unknown, a browser downloads exactly one
bundle, and the cost — a ~74 MB deploy artifact — is recorded with
per-host caps instead. coi stays excluded. (2) Build-time stats cards
(S3 reviewer): good idea, S3 scope; recorded as recommendation, not
built. (3) Netlify/R2 hosting findings: recorded as ARCHITECTURE.md
constraints + a default recommendation; the decision itself stays with
TEA-906.

**Deferred to GitHub issues (S1 snapshot-contract scope, not S2):**
classification_vintage in MANIFEST; unmapped_issuers audit list missing
null-named issuers (215 docs invisible to the audit); pages[].offset
lacking offset_utf16. Also: TEA-903's parity pointer names
demo/shiny-app/ but the real v1 target is shiny/app.py — noted on the
Linear issues.
