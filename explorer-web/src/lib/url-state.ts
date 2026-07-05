// Pure URL codec for browse state and the doc-page search term. The URL is
// the single source of truth for browse state; this module owns the param
// names. Unknown params PASS THROUGH VERBATIM on every write (a future
// SearchSlot or campaign param must survive filter interactions); only the
// values of the codec's own params are validated, and invalid values are
// dropped with a flag so the caller can show the removed-filter notice.

export interface BrowseUrlState {
  countries: string[];
  regions: string[];
  incomes: string[];
  sources: string[];
  includeHighIncome: boolean;
  includeNonSovereign: boolean;
  page: number; // 0-based internal; 1-based in the URL, omitted at page 1
}

export interface KnownOptions {
  countries: string[];
  regions: string[];
  incomes: string[];
  sources: string[];
}

const MULTI_KEYS = ['country', 'region', 'income', 'source'] as const;
const OWN_KEYS = [...MULTI_KEYS, 'hi', 'scope', 'page'] as const;

function readMulti(
  q: URLSearchParams,
  key: string,
  known: string[]
): { values: string[]; dropped: boolean } {
  const raw = q.getAll(key);
  const values: string[] = [];
  let dropped = false;
  for (const v of raw) {
    if (v === '' || !known.includes(v)) {
      dropped = true;
    } else if (!values.includes(v)) {
      values.push(v);
    }
    // duplicates dedupe silently: nothing was semantically removed, so the
    // removed-filter notice would overclaim (council PR gate)
  }
  return { values, dropped };
}

export function decodeBrowseState(
  search: string,
  known: KnownOptions
): { state: BrowseUrlState; droppedAny: boolean } {
  const q = new URLSearchParams(search);
  let droppedAny = false;

  const read = (key: string, options: string[]): string[] => {
    const { values, dropped } = readMulti(q, key, options);
    droppedAny ||= dropped;
    return values;
  };

  const countries = read('country', known.countries);
  const regions = read('region', known.regions);
  const incomes = read('income', known.incomes);
  const sources = read('source', known.sources);

  const hiRaw = q.get('hi');
  const includeHighIncome = hiRaw === '1';
  if (hiRaw !== null && hiRaw !== '1') droppedAny = true;

  const scopeRaw = q.get('scope');
  const includeNonSovereign = scopeRaw === 'all';
  if (scopeRaw !== null && scopeRaw !== 'all') droppedAny = true;

  let page = 0;
  const pageRaw = q.get('page');
  if (pageRaw !== null) {
    const n = Number(pageRaw);
    if (Number.isSafeInteger(n) && n >= 1) {
      page = n - 1;
    } else {
      droppedAny = true;
    }
  }

  return {
    state: { countries, regions, incomes, sources, includeHighIncome, includeNonSovereign, page },
    droppedAny,
  };
}

export function encodeBrowseState(currentSearch: string, state: BrowseUrlState): string {
  const q = new URLSearchParams(currentSearch);
  for (const key of OWN_KEYS) q.delete(key);
  for (const v of state.countries) q.append('country', v);
  for (const v of state.regions) q.append('region', v);
  for (const v of state.incomes) q.append('income', v);
  for (const v of state.sources) q.append('source', v);
  if (state.includeHighIncome) q.set('hi', '1');
  if (state.includeNonSovereign) q.set('scope', 'all');
  if (state.page > 0) q.set('page', String(state.page + 1));
  return q.toString();
}

export function decodeDocQuery(search: string): string {
  return new URLSearchParams(search).get('q') ?? '';
}

export function encodeDocQuery(currentSearch: string, qValue: string): string {
  const q = new URLSearchParams(currentSearch);
  if (qValue) {
    q.set('q', qValue);
  } else {
    q.delete('q');
  }
  return q.toString();
}
