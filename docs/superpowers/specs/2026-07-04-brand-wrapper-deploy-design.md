# S4 (TEA-904): Private brand wrapper + Netlify deploy design

Date: 2026-07-04. Issue: TEA-904. Upstream pin: `f80ed97` (PR #90, S3 parity
build, on main). Companion docs: `explorer-web/ARCHITECTURE.md` (theme
contract + hosting constraints), the Klim Web Font Licence (verified against
klim.co.nz 2026-07-04), `tealinsights-site/LICENSE-FONTS.md`.

## Goal

The branded explorer live at prospectus.tealinsights.com: a new PRIVATE repo
`Teal-Insights/prospectus-web-ti` that pulls explorer-web at the pinned ref,
overrides the neutral theme with Teal Insights brand (Tiempos Headline
display, Soehne UI/body), and deploys to a new Netlify site. No application
logic in the private repo. Fonts live only in the private repo and are served
only from the subdomain. Data hosting resolved. Teal does DNS records and
dashboard logins from a numbered handoff list.

## Verified facts the design rests on

- **DNS:** tealinsights.com nameservers are Google Cloud DNS
  (ns-cloud-e*.googledomains.com). Apex A 75.2.60.5 (Netlify LB), www CNAME
  tealinsights.netlify.app. No prospectus record yet. Consequence: **R2
  custom domains are unavailable without moving the zone to Cloudflare**
  (R2 custom domains require the domain to be a zone in the same Cloudflare
  account).
- **Klim licence (primary source, 2026-07-04):** modification prohibited
  except a narrow subsetting carve-out (3g, file-size reduction only; not
  needed at 37-40 KB/file); WOFF2 only (3a); third-party hosting allowed
  only if the provider adheres to the licence (3e); affirmative hotlink and
  direct-download protection obligation (3d, "reasonable measures");
  subdomains of the licensed second-level domain are covered (1f), subject
  to the aggregate page-view tier across all sites (3a/3b); public repos =
  redistribution (1d, 3f, 3j). Consequence: fonts stay in the private repo,
  serve same-origin from prospectus.tealinsights.com, and font paths must
  NOT carry Access-Control-Allow-Origin (browsers require CORS for
  cross-origin @font-face, so a missing ACAO header IS the hotlink
  protection).
- **Theme contract:** `src/styles/tokens.css` is the complete style-value
  inventory (S3 added 12 tokens; the ::highlight() rules live in tokens.css
  with literal var() fallbacks). base.css consumes tokens only. h1/h2 have
  no font-family of their own (inherit body) and no display-font token
  exists yet. `.ew-header` is a text link; explorer-web/public/ is empty
  (no favicon anywhere; browsers fall back to requesting /favicon.ico).
  Base.astro has no head seam (no favicon link, no analytics, no OG tags;
  OG images are S5 scope per the sprint calendar).
- **Wasm:** dist carries both bundles, 34.2 MB (eh) + 39.4 MB (mvp) raw;
  5.92 MB brotli for the one a modern browser actually downloads. Worker JS
  is small (773 KB eh). duck.ts imports both via Vite `?url` (same-origin);
  the Worker() constructor is same-origin restricted, the wasm binary is
  not.
- **Build inputs:** the Astro build reads only documents.parquet (1.75 MB)
  + MANIFEST.json via SNAPSHOT_DIR; the 2.46 GB text/ corpus is
  client-fetched from PUBLIC_DATA_BASE_URL (build gate requires https).
  Tokens/base CSS ships as a LINKED stylesheet in dist (fonts declared
  there are discovered after the CSS fetch; preload is the lever if
  Lighthouse objects).
- **Fonts on hand:** 5 WOFF2 files, 37-40 KB each (~193 KB total), plus
  @font-face reference blocks and brand tokens in tealinsights-site
  (surface #FAFAF7, dark #2A2A2A, ink #143E5A, teal #0094BC, divider
  #D4D0CA, slate #5C6770, terracotta #B5380C; Soehne stack + Tiempos
  Headline display; main-site header = logo PNG at 38px + nav; Plausible
  via first-party /pipes proxy in netlify.toml).
