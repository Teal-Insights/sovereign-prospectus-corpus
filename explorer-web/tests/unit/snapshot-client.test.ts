import { expect, it } from 'vitest';

import { SnapshotError, loadManifest } from '../../src/lib/snapshot-client';

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
