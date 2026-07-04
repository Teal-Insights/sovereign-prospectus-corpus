/// <reference types="astro/client" />

interface EwDocMetrics {
  fetchMs: number;
  parseMs: number;
  renderMs: number;
  // UTF-16 code units of the fetched JSON body (not bytes; see NOTES.md)
  stringLength: number;
}

interface EwBrowseMetrics {
  bundleName: string;
  workerMs: number;
  instantiateMs: number;
  manifestMs: number;
  parquetFetchMs: number;
  registerMs: number;
  firstQueryMs: number;
  secondQueryMs: number;
  rowsRendered: number;
  totalToFirstRenderMs: number;
}

interface Window {
  __ewDoc?: { getRawText(): string | null };
  __ewDocMetrics?: EwDocMetrics;
  __ewMetrics?: EwBrowseMetrics;
}
