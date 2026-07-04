# S3: Explorer core at Shiny-app parity with real URLs (TEA-903)

**Date:** 2026-07-04 (revised same day after the council spec gate; see Disposition)
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
  the architecture decision and neither candidate is foreclosed here. The
  in-document search controls use an `ew-doc-search-*` naming prefix;
  `ew-search-*` stays reserved for the slot.
- Hosting/deployment (TEA-906). Verification is against a locally served build.
- Theming beyond the neutral tokens (S4 re-themes).
- Rendering markdown as rich HTML (see "Text rendering" below for why raw
  pre-wrap text is load-bearing).
- Snapshot schema changes. #86 (pages[].offset_utf16) stays open; this design
  does not need pages[] at all. #84 (vintage into MANIFEST) stays open; the
  hardcoded FY2027 footnote remains the stopgap (code comment links #84; the
  vendored classifications roll every July, so switch to the MANIFEST value
  the moment it exists).

## Data facts that shaped the design (profiled 2026-07-04 snapshot; council-verified)

- 9,774 docs: 9,641 markdown-sourced, 30 pages-sourced, 103 no-text.
- Text scale: 3,308 docs over v1's 200K-char full-render threshold; 620 over
  1M chars; max 28.6M chars (29.0 MB, luxse-100387641); 15 docs over the 5 MB
  click-gate (all 15 exceed 1M units, so gated docs always proceed to
  segmented mode).
- Chunked cohort profile (the 620 docs over 1M units): TOC offsets are sorted,
  in-range, and duplicate-free across the whole cohort today (the part math
  is still defensive, see below); 12 have no TOC at all (the fixed-cut
  fallback is load-bearing); 30 contain a single TOC section over 500K units
  (max 16.3M, so the oversized-section cut path is load-bearing); 19 sit at
  the 2,000-entry TOC cap (the tail after the last entry is a cuttable
  section); max front matter before the first TOC entry is 56K units; max
  inter-newline span in large docs is ~30K, so newline snapping always finds
  a nearby cut; 14 of the 620 have `offset != offset_utf16` somewhere in
  their TOC (astral characters are reachable in production data, not
  theoretical).
