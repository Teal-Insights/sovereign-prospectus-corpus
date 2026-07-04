# S3: Explorer core at Shiny-app parity with real URLs (TEA-903)

**Date:** 2026-07-04
**Issue:** TEA-903 (S3 of the Explorer v2 project)
**Builds on:** S2 scaffold (PR #87), `explorer-web/ARCHITECTURE.md`, spec
`2026-07-04-explorer-web-scaffold-design.md`
**Parity target:** `shiny/app.py` + `explorer/queries.py`, `explorer/highlight.py`,
`explorer/display.py` in the Dropbox repo (NOT `demo/shiny-app/`; that pointer
in the issue description predates the correction on the issue)

## Goal

Bring `explorer-web/` to functional parity with the v1 Shiny app, plus the four
improvements that justify the rebuild: filters in query params (shareable URLs),
working back/forward, instant client-side filtering, and a sensible mobile
layout. Runs against the full snapshot (9,774 docs). Lighthouse performance 90+
on browse. Neutral theme held (CSS custom properties only; no Teal Insights
fonts or brand).

## Non-goals

- Corpus-wide search. `SearchSlot.astro` stays empty; issue #82 / TEA-907 owns
  the architecture decision and neither candidate is foreclosed here.
- Hosting/deployment (TEA-906). Verification is against a locally served build.
- Theming beyond the neutral tokens (S4 re-themes).
- Rendering markdown as rich HTML (see "Text rendering" below for why raw
  pre-wrap text is load-bearing).
- Snapshot schema changes. #86 (pages[].offset_utf16) stays open; this design
  does not need pages[] at all. #84 (vintage into MANIFEST) stays open; the
  hardcoded FY2027 footnote remains the stopgap.

## Data facts that shaped the design (profiled 2026-07-04 snapshot)

- 9,774 docs: 9,641 markdown-sourced, 30 pages-sourced, 103 no-text.
- Text scale: 3,308 docs over v1's 200K-char full-render threshold; 620 over
  1M chars; max 28.6M chars (29.0 MB, luxse-100387641); 15 docs over the 5 MB
  click-gate.
- `toc[]` entries carry `offset` (code points) and `offset_utf16`; capped at
  2,000 entries per doc (worst doc: ~14K chars per section on average).
  `pages[]` carries code-point offsets only (issue #86) and is not consumed.
- Classifications: `income_group` and `region` are already materialized with
  'Unknown' as a real value (215 docs); no NULLs. 101 distinct country codes.
  High income is 5,555 of 9,774 docs (LuxSE bulk).
- Corpus stats for the cards: 9,774 documents, 4 sources, 265 issuers
  (computed at build time from the parquet).

## v1 parity inventory

This table is the parity checklist verified side by side against the live
Shiny app at the end of the build.

| # | v1 feature (shiny/app.py) | S3 treatment |
|---|---------------------------|--------------|
| P1 | Stats cards: Documents, Sources, Issuers | Build-time static HTML from parquet (keeps LCP static) |
| P2 | "About this project" expander | Static `<details>` with v1 content (links to GitHub, prototype, Q-CRAFT, contact); neutral styling |
| P3 | Country filter (multi, searchable, sorted by name) | Searchable multi-select (input + datalist + removable chips); country_code values, country_name labels |
| P4 | Region filter (multi) | Checkbox-group popover (`<details>`), 'Unknown' included |
| P5 | Income group filter (multi) | Checkbox-group popover, 'Unknown' included |
| P6 | Source filter (multi, display names) | Checkbox-group popover; display names shown, source keys as values |
| P7 | "Include high-income countries" toggle, default off | Same checkbox, same default, same label |
| P8 | Count line "N documents, newest first (showing X to Y)" | Status line keeps S2's scope-accurate copy and adds the shown range |
| P9 | Paginated table, 50/page, newest first | Kept from S2 (adds Country/Type/Status columns); order `publication_date DESC NULLS LAST, slug DESC` |
| P10 | Row click opens document | Real links to `/doc/<slug>/` (improvement: middle-click, share, back all work) |
| P11 | Prev/Next pagination | Kept from S2, page in URL |
| P12 | Detail metadata (source, date, type, country, region) | Kept from S2 (richer: adds income group, lending category, badge, cite-as) |
| P13 | "View original filing" link | Kept from S2 |
| P14 | Table of Contents expander | `<details>` TOC rendered from `toc[]`; entries are clickable jumps (improvement: v1's list was inert) |
| P15 | Full text display | Raw pre-wrap text (see "Text rendering"); v1 rendered markdown as HTML below 200K chars, a deliberate deviation recorded in the checklist |
| P16 | In-document search with highlighting and match count | CSS Custom Highlight API over the raw text; total count, per-section counts, prev/next match navigation; `q` in URL |
| P17 | Page-at-a-time fallback for large docs | Unreproducible (markdown docs have no page anchors); replaced by chunk-by-TOC-offset (see "Large documents") |
| P18 | "Full text not yet available" for missing text | S2's no-text state kept (more honest: shows `no_text_reason`) |
| P19 | Source display names (SEC EDGAR, FCA NSM, Luxembourg Stock Exchange, #PublicDebtIsPublic) | `sourceDisplay()` added to `lib/format.ts`, used in table, filters, doc page |
| P20 | Teal branding (Inter/Playfair, teal palette, logos) | Explicitly NOT ported: neutral tokens only, font licence forbids the brand fonts here; S4 re-themes |

Improvements beyond parity (the rebuild's justification): filters in query
params, working back/forward (bfcache + popstate), instant client-side
filtering (25-35 ms steady-state queries), sensible mobile layout.

## Design

### Scoping model: two independent toggles

- **Sovereign scope** (S2 council credibility feature, kept): default
  sovereign-only, "Include N non-sovereign or unverified documents" toggle,
  live counts, three-state badges.
- **High-income toggle** (v1 parity): "Include high-income countries",
  default off, i.e. default predicate `income_group != 'High income'`
  ('Unknown' passes, matching v1's COALESCE semantics).
- Interplay fix over v1: when the income-group filter has explicit selections,
  the high-income exclusion clause is dropped (v1 ANDs both, so selecting
  "High income" with the toggle off silently yields zero rows; S3 treats an
  explicit income selection as authoritative). Recorded as a deviation.
- Status copy must stay scope-accurate (extends S2's `filteredStatus`
  pattern); every rendering of counts states which scope it covers.

### Filters and URL state

All browse state lives in query params; the URL is the single source of truth.

- Params: `country` (comma-joined ISO codes), `region`, `income`, `source`
  (comma-joined; source uses keys, not display names), `hi=1` (include high
  income), `scope=all` (include non-sovereign), `page` (0-based, omitted when
  0). Comma-joining is safe: codes and these enum values never contain commas.
  Unknown values from a shared URL are dropped (S2's reset rule, extended).
- Doc page: `q` (in-document search term).
- **History semantics:** discrete state changes (filter select/remove, toggle,
  page nav) call `pushState`, so back/forward walks the filter history.
  Continuous input (typing in the doc search box) is debounced (250 ms) into
  `replaceState`. A `popstate` handler re-reads state from the URL and
  re-renders without refetching (DuckDB and the parquet are already resident;
  bfcache keeps the worker alive across page navigations).
- **Filter controls** (vanilla, tokens-only styling, one shared implementation):
  - Country: `<input list>` + `<datalist>` (native searchable autocomplete over
    101 countries) with removable chips for selected values. Labeled, chip
    remove buttons are real `<button>`s with accessible names.
  - Region / Income / Source: `<details>` popovers containing checkbox groups
    (4-8 options each); summary shows selection count.
  - No Apply button; every change re-queries immediately.
- `lib/queries.ts` grows `BrowseFilters` (arrays for the four filters, the two
  booleans, page) and the WHERE builder; all SQL stays in that file. Filter
  option queries: distinct region/income/source, distinct
  `country_code, country_name` pairs sorted by name.

### Browse page

- Stats cards (P1) and the About expander (P2) are static HTML rendered at
  build time via `lib/build-data.ts` aggregation over the parquet, above the
  filter row; zero CLS, LCP stays static.
- Subtitle line under the h1 carries the build-stamped document count
  ("Browse 9,774 sovereign bond prospectuses..." with the live number).
- The World Bank vintage footnote (`WB_VINTAGE_NOTE`) renders on browse
  because region and income group are now filter dimensions there (the
  obligation travels with any classification column or filter).
- Table: Date, Issuer, Country, Type, Source, Status columns (S2 set, with
  source display names). Mobile (< 640px): Type and Status columns hidden via
  CSS; the table region also gets `overflow-x: auto` as a safety rail. Filter
  row wraps. Reserved heights: the table region keeps
  `--ew-table-min-height`; the filter block gets a reserved min-height token
  so late-arriving option lists cannot shift layout (CLS 0 commitment).
- DuckDB init stays deferred past first paint (`window load`), unchanged
  from S2.

### Document page: text rendering

Raw text in a single pre-wrap container (`#ew-doc-text`), exactly the S2
contract: offsets in JS string space (UTF-16) map 1:1 to the rendered text
node, which is what makes TOC jumps, chunking, and the Highlight API
composable. Rendering markdown as HTML would break offset addressing, add an
injection surface, and misrepresent machine-converted text as a facsimile;
v1's rich rendering below 200K chars is deliberately not ported (P15).
`window.__ewDoc.getRawText()` stays.

Only `offset_utf16` is ever consumed from `toc[]`; code-point `offset` fields
are never used in the client (the #86 asymmetry cannot bite).

### Document page: large documents (P17 replacement)

Three render modes by text length (UTF-16 units of the fetched string):

1. **Full render** (length <= 1M, 9,154 docs): one text node, TOC jumps via
   `Range` + `scrollIntoView` at `offset_utf16`.
2. **Chunked render** (length > 1M, 620 docs): the text splits into parts at
   TOC-entry boundaries. Greedy packing: accumulate consecutive TOC sections
   until the next section would push the part past 500K units; a single
   section longer than 500K is cut at the last newline before each 500K step.
   Text before the first TOC entry belongs to part 1. Docs with no TOC use
   fixed 500K cuts snapped forward to the next newline. UI: "Part k of n"
   with Prev/Next part buttons and a notice that the document is shown in
   parts; the TOC lists all entries and clicking one renders the part
   containing it, then scrolls to the exact offset. `#ew-doc-text` holds the
   current part's single text node; part boundaries are pure functions of
   (text length, toc), unit-testable without a browser.
3. **Click-gate** (bytes > 5 MB, 15 docs): unchanged from S2; after the click,
   the doc proceeds through mode 2 (all 15 exceed 1M units).

Chunking math lives in a new `lib/doc-view.ts` (pure, DOM-free, vitest-able):
part computation, offset-to-part lookup, search-match computation. The client
script consumes it.

### Document page: in-document search (P16)

- Input above the text region; literal substring, case-insensitive (v1
  semantics: Python `re.escape` + IGNORECASE). Implementation:
  `new RegExp(escapeRegExp(q), 'gi')` + `matchAll` over the raw string, so
  match indices are UTF-16 offsets on the original string (lowercasing the
  haystack is wrong: `toLowerCase()` can change string length, e.g. Turkish
  dotted I, which would shift every offset).
- Results: total match count; in chunked mode, per-part counts and the TOC
  gains per-section counts next to entries with hits ("Events of Default (12)").
- Highlighting: CSS Custom Highlight API (Baseline since June 2025), two named
  highlights (`ew-match`, `ew-match-current`) styled via `::highlight()` with
  theme tokens. Ranges are built only for the currently rendered part
  (bounded work), capped at 2,000 ranges per part with a visible "showing
  first 2,000 highlights in this part" note (v1 capped at 100 total).
- Match navigation: Prev/Next match buttons + "match i of N"; navigating to a
  match in another part renders that part first, then scrolls. Current match
  gets the distinct highlight.
- Feature detection: without `CSS.highlights`, counts and match navigation
  still work (scroll positioning via Range), only the paint is missing; a
  muted note says highlights need a newer browser.
- `q` restores from the URL after text load; on gated docs the search runs
  after the user clicks through the gate (the gate is a data-cost consent and
  a `q` param must not bypass it).
- Empty result copy mirrors v1: '"term" not found in this document.'

### format.ts additions

`sourceDisplay()`, the shown-range copy, chunk/part labels, search-count copy,
highlight-cap note, chunked-mode notice, browser-support note. All user-facing
credibility copy stays in `lib/format.ts` under the existing em-dash-free test
guard; new copy gets the same test treatment.

### Seams held (S2 contract)

- `lib/queries.ts` owns ALL SQL; client scripts contain zero SQL, zero fetch,
  zero URL assembly. `scripts/browse.ts` and `scripts/doc-text.ts` are
  replaced wholesale (their contract allows it), staying disposable.
- `lib/duck.ts` untouched (DOM-free, framework-agnostic).
- `DocText.astro` keeps `#ew-doc-text` as the single slice-addressable
  container and `window.__ewDoc.getRawText()`.
- MANIFEST-first fetching, version tokens, drift notices, visible error
  states: all unchanged.

### Error handling

Every new async path ends in a visible state, never a blank region (S2 rule):
search over a failed text load is disabled with the error shown; a TOC jump
that cannot resolve (offset beyond text, malformed entry) falls back to
rendering part 1 with a notice; URL params that fail validation are dropped
and the URL is rewritten to the cleaned state.

## Testing

- **Fixture first (issue #88, done early):** extend
  `scripts/make_fixture.py` with two clearly-synthetic shapes: a row with
  inflated `text_bytes` metadata (makes the gate branch reachable in tests)
  and a doc whose text contains an astral character before a TOC entry so
  `offset != offset_utf16` (a conflation bug then fails tests). Plus a small
  synthetic doc with a TOC suitable for part-boundary tests.
- **Unit (vitest):** doc-view part computation (TOC packing, oversized
  section cuts, no-TOC fallback, offset-to-part lookup), search match
  computation (case-insensitivity, astral offsets, regex escaping), URL state
  codec round-trip (encode/decode/unknown-value dropping), queries.ts WHERE
  builder for all filter combinations (including the high-income interplay
  rule), format.ts copy (em-dash guard extended to new strings).
- **Browser smoke (`scripts/smoke.mjs` extended):** filters change the table
  and the URL; back/forward restores state; doc page renders text, TOC jump
  works, search finds and navigates matches; chunked doc switches parts;
  gated doc shows the button. Run against the fixture snapshot in CI and the
  full snapshot locally.
- **Measurement:** `scripts/measure.mjs` re-run on the full snapshot build;
  Lighthouse on browse must be 90+ (S2 baseline 100 / CLS 0; the two
  commitments that produced it are explicitly held).
- **Parity:** side-by-side manual pass against the live Shiny app over the
  P1-P20 checklist, posted to TEA-903.

## Build and verification path

Full-snapshot build via `SNAPSHOT_DIR=../data/snapshot` (dev serves `/data`;
served builds use `scripts/serve-static.mjs`). Long builds run via nohup with
a Monitor on a file condition. CI keeps the fixture snapshot.

## Council spec gate disposition

(recorded after the gate runs)
