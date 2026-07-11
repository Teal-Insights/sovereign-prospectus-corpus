// Guards the synthetic fixture shapes from issue #88: the click-gate branch,
// UTF-16 offset divergence, and segment-scale text must stay CI-reachable.
import { readFileSync } from 'node:fs';

import { asyncBufferFromFile, parquetReadObjects } from 'hyparquet';
import { expect, it } from 'vitest';

import { DEFAULT_SEGMENT_CONFIG, computeSegments } from '../../src/lib/doc-view';

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

it('has a segmented markdown-rich doc whose default cuts are markdown-safe (TEA-989)', () => {
  const doc = readDoc('synthetic-seg-rich');
  expect(doc.text.length).toBeGreaterThan(1_000_000);
  // adversarial content the cut logic must dodge, plus the smoke needles
  const tStart = doc.text.indexOf('| Tranche | Coupon |');
  const tEnd = doc.text.indexOf('\n\n', tStart) + 1; // straddling table's last row
  const fStart = doc.text.indexOf('```');
  const fEnd = doc.text.indexOf('```', fStart + 3) + 3;
  expect(tStart).toBeGreaterThan(0);
  expect(fStart).toBeGreaterThan(0);
  expect(doc.text).toContain('collective **action** clauses');
  expect(doc.text).toContain('quantum sovereign covenant');
  // the table must straddle the 500K default cut so the fixture actually
  // exercises the markdown-safe cut logic
  expect(tStart).toBeLessThan(500_000);
  expect(tEnd).toBeGreaterThan(500_000);
  const segments = computeSegments(doc.text, doc.toc, DEFAULT_SEGMENT_CONFIG);
  expect(segments.length).toBeGreaterThanOrEqual(3);
  for (const s of segments.slice(1)) {
    // no boundary lands inside the table or the fence
    expect(s.start <= tStart || s.start > tEnd).toBe(true);
    expect(s.start <= fStart || s.start > fEnd).toBe(true);
  }
  // the fence straddles the second cut's window and forces a dodge: at least
  // one boundary sits at or before the fence start while the fence itself
  // ends past that boundary plus nothing between the rows
  expect(fEnd).toBeGreaterThan(segments[2].start);
  // the last segment carries the needle and the final heading for the
  // cross-segment search and TOC smoke scenarios
  const last = segments[segments.length - 1];
  const needleAt = doc.text.indexOf('quantum sovereign covenant');
  const finalHeadingAt = doc.text.indexOf('## Final Provisions');
  expect(needleAt).toBeGreaterThanOrEqual(last.start);
  expect(finalHeadingAt).toBeGreaterThanOrEqual(last.start);
});

it('has a markdown-rich doc for rendered mode (bold-split phrase, table, headings)', () => {
  const doc = readDoc('synthetic-rich');
  // rendered-mode eligible: markdown and at or under the 1M-unit ceiling
  expect(doc.text.length).toBeLessThan(1_000_000);
  // a phrase split across bold in the raw markdown; matches a spaced query
  // only after rendering strips the asterisks (the active-text contract)
  expect(doc.text).toContain('collective **action** clauses');
  // a GFM table so table rendering stays CI-reachable
  expect(doc.text).toContain('| Series | Rate | Maturity |');
  expect(doc.toc.length).toBeGreaterThanOrEqual(3);
});
