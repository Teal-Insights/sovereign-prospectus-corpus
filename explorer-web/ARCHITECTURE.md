# explorer-web architecture (S2 scaffold, TEA-902)

Decisions and spike measurements for the Astro + DuckDB-WASM explorer
scaffold. Spec with council dispositions:
`docs/superpowers/specs/2026-07-04-explorer-web-scaffold-design.md`.
Raw measurement records: `measurements/results.json` + `measurements/NOTES.md`.

## Verdict on the three spike risks (2026-07-04)

1. **In-browser DuckDB-WASM over the snapshot parquet: PASS.** Cold load
   to first rendered rows 1.35 s (localhost, compressed serving), warm
   0.80 s, throttled (4x CPU, 8 Mbps/40 ms) 9.1 s. Steady-state queries
   24-36 ms. Cold transfer ~8.7 MB, of which 5.92 MB is the brotli eh
   wasm bundle. All pre-registered budgets met; the fallback (hyparquet
   client-side, no SQL) is NOT needed, but remains documented in the spec
   should the wasm-size hosting constraint below ever become unmeetable.
2. **Pre-rendered build at 10k-page scale: PASS, decisively.** 9,775
   pages in 4.63 s (5.43 s wall), peak RSS 690 MB, on an Apple Silicon
   Mac. Budgets were 15 min / 4 GB. Build scale is a non-issue.
3. **Config-driven data URLs: PASS.** One client value
   (`PUBLIC_DATA_BASE_URL`, astro:env schema, build fails fast when
   missing or non-https) plus one build value (`SNAPSHOT_DIR`). The
   measurement harness runs pages and data on different origins, so the
   cross-origin path (CORS) is proven, not assumed.

## Stack and version decisions

- **Astro 6.4.8 (pinned `astro@6`).** npm `latest` is Astro 7; this
  scaffold was reviewed and verified against 6.x semantics. Upgrading is
  a deliberate task, not an npm accident.
- **@duckdb/duckdb-wasm 1.32.0 (exact).** The npm `latest` dist-tag
  points at a dev build (1.33.1-devNN); 1.32.0 is the newest stable
  (wraps DuckDB 1.5.4).
- **hyparquet at build time** (pure JS, snappy built in, no
  hyparquet-compressors needed): reads the snapshot parquet in Node for
  `getStaticPaths`. The browser side uses DuckDB-WASM; the two never mix.
- **Wasm bundles: mvp + eh via `selectBundle`, coi excluded.** A browser
  downloads exactly one (eh on anything modern); both sit in `dist/`
  (~74 MB artifact, see hosting constraints). coi (threads) would demand
  cross-origin isolation headers; excluded on purpose.
- **Client scripts, not framework islands.** `src/scripts/browse.ts` and
  `doc-text.ts` are plain Vite-bundled scripts (no hydration, no
  `client:*` directives). They are disposable by contract: zero SQL, zero
  fetch logic, zero URL assembly inside them; `lib/queries.ts`,
  `lib/snapshot-client.ts`, `lib/urls.ts`, and `lib/duck.ts` (DOM-free
  async API) own all of that, so S3 can swap the UI layer without
  touching the data layer.
- **Dates cross the SQL boundary as ISO strings**
  (`strftime(publication_date, '%Y-%m-%d')`): Arrow JS's Date32
  representation has varied across versions (Date objects vs epoch-ms);
  casting in SQL removes the ambiguity. Counts are cast `::INTEGER`
  (COUNT(*) is otherwise a BigInt that throws in JS arithmetic/JSON).

## Snapshot contract consumption

- **MANIFEST-first**: `MANIFEST.json` fetched `cache: 'no-store'` before
  any data read; `schema_version === 1` enforced with a visible error
  state; `generated_at` is the cache-busting token.
- **Version tokens on BOTH text and parquet**:
  `documents.parquet?v=<generated_at>` and `text/<slug>.json?v=...`
  (both files are overwritten in place at stable URLs; a long-max-age
  cache is only safe because of the token).
- **Staleness model, both directions**: pages built from snapshot N vs
  data host at N+1 shows the pinned drift notice (browse and doc pages
  compare runtime `generated_at` against the build-stamped value on
  `<body>`); client-cache staleness is eliminated by the version tokens.
  The footer snapshot date and per-page "Cite as" line are build-time
  static so citations survive JS failure and printing.

