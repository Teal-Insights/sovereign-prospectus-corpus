// Browse client script. Disposable by contract: zero SQL, zero fetch logic,
// zero URL assembly in this file; lib modules own all of it, so a future
// framework island can replace this without touching the data layer.
// The static shell paints first; all data work starts after load.

import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import { DRIFT_NOTICE, formatDate, orNA, scopeStatus, scopeToggleLabel, sovereignBadge } from '../lib/format';
import { initDuckDB, registerDocumentsParquet, type DuckHandle } from '../lib/duck';
import {
  buildCountSql,
  buildDistinctSql,
  buildListSql,
  buildScopeCountsSql,
  runQuery,
  type BrowseFilters,
  type BrowseRow,
} from '../lib/queries';
import { loadManifest } from '../lib/snapshot-client';
import { parquetUrl } from '../lib/urls';
import { renderError, renderNotice, userMessageOf } from './dom';

const PAGE_SIZE = 50;

interface UiState {
  country: string;
  source: string;
  includeNonSovereign: boolean;
  page: number;
}

function stateFromUrl(): UiState {
  const q = new URLSearchParams(location.search);
  return {
    country: q.get('country') ?? '',
    source: q.get('source') ?? '',
    includeNonSovereign: q.get('scope') === 'all',
    page: Math.max(0, Number(q.get('page') ?? 0) || 0),
  };
}

function stateToUrl(s: UiState): void {
  const q = new URLSearchParams();
  if (s.country) q.set('country', s.country);
  if (s.source) q.set('source', s.source);
  if (s.includeNonSovereign) q.set('scope', 'all');
  if (s.page > 0) q.set('page', String(s.page));
  const qs = q.toString();
  history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
}

function filtersOf(s: UiState): BrowseFilters {
  return {
    country: s.country || undefined,
    source: s.source || undefined,
    includeNonSovereign: s.includeNonSovereign,
    page: s.page,
    pageSize: PAGE_SIZE,
  };
}

function el<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing #${id}`);
  return found as T;
}

function fillSelect(select: HTMLSelectElement, values: string[], current: string): void {
  for (const v of values) {
    const option = document.createElement('option');
    option.value = v;
    option.textContent = v;
    if (v === current) option.selected = true;
    select.appendChild(option);
  }
  select.disabled = false;
}

function renderRows(tbody: HTMLTableSectionElement, rows: BrowseRow[]): void {
  tbody.innerHTML = '';
  for (const row of rows) {
    const tr = document.createElement('tr');
    const badge = sovereignBadge(row.is_sovereign);

    const dateTd = document.createElement('td');
    dateTd.textContent = formatDate(row.publication_date);
    const issuerTd = document.createElement('td');
    const link = document.createElement('a');
    link.href = `/doc/${row.slug}/`;
    link.textContent = orNA(row.display_name ?? row.issuer_name);
    issuerTd.appendChild(link);
    const countryTd = document.createElement('td');
    countryTd.textContent = orNA(row.country_name);
    const typeTd = document.createElement('td');
    typeTd.textContent = orNA(row.doc_type);
    const sourceTd = document.createElement('td');
    sourceTd.textContent = orNA(row.source);
    const badgeTd = document.createElement('td');
    const span = document.createElement('span');
    span.className = badge.cls;
    span.textContent = badge.label;
    badgeTd.appendChild(span);

    tr.append(dateTd, issuerTd, countryTd, typeTd, sourceTd, badgeTd);
    tbody.appendChild(tr);
  }
}

