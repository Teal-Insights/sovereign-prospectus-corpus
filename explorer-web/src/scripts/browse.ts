// Browse client script. Disposable by contract: zero SQL, zero fetch calls,
// zero URL assembly in this file; lib modules own all of it. The URL is the
// single source of truth: interactions pushState then render; corrections
// (page clamp, invalid params) replaceState; popstate never writes history.
// The static shell paints first; DuckDB work starts after the load event
// (first Lighthouse commitment).

import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import { toCsv, type ExportRow } from '../lib/csv';
import { initDuckDB, registerDocumentsParquet, type DuckHandle } from '../lib/duck';
import {
  DRIFT_NOTICE,
  DROPPED_PARAM_NOTICE,
  EXPORT_TRUNCATED_NOTE,
  HI_OVERRIDE_HINT_COUNTRY,
  HI_OVERRIDE_HINT_INCOME,
  chipRemoveLabel,
  formatDate,
  orNA,
  sourceDisplay,
  sovereignBadge,
  statusLine,
} from '../lib/format';
import {
  buildExportSql,
  buildListSql,
  buildStatusCountsSql,
  highIncomeExclusionActive,
  runQuery,
  type BrowseFilters,
  type BrowseRow,
} from '../lib/queries';
import { fetchParquetBytes, loadManifest } from '../lib/snapshot-client';
import { decodeBrowseState, encodeBrowseState, type BrowseUrlState } from '../lib/url-state';
import { docPath } from '../lib/urls';
import { renderError, renderNotice, userMessageOf } from './dom';

const PAGE_SIZE = 50;
// Typing granularity: coalesce keystrokes before touching the URL/engine.
const SEARCH_DEBOUNCE_MS = 250;
const MAX_Q_LENGTH = 200;

function el<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing #${id}`);
  return found as T;
}

const notices = el<HTMLDivElement>('ew-browse-notices');
const status = el<HTMLParagraphElement>('ew-status');
const table = el<HTMLTableElement>('ew-table');
const tbody = el<HTMLTableSectionElement>('ew-rows');
const prev = el<HTMLButtonElement>('ew-prev');
const next = el<HTMLButtonElement>('ew-next');
const scopeToggle = el<HTMLInputElement>('ew-scope-toggle');
const hiToggle = el<HTMLInputElement>('ew-hi-toggle');
const hiHint = el<HTMLSpanElement>('ew-hi-hint');
const searchInput = el<HTMLInputElement>('ew-search-input');
const exportButton = el<HTMLButtonElement>('ew-export');
const form = el<HTMLFormElement>('ew-filters');

interface FilterGroup {
  stateKey: 'countries' | 'regions' | 'incomes' | 'sources';
  select: HTMLSelectElement;
  chips: HTMLUListElement;
}

const GROUPS: FilterGroup[] = (
  [
    ['countries', 'country'],
    ['regions', 'region'],
    ['incomes', 'income'],
    ['sources', 'source'],
  ] as const
).map(([stateKey, key]) => ({
  stateKey,
  select: el<HTMLSelectElement>(`ew-filter-${key}-select`),
  chips: el<HTMLUListElement>(`ew-filter-${key}-chips`),
}));

// Baked options are the validation universe for URL values (empty prompt
// values excluded).
function optionValues(select: HTMLSelectElement): string[] {
  return [...select.options].map((o) => o.value).filter((v) => v !== '');
}

function optionLabel(select: HTMLSelectElement, value: string): string {
  for (const o of select.options) if (o.value === value) return o.textContent ?? value;
  return value;
}

const known = {
  countries: optionValues(GROUPS[0].select),
  regions: optionValues(GROUPS[1].select),
  incomes: optionValues(GROUPS[2].select),
  sources: optionValues(GROUPS[3].select),
};

// ---- state (module eval runs pre-load: chips and toggles restore early) ----

let state: BrowseUrlState;
let ready = false;
let pendingPop = false;
let refreshGeneration = 0;
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let exportNotice: Element | null = null;
// Last known page count: guards a rapid double-click past the final page
// from pushing an entry the clamp then has to replace (duplicate history).
let lastPages = Number.POSITIVE_INFINITY;

function writeUrl(push: boolean): void {
  const qs = encodeBrowseState(location.search, state);
  if (qs === location.search.replace(/^\?/, '')) return; // skip no-op writes
  const target = qs ? `?${qs}` : location.pathname;
  try {
    if (push) history.pushState(null, '', target);
    else history.replaceState(null, '', target);
  } catch {
    // WebKit rate-limits history writes (100 per 10 s); the UI must survive.
  }
}

function setNav(button: HTMLButtonElement, disabled: boolean): void {
  button.hidden = false;
  button.setAttribute('aria-disabled', String(disabled));
}

