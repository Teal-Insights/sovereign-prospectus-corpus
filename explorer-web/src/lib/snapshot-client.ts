// MANIFEST-first client data access (snapshot contract: read MANIFEST.json
// uncached before any data read; its generated_at is the cache-busting token
// for parquet and text fetches).

import { manifestUrl, parquetUrl, textUrl } from './urls';

export interface Manifest {
  schema_version: number;
  snapshot_date: string;
  generated_at: string;
  document_count: number;
}

export class SnapshotError extends Error {
  readonly userMessage: string;

  constructor(message: string, userMessage: string) {
    super(message);
    this.name = 'SnapshotError';
    this.userMessage = userMessage;
  }
}

const SUPPORTED_SCHEMA_VERSION = 1;

export async function loadManifest(base: string, fetchFn: typeof fetch = fetch): Promise<Manifest> {
  let res: Response;
  try {
    res = await fetchFn(manifestUrl(base), { cache: 'no-store' });
  } catch (e) {
    throw new SnapshotError(`manifest fetch failed: ${String(e)}`, 'Could not reach the data host.');
  }
  if (!res.ok) {
    throw new SnapshotError(
      `manifest HTTP ${res.status}`,
      `The data host returned an error (HTTP ${res.status}) for the snapshot manifest.`
    );
  }
  let manifest: Manifest;
  try {
    manifest = (await res.json()) as Manifest;
  } catch {
    throw new SnapshotError('manifest is not valid JSON', 'The snapshot manifest is not valid JSON.');
  }
  if (!manifest || typeof manifest !== 'object') {
    throw new SnapshotError('manifest is not an object', 'The snapshot manifest is invalid.');
  }
  if (manifest.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new SnapshotError(
      `unsupported schema_version ${manifest.schema_version}`,
      `This explorer supports snapshot schema version ${SUPPORTED_SCHEMA_VERSION}; the data host serves version ${manifest.schema_version}. The site needs a rebuild.`
    );
  }
  return manifest;
}

// All data fetching lives here (the client scripts are disposable UI and
// never call fetch directly).

export async function fetchParquetBytes(
  base: string,
  generatedAt: string,
  fetchFn: typeof fetch = fetch
): Promise<{ bytes: Uint8Array; fetchMs: number }> {
  const t0 = performance.now();
  const res = await fetchFn(parquetUrl(base, generatedAt));
  if (!res.ok) {
    throw new SnapshotError(
      `parquet HTTP ${res.status}`,
      `The data host returned an error (HTTP ${res.status}) for the document index.`
    );
  }
  const bytes = new Uint8Array(await res.arrayBuffer());
  return { bytes, fetchMs: performance.now() - t0 };
}

export interface TocEntry {
  level: number;
  title: string;
  offset: number;
  offset_utf16: number;
}

export interface TextDoc {
  text: string;
  toc: TocEntry[];
}

export interface TextFetchResult {
  doc: TextDoc;
  fetchMs: number;
  parseMs: number;
  // UTF-16 code units of the response body, not bytes (transfer is
  // compressed anyway; text_bytes in the parquet is the exact stored size).
  stringLength: number;
}

export async function fetchDocText(
  base: string,
  slug: string,
  generatedAt: string,
  fetchFn: typeof fetch = fetch
): Promise<TextFetchResult> {
  const t0 = performance.now();
  const res = await fetchFn(textUrl(base, slug, generatedAt));
  if (!res.ok) {
    throw new SnapshotError(
      `text HTTP ${res.status}`,
      `The data host returned an error (HTTP ${res.status}) for this document's text.`
    );
  }
  const body = await res.text();
  const t1 = performance.now();
  const doc = JSON.parse(body) as TextDoc;
  return { doc, fetchMs: t1 - t0, parseMs: performance.now() - t1, stringLength: body.length };
}
