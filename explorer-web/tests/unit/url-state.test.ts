import { expect, it } from 'vitest';

import {
  decodeBrowseState,
  decodeDocQuery,
  encodeBrowseState,
  encodeDocQuery,
  type BrowseUrlState,
} from '../../src/lib/url-state';

const KNOWN = {
  countries: ['KEN', 'GHA', 'ARG'],
  regions: ['Sub-Saharan Africa', 'Unknown'],
  incomes: ['High income', 'Low income', 'Unknown'],
  sources: ['edgar', 'nsm'],
};

const EMPTY: BrowseUrlState = {
  countries: [],
  regions: [],
  incomes: [],
  sources: [],
  includeHighIncome: false,
  includeNonSovereign: false,
  page: 0,
  q: '',
};

it('decodes repeated keys, booleans, and 1-based page', () => {
  const { state, droppedAny } = decodeBrowseState(
    '?country=KEN&country=GHA&income=Low+income&hi=1&scope=all&page=3',
    KNOWN
  );
  expect(state).toEqual({
    countries: ['KEN', 'GHA'],
    regions: [],
    incomes: ['Low income'],
    sources: [],
    includeHighIncome: true,
    includeNonSovereign: true,
    page: 2,
    q: '',
  });
  expect(droppedAny).toBe(false);
});

it('drops unknown and empty values with a flag; duplicates dedupe silently', () => {
  const { state, droppedAny } = decodeBrowseState('?country=ZZ&country=KEN&region=', KNOWN);
  expect(state.countries).toEqual(['KEN']);
  expect(state.regions).toEqual([]);
  expect(droppedAny).toBe(true);
  const dup = decodeBrowseState('?country=KEN&country=KEN', KNOWN);
  expect(dup.state.countries).toEqual(['KEN']);
  expect(dup.droppedAny).toBe(false);
});

it('rejects non-canonical boolean values and bad pages', () => {
  expect(decodeBrowseState('?hi=0', KNOWN).droppedAny).toBe(true);
  expect(decodeBrowseState('?hi=0', KNOWN).state.includeHighIncome).toBe(false);
  expect(decodeBrowseState('?scope=none', KNOWN).droppedAny).toBe(true);
  expect(decodeBrowseState('?page=abc', KNOWN).state.page).toBe(0);
  expect(decodeBrowseState('?page=abc', KNOWN).droppedAny).toBe(true);
  expect(decodeBrowseState('?page=0', KNOWN).droppedAny).toBe(true);
});

it('round-trips state and preserves unknown params verbatim', () => {
  const state: BrowseUrlState = {
    ...EMPTY,
    countries: ['KEN', 'GHA'],
    incomes: ['High income'],
    includeHighIncome: true,
    page: 2,
  };
  const qs = encodeBrowseState('?utm=x&search=pari+passu', state);
  expect(qs).toContain('utm=x');
  expect(qs).toContain('search=pari+passu');
  expect(qs).toContain('page=3'); // 1-based in the URL
  const back = decodeBrowseState(`?${qs}`, KNOWN);
  expect(back.state).toEqual(state);
  expect(back.droppedAny).toBe(false);
});

it('omits defaults from the URL (page 1, toggles off, no filters)', () => {
  expect(encodeBrowseState('', EMPTY)).toBe('');
  expect(encodeBrowseState('?utm=x', EMPTY)).toBe('utm=x');
});

it('encode over its own canonical URL is a string no-op', () => {
  const state: BrowseUrlState = { ...EMPTY, countries: ['KEN'], page: 1 };
  const first = encodeBrowseState('?utm=x', state);
  const second = encodeBrowseState(`?${first}`, state);
  expect(second).toBe(first);
});

it('doc q codec round-trips and preserves unknowns', () => {
  const qs = encodeDocQuery('?v=123', 'pari passu');
  expect(qs).toContain('v=123');
  expect(decodeDocQuery(`?${qs}`)).toBe('pari passu');
  expect(encodeDocQuery(`?${qs}`, '')).toBe('v=123'); // empty q removes the key
  expect(decodeDocQuery('?v=1')).toBe('');
});

// ---- B2 additions (TEA-930): browse search term `q` ----

it('decodes and round-trips the browse q param, preserving unknowns', () => {
  const decoded = decodeBrowseState('?q=Philippines+2031&utm=x', KNOWN);
  expect(decoded.state.q).toBe('Philippines 2031');
  expect(decoded.droppedAny).toBe(false);
  const qs = encodeBrowseState('?utm=x', { ...EMPTY, q: 'Philippines 2031' });
  expect(qs).toContain('q=Philippines+2031');
  expect(qs).toContain('utm=x');
  expect(decodeBrowseState(`?${qs}`, KNOWN).state.q).toBe('Philippines 2031');
});

it('trims the decoded q and does not flag truncation as a dropped param', () => {
  const decoded = decodeBrowseState('?q=++spaced++', KNOWN);
  expect(decoded.state.q).toBe('spaced');
  const long = 'a'.repeat(250);
  const dl = decodeBrowseState(`?q=${long}`, KNOWN);
  expect(dl.state.q.length).toBe(200);
  expect(dl.droppedAny).toBe(false); // free text: silent truncation, no notice
});

it('omits q when empty and does not let a stale q survive clearing', () => {
  expect(encodeBrowseState('', EMPTY)).toBe('');
  expect(encodeBrowseState('?q=old', EMPTY)).toBe(''); // cleared search drops the key
  expect(encodeBrowseState('?utm=x&q=old', EMPTY)).toBe('utm=x');
});

it('encoding truncates q to 200 chars so the URL matches the decoded state', () => {
  const long = 'b'.repeat(250);
  const qs = encodeBrowseState('', { ...EMPTY, q: long });
  const back = decodeBrowseState(`?${qs}`, KNOWN);
  expect(back.state.q.length).toBe(200);
});
