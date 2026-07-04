import { expect, it } from 'vitest';

import {
  DOC_NOSCRIPT_NOTE,
  DRIFT_NOTICE,
  NO_PAGE_ANCHORS_NOTE,
  NOSCRIPT_NOTE,
  PROVENANCE_NOTE,
  WB_VINTAGE_NOTE,
  citeAs,
  filteredStatus,
  formatBytes,
  formatDate,
  loadGateLabel,
  orNA,
  scopeAllStatus,
  scopeStatus,
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

it('scope copy pinned', () => {
  expect(scopeStatus(7381)).toBe('Showing 7,381 sovereign documents.');
  expect(scopeAllStatus(9774)).toBe('Showing 9,774 documents.');
  expect(scopeToggleLabel(2393)).toBe('Include 2,393 non-sovereign or unverified documents');
});

it('filtered status never claims to show more than the filter allows', () => {
  expect(filteredStatus(155, 7381, true)).toBe('155 of 7,381 sovereign documents match the current filters.');
  expect(filteredStatus(160, 9774, false)).toBe('160 of 9,774 documents match the current filters.');
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
    scopeStatus(1),
    scopeAllStatus(1),
    filteredStatus(1, 2, true),
    scopeToggleLabel(1),
    loadGateLabel(1),
  ];
  for (const s of all) expect(s.includes('—')).toBe(false);
});

it('cite line', () =>
  expect(citeAs('2026-07-04', 'nsm-101126915')).toBe(
    'Cite as: Sovereign Prospectus Corpus snapshot 2026-07-04, nsm-101126915'
  ));