- **CI:** ci.yml explorer-web job = npm ci, astro check, vitest, fixture
  build, assert-dist.mjs, two-origin browser smoke (serve-static.mjs +
  smoke.mjs). Node 24 in CI; package.json engines >= 22.12.
- **Netlify (primary docs, 2026-07-04):** accounts created before
  2025-09-04 keep legacy plans (Free 100 GB/mo bandwidth hard cap; Pro
  1 TB/mo); newer accounts are credit-metered (Free 300 credits/mo,
  bandwidth 20 credits/GB since 2026-04-14, and EVERY production deploy
  costs 15 credits). The CDN cache key does NOT include query strings for
  static assets by default (the ?v= scheme is CDN-defeated unless the
  response sends `Netlify-Vary: query` or the data ships inside the same
  atomic deploy, which invalidates the CDN on every deploy). Custom
  `_headers` rules may set Cache-Control freely but Content-Encoding is a
  forbidden header: pre-compressed serving is impossible; edge brotli is
  documented for text assets only (application/wasm and large JSON
  behavior UNDOCUMENTED; requires an empirical probe once a site
  exists). 54,000 files per directory cap (text/ has 9,671: fine); no
  documented single-file or total-size cap (staff guidance ~10 MB/file is
  soft). Public https submodules clone with zero config (recursive
  submodules do not). Deploys are content-addressed (unchanged files
  never re-upload) and atomic. External-DNS subdomain = CNAME to
  <sitename>.netlify.app with automatic Let's Encrypt; NODE_VERSION env
  or .nvmrc pins Node (default 22 on the current image).
- **Cloudflare (primary docs, 2026-07-04):** R2 custom domains require
  the domain to be a zone in the SAME account; keeping DNS at Google
  Cloud DNS would need a partial (CNAME) setup, which is
  Business/Enterprise only. r2.dev is rate-limited, "development
  purposes" only, no cache/custom headers. Workers on workers.dev are
  documented as hobby-tier ("not business-critical"), and the Cache API
  is an explicit NO-OP on workers.dev (edge caching requires a custom
  domain, which again requires the zone). Workers Free = 100k req/day.
  R2 free tier = 10 GB storage, 1M class A + 10M class B ops/mo, zero
  egress, but enabling R2 requires a payment method on file. Zone
  onboarding auto-imports records with explicit "verify MX/TXT yourself"
  warnings and up-to-24 h nameserver propagation. Net: every
  Cloudflare-hosted-data path runs through moving the tealinsights.com
  zone to Cloudflare first.

## Design decisions

### D1: How the wrapper pins and pulls explorer-web

**Decision: git submodule of the open repo, pinned at f80ed97; build runs
against a staging copy.**

- The open repo is small (8.7 MB .git), so a submodule clone is cheap.
- npm-tarball install is not viable: explorer-web is a subdirectory of the
  monorepo and is not published; npm cannot install a git subdirectory.
- A build-time tarball fetch (codeload at a SHA) works but hides the pin in
  a script variable and re-downloads every build. The submodule makes the
  pin a first-class, reviewable gitlink: bumping it is a one-line diff in a
  PR, and local dev gets the exact upstream tree.
- The build never mutates the submodule worktree: `scripts/build.sh` rsyncs
  `upstream/explorer-web/` to a gitignored `.build/` staging dir, overlays
  `brand/` files, and builds there. The submodule stays pristine (clean
  `git status`, no accidental commits of brand files into the open tree).

### D2: Where the brand override lives (the no-application-logic line)

**Decision: one small upstream PR to explorer-web adds a neutral
brand-slot contract; the wrapper supplies only assets and markup.**

