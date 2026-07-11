import { expect, it } from 'vitest';

import {
  DEFAULT_SEARCH_LIMITS,
  DEFAULT_SEGMENT_CONFIG,
  FORCE_PLAIN_SLUGS,
  buildSearchPattern,
  computeSegments,
  countsByBins,
  findMatches,
  locateSpan,
  needsSegments,
  nthTitleIndex,
  pickRenderedOrdinal,
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

it('snippetAround never cuts a surrogate pair at its edges', () => {
  const text = `${'\u{1F4C4}'.repeat(30)}needle${'\u{1F4C4}'.repeat(30)}`;
  const start = text.indexOf('needle');
  const s = snippetAround(text, start, start + 6, 15);
  expect(s.includes('\uFFFD')).toBe(false);
  const first = s.charCodeAt(0);
  expect(first >= 0xdc00 && first <= 0xdfff).toBe(false);
  const last = s.charCodeAt(s.length - 1);
  expect(last >= 0xd800 && last <= 0xdbff).toBe(false);
});

// ---- locateSpan (rendered-mode text-node offset mapping) ----

// nodes of length 5, 3, 4 -> starts [0, 5, 8], total 12
const STARTS = [0, 5, 8];
const LENGTHS = [5, 3, 4];

it('locateSpan: span within a single node', () => {
  expect(locateSpan(STARTS, LENGTHS, 1, 4)).toEqual({
    startNode: 0,
    startOffset: 1,
    endNode: 0,
    endOffset: 4,
  });
});

it('locateSpan: span across two nodes', () => {
  expect(locateSpan(STARTS, LENGTHS, 3, 7)).toEqual({
    startNode: 0,
    startOffset: 3,
    endNode: 1,
    endOffset: 2,
  });
});

it('locateSpan: span across three nodes reaching the very end', () => {
  expect(locateSpan(STARTS, LENGTHS, 0, 12)).toEqual({
    startNode: 0,
    startOffset: 0,
    endNode: 2,
    endOffset: 4,
  });
});

it('locateSpan: a start exactly on a node boundary picks the later node', () => {
  expect(locateSpan(STARTS, LENGTHS, 5, 8)).toEqual({
    startNode: 1,
    startOffset: 0,
    endNode: 1,
    endOffset: 3,
  });
});

it('locateSpan: end clamps to the total length', () => {
  expect(locateSpan(STARTS, LENGTHS, 10, 999)).toEqual({
    startNode: 2,
    startOffset: 2,
    endNode: 2,
    endOffset: 4,
  });
});

it('locateSpan: start at or past the total returns null', () => {
  expect(locateSpan(STARTS, LENGTHS, 12, 15)).toBeNull();
  expect(locateSpan(STARTS, LENGTHS, 99, 200)).toBeNull();
});

it('locateSpan: an empty span (after clamping) returns null', () => {
  expect(locateSpan(STARTS, LENGTHS, 5, 5)).toBeNull();
  expect(locateSpan(STARTS, LENGTHS, 6, 3)).toBeNull();
  expect(locateSpan(STARTS, LENGTHS, 8, 8)).toBeNull();
});

it('locateSpan: zero-length nodes never trap the start or end', () => {
  // node 1 is empty: starts [0, 5, 5], lengths [5, 0, 3], total 8
  const starts = [0, 5, 5];
  const lengths = [5, 0, 3];
  // start on the shared boundary lands on the non-empty node 2
  expect(locateSpan(starts, lengths, 5, 8)).toEqual({
    startNode: 2,
    startOffset: 0,
    endNode: 2,
    endOffset: 3,
  });
  // a span ending on the shared boundary stays in node 0
  expect(locateSpan(starts, lengths, 3, 5)).toEqual({
    startNode: 0,
    startOffset: 3,
    endNode: 0,
    endOffset: 5,
  });
});

it('locateSpan: single-node and empty-index inputs', () => {
  expect(locateSpan([0], [4], 1, 3)).toEqual({
    startNode: 0,
    startOffset: 1,
    endNode: 0,
    endOffset: 3,
  });
  expect(locateSpan([0], [4], 4, 5)).toBeNull();
  expect(locateSpan([], [], 0, 1)).toBeNull();
});

it('FORCE_PLAIN_SLUGS is empty by default', () => {
  expect(FORCE_PLAIN_SLUGS.size).toBe(0);
  expect(FORCE_PLAIN_SLUGS.has('anything')).toBe(false);
});

// ---- TEA-989: markdown-safe segment cuts ----

function boundaries(segments: Segment[]): number[] {
  return segments.slice(1).map((s) => s.start);
}

const PARA = `${'p'.repeat(58)}\n\n`; // one paragraph block: 58 chars + newline + blank line
// multi-line paragraph: inner newlines are NOT block boundaries
const MULTILINE_PARA = `${'a'.repeat(19)}\n${'b'.repeat(19)}\n${'c'.repeat(19)}\n\n`; // 61 chars

it('prefers a blank-line block boundary over a mid-paragraph newline', () => {
  const text = MULTILINE_PARA.repeat(10); // 610 chars, blocks every 61
  const segments = computeSegments(text, [], cfg(150));
  assertTiling(segments, text.length);
  expect(segments.length).toBeGreaterThan(2);
  for (const b of boundaries(segments)) {
    // every segment starts at a block start, right after a blank line,
    // never at one of the paragraph-internal newlines
    expect(text.slice(b - 2, b)).toBe('\n\n');
  }
});

it('never cuts inside a GFM table straddling the target', () => {
  const prefix = PARA.repeat(3); // 180 chars
  const rows = Array.from({ length: 12 }, (_, i) => `| row${i} | ${'v'.repeat(10)} |`).join('\n');
  const table = `| a | b |\n| --- | --- |\n${rows}\n`;
  const text = `${prefix}${table}\n${PARA.repeat(3)}`;
  const tStart = prefix.length;
  const tEnd = tStart + table.length;
  const segments = computeSegments(text, [], cfg(300)); // target lands mid-table
  assertTiling(segments, text.length);
  const bs = boundaries(segments);
  expect(bs.length).toBeGreaterThan(0);
  for (const b of bs) {
    expect(b <= tStart || b > tEnd).toBe(true);
  }
  // the cut before the table lands exactly on the table's block start
  expect(bs).toContain(tStart);
});

it('never cuts inside a fenced code block, even at blank lines within the fence', () => {
  const prefix = PARA.repeat(3); // 180 chars
  const fence = '```\ncode a\n\ncode b\n\n' + 'z'.repeat(120) + '\ncode c\n```\n';
  const text = `${prefix}${fence}\n${PARA.repeat(3)}`;
  const fStart = prefix.length;
  const fEnd = fStart + fence.length;
  const segments = computeSegments(text, [], cfg(250)); // target lands mid-fence
  assertTiling(segments, text.length);
  const bs = boundaries(segments);
  expect(bs.length).toBeGreaterThan(0);
  for (const b of bs) {
    // the blank lines INSIDE the fence must never be chosen
    expect(b <= fStart || b > fEnd).toBe(true);
  }
  expect(bs).toContain(fStart);
});

it('with no blank lines, falls back to a newline that never splits table rows', () => {
  const lines = Array.from({ length: 10 }, (_, i) => `plain line ${i} ${'w'.repeat(8)}`).join('\n');
  const table = `| a | b |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n`;
  const text = `${lines}\n${table}`;
  const tStart = lines.length + 1;
  const segments = computeSegments(text, [], cfg(tStart + 20)); // target inside the table
  assertTiling(segments, text.length);
  const bs = boundaries(segments);
  expect(bs.length).toBeGreaterThan(0);
  for (const b of bs) {
    // a cut AT the table's first row is safe (the whole table starts the next
    // segment); a cut between two table rows is never allowed
    expect(b <= tStart || b >= text.length).toBe(true);
  }
});

it('markdown-safe cuts preserve the exact tiling contract on mixed content', () => {
  const blocks = [
    '# Title\n\n',
    PARA.repeat(2),
    '| h1 | h2 |\n| --- | --- |\n| a | b |\n\n',
    '```\nfenced\n```\n\n',
    PARA.repeat(3),
  ];
  const text = blocks.join('');
  for (const target of [50, 90, 140, 220]) {
    assertTiling(computeSegments(text, [], cfg(target)), text.length);
  }
});

// ---- TEA-989: raw-ordinal to rendered-ordinal match mapping ----

it('pickRenderedOrdinal is the identity when raw and rendered counts agree', () => {
  expect(pickRenderedOrdinal(0, 5, 5)).toBe(0);
  expect(pickRenderedOrdinal(2, 5, 5)).toBe(2);
  expect(pickRenderedOrdinal(4, 5, 5)).toBe(4);
});

it('pickRenderedOrdinal maps proportionally when counts diverge', () => {
  // 3 raw matches, 5 rendered: first->first, last->last, middle->middle
  expect(pickRenderedOrdinal(0, 3, 5)).toBe(0);
  expect(pickRenderedOrdinal(1, 3, 5)).toBe(2);
  expect(pickRenderedOrdinal(2, 3, 5)).toBe(4);
  // 5 raw, 2 rendered: endpoints still map to endpoints
  expect(pickRenderedOrdinal(0, 5, 2)).toBe(0);
  expect(pickRenderedOrdinal(4, 5, 2)).toBe(1);
});

it('pickRenderedOrdinal: a single raw match lands on the first rendered match', () => {
  expect(pickRenderedOrdinal(0, 1, 4)).toBe(0);
});

it('pickRenderedOrdinal returns null when unmappable', () => {
  expect(pickRenderedOrdinal(0, 3, 0)).toBeNull(); // nothing rendered to map onto
  expect(pickRenderedOrdinal(0, 0, 3)).toBeNull(); // no raw matches in the segment
  expect(pickRenderedOrdinal(3, 3, 3)).toBeNull(); // ordinal out of range
  expect(pickRenderedOrdinal(-1, 3, 3)).toBeNull();
});

// ---- TEA-989: TOC title anchoring into a rendered segment ----

it('nthTitleIndex finds the k-th heading with a matching title', () => {
  const titles = ['Terms', 'Events of Default', 'Terms', 'Notices'];
  expect(nthTitleIndex(titles, 'Terms', 0)).toBe(0);
  expect(nthTitleIndex(titles, 'Terms', 1)).toBe(2);
  expect(nthTitleIndex(titles, 'Notices', 0)).toBe(3);
});

it('nthTitleIndex compares whitespace-normalized titles', () => {
  const titles = ['Terms  and\nConditions '];
  expect(nthTitleIndex(titles, 'Terms and Conditions', 0)).toBe(0);
  expect(nthTitleIndex(['Terms and Conditions'], ' Terms  and Conditions', 0)).toBe(0);
});

it('nthTitleIndex returns null when absent or past the last occurrence', () => {
  const titles = ['Terms', 'Notices'];
  expect(nthTitleIndex(titles, 'Missing', 0)).toBeNull();
  expect(nthTitleIndex(titles, 'Terms', 1)).toBeNull();
  expect(nthTitleIndex([], 'Terms', 0)).toBeNull();
});