function navDisabled(button: HTMLButtonElement): boolean {
  return button.getAttribute('aria-disabled') === 'true';
}

function applyStateToControls(): void {
  // Restore the search box from state (init and popstate). Skip the sync while a
  // search debounce is pending: a filter/toggle/chip change (its handler calls
  // this) must not overwrite keystrokes that have not yet been committed to
  // state.q, or the in-flight term is silently dropped. The pending timer then
  // commits the typed value on top of the new filter state.
  if (searchTimer === undefined && searchInput.value !== state.q) {
    searchInput.value = state.q;
  }
  for (const group of GROUPS) {
    const values = state[group.stateKey];
    group.chips.innerHTML = '';
    for (const value of values) {
      const li = document.createElement('li');
      li.className = 'ew-chip';
      const label = document.createElement('span');
      label.textContent = optionLabel(group.select, value);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = '×';
      remove.setAttribute('aria-label', chipRemoveLabel(optionLabel(group.select, value)));
      remove.addEventListener('click', () => removeChip(group, value));
      li.append(label, remove);
      group.chips.appendChild(li);
    }
    for (const option of group.select.options) {
      option.disabled = option.value !== '' && values.includes(option.value);
    }
    group.select.value = '';
  }
  scopeToggle.checked = state.includeNonSovereign;
  hiToggle.checked = state.includeHighIncome;
  const overriddenByIncome = state.incomes.length > 0;
  const overriddenByCountry = state.countries.length > 0;
  const overridden = overriddenByIncome || overriddenByCountry;
  // Disabling a focused control (possible via popstate) strands focus.
  if (overridden && document.activeElement === hiToggle) scopeToggle.focus();
  hiToggle.disabled = overridden;
  // aria-describedby only while the hint applies: a permanently wired
  // reference is read by AT even when the hint is visibility-hidden.
  if (overridden) hiToggle.setAttribute('aria-describedby', 'ew-hi-hint');
  else hiToggle.removeAttribute('aria-describedby');
  hiHint.textContent = overriddenByIncome
    ? HI_OVERRIDE_HINT_INCOME
    : overriddenByCountry
      ? HI_OVERRIDE_HINT_COUNTRY
      : '';
  hiHint.classList.toggle('ew-visible', overridden);
}

function removeChip(group: FilterGroup, value: string): void {
  const idx = state[group.stateKey].indexOf(value);
  state[group.stateKey] = state[group.stateKey].filter((v) => v !== value);
  state.page = 0;
  writeUrl(true);
  applyStateToControls();
  // Focus rule: next chip in the group, else the group's select (a removed
  // focused element must never strand focus on body).
  const remaining = [...group.chips.querySelectorAll('button')];
  const target = remaining[Math.min(idx, remaining.length - 1)];
  (target ?? group.select).focus();
  void refresh();
}

function toFilters(s: BrowseUrlState): BrowseFilters {
  return {
    countries: s.countries,
    regions: s.regions,
    incomes: s.incomes,
    sources: s.sources,
    includeNonSovereign: s.includeNonSovereign,
    includeHighIncome: s.includeHighIncome,
    page: s.page,
    pageSize: PAGE_SIZE,
    q: s.q,
  };
}

function renderRows(rows: BrowseRow[]): void {
  // A popstate re-render can remove a focused row link.
  if (tbody.contains(document.activeElement)) {
    el<HTMLDivElement>('ew-table-region').focus({ preventScroll: true });
  }
  tbody.innerHTML = '';
  for (const row of rows) {
    const tr = document.createElement('tr');
    const badge = sovereignBadge(row.is_sovereign);

    const dateTd = document.createElement('td');
    dateTd.className = 'ew-col-date';
    dateTd.textContent = formatDate(row.publication_date);
    const issuerTd = document.createElement('td');
    issuerTd.className = 'ew-col-issuer';
    const link = document.createElement('a');
    link.href = docPath(row.slug);
    link.textContent = orNA(row.display_name ?? row.issuer_name);
    issuerTd.appendChild(link);
    const countryTd = document.createElement('td');
    countryTd.className = 'ew-col-country';
    countryTd.textContent = orNA(row.country_name);
    const typeTd = document.createElement('td');
    typeTd.className = 'ew-col-type';
    typeTd.textContent = orNA(row.doc_type);
    const sourceTd = document.createElement('td');
    sourceTd.className = 'ew-col-source';
    sourceTd.textContent = sourceDisplay(row.source);
    const badgeTd = document.createElement('td');
    badgeTd.className = 'ew-col-status';
    const span = document.createElement('span');
    span.className = badge.cls;
    span.textContent = badge.label;
    badgeTd.appendChild(span);

    tr.append(dateTd, issuerTd, countryTd, typeTd, sourceTd, badgeTd);
    tbody.appendChild(tr);
  }
}