- `toc[]` entries carry `offset` (code points) and `offset_utf16`; capped at
  2,000 entries per doc. `pages[]` carries code-point offsets only (issue
  #86) and is not consumed.
- Classifications: `income_group` and `region` are materialized with
  'Unknown' as a real value (215 docs); no NULLs today. 101 distinct country
  codes; region names contain "&" but no commas in this vintage. High income
  is 5,555 of 9,774 docs.
- Scope arithmetic: 7,381 sovereign docs; the sovereign + non-high-income
  default view is 3,990 docs (41% of corpus); the high-income default hides
  3,391 of 7,381 sovereign docs (46%). The status line must carry this
  honestly (see "Scope status copy").
- Corpus stats for the cards: 9,774 documents, 4 sources, 265 issuers
  (215 sovereign), computed at build time from the parquet.

## v1 parity inventory

This table is the parity checklist verified side by side against the live
Shiny app at the end of the build.

| # | v1 feature (shiny/app.py) | S3 treatment |
|---|---------------------------|--------------|
| P1 | Stats cards: Documents, Sources, Issuers | Build-time static HTML from parquet, captioned "Full corpus" (default view is a filtered subset) |
| P2 | "About this project" expander | Static `<details>` with v1 content. Attribution text links (Teal Insights, NatureFinance) stay; logo imagery, brand fonts, and brand palette do not (font licence; S4 re-themes) |
| P3 | Country filter (multi, searchable, sorted by name) | Native `<select>` ("Add country...") + removable chips; country_code values, country_name labels, name-sorted. Desktop search via native type-ahead; mobile gets native pickers. v1's selectize fuzzy search is deliberately traded for native reliability (see Disposition: datalist rejected) |
| P4 | Region filter (multi) | Same select+chips control, 'Unknown' included |
| P5 | Income group filter (multi) | Same select+chips control, 'Unknown' included |
| P6 | Source filter (multi, display names) | Same select+chips control; display names shown, source keys as values |
| P7 | "Include high-income countries" toggle, default off | Same checkbox, same default, same label; disabled with a visible hint when explicit income selections override it |
| P8 | Count line "N documents, newest first (showing X to Y)" | Scope-status copy matrix (see below): match count, shown range, and one sentence per active default exclusion, with live hidden-counts |
| P9 | Paginated table, 50/page, newest first | Kept from S2 (adds Country/Type/Status columns); order `publication_date DESC NULLS LAST, slug DESC` |
| P10 | Row click opens document | Real links to `/doc/<slug>/` (improvement: middle-click, share, back all work) |
| P11 | Prev/Next pagination | Kept from S2; page in URL (1-based in the URL, "Page k of n" matches it) |
| P12 | Detail metadata (source, date, type, country, region) | Kept from S2 (richer: adds income group, lending category, badge, cite-as) |
| P13 | "View original filing" link | Kept from S2 |
| P14 | Table of Contents expander | `<details>` (closed by default) rendered from `toc[]`; entries are real `<button>`s that jump (improvement: v1's list was inert); a filter input appears for TOCs over 100 entries; a synthetic "(Front matter)" row covers text before the first entry |
| P15 | Full text display | Raw pre-wrap text; v1 rendered markdown as HTML below 200K chars, a deliberate deviation (offset addressing, injection surface, facsimile honesty; the accessibility cost of losing heading navigation is accepted and recorded) |
| P16 | In-document search with highlighting and match count | CSS Custom Highlight API over the raw text; total count, per-part and per-section counts, prev/next match navigation; `q` in URL; min query length 2; whitespace-flexible and quote-tolerant literal matching (see Search) |
| P17 | Page-at-a-time fallback for large docs | Unreproducible (markdown docs have no page anchors); replaced by segment-by-TOC-offset (see "Large documents") |
| P18 | "Full text not yet available" for missing text | S2's no-text state kept (more honest: shows `no_text_reason`) |
| P19 | Source display names (SEC EDGAR, FCA NSM, Luxembourg Stock Exchange, #PublicDebtIsPublic) | `sourceDisplay()` added to `lib/format.ts`, used in table, filters, doc page |
| P20 | Teal branding (Inter/Playfair, teal palette, logos) | Explicitly NOT ported: neutral tokens only; S4 re-themes |
| P21 | "No documents match these filters." empty state | Same copy, in format.ts under the test guard |
| P22 | "Back to browse" affordance on doc page | Link to `/`, upgraded by script: same-origin referrer from browse triggers `history.back()` (restores filters and scroll via bfcache); direct entries navigate to `/` |

Improvements beyond parity (the rebuild's justification): filters in query
params, working back/forward (bfcache + popstate), instant client-side
filtering (25-35 ms steady-state queries), sensible mobile layout.

## Design

### Scoping model: two independent toggles

- **Sovereign scope** (S2 council credibility feature, kept): default
  sovereign-only, "Include N non-sovereign or unverified documents" toggle
  (N build-stamped into the static label; no post-load label swap), live
  counts in the status line, three-state badges.
- **High-income toggle** (v1 parity): "Include high-income countries",
  default off, i.e. default predicate `COALESCE(income_group, 'Unknown') !=
  'High income'` ('Unknown' passes, matching v1; the COALESCE guards a
  future snapshot regressing to NULLs, which would otherwise silently drop
  rows under the default).
- Interplay rule: when the income-group filter has explicit selections, the
  high-income exclusion clause is dropped (v1 ANDs both, so selecting "High
  income" with the toggle off silently yields zero rows). UI: the toggle is
  disabled with a visible hint ("overridden by the income filter") while
  income selections exist; its stored state and URL param ride along
  unchanged. The status line names the override (copy matrix below).

### Scope status copy (the denominator design)

One aggregate SQL statement (FILTER clauses, single round trip) returns, for
the currently active explicit filters: the matching count, the count
additionally hidden by sovereign scope, and the count additionally hidden by
the high-income exclusion. The status line composes from format.ts templates:

- Base: "N documents match, newest first (showing A to B). Page k of n."
- If sovereign scope hides rows: "Including non-sovereign or unverified
  documents would add M." (marginal semantics made explicit in the copy;
  the two hidden counts are marginals and deliberately do not sum to the
  total hidden by both toggles)
- If the high-income exclusion hides rows: "Including high-income countries
  would add H."
- Override sentence, rendered ONLY when 'High income' is among the selected
  incomes while the toggle is off (an income selection of only lower bands
  includes no high-income docs, so the earlier broader wording could assert
  a falsehood): "High-income documents are included by the income filter."
- Zero results: "No documents match these filters." (P21)

The browse subtitle is build-stamped and scope-honest: "Browse S sovereign
bond prospectuses and R related filings." (S and R from the parquet at build;
never "9,774 sovereign prospectuses", which the page's own badges would
contradict). The stats cards carry the caption "Full corpus."

The World Bank vintage footnote (`WB_VINTAGE_NOTE`) renders directly beneath
the filter row, adjacent to the income filter and the high-income toggle that
act on it (not below the table), because the toggle silently deletes rows by
FY2027 status applied to 1990-2026 filings.

### Filters and URL state

All browse state lives in query params; the URL is the single source of truth.

- Params: `country`, `region`, `income`, `source` as REPEATED keys
  (`?country=KE&country=GH`, read via `getAll`); comma-joining was rejected
  because World Bank taxonomies can carry commas in future vintages.
  `hi=1` (include high income), `scope=all` (include non-sovereign), `page`
  (1-based, omitted when 1). Doc page: `q` (search term).
- **Unknown params pass through verbatim on every URL write** (a future
  SearchSlot or analytics param must survive filter interactions); only the
  codec's own params are validated. Invalid values of known params are
  dropped with a visible notice ("a filter from this link is no longer valid
  and was removed") and the URL corrected via `replaceState`.
- **History discipline** (the popstate/pushState rules are load-bearing):
  - A discrete interaction (chip add/remove, toggle, page nav) writes the
    URL with `pushState` immediately, then renders FROM the URL through the
    same code path popstate uses.
  - Corrective rewrites (page clamp, invalid-param cleaning) always use
    `replaceState`; a shared `?page=99` link clamps without minting history
    entries (no back-button clamp loop).
  - Renders initiated by `popstate` never write history.
  - Pending debounced URL writes are cancelled on `popstate` and `pagehide`
    (a stale `q` must not stamp a restored entry).
  - A popstate arriving before DuckDB init completes queues one re-render.
  - No-op writes (URL unchanged) are skipped, and history calls are wrapped
    in try/catch (WebKit throws SecurityError past 100 history writes per
    10 seconds, verified in current WebKit source; it must not take the UI
    down). Typing in the doc search box debounces 250 ms into
    `replaceState`.
  - Deliberate consequence, recorded: each checkbox/chip interaction is one
    history entry; heavy filter fiddling means several Back presses (and
    Chrome caps session history around 50 entries). Accepted; coalescing
    was rejected as surprising.
- **Filter controls: one shared select+chips implementation, four instances.**
  A labeled native `<select>` whose first option is the prompt ("Add
  country..."); choosing an option appends a removable chip and resets the
  select; chips render before the select row. Chip remove buttons are real
  `<button>`s with accessible names ("Remove Kenya"). Options already chosen
  are disabled in the select. This replaces the earlier datalist and
  details-popover designs (Firefox for Android has no datalist at all;
  details-popovers need hand-rolled dismissal; native selects are fully
  keyboard- and SR-accessible with zero custom code and native mobile
  pickers). No Apply button; every change re-queries immediately.
- **Filter options are baked at build time** from the parquet (101 countries,
  8 regions, 5 income groups, 4 sources): the selects are complete static
  HTML before any JS runs, URL validation needs no await, and no
  late-arriving option list can shift layout. Runtime distinct-value queries
  are removed from the browse path. Snapshot drift between build options and
  the data host is covered by the existing drift notice.
- The `#ew-filters` form gets a `submit` preventDefault guard (a text input
  in a form triggers implicit GET submission on Enter, which would reload
  the page and destroy the DuckDB session).
- `lib/queries.ts` grows `BrowseFilters` (arrays for the four filters, the
  two booleans, page) plus the WHERE builder and the aggregate scope-counts
  statement; all SQL stays in that file.

### Browse page

- Stats cards (P1), About expander (P2), subtitle, filter option lists, and
  the scope-toggle label count are static build-time HTML via
  `lib/build-data.ts` aggregation over the parquet; zero CLS, LCP stays
  static.
- Chips restored from a shared URL render post-load; the chips container
  reserves one row of height (token) so the common case cannot shift layout.
  Multi-row chip restores from parameter-heavy links are accepted as minor
  CLS and Lighthouse is additionally run on a parameterized URL to keep the
  number honest.
- Table: Date, Issuer, Country, Type, Source, Status columns with source
  display names. Mobile (< 640px): Type and Source hidden via CSS; Date,
  Issuer, Country, Status stay (Status carries the credibility signal in
  scope=all links, so it is never the column that goes). The table region
  keeps `--ew-table-min-height` and gets `overflow-x: auto` as a safety
  rail.
- DuckDB init stays deferred past first paint (`window load`), unchanged
  from S2.

### Document page: text rendering

Raw text in a single pre-wrap container (`#ew-doc-text`), exactly the S2
contract: offsets in JS string space (UTF-16) map 1:1 to the rendered text
node, which is what makes TOC jumps, segmenting, and the Highlight API
composable. Rendering markdown as HTML would break offset addressing, add an
injection surface, and misrepresent machine-converted text as a facsimile;
v1's rich rendering below 200K chars is deliberately not ported (P15). The
container gets `overflow-wrap: anywhere` (long unbroken table rows and URLs
must not force page-wide horizontal scroll on mobile; wrapping does not
affect string offsets or Ranges) and a doc-text font-size token that steps up
slightly under 640px for readability.

Only `offset_utf16` is ever consumed from `toc[]`; code-point `offset` fields
are never used in the client (the #86 asymmetry cannot bite).

For pages-sourced docs (30), a note states that page boundaries exist in the
data but are not displayed in this viewer (v1 showed real page numbers for
these; S3 does not, and must not let users assume section positions are page
citations).

**The `window.__ewDoc` contract** (documented for S4/TEA-907):
- `getRawText()` returns the FULL raw string in every render mode (full or
  segmented) once text is loaded; `null` before load and behind an unclicked
  gate.
- `?q=` is the only supported deep-link integration point; `q` on a gated
  doc does NOT auto-load (the gate is data-cost consent), so search runs
  after the user clicks through.
- `#ew-doc-text` always contains exactly one text node whose content is the
  currently rendered slice; `data-` attributes carry the slice's UTF-16
  start offset.

### Document page: large documents (P17 replacement)

Three render modes by text length (UTF-16 units of the fetched string):

1. **Full render** (length <= 1M; 9,051 docs with text): one text node, TOC
   jumps scroll to the offset.
2. **Segmented render** (length > 1M, 620 docs): the text splits into
   segments at TOC-entry boundaries. Greedy packing: accumulate consecutive
   TOC sections until the next section would push the segment past 500K
   units; a single section longer than 500K is cut at the last newline
   before each 500K step; if a window contains no newline, hard-cut at the
   step but never between surrogate pair halves. Text before the first TOC
   entry belongs to segment 1. Docs with no TOC (12) use fixed 500K cuts
   snapped to the last newline before each cut point (backward snap keeps
   every segment bounded by the target; unified with the oversized-section
   rule at the plan gate). Segment computation is defensive:
   TOC offsets are sorted, deduplicated, and clamped; entries beyond text
   end are dropped.
   UI: "Segment k of n" with persistent Prev/Next segment buttons and a
   notice: segments are a display convenience for very large documents, not
   document structure, and must not be cited (many prospectuses contain
   literal "PART I/II" headings, so the word "Part" is avoided). The TOC
   lists all entries; clicking one renders the containing segment, then
   scrolls to the exact offset. The cite-as line stays segment-free.
3. **Click-gate** (bytes > 5 MB, 15 docs): unchanged from S2; after the
   click, the doc proceeds through mode 2.

Jump mechanism (mode 1 and 2): build a non-collapsed `Range` on the text
node at the target offset, `range.getBoundingClientRect()` +
`window.scrollTo` (`Range` has NO `scrollIntoView`; gBCR forces layout
synchronously, measured ~2 ms, so no rAF choreography is needed), then focus
`#ew-doc-text` (`tabindex="-1"`, `preventScroll: true`) so keyboard users
continue from the text.

Segment math and search-match math live in a new `lib/doc-view.ts` (pure,
DOM-free, vitest-able, thresholds passed as parameters). The client script
consumes it.

### Document page: in-document search (P16)

- Input above the text region (`ew-doc-search-*` ids). Matching: literal,
  case-insensitive, offset-exact, with two tolerance rules for
  machine-converted text: whitespace runs in the query match any whitespace
  run including newlines (`\s+`), and quotes/apostrophes match across
  straight and typographic forms in BOTH directions (symmetric classes; the
  likeliest user flow is copying a phrase out of the rendered document and
  pasting it into the search box). Implementation: build the
  pattern by escaping regex syntax, then substituting those two character
  classes; run with `matchAll`-equivalent exec loop over the raw string so
  match indices are UTF-16 offsets on the original string (lowercasing the
  haystack is wrong: `toLowerCase()` can change string length). This is a
  documented superset of v1's exact-literal semantics, serving the legal
  use case (phrases split across line breaks must still match).
- **Compute guards** (the caps live at the computation layer, not just
  rendering): minimum query length 2 (shorter shows a hint, runs nothing);
  empty/whitespace queries clear state; the exec loop stores bare number
  offsets (never match objects) and stops at a hard cap of 20,000 matches
  with honest copy ("20,000+ matches; refine your search"); a
  non-advancing-lastIndex guard prevents zero-length-match loops. Measured
  floor after guards: 16-30 ms per scan on the 28.6M-char worst case;
  main-thread with 250 ms debounce, no worker needed.
- Results: total match count; in segmented mode, the per-segment count
  rides in the segment label ("Segment 2 of 6 (14 matches in this
  segment)") and per-section TOC counts sit on TOC entries (binary search
  of stored offsets against boundaries; counts update in place, no list
  rebuild; "(Front matter)" owns pre-TOC matches so section counts always
  sum to the total). The total past the compute cap displays as "20,000+";
  per-section and per-segment counts are SUPPRESSED when capped (a
  truncated scan would show false zeros on later sections, which misleads
  exactly the operative-clauses-at-the-end lookup) with a note that counts
  are unavailable past the cap. Per-section TOC counts are the first
  feature overboard if schedule slips (recorded).
- A match straddling a segment boundary belongs to the segment containing
  its start; its highlight Range is clamped to the segment end.
- Highlighting: CSS Custom Highlight API (web-verified: Baseline newly
  available since June 2025; Chrome 105 / Safari 17.2 / Firefox 140), two
  named highlights (`ew-match`, `ew-match-current`) with explicit
  `Highlight.priority` so the current match wins overlap. The
  `::highlight()` rules live in `tokens.css` itself with literal fallback
  values (`var(--ew-color-match-bg, <literal>)`): web verification
  empirically confirmed current Chrome/Safari/Firefox all resolve `var()`
  from the originating element in highlight pseudos AND honor the literal
  fallback, while Chromium before 134 (March 2025) silently fails `var()`,
  which is exactly what the literal fallback covers. Styling uses only
  `background-color` and `color` (the interoperable subset: Firefox
  supported neither text-decoration nor text-shadow in highlights until
  146/149), so the current-match distinction is a strong lightness step of
  the two background tokens, not hue alone, and both pairs must pass 4.5:1
  against the text color. Ranges are built only for the currently rendered segment,
  capped at 2,000 per segment with a visible note; the CURRENT match is
  always painted regardless of the cap.
- Match navigation: Prev/Next buttons + "match i of N"; navigating to a
  match in another segment renders that segment first, then scrolls and
  focuses per the jump mechanism. Nav buttons at the ends use
  `aria-disabled` + no-op (never `disabled`, which drops keyboard focus to
  body); segment nav buttons are persistent DOM across re-renders.
- Feature detection: without `CSS.highlights`, the current match is painted
  by setting the window selection to its Range (native selection color;
  cleared by any tap, accepted), counts and navigation work unchanged, and
  a muted note recommends a newer browser BEFORE the user types.
- `q` restores from the URL after text load.
- Absence copy (soft, honest): 'No exact matches for "term". Search is
  literal; machine-converted text can split phrases across line breaks.'

### Accessibility (design-level commitments)

- **One polite live region per page.** Browse: the existing `#ew-status`.
  Doc page: a new live region announcing, on a ~500 ms idle debounce,
  search result counts ("N matches for 'term'"), match navigation ("Match i
  of N: ...40-char context snippet..."), segment changes ("Segment k of
  n"), and the absence copy. Updates replace text (no appended nodes).
  Custom Highlight paints are not RELIABLY exposed to assistive tech
  (web-verified: the spec says SHOULD, engines are inconsistent, and the
  default highlight type is effectively invisible to screen readers); the
  live region and the count/navigation UI ARE the accessible channel, and
  this limitation is recorded.
- **Focus rules for every dynamic mutation:** chip removal moves focus to
  the next chip, else back to that filter's select; TOC jumps and match/
  segment navigation focus `#ew-doc-text` (tabindex -1, preventScroll);
  end-of-range nav buttons use `aria-disabled`, never `disabled`; no
  focused element is ever removed or disabled without a specified focus
  destination. Recorded limitation: focusing the text container starts
  screen-reader reading at the container top; the announced context snippet
  is the SR affordance for match position.
- **Contrast:** a new `--ew-color-border-strong` token (>= 3:1 against
  white) borders all form controls (the existing `--ew-color-border` at
  1.38:1 stays for decorative rules like table row separators only). The
  two highlight background tokens pass 4.5:1 under `--ew-color-text`.
- **Target sizes:** interactive controls (chips, remove buttons, nav
  buttons, TOC entry buttons, checkbox rows) get min 24px height always and
  min 44px under 640px.
- **TOC usability:** `<details>` closed by default; entries are real
  buttons rendered via one DocumentFragment; a within-TOC filter input
  appears over 100 entries (2,000-entry TOCs are usable as searched
  structures, not scrolled ones).
- **Testing gate:** Lighthouse accessibility score asserted >= 95 on browse
  and one doc page; an axe pass wired into the smoke script; one manual
  keyboard+SR script in the parity pass (filter, open doc, search, navigate
  match, switch segment).

### format.ts additions

`sourceDisplay()`, the scope status matrix templates, shown-range and empty
state copy, segment labels and the segments notice, search count/cap/absence
copy, the min-length hint, the dropped-param notice, the pages-sourced note,
the browser-support note, chip/remove-button accessible-name templates. All
user-facing copy stays in `lib/format.ts` under the existing em-dash-free
test guard; new strings get the same treatment.

### Tokens added (S4 acceptance: tokens.css stays the complete inventory)

`--ew-color-border-strong`, `--ew-color-match-bg`, `--ew-color-match-text`,
`--ew-color-match-current-bg`, `--ew-color-match-current-text`,
`--ew-font-size-doc` (with its small-screen step-up defined beside it),
`--ew-filters-min-height`, `--ew-chips-min-height`, plus any spacing tokens
the chips need. The PR description lists every token added so S4 re-themes
by diffing one file.

### Seams held (S2 contract)

- `lib/queries.ts` owns ALL SQL; client scripts contain zero SQL, zero fetch,
  zero URL assembly. `scripts/browse.ts` and `scripts/doc-text.ts` are
  replaced wholesale (their contract allows it), staying disposable.
- `lib/duck.ts` untouched (DOM-free, framework-agnostic).
- `DocText.astro` keeps `#ew-doc-text` as the single slice-addressable
  container; the `__ewDoc` contract above is additive.
- MANIFEST-first fetching, version tokens, drift notices, visible error
  states: all unchanged.

### Error handling

Every new async path ends in a visible state, never a blank region (S2 rule):
search over a failed text load is disabled with the error shown; a TOC jump
that cannot resolve falls back to rendering segment 1 with a notice; invalid
known-param values are dropped with the visible notice and a `replaceState`
correction; segment computation over malformed TOC input (unsorted,
out-of-range, duplicate offsets) sanitizes rather than throws.

## Testing

- **Fixture first (issue #88, done early):** extend
  `scripts/make_fixture.py` with clearly-synthetic shapes: a row with
  inflated `text_bytes` metadata (makes the gate branch reachable), a doc
  whose text contains an astral character before a TOC entry so
  `offset != offset_utf16` (offset-conflation bugs fail tests), and a
  synthetic doc over 1M units (~1.05 MB, repetitive text with distinct
  section markers; compresses well in git and fits the 3 MB fixture cap)
  so segmented mode is REACHABLE in CI smoke, not just unit tests.
- **Unit (vitest):** doc-view segment computation (TOC packing, oversized
  section cuts, no-TOC fallback, no-newline hard cut with surrogate-pair
  safety, defensive sanitization, offset-to-segment lookup, front-matter
  attribution); search-match computation (case-insensitivity, whitespace
  and quote tolerance, astral offsets, regex escaping, compute cap,
  zero-length guard, boundary-straddling ownership); URL codec round-trip
  (repeated params, 1-based page, unknown-param PASS-THROUGH, invalid-value
  dropping, hi/income interplay encoding); queries.ts WHERE builder for all
  filter combinations including the interplay rule and the COALESCE guard;
  scope-counts SQL shape; format.ts copy (em-dash guard extended).
- **Browser smoke (`scripts/smoke.mjs` extended):** filters change the
  table and the URL; back/forward restores state including a clamped-page
  case (no clamp loop); unknown query param survives a filter interaction;
  doc page renders text, TOC jump works, search finds and navigates
  matches; segmented doc switches segments; gated doc shows the button; axe
  pass on browse and one doc page. Runs against the fixture snapshot in CI
  and the full snapshot locally.
- **Measurement:** `scripts/measure.mjs` re-run on the full snapshot build.
  Lighthouse performance >= 90 AND accessibility >= 95 on browse, measured
  on BOTH the bare URL and a parameterized URL (chips restored); the S2
  baseline is 100/CLS 0 and the two commitments that produced it are held.
- **Parity:** side-by-side manual pass against the live Shiny app over the
  P1-P22 checklist, posted to TEA-903, including one manual Firefox and
  Safari check of highlight painting (var() in ::highlight() interop).

## Build and verification path

Full-snapshot build via `SNAPSHOT_DIR=../data/snapshot` (dev serves `/data`;
served builds use `scripts/serve-static.mjs`). Long builds run via nohup with
a Monitor on a file condition. CI keeps the fixture snapshot.

## Council spec gate disposition (2026-07-04)

Six fresh-context reviewers (independent generalist, frontend/Astro,
sovereign-debt researcher, S4 wrapper builder, accessibility/mobile,
performance) + a web-verification pass on platform claims. Every data fact in
the draft was independently re-verified against the live parquet (all exact).
The architecture (segment-by-TOC-offset, Highlight API, URL-as-state, seam
discipline) survived all six reviews; findings concentrated in the browse
scoping copy, URL-write discipline, search compute limits, and the
interaction layer's accessibility.

**Adopted (and reflected above):**
- Researcher C1/C2 + generalist M1/m1: scope-honest subtitle, the status
  copy denominator matrix with live hidden-counts, "Full corpus" card
  caption, vintage note placed adjacent to the toggle it explains.
- Researcher M2 + generalist M2 + a11y m3: interplay override disables the
  toggle with a hint and is named in the status line; URL encoding pinned.
- Researcher M3: whitespace-flexible + quote-tolerant matching (offset-exact
  superset of v1), softened absence copy.
- Researcher M4: "Segment" naming (never "Part"), non-citable notice.
- Researcher m3/m4/m5/m6: pages-sourced note, front-matter row, current
  match always painted, dropped-param notice.
- Generalist M3: back-link behavior (P22). Generalist m2/m5/m6/m8/m9:
  replaceState for corrections, COALESCE guard, repeated URL params,
  corrected mode-1 population (9,051), empty-state copy (P21).
- Frontend M3/M4/M5 + perf C1/M3: full history-write discipline (push
  immediately, render from URL, popstate never writes, debounce
  cancellation on popstate/pagehide, no-op skip, try/catch for Safari's
  rate limit), search compute guards (min length 2, 20K hard cap,
  index-only storage, zero-length guard).
- Frontend M1 + a11y M1 + S4 Major 3: the datalist AND details-popover
  designs were REPLACED wholesale by one native select+chips control
  (Firefox Android has no datalist; popovers need hand-rolled dismissal;
  selects are native-accessible everywhere). This also mooted autofill,
  implicit-submit (guard kept anyway), and most native-chrome theming gaps.
- Frontend m1/m3/m4: straddling-match ownership + clamping, defensive
  segment computation with surrogate-pair-safe cuts, Highlight.priority.
- Frontend m8 + perf M2: filter options and count-bearing labels baked at
  build time; chips row reserved height; Lighthouse also on a
  parameterized URL.
- Frontend m9a: 1-based page param. Frontend m7 + generalist m4: committed
  synthetic >1M-unit fixture doc so CI smoke reaches segmented mode.
- Generalist m7 + perf M1: jump mechanism corrected to
  `getBoundingClientRect` + `scrollTo` (Range has no scrollIntoView).
- A11y C1/C2: live-region design (counts + context snippets as the SR
  channel), focus rules for every dynamic mutation, tabindex -1 focus
  handoff to the text container, recorded SR limitations.
- A11y M5/M6/M7/M8 + m2/m5: border-strong contrast token, overflow-wrap:
  anywhere + doc font step-up, Status column kept on mobile (Type/Source
  hidden instead), TOC closed/buttons/filter-input/target sizes, a11y
  testing gate (Lighthouse a11y + axe + manual SR script).
- A11y M4: selection-based fallback paint for the current match when
  CSS.highlights is absent, support note shown before typing.
- S4 Major 1: unknown-param pass-through with a unit test. S4 Major 2:
  ::highlight() rules live in tokens.css with literal var() fallbacks;
  background-color/color only. S4 Major 3: accent-color on checkboxes via
  the accent token, as progressive enhancement (web-verified: NOT Baseline;
  functional in Chrome/Firefox since 2021 but Safari honored it fully only
  from 26.2; older Safari falls back to default control rendering, which is
  acceptable because checkbox state never relies on the tint). S4 Minors:
  token inventory listed, About attribution boundary pinned (P2), __ewDoc
  contract block, ew-doc-search-* naming.
- Perf m2: TOC rendered once via fragment, counts updated in place.

**Rejected, with reasons:**
- Worker-offloaded or incremental search (perf considered): unnecessary
  after compute guards; measured 16-30 ms full-string scan floor.
- Whitespace-NORMALIZING search (researcher M3 alternative): breaks offset
  exactness; the flexible-pattern approach achieves the goal offset-exact.
- Build-time TOC pre-render for gated docs (ARCHITECTURE.md option;
  generalist m12): declined for S3; 15 docs, v1 parity does not require it,
  and the 2.46 GB build-time read stays avoided. Recorded as a deliberate
  choice.
- Coalesced history entries per popover-close (frontend m9e): surprising
  semantics; one interaction = one entry stands.
- Custom ARIA combobox for country search (a11y M1 option): heavy custom
  a11y surface vs native select+chips; the fuzzy-search loss is recorded in
  P3.
- 'u'-flag regex for astral case pairs (frontend, footnote): negligible for
  this corpus; escapeRegExp covers syntax safety.
- scrollRestoration 'manual' (frontend m9d): default 'auto' + reserved
  table height suffices; revisit only if smoke shows jumpiness.

**Deferred / tracked elsewhere:** #84 vintage-from-MANIFEST (tripwire
comment in code); #86 unconsumed; per-section TOC counts flagged as first
overboard on schedule risk (generalist m10); real low-end-device INP
spot-check noted as a nice-to-have beyond the Lighthouse gate (perf m1/m5).

**Plan-gate amendments (2026-07-04, same day):** the implementation-plan
council (5 fresh reviewers; disposition in the plan doc) fed four
refinements back into this spec: backward newline snapping unified for all
cuts; status-copy marginal wording ("would add N") and the override
sentence narrowed to explicit 'High income' selection; symmetric quote
tolerance; per-segment counts in the segment label with all per-section and
per-segment counts suppressed past the compute cap.

**Web-verification outcomes** (all against primary sources: MDN/BCD, CSSWG
drafts, WebKit source): Highlight API Baseline June 2025 CONFIRMED with
Firefox property caveats (text-decoration in highlights only from Fx146,
text-shadow from Fx149; the background-color/color restriction above is the
interoperable subset). var()-in-highlight: current engines all resolve it
and honor literal fallbacks (empirically tested); pre-134 Chromium needs
the fallback. accent-color Baseline claim REFUTED (Limited availability;
Safari partial until 26.2): downgraded to progressive enhancement.
WebKit history limit corrected to 100 writes per 10 seconds (was 30 s until
May 2023). AT exposure of highlights: "not reliably exposed", not "not
exposed at all". overflow-wrap: anywhere and popover Baseline claims
CONFIRMED.
