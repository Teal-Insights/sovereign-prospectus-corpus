// Shared formatters and ALL user-facing data-credibility copy. Nothing in
// this file may contain an em-dash (guarded by tests); the null display
// token is 'n/a'.

export const WB_VINTAGE_NOTE =
  'World Bank FY2027 classification (July 2026); reflects current status, not status at filing date.';
export const PROVENANCE_NOTE =
  'Text is machine-converted (Docling markdown or extracted page text), not a facsimile of the filed PDF. Verify quotes against the original filing.';
export const NO_PAGE_ANCHORS_NOTE =
  'This text was converted from markdown and carries no page anchors; page citations must be checked against the original filing.';
export const NOSCRIPT_NOTE = 'Browsing requires JavaScript; document pages are static.';
export const DOC_NOSCRIPT_NOTE =
  'Loading the document text requires JavaScript; the metadata above is static.';
// Fires on any generated_at mismatch, in either direction (data host ahead
// of the build, or rolled back behind it).
export const DRIFT_NOTICE =
  'The data snapshot differs from the one this page was built from; listings and pre-rendered pages may disagree until the site rebuilds.';

export function formatDate(v: number | Date | string | null | undefined): string {
  if (v === null || v === undefined) return 'undated';
  if (typeof v === 'string') return v.slice(0, 10);
  const d = typeof v === 'number' ? new Date(v) : v;
  return d.toISOString().slice(0, 10);
}

// Decimal units so displayed sizes agree with the 5_000_000-byte click-gate.
export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return 'n/a';
  if (n < 1000) return `${n} B`;
  if (n < 1_000_000) return `${Math.round(n / 1000)} KB`;
  return `${(n / 1_000_000).toFixed(1)} MB`;
}

export function orNA(v: string | number | null | undefined): string {
  return v === null || v === undefined || v === '' ? 'n/a' : String(v);
}

export interface SovereignBadge {
  label: 'Sovereign' | 'Non-sovereign' | 'Unverified';
  cls: string;
}

export function sovereignBadge(v: boolean | null | undefined): SovereignBadge {
  if (v === true) return { label: 'Sovereign', cls: 'ew-badge ew-badge--sovereign' };
  if (v === false) return { label: 'Non-sovereign', cls: 'ew-badge ew-badge--nonsovereign' };
  return { label: 'Unverified', cls: 'ew-badge ew-badge--unverified' };
}

export function scopeToggleLabel(other: number): string {
  return `Include ${other.toLocaleString('en-US')} non-sovereign or unverified documents`;
}

export function loadGateLabel(textBytes: number): string {
  return `Load full text (${formatBytes(textBytes)})`;
}

export function citeAs(snapshotDate: string, slug: string): string {
  return `Cite as: Sovereign Prospectus Corpus snapshot ${snapshotDate}, ${slug}`;
}

// ---- S3 additions (TEA-903). Copy rules: no em-dashes; segment UI never
// says "Part" (prospectuses contain literal PART I/II headings). ----

const num = (n: number): string => n.toLocaleString('en-US');

export const SOURCE_DISPLAY_NAMES: Record<string, string> = {
  edgar: 'SEC EDGAR',
  nsm: 'FCA NSM',
  luxse: 'Luxembourg Stock Exchange',
  lse: 'London Stock Exchange',
  pdip: '#PublicDebtIsPublic',
};

export function sourceDisplay(key: string | null | undefined): string {
  if (key === null || key === undefined || key === '') return 'n/a';
  return SOURCE_DISPLAY_NAMES[key] ?? key;
}

export interface StatusLineArgs {
  matching: number;
  shownFrom: number;
  shownTo: number;
  page: number;
  pages: number;
  // null = the exclusion is inactive OR would add zero; sentence suppressed.
  hiddenScope: number | null;
  hiddenHi: number | null;
  includedHiByCountry: number | null;
  // true ONLY when 'High income' is among the selected incomes while the
  // include-high-income toggle is off (broader wording would assert
  // inclusion of documents the income filter itself excludes).
  hiOverride: boolean;
}

export function statusLine(a: StatusLineArgs): string {
  // Zero results keep the marginal sentences: "No documents match" with the
  // reason hidden would read as "not in the corpus" (council PR gate).
  let s =
    a.matching === 0
      ? EMPTY_STATE
      : `${num(a.matching)} documents match, newest first ` +
        `(showing ${num(a.shownFrom)} to ${num(a.shownTo)}). ` +
        `Page ${num(a.page)} of ${num(a.pages)}.`;
  if (a.hiddenScope !== null && a.hiddenScope > 0) {
    s += ` Including non-sovereign or unverified documents would add ${num(a.hiddenScope)}.`;
  }
  if (a.hiddenHi !== null && a.hiddenHi > 0) {
    s += ` Including high-income countries would add ${num(a.hiddenHi)}.`;
  }
  if (a.hiOverride) {
    s += ' High-income documents are included by the income filter.';
  }
  if (a.includedHiByCountry !== null && a.includedHiByCountry > 0) {
    s += ` Showing ${num(a.includedHiByCountry)} high-income documents because their countries are selected.`;
  }
  return s;
}

