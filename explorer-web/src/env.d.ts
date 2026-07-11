/// <reference types="astro/client" />

interface EwDocMetrics {
  fetchMs: number;
  parseMs: number;
  renderMs: number;
  // Last per-segment markdown render (parse + sanitize + inject + index),
  // updated on every segment render in seg-rendered mode; null elsewhere
  // (TEA-989).
  segRenderMs: number | null;
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
  // The documented S3 integration contract (see explorer-web/ARCHITECTURE.md),
  // mode-scoped as of B1/TEA-929, extended to segmented docs by TEA-989:
  //   - getRawText() returns the FULL raw string in EVERY mode (plain full,
  //     segmented, rendered, and seg-rendered) once text is loaded; null
  //     before load and behind an unclicked gate.
  //   - PLAIN and SEGMENTED-PLAIN modes (pages-source docs, force-listed
  //     slugs, and the raw view of any doc): whenever getRawText() returns
  //     non-null, #ew-doc-text holds exactly one text node whose content is
  //     the rendered slice and data-seg-start carries the slice's UTF-16
  //     start offset (gate, loading, and error states hold other DOM).
  //   - RENDERED modes (markdown docs of ANY size; per-segment above 1M
  //     units): #ew-doc-text holds a rendered HTML tree wrapped in
  //     <div class="ew-doc-rendered"> covering the whole doc at or under 1M
  //     units and the ACTIVE SEGMENT above; the single-text-node /
  //     data-seg-start invariant does NOT hold. Detect these modes by the
  //     .ew-doc-rendered child (data-text-source on the container names the
  //     source but not the eligibility). getRawText() still returns the full
  //     raw markdown string.
  //   - ?q= is the only supported deep-link into a document, and it never
  //     bypasses the 5 MB click-gate.
  __ewDoc?: { getRawText(): string | null };
  __ewDocMetrics?: EwDocMetrics;
  __ewMetrics?: EwBrowseMetrics;
}
