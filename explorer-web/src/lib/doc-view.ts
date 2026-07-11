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

function lineIsBlank(text: string, start: number, end: number): boolean {
  for (let i = start; i < end; i++) {
    const c = text.charCodeAt(i);
    if (c !== 0x20 && c !== 0x09 && c !== 0x0d) return false;
  }
  return true;
}

// First non-space/tab index of the line, or `end` when none.
function lineContentStart(text: string, start: number, end: number): number {
  let i = start;
  while (i < end && (text.charCodeAt(i) === 0x20 || text.charCodeAt(i) === 0x09)) i++;
  return i;
}

function lineIsTableRow(text: string, start: number, end: number): boolean {
  return text.charCodeAt(lineContentStart(text, start, end)) === 0x7c; // '|'
}

function lineIsFenceDelimiter(text: string, start: number, end: number): boolean {
  const i = lineContentStart(text, start, end);
  const c = text.charCodeAt(i);
  if (c !== 0x60 && c !== 0x7e) return false; // '`' or '~'
  return i + 2 < end && text.charCodeAt(i + 1) === c && text.charCodeAt(i + 2) === c;
}

// TEA-989: segment cuts must be markdown-safe. Rendered mode parses each
// segment independently, so a cut inside a fenced code block or a GFM table
// mangles both neighbors. Three tiers, the LATEST valid candidate at or
// before `at` wins:
//   1. a block boundary: the start of a line whose previous line is blank,
//      outside any ```/~~~ fence (blank lines terminate GFM tables and
//      paragraphs, so tier 1 can never split either);
//   2. no blank line in the window: a line start outside a fence where the
//      two adjacent lines are not both table rows (never cuts BETWEEN table
//      rows; cutting AT a table's first row is safe);
//   3. pathological (e.g. one window-sized line): the last newline, then a
//      hard cut guarded against splitting a surrogate pair.
// Fence state is tracked from the window start; window starts are themselves
// prior safe cuts (or converter-emitted heading offsets), which sit outside
// fences, so the induction holds for balanced fences. An unbalanced stray
// delimiter degrades this window to tier 3 (the pre-TEA-989 behavior).
// The line scan is bounded by `at`, so computeSegments stays O(text length).
function findCut(text: string, from: number, at: number): number {
  let blankCut = -1;
  let calmCut = -1;
  let inFence = false;
  let prevBlank = false;
  let prevTable = false;
  let ls = from;
  while (ls < at) {
    let le = ls;
    while (le < at && text.charCodeAt(le) !== 0x0a) le++;
    const truncated = le >= at && !(le < text.length && text.charCodeAt(le) === 0x0a);
    const blank = truncated ? false : lineIsBlank(text, ls, le);
    const table = lineIsTableRow(text, ls, le);
    if (ls > from && !inFence) {
      if (prevBlank) blankCut = ls;
      if (!(prevTable && table)) calmCut = ls;
    }
    if (lineIsFenceDelimiter(text, ls, le)) inFence = !inFence;
    prevBlank = blank;
    prevTable = table;
    if (le >= at) break; // the line runs past the window; no later line start fits
    ls = le + 1;
  }
  if (blankCut > from) return blankCut;
  if (calmCut > from) return calmCut;
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

// ---- per-segment rendered mode (TEA-989) ----

// Segmented docs search RAW whole-doc text (offsets must span segments), but
// the active segment displays a rendered tree whose text differs from the raw
// slice (markdown syntax stripped). There is no exact raw-to-rendered offset
// map, so the CURRENT match is located by ordinal: the raw match's position
// among raw matches inside the segment maps onto the segment's rendered
// matches. Identity when the counts agree (the overwhelmingly common case);
// proportional-nearest when formatting splits or syntax-only matches make the
// counts diverge; null when the rendered segment has no matches to map onto.
export function pickRenderedOrdinal(
  rawOrdinal: number,
  rawCount: number,
  renderedCount: number
): number | null {
  if (renderedCount <= 0 || rawCount <= 0) return null;
  if (rawOrdinal < 0 || rawOrdinal >= rawCount) return null;
  if (rawCount === renderedCount) return rawOrdinal;
  if (rawCount === 1) return 0;
  const t = rawOrdinal / (rawCount - 1);
  return Math.min(renderedCount - 1, Math.max(0, Math.round(t * (renderedCount - 1))));
}

function normalizeTitle(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}

// TOC clicks on a rendered segment anchor on the heading ELEMENT whose text
// matches the clicked snapshot-toc title; `ordinal` disambiguates repeated
// titles ("(continued)" sections) counted among same-title entries within the
// segment. Comparison is whitespace-normalized on both sides. Returns the
// index into `titles` (rendered headings in document order) or null.
export function nthTitleIndex(titles: string[], title: string, ordinal: number): number | null {
  const wanted = normalizeTitle(title);
  let seen = 0;
  for (let i = 0; i < titles.length; i++) {
    if (normalizeTitle(titles[i]) === wanted) {
      if (seen === ordinal) return i;
      seen++;
    }
  }
  return null;
}

// Escape hatch (empty by default): a slug listed here always uses the plain
// path even when it is markdown and small enough, in case sampling flags a
// document the renderer mangles.
export const FORCE_PLAIN_SLUGS: ReadonlySet<string> = new Set<string>();
