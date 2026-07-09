# explorer-web architecture (S2 scaffold TEA-902; S3 parity build TEA-903)

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

- Full build: 9,775 pages, ~4.7 s build / ~5.4 s wall, peak RSS ~690 MB.
  dist 155 MB decimal (73.6 MB is the two wasm bundles; ~6.3 KB HTML per
  doc page).
- Browse cold ~1.4-1.5 s / warm ~0.8 s / throttled ~9.1-9.2 s to first
  rows (clock starts at the window load event; Lighthouse FCP/LCP cover
  the pre-load phase). DuckDB instantiate ~420 ms (6.3 s throttled: the
  wasm download lives inside it, fetched by the worker); queries
  24-36 ms steady-state.
- Cold transfer ~8.7 MB in the harness: 5.92 MB brotli wasm + ~1.4 MB
  gzipped parquet + page assets (~9.0 MB on hosts that do not compress
  the octet-stream parquet, which is the common default).
- Doc pages: 729 KB text renders in ~24 ms end-to-end. Worst case
  (29 MB, `luxse-100387641`) sits behind a click-gate (threshold 5 MB
  decimal, 15 docs over it); post-click work is ~0.4 s (fetch + JSON
  parse 48 ms + render 9.5 ms), ~2.8 s wall from navigation including
  page load and the gate click. No tab hang.
- Lighthouse on the served build: performance 100, FCP 978 ms, LCP
  1,534 ms, TBT 0, CLS 0 (DuckDB init deferred past first paint; table
  region has reserved height). S3 inherits a 100 baseline for its 90+
  target.
- bfcache: browse -> doc -> back RESTORES with the DuckDB worker alive;
  back navigation 159 ms. Measured with full Chrome and Playwright's
  default --disable-back-forward-cache switch removed, verified by a
  surviving page sentinel and pageshow.persisted === true (an earlier
  record claiming this via notRestoredReasons was methodologically
  invalid; see measurements/NOTES.md).

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
  The parquet ships as `application/octet-stream`, which most hosts will
  NOT auto-compress; either accept the 1.7 MB raw fetch (budgeted) or
  configure the host to compress it.
- **Origin-root deployment assumed:** internal links are root-relative
  (`/`, `/doc/<slug>/`; see `docPath` in `src/lib/urls.ts`). Subpath
  deployments (e.g. a GitHub Pages project page) would need Astro
  `base` support added first.
- **COOP/COEP:** not required (mvp/eh only). If threads are ever
  revisited, header configurability varies by host and COEP forces
  CORS-cleanliness on every subresource.
- **Third live origin, now self-hostable (TEA-932):** at runtime
  DuckDB-WASM autoloads `parquet.duckdb_extension.wasm` from
  extensions.duckdb.org on the first query (pre-existing behavior,
  surfaced at the S4 plan gate). When `PUBLIC_EXTENSION_BASE_URL` is set,
  `boot()` runs `INSTALL parquet FROM <base>; LOAD parquet` right after
  `db.connect()` (a local blocked-origin proof verified this redirects
  the fetch to our mirror; `custom_extension_repository` is the autoload
  fallback), so the deployed site no longer depends on that origin's
  availability. DuckDB appends `<core-version>/<wasm-platform>/<name>` to
  the base, keyed by the DuckDB core inside the wasm build (v1.4.3 for
  duckdb-wasm 1.32.0), NOT the npm string; the mirror lives under the
  versioned wasm prefix (`.../duckdb-wasm-1.32.0/ext`) so it moves
  atomically with the pin. Unset means byte-identical open-repo behavior
  (fetch from extensions.duckdb.org). The setup runs once on the single
  boot connection; the app uses exactly one connection, so if a second
  connection is ever introduced, confirm the loaded extension is visible
  to it (or move the setup to a per-database hook).

## S3 (TEA-903): parity build contracts

Spec with council dispositions:
`docs/superpowers/specs/2026-07-04-explorer-core-parity-design.md`; plan with
the plan-gate disposition: `docs/superpowers/plans/2026-07-04-explorer-core-parity.md`.

- **URL is the single source of truth for browse state.** Params: repeated
  `country`/`region`/`income`/`source` keys, `hi=1`, `scope=all`, 1-based
  `page` (omitted at 1); doc pages carry `q`. Unknown params PASS THROUGH
  verbatim on every write (a future SearchSlot param survives filter
  interactions; unit-tested). History discipline: interactions pushState
  then render from the URL; corrections (page clamp, invalid values)
  replaceState; popstate-initiated renders never write history; debounced
  writes are cancelled on popstate/pagehide; no-op writes skipped; history
  calls sit in try/catch (WebKit rate limit: 100 writes/10 s).