The tokens.css swap covers every style VALUE, but three brand needs have no
seam today: a logo/wordmark in the header, head-level additions (favicon
links, font preloads if needed, analytics), and a display-font for
headings. Overlaying Base.astro from the wrapper would fork a load-bearing
layout file (drift trap: every upstream Base.astro change silently
diverges). Instead, upstream (open repo, neutral defaults, no behavior
change when brand files are absent):

1. **`--ew-font-display` token** defaulting to the body stack, consumed by
   `h1, h2 { font-family: var(--ew-font-display); font-weight: 600; }` in
   base.css. (600 because Tiempos Headline ships only semibold; with
   Soehne 400/500/600 loaded, a 700 request would resolve to the 600 face
   anyway per CSS font matching, so the neutral look shift is nil-to-
   imperceptible.)
2. **Brand slots in Base.astro** via `import.meta.glob` with eager import:
   if `src/brand/Head.astro` exists it renders at the end of `<head>`; if
   `src/brand/Header.astro` exists it replaces the neutral header markup
   (else the current text-link header renders). `src/brand/` ships empty
   (a README documenting the contract) and gitignored for content.
3. **Optional `PUBLIC_WASM_BASE_URL` env** (astro:env, optional string):
   when set, duck.ts uses `<base>/duckdb-eh.wasm` and
   `<base>/duckdb-mvp.wasm` as mainModule URLs instead of the bundled
   `?url` assets; worker JS always stays same-origin (Worker() constructor
   restriction). When unset, behavior is byte-identical to today. This is
   what lets the 34-39 MB binaries live on the data host instead of
   burning Netlify bandwidth credits.

The wrapper then supplies: `brand/tokens.css` (the complete branded
inventory, including @font-face blocks and the ::highlight rules),
`brand/Head.astro` (favicon links, Plausible via first-party proxy, font
preloads only if measurements demand), `brand/Header.astro` (wordmark),
fonts, favicons, logo. Markup and assets, no logic; every future feature
still lands upstream.

Plausible earns its place in the wrapper because the Klim licence ties the
licence tier to aggregate monthly page views: the analytics IS part of
licence compliance, and the main site's /pipes proxy pattern is reused
verbatim in the wrapper's netlify.toml.

### D3: Font-loading strategy

**Decision: all five faces, unmodified, same-origin under /fonts/;
font-display: swap plus metric-tuned local fallbacks; no preload in v1;
doc text stays mono.**

- Faces: Soehne Buch 400 / Buch Kursiv 400 italic / Kraeftig 500 /
  Halbfett 600, Tiempos Headline Semibold 600 (display). 193 KB total.
- No subsetting (permitted by 3g but unnecessary at these sizes, and Klim
  does not support subsetted fonts). No format conversion (3a).
