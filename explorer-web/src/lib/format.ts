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
export const DRIFT_NOTICE =
  'The data snapshot is newer than this page; listings may not match pre-rendered pages until the site rebuilds.';

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

export function scopeStatus(sovereign: number): string {
  return `Showing ${sovereign.toLocaleString('en-US')} sovereign documents.`;
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
