// MANIFEST-first client data access (snapshot contract: read MANIFEST.json
// uncached before any data read; its generated_at is the cache-busting token
// for parquet and text fetches).

import { manifestUrl } from './urls';

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
  if (manifest.schema_version !== SUPPORTED_SCHEMA_VERSION) {
    throw new SnapshotError(
      `unsupported schema_version ${manifest.schema_version}`,
      `This explorer supports snapshot schema version ${SUPPORTED_SCHEMA_VERSION}; the data host serves version ${manifest.schema_version}. The site needs a rebuild.`
    );
  }
  return manifest;
}