- @font-face blocks live in the branded tokens.css, so the single-file
  swap contract holds. URLs are root-relative /fonts/*.woff2 (Vite leaves
  absolute public paths untouched).
- CLS defense: paired `@font-face` fallback declarations with
  size-adjust/ascent-override/descent-override/line-gap-override tuned so
  the fallback (Helvetica/Arial) occupies the same space as Soehne, and
  `--ew-jump-offset` re-measured against the branded header height. The
  S3 reservation tokens (--ew-table-min-height, --ew-filters-min-height,
  --ew-chips-min-height) are re-checked under brand metrics and adjusted
  in the branded tokens.css if needed.
- `#ew-doc-text` keeps `--ew-font-mono` (system mono): the raw-text
  facsimile is a deliberate S3 decision, webfonting 29 MB of prospectus
  text buys nothing, and it insulates the largest render surface from
  font-swap reflow entirely.
- Fonts get `Cache-Control: public, max-age=31536000, immutable` and NO
  Access-Control-Allow-Origin header (hotlink protection per Klim 3d).
- Preload is deliberately deferred: the tokens CSS is the first linked
  stylesheet, faces are 38 KB each, and Lighthouse runs on the live site
  decide. If FCP/CLS numbers demand it, `brand/Head.astro` gains
  `<link rel="preload" as="font" crossorigin>` for Buch + Tiempos only.

### D4: Brand color mapping (contrast bars re-passed)

Branded token values, checked against the recorded bars before build (the
numbers get re-verified in the plan's contrast step):

- `--ew-color-bg` #FFFFFF (keep white for data surfaces; #FAFAF7 for
  --ew-color-surface), text #2A2A2A, muted slate #5C6770 (4.5:1+ on
  white), accent/link ink #143E5A with teal #0094BC reserved for hover
  and the header wordmark accents (raw #0094BC on white is ~3.0:1, below
  the 4.5:1 text bar, so it is never body-link-on-white).
- `--ew-color-border` #D4D0CA (decorative), `--ew-color-border-strong`
  must hold >= 3:1 on white: slate #5C6770 (~5.6:1) passes.
- Badge/error/notice pairs keep S3's hue semantics recolored toward the
  brand only where the 4.5:1 pair bar still passes; otherwise S3 values
  stay (they are already neutral).
- Highlight pairs: keep S3's amber pair unless the accessibility reviewer
  proposes brand-adjacent values that hold >= 4.5:1 against #2A2A2A text
  and preserve the lightness step between current-match and match.
- Every final value gets a computed contrast ratio comment in the branded
  tokens.css, mirroring the S3 practice.

### D5: Data + wasm hosting

**Decision: split hosting. Pages + fonts + worker JS on Netlify; the
snapshot (2.46 GB text/, parquet, MANIFEST) AND both wasm binaries on
S3 + CloudFront at data.tealinsights.com, everything compressible
pre-compressed at rest.** (AWS facts verified against primary docs
2026-07-04; see agent findings inline below.)

Why S3 + CloudFront wins against the alternatives:

- **It works with DNS exactly where it is.** ACM cert (us-east-1,
  DNS-validated via CNAMEs at any provider) + one CNAME
  data.tealinsights.com -> distribution domain. Both are early-day DNS
  items. Every Cloudflare path (R2 custom domain, Worker custom domain,
  functional Cache API) requires moving the tealinsights.com zone to
  Cloudflare nameservers first: an email-endangering, up-to-24 h
  migration that does not belong in launch week.
- **Compression is deterministic, not provider-mood.** CloudFront only
  edge-compresses 1 KB-10 MB objects, so the 29 MB worst-case JSON and
  34.2 MB wasm would ship raw IF we relied on the edge. We do not: all
  text JSON + MANIFEST + parquet are stored gzip-encoded
  (Content-Encoding: gzip metadata, ~490 MB at rest, universal client
  support), the wasm stored brotli (Content-Encoding: br, 5.92 MB; every
  wasm-capable browser speaks br on https). S3 passes stored
  Content-Encoding through; CloudFront never re-compresses such objects.
- **The binding checklist is satisfiable in managed config:** cache
  behavior with the managed `UseOriginCacheControlHeaders-QueryStrings`
  cache policy (query strings IN the cache key, per-object Cache-Control
  honored: MANIFEST no-store, everything else
  public,max-age=31536000,immutable, all set as S3 object metadata at
  upload) + managed `SimpleCORS` response headers policy (blanket
  `Access-Control-Allow-Origin: *`, no S3 CORS config needed). MIME set
  per object at upload (application/wasm, application/json,
  application/octet-stream for parquet).
- **Cost ~ $0.** CloudFront's 1 TB/mo + 10M req/mo always-free tier
  survives the 2025 pricing changes on pay-as-you-go; S3 storage + PUTs
  land at $0.06-0.11/month. New-account note for the handoff: choose the
  PAID account plan (pay-as-you-go; the "Free account plan" auto-closes
  after 6 months) and skip the CloudFront flat-rate plans.
- **Wasm off Netlify** protects the shared team bandwidth/credits (34 MB
  raw per cold visitor otherwise, and Netlify cannot serve
  pre-compressed files, and its wasm edge-compression is undocumented)
  and fixes the throttled cold-load profile (5.92 MB br vs 34.2 MB raw).
  Requires the D2.3 upstream seam (PUBLIC_WASM_BASE_URL). Worker JS
  (773 KB, text/javascript: documented Netlify brotli territory) stays
  same-origin per the Worker() constructor restriction.
- **S6-ready:** the refresh Action needs one IAM deploy credential
  (aws s3 sync --content-encoding ... or rclone) + a Netlify build hook.

Branches considered and held:

- **All-on-Netlify** (data + wasm inside the site deploy): viable ONLY if
  the org account is on a LEGACY plan (pre-2025-09-04: 100 GB Free /
  1 TB Pro classic bandwidth, no per-deploy credit burn) AND an
  empirical compression probe passes for large application/json (the
  wasm would ship raw regardless: pre-compressed serving is
  impossible). CDN staleness is safe in this branch only because data
  ships in the same atomic deploy; the ?v= scheme still needs
  `Netlify-Vary: query` via _headers for belt and braces. Held as
  fallback if AWS onboarding stalls: functional, worse cold-load, no
  new vendor. If the account is on credit pricing, this branch is dead
  on arrival (bandwidth 20 credits/GB + 15 credits per deploy against
  300/mo shared with the main site).
- **Cloudflare zone move + R2 custom domain:** the cleanest long-term
  home (zero egress forever, edge cache with query strings in the key,
  json edge compression) and the original recorded default, but gated
  on migrating tealinsights.com nameservers (MX/TXT re-verification,
  24 h propagation, main-site blast radius). Post-launch migration path:
  move the zone, add data.tealinsights.com as an R2 custom domain, sync
  the snapshot to R2, and no rebuild is needed because the hostname
  stays the same. Recorded for S6+, decided by Teal, never in launch
  week.
- **workers.dev / r2.dev serving:** refuted for production (hobby-tier
  framing, Cache API no-op on workers.dev, r2.dev rate-limited
  dev-only).
- **jsDelivr for the wasm** (duckdb-wasm's own npm artifacts, CORS +
  immutable): held as an emergency fallback only; adds a third-party
  runtime dependency to the flagship and the exact-version pin becomes
  someone else's uptime.

Data URL shape: `PUBLIC_DATA_BASE_URL=https://data.tealinsights.com/prospectus/snapshot`
(generic data host, path-scoped per tool, so future SovTech tools share
the bucket + cert + distribution). PUBLIC_WASM_BASE_URL points at
`.../prospectus/wasm` carrying the two pinned binaries.

### D6: Build and refresh flow

- `scripts/build.sh` (runs locally and on Netlify): rsync submodule
  explorer-web -> .build/, overlay brand/, `npm ci`, then fetch
  MANIFEST.json + documents.parquet from the LIVE data host
  (`DATA_BASE_URL`) into `.build/snapshot/`, and `astro build` with
  SNAPSHOT_DIR=.build/snapshot and PUBLIC_DATA_BASE_URL. Building from
  the data host's own manifest means pages are stamped with the host's
  generated_at: no drift notice on deploy, and the S6 refresh flow is
  already "upload snapshot, fire build hook".
- `scripts/upload-snapshot.sh`: syncs data/snapshot/ from the corpus
  machine to the data host (tool depends on D5 host; S3-compatible either
  way), sets per-object-class Cache-Control and Content-Type at upload.
- netlify.toml: build command `bash scripts/build.sh`, publish
  `.build/dist`, NODE_VERSION pin, headers block (font caching sans ACAO,
  HTML no-cache defaults as upstream assumes), Plausible /pipes redirects.
- Wrapper CI (GitHub Actions): the branded analogue of the upstream
  explorer-web job: build.sh against the submodule's fixture snapshot
  (SNAPSHOT_DIR override), assert-dist, two-origin smoke with the branded
  dist. No secrets; PUBLIC_DATA_BASE_URL uses the CI dummy.

### D7: Repo layout (prospectus-web-ti, private)

```
upstream/                       # submodule: Teal-Insights/sovereign-prospectus-corpus @ f80ed97
brand/
  tokens.css                    # complete branded inventory (@font-face, ::highlight, contrast comments)
  Head.astro                    # favicons, Plausible (proxied), [preloads if needed]
  Header.astro                  # branded header (logo wordmark, height -> --ew-jump-offset)
  fonts/*.woff2                 # 5 Klim files (LICENSED: private repo only)
  favicon.ico + favicon.svg + apple-touch-icon.png
  assets/logo.(png|svg)
scripts/build.sh                # staging build (D6)
scripts/upload-snapshot.sh      # snapshot -> data host (D6)
netlify.toml                    # build, publish, headers, redirects
.github/workflows/ci.yml        # branded fixture build + smoke
README.md                       # purpose, no-app-logic rule, pin-bump how-to,
                                # LICENSE-FONTS rules copied verbatim, hosting runbook
```

## Scope boundaries

- No application logic in the wrapper; the three upstream seams (D2) are
  the only open-repo changes, all neutral-default no-ops.
- OG images and meta descriptions: S5 (sprint calendar assigns them
  there); the Head slot makes them a wrapper-side follow-up.
- No search work (#82 / TEA-907), no auto-refresh Action (TEA-906).
- DNS records, Netlify dashboard, data-host account: Teal, via the
  numbered handoff list; DNS items go out first (propagation).

## Sequencing and the Teal handoff (day structure)

Work that needs no dashboard: build the wrapper repo locally, the three
upstream seams (one small PR to the open repo), the branded tokens with
contrast math, local branded build + smoke + Lighthouse, the
upload-snapshot script with pre-compression, and the gh-created private
repo (gh auth has repo scope; if org policy blocks creation it becomes
handoff item 0).

The numbered handoff list (delivered as the first user-facing output of
the day, DNS-bearing items first):

1. DNS now: CNAME `prospectus.tealinsights.com` ->
   `<site-name>.netlify.app` (site name proposed in the list; adjust if
   taken).
2. Netlify: record the org plan (legacy pre-2025-09-04 or
   credit-metered: decides the all-on-Netlify fallback viability and how
   carefully we ration deploys); grant the Netlify GitHub app access to
   the private repo; create the site (or `! netlify login` and the
   session drives it); set env vars; add the custom domain.
3. AWS: confirm/create the account (Paid account plan), create the
   scoped IAM credential (policy JSON provided); the session then
   scripts bucket, upload, ACM request, distribution.
4. DNS after ACM request: one validation CNAME; DNS after distribution:
   CNAME `data.tealinsights.com` -> `<distribution>.cloudfront.net`.
5. Go/no-go points reserved for Teal: PR merges (both repos) and the DNS
   cutover.

## Verification plan (live site, per the kickoff)

1. Lighthouse on prospectus.tealinsights.com: performance >= 90,
   accessibility >= 95 on browse with brand fonts loaded (record bare +
   parameterized + doc page, mirroring S3).
2. Compression: `curl -H 'Accept-Encoding: br,gzip' -so /dev/null
   -w '%{size_download}'` on the largest text URL
   (luxse-100387641.json, 29 MB raw -> ~2.7 MB) and the eh wasm
   (34.2 MB -> 5.92 MB br).
3. Fonts: every font request originates from prospectus.tealinsights.com
   (DevTools network check); a cross-origin @font-face fetch of a font
   URL fails (no ACAO).
4. MANIFEST reachable from the live origin; drift notice absent; snapshot
   date current; ?v= tokens present on parquet/text requests.
5. TLS valid (certificate for prospectus.tealinsights.com).
6. Smoke suite + measurement harness from explorer-web/scripts/ against
   the live URL (SMOKE_BASE=https://prospectus.tealinsights.com).
7. One doc page spot-checked on a phone.
8. Contrast: computed ratios for every changed token pair recorded in
   tokens.css comments; axe pass on browse + doc page of the branded
   build.

## Council dispositions

(Recorded after each gate runs.)

- Spec gate: PENDING
- Plan gate: PENDING
- PR gate: PENDING
