// Pure, DOM-free math for the document page: segment computation for very
// large documents (chunk-by-TOC-offset) and in-document search matching.
// Everything here works in UTF-16 string offsets exclusively; the snapshot's
// code-point `offset` fields are never consumed (issue #86 firewall).
// Thresholds arrive as parameters so tests drive tiny configurations.

export interface SegmentConfig {
  fullRenderMax: number;
  segmentTarget: number;
}

export const DEFAULT_SEGMENT_CONFIG: SegmentConfig = {
  fullRenderMax: 1_000_000,
  segmentTarget: 500_000,
};

export interface TocEntryLike {
  level: number;
  title: string;
  offset_utf16: number;
}

// [start, end) in UTF-16 units. Segments always tile the text exactly:
// first start 0, contiguous, last end = text.length.
export interface Segment {
  start: number;
  end: number;
}

export function sanitizeToc(toc: TocEntryLike[], textLength: number): TocEntryLike[] {
  const seen = new Set<number>();
  return [...toc]
    .filter(
      (e) =>
        Number.isSafeInteger(e.offset_utf16) && e.offset_utf16 >= 0 && e.offset_utf16 < textLength
    )
    .sort((a, b) => a.offset_utf16 - b.offset_utf16)
    .filter((e) => {
      if (seen.has(e.offset_utf16)) return false;
      seen.add(e.offset_utf16);
      return true;
    });
}

export function needsSegments(textLength: number, cfg: SegmentConfig = DEFAULT_SEGMENT_CONFIG): boolean {
  return textLength > cfg.fullRenderMax;
}

function findCut(text: string, from: number, at: number): number {
  const nl = text.lastIndexOf('\n', at - 1);
  if (nl > from) return nl + 1;
  const c = text.charCodeAt(at - 1);
  // never split a surrogate pair: back off when the last unit before the
  // cut is a high surrogate (its partner sits at `at`)
  return c >= 0xd800 && c <= 0xdbff ? at - 1 : at;
}

export function computeSegments(
  text: string,
  toc: TocEntryLike[],
  cfg: SegmentConfig = DEFAULT_SEGMENT_CONFIG
): Segment[] {
  const len = text.length;
  const starts = [0, ...sanitizeToc(toc, len).map((e) => e.offset_utf16).filter((o) => o > 0)];
  const segs: Segment[] = [];
  let segStart = 0;
  for (let i = 1; i <= starts.length; i++) {
    const next = i < starts.length ? starts[i] : len;
    if (next - segStart <= cfg.segmentTarget) continue; // keep packing sections
    const prev = starts[i - 1];
    if (prev > segStart) {
      segs.push({ start: segStart, end: prev });
      segStart = prev;
    }
    while (next - segStart > cfg.segmentTarget) {
      const cut = findCut(text, segStart, segStart + cfg.segmentTarget);
      if (cut <= segStart) break; // unreachable with target > 1; dead-man insurance
      segs.push({ start: segStart, end: cut });
      segStart = cut;
    }
  }
  if (segStart < len || segs.length === 0) segs.push({ start: segStart, end: len });
  return segs;
}

export function segmentForOffset(segments: Segment[], offset: number): number {
  let lo = 0;
  let hi = segments.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (segments[mid].end > offset) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

// ---- in-document search ----

export interface SearchLimits {
  minQueryLength: number;
  maxMatches: number;
}

export const DEFAULT_SEARCH_LIMITS: SearchLimits = {
  minQueryLength: 2,
  maxMatches: 20_000,
};

const SINGLE_QUOTES = "['\\u2018\\u2019]";
const DOUBLE_QUOTES = '["\\u201C\\u201D]';

// Literal, case-insensitive matching with two tolerances for
// machine-converted text: whitespace runs match any whitespace run
// (phrases split across line breaks still match), and quotes match across
// straight and typographic forms in both directions. The haystack is never
// lowercased (toLowerCase can change string length and shift every offset).
export function buildSearchPattern(
  query: string,
  limits: SearchLimits = DEFAULT_SEARCH_LIMITS
): RegExp | null {
  const q = query.trim();
  if ([...q].length < limits.minQueryLength) return null;
  let src = '';
  for (const ch of q) {
    if (/\s/.test(ch)) {
      if (!src.endsWith('\\s+')) src += '\\s+';
    } else if (ch === "'" || ch === '‘' || ch === '’') {
      src += SINGLE_QUOTES;
    } else if (ch === '"' || ch === '“' || ch === '”') {
      src += DOUBLE_QUOTES;
    } else {
      src += ch.replace(/[.*+?^${}()|[\]\\/]/, '\\$&');
    }
  }
  return new RegExp(src, 'gi');
}

export interface SearchMatches {
  starts: number[];
  ends: number[];
  capped: boolean;
}

export function findMatches(
  text: string,
  query: string,
  limits: SearchLimits = DEFAULT_SEARCH_LIMITS
): SearchMatches | null {
  const re = buildSearchPattern(query, limits);
  if (!re) return null;
  const starts: number[] = [];
  const ends: number[] = [];
  let capped = false;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[0].length === 0) {
      // defensive: no emitted pattern atom is zero-width, but never loop
      re.lastIndex++;
      continue;
    }
    if (starts.length >= limits.maxMatches) {
      // look-ahead-one: exactly maxMatches matches is not "20,000+"
      capped = true;
      break;
    }
    starts.push(m.index);
    ends.push(m.index + m[0].length);
  }
  return { starts, ends, capped };
}

// Attribute sorted match starts to bins whose starts are `binStarts`
// (sorted, deduped). Bin i owns [binStarts[i], binStarts[i+1]); matches
// before binStarts[0] fall nowhere (callers include 0 as the front-matter
// bin when they want full coverage).
export function countsByBins(starts: number[], binStarts: number[]): number[] {
  const counts = new Array<number>(binStarts.length).fill(0);
  let bin = -1;
  for (const s of starts) {
    while (bin + 1 < binStarts.length && binStarts[bin + 1] <= s) bin++;
    if (bin >= 0) counts[bin]++;
  }
  return counts;
}

export function snippetAround(text: string, start: number, end: number, context = 40): string {
  const from = Math.max(0, start - context);
  const to = Math.min(text.length, end + context);
  return text.slice(from, to).replace(/\s+/g, ' ').trim();
}