- **The `window.__ewDoc` contract** (for S4/TEA-907), mode-scoped as of
  B1/TEA-929: `getRawText()` returns the FULL raw string in EVERY mode (plain
  full, segmented, and rendered) once text is loaded, `null` before load and
  behind an unclicked gate. In **plain and segmented modes** (pages-source
  docs, docs over 1M units, force-listed slugs) `#ew-doc-text` holds exactly
  one text node whose content is the rendered slice and `data-seg-start`
  carries the slice's UTF-16 start offset. In **rendered mode** (markdown docs
  at or under 1M units) `#ew-doc-text` holds a rendered HTML tree wrapped in
  `<div class="ew-doc-rendered">`; the single-text-node / `data-seg-start`
  invariant does NOT hold, and search runs over the concatenation of the
  rendered text nodes (so phrases split by bold in the raw markdown match).
  Consumers detect rendered mode by the `.ew-doc-rendered` child. `?q=` is the
  only supported deep-link into a document and never bypasses the 5 MB
  click-gate (data-cost consent). In-document search controls use the
  `ew-doc-search-*` prefix; `ew-search-*` stays reserved for the slot.
- **Large documents** render in segments above 1M UTF-16 units (620 docs):
  TOC-boundary packing to 500K-unit targets, oversized sections cut at the
  last newline before each step (hard cuts never split surrogate pairs),
  fixed cuts for the 12 no-TOC large docs. Segment math is pure and
  DOM-free (`lib/doc-view.ts`). The UI says "Segment k of n", never "Part"
  (prospectuses contain literal PART I/II headings; test-guarded), with a
  notice that segments are a display convenience and not citable.
- **In-document search compute guards:** minimum query length 2; a hard
  20,000-match compute cap with look-ahead-one honesty ("20,000+") and
  per-section/per-segment counts SUPPRESSED when capped; bare-index match
  storage; whitespace-flexible and symmetrically quote-tolerant literal
  matching, offset-exact on the raw string (never lowercase the haystack).
  Highlights paint via the CSS Custom Highlight API bounded to the rendered
  segment (2,000-range cap; the current match is always painted and lives
  only in `ew-match-current`); the `::highlight()` rules live in tokens.css
  with literal var() fallbacks. Without `CSS.highlights`, counts and
  navigation still work and the current match paints via the selection.
- **Accessibility channel:** highlight paints are not reliably exposed to
  assistive tech; the per-page polite live region (`#ew-status` on browse,
  `#ew-doc-live` on doc pages, 500 ms idle, replace-text updates) carries
  counts, match positions with context snippets, and segment changes. Focus
  rules: chip removal moves focus to the next chip else the group's select;
  TOC jumps and match/segment navigation focus `#ew-doc-text`
  (tabindex -1, preventScroll); range-end nav buttons use aria-disabled,
  never disabled.
- **tokens.css stays the complete style-value inventory.** S3 added:
  `--ew-color-border-strong` (form-control boundaries; the light border is
  decorative-only), the four `--ew-color-match-*` highlight pairs,
  `--ew-font-size-doc` (+ small-screen step-up), `--ew-filters-min-height`,
  `--ew-chips-min-height`, `--ew-tap-target-min` (24px floor),
  `--ew-tap-target` (44px under 640px). PRs that add tokens list them.
- **Lighthouse commitments held:** DuckDB init starts after the window load
  event (bootstrap block in browse.ts); `#ew-table-region` keeps
  `min-height: var(--ew-table-min-height)` (now in base.css); all
  count-bearing static labels (stats, subtitle, scope-toggle count) and the
  four filter option lists are baked at build time; the hi-override hint is
  always rendered with visibility toggling so it cannot shift layout.

## Inputs for S3 (TEA-903 parity build; CONSUMED, kept for the record)

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
- **bfcache restores** with the DuckDB worker alive (measured with full
  Chrome, sentinel + pageshow.persisted, 159 ms back navigation); URL
  state (country/source/scope/page in query params via
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

S4 (TEA-904) theme-contract seams, all neutral no-ops when brand files
are absent:

- `--ew-font-display` + `--ew-font-weight-display` (defaults: body
  stack, 700) drive h1/h2; the neutral rendering is unchanged.
- Brand slots in Base.astro via `import.meta.glob`: an optional
  `src/brand/Head.astro` renders at the end of the AUTHORED head
  (before Astro's hoisted stylesheet link, which is what font preloads
  want); an optional `src/brand/Header.astro` replaces the neutral
  header (re-measure `--ew-jump-offset` against the new height).
  `src/brand/*.astro` is gitignored; see `src/brand/README.md`.
- Optional `PUBLIC_WASM_BASE_URL` (https-gated like the data URL): when
  set, the two DuckDB wasm binaries load from that base instead of the
  bundled dist assets; worker JS always stays same-origin (Worker()
  constructor restriction). The base MUST be a VERSIONED path (e.g.
  `.../duckdb-wasm-1.32.0`) when the host serves immutable caching:
  worker JS is content-hashed per deploy but this URL is stable, and a
  version bump behind an unversioned immutable URL breaks returning
  visitors with a worker/module mismatch. Note the static `?url`
  imports still emit both binaries into dist; a wrapper that sets the
  env var should strip `dist/_astro/*.wasm`.
- `src/pages/404.astro` (static hosts serve dist/404.html for unknown
  paths); `scripts/assert-dist.mjs` is SNAPSHOT_DIR-aware so a
  full-snapshot build asserts all routes, not the fixture's.
- `userMessageOf` logs the raw error to the console so live failures
  are diagnosable (data-host misconfiguration vs app bug).
- CI carries a font tripwire: `git ls-files` for font binaries must be
  empty in this repo, forever (licence).

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