async function main(): Promise<void> {
  const status = el<HTMLParagraphElement>('ew-status');
  const tableRegion = el<HTMLDivElement>('ew-table-region');
  const table = el<HTMLTableElement>('ew-table');
  const tbody = el<HTMLTableSectionElement>('ew-rows');
  const notices = el<HTMLDivElement>('ew-browse-notices');
  const countrySelect = el<HTMLSelectElement>('ew-filter-country');
  const sourceSelect = el<HTMLSelectElement>('ew-filter-source');
  const scopeToggle = el<HTMLInputElement>('ew-scope-toggle');
  const scopeToggleText = el<HTMLSpanElement>('ew-scope-toggle-text');
  const prev = el<HTMLButtonElement>('ew-prev');
  const next = el<HTMLButtonElement>('ew-next');

  const state = stateFromUrl();
  const tStart = performance.now();

  let handle: DuckHandle;
  let sovereignCount = 0;
  let otherCount = 0;
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

  try {
    const tManifest = performance.now();
    const manifest = await loadManifest(PUBLIC_DATA_BASE_URL, fetch);
    metrics.manifestMs = performance.now() - tManifest;

    const stamped = document.body.dataset.buildGeneratedAt;
    if (stamped && manifest.generated_at !== stamped) renderNotice(notices, DRIFT_NOTICE);

    status.textContent = 'Starting the query engine...';
    handle = await initDuckDB();
    metrics.bundleName = handle.bundleName;
    metrics.workerMs = handle.timings.workerMs;
    metrics.instantiateMs = handle.timings.instantiateMs;

    status.textContent = 'Fetching the document index...';
    const tFetch = performance.now();
    const res = await fetch(parquetUrl(PUBLIC_DATA_BASE_URL, manifest.generated_at));
    if (!res.ok) throw new Error(`parquet fetch HTTP ${res.status}`);
    const bytes = new Uint8Array(await res.arrayBuffer());
    metrics.parquetFetchMs = performance.now() - tFetch;

    const tRegister = performance.now();
    await registerDocumentsParquet(handle, bytes);
    metrics.registerMs = performance.now() - tRegister;

    // First query: scope counts (also the engine warm-up; measured apart
    // from the second, steady-state query).
    const tFirst = performance.now();
    const scopeRows = await runQuery(handle.conn, buildScopeCountsSql());
    metrics.firstQueryMs = performance.now() - tFirst;
    const scope = scopeRows[0] as { total: number; sovereign: number };
    sovereignCount = Number(scope.sovereign);
    otherCount = Number(scope.total) - sovereignCount;
  } catch (e) {
    status.textContent = '';
    renderError(tableRegion, userMessageOf(e, 'Could not start the in-browser query engine.'));
    return;
  }

  scopeToggleText.textContent = scopeToggleLabel(otherCount);
  scopeToggle.checked = state.includeNonSovereign;
  scopeToggle.disabled = false;

  async function refresh(): Promise<void> {
    try {
      const filters = filtersOf(state);
      const tQuery = performance.now();
      const rows = (await runQuery(handle.conn, buildListSql(filters))) as unknown as BrowseRow[];
      const countRows = await runQuery(handle.conn, buildCountSql(filters));
      if (!metrics.secondQueryMs) metrics.secondQueryMs = performance.now() - tQuery;
      const total = Number((countRows[0] as { n: number }).n);

      renderRows(tbody, rows);
      table.hidden = false;
      metrics.rowsRendered = rows.length;
      if (!metrics.totalToFirstRenderMs) metrics.totalToFirstRenderMs = performance.now() - tStart;

      const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      const scopeText = state.includeNonSovereign ? `Showing ${total.toLocaleString('en-US')} documents.` : scopeStatus(sovereignCount);
      const filterText = total !== (state.includeNonSovereign ? sovereignCount + otherCount : sovereignCount)
        ? ` ${total.toLocaleString('en-US')} match the current filters.`
        : '';
      status.textContent = `${scopeText}${filterText} Page ${state.page + 1} of ${pages.toLocaleString('en-US')}.`;
      prev.hidden = next.hidden = false;
      prev.disabled = state.page === 0;
      next.disabled = state.page >= pages - 1;
      stateToUrl(state);
    } catch (e) {
      renderError(tableRegion, userMessageOf(e, 'Query failed.'));
    }
  }

  try {
    const [countries, sources] = await Promise.all([
      runQuery(handle.conn, buildDistinctSql('country_name')),
      runQuery(handle.conn, buildDistinctSql('source')),
    ]);
    fillSelect(countrySelect, countries.map((r) => String(r.v)), state.country);
    fillSelect(sourceSelect, sources.map((r) => String(r.v)), state.source);
  } catch (e) {
    renderNotice(notices, userMessageOf(e, 'Filter values failed to load.'));
  }

  countrySelect.addEventListener('change', () => {
    state.country = countrySelect.value;
    state.page = 0;
    void refresh();
  });
  sourceSelect.addEventListener('change', () => {
    state.source = sourceSelect.value;
    state.page = 0;
    void refresh();
  });
  scopeToggle.addEventListener('change', () => {
    state.includeNonSovereign = scopeToggle.checked;
    state.page = 0;
    void refresh();
  });
  prev.addEventListener('click', () => {
    state.page = Math.max(0, state.page - 1);
    void refresh();
  });
  next.addEventListener('click', () => {
    state.page += 1;
    void refresh();
  });

  await refresh();
}

// Defer all data work until after first paint (static shell renders first;
// S3 inherits a Lighthouse 90+ target).
if (document.readyState === 'complete') {
  void main();
} else {
  window.addEventListener('load', () => void main());
}
