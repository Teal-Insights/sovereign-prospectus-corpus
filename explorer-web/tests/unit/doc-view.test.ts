import { expect, it } from 'vitest';

import {
  DEFAULT_SEARCH_LIMITS,
  DEFAULT_SEGMENT_CONFIG,
  buildSearchPattern,
  computeSegments,
  countsByBins,
  findMatches,
  needsSegments,
  sanitizeToc,
  segmentForOffset,
  snippetAround,
  type Segment,
  type TocEntryLike,
} from '../../src/lib/doc-view';

const cfg = (segmentTarget: number, fullRenderMax = segmentTarget * 2) => ({
  fullRenderMax,
  segmentTarget,
});

const entry = (offset_utf16: number, title = `h@${offset_utf16}`): TocEntryLike => ({
  level: 2,
  title,
  offset_utf16,
});

function assertTiling(segments: Segment[], len: number): void {
  expect(segments[0].start).toBe(0);
  expect(segments[segments.length - 1].end).toBe(len);
  for (let i = 0; i < segments.length; i++) {
    if (len > 0) expect(segments[i].end).toBeGreaterThan(segments[i].start);
    if (i > 0) expect(segments[i].start).toBe(segments[i - 1].end);
  }
}

// ---- segment computation ----

it('defaults: 1M full-render ceiling, 500K target', () => {
  expect(DEFAULT_SEGMENT_CONFIG).toEqual({ fullRenderMax: 1_000_000, segmentTarget: 500_000 });
  expect(needsSegments(1_000_000)).toBe(false);
  expect(needsSegments(1_000_001)).toBe(true);
});

it('packs consecutive sections until the target, closing at section boundaries', () => {
  // sections at 0, 40, 80, 120 in 160 chars; target 100 -> [0,80) + [80,160)
  const text = 'a'.repeat(160);
  const toc = [entry(40), entry(80), entry(120)];
  const segments = computeSegments(text, toc, cfg(100));
  expect(segments).toEqual([
    { start: 0, end: 80 },
    { start: 80, end: 160 },
  ]);
});

it('cuts an oversized single section at the last newline before each step', () => {
  // one section of 250 chars with newlines every 40; target 100
  const line = `${'x'.repeat(39)}\n`;
  const text = line.repeat(6) + 'y'.repeat(10); // 250 chars
  const segments = computeSegments(text, [], cfg(100));
  assertTiling(segments, text.length);
  for (const s of segments) expect(s.end - s.start).toBeLessThanOrEqual(100);
  // cuts land after newlines
  for (const s of segments.slice(1)) expect(text[s.start - 1]).toBe('\n');
});

it('hard-cuts a no-newline window at the step', () => {
  const text = 'z'.repeat(250);
  const segments = computeSegments(text, [], cfg(100));
  expect(segments).toEqual([
    { start: 0, end: 100 },
    { start: 100, end: 200 },
    { start: 200, end: 250 },
  ]);
});

it('never splits a surrogate pair on a hard cut', () => {
  const text = '\u{1F4C4}'.repeat(100); // 200 UTF-16 units, no newlines
  const segments = computeSegments(text, [], cfg(75));
  assertTiling(segments, 200);
  for (const s of segments.slice(1)) {
    const c = text.charCodeAt(s.start);
    // a segment must never begin on a low surrogate (second half of a pair)
    expect(c >= 0xdc00 && c <= 0xdfff).toBe(false);
  }
});

it('tiny segments are accepted: small front matter before an oversized section', () => {
  const text = 'a'.repeat(1200).replace(/^.{100}/, `${'f'.repeat(99)}\n`);
  const segments = computeSegments(text, [entry(100)], cfg(500));
  assertTiling(segments, 1200);
  expect(segments[0]).toEqual({ start: 0, end: 100 });
});

it('tail after the last TOC entry is cuttable', () => {
  const text = 'b'.repeat(1000);
  const segments = computeSegments(text, [entry(10, 'late')], cfg(300));
  assertTiling(segments, 1000);
  expect(segments.length).toBeGreaterThan(2);
});

it('empty text yields the single empty segment', () => {
  expect(computeSegments('', [], cfg(100))).toEqual([{ start: 0, end: 0 }]);
});

it('sanitizes toc: sorts, dedupes offsets, drops out-of-range entries', () => {
  const toc = [entry(50), entry(10), entry(50), entry(-1), entry(999), entry(20)];
  expect(sanitizeToc(toc, 100).map((e) => e.offset_utf16)).toEqual([10, 20, 50]);
});

