import { expect, it } from 'vitest';

import { SnapshotError, fetchDocText, fetchParquetBytes, loadManifest } from '../../src/lib/snapshot-client';

const GOOD = {
  schema_version: 1,
  snapshot_date: '2026-07-04',
  generated_at: '2026-07-04T17:04:09+00:00',
  document_count: 9774,
};

it('resolves a valid manifest', async () => {
  const fake = (async () => new Response(JSON.stringify(GOOD))) as unknown as typeof fetch;
  const m = await loadManifest('/data', fake);
  expect(m.generated_at).toBe(GOOD.generated_at);
  expect(m.document_count).toBe(9774);
});

it('passes cache no-store and the manifest URL', async () => {
  let url: string | undefined;
  let init: RequestInit | undefined;
  const fake = (async (u: string, i?: RequestInit) => {
    url = u;
    init = i;
    return new Response(JSON.stringify(GOOD));
  }) as unknown as typeof fetch;
  await loadManifest('/data', fake);
  expect(url).toBe('/data/MANIFEST.json');
  expect(init?.cache).toBe('no-store');
});

it('rejects wrong schema_version with a user-renderable error', async () => {
  const fake = (async () =>
    new Response(JSON.stringify({ ...GOOD, schema_version: 2 }))) as unknown as typeof fetch;
  const err = await loadManifest('/data', fake).catch((e: unknown) => e);
  expect(err).toBeInstanceOf(SnapshotError);
  expect((err as SnapshotError).userMessage).toContain('schema version');
});

it('rejects HTTP errors', async () => {
  const fake = (async () => new Response('nope', { status: 500 })) as unknown as typeof fetch;
  await expect(loadManifest('/data', fake)).rejects.toBeInstanceOf(SnapshotError);
});

it('rejects invalid JSON', async () => {
  const fake = (async () => new Response('<html>not json</html>')) as unknown as typeof fetch;
  await expect(loadManifest('/data', fake)).rejects.toBeInstanceOf(SnapshotError);
});

it('rejects a null manifest (valid JSON, not an object)', async () => {
  const fake = (async () => new Response('null')) as unknown as typeof fetch;
  await expect(loadManifest('/data', fake)).rejects.toBeInstanceOf(SnapshotError);
});

it('fetchParquetBytes returns bytes from the versioned URL', async () => {
  let url: string | undefined;
  const payload = new Uint8Array([1, 2, 3]);
  const fake = (async (u: string) => {
    url = u;
    return new Response(payload);
  }) as unknown as typeof fetch;
  const result = await fetchParquetBytes('/data', 'g1', fake);
  expect(url).toBe('/data/documents.parquet?v=g1');
  expect([...result.bytes]).toEqual([1, 2, 3]);
});

it('fetchParquetBytes throws SnapshotError on HTTP error', async () => {
  const fake = (async () => new Response('x', { status: 503 })) as unknown as typeof fetch;
  await expect(fetchParquetBytes('/data', 'g1', fake)).rejects.toBeInstanceOf(SnapshotError);
});

it('fetchDocText parses text JSON with timing splits', async () => {
  let url: string | undefined;
  const fake = (async (u: string) => {
    url = u;
    return new Response(JSON.stringify({ text: 'hello', toc: [] }));
  }) as unknown as typeof fetch;
  const result = await fetchDocText('/data', 'nsm-1', 'g1', fake);
  expect(url).toBe('/data/text/nsm-1.json?v=g1');
  expect(result.doc.text).toBe('hello');
  expect(result.stringLength).toBeGreaterThan(0);
});

it('fetchDocText throws SnapshotError on 404', async () => {
  const fake = (async () => new Response('missing', { status: 404 })) as unknown as typeof fetch;
  await expect(fetchDocText('/data', 'nope', 'g1', fake)).rejects.toBeInstanceOf(SnapshotError);
});