export const EMPTY_STATE = 'No documents match these filters. Remove a filter to widen the results.';

export function browseSubtitle(sovereign: number, related: number): string {
  return `Browse ${num(sovereign)} sovereign bond prospectuses and ${num(related)} related filings.`;
}

export function statsCaption(snapshotDate: string): string {
  return `Snapshot ${snapshotDate}. Counts cover the full corpus before filters.`;
}

export function filingLinkLabel(source: string | null | undefined): string {
  return source === 'pdip' ? 'Via PDIP archive' : 'Original filing';
}

export function segmentLabel(k: number, n: number, matchCount?: number | null): string {
  const base = `Segment ${num(k)} of ${num(n)}`;
  if (matchCount === undefined || matchCount === null) return base;
  const word = matchCount === 1 ? 'match' : 'matches';
  return `${base} (${num(matchCount)} ${word} in this segment)`;
}

export const SEGMENTS_NOTICE =
  'Large document: displayed in segments for performance. Segments are a display convenience, not document structure; do not cite segment numbers.';

export function matchCountCopy(total: number, capped: boolean, query: string): string {
  if (capped) return `${num(total)}+ matches for "${query}"; refine your search.`;
  const word = total === 1 ? 'match' : 'matches';
  return `${num(total)} ${word} for "${query}".`;
}

export function matchPositionLabel(i: number, n: number, capped: boolean): string {
  return `Match ${num(i)} of ${num(n)}${capped ? '+' : ''}`;
}

export function matchPositionCopy(i: number, n: number, capped: boolean, snippet: string): string {
  return `${matchPositionLabel(i, n, capped)}: ${snippet}`;
}

export const COUNTS_PAST_CAP_NOTE =
  'Per-section and per-segment counts are unavailable past 20,000 matches.';

export function absenceCopy(query: string): string {
  return `No exact matches for "${query}". Search is literal; machine-converted text can split phrases across line breaks.`;
}

export const MIN_QUERY_HINT = 'Enter at least 2 characters to search.';

export const DROPPED_PARAM_NOTICE =
  'A filter or page from this link is no longer valid and was removed.';

export const PAGES_NOT_DISPLAYED_NOTE =
  'This document has page-anchored text, but page boundaries are not displayed in this viewer; verify page citations against the original filing.';

export const HIGHLIGHT_SUPPORT_NOTE =
  'Match highlighting needs a newer browser; match counts and navigation still work.';

export const HI_OVERRIDE_HINT_INCOME = 'Overridden by the income filter selection.';
export const HI_OVERRIDE_HINT_COUNTRY = 'Overridden by the country selection.';

export const HI_TOGGLE_LABEL = 'Include high-income countries';

export function chipRemoveLabel(name: string): string {
  return `Remove ${name}`;
}

export function highlightCapNote(cap: number): string {
  return `Showing the first ${num(cap)} highlights in this segment.`;
}

// Rendered mode has no segments, so the cap note must not say "in this
// segment"; the cap is over the whole document (TEA-929).
export function highlightCapNoteWhole(cap: number): string {
  return `Showing the first ${num(cap)} highlights.`;
}

export const TOC_FILTER_PLACEHOLDER = 'Filter contents...';

export const FRONT_MATTER_LABEL = '(Front matter)';

export const NO_TOC_LABEL = 'No table of contents in this document.';

export function loadingText(bytes: number): string {
  return `Loading ${formatBytes(bytes)}...`;
}

export const TOC_JUMP_FALLBACK_NOTE =
  'That contents entry could not be located; showing the start of the document.';

// ---- B2 additions (TEA-930): find-the-document search on browse ----

export const SEARCH_LABEL = 'Search documents';
export const SEARCH_PLACEHOLDER = 'Issuer, title, or country...';

// ---- B8 additions (TEA-936): filtered table export ----

export const EXPORT_LABEL = 'Download CSV';
export const EXPORT_TRUNCATED_NOTE =
  'Export capped at 10,000 rows; narrow the filters for a complete set.';

// ---- B1 (TEA-929): rendered-mode view toggle ----

// The toggle label names the mode it switches TO, matching browser
// conventions (the button reads "View raw text" while formatted).
export const VIEW_RAW_LABEL = 'View raw text';
export const VIEW_FORMATTED_LABEL = 'View formatted text';

export function viewModeAnnouncement(formatted: boolean): string {
  return formatted ? 'Showing formatted text.' : 'Showing raw converted text.';
}
