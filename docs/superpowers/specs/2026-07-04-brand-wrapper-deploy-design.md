# S4 (TEA-904): Private brand wrapper + Netlify deploy design

Date: 2026-07-04, revised post-spec-gate. Issue: TEA-904. Upstream base:
`f80ed97` (PR #90, S3 parity build, on main); the wrapper pins the merge
SHA of the S4 seams PR described in D2 (see D1). Companion docs:
`explorer-web/ARCHITECTURE.md` (theme contract + hosting constraints),
the Klim Web Font Licence (verified against klim.co.nz 2026-07-04),
`tealinsights-site/LICENSE-FONTS.md`.

## Goal

The branded explorer live at prospectus.tealinsights.com: a new PRIVATE
repo `Teal-Insights/prospectus-web-ti` that pulls explorer-web at a
pinned ref, overrides the neutral theme with Teal Insights brand
(Tiempos Headline display, Soehne UI/body), and deploys to a new Netlify
site. No application logic in the private repo. Fonts live only in the
private repo and are served only from the subdomain. Data hosting
resolved. Teal does DNS records and dashboard logins from a numbered
handoff list.

## Verified facts the design rests on

- **DNS:** tealinsights.com nameservers are Google Cloud DNS
  (ns-cloud-e*.googledomains.com). Apex A 75.2.60.5 (Netlify LB), www
  CNAME tealinsights.netlify.app. No prospectus record yet. Consequence:
  **R2 custom domains are unavailable without moving the zone to
  Cloudflare** (R2 custom domains require the domain to be a zone in the
  same Cloudflare account; partial/CNAME setup is Business tier).
- **Klim licence (primary source, 2026-07-04):** modification prohibited
  except a narrow subsetting carve-out (3g, file-size reduction only;
  not needed at 37-40 KB/file); WOFF2 only (3a); third-party hosting
  allowed only if the provider adheres to the licence (3e); affirmative
  hotlink AND direct-download protection obligation (3d, "reasonable
  measures"); subdomains of the licensed second-level domain are covered
  (1f), subject to the aggregate page-view tier across all sites
  (3a/3b); public repos = redistribution (1d, 3f, 3j). Fonts must never
  reach an unlicensed hostname: **netlify.app is an unlicensed
  hostname**, Netlify never auto-redirects it, and the spec gate
  verified the main site is serving Soehne from
  tealinsights.netlify.app with HTTP 200 today (separate fix, on the
  handoff).
- **Theme contract:** `src/styles/tokens.css` is the complete style-value
  inventory (S3 added 12 tokens; the ::highlight() rules live in
  tokens.css with literal var() fallbacks). base.css consumes tokens
  only. h1/h2 have no font-family or font-weight rules of their own
  (system UA bold 700 today). `.ew-header` is a text link;
  explorer-web has no public/ directory and no favicon; Base.astro has
  no head seam (no favicon link, no analytics, no OG tags; OG images
  are S5 scope). No 404 page exists upstream.
- **Wasm:** dist carries both bundles, 34.2 MB (eh) + 39.4 MB (mvp) raw;
  5.92 MB brotli for the one a modern browser downloads. Worker JS is
  773 KB (eh). duck.ts imports both via Vite `?url` (static imports:
  both binaries land in dist regardless of any env override); the
  Worker() constructor is same-origin restricted, the wasm binary is
  not. duck.ts derives bundleName by identity comparison with the
  imported URL (breaks under an override; the seams PR fixes it).
- **Build inputs:** the Astro build reads only documents.parquet
  (1.75 MB) + MANIFEST.json via SNAPSHOT_DIR; the 2.46 GB text/ corpus
  is client-fetched from PUBLIC_DATA_BASE_URL (build gate requires
  https, localhost excepted). Tokens/base CSS ships as one LINKED
  stylesheet (5.9 KB raw); fonts declared there are discovered after
  the CSS fetch.
- **Fonts on hand:** 5 WOFF2 files, 37-40 KB each (~193 KB total).
  Extracted metrics (fontTools, read-only): Soehne asc 1.171 desc
  -0.423 linegap 0, avg width 0.4715 (Buch) vs Arial 0.4725
  (size-adjust ~100%); Tiempos Headline SB asc 0.962 desc -0.25, avg
  width 0.4864 vs Georgia 0.4636 (size-adjust ~104.9%). --ew-line-height
  is 1.55 unitless everywhere, so line boxes are metric-independent;
  residual swap risk is wrap-shift only.
- **Netlify (primary docs, 2026-07-04):** pre-2025-09-04 accounts keep
  legacy plans (Free 100 GB/mo bandwidth; Pro 1 TB/mo); newer accounts
  are credit-metered (Free 300 credits/mo, bandwidth 20 credits/GB, 15
  credits per successful production deploy). CDN cache key does NOT
  include query strings for static assets (Netlify-Vary exists; atomic
  deploys invalidate the CDN anyway). `_headers` sets Cache-Control
  freely but Content-Encoding is forbidden: pre-compressed serving is
  impossible; edge brotli documented for text assets only. HTML default
  is `public, max-age=0, must-revalidate` with atomic invalidation:
  new deploys show immediately. 54,000 files per directory cap. Public
  https submodules clone with zero config. Deploys are
  content-addressed and atomic. External-DNS subdomain = CNAME to
  <sitename>.netlify.app with automatic Let's Encrypt; the site and
  custom domain should exist BEFORE the CNAME (Netlify docs order).
  Deploy Previews are public at enumerable
  deploy-preview-N--<site>.netlify.app URLs; deploy permalinks
  (<deploy-id>--<site>.netlify.app) cannot be disabled (unguessable
  IDs; accepted residual risk). NODE_VERSION env or .nvmrc pins Node.
- **Cloudflare (primary docs, 2026-07-04):** every
  Cloudflare-hosted-data path (R2 custom domain, Worker custom domain,
  functional Cache API) requires the tealinsights.com zone on
  Cloudflare first. r2.dev is dev-only; workers.dev is hobby-tier and
  its Cache API is a documented no-op. R2 requires a payment method
  even for free tier.
- **AWS (primary docs, 2026-07-04):** CloudFront 1 TB/mo + 10M req/mo
  always-free survives the 2025 pricing changes on pay-as-you-go (new
  accounts should take the PAID account plan; the "Free account plan"
  auto-closes after 6 months). CloudFront edge-compresses only 1 KB to
  10 MB objects; S3 objects stored with Content-Encoding metadata pass
  through untouched and are never re-compressed. Managed
  UseOriginCacheControlHeaders-QueryStrings includes Host in the cache
  key, and Host-based caching is documented as UNSUPPORTED for S3
  origins (S3 resolves buckets by Host: guaranteed 403s), so a CUSTOM
  cache policy is required (five fields, below). SimpleCORS response
  headers policy adds `ACAO: *` to CORS requests without touching
  bucket config, on cache hits too. ACM cert in us-east-1, DNS
  validation CNAMEs at any provider; distribution CNAME at any
  provider; apex would not work on external DNS but subdomains do. S3
  ~2.5 GB + monthly PUTs ~ $0.06-0.11/mo.

## Design decisions

### D1: How the wrapper pins and pulls explorer-web

**Decision: git submodule of the open repo; build runs against a staging
copy. The pin is the merge SHA of the D2 seams PR (which builds on
f80ed97), stated explicitly: the seams PR merges upstream FIRST, then
the wrapper pins that commit.**

- The open repo is small (8.7 MB .git), so a submodule clone is cheap.
- npm-tarball install is not viable: explorer-web is an unpublished
  subdirectory of the monorepo.
- A build-time tarball fetch hides the pin in a script variable and
  re-downloads every build. The submodule makes the pin a first-class,
  reviewable gitlink: bumping it is a one-line diff in a PR.
- The build never mutates the submodule worktree: `scripts/build.sh`
  rsyncs `upstream/explorer-web/` to a gitignored `.build/` staging dir
  (excluding node_modules, dist, .astro), overlays `brand/`, and builds
  there. The submodule stays pristine.
- README pin-bump procedure: bump gitlink, diff upstream tokens.css
  token NAMES against the branded copy (S3 added 12 in one PR; that
  will recur), re-run wrapper CI, redeploy.

### D2: Where the brand override lives (the no-application-logic line)

**Decision: ONE upstream PR to explorer-web ("S4 seams") adds a neutral
brand contract; the wrapper supplies only assets and markup.** Contents
of the seams PR, every item a no-op when brand files are absent:

1. **`--ew-font-display` + `--ew-font-weight-display` tokens**
   (defaults: the body stack and 700), consumed by
   `h1, h2 { font-family: var(--ew-font-display); font-weight:
   var(--ew-font-weight-display); }` in base.css. Neutral rendering is
   byte-identical (system stack at UA-bold 700, exactly today's
   output); the wrapper sets Tiempos + 600.
2. **Brand slots in Base.astro** via eager `import.meta.glob`: if
   `src/brand/Head.astro` exists it renders at the end of `<head>`; if
   `src/brand/Header.astro` exists it replaces the neutral header
   markup. `src/brand/` ships with a README documenting the contract
   (neutral examples only: no Klim names or URLs) and a .gitignore for
   content.
3. **Optional `PUBLIC_WASM_BASE_URL` env** (astro:env, optional): when
   set, duck.ts uses `<base>/duckdb-eh.wasm` / `<base>/duckdb-mvp.wasm`
   as mainModule URLs; worker JS always stays same-origin. Fix
   bundleName derivation to not depend on URL identity. When unset,
   byte-identical behavior.
4. **`src/pages/404.astro`** (neutral, uses Base): Astro emits
   dist/404.html, which Netlify serves automatically for unknown paths.
   Closes the S5 QA gap for truncated /doc/ URLs.
5. **Diagnostics one-liner:** browse.ts and doc-text.ts `console.error`
   the underlying SnapshotError (message + URL) alongside the rendered
   userMessage, so live failures are diagnosable (data host
   misconfiguration vs app bug).
6. **Font tripwire:** gitignore `explorer-web/public/fonts/` and add a
   CI step asserting `git ls-files '*.woff2' '*.woff' '*.ttf' '*.otf'`
   is empty (the only human path by which font bytes could reach the
   open repo).

The wrapper supplies: `brand/tokens.css` (complete branded inventory
including @font-face and ::highlight), `brand/Head.astro` (favicons,
preconnect + font preloads, build-stamp meta, Plausible), 
`brand/Header.astro` (branded header), fonts, favicons, logo. Markup
and assets, no logic.

Plausible earns its place because the Klim licence ties the tier to
aggregate monthly page views: analytics IS licence compliance. The
main site's /pipes first-party proxy pattern is reused verbatim.
Loaded with `defer`. The README documents the cross-site aggregation
procedure (main site + explorer page views must be summable against
the tier on the house licence; the order number lives in the private
wrapper README and tealinsights-site/LICENSE-FONTS.md).

### D3: Font-loading strategy

**Decision: all five faces, unmodified, same-origin under /fonts/;
font-display: swap plus metric-tuned fallbacks; preconnect + preload
from day one; doc text stays mono.**

- Faces: Soehne Buch 400 / Buch Kursiv 400 italic / Kraeftig 500 /
  Halbfett 600, Tiempos Headline Semibold 600 (display). 193 KB total.
  No subsetting, no format conversion.
- @font-face blocks live in the branded tokens.css (single-file swap
  contract holds; adds <10 KB to the one linked stylesheet).
- **Preload Buch + Tiempos + Halbfett** (stat values and header
  wordmark are 600-weight above the fold) in brand/Head.astro with
  `crossorigin` (required on font preloads even same-origin; same-origin
  requests need no ACAO so this does not conflict with the hotlink
  posture). Acceptance criteria from the perf review: Lighthouse
  CLS <= 0.02 and perf >= 90 on all three recorded page types; DevTools
  shows exactly ONE request per face (guards crossorigin-mismatch
  double-download); throttled trace shows preloaded fonts finishing
  before FCP or within 200 ms after.
- **`<link rel="preconnect" href="https://data.tealinsights.com"
  crossorigin>`** in brand/Head.astro: saves 120-500 ms of
  DNS+TCP+TLS on real networks before the MANIFEST fetch; the wasm
  reuses the warm connection.
- CLS defense: fallback @font-face declarations with metric overrides.
  Soehne -> Arial: size-adjust 99.79%, ascent-override 117.1%,
  descent-override 42.3%, line-gap-override 0%. Tiempos -> Georgia
  (serif fallback, not Helvetica): size-adjust 104.92%,
  ascent-override 91.69%, descent-override 23.83%, line-gap-override
  0%. Line boxes are already metric-independent (unitless 1.55);
  overrides close the wrap-shift residual.
- Reservation tokens re-measured under brand metrics, priority order
  from the perf review: --ew-table-min-height (measure a POPULATED
  20-row page, not the empty reservation), --ew-filters-min-height
  (both breakpoints), --ew-jump-offset (branded header height),
  --ew-chips-min-height.
- `#ew-doc-text` keeps `--ew-font-mono`: insulates the largest render
  surface (29 MB worst case) from swap reflow entirely.
- Fonts get `Cache-Control: public, max-age=31536000, immutable` and NO
  Access-Control-Allow-Origin header (cross-origin @font-face fails
  without CORS: the hotlink half of Klim 3d). If a font file ever
  changes, it gets a new filename (immutable is forever).
- Klim 3d "direct downloads": adopted baseline = no-ACAO + no directory
  listing + the netlify.app 301 (D6) + previews disabled, recorded in
  the README as the "reasonable measures" posture. A
  Sec-Fetch-Dest-gating Edge Function is documented as available
  hardening, deliberately not built in v1.
- `--ew-font-display` never extends below h2 (Tiempos Headline is a
  display face; 1.25rem is its floor here).

### D4: Brand color mapping (all ratios computed at the gate)

- `--ew-color-bg` #FFFFFF; `--ew-color-surface` #FAFAF7;
  `--ew-color-text` #2A2A2A (14.35:1 white / 13.73:1 surface);
  `--ew-color-text-muted` #5C6770 (5.79:1 / 5.53:1);
  `--ew-color-link` AND `--ew-color-accent` pinned ink #143E5A
  (11.25:1 / 10.76:1; checkbox accent fill-vs-white and glyph-vs-fill
  both 11.25:1).
- **Teal #0094BC is NON-TEXT ONLY** (3.52:1 on white: passes the 3:1
  non-text bar, fails 4.5:1 text in every state including hover, which
  axe/Lighthouse cannot catch). Link hover stays in the ink family
  with underline/weight treatment; the header wordmark may use teal
  (logotype exemption). If a teal-family text color is ever wanted:
  #00708F (5.65:1).
- `--ew-color-border` #D4D0CA (decorative only);
  `--ew-color-border-strong` #5C6770 (5.79:1 white, 5.53:1 surface;
  beats S3's 4.62:1).
- Badge/error/notice pairs: keep S3 values (all still on white:
  7.30/7.65/5.41 badges, 7.05 error, 6.03 notice); terracotta #B5380C
  is viable for alert text if wanted (5.94/5.68/5.11/5.51 on
  white/surface/error-bg/notice-bg).
- Highlight pairs unchanged (#ffe08a and #f0a84b) with text #2A2A2A:
  11.13:1 and 7.11:1, lightness step preserved. The ::highlight
  literal var() fallbacks in the branded file update to #2A2A2A.
- The branded tokens.css carries the FULL token inventory (all names
  in upstream tokens.css at the pin); build.sh asserts the branded
  file defines every --ew-* name the upstream file does (fails the
  build on drift). Computed contrast ratios recorded as comments per
  the S3 practice. No `outline: none` anywhere in brand CSS (focus
  rides on UA defaults, as upstream).

### D5: Data + wasm hosting

**Decision: split hosting. Pages + fonts + worker JS on Netlify; the
snapshot (2.46 GB text/, parquet, MANIFEST) AND both wasm binaries on
S3 + CloudFront at data.tealinsights.com, everything pre-compressed at
rest.**

Why S3 + CloudFront wins:

- **Works with DNS exactly where it is.** ACM cert (us-east-1,
  DNS-validated) + CNAME data.tealinsights.com -> distribution. Every
  Cloudflare path requires the zone move first: not in launch week.
- **Compression is deterministic.** CloudFront edge compression stops
  at 10 MB, so the 29 MB JSON and 34.2 MB wasm ship raw IF the edge is
  relied on; instead everything compressible is stored pre-compressed:
  text JSON + MANIFEST + parquet gzip (`gzip -n`, ~490 MB at rest,
  universal decode: this audience sits behind TLS-inspecting proxies
  that mangle br), wasm brotli (5.92 MB; every wasm-capable browser
  decodes br on https). S3 serves stored Content-Encoding
  unconditionally; CloudFront never re-compresses such objects.
  Distribution "Compress objects automatically" OFF.
- **Cache + CORS in verified config:** a CUSTOM cache policy (the
  managed UseOriginCacheControlHeaders-QueryStrings policy puts Host in
  the cache key, documented unsupported for S3 origins): MinTTL 0,
  DefaultTTL 0, MaxTTL 31536000, query strings ALL, headers none,
  cookies none. MinTTL=0 semantics honor per-object Cache-Control:
  MANIFEST no-store stays uncached end to end (client also fetches it
  cache:'no-store'); parquet/text/wasm carry
  public,max-age=31536000,immutable as S3 metadata. Response headers
  policy: managed SimpleCORS (`ACAO: *`, attached on cache hits too).
  MIME per object at upload: application/json, application/wasm,
  application/octet-stream (parquet).
- **Bucket:** private, Block Public Access ON, CloudFront OAC with the
  standard cloudfront.amazonaws.com SourceArn policy.
- **Wasm URLs are versioned:**
  `/prospectus/wasm/duckdb-wasm-1.32.0/duckdb-{eh,mvp}.wasm`, baked
  into PUBLIC_WASM_BASE_URL. Immutable caching at an unversioned path
  would hard-break returning visitors on the first duckdb-wasm bump
  (worker JS and wasm must version together).
- **Cost ~ $0:** CloudFront always-free 1 TB/mo + 10M req on
  pay-as-you-go; S3 $0.06-0.11/mo. New account: PAID account plan,
  skip flat-rate CloudFront plans (their Free tier also blocks custom
  cache policies).
- **S6-ready:** refresh = upload snapshot (MANIFEST last), fire build
  hook, one IAM deploy credential.

Branches considered and held: all-on-Netlify (only if legacy plan +
empirical large-JSON compression probe passes; wasm would ship raw
regardless since pre-compressed serving is impossible; ?v= would need
Netlify-Vary: query; dead on arrival on credit pricing), Cloudflare
zone move + R2 (cleanest long-term, zero egress; post-launch decision
for Teal; same-hostname migration needs no rebuild), workers.dev /
r2.dev (refuted for production), jsDelivr wasm (emergency only).

Data URL shape:
`PUBLIC_DATA_BASE_URL=https://data.tealinsights.com/prospectus/snapshot`
(generic data host, path-scoped per tool).

### D6: Build, deploy, and refresh flow

- `scripts/build.sh` (local + Netlify + CI, no arguments):
  1. rsync `upstream/explorer-web/` -> `.build/` (exclude
     node_modules, dist, .astro), overlay: `brand/tokens.css` ->
     `.build/src/styles/tokens.css`; `brand/Head.astro` +
     `brand/Header.astro` -> `.build/src/brand/`; `brand/fonts/` ->
     `.build/public/fonts/`; favicons + logo -> `.build/public/`.
  2. Assert the branded tokens.css defines every --ew-* name the
     upstream tokens.css does.
  3. Snapshot acquisition: if SNAPSHOT_DIR is preset (wrapper CI uses
     the submodule fixture), skip network. Else fetch
     `MANIFEST.json` (no-store) from
     `${BUILD_DATA_FETCH_BASE:-$PUBLIC_DATA_BASE_URL}`, read
     generated_at, then fetch `documents.parquet?v=<generated_at>`
     (NEVER the bare URL: a bare fetch primes CloudFront's
     unversioned cache entry for a year and later builds silently get
     stale bytes while stamping fresh generated_at, suppressing the
     drift notice). Fetch with `curl --compressed` (objects are
     gzip-at-rest) and assert parquet magic `PAR1` + MANIFEST parses.
     BUILD_DATA_FETCH_BASE exists solely as an emergency build-time
     fetch override (e.g. the raw CloudFront domain during a DNS
     outage); baked client URLs always use PUBLIC_DATA_BASE_URL.
  4. `npm ci`, `astro build` with SNAPSHOT_DIR + PUBLIC_DATA_BASE_URL
     + PUBLIC_WASM_BASE_URL.
  5. Strip `dist/_astro/*.wasm` (74 MB dead weight; the static ?url
     imports emit both binaries regardless of the env override;
     assert-dist checks routes only). Run `node
     scripts/assert-dist.mjs` from the staging copy.
- `scripts/upload-snapshot.sh` (runs where data/snapshot lives):
  builds a pre-compressed staging tree (`gzip -n` for determinism),
  then four metadata-scoped passes: text/*.json (gzip, json,
  immutable), documents.parquet (gzip, octet-stream, immutable), wasm
  (br, application/wasm, immutable, versioned path), and MANIFEST.json
  LAST as a separate `aws s3 cp` (gzip, json, no-store). MANIFEST-last
  ordering is load-bearing: sync uploads alphabetically, and a visitor
  fetching the NEW manifest during the upload window would cache OLD
  parquet/text bytes under the NEW ?v= token immutably. Full re-upload
  on refresh (~490 MB, ~$0.05) is accepted; never use --size-only.
  Runbook notes: scripted consumers must send Accept-Encoding/use
  --compressed (stored encoding is served unconditionally); gzip
  Content-Encoding at rest makes Range requests range over compressed
  bytes (nothing ranges today; recorded for any future TEA-907
  parquet-range design).
- `netlify.toml`: build `bash scripts/build.sh`, publish `.build/dist`,
  NODE_VERSION=22, `_headers` (fonts immutable + no ACAO; everything
  else default), Plausible /pipes redirects, and a FORCED 301
  `https://<site>.netlify.app/*` ->
  `https://prospectus.tealinsights.com/:splat` (Netlify never
  auto-redirects the default subdomain: this is the licence fix; the
  main site needs the identical rule, on the handoff).
- Netlify site settings (handoff): Deploy Previews and branch deploys
  DISABLED (public enumerable netlify.app URLs would serve fonts;
  deploy permalinks are the accepted unguessable residual). QA fixes
  verify locally via serve-static, then deploy to production.
- brand/Head.astro emits a build-stamp meta (wrapper commit, upstream
  pin, Netlify deploy id from build env) so defect reports pin exact
  deploys.
- Wrapper CI (GitHub Actions): build.sh with SNAPSHOT_DIR=fixture +
  PUBLIC_DATA_BASE_URL dummy, assert-dist, two-origin browser smoke
  (fixture smoke works against the branded build: no assertion touches
  branding), and the woff2-never-in-public-repo guard lives upstream
  (D2.6). Branded dist is never uploaded as an artifact.

### D7: Repo layout (prospectus-web-ti, private)

```
upstream/                       # submodule: sovereign-prospectus-corpus @ <seams merge SHA>
brand/
  tokens.css                    # complete branded inventory (@font-face, ::highlight, ratios)
  Head.astro                    # favicons, preconnect, font preloads, build stamp, Plausible
  Header.astro                  # branded header (height -> --ew-jump-offset)
  fonts/*.woff2                 # 5 Klim files (LICENSED: private repo only)
  favicon.ico + favicon.svg + apple-touch-icon.png
  assets/logo.png
scripts/build.sh
scripts/upload-snapshot.sh
netlify.toml
.github/workflows/ci.yml
README.md                       # purpose, no-app-logic rule, pin-bump how-to (tokens diff),
                                # LICENSE-FONTS rules verbatim PLUS: page-view tier +
                                # 3-month-average aggregation procedure (Plausible), fonts
                                # never on data.tealinsights.com (blanket ACAO there),
                                # netlify.app 301 + previews-off rules, deploy-permalink
                                # residual, 3i contractor deletion duty, notify-Klim duty,
                                # local dev loop (.build/ + astro dev), rollback (Netlify
                                # publish-a-previous-deploy; note an older deploy may
                                # legitimately show the drift notice), hosting runbook
```

## Scope boundaries

- No application logic in the wrapper; the single seams PR (D2) is the
  only open-repo change.
- OG images and meta descriptions: S5 (the Head slot makes them a
  wrapper-side follow-up).
- No search work (#82 / TEA-907), no auto-refresh Action (TEA-906),
  no Sec-Fetch-Dest font gate (documented hardening option).
- Main-site netlify.app font leak: fix prepared for tealinsights-site
  (same 301 pattern) but merged by Teal; outside TEA-904's repos.
- DNS records, Netlify dashboard, AWS account: Teal, via the numbered
  handoff list.

## Sequencing (revised at the gate: data host BEFORE first build)

Local-only (no dashboards, all today): seams PR on the open repo;
wrapper repo built locally (brand files, scripts, CI, README); branded
fixture build + smoke + local Lighthouse; upload-snapshot.sh staged
against the local snapshot; this spec + plan + dispositions.

Handoff (numbered list to Teal; DNS-latency items as early as their
prerequisites allow):

1. Create the private GitHub repo (blocked for the session by the
   permission classifier, correctly); grant the Netlify GitHub app
   access to it.
2. AWS: confirm/create account (PAID account plan; note: new-account
   verification holds can take hours, so start this first), create the
   scoped IAM credential (policy JSON provided). Session then scripts:
   bucket (private + OAC), upload (~30-60 min for 490 MB), ACM request.
3. DNS batch 1 (immediately after ACM request): the ACM validation
   CNAME. Session then creates the distribution.
4. DNS batch 2 (after distribution exists): CNAME data.tealinsights.com
   -> <distribution>.cloudfront.net, TTL 300. Gate: `curl -H 'Origin:
   https://prospectus.tealinsights.com' --compressed
   https://data.tealinsights.com/prospectus/snapshot/MANIFEST.json`
   succeeds.
5. Netlify (after the data-host gate passes): record the org PLAN
   (legacy vs credit-metered: decides deploy rationing), create the
   site in the SAME team as tealinsights.com with builds initially
   stopped, connect the repo, set env vars (PUBLIC_DATA_BASE_URL,
   PUBLIC_WASM_BASE_URL), DISABLE deploy previews + branch deploys, add
   the custom domain prospectus.tealinsights.com, then enable builds /
   trigger the first build.
6. DNS batch 3: CNAME prospectus.tealinsights.com ->
   <sitename>.netlify.app, TTL 300 (site + domain exist first, per
   Netlify's documented order; also avoids a dangling-CNAME takeover
   smell). Let's Encrypt provisions automatically once it resolves.
7. Main-site licence fix (separate from TEA-904 but urgent): merge the
   prepared tealinsights-site 301 PR, or add the same redirect rule in
   its netlify.toml.
8. Go/no-go points reserved for Teal: seams PR merge (open repo),
   wrapper PR merge, DNS cutover, and the first production deploy.

Interim-hostname policy: never run a production build against the raw
cloudfront.net domain (PUBLIC_DATA_BASE_URL is baked into 9,775 pages);
wait for data.tealinsights.com. If DNS stalls, QA can use the
<sitename>.netlify.app fallback URL knowing: fonts DO load there
(same-origin within the deploy) but the netlify.app 301 cannot be
active until the custom domain resolves, TLS-for-subdomain and
font-origin checks are deferred to cutover, and font exposure on
netlify.app is time-boxed to that window.

## Verification plan (live site)

1. Lighthouse on prospectus.tealinsights.com: performance >= 90,
   accessibility >= 95, CLS <= 0.02 on browse bare + parameterized +
   one doc page, brand fonts loading (record all three, mirroring S3).
2. Compression + cache semantics, all with
   `-H 'Origin: https://prospectus.tealinsights.com'` (SimpleCORS only
   decorates CORS requests): largest text URL
   (text/luxse-100387641.json?v=<current>) shows Content-Encoding gzip
   and ~2.7 MB transfer; the eh wasm URL shows Content-Encoding br and
   ~5.92 MB; repeat the text check WITHOUT ?v= confirming the custom
   cache policy keys them separately; MANIFEST response shows no-store
   and fresh generated_at.
3. Fonts: every font request in DevTools originates from
   prospectus.tealinsights.com; exactly ONE request per face (preload
   crossorigin correctness); a cross-origin @font-face fetch fails (no
   ACAO); `curl -sI https://<site>.netlify.app/fonts/<f>.woff2`
   returns the 301; deploy previews confirmed off.
4. MANIFEST reachable from the live origin; drift notice absent right
   after deploy (and the runbook documents when it legitimately
   appears); ?v= tokens on parquet/text requests; snapshot date
   current.
5. TLS valid for prospectus.tealinsights.com AND data.tealinsights.com.
6. Live-safe checks (the fixture smoke suite is fixture-bound:
   synthetic slugs, fixture counts, fixture page bounds; it runs in
   wrapper CI, NOT against production): manual/scripted live pass over
   browse (filters, chips, pagination, scope toggle, zero-result
   country, unknown param passthrough), history back/forward, two real
   doc pages resolved from the live parquet, in-document search on one,
   axe on browse + doc.
7. Phone spot-check pinned to /doc/luxse-100387641/: click-gate shows
   before any text fetch, post-click render works on cellular,
   ?q=pari+passu deep-link still respects the gate.
8. Trailing-slash + 404: /doc/<slug> without slash 301s to the slash
   form with query string intact; a bad slug serves the branded
   404.astro with HTTP 404 status.
9. Contrast ratios recorded as comments in the branded tokens.css; axe
   (target-size enabled) zero serious/critical on browse + doc.
10. Rollback rehearsed once: Netlify "publish a previous deploy"
    (noting the drift-notice caveat for older deploys).

## Council dispositions (spec gate, 6 fresh reviewers, 2026-07-04)

All six reviewed the committed draft; every CRITICAL and IMPORTANT was
either fixed in this revision or explicitly recorded:

- **Generalist:** C1 tokenized build fetch -> FIXED (D6.3); C2 pin
  contradiction -> FIXED (D1: pin = seams merge SHA, seams PR first);
  C3 live smoke unrunnable -> FIXED (verification 6 rewritten; fixture
  smoke stays in CI); I1 bootstrap ordering -> FIXED (Sequencing);
  I2 font-weight seam not neutral -> FIXED (weight token, D2.1);
  I3 unversioned wasm URL -> FIXED (D5 versioned path); I4 dist wasm
  dead weight + bundleName -> FIXED (D6.5, D2.3); I5 build.sh modes +
  overlay mapping -> FIXED (D6.1/6.3). Minors: 404 page (D2.4), local
  dev docs + tokens diff (D7 README), Range-vs-gzip note (D6), metric
  fallbacks kept but timeboxed. Accepted-as-is: none rejected.
- **Deploy/infra:** C1 managed cache policy unsupported on S3 origins
  -> FIXED (custom five-field policy, D5); I1 MANIFEST-last upload ->
  FIXED (D6); I2 first-build gate -> FIXED (Sequencing 4-5); I3
  --compressed + PAR1 -> FIXED (D6.3); I4 site-before-CNAME -> FIXED
  (Sequencing 5-6); I5 wasm versioning -> FIXED; I6 four-pass upload +
  staging tree -> FIXED (D6). Minors adopted: Origin-header curls, TTL
  300, OAC + BPA, scripted-consumer caveat, font-rename rule,
  refresh-rebuild credit note (recorded here: every refresh rewrites
  all HTML; refresh cadence = deploy cadence on a credit plan).
- **Font licence:** C1 netlify.app leak (incl. LIVE main-site leak
  found during review) -> FIXED for the wrapper (forced 301 in
  netlify.toml from first deploy) + main-site fix on the handoff; C2
  deploy previews -> FIXED (disabled; permalink residual documented);
  I1 woff2 tripwire -> FIXED (D2.6); I2 direct-download posture ->
  DECIDED (baseline recorded in README; Edge Function documented, not
  built); I3 README additions -> FIXED (D7). Minors adopted (neutral
  upstream examples, netlify.app 301 verification line, no dist
  artifacts, org visibility-change restriction suggested to Teal).
- **Performance:** no criticals. Preconnect -> ADOPTED (D3); day-one
  preload -> ADOPTED (D3, with the reviewer's acceptance criteria);
  swap+metrics over optional -> CONFIRMED (Tiempos fallback moved to
  Georgia); reservation re-measure priorities -> ADOPTED; gzip (not
  br) for text -> CONFIRMED; Plausible defer + dist-wasm note ->
  ADOPTED.
- **Accessibility:** C1 teal hover fails 1.4.3 -> FIXED (D4: teal is
  non-text only; hover stays ink); corrected ratios recorded (3.52,
  5.79, full table in the review); accent pinned to ink -> ADOPTED;
  full-inventory token assert -> ADOPTED (D4/D6.2); highlight literal
  fallbacks -> ADOPTED; display font never below h2 -> ADOPTED.
- **S5 QA analyst:** C1 fixture smoke -> FIXED (as generalist C3); C2
  no 404 -> FIXED (D2.4); C3 no rollback -> FIXED (verification 10 +
  README); C4 build DNS dependency -> FIXED (BUILD_DATA_FETCH_BASE +
  sequencing gate); I1 preview posture -> FIXED (disabled + local
  verify loop); I2 diagnosability -> FIXED (D2.5 console.error); I3
  fallback-URL semantics -> FIXED (Sequencing, interim policy); I4
  trailing slash -> FIXED (verification 8); I5 pinned phone check ->
  FIXED (verification 7); I6 drift-notice briefing -> FIXED
  (README/runbook note). Minors adopted: build-stamp meta,
  Content-Encoding assertions in curls, live zero-result check.

Sound findings (all six): split hosting + pre-compression + custom
policy semantics, submodule + staging build, brand-slot seams as
genuinely neutral, no-ACAO hotlink mechanics, mono doc text as the
best CLS decision, URL-state discipline, scope discipline.

- Spec gate: PASSED with revisions (this document).
- Plan gate: PENDING
- PR gate: PENDING
