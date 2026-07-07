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
  let from = Math.max(0, start - context);
  let to = Math.min(text.length, end + context);
  // never begin on a low surrogate or end after a lone high surrogate
  const fromCode = text.charCodeAt(from);
  if (fromCode >= 0xdc00 && fromCode <= 0xdfff) from++;
  const lastCode = text.charCodeAt(to - 1);
  if (lastCode >= 0xd800 && lastCode <= 0xdbff) to--;
  return text.slice(from, to).replace(/\s+/g, ' ').trim();
}

// ---- rendered-mode text-node offset mapping (TEA-929) ----

// Rendered mode holds a whole DOM tree in #ew-doc-text, not one text node.
// The search haystack is the concatenation of the tree's text nodes;
// `starts[i]` is node i's global UTF-16 start in that concatenation and
// `lengths[i]` its length (contiguous by construction: starts[i+1] ===
// starts[i] + lengths[i], with starts[0] === 0). Matches are stored as
// global spans over the concatenation; a Range needs per-node positions.
export interface NodeSpan {
  startNode: number;
  startOffset: number;
  endNode: number;
  endOffset: number;
}

// Largest i with starts[i] <= offset. starts is non-decreasing (equal runs
// mark zero-length nodes); the largest-index rule prefers the later,
// non-empty node at a shared boundary, so a span never starts inside an
// empty node it could avoid.
function nodeContaining(starts: number[], offset: number): number {
  let lo = 0;
  let hi = starts.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (starts[mid] <= offset) lo = mid + 1;
    else hi = mid;
  }
  return lo - 1;
}

// Map a global [start, end) UTF-16 span onto per-node Range positions. `end`
// clamps to the total length; returns null when `start` is at or past the
// total length, or when the span is empty after clamping. The end position
// attaches to the node holding the last covered character, so endOffset is
// in (0, lengths[endNode]] and every Range this produces is non-degenerate.
export function locateSpan(
  starts: number[],
  lengths: number[],
  start: number,
  end: number
): NodeSpan | null {
  const n = starts.length;
  const total = n > 0 ? starts[n - 1] + lengths[n - 1] : 0;
  if (start >= total) return null;
  const e = Math.min(end, total);
  if (e <= start) return null;
  const startNode = nodeContaining(starts, start);
  const endNode = nodeContaining(starts, e - 1);
  return {
    startNode,
    startOffset: start - starts[startNode],
    endNode,
    endOffset: e - starts[endNode],
  };
}

// Escape hatch (empty by default): a slug listed here always uses the plain
// path even when it is markdown and small enough, in case sampling flags a
// document the renderer mangles.
export const FORCE_PLAIN_SLUGS: ReadonlySet<string> = new Set<string>();