## Data credibility (S2 scope, from the council's researcher lens)

- **Sovereign scope default.** 2,178 of 9,774 rows (22.3%) are
  `is_sovereign = false` and 215 are null. Browse defaults to sovereign
  only, states it in prose ("Showing 7,381 sovereign documents."), and
  offers "Include 2,393 non-sovereign or unverified documents" with live
  counts. Every row and doc page carries a three-state badge
  (Sovereign / Non-sovereign / Unverified).
- **Classification vintage.** Region, income group, and lending category
  are the World Bank FY2027 edition applied to 1990-2026 filings; every
  rendering carries the footnote "World Bank FY2027 classification (July
  2026); reflects current status, not status at filing date." The
  vintage should travel with the data: issue #84 adds it to MANIFEST.
  **S3 note: this footnote obligation travels with any classification
  column or filter S3 adds to browse.**
- **Text provenance.** The caveat ("Text is machine-converted... Verify
  quotes against the original filing.") is server-rendered static HTML
  above the text region, with the filing link and `text_source` value.
  Markdown-sourced text additionally states it has no page anchors.
- **Null honesty.** Null dates render "undated" (814 docs, 99% of PDIP);
  other nulls render "n/a"; "Unknown" classifications are real filter
  values. Ordering is `publication_date DESC NULLS LAST, slug DESC`
  (slug tiebreak: `document_id` is rebuild-unstable by contract).

## Measurements (2026-07-04, Apple Silicon Mac, Node 24, Chromium 149)

See `measurements/NOTES.md` for tables and caveats; headlines:

- Full build: 9,775 pages, 4.63 s build / 5.43 s wall, peak RSS 690 MB.
  dist 148 MB (72 MB wasm, ~6.3 KB HTML per doc page).
- Browse cold 1,346 ms / warm 795 ms / throttled 9,101 ms to first rows;
  DuckDB instantiate ~420 ms (6.3 s throttled: the wasm download lives
  inside it, fetched by the worker); queries 24-36 ms steady-state.
- Cold transfer ~8.7 MB: 5.92 MB brotli wasm + ~1.4 MB gzipped parquet +
  page assets.
- Doc pages: 729 KB text renders in ~22 ms end-to-end. Worst case
  (29 MB, `luxse-100387641`) sits behind a click-gate (threshold 5 MB
  decimal, 15 docs over it) and renders ~2.8 s after the click with no
  tab hang (JSON parse 40 ms, render 7.8 ms).
- Lighthouse on the served build: performance 100, FCP 978 ms, LCP
  1,534 ms, TBT 0, CLS 0 (DuckDB init deferred past first paint; table
  region has reserved height). S3 inherits a 100 baseline for its 90+
  target.
- bfcache: browse -> doc -> back RESTORES (notRestoredReasons null); the
  dedicated DuckDB worker does not block bfcache in Chromium 149.

## Hosting constraints (input to TEA-906; no hosting decision made here)

- **CORS contract for the data host:** `Access-Control-Allow-Origin: *`
  (public data; avoids `Vary: Origin` cache fragmentation), GET/HEAD.
  The client sends no custom request headers, so every fetch is a CORS
  "simple request" (no preflight). R2 caveat: CORS-policy changes do not
  apply to already-cached assets until purge.
- **Cache-Control per object class:** MANIFEST `no-store`; parquet and
  text `public, max-age=31536000, immutable` (safe: version-tokened).
  HARD requirement: the data host's cache key MUST include the query
  string (Cloudflare default does; CloudFront's default CachingOptimized
  policy strips it, which would also silently disable the `?v=` scheme).
- **Compression is a stated requirement, not a provider accident.**
  Wasm: 34.2 MB raw, 5.92 MB brotli; CloudFront auto-compresses only
  objects under 10 MB, so the wasm ships raw unless precompressed at the
  origin with Content-Encoding. Text: must be served as
  `application/json` (compression is content-type-gated on Cloudflare
  and CloudFront; `application/octet-stream` silently disables it and
  the 29 MB doc ships uncompressed). Measured: the 29 MB worst case
  gzips 10.6x to ~2.7 MB; the 2.46 GB corpus is ~490 MB over the wire.
  Verification once a real host exists:
  `curl -H 'Accept-Encoding: br,gzip' -so /dev/null -w '%{size_download}' <largest text URL>`.
- **Per-host caps that veto or constrain the pages host:** Cloudflare
  Pages caps single assets at 25 MiB; a dist containing the 34 MB wasm
  cannot deploy there (escape hatch: serve the .wasm files from the data
  host via fetch+CORS; the `Worker()` constructor URL is same-origin
  restricted but the wasm binary is not). GitHub Pages sets no custom
  headers at all. Netlify post-2025 free tier is credit-metered
  (bandwidth 20 credits/GB against 300/month); serving ~6 MB of wasm per
  cold visitor from the pages host burns it fast, so prefer wasm on the
  data host there too, and record which Netlify plan the org account is
  on before wiring TEA-906's build hook.
- **Concrete viable default (recommendation only):** Cloudflare R2
  public bucket behind a custom domain: $0/month at current size, zero
  egress, per-bucket CORS, edge compression for application/json.
  `r2.dev` URLs are rate-limited and explicitly non-production.
- **MIME:** the host must serve `.wasm` as `application/wasm`
  (instantiateStreaming requires it) and `.json` as `application/json`.
- **COOP/COEP:** not required (mvp/eh only). If threads are ever
  revisited, header configurability varies by host and COEP forces
  CORS-cleanliness on every subresource.

## Inputs for S3 (TEA-903 parity build)

- **Large documents:** markdown-sourced text (9,641 docs) has NO page
  anchors in the snapshot (`pages[]` empty; the v1 Shiny page-at-a-time
  fallback is unreproducible). 3,300 markdown docs exceed v1's 200K-char
  full-render threshold. The viable strategy is chunk-by-TOC-offset:
  DocText keeps the raw fetched string reachable (`window.__ewDoc
  .getRawText()`) and renders into the single `#ew-doc-text` container,
  re-renderable in offset-addressed slices. `toc[].offset_utf16` exists;
  `pages[].offset` has no UTF-16 variant (issue #86).
- **TOC arrives only with the full text fetch.** If S3 wants TOC before
  text (or for gated docs), `build-data.ts` is the seam to pre-render it
  at build time (a local 2.46 GB read; feasible given the 5 s build).
- **Stats cards** can be computed at build time from the parquet through
  the same seam, keeping browse LCP static HTML.
- **Lighthouse baseline 100 / CLS 0** comes from two commitments S3 must
  keep: DuckDB init deferred until after first paint, and reserved
  layout (`--ew-table-min-height`) for the table region.
- **bfcache restores** with the DuckDB worker alive (measured, Chromium
  149); URL state (country/source/scope/page in query params via
  `history.replaceState`) already round-trips through back/forward.
- **The vintage footnote obligation travels** with any classification
  column/filter S3 adds (see Data credibility).

## Search slot

`src/components/SearchSlot.astro` is the mount point and deliberately
empty. Corpus-wide search architecture is decided in the search spec,
not here; both candidates (static prebuilt index, GitHub issue #82;
MotherDuck BYO-token, TEA-907) are client-side and mount in this slot.
S2 emits no index and adds no server dependency.

## Theme

`src/styles/tokens.css` holds every color, font stack, size, space, and
radius as `--ew-*` custom properties; `base.css` and components consume
tokens only. Neutral, light-only, system fonts. S4's private wrapper
re-themes by swapping the tokens file; no Teal Insights brand or fonts
exist in this package (font licence).

## Known dev-environment notes

- `astro preview` does not serve `/data` (the middleware is dev-only);
  use `scripts/serve-static.mjs` for a served build.
- Vite pre-bundling is excluded for `@duckdb/duckdb-wasm`
  (`optimizeDeps.exclude`), the documented workaround for dev-mode
  worker resolution issues.
- Lighthouse cannot drive Playwright's chromium-headless-shell (NO_FCP);
  use system Chrome or point CHROME_PATH at a full Chromium.
- Wasm network cost hides inside `instantiateMs` (the worker fetches
  it); page-level CDP shows 0 wasm bytes. See measurements/NOTES.md.