it('tiling property holds across generated shapes', () => {
  const shapes: Array<{ len: number; offsets: number[]; target: number }> = [
    { len: 1, offsets: [], target: 100 },
    { len: 99, offsets: [98], target: 10 },
    { len: 1000, offsets: [1, 2, 3, 999], target: 50 },
    { len: 5000, offsets: [2500], target: 400 },
    { len: 777, offsets: [111, 222, 333, 444, 555, 666], target: 200 },
  ];
  for (const { len, offsets, target } of shapes) {
    const text = 'q'.repeat(len);
    const segments = computeSegments(text, offsets.map((o) => entry(o)), cfg(target));
    assertTiling(segments, len);
  }
});

it('segmentForOffset: exact boundaries and clamping', () => {
  const segments: Segment[] = [
    { start: 0, end: 100 },
    { start: 100, end: 250 },
    { start: 250, end: 300 },
  ];
  expect(segmentForOffset(segments, 0)).toBe(0);
  expect(segmentForOffset(segments, 99)).toBe(0);
  expect(segmentForOffset(segments, 100)).toBe(1);
  expect(segmentForOffset(segments, 299)).toBe(2);
  expect(segmentForOffset(segments, 300)).toBe(2); // clamped
  expect(segmentForOffset(segments, -5)).toBe(0); // clamped
});

// ---- search ----

it('matches case-insensitively with UTF-16-true offsets', () => {
  const m = findMatches('Pari Passu and pari passu', 'pari passu')!;
  expect(m.starts).toEqual([0, 15]);
  expect(m.ends).toEqual([10, 25]);
  expect(m.capped).toBe(false);
});

it('whitespace in the query matches across line breaks', () => {
  const text = 'collective action\n  clauses apply';
  const m = findMatches(text, 'collective action clauses')!;
  expect(m.starts).toEqual([0]);
  expect(text.slice(m.starts[0], m.ends[0])).toBe('collective action\n  clauses');
});

it('quote tolerance is symmetric across straight and typographic forms', () => {
  const text = "Noteholders’ meetings and Noteholders' rights";
  expect(findMatches(text, "Noteholders' meetings")!.starts).toEqual([0]);
  expect(findMatches(text, 'Noteholders’ rights')!.starts.length).toBe(1);
  const doubles = findMatches('say “default” here', '"default"')!;
  expect(doubles.starts.length).toBe(1);
});

it('regex metacharacters are literal', () => {
  const m = findMatches('rate of 10.5% (fixed)', '10.5% (fixed)')!;
  expect(m.starts).toEqual([8]);
  expect(findMatches('10x5% or 1035%', '10.5%')).toEqual({ starts: [], ends: [], capped: false });
});

it('astral characters keep offsets UTF-16-true', () => {
  const text = 'before \u{1F4C4} pari passu';
  const m = findMatches(text, 'pari passu')!;
  expect(text.slice(m.starts[0], m.ends[0])).toBe('pari passu');
});

it('rejects too-short and whitespace-only queries', () => {
  expect(buildSearchPattern('a')).toBeNull();
  expect(buildSearchPattern('  ')).toBeNull();
  expect(findMatches('anything', 'a')).toBeNull();
  expect(buildSearchPattern('ab')).not.toBeNull();
  // min length counts code points: one astral char is still one char
  expect(buildSearchPattern('\u{1F4C4}')).toBeNull();
});

it('caps with look-ahead: exactly at the cap is not capped', () => {
  const text = 'ab '.repeat(30);
  const limits = { ...DEFAULT_SEARCH_LIMITS, maxMatches: 30 };
  const exact = findMatches(text, 'ab', limits)!;
  expect(exact.starts.length).toBe(30);
  expect(exact.capped).toBe(false);
  const over = findMatches(`${text}ab`, 'ab', limits)!;
  expect(over.starts.length).toBe(30);
  expect(over.capped).toBe(true);
});

it('countsByBins sums to the match count, bin 0 owning pre-boundary matches', () => {
  const starts = [5, 10, 15, 100, 150, 900];
  expect(countsByBins(starts, [0, 100, 200])).toEqual([3, 2, 1]);
  // no zero boundary: bin 0 starts at the first boundary; earlier matches fall nowhere
  expect(countsByBins([5, 250], [200, 300])).toEqual([1, 0]);
});

it('snippetAround collapses whitespace and clips at the ends', () => {
  const text = `start\n\nmiddle target middle\n\nend`;
  const s = snippetAround(text, text.indexOf('target'), text.indexOf('target') + 6, 10);
  expect(s).toContain('target');
  expect(s.includes('\n')).toBe(false);
  const atStart = snippetAround('target tail', 0, 6, 20);
  expect(atStart.startsWith('target')).toBe(true);
});