let handle: DuckHandle;
const metrics: EwBrowseMetrics = {
  bundleName: '',
  workerMs: 0,
  instantiateMs: 0,
  manifestMs: 0,
  parquetFetchMs: 0,
  registerMs: 0,
  firstQueryMs: 0,
  secondQueryMs: 0,
  rowsRendered: 0,
  totalToFirstRenderMs: 0,
};
window.__ewMetrics = metrics;
const tStart = performance.now();

const showError = (e: unknown, fallback: string): void => {
  renderError(notices, userMessageOf(e, fallback));
};

async function refresh(): Promise<void> {
  if (!ready) return;
  const generation = ++refreshGeneration;
  const filters = toFilters(state);
  try {
    const tQuery = performance.now();
    const [rows, countRows] = (await Promise.all([
      runQuery(handle.conn, buildListSql(filters)),
      runQuery(handle.conn, buildStatusCountsSql(filters)),
    ])) as [unknown, Record<string, unknown>[]] as [BrowseRow[], Record<string, unknown>[]];
    if (generation !== refreshGeneration) return; // stale response
    if (!metrics.secondQueryMs) metrics.secondQueryMs = performance.now() - tQuery;
    const counts = countRows[0] as {
      matching: number;
      hidden_scope: number;
      hidden_hi: number;
      included_hi_override: number;
    };
    const matching = Number(counts.matching);
    const pages = Math.max(1, Math.ceil(matching / PAGE_SIZE));
    lastPages = pages;

    // A shared link can point past the last page; correct via replaceState
    // (never a pushed entry: a clamp loop would trap the back button).
    if (state.page > pages - 1) {
      state.page = pages - 1;
      writeUrl(false);
      return refresh();
    }

    renderRows(rows);
    table.hidden = false;
    metrics.rowsRendered = rows.length;
    if (!metrics.totalToFirstRenderMs) metrics.totalToFirstRenderMs = performance.now() - tStart;

    // statusLine renders the zero case itself (EMPTY_STATE + the marginal
    // sentences): bypassing it here hid WHY a result set was empty.
    const offset = state.page * PAGE_SIZE;
    // Pinned mapping: inactive or zero marginals render no sentence.
    const hiddenScope =
      !state.includeNonSovereign && Number(counts.hidden_scope) > 0
        ? Number(counts.hidden_scope)
        : null;
    const hiddenHi =
      highIncomeExclusionActive(filters) && Number(counts.hidden_hi) > 0
        ? Number(counts.hidden_hi)
        : null;
    const includedHiByCountry =
      !state.includeHighIncome &&
      state.countries.length > 0 &&
      state.incomes.length === 0 &&
      Number(counts.included_hi_override) > 0
        ? Number(counts.included_hi_override)
        : null;
    status.textContent = statusLine({
      matching,
      shownFrom: offset + 1,
      shownTo: offset + rows.length,
      page: state.page + 1,
      pages,
      hiddenScope,
      hiddenHi,
      hiOverride: !state.includeHighIncome && state.incomes.includes('High income'),
      includedHiByCountry,
    });
    setNav(prev, state.page === 0);
    setNav(next, state.page >= pages - 1);
  } catch (e) {
    if (generation !== refreshGeneration) return;
    showError(e, 'Query failed.');
  }
}

// ---- wiring (module eval) ----

const decoded = decodeBrowseState(location.search, known);
state = decoded.state;
applyStateToControls();
if (decoded.droppedAny) {
  renderNotice(notices, DROPPED_PARAM_NOTICE);
  writeUrl(false);
}

form.addEventListener('submit', (e) => e.preventDefault());

for (const group of GROUPS) {
  group.select.addEventListener('change', () => {
    const value = group.select.value;
    if (!value || state[group.stateKey].includes(value)) return;
    state[group.stateKey] = [...state[group.stateKey], value];
    state.page = 0;
    writeUrl(true);
    applyStateToControls();
    void refresh();
  });
}

scopeToggle.addEventListener('change', () => {
  state.includeNonSovereign = scopeToggle.checked;
  state.page = 0;
  writeUrl(true);
  applyStateToControls();
  void refresh();
});

hiToggle.addEventListener('change', () => {
  state.includeHighIncome = hiToggle.checked;
  state.page = 0;
  writeUrl(true);
  applyStateToControls();
  void refresh();
});

