# S4 Brand Wrapper + Netlify Deploy Implementation Plan (TEA-904)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The branded explorer live at prospectus.tealinsights.com: an upstream "S4 seams" PR on the open repo, a new private wrapper repo (prospectus-web-ti) carrying brand + fonts + deploy config, and the S3+CloudFront data host.

**Architecture:** Per the gated spec `docs/superpowers/specs/2026-07-04-brand-wrapper-deploy-design.md`. Split hosting (Netlify pages, S3+CloudFront data + wasm, pre-compressed at rest). Wrapper = submodule pin + rsync staging build + brand overlay; one neutral seams PR upstream.

**Tech Stack:** Astro 6.4.8, @duckdb/duckdb-wasm 1.32.0, Netlify, AWS S3 + CloudFront + ACM, bash, GitHub Actions.

## Global Constraints

- No em-dashes in any file, commit message, PR body, or comment.
- Node >= 22.12 (upstream engines); Netlify NODE_VERSION=22.
- Upstream changes are neutral no-ops when brand files are absent; neutral rendering byte-identical.
- No application logic in the wrapper; no brand assets (names included) in open-repo examples.
- Font files (*.woff2) exist ONLY in prospectus-web-ti; never in any public repo, artifact, or non-subdomain origin. No ACAO on font paths.
- Open-repo work happens in `~/Code/sovereign-prospectus-corpus` on branch `lte/tea-904-s4-private-brand-wrapper-netlify-deploy`; wrapper in `~/Code/prospectus-web-ti`.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- The wrapper submodule pin ends at the seams PR MERGE SHA (bumped in Phase C after Teal's merge go-ahead).

---

## Phase A: upstream seams PR (open repo)

### Task 1: Display-font tokens

**Files:**
- Modify: `explorer-web/src/styles/tokens.css` (Type block, after `--ew-line-height`)
- Modify: `explorer-web/src/styles/base.css` (after the existing h2 rule, line ~25)

**Interfaces:**
- Produces: `--ew-font-display` (font stack, default = body stack), `--ew-font-weight-display` (default 700). Consumed by base.css h1/h2. The branded tokens.css overrides both.

- [ ] **Step 1: Add tokens.** In tokens.css after `--ew-line-height: 1.55;`:

```css
  /* S4 (TEA-904): display face for h1/h2. Neutral default = the body
     stack at UA bold weight, byte-identical to the pre-token rendering;
     the private wrapper overrides both. */
  --ew-font-display: var(--ew-font-body);
  --ew-font-weight-display: 700;
```

- [ ] **Step 2: Consume in base.css.** After the `h2 { ... }` block:

```css
h1,
h2 {
  font-family: var(--ew-font-display);
  font-weight: var(--ew-font-weight-display);
}
```

- [ ] **Step 3: Verify neutral no-op.** Run from `explorer-web/`:

```bash
SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=https://data.example.invalid npx astro build && node scripts/assert-dist.mjs
```
Expected: build succeeds, assert passes. Visual check: `git stash && npx astro build ... && cp dist/index.html /tmp/before.html && git stash pop` is unnecessary; the CSS change is provably inert (font-family resolves to the same stack; weight 700 = UA default for h1/h2).

- [ ] **Step 4: Commit** `feat(explorer-web): display-font tokens for the S4 theme contract`

### Task 2: Brand slots in Base.astro

**Files:**
- Modify: `explorer-web/src/layouts/Base.astro`
- Create: `explorer-web/src/brand/README.md`
- Modify: `explorer-web/.gitignore`

**Interfaces:**
- Produces: optional `src/brand/Head.astro` (rendered at end of head) and `src/brand/Header.astro` (replaces the neutral header). The wrapper build copies its brand components to `src/brand/` in the staging tree.

- [ ] **Step 1: Rewrite Base.astro:**

```astro
---
import '../styles/tokens.css';
import '../styles/base.css';

interface Props {
  title: string;
  snapshotDate: string;
  generatedAt: string;
}
const { title, snapshotDate, generatedAt } = Astro.props;

// Brand slots (S4 theme contract): a private wrapper may drop
// Head.astro / Header.astro into src/brand/ at build time. Absent files
// mean the neutral defaults below; nothing here reads brand content.
type AstroComponent = (props: Record<string, never>) => unknown;
const brand = import.meta.glob<{ default: AstroComponent }>('../brand/*.astro', {
  eager: true,
});
const BrandHead = brand['../brand/Head.astro']?.default;
const BrandHeader = brand['../brand/Header.astro']?.default;
---

<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    {BrandHead && <BrandHead />}
  </head>
  <body data-build-generated-at={generatedAt} data-build-snapshot-date={snapshotDate}>
    {
      BrandHeader ? (
        <BrandHeader />
      ) : (
        <header class="ew-header">
          <a href="/">Sovereign Prospectus Explorer</a>
        </header>
      )
    }
    <main>
      <slot />
    </main>
    <footer class="ew-footer">
      Snapshot {snapshotDate}. Data and code: sovereign-prospectus-corpus.
    </footer>
  </body>
</html>
```

- [ ] **Step 2: Create src/brand/README.md** (neutral examples only; no font-vendor names):

```markdown
# Brand slots

A private re-theming wrapper may place two optional Astro components
here at build time (this directory ships empty; *.astro is gitignored):

- `Head.astro`: rendered at the end of `<head>` on every page. Use for
  favicon links, font preloads, analytics, build stamps.
- `Header.astro`: replaces the neutral `<header class="ew-header">`. Keep
  the `ew-header` class (or an equivalent) and re-measure
  `--ew-jump-offset` against the new header height.

Rules: markup and assets only, no application logic; style values come
from tokens (`--ew-*`); nothing licensed or brand-specific may be
committed to THIS repository.
```

- [ ] **Step 3: gitignore.** Append to `explorer-web/.gitignore`:

```
src/brand/*.astro
public/fonts/
```

- [ ] **Step 4: Verify both paths.** Neutral: fixture build (command as Task 1 step 3), then `grep -c 'ew-header' dist/index.html` expected >= 1. Branded: `printf -- '---\n---\n<meta name="x-brand-test" content="1" />\n' > src/brand/Head.astro`, rebuild, `grep -c 'x-brand-test' dist/index.html` expected 1, then `rm src/brand/Head.astro`.

- [ ] **Step 5: `npx astro check`** Expected: no new errors. **Commit** `feat(explorer-web): optional brand slots in Base.astro`

### Task 3: Optional PUBLIC_WASM_BASE_URL

**Files:**
- Modify: `explorer-web/astro.config.mjs`
- Modify: `explorer-web/src/lib/config.ts`
- Modify: `explorer-web/src/lib/duck.ts`

**Interfaces:**
- Produces: optional client env `PUBLIC_WASM_BASE_URL`; when set, DuckDB mainModule URLs are `<base>/duckdb-eh.wasm` / `<base>/duckdb-mvp.wasm`. Worker JS always same-origin. Consumed by the wrapper (set to the versioned data-host path).

- [ ] **Step 1: astro.config.mjs.** In the env schema add:

```js
      PUBLIC_WASM_BASE_URL: envField.string({ context: 'client', access: 'public', optional: true }),
```

And in the build gate section, after the data URL checks:

```js
  const wasmUrl = env.PUBLIC_WASM_BASE_URL;
  if (wasmUrl) {
    let w;
    try {
      w = new URL(wasmUrl);
    } catch {
      throw new Error(`PUBLIC_WASM_BASE_URL must be an absolute URL when set; got ${wasmUrl}`);
    }
    const wLocal = w.hostname === 'localhost' || w.hostname === '127.0.0.1';
    if (w.protocol !== 'https:' && !wLocal) {
      throw new Error(`PUBLIC_WASM_BASE_URL must be https (mixed content); got ${wasmUrl}`);
    }
  }
```

- [ ] **Step 2: config.ts:**

```ts
// The only module that touches astro:env. Everything else takes the base URL
// as a parameter (keeps the virtual module out of the vitest import graph).
// Presence/https validation happens at build time in astro.config.mjs.

export { PUBLIC_DATA_BASE_URL, PUBLIC_WASM_BASE_URL } from 'astro:env/client';
```

- [ ] **Step 3: duck.ts.** Replace the BUNDLES block and bundleName derivation:

```ts
import { PUBLIC_WASM_BASE_URL } from './config';
import { joinUrl } from './urls';
```

```ts
// Self-hosted by default; a wrapper may serve the large binaries from its
// data host (PUBLIC_WASM_BASE_URL). Worker JS is ALWAYS same-origin: the
// Worker() constructor is same-origin restricted; the wasm binary is not.
const BUNDLES: duckdb.DuckDBBundles = PUBLIC_WASM_BASE_URL
  ? {
      mvp: { mainModule: joinUrl(PUBLIC_WASM_BASE_URL, 'duckdb-mvp.wasm'), mainWorker: workerMvp },
      eh: { mainModule: joinUrl(PUBLIC_WASM_BASE_URL, 'duckdb-eh.wasm'), mainWorker: workerEh },
    }
  : {
      mvp: { mainModule: wasmMvp, mainWorker: workerMvp },
      eh: { mainModule: wasmEh, mainWorker: workerEh },
    };
```

In `boot()`, change `bundleName: bundle.mainModule === wasmEh ? 'eh' : 'mvp'` to:

```ts
    bundleName: bundle.mainWorker === workerEh ? 'eh' : 'mvp',
```

(worker identity is stable under the mainModule override).

- [ ] **Step 4: Two-origin wasm smoke.** Build with the override pointing at a second local origin, serve wasm cross-origin, run the browse smoke:

```bash
SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 \
  PUBLIC_WASM_BASE_URL=http://127.0.0.1:8082 npx astro build
mkdir -p /tmp/wasm-origin && cp node_modules/@duckdb/duckdb-wasm/dist/duckdb-eh.wasm \
  node_modules/@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm /tmp/wasm-origin/
node scripts/serve-static.mjs --dir dist --port 8080 &
node scripts/serve-static.mjs --dir tests/fixtures/snapshot --port 8081 --cors &
node scripts/serve-static.mjs --dir /tmp/wasm-origin --port 8082 --cors &
SMOKE_BASE=http://127.0.0.1:8080 node scripts/smoke.mjs
```
Expected: smoke passes (first rows render proves the cross-origin wasm fetched + instantiated). Also rebuild WITHOUT the env and re-run smoke: proves the no-op path.

- [ ] **Step 5: `npx vitest run` + `npx astro check`. Commit** `feat(explorer-web): optional PUBLIC_WASM_BASE_URL for off-origin wasm binaries`

### Task 4: 404 page

**Files:**
- Create: `explorer-web/src/pages/404.astro`

- [ ] **Step 1:**

```astro
---
import Base from '../layouts/Base.astro';
import { loadSnapshotManifest } from '../lib/build-data';

const stamp = await loadSnapshotManifest();
---

<Base
  title="Page not found | Sovereign Prospectus Explorer"
  snapshotDate={stamp.snapshot_date}
  generatedAt={stamp.generated_at}
>
  <h1>Page not found</h1>
  <p>
    That page does not exist. Document addresses look like
    <code>/doc/&lt;slug&gt;/</code>; the slug may have changed in a
    snapshot refresh.
  </p>
  <p><a href="/">Back to browse</a></p>
</Base>
```

- [ ] **Step 2: Make assert-dist SNAPSHOT_DIR-aware** (plan-gate CRITICAL: it hardcodes the fixture parquet, and the fixture contains 3 synthetic slugs absent from production, so every production build would fail the assert). In `scripts/assert-dist.mjs`, replace the hardcoded fixture path:

```js
const snapshotDir = process.env.SNAPSHOT_DIR ?? 'tests/fixtures/snapshot';
const fixtureParquet = path.join(snapshotDir, 'documents.parquet');
```

(adapt to the file's actual variable names; neutral no-op upstream because CI always sets the fixture SNAPSHOT_DIR; turns the wrapper's production build into a real all-routes gate.)

- [ ] **Step 3: Verify.** Fixture build; `test -f dist/404.html && grep -c 'Page not found' dist/404.html` expected 1; assert-dist passes with and without SNAPSHOT_DIR set to the fixture. **Commit** `feat(explorer-web): 404 page + SNAPSHOT_DIR-aware assert-dist`

### Task 5: Raw-error diagnostics

**Files:**
- Modify: `explorer-web/src/scripts/dom.ts` (the `userMessageOf` function; single seam through which browse.ts and doc-text.ts route errors)

- [ ] **Step 1:** Read `src/scripts/dom.ts`, find `userMessageOf`, insert as its first statement:

```ts
  // Raw error to the console (S4): live-site failures must be
  // diagnosable as data-host misconfiguration vs app bug; the rendered
  // userMessage is deliberately generic.
  console.error('[explorer]', e);
```

(match the function's actual parameter name; if `userMessageOf` does not receive the error object in all paths, place the console.error at the catch sites in browse.ts:296,398 and doc-text.ts:605 instead, same comment.)

- [ ] **Step 2:** `npx vitest run` (dom.ts has tests if any; expect pass), fixture build + smoke. **Commit** `feat(explorer-web): log raw snapshot errors for live diagnosis`

### Task 6: Font tripwire in CI

**Files:**
- Modify: `.github/workflows/ci.yml` (explorer-web job, after checkout)

- [ ] **Step 1:** Add step (working-directory root overrides the job default):

```yaml
      - name: Font tripwire (Klim licence; open repo must never carry font binaries)
        working-directory: .
        run: |
          if git ls-files -- '*.woff2' '*.woff' '*.ttf' '*.otf' | grep .; then
            echo 'Font binaries found in the open repo; licence forbids this.'; exit 1
          fi
```

- [ ] **Step 2:** Verify locally: `git ls-files -- '*.woff2' '*.woff' '*.ttf' '*.otf' | wc -l` expected 0. **Commit** `ci: font-binary tripwire (licence)`

### Task 7: ARCHITECTURE.md note + PR

**Files:**
- Modify: `explorer-web/ARCHITECTURE.md` (Theme section)

- [ ] **Step 1:** Extend the Theme section with the S4 contract: the two display tokens, the brand slots (Head renders at the end of the AUTHORED head, before Astro's hoisted stylesheet link, which is exactly what font preloads want; Header replacement; `--ew-jump-offset` re-measure duty), PUBLIC_WASM_BASE_URL (worker stays same-origin), 404 page, SNAPSHOT_DIR-aware assert-dist, and the tripwire. Also record in Hosting constraints: the runtime fetches `parquet.duckdb_extension.wasm` from extensions.duckdb.org (a third live origin the deployed site depends on; pre-existing behavior, surfaced at the S4 plan gate; candidate future issue to self-host the extension).
- [ ] **Step 2:** Full local CI parity: `npm ci && npx astro check && npx vitest run`, fixture build + assert-dist, two-origin smoke (CI recipe). Expected: all green.
- [ ] **Step 3:** Push branch, `gh pr create` titled "S4 seams: brand slots, display tokens, off-origin wasm, 404, diagnostics (TEA-904)" with a body listing the six seams and their no-op guarantees. Comment `@codex review`. PR gate (Phase C) covers the diff; merge waits for Teal.

---

## Phase B: wrapper repo (local at ~/Code/prospectus-web-ti until Teal creates the GitHub repo)

### Task 8: Scaffold

- [ ] **Step 1:**

```bash
mkdir -p ~/Code/prospectus-web-ti && cd ~/Code/prospectus-web-ti && git init -b main
git submodule add https://github.com/Teal-Insights/sovereign-prospectus-corpus upstream
git -C upstream checkout lte/tea-904-s4-private-brand-wrapper-netlify-deploy  # temporary pin; bumped to the seams MERGE SHA in Phase C
mkdir -p brand/fonts brand/assets scripts .github/workflows
printf '.build/\nnode_modules/\n.env\n' > .gitignore
git add -A && git commit -m "scaffold: submodule + layout"
```

### Task 9: brand/tokens.css + fonts + favicons

**Files:**
- Create: `brand/tokens.css` (complete file below)
- Copy: 5 woff2 from `~/Code/tealinsights-site/public/fonts/` -> `brand/fonts/`
- Copy: `favicon.ico`, `favicon.png`, `apple-touch-icon.png` from `~/Code/tealinsights-site/public/` -> `brand/`; `teal-insights-logo.png` from its `src/assets/` -> `brand/assets/`

- [ ] **Step 1: Write brand/tokens.css** (complete; every upstream token name present; ratios computed at the spec gate):

```css
/* Teal Insights brand tokens for the Sovereign Prospectus Explorer.
   Swapped over src/styles/tokens.css by scripts/build.sh (staging copy
   only; the submodule stays pristine). Contrast ratios per the recorded
   bars: text pairs >= 4.5:1, non-text boundaries >= 3:1. Fonts are
   licensed (Klim): private repo only, served same-origin only. */

/* Klim webfonts, self-hosted from THIS site's /fonts/ (never a CDN,
   never the data host: that origin serves blanket ACAO). */
@font-face {
  font-family: 'Söhne';
  src: url('/fonts/soehne-buch.woff2') format('woff2');
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Söhne';
  src: url('/fonts/soehne-buch-kursiv.woff2') format('woff2');
  font-weight: 400;
  font-style: italic;
  font-display: swap;
}
@font-face {
  font-family: 'Söhne';
  src: url('/fonts/soehne-kraftig.woff2') format('woff2');
  font-weight: 500;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Söhne';
  src: url('/fonts/soehne-halbfett.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: 'Tiempos Headline';
  src: url('/fonts/tiempos-headline-semibold.woff2') format('woff2');
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}

/* Metric-tuned fallbacks (fontTools-derived, 2026-07-04): line boxes are
   metric-independent under the unitless 1.55 line-height; these close
   the wrap-shift residual during font-display: swap. */
@font-face {
  font-family: 'Söhne Fallback';
  src: local('Arial');
  size-adjust: 99.79%;
  ascent-override: 117.1%;
  descent-override: 42.3%;
  line-gap-override: 0%;
}
@font-face {
  font-family: 'Tiempos Headline Fallback';
  src: local('Georgia');
  size-adjust: 104.92%;
  ascent-override: 91.69%;
  descent-override: 23.83%;
  line-gap-override: 0%;
}

:root {
  /* Color. Data surfaces stay white; brand surface is the warm paper. */
  --ew-color-bg: #ffffff;
  --ew-color-surface: #fafaf7;
  --ew-color-text: #2a2a2a; /* 14.35:1 on white, 13.73:1 on surface */
  --ew-color-text-muted: #5c6770; /* 5.79:1 / 5.53:1 */
  --ew-color-accent: #143e5a; /* ink; checkbox accent 11.25:1 both ways */
  --ew-color-accent-contrast: #ffffff;
  --ew-color-border: #d4d0ca; /* decorative only */
  --ew-color-link: #143e5a; /* 11.25:1; hover stays ink + underline.
     Teal #0094BC is NON-TEXT ONLY (3.52:1 on white: passes the 3:1
     non-text bar, fails 4.5:1 text in every state, hover included). */
  --ew-color-badge-sovereign-bg: #e3efe6; /* S3 pairs kept: 7.30:1 */
  --ew-color-badge-sovereign-text: #1e5631;
  --ew-color-badge-nonsovereign-bg: #f3e6e6; /* 7.65:1 */
  --ew-color-badge-nonsovereign-text: #7a2e2e;
  --ew-color-badge-unverified-bg: #eeeae0; /* 5.41:1 */
  --ew-color-badge-unverified-text: #6b5d2e;
  --ew-color-error-bg: #fbeaea; /* 7.05:1 */
  --ew-color-error-text: #8c2f2f;
  --ew-color-notice-bg: #fdf6e3; /* 6.03:1 */
  --ew-color-notice-text: #6b5d2e;

  /* Type */
  --ew-font-body: 'Söhne', 'Söhne Fallback', -apple-system, BlinkMacSystemFont,
    'Segoe UI', Helvetica, Arial, sans-serif;
  --ew-font-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  --ew-font-display: 'Tiempos Headline', 'Tiempos Headline Fallback', Georgia,
    'Times New Roman', serif;
  --ew-font-weight-display: 600; /* Tiempos Headline ships semibold only */
  --ew-font-size-base: 1rem;
  --ew-font-size-small: 0.875rem;
  --ew-font-size-h1: 1.5rem;
  --ew-font-size-h2: 1.25rem;
  --ew-line-height: 1.55;

  /* Space and shape */
  --ew-space-1: 0.25rem;
  --ew-space-2: 0.5rem;
  --ew-space-3: 1rem;
  --ew-space-4: 1.5rem;
  --ew-space-5: 2.5rem;
  --ew-radius: 4px;
  --ew-max-width: 72rem;

  /* Layout reservations (re-measured under brand metrics in the branded
     build; see the verification log in the wrapper README). */
  --ew-table-min-height: 32rem;
  --ew-filters-min-height: 8rem;
  --ew-chips-min-height: 2.25rem;

  /* Form boundaries + search highlights + doc text + tap targets. */
  --ew-color-border-strong: #5c6770; /* 5.79:1 on white (bar: >= 3:1) */
  --ew-color-match-bg: #ffe08a; /* 11.13:1 vs #2a2a2a */
  --ew-color-match-text: #2a2a2a;
  --ew-color-match-current-bg: #f0a84b; /* 7.11:1 vs #2a2a2a; the
     lightness step vs match-bg is the current-match distinction */
  --ew-color-match-current-text: #2a2a2a;
  --ew-font-size-doc: 0.875rem;
  --ew-tap-target-min: 24px;
  --ew-tap-target: 44px;
  --ew-disabled-opacity: 0.5;
  --ew-jump-offset: 80px; /* re-measured against the branded header in
     the branded build; adjust here if the measured height differs */
}

@media (max-width: 640px) {
  :root {
    --ew-font-size-doc: 0.9375rem;
  }
}

/* Highlight pseudo-elements live in the tokens file so the token swap
   reaches them; literal fallbacks for engines that do not resolve var()
   inside highlight pseudos (Chromium before 134). */
::highlight(ew-match) {
  background-color: var(--ew-color-match-bg, #ffe08a);
  color: var(--ew-color-match-text, #2a2a2a);
}
::highlight(ew-match-current) {
  background-color: var(--ew-color-match-current-bg, #f0a84b);
  color: var(--ew-color-match-current-text, #2a2a2a);
}
```

- [ ] **Step 2: Copy assets:**

```bash
cd ~/Code/prospectus-web-ti
cp ~/Code/tealinsights-site/public/fonts/*.woff2 brand/fonts/
cp ~/Code/tealinsights-site/public/favicon.ico ~/Code/tealinsights-site/public/favicon.png \
   ~/Code/tealinsights-site/public/apple-touch-icon.png brand/
cp ~/Code/tealinsights-site/src/assets/teal-insights-logo.png brand/assets/
ls -la brand/fonts/  # expect 5 files, 36-40 KB each
```

- [ ] **Step 3: Commit** `brand: tokens, Klim fonts (licensed, private), favicons, logo`

### Task 10: brand/Head.astro + brand/Header.astro

**Files:**
- Create: `brand/Head.astro`, `brand/Header.astro`

- [ ] **Step 1: Head.astro:**

```astro
---
// Brand head additions: assets, preloads, stamp, analytics. No logic.
const wrapperCommit = import.meta.env.PUBLIC_WRAPPER_COMMIT ?? 'local';
const upstreamPin = import.meta.env.PUBLIC_UPSTREAM_PIN ?? 'local';
const deployId = import.meta.env.PUBLIC_DEPLOY_ID ?? 'local';
---

<link rel="icon" href="/favicon.ico" sizes="32x32" />
<link rel="icon" href="/favicon.png" type="image/png" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="preconnect" href="https://data.tealinsights.com" crossorigin />
<link rel="preload" href="/fonts/soehne-buch.woff2" as="font" type="font/woff2" crossorigin />
<link rel="preload" href="/fonts/soehne-halbfett.woff2" as="font" type="font/woff2" crossorigin />
<link rel="preload" href="/fonts/tiempos-headline-semibold.woff2" as="font" type="font/woff2" crossorigin />
<meta name="ti-build" content={`wrapper=${wrapperCommit} pin=${upstreamPin} deploy=${deployId}`} />
<script
  is:inline
  defer
  data-domain="prospectus.tealinsights.com"
  data-api="/pipes/flow"
  src="/pipes/main.js"></script>
```

- [ ] **Step 2: Header.astro** (logo dimensions: read the PNG's real width/height with `sips -g pixelWidth -g pixelHeight brand/assets/teal-insights-logo.png` and set width to round(38 * aspect); the explicit attributes are the CLS guard):

```astro
---
// Branded header. Height feeds --ew-jump-offset (re-measured in the
// branded build; see tokens.css).
---

<header class="ew-header">
  <a href="/" class="ti-brand" aria-label="Sovereign Prospectus Explorer home">
    <img src="/teal-insights-logo.png" alt="Teal Insights" height="30" width="{COMPUTED}" />
    <span class="ti-wordmark">Sovereign Prospectus Explorer</span>
  </a>
</header>

<style>
  .ti-brand {
    display: inline-flex;
    align-items: center;
    gap: var(--ew-space-2);
    text-decoration: none;
  }
  .ti-brand img {
    display: block;
  }
  .ti-wordmark {
    font-weight: 600;
    color: var(--ew-color-accent);
  }
</style>
```

- [ ] **Step 3: Commit** `brand: Head (preconnect, preloads, stamp, Plausible) + Header (logo wordmark)`

### Task 11: scripts/build.sh

**Files:**
- Create: `scripts/build.sh` (mode 755)

- [ ] **Step 1:**

```bash
#!/usr/bin/env bash
# Branded build: rsync the pinned upstream explorer-web into .build/,
# overlay brand, acquire the snapshot meta, build, prune. Runs
# identically on Netlify, CI (SNAPSHOT_DIR preset), and locally.
set -euo pipefail
cd "$(dirname "$0")/.."

UP=upstream/explorer-web
ST=.build

command -v rsync >/dev/null || { echo "rsync required"; exit 1; }
rsync -a --delete --exclude node_modules --exclude dist --exclude .astro "$UP/" "$ST/"

# Brand overlay (assets + markup only; logic lives upstream).
cp brand/tokens.css "$ST/src/styles/tokens.css"
mkdir -p "$ST/src/brand" "$ST/public/fonts"
cp brand/Head.astro brand/Header.astro "$ST/src/brand/"
cp brand/fonts/*.woff2 "$ST/public/fonts/"
cp brand/favicon.ico brand/favicon.png brand/apple-touch-icon.png "$ST/public/"
cp brand/assets/teal-insights-logo.png "$ST/public/"

# Token-inventory assert: every --ew-* name upstream defines must exist
# in the branded file (S3 added 12 tokens in one PR; drift breaks layout).
toks=$(grep -o -- '--ew-[a-z0-9-]*' "$UP/src/styles/tokens.css" | sort -u)
[ -n "$toks" ] || { echo "no --ew-* tokens found upstream (file moved?)"; exit 1; }
missing=0
while IFS= read -r tok; do
  grep -q -- "$tok:" brand/tokens.css || { echo "MISSING TOKEN: $tok"; missing=1; }
done <<< "$toks"
[ "$missing" -eq 0 ] || exit 1

# Wasm version drift guard: the versioned data-host path must match the
# installed duckdb-wasm, or returning visitors get a poisoned immutable
# cache on the first version bump.
if [ -n "${PUBLIC_WASM_BASE_URL:-}" ]; then
  DW_V=$(node -p "require('./$UP/package.json').dependencies['@duckdb/duckdb-wasm']")
  case "$PUBLIC_WASM_BASE_URL" in
    *"duckdb-wasm-$DW_V") : ;;
    *) echo "PUBLIC_WASM_BASE_URL must end with duckdb-wasm-$DW_V"; exit 1 ;;
  esac
fi

# Snapshot acquisition. CI presets SNAPSHOT_DIR (fixture, no network).
if [ -z "${SNAPSHOT_DIR:-}" ]; then
  FETCH_BASE="${BUILD_DATA_FETCH_BASE:-${PUBLIC_DATA_BASE_URL:?PUBLIC_DATA_BASE_URL required}}"
  SNAP="$ST/snapshot-cache"
  mkdir -p "$SNAP"
  # MANIFEST first (no-store), then the parquet WITH the version token:
  # a bare parquet URL would prime the CDN's unversioned cache entry for
  # a year and later builds would silently get stale bytes.
  curl -fsSL --compressed "$FETCH_BASE/MANIFEST.json" -o "$SNAP/MANIFEST.json"
  GEN=$(node -e 'console.log(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).generated_at)' "$SNAP/MANIFEST.json")
  # Guard: an empty/undefined GEN would prime "?v=undefined" as a STABLE
  # immutable cache key, the exact failure the token exists to prevent.
  { [ -n "$GEN" ] && [ "$GEN" != "undefined" ]; } || { echo "MANIFEST.generated_at missing"; exit 1; }
  curl -fsSL --compressed "$FETCH_BASE/documents.parquet?v=$(node -e 'console.log(encodeURIComponent(process.argv[1]))' "$GEN")" -o "$SNAP/documents.parquet"
  head -c4 "$SNAP/documents.parquet" | grep -q 'PAR1' || { echo "parquet magic missing (gzip not decoded?)"; exit 1; }
  export SNAPSHOT_DIR="snapshot-cache"
fi

# Build stamp (Netlify provides COMMIT_REF/DEPLOY_ID; verified names).
export PUBLIC_WRAPPER_COMMIT="${COMMIT_REF:-$(git rev-parse --short HEAD 2>/dev/null || echo local)}"
PIN="$(git -C upstream rev-parse --short HEAD 2>/dev/null || echo local)"
if [ "${NETLIFY:-}" = "true" ] && [ "$PIN" = "local" ]; then
  echo "submodule pin unreadable in a Netlify build"; exit 1
fi
export PUBLIC_UPSTREAM_PIN="$PIN"
export PUBLIC_DEPLOY_ID="${DEPLOY_ID:-local}"

cd "$ST"
npm ci
npx astro build
# The static ?url imports emit both wasm binaries (74 MB) even when
# PUBLIC_WASM_BASE_URL moves them to the data host; strip the dead weight.
if [ -n "${PUBLIC_WASM_BASE_URL:-}" ]; then
  rm -f dist/_astro/*.wasm
fi
node scripts/assert-dist.mjs
echo "BUILD OK: $(find dist -name '*.html' | wc -l | tr -d ' ') pages"
```

- [ ] **Step 2: Verify against the fixture** (no network, branded):

```bash
cd ~/Code/prospectus-web-ti
SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=https://data.example.invalid bash scripts/build.sh
```
SNAPSHOT_DIR resolves from `.build/` cwd, so the fixture path is valid from there (it is inside the staging copy). Expected: `BUILD OK: 22 pages` (20 fixture docs + index + 404), dist contains fonts + favicon, `grep -c 'Tiempos' .build/dist/_astro/*.css` >= 1, `grep -c 'ti-build' .build/dist/index.html` = 1.

- [ ] **Step 3: Commit** `build: staging-copy branded build with token assert + tokenized snapshot fetch`

### Task 12: netlify.toml

**Files:**
- Create: `netlify.toml`

- [ ] **Step 1:**

```toml
# prospectus.tealinsights.com (private brand wrapper)

[build]
  command = "bash scripts/build.sh"
  publish = ".build/dist"

[build.environment]
  NODE_VERSION = "22"

# The default netlify.app hostname is NOT covered by the font licence;
# force everything to the licensed subdomain (Netlify never
# auto-redirects the default subdomain). HARD COUPLING: the Netlify site
# name MUST be prospectus-tealinsights, or this rule silently never
# matches and fonts serve 200 from the real default hostname. If the
# name is taken at creation, update this `from` BEFORE the first build.
[[redirects]]
  from = "https://prospectus-tealinsights.netlify.app/*"
  to = "https://prospectus.tealinsights.com/:splat"
  status = 301
  force = true

# Plausible first-party proxy (same pattern as the main site).
[[redirects]]
  from = "/pipes/main.js"
  to = "https://plausible.io/js/script.file-downloads.outbound-links.js"
  status = 200
  force = true

[[redirects]]
  from = "/pipes/flow"
  to = "https://plausible.io/api/event"
  status = 200
  force = true

# Fonts: immutable, and deliberately NO Access-Control-Allow-Origin
# (cross-origin @font-face fails without CORS: the Klim 3d hotlink
# measure). If a font file ever changes it gets a new filename.
[[headers]]
  for = "/fonts/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

- [ ] **Step 2: Commit** `deploy: netlify config (redirects incl. licence 301, font headers)`

### Task 13: wrapper CI + README

**Files:**
- Create: `.github/workflows/ci.yml`, `README.md`

- [ ] **Step 1: ci.yml:**

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  branded-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - name: Branded fixture build
        run: SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=https://data.example.invalid bash scripts/build.sh
      - name: Install Playwright Chromium
        run: cd .build && npx playwright install --with-deps chromium
      - name: Branded smoke (two origins)
        run: |
          cd .build
          SNAPSHOT_DIR=tests/fixtures/snapshot PUBLIC_DATA_BASE_URL=http://127.0.0.1:8081 npx astro build
          node scripts/serve-static.mjs --dir dist --port 8080 &
          node scripts/serve-static.mjs --dir tests/fixtures/snapshot --port 8081 --cors &
          curl --silent --output /dev/null --retry 15 --retry-connrefused --retry-delay 1 http://127.0.0.1:8080/
          curl --silent --output /dev/null --retry 15 --retry-connrefused --retry-delay 1 http://127.0.0.1:8081/MANIFEST.json
          SMOKE_BASE=http://127.0.0.1:8080 node scripts/smoke.mjs
      # The branded dist is never uploaded as an artifact (fonts).
```

- [ ] **Step 2: README.md** with sections: what this repo is (wrapper; no application logic; features go upstream), repo map, pin-bump procedure (bump gitlink; diff upstream tokens.css names vs brand/tokens.css; CI; deploy), local dev loop (build.sh then `node .build/scripts/serve-static.mjs --dir .build/dist`; or `cd .build && npm run dev` with a local SNAPSHOT_DIR), deploy runbook (env vars, first-build gate, rollback via Netlify publish-a-previous-deploy + drift-notice caveat), data-host runbook (upload-snapshot.sh; MANIFEST-last rationale; scripted consumers need --compressed; Range-over-gzip note), and **Font licensing** quoting LICENSE-FONTS.md verbatim PLUS the additions ratified at the spec gate: netlify.app 301 + previews/branch-deploys disabled + deploy-permalink residual; fonts never on data.tealinsights.com (blanket ACAO); page-view tier on the house licence (order number recorded in the private wrapper README and tealinsights-site/LICENSE-FONTS.md) aggregates across ALL tealinsights.com sites, 3-month average (Plausible on both sites is the monitoring; sum monthly); contractor deletion duty (3i) and notify-Klim duty; no subsetting/format conversion; repo must stay private, if it ever must go public the fonts move out first.
- [ ] **Step 3: Commit** `ci + README (licence rules, runbooks)`

### Task 14: Data-host tooling (runs when AWS credentials arrive; written and reviewed now)

**Files:**
- Create: `scripts/upload-snapshot.sh`, `scripts/provision-data-host.sh`, `scripts/iam-deploy-policy.json`

- [ ] **Step 1: upload-snapshot.sh:**

```bash
#!/usr/bin/env bash
# Publish data/snapshot to the data host, pre-compressed at rest.
# Usage: BUCKET=ti-sovtech-data SNAPSHOT=~/Code/sovereign-prospectus-corpus/data/snapshot bash scripts/upload-snapshot.sh
# Requires: aws cli with a credential allowed by iam-deploy-policy.json.
set -euo pipefail
BUCKET="${BUCKET:?}"
SNAPSHOT="${SNAPSHOT:?}"
PREFIX=prospectus/snapshot
WASM_PREFIX=prospectus/wasm/duckdb-wasm-1.32.0
TMPROOT="$(mktemp -d)"
STAGE="$TMPROOT/stage"
trap 'rm -rf "$TMPROOT"' EXIT
IMMUTABLE="public, max-age=31536000, immutable"

command -v aws >/dev/null || { echo "aws cli required"; exit 1; }
command -v brotli >/dev/null || { echo "brotli required (brew install brotli)"; exit 1; }
WASM_SRC="$(cd "$(dirname "$0")/.." && pwd)/.build/node_modules/@duckdb/duckdb-wasm/dist"
[ -d "$WASM_SRC" ] || { echo "run scripts/build.sh first (.build/node_modules missing)"; exit 1; }
# The versioned prefix must match the installed version: uploading new
# bytes to an old immutable path is permanent cache poisoning.
DW_V=$(node -p "require('$WASM_SRC/../package.json').version")
[ "duckdb-wasm-$DW_V" = "$(basename "$WASM_PREFIX")" ] || { echo "wasm $DW_V != prefix $WASM_PREFIX"; exit 1; }

echo "staging gzip tree (gzip -n: header-stable on one gzip build)..."
mkdir -p "$STAGE/text"
gzip -n -9 -c "$SNAPSHOT/documents.parquet" > "$STAGE/documents.parquet"
find "$SNAPSHOT/text" -name '*.json' -print0 | while IFS= read -r -d '' f; do
  gzip -n -6 -c "$f" > "$STAGE/text/$(basename "$f")"
done
gzip -n -9 -c "$SNAPSHOT/MANIFEST.json" > "$STAGE/MANIFEST.json"

echo "pass 1/4: text (json, gzip, immutable)..."
# Metadata flags apply to every object THIS sync transfers; never reuse a
# staging dir and never add --size-only. No --delete: removed docs leave
# stale (fetchable) objects; a takedown needs a manual aws s3 rm (runbook).
aws s3 sync "$STAGE/text" "s3://$BUCKET/$PREFIX/text" \
  --content-type application/json --content-encoding gzip \
  --cache-control "$IMMUTABLE" --only-show-errors

echo "pass 2/4: parquet..."
aws s3 cp "$STAGE/documents.parquet" "s3://$BUCKET/$PREFIX/documents.parquet" \
  --content-type application/octet-stream --content-encoding gzip \
  --cache-control "$IMMUTABLE"

echo "pass 3/4: wasm (brotli, versioned path)..."
for w in duckdb-eh.wasm duckdb-mvp.wasm; do
  brotli -f -q 11 -o "$STAGE/$w.br" "$WASM_SRC/$w"
  aws s3 cp "$STAGE/$w.br" "s3://$BUCKET/$WASM_PREFIX/$w" \
    --content-type application/wasm --content-encoding br \
    --cache-control "$IMMUTABLE"
done

echo "pass 4/4: MANIFEST LAST (no-store; ordering is load-bearing:"
echo "a visitor reading the NEW manifest mid-upload would cache OLD"
echo "bytes under the NEW ?v= token immutably)..."
aws s3 cp "$STAGE/MANIFEST.json" "s3://$BUCKET/$PREFIX/MANIFEST.json" \
  --content-type application/json --content-encoding gzip \
  --cache-control "no-store"
echo "DONE"
```

- [ ] **Step 2: provision-data-host.sh** (two phases; region us-east-1; the plan-gate ops reviewer supplied and reviewed these bodies. Phase 1 = bucket + BPA + cache policy + OAC + ACM request, prints DNS batch 1 and exits; the snapshot UPLOAD starts immediately after phase 1, in parallel with cert validation. Phase 2 runs after validation and creates the distribution ONCE with alias + cert, no update-distribution dance):

```bash
# Phase 1
aws s3api create-bucket --bucket "$BUCKET" --region us-east-1
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

CP_ID=$(aws cloudfront create-cache-policy --cache-policy-config '{
  "Name":"ti-data-precompressed",
  "Comment":"MinTTL 0 honors per-object Cache-Control; ?v= in key; no AE keying (pre-compressed at rest, Compress=false)",
  "MinTTL":0,"DefaultTTL":0,"MaxTTL":31536000,
  "ParametersInCacheKeyAndForwardedToOrigin":{
    "EnableAcceptEncodingGzip":false,"EnableAcceptEncodingBrotli":false,
    "HeadersConfig":{"HeaderBehavior":"none"},
    "CookiesConfig":{"CookieBehavior":"none"},
    "QueryStringsConfig":{"QueryStringBehavior":"all"}}}' \
  --query CachePolicy.Id --output text)

OAC_ID=$(aws cloudfront create-origin-access-control --origin-access-control-config \
  '{"Name":"ti-sovtech-data-oac","OriginAccessControlOriginType":"s3","SigningBehavior":"always","SigningProtocol":"sigv4"}' \
  --query OriginAccessControl.Id --output text)

CERT_ARN=$(aws acm request-certificate --region us-east-1 --domain-name data.tealinsights.com \
  --validation-method DNS --query CertificateArn --output text)
sleep 10
aws acm describe-certificate --region us-east-1 --certificate-arn "$CERT_ARN" \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'   # -> DNS batch 1
```

```bash
# Phase 2 (after Teal adds the validation CNAME)
aws acm wait certificate-validated --region us-east-1 --certificate-arn "$CERT_ARN"
DIST_ID=$(aws cloudfront create-distribution --distribution-config '{
  "CallerReference":"ti-data-'"$(date +%s)"'",
  "Comment":"data.tealinsights.com (pre-compressed S3 origin)",
  "Enabled":true,"DefaultRootObject":"","HttpVersion":"http2and3","IsIPV6Enabled":true,
  "Aliases":{"Quantity":1,"Items":["data.tealinsights.com"]},
  "Origins":{"Quantity":1,"Items":[{"Id":"s3-data",
    "DomainName":"'"$BUCKET"'.s3.us-east-1.amazonaws.com",
    "OriginAccessControlId":"'"$OAC_ID"'","S3OriginConfig":{"OriginAccessIdentity":""}}]},
  "DefaultCacheBehavior":{"TargetOriginId":"s3-data","ViewerProtocolPolicy":"redirect-to-https",
    "AllowedMethods":{"Quantity":3,"Items":["GET","HEAD","OPTIONS"],
      "CachedMethods":{"Quantity":3,"Items":["GET","HEAD","OPTIONS"]}},
    "Compress":false,"CachePolicyId":"'"$CP_ID"'",
    "ResponseHeadersPolicyId":"60669652-455b-4ae9-85a4-c4c02393f86c"},
  "ViewerCertificate":{"ACMCertificateArn":"'"$CERT_ARN"'","SSLSupportMethod":"sni-only",
    "MinimumProtocolVersion":"TLSv1.2_2021"}}' \
  --query Distribution.Id --output text)
# The ResponseHeadersPolicyId is managed SimpleCORS; verify at run time:
#   aws cloudfront list-response-headers-policies --type managed \
#     --query "ResponseHeadersPolicyList.Items[?ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name=='Managed-SimpleCORS'].ResponseHeadersPolicy.Id" --output text

ACCT=$(aws sts get-caller-identity --query Account --output text)
aws s3api put-bucket-policy --bucket "$BUCKET" --policy '{
  "Version":"2012-10-17","Statement":[{"Sid":"AllowCloudFront","Effect":"Allow",
  "Principal":{"Service":"cloudfront.amazonaws.com"},"Action":"s3:GetObject",
  "Resource":"arn:aws:s3:::'"$BUCKET"'/*",
  "Condition":{"StringEquals":{"AWS:SourceArn":"arn:aws:cloudfront::'"$ACCT"':distribution/'"$DIST_ID"'"}}}]}'
aws cloudfront get-distribution --id "$DIST_ID" --query Distribution.DomainName --output text  # -> DNS batch 2
```

- [ ] **Step 3: iam-deploy-policy.json** enumerating: `s3:CreateBucket, s3:PutBucketPublicAccessBlock, s3:PutBucketPolicy, s3:GetBucketLocation, s3:ListBucket, s3:PutObject`; `cloudfront:CreateCachePolicy, CreateOriginAccessControl, CreateDistribution, GetDistribution, GetDistributionConfig, UpdateDistribution, ListResponseHeadersPolicies`; `acm:RequestCertificate, DescribeCertificate, ListCertificates`; `sts:GetCallerIdentity`.
- [ ] **Step 4: `bash -n` both scripts (syntax); shellcheck if available. Commit** `data host: provisioning + pre-compressed upload tooling`

### Task 15: Local verification of the branded build (full snapshot)

- [ ] **Step 1: Full branded build against the local snapshot** (no network; SNAPSHOT_DIR must be ABSOLUTE because astro resolves it from `.build/`):

```bash
cd ~/Code/prospectus-web-ti
SNAPSHOT_DIR="$HOME/Code/sovereign-prospectus-corpus/data/snapshot" \
  PUBLIC_DATA_BASE_URL=http://127.0.0.1:8091 bash scripts/build.sh
```
Expected: `BUILD OK: 9776 pages` (9,774 docs + index + 404; MANIFEST document_count is 9774).

- [ ] **Step 2: Serve two origins + eyeball + measure** (no --precompress: it is a one-shot compression mode that exits, not a serve flag; the server already gzips json/parquet on the fly):

```bash
node .build/scripts/serve-static.mjs --dir .build/dist --port 8090 &
node .build/scripts/serve-static.mjs --dir ~/Code/sovereign-prospectus-corpus/data/snapshot --port 8091 --cors &
```
Playwright-driven checks (script in scratchpad, not committed): header offsetHeight -> set `--ew-jump-offset` in brand/tokens.css to the measured value; populated 50-row table region offsetHeight -> raise `--ew-table-min-height` if the measured value exceeds 32rem/512px... measure and record; filters block height at 1280px and 375px vs 8rem; exactly ONE network request per font face; every font request origin = 127.0.0.1:8090.
- [ ] **Step 3: Lighthouse (system Chrome) on browse bare + parameterized + one doc page.** Gates: perf >= 90, a11y >= 95, CLS <= 0.02 (expect ~100/100/0 on localhost). Record numbers in the wrapper README verification log.
- [ ] **Step 4: axe via the upstream harness pattern (target-size on): zero serious/critical on browse + doc.**
- [ ] **Step 5: Fix anything found (token values only), re-run, commit** `verify: branded build measurements + reservation re-tunes`

### Task 16: tealinsights-site licence fix (separate repo, for Teal's merge)

- [ ] **Step 1:** In `~/Code/tealinsights-site`, branch `fix/netlify-app-font-leak`, insert ABOVE the /pipes rules in netlify.toml (first match wins; putting the host rule first gives uniform "nothing serves from netlify.app" semantics):

```toml
# The default netlify.app hostname is not covered by the Klim licence;
# force everything to the licensed domain. (Found during TEA-904's spec
# gate: fonts were serving 200 from tealinsights.netlify.app.)
[[redirects]]
  from = "https://tealinsights.netlify.app/*"
  to = "https://tealinsights.com/:splat"
  status = 301
  force = true
```

- [ ] **Step 2:** Commit, push, `gh pr create` (title "fix: 301 the netlify.app hostname to tealinsights.com (font licence)"), note it in TEA-904. Teal merges.

---

## Phase C: gated ship sequence (each step waits for its prerequisite)

1. **PR gate council** on both diffs (open-repo seams PR + wrapper repo tree), fresh reviewers, dispositions posted (seams PR comment + TEA-904 comment). Fix findings.
2. Teal merges the seams PR -> bump wrapper submodule to the MERGE SHA -> push wrapper main to the created GitHub repo (first push direct; recorded deviation: subsequent pin bumps and changes go via PR) -> wrapper CI green.
3. AWS credential arrives -> provision-data-host.sh phase 1 (bucket, BPA, cache policy, OAC, ACM request) -> START upload-snapshot.sh IMMEDIATELY (needs only the bucket; ~30-60 min runs in parallel with cert validation) -> hand Teal the ACM validation CNAME (DNS batch 1) -> cert validates -> phase 2 (distribution, bucket policy) -> hand the distribution domain (DNS batch 2) -> gate: `curl -fsS -H 'Origin: https://prospectus.tealinsights.com' --compressed https://data.tealinsights.com/prospectus/snapshot/MANIFEST.json`.
4. Teal creates the Netlify site: name MUST be `prospectus-tealinsights` (the licence 301 in netlify.toml is host-coupled; if taken, report the actual name so the toml is updated BEFORE the first build). Record the org PLAN (legacy vs credit-metered) on TEA-904. Builds stopped, deploy previews + branch deploys disabled, env vars PUBLIC_DATA_BASE_URL=https://data.tealinsights.com/prospectus/snapshot and PUBLIC_WASM_BASE_URL=https://data.tealinsights.com/prospectus/wasm/duckdb-wasm-1.32.0, custom domain added, register prospectus.tealinsights.com in the Plausible dashboard -> DNS batch 3 (prospectus CNAME) -> first build (Teal's go-ahead) -> TLS provisions.
5. Live verification per the spec's 10-point plan, PLUS: `curl -sI https://prospectus-tealinsights.netlify.app/fonts/soehne-buch.woff2` expecting 301 to the subdomain. Record numbers.
6. Confirm the tealinsights-site netlify.app 301 PR (Task 16) is merged: the main-site leak is live until then.
7. TEA-904: comment live Lighthouse numbers + hosting decisions, tick the checklist, close. Update SESSION-HANDOFF.md and the project status.

## Plan-gate dispositions (3 reviewers, 2026-07-04)

- **Empiricist (prototyped Tasks 1-4 in a scratch copy):** all four seams
  WORK AS PLANNED verbatim: import.meta.glob brand slots compile and pass
  astro check 0/0 in both states; the wasm override passed the full
  three-origin smoke (39 checks incl. axe) with dist wasm deleted and
  bundleName correct; vitest 97/97; both build-gate reject paths fire
  with the exact messages. Findings adopted: byte-vs-rendering wording,
  authored-head emission nuance (recorded in Task 7), the
  extensions.duckdb.org third-origin discovery (Task 7 + ARCHITECTURE).
- **Ops reviewer:** CRITICAL assert-dist fixture-binding -> FIXED (Task 4
  Step 2, SNAPSHOT_DIR-aware upstream). IMPORTANTs all adopted:
  generated_at guard, wasm version asserts (build.sh + upload script),
  tool guards + trap cleanup + --only-show-errors in upload-snapshot.sh,
  full provision-script bodies (one-shot distribution after cert
  validation), Task 15 command corrections (absolute SNAPSHOT_DIR, no
  --precompress), Phase C upload reordering + main-site-301 merge step +
  plan-fact recording + first-push deviation recorded. Sound: token
  assert scoping, SNAPSHOT_DIR relative semantics, curl/PAR1 mechanics,
  rsync exclude interplay, MANIFEST-last guarantee.
- **Netlify/CI reviewer:** IMPORTANT site-name coupling -> FIXED
  (netlify.toml comment + Phase C.4 + verification curl). Minors
  adopted: is:inline on the Plausible tag, port 8081 readiness probe,
  Plausible dashboard registration (Phase C.4), main-site rule ordering
  (Task 16), wasm URL triple-check confirmed exact. Platform behaviors
  verified: host-scoped forced redirects, netlify.toml headers are
  publish-dir independent, no default ACAO (verified live), COMMIT_REF /
  DEPLOY_ID exact names, PUBLIC_* env exposure without schema, checkout
  submodules: true semantics.

## Self-review notes

- Spec coverage: D1 (Task 8 + Phase C.2), D2 (Tasks 1-6), D3 (Tasks 9-10, 15), D4 (Task 9), D5 (Task 14 + Phase C.3), D6 (Tasks 11-13), D7 (Tasks 8-14), sequencing + verification (Phase C).
- The fixture page count in Task 11 Step 2 and the `{COMPUTED}` logo width in Task 10 are measured at execution time (real values recorded then; not placeholders for code, but for measurements only obtainable by running).
- Type consistency: joinUrl imported from './urls' (exists, exported); PUBLIC_WASM_BASE_URL exported from config.ts and consumed only in duck.ts; brand glob keys match the literal './../brand/*.astro' Vite pattern relative to src/layouts/.
