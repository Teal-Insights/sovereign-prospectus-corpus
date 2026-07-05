// Guards the synthetic fixture shapes from issue #88: the click-gate branch,
// UTF-16 offset divergence, and segment-scale text must stay CI-reachable.
import { readFileSync } from 'node:fs';

import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';
import { expect, it } from 'vitest';

const FIX = new URL('../fixtures/snapshot/', import.meta.url).pathname;

interface TocEntryJson {
  level: number;
  title: string;
  offset: number;
  offset_utf16: number;
}

interface TextDocJson {
  text: string;
  toc: TocEntryJson[];
}

const readDoc = (slug: string): TextDocJson =>
  JSON.parse(readFileSync(`${FIX}text/${slug}.json`, 'utf8')) as TextDocJson;

async function rows(): Promise<Record<string, unknown>[]> {
  const file = await asyncBufferFromFile(`${FIX}documents.parquet`);
  return (await parquetReadObjects({ file })) as Record<string, unknown>[];
}

it('has a gate-scale row with inflated text_bytes and a small file', async () => {
  const r = (await rows()).find((x) => x.slug === 'synthetic-gate');
  expect(r).toBeDefined();
  expect(Number(r!.text_bytes)).toBeGreaterThan(5_000_000);
  expect(r!.has_text).toBe(true);
  expect(readDoc('synthetic-gate').text.length).toBeLessThan(10_000);
});

it('keeps synthetic rows out of the country options (null country_code)', async () => {
  const synth = (await rows()).filter((x) => x.source === 'synthetic');
  expect(synth.length).toBeGreaterThanOrEqual(3);
  for (const r of synth) expect(r.country_code ?? null).toBeNull();
});

it('has an astral doc where a toc offset diverges from offset_utf16', () => {
  const doc = readDoc('synthetic-astral');
  const diverging = doc.toc.find((e) => e.offset !== e.offset_utf16);
  expect(diverging).toBeDefined();
  expect(doc.text.slice(diverging!.offset_utf16, diverging!.offset_utf16 + 2)).toBe('##');
});

it('has a segment-scale doc (>1M units, one oversized section)', () => {
  const doc = readDoc('synthetic-large');
  expect(doc.text.length).toBeGreaterThan(1_000_000);
  expect(doc.toc.length).toBeGreaterThanOrEqual(8);
  const offs = doc.toc.map((e) => e.offset_utf16);
  const gaps = offs.slice(1).map((o, i) => o - offs[i]);
  expect(Math.max(...gaps, doc.text.length - offs[offs.length - 1])).toBeGreaterThan(500_000);
});
