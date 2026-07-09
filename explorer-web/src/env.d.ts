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
  // The documented S3 integration contract (see explorer-web/ARCHITECTURE.md),
  // mode-scoped as of B1/TEA-929:
  //   - getRawText() returns the FULL raw string in EVERY mode (plain full,
  //     segmented, and rendered) once text is loaded; null before load and
  //     behind an unclicked gate.
  //   - PLAIN and SEGMENTED modes (pages-source docs, docs over 1M units,
  //     force-listed slugs): whenever getRawText() returns non-null,
  //     #ew-doc-text holds exactly one text node whose content is the rendered
  //     slice and data-seg-start carries the slice's UTF-16 start offset (gate,
  //     loading, and error states hold other DOM).
  //   - RENDERED mode (markdown docs at or under 1M units): #ew-doc-text holds
  //     a rendered HTML tree wrapped in <div class="ew-doc-rendered">; the
  //     single-text-node / data-seg-start invariant does NOT hold. Detect this
  //     mode by the .ew-doc-rendered child (data-text-source on the container
  //     names the source but not the eligibility). getRawText() still returns
  //     the full raw markdown string.
  //   - ?q= is the only supported deep-link into a document, and it never
  //     bypasses the 5 MB click-gate.
  __ewDoc?: { getRawText(): string | null };
  __ewDocMetrics?: EwDocMetrics;
  __ewMetrics?: EwBrowseMetrics;
}
