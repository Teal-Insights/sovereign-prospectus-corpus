import { expect, it } from 'vitest';

import {
  DOC_NOSCRIPT_NOTE,
  DRIFT_NOTICE,
  NO_PAGE_ANCHORS_NOTE,
  NOSCRIPT_NOTE,
  PROVENANCE_NOTE,
  WB_VINTAGE_NOTE,
  citeAs,
  formatBytes,
  formatDate,
  loadGateLabel,
  orNA,
  scopeToggleLabel,
  sovereignBadge,
} from '../../src/lib/format';

it('formats epoch-ms (Arrow Date32) in UTC', () => expect(formatDate(1786752000000)).toBe('2026-08-15'));
it('formats JS Date (hyparquet) in UTC', () =>
  expect(formatDate(new Date('2002-11-27T00:00:00Z'))).toBe('2002-11-27'));
it('passes through ISO strings', () => expect(formatDate('2002-11-27')).toBe('2002-11-27'));
it('renders null date as undated', () => expect(formatDate(null)).toBe('undated'));

it('formats bytes in decimal units (agrees with the 5 MB gate)', () => {
  expect(formatBytes(41588)).toBe('42 KB');
  expect(formatBytes(29031849)).toBe('29.0 MB');
  expect(formatBytes(null)).toBe('n/a');
});

it('orNA', () => {
  expect(orNA(null)).toBe('n/a');
  expect(orNA('424B5')).toBe('424B5');
  expect(orNA(18)).toBe('18');
});

it('three-state badge', () => {
  expect(sovereignBadge(true).label).toBe('Sovereign');
  expect(sovereignBadge(false).label).toBe('Non-sovereign');
  expect(sovereignBadge(null).label).toBe('Unverified');
});

it('load gate label', () => expect(loadGateLabel(29031849)).toBe('Load full text (29.0 MB)'));

it('pinned copy has no em-dash', () => {
  const all = [
    WB_VINTAGE_NOTE,
    PROVENANCE_NOTE,
    NO_PAGE_ANCHORS_NOTE,
    NOSCRIPT_NOTE,
    DOC_NOSCRIPT_NOTE,
    DRIFT_NOTICE,
    scopeToggleLabel(1),
    loadGateLabel(1),
  ];
  for (const s of all) expect(s.includes('—')).toBe(false);
});

it('cite line', () =>
  expect(citeAs('2026-07-04', 'nsm-101126915')).toBe(
    'Cite as: Sovereign Prospectus Corpus snapshot 2026-07-04, nsm-101126915'
  ));

// ---- S3 additions (TEA-903) ----
import * as fmt from '../../src/lib/format';
import {
  DROPPED_PARAM_NOTICE,
  EMPTY_STATE,
  FRONT_MATTER_LABEL,
  HI_OVERRIDE_HINT,
  HI_TOGGLE_LABEL,
  MIN_QUERY_HINT,
  SEGMENTS_NOTICE,
  STATS_CAPTION,
  absenceCopy,
  browseSubtitle,
  chipRemoveLabel,
  highlightCapNote,
  matchCountCopy,
  matchPositionCopy,
  segmentLabel,
  sourceDisplay,
  statusLine,
} from '../../src/lib/format';

const BASE_ARGS = {
  matching: 3990,
  shownFrom: 1,
  shownTo: 50,
  page: 1,
  pages: 80,
  hiddenScope: null,
  hiddenHi: null,
  hiOverride: false,
};

it('status line base form', () => {
  expect(statusLine(BASE_ARGS)).toBe(
    '3,990 documents match, newest first (showing 1 to 50). Page 1 of 80.'
  );
});

it('status line appends marginal hidden sentences', () => {
  expect(statusLine({ ...BASE_ARGS, hiddenScope: 229 })).toBe(
    '3,990 documents match, newest first (showing 1 to 50). Page 1 of 80. ' +
      'Including non-sovereign or unverified documents would add 229.'
  );
  expect(statusLine({ ...BASE_ARGS, hiddenHi: 3391 })).toContain(
    'Including high-income countries would add 3,391.'
  );
  const both = statusLine({ ...BASE_ARGS, hiddenScope: 229, hiddenHi: 3391 });
  expect(both).toContain('would add 229.');
  expect(both).toContain('would add 3,391.');
});

