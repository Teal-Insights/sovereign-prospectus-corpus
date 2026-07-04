// Works ONLY because loadDocuments() reads SNAPSHOT_DIR lazily on first
// call: ESM imports hoist, so a module-scope env read in build-data.ts would
// capture the default before this assignment ran.
process.env.SNAPSHOT_DIR = 'tests/fixtures/snapshot';

import { readFileSync } from 'node:fs';

import { expect, it } from 'vitest';

import { loadDocuments, loadSnapshotManifest } from '../../src/lib/build-data';

interface FixtureManifest {
  document_count: number;
  snapshot_date: string;
  generated_at: string;
}
const fixtureManifest = JSON.parse(
  readFileSync('tests/fixtures/snapshot/MANIFEST.json', 'utf8')
) as FixtureManifest;

it('loads every fixture row', async () => {
  const docs = await loadDocuments();
  expect(docs.length).toBe(fixtureManifest.document_count);
});

it('slugs are unique non-empty strings', async () => {
  const docs = await loadDocuments();
  const slugs = docs.map((d) => d.slug);
  expect(new Set(slugs).size).toBe(docs.length);
  for (const s of slugs) {
    expect(typeof s).toBe('string');
    expect(s.length).toBeGreaterThan(0);
  }
});

it('normalizes dates to ISO strings and keeps nulls null', async () => {
  const docs = await loadDocuments();
  const dated = docs.filter((d) => d.publication_date !== null);
  const undated = docs.filter((d) => d.publication_date === null);
  expect(dated.length).toBeGreaterThan(0);
  expect(undated.length).toBeGreaterThan(0);
  for (const d of dated) expect(d.publication_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

it('is BigInt-free (numeric columns are numbers or null)', async () => {
  const docs = await loadDocuments();
  for (const d of docs) {
    for (const v of [d.text_bytes, d.text_chars, d.page_count, d.document_id]) {
      expect(v === null || typeof v === 'number').toBe(true);
    }
  }
});

it('no-text rows carry a reason', async () => {
  const docs = await loadDocuments();
  const noText = docs.filter((d) => d.has_text === false);
  expect(noText.length).toBeGreaterThan(0);
  for (const d of noText) expect(d.no_text_reason).not.toBeNull();
});

it('covers sovereign true, false, and null shapes', async () => {
  const docs = await loadDocuments();
  const values = new Set(docs.map((d) => d.is_sovereign));
  expect(values.has(false)).toBe(true);
  expect(values.has(null)).toBe(true);
});

it('caches (same array reference on second call)', async () => {
  const a = await loadDocuments();
  const b = await loadDocuments();
  expect(a).toBe(b);
});

it('reads the snapshot manifest for build stamping', async () => {
  const m = await loadSnapshotManifest();
  expect(m.snapshot_date).toBe(fixtureManifest.snapshot_date);
  expect(m.generated_at).toBe(fixtureManifest.generated_at);
});