// Search box: debounced, and the ONE control that writes history via
// replaceState (typing must not spam the back stack; matches the doc page's
// ?q= behavior). IME composition needs no special casing: the debounce
// coalesces the intermediate input events. applyStateToControls is not called
// here, so the input value is never reset mid-keystroke.
function commitSearchInput(): boolean {
  if (searchTimer !== undefined) clearTimeout(searchTimer);
  searchTimer = undefined;
  const nextQ = searchInput.value.trim().slice(0, MAX_Q_LENGTH);
  if (nextQ === state.q) return false;
  state.q = nextQ;
  state.page = 0;
  writeUrl(false);
  return true;
}

searchInput.addEventListener('input', () => {
  if (searchTimer !== undefined) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchTimer = undefined;
    if (!commitSearchInput()) return; // debounce collapsed to a no-op
    void refresh();
  }, SEARCH_DEBOUNCE_MS);
});

prev.addEventListener('click', () => {
  if (navDisabled(prev)) return;
  state.page = Math.max(0, state.page - 1);
  writeUrl(true);
  void refresh();
});

next.addEventListener('click', () => {
  if (navDisabled(next)) return;
  if (state.page + 1 > lastPages - 1) return; // stale aria-disabled double-click
  state.page += 1;
  writeUrl(true);
  void refresh();
});

exportButton.addEventListener('click', async () => {
  if (!ready) return;
  if (commitSearchInput()) void refresh();
  exportButton.disabled = true;
  exportNotice?.remove();
  exportNotice = null;
  try {
    const rows = (await runQuery(
      handle.conn,
      buildExportSql(toFilters(state))
    )) as unknown as ExportRow[];
    const result = toCsv(rows, location.origin);
    const snapshotDate = document.body.dataset.buildSnapshotDate;
    if (!snapshotDate) throw new Error('missing build snapshot date');

    const url = URL.createObjectURL(new Blob([result.csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `prospectus-explorer-export-${snapshotDate}.csv`;
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);

    if (result.truncated) {
      renderNotice(notices, EXPORT_TRUNCATED_NOTE);
      exportNotice = notices.lastElementChild;
      const renderedNotice = exportNotice;
      setTimeout(() => {
        renderedNotice?.remove();
        if (exportNotice === renderedNotice) exportNotice = null;
      }, 10_000);
    }
  } catch (e) {
    const exportError = document.createElement('div');
    notices.appendChild(exportError);
    renderError(exportError, userMessageOf(e, 'Export failed.'));
    exportNotice = exportError;
  } finally {
    exportButton.disabled = false;
  }
});

window.addEventListener('popstate', () => {
  // Renders initiated by popstate never PUSH history; a non-canonical entry
  // (unreachable via our own writes, defensive only) is corrected in place.
  const popDecoded = decodeBrowseState(location.search, known);
  state = popDecoded.state;
  applyStateToControls();
  if (popDecoded.droppedAny) writeUrl(false);
  if (!ready) {
    pendingPop = true;
    return;
  }
  void refresh();
});

async function main(): Promise<void> {
  try {
    const tManifest = performance.now();
    const manifest = await loadManifest(PUBLIC_DATA_BASE_URL);
    metrics.manifestMs = performance.now() - tManifest;

    const stamped = document.body.dataset.buildGeneratedAt;
    if (stamped && manifest.generated_at !== stamped) renderNotice(notices, DRIFT_NOTICE);

    status.textContent = 'Starting the query engine...';
    handle = await initDuckDB();
    metrics.bundleName = handle.bundleName;
    metrics.workerMs = handle.timings.workerMs;
    metrics.instantiateMs = handle.timings.instantiateMs;

    status.textContent = 'Fetching the document index...';
    const parquet = await fetchParquetBytes(PUBLIC_DATA_BASE_URL, manifest.generated_at);
    metrics.parquetFetchMs = parquet.fetchMs;

    const tRegister = performance.now();
    await registerDocumentsParquet(handle, parquet.bytes);
    metrics.registerMs = performance.now() - tRegister;
    const tFirst = performance.now();
    ready = true;
    exportButton.disabled = false;
    if (pendingPop) pendingPop = false; // state is already current; fall through
    await refresh();
    if (!metrics.firstQueryMs) metrics.firstQueryMs = performance.now() - tFirst;
  } catch (e) {
    const message = userMessageOf(e, 'Could not start the in-browser query engine.');
    // #ew-status is the live region: the failure must be announced, and the
    // filter controls must not sit there looking interactive while every
    // interaction silently no-ops.
    status.textContent = message;
    renderError(notices, message);
    for (const group of GROUPS) group.select.disabled = true;
    scopeToggle.disabled = true;
    hiToggle.disabled = true;
    searchInput.disabled = true;
  }
}

// Defer all data work until after first paint (Lighthouse commitment).
if (document.readyState === 'complete') {
  void main();
} else {
  window.addEventListener('load', () => void main());
}
