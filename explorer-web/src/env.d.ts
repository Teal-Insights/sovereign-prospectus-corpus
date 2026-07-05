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
  // The documented S3 integration contract (see explorer-web/ARCHITECTURE.md):
  // getRawText() returns the FULL raw string in every render mode (full or
  // segmented) once text is loaded; null before load and behind an unclicked
  // gate. Whenever getRawText() returns non-null, #ew-doc-text holds
  // exactly one text node whose content is the rendered slice and
  // data-seg-start carries the slice's UTF-16 start offset (gate, loading,
  // and error states hold other DOM). ?q= is the only supported deep-link into a document, and it
  // never bypasses the 5 MB click-gate.
  __ewDoc?: { getRawText(): string | null };
  __ewDocMetrics?: EwDocMetrics;
  __ewMetrics?: EwBrowseMetrics;
}
