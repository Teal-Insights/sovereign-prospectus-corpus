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
  });
  expect(droppedAny).toBe(false);
});

it('drops unknown values, empty values, and duplicates with a flag', () => {
  const { state, droppedAny } = decodeBrowseState('?country=ZZ&country=KEN&country=KEN&region=', KNOWN);
  expect(state.countries).toEqual(['KEN']);
  expect(state.regions).toEqual([]);
  expect(droppedAny).toBe(true);
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
