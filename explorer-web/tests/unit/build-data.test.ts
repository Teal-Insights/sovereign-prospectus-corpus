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

// ---- S3 additions (TEA-903): pure aggregations for the baked static shell ----
import { computeFilterOptions, computeStats, type DocRow } from '../../src/lib/build-data';

function row(over: Partial<DocRow>): DocRow {
  return {
    slug: 's',
    document_id: null,
    storage_key: null,
    source: null,
    native_id: null,
    display_name: null,
    issuer_name: null,
    title: null,
    doc_type: null,
    publication_date: null,
    country_code: null,
    country_name: null,
    region: null,
    income_group: null,
    lending_category: null,
    is_sovereign: null,
    filing_url: null,
    page_count: null,
    has_text: null,
    text_source: null,
    text_chars: null,
    text_bytes: null,
    no_text_reason: null,
    ...over,
  };
}

it('computeStats: distinct issuers exclude nulls; sovereign + related tile the corpus', () => {
  const stats = computeStats([
    row({ slug: 'a', source: 'edgar', issuer_name: 'Kenya', is_sovereign: true }),
    row({ slug: 'b', source: 'edgar', issuer_name: 'Kenya', is_sovereign: true }),
    row({ slug: 'c', source: 'nsm', issuer_name: null, is_sovereign: false }),
    row({ slug: 'd', source: 'pdip', issuer_name: 'Ghana', is_sovereign: null }),
  ]);
  expect(stats).toEqual({ docs: 4, sources: 3, issuers: 2, sovereign: 2, related: 2 });
});

it('computeFilterOptions: null-code countries dropped, name-sorted, Unknown materialized, sorted lists', () => {
  const opts = computeFilterOptions([
    row({ slug: 'a', country_code: 'KEN', country_name: 'Kenya', region: 'Sub-Saharan Africa', income_group: 'Lower middle income', source: 'edgar' }),
    row({ slug: 'b', country_code: 'ARG', country_name: 'Argentina', region: null, income_group: null, source: 'luxse' }),
    row({ slug: 'c', country_code: 'KEN', country_name: 'Kenya', region: 'Sub-Saharan Africa', income_group: 'Lower middle income', source: 'edgar' }),
    row({ slug: 'd', country_code: null, country_name: 'Synthetic', region: 'Unknown', income_group: 'Unknown', source: 'synthetic' }),
  ]);
  expect(opts.countries).toEqual([
    { code: 'ARG', name: 'Argentina' },
    { code: 'KEN', name: 'Kenya' },
  ]);
  expect(opts.regions).toEqual(['Sub-Saharan Africa', 'Unknown']);
  expect(opts.incomes).toEqual(['Lower middle income', 'Unknown']);
  expect(opts.sources).toEqual(['edgar', 'luxse', 'synthetic']);
});

it('aggregations over the real fixture agree with the MANIFEST', async () => {
  const docs = await loadDocuments();
  const stats = computeStats(docs);
  expect(stats.docs).toBe(fixtureManifest.document_count);
  expect(stats.sovereign + stats.related).toBe(stats.docs);
  const opts = computeFilterOptions(docs);
  expect(opts.countries.every((c) => c.code && c.name)).toBe(true);
  // synthetics have null country_code and must not surface as options
  expect(opts.countries.some((c) => c.name === 'Synthetic')).toBe(false);
});
