// Browse client script. Disposable by contract: zero SQL, zero fetch calls,
// zero URL assembly in this file; lib modules own all of it, so a future
// framework island can replace this without touching the data layer.
// The static shell paints first; all data work starts after load.

import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import {
  DRIFT_NOTICE,
  filteredStatus,
  formatDate,
  orNA,
  scopeAllStatus,
  scopeStatus,
  scopeToggleLabel,
  sovereignBadge,
} from '../lib/format';
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
import { fetchParquetBytes, loadManifest } from '../lib/snapshot-client';
import { docPath } from '../lib/urls';
import { renderError, renderNotice, userMessageOf } from './dom';

const PAGE_SIZE = 50;

interface UiState {
  country: string;
  source: string;
  includeNonSovereign: boolean;
  page: number;
}

function clampPage(v: unknown): number {
  const n = Math.floor(Number(v));
  return Number.isSafeInteger(n) && n > 0 ? n : 0;
}

function stateFromUrl(): UiState {
  const q = new URLSearchParams(location.search);
  return {
    country: q.get('country') ?? '',
    source: q.get('source') ?? '',
    includeNonSovereign: q.get('scope') === 'all',
    page: clampPage(q.get('page')),
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
    link.href = docPath(row.slug);
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

  // Errors render into the notices region; the table skeleton is never
  // destroyed, so a failed query does not brick later successful renders.
  const showError = (e: unknown, fallback: string): void => {
    renderError(notices, userMessageOf(e, fallback));
  };

  let handle: DuckHandle;
  let grandTotal = 0;
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

    // First query: scope counts (also the engine warm-up; measured apart
    // from the later steady-state queries).
    const tFirst = performance.now();
    const scopeRows = await runQuery(handle.conn, buildScopeCountsSql());
    metrics.firstQueryMs = performance.now() - tFirst;
    const scope = scopeRows[0] as { total: number; sovereign: number };
    grandTotal = Number(scope.total);
    sovereignCount = Number(scope.sovereign);
    otherCount = grandTotal - sovereignCount;
  } catch (e) {
    status.textContent = '';
    showError(e, 'Could not start the in-browser query engine.');
    return;
  }

  scopeToggleText.textContent = scopeToggleLabel(otherCount);
  scopeToggle.checked = state.includeNonSovereign;
  scopeToggle.disabled = false;

  // Generation token: overlapping refreshes (rapid clicks) must not let a
  // stale response render over a newer one or write a stale URL.
  let refreshGeneration = 0;

  async function refresh(): Promise<void> {
    const generation = ++refreshGeneration;
    const snapshot: UiState = { ...state };
    const filters = filtersOf(snapshot);
    try {
      const tQuery = performance.now();
      const rows = (await runQuery(handle.conn, buildListSql(filters))) as unknown as BrowseRow[];
      const countRows = await runQuery(handle.conn, buildCountSql(filters));
      if (generation !== refreshGeneration) return; // stale
      if (!metrics.secondQueryMs) metrics.secondQueryMs = performance.now() - tQuery;
      const total = Number((countRows[0] as { n: number }).n);
      const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

      // A shared link can point past the last page; clamp and requery.
      if (snapshot.page > pages - 1) {
        state.page = pages - 1;
        void refresh();
        return;
      }

      renderRows(tbody, rows);
      table.hidden = false;
      metrics.rowsRendered = rows.length;
      if (!metrics.totalToFirstRenderMs) metrics.totalToFirstRenderMs = performance.now() - tStart;

      const scopeTotal = snapshot.includeNonSovereign ? grandTotal : sovereignCount;
      const hasFilters = Boolean(snapshot.country || snapshot.source);
      const scopeText = hasFilters
        ? filteredStatus(total, scopeTotal, !snapshot.includeNonSovereign)
        : snapshot.includeNonSovereign
          ? scopeAllStatus(grandTotal)
          : scopeStatus(sovereignCount);
      status.textContent = `${scopeText} Page ${snapshot.page + 1} of ${pages.toLocaleString('en-US')}.`;
      prev.hidden = next.hidden = false;
      prev.disabled = snapshot.page === 0;
      next.disabled = snapshot.page >= pages - 1;
      stateToUrl(snapshot);
    } catch (e) {
      if (generation !== refreshGeneration) return;
      showError(e, 'Query failed.');
    }
  }

  try {
    const [countries, sources] = await Promise.all([
      runQuery(handle.conn, buildDistinctSql('country_name')),
      runQuery(handle.conn, buildDistinctSql('source')),
    ]);
    const countryValues = countries.map((r) => String(r.v));
    const sourceValues = sources.map((r) => String(r.v));
    // A URL-supplied filter value that does not exist would silently apply
    // an invisible filter (select shows "All"); reset it instead.
    if (state.country && !countryValues.includes(state.country)) state.country = '';
    if (state.source && !sourceValues.includes(state.source)) state.source = '';
    fillSelect(countrySelect, countryValues, state.country);
    fillSelect(sourceSelect, sourceValues, state.source);
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
    if (!next.disabled) state.page += 1;
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
