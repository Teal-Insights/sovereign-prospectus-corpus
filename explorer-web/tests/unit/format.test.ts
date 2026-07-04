import { expect, it } from 'vitest';

import {
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
  expect(scopeToggleLabel(2393)).toBe('Include 2,393 non-sovereign or unverified documents');
});

it('load gate label', () => expect(loadGateLabel(29031849)).toBe('Load full text (29.0 MB)'));

it('pinned copy has no em-dash', () => {
  const all = [
    WB_VINTAGE_NOTE,
    PROVENANCE_NOTE,
    NO_PAGE_ANCHORS_NOTE,
    NOSCRIPT_NOTE,
    DRIFT_NOTICE,
    scopeStatus(1),
    scopeToggleLabel(1),
    loadGateLabel(1),
  ];
  for (const s of all) expect(s.includes('—')).toBe(false);
});

it('cite line', () =>
  expect(citeAs('2026-07-04', 'nsm-101126915')).toBe(
    'Cite as: Sovereign Prospectus Corpus snapshot 2026-07-04, nsm-101126915'
  ));
