# B0 Design Audit Punch List (TEA-928)

**Date:** 2026-07-07. **Advisory only: no code was written.**
**Auditor:** fresh-context designer session (B0 per
`docs/superpowers/plans/2026-07-06-premonday-batch-plan.md`).

## Method

Walked the live site https://prospectus.tealinsights.com with headless
Playwright Chromium at exactly 1440x900 and 390x844. Two screens: the browse
page `/` and one document page with rendered text,
`/doc/edgar-0001193125-26-279169/` (Mexico 424B2, the most recent row in the
default table; text source `pages`, 95 KB, full text rendered). Interaction
probes: About box open, zero-result filter state (Austria + Low income),
in-document search for "interest" with Enter navigation, Contents open,
computed-style and fold measurements at both widths. 14 screenshots archived
to the session scratchpad, not the repo.

Lenses: (a) the seven ISO 9241-110 interaction principles, one pass per
principle over both screens, including the cold open ("someone WhatsApped me
this doc URL; does the page explain itself?"); (b) aesthetic: hierarchy, type
scale, spacing, page furniture, the `.ew-about` disclosure box, empty states.
Rubric source: `~/Dropbox/lte-workbench/docs/explainers/interface-design-for-small-data-tools.md`.
Brand values: `~/Code/prospectus-web-ti/brand/tokens.css`.

**LIC-DSF visual-advisor pattern: not found.** Searched
`~/Dropbox/lte-workbench/` for "visual advisor" (and variants); no such
document exists there. Proceeded without it, as the plan allows.

**Site health during the walk:** zero console errors, zero failed network
requests, both widths, all pages. No stop-and-report condition.

Note on scope: markdown-source docs render as plaintext on the live site
today (B1 is in flight), so P1 specs the rendered-mode typography B1's task 7
expects from this audit, and P2 covers the plaintext mode that `pages`-source
docs (most recent EDGAR filings) will keep permanently.

## ISO 9241-110 pass (both screens; findings reference punch items)

1. **Suitability for the task.** Browse: the filter-to-table path works and
   the columns are the right ones for the audience. Doc: the quote-and-verify
   path works (search, highlight, cite-as, original-filing link), but the
   reading surface starts at the very bottom edge of a 900px viewport behind
   a 12-row metadata wall (P6), and the text measure fights sustained reading
   (P1, P2).
2. **Self-descriptiveness.** Cold open verdict: the doc page explains itself
   well. Title, Sovereign badge, "Cite as" line, provenance table, and the
   machine-conversion notice with a link to the original filing are all
   present without scrolling. The gap is upstream of the page: the link
   unfurl itself is a bare title, because the head has no description and no
   Open Graph tags (P9).
3. **Conformity with user expectations.** Text inputs render as unstyled
   browser defaults (Arial, 2px inset border, 21px tall) while every button
   and select is styled; the search field on the doc page reads as broken
   (P3). The badge inside the doc h1 inherits the display serif and reads as
   a typo (P4). The select-to-chip filter pattern is nonstandard but
   discoverable and now common in data tools; sound.
4. **Learnability.** "Add country..." placeholders teach the chip pattern in
   one use; toggle labels carry their counts; match count plus Previous/Next
   appear on demand; the empty TOC is labeled ("No table of contents in this
   document."). Sound overall.
5. **Controllability.** Filter state round-trips through the URL
   (`?country=AUT&income=Low+income` observed), back/forward work, pagination
   is present. Gap: in a 31,000px-tall document the search controls and the
   match-position indicator scroll away; keyboard Enter still cycles, but
   mouse users lose Previous/Next and everyone loses the count (P7).
6. **Use-error robustness.** The zero-result state is honest ("No documents
   match these filters.") but is a dead end rendered as a floating header row
   over blank space; one sentence of recovery guidance is missing (P10). The
   large-document gate and per-chip removal are sound protections.
7. **User engagement.** The engagement gap is the aesthetic gap: page title
   at 24px equals the stat numbers (P5), fifty identical green pills per page
   (P4), a monospace wall at 133 characters per line (P1, P2), unstyled
   inputs (P3), and an About box whose lines run 130+ characters (P8). None
   of it is broken; all of it says research prototype rather than
   publication.

Aesthetic pass, additional: spacing is generally calm and generous (good
base); header and footer furniture are clean; date and source cells wrap
raggedly in the table and row heights alternate (P4); the World Bank vintage
note floats contextless between the form and the results (noted, no slot
spent; see WAIT).

## Punch items (10, sized S or M, each routed to exactly one branch)

### P1 (M, route: B1) Rendered-document reading typography

The centerpiece. `.ew-doc-rendered` gets a real reading design. Document
content speaks the body sans (Söhne via `--ew-font-body`), never Tiempos:
site chrome speaks the display face, filing content must not be confused
with product furniture. Document-internal headings sit BELOW the page h1
scale. Append to `explorer-web/src/styles/base.css` (B1 task 7 slot):

```css
.ew-doc-rendered {
  font-family: var(--ew-font-body);
  font-size: 1rem;
  line-height: 1.65;
  max-width: 72ch;
}
.ew-doc-rendered h1,
.ew-doc-rendered h2,
.ew-doc-rendered h3,
.ew-doc-rendered h4,
.ew-doc-rendered h5,
.ew-doc-rendered h6 {
  font-family: var(--ew-font-body);
  font-weight: 600;
  line-height: 1.3;
  margin: 2em 0 0.5em;
}
.ew-doc-rendered h1 { font-size: 1.375rem; }
.ew-doc-rendered h2 { font-size: 1.1875rem; }
.ew-doc-rendered h3 { font-size: 1.0625rem; }
.ew-doc-rendered h4,
.ew-doc-rendered h5,
.ew-doc-rendered h6 { font-size: 1rem; }
.ew-doc-rendered p,
.ew-doc-rendered ul,
.ew-doc-rendered ol { margin: 0 0 0.9em; }
.ew-doc-rendered table {
  display: block;
  overflow-x: auto;
  max-width: 100%;
  border-collapse: collapse;
  font-size: var(--ew-font-size-small);
  font-variant-numeric: tabular-nums;
  margin: var(--ew-space-3) 0;
}
.ew-doc-rendered th,
.ew-doc-rendered td {
  border: 1px solid var(--ew-color-border);
  padding: var(--ew-space-1) var(--ew-space-2);
  text-align: left;
  vertical-align: top;
}
.ew-doc-rendered th {
  background: var(--ew-color-surface);
  color: var(--ew-color-text);
  font-weight: 600;
}
.ew-doc-rendered blockquote {
  margin: 0 0 0.9em;
  padding-left: var(--ew-space-3);
  border-left: 3px solid var(--ew-color-border);
  color: var(--ew-color-text-muted);
}
.ew-doc-rendered hr {
  border: 0;
  border-top: 1px solid var(--ew-color-border);
  margin: var(--ew-space-4) 0;
}
```

This subsumes B1's written defaults (72ch, bordered padded cells) and adds
the type scale, line-height, spacing, and numeric tables the defaults left
to this audit. Highlight and offset machinery is unaffected: layout-only.

### P2 (S, route: B6, re-routed from B1 by architect: CSS-only, plain surface) Plaintext reading measure

`pages`-source documents (including the most recent EDGAR filings, like the
audited Mexico 424B2) never enter rendered mode; the plain view is their
permanent reading surface. Measured today: 133 characters per line at
1440x900, line-height 1.55. Amend the existing `#ew-doc-text` rule in
`explorer-web/src/styles/base.css` (B1 owns this file this week), adding two
properties, changing nothing else in the rule:

```css
#ew-doc-text {
  max-width: 80ch;
  line-height: 1.6;
}
```

`white-space: pre-wrap`, `overflow-wrap: anywhere`, the mono face, and the
offset contract are untouched; this is width and leading only. Mobile is
already narrower than 80ch; no media query needed.

### P3 (S, route: B6) Style text inputs like the rest of the control set

Evidence: `#ew-doc-search-input` computes to Arial 13.3px, 2px inset border,
176x21px, on a page where every button and select is token-styled. 21px is
also below the 24px target floor the site otherwise enforces. The TOC filter
input has the same problem, and B2's incoming `#ew-search-input` on browse
will inherit the fix by construction. Append to
`explorer-web/src/styles/base.css`:

```css
input[type='search'],
input[type='text'] {
  font: inherit;
  padding: var(--ew-space-1) var(--ew-space-2);
  border: 1px solid var(--ew-color-border-strong);
  border-radius: var(--ew-radius);
  background: var(--ew-color-bg);
  color: var(--ew-color-text);
  min-height: var(--ew-tap-target-min);
}
#ew-doc-search-input {
  width: min(28rem, 100%);
}
@media (max-width: 640px) {
  input[type='search'],
  input[type='text'] {
    min-height: var(--ew-tap-target);
  }
}
```

### P4 (S, route: B6) Browse table rhythm and badge calm-down

Evidence: "SEC EDGAR" wraps to two lines in every EDGAR row while NSM rows
stay on one, so row heights alternate down the page; dates wrap mid-string
("2026-" / "06-23") whenever an issuer name is long; all 50 default rows
carry an identical green "Sovereign" pill (pure noise; the exceptions are
what need flagging); the badge in the doc h1 inherits Tiempos. The `td`
cells already carry `ew-col-*` classes (set in `browse.ts`; no markup
change). Append to `explorer-web/src/styles/base.css`:

```css
.ew-col-date {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.ew-col-source {
  white-space: nowrap;
}
#ew-table th {
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
#ew-rows tr:hover td {
  background: var(--ew-color-surface);
}
.ew-badge {
  font-family: var(--ew-font-body);
  font-weight: 500;
}
#ew-rows .ew-badge--sovereign {
  background: transparent;
  color: var(--ew-color-text-muted);
  padding: 0;
}
```

Sovereign rows read as quiet muted text; Non-sovereign and Unverified keep
their pills everywhere and now actually stand out. The doc-page h1 badge
keeps its pill (single instance, informative) but drops the serif. The
nowrap rules are safe at phone width: `ew-col-source` is hidden at 640px
already, and the date column costs ~90px of 390. Weight 500 exercises the
already-declared soehne-kraftig face (currently loaded by nothing).

### P5 (S, route: B6) One more step of display scale

Evidence: h1 is 24px, identical to the stat values beside it; on an 1120px
content column the page reads flat, one type step above body. Change token
VALUES in BOTH files (brand parity rule):
`~/Code/prospectus-web-ti/brand/tokens.css` AND
`explorer-web/src/styles/tokens.css`:

```css
--ew-font-size-h1: 2rem;
--ew-font-size-h2: 1.375rem;
```

Both files already contain a `@media (max-width: 640px)` block (it holds
`--ew-font-size-doc`); add this line to that block in each file:

```css
--ew-font-size-h1: 1.625rem;
```

Plus one rule appended to `explorer-web/src/styles/base.css` so long
all-caps issuer titles wrap evenly at both widths:

```css
h1 {
  text-wrap: balance;
}
```

Doc h1 with the longest common issuer strings fits one line at 2rem/1120px;
verified against "UNITED MEXICAN STATES" and "MINISTRY OF FINANCE, THE
DEMOCRATIC REPUBLIC OF THE CONGO" (wraps to two balanced lines).

### P6 (S, route: B6) Compact the doc metadata block

Evidence: the metadata table is 406px tall and spans the full 1120px column,
so its hairline borders run edge to edge and the "Document text" heading
sits at y=673 with the text itself starting at y=883 on a 900px viewport.
Together with B3's removal of the "Pages: n/a" row this pulls the reading
surface up meaningfully. Append to `explorer-web/src/styles/base.css`:

```css
.ew-doc-meta {
  max-width: 48rem;
  font-size: var(--ew-font-size-small);
}
.ew-doc-meta th {
  white-space: nowrap;
}
```

(Cell padding already comes from the shared th/td rule; unchanged. The
long-URL cell keeps `overflow-wrap: anywhere` from S5.)

### P7 (M, route: B6) Sticky in-document search controls on desktop

Evidence: the walked doc renders 31,230px tall; after navigating a few
matches the search input, Previous/Next, and the match-position indicator
are thousands of pixels above the viewport. Keyboard Enter still cycles, but
the count and buttons are gone. Add to the `<style>` block of
`explorer-web/src/components/DocText.astro`:

```css
@media (min-width: 641px) {
  .ew-doc-search {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--ew-color-bg);
    padding: var(--ew-space-2) 0;
    border-bottom: 1px solid var(--ew-color-border);
  }
}
```

REQUIRED SECOND HALF: `--ew-jump-offset` (read at scroll time by
`doc-text.ts` `jumpOffsetPx()`) currently clears only the site header (80px).
With a sticky search bar, TOC jumps and match scrolls would land underneath
it. Re-measure in the branded build (header 54px + sticky bar height +
breathing room; expect roughly 150px) and update the token in BOTH
`~/Code/prospectus-web-ti/brand/tokens.css` and
`explorer-web/src/styles/tokens.css`, keeping each file's comment about
where the number comes from. Verify: TOC jump lands fully below the bar,
match navigation snippet visible, existing smoke jump scenarios green.
Desktop only by design: at 390x844 a sticky bar plus the phone keyboard
would eat the reading viewport. Known small caveat: the bar grows if the
search hint unhides; the offset should be measured with the count row
visible. This item is CSS plus a token re-measure; if it turns out to
require touching `doc-text.ts`, that is B6's stop-and-report, not a license
to edit logic.

### P8 (S, route: B6) About box shell

Evidence: opened, the box is a full-width text wall with 130+ character
lines; the summary row gives no affordance beyond the OS triangle. B3
replaces the COPY (verbatim in the batch plan); this item restyles the SHELL
only, in the `<style>` block of `explorer-web/src/pages/index.astro`:

```css
.ew-about {
  padding: var(--ew-space-3) var(--ew-space-4);
}
.ew-about > :not(summary) {
  max-width: 70ch;
}
.ew-about summary {
  color: var(--ew-color-accent);
}
.ew-about summary:hover {
  text-decoration: underline;
}
.ew-about[open] summary {
  margin-bottom: var(--ew-space-2);
}
```

(The existing `.ew-about` margin/border/background rules stay; the padding
declaration replaces the current one.)

### P9 (S, route: B6) Head metadata so shared links unfurl

Evidence from the live head: no `meta[name=description]`, no Open Graph
tags. A URL shared in a chat app unfurls as a bare title; this week the
expected distribution of the tool IS a shared link. In
`explorer-web/src/layouts/Base.astro`, add an optional prop
`description?: string` defaulting to the site description below, and render
in `<head>` after `<title>`:

```astro
<meta name="description" content={description} />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:site_name" content="Sovereign Prospectus Explorer" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary" />
```

Default description string, verbatim:
`An open, searchable corpus of sovereign bond prospectuses and related filings from the FCA NSM, SEC EDGAR, the Luxembourg Stock Exchange, and the #PublicDebtIsPublic dataset.`
Doc pages already pass distinct titles, so og:title differentiates per
document. Per-document descriptions and an og:image card are deliberately
NOT in scope (see WAIT).

### P10 (S, route: B3) Zero-result recovery copy

Evidence: the zero-result state renders the table header row floating over
blank space with the sentence "No documents match these filters." and no
recovery hint. The chips already provide the mechanics; the copy should
point at them. In `explorer-web/src/lib/format.ts` line 114, change the
constant (and update its assertion in `format.test.ts`; append to the
em-dash guard array if the file's convention requires each constant listed):

```ts
export const EMPTY_STATE =
  'No documents match these filters. Remove a filter to widen the results.';
```

## WAIT list (not in the 10; L-sized or owned by a later branch)

- **W1, issuer-name casing.** EDGAR issuers arrive ALL CAPS ("UNITED MEXICAN
  STATES") while NSM/PDIP rows are mixed case, so the table mixes shouting
  and prose. A display-layer title-case is NOT safe: naive rules produce
  errors like "D'ivoire", and a wrong sovereign name in front of this
  audience costs more than caps. Needs a data-side normalization with a
  reviewed mapping. L, post-Monday.
- **W2, social card image.** og:image needs a designed asset in the wrapper
  (brand fonts in a raster raise the licence question too). L, post-Monday.
- **W3, mobile pre-table chrome (for B7, recorded here so it is not lost).**
  At 390x844 the first data row sits at ~1170px: the reserved empty chip
  rows (`--ew-chips-min-height`) and `--ew-filters-min-height` insert ~200px
  of dead space between the four stacked selects, and the stats row wraps
  raggedly. Suggested mechanism, S-sized, inside B7's charter (which runs
  after B6 and owns phone width): media-query both reservation tokens to 0
  at 640px in both token files and tighten `.ew-stats` gap; accept the
  below-fold layout shift on deep-link restore as the cheaper evil on
  phones.
- **W4, status-line copy math.** The four-sentence number soup in
  `#ew-status` is issue #96 and explicitly out of this batch's scope beyond
  what M4 adds. Do not touch this week.
- **W5, table sorting and a page indicator beside the pager.** Both need
  `browse.ts` logic. Post-Monday.

## What I checked that came back sound

- Site health: the full walk (both widths, both screens, filters, search,
  TOC, pagination visible) produced zero console errors and zero failed
  requests; DuckDB-WASM booted and rendered rows every time.
- No horizontal page scroll at 390x844 on either screen
  (`scrollWidth === innerWidth === 390`); the S5 long-URL wrap fix holds in
  the metadata table; the table region scrolls within itself.
- Mobile column trimming works: Type and Source hidden at 390px.
- Tap targets: chip removers, pager, Previous/Next, and TOC buttons all
  carry the 24px/44px min-height rules. The one gap found is text inputs
  (P3).
- Accessibility structures: `aria-live` browse status announces counts; the
  doc page has an sr-only live region; `lang="en"` set; aria-disabled
  buttons keep focusability and look inert; favicon set present (ico, png,
  apple-touch).
- Provenance chain is complete and consistent: "Cite as" line, snapshot date
  in caption and footer, machine-conversion notice linking the original
  filing, World Bank vintage note with asterisk convention on the doc page.
- In-document search behaved: "70 matches for "interest".", amber highlight
  with a distinct current-match step, Enter navigation scrolled correctly.
- Empty states exist rather than blanks: zero-result sentence (improved by
  P10) and the labeled empty TOC ("No table of contents in this document.").
- Deep-link state: filter selections write to and restore from the URL.
- Licensed fonts load same-origin (Söhne 400/600, Tiempos Headline 600;
  Söhne 500 declared and available for P4); metric-tuned fallbacks declared.
- Contrast: all observed text pairs match the ratios recorded in the token
  comments; every punch item reuses existing tokens, introducing no new
  color pairs.