it('status line renders the override sentence only when flagged', () => {
  expect(statusLine({ ...BASE_ARGS, hiOverride: true })).toContain(
    'High-income documents are included by the income filter.'
  );
  expect(statusLine(BASE_ARGS)).not.toContain('income filter');
});

it('status line suppresses null hidden counts (zero maps to null upstream)', () => {
  expect(statusLine(BASE_ARGS)).not.toContain('would add');
});

it('empty state pinned', () => expect(EMPTY_STATE).toBe('No documents match these filters.'));

it('subtitle is scope-honest with both build-stamped numbers', () => {
  expect(browseSubtitle(7381, 2393)).toBe(
    'Browse 7,381 sovereign bond prospectuses and 2,393 related filings.'
  );
});

it('stats caption pinned', () => expect(STATS_CAPTION).toBe('Full corpus.'));

it('source display names', () => {
  expect(sourceDisplay('edgar')).toBe('SEC EDGAR');
  expect(sourceDisplay('nsm')).toBe('FCA NSM');
  expect(sourceDisplay('luxse')).toBe('Luxembourg Stock Exchange');
  expect(sourceDisplay('pdip')).toBe('#PublicDebtIsPublic');
  expect(sourceDisplay('synthetic')).toBe('synthetic');
  expect(sourceDisplay(null)).toBe('n/a');
});

it('segment label with and without an active search count', () => {
  expect(segmentLabel(2, 6)).toBe('Segment 2 of 6');
  expect(segmentLabel(2, 6, 14)).toBe('Segment 2 of 6 (14 matches in this segment)');
  expect(segmentLabel(2, 6, 1)).toBe('Segment 2 of 6 (1 match in this segment)');
  expect(segmentLabel(2, 6, null)).toBe('Segment 2 of 6');
});

it('match count copy, capped and uncapped', () => {
  expect(matchCountCopy(128, false, 'pari passu')).toBe('128 matches for "pari passu".');
  expect(matchCountCopy(1, false, 'x')).toBe('1 match for "x".');
  expect(matchCountCopy(20000, true, 'the')).toBe(
    '20,000+ matches for "the"; refine your search.'
  );
});

it('match position copy carries the cap', () => {
  expect(matchPositionCopy(3, 128, false, '...rank pari passu with...')).toBe(
    'Match 3 of 128: ...rank pari passu with...'
  );
  expect(matchPositionCopy(3, 20000, true, 's')).toBe('Match 3 of 20,000+: s');
});

it('absence copy pinned', () => {
  expect(absenceCopy('cross default')).toBe(
    'No exact matches for "cross default". Search is literal; machine-converted text can split phrases across line breaks.'
  );
});

it('assorted S3 strings pinned', () => {
  expect(MIN_QUERY_HINT).toBe('Enter at least 2 characters to search.');
  expect(DROPPED_PARAM_NOTICE).toBe('A filter or page from this link is no longer valid and was removed.');
  expect(HI_OVERRIDE_HINT).toBe('Overridden by the income filter selection.');
  expect(HI_TOGGLE_LABEL).toBe('Include high-income countries');
  expect(FRONT_MATTER_LABEL).toBe('(Front matter)');
  expect(chipRemoveLabel('Kenya')).toBe('Remove Kenya');
  expect(highlightCapNote(2000)).toBe('Showing the first 2,000 highlights in this segment.');
  expect(SEGMENTS_NOTICE.toLowerCase()).toContain('do not cite');
});

it('every exported string and exercised output is em-dash-free and never says Part', () => {
  const outputs: string[] = Object.values(fmt).filter((v): v is string => typeof v === 'string');
  outputs.push(
    statusLine({ ...BASE_ARGS, hiddenScope: 1, hiddenHi: 1, hiOverride: true }),
    browseSubtitle(1, 1),
    sourceDisplay('edgar'),
    segmentLabel(1, 2, 3),
    matchCountCopy(5, false, 'q'),
    matchCountCopy(20000, true, 'q'),
    matchPositionCopy(1, 2, true, 'snip'),
    absenceCopy('q'),
    chipRemoveLabel('Kenya'),
    highlightCapNote(2000)
  );
  for (const s of outputs) {
    expect(s.includes('—')).toBe(false);
    expect(s.includes('–')).toBe(false);
    expect(/\bPart\b/.test(s)).toBe(false);
  }
});
