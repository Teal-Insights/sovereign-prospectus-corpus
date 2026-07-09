// Client script for document pages. Disposable by contract: zero SQL, zero
// raw fetch, zero URL assembly (lib modules own all of it). Two render modes
// share one search/highlight/TOC machine through the active-text contract
// (TEA-929): every haystack and offset lives in `active.text` for the current
// mode.
//   - PLAIN mode (pages-source docs, docs over 1M units, force-listed slugs):
//     the raw text renders into the single #ew-doc-text container (one text
//     node; offsets map 1:1 to the node), segmented above 1M units, with
//     search over the FULL raw string and CSS Custom Highlight paints bounded
//     to the rendered segment. Behavior is unchanged.
//   - RENDERED mode (markdown docs at or under 1M units): the markdown renders
//     to a DOM tree inside #ew-doc-text; the haystack is the concatenation of
//     that tree's text nodes (indexed by a TreeWalker), so phrases split by
//     bold in the raw markdown now match, and highlight ranges span node
//     boundaries. The TOC is derived from the rendered headings. A toggle
//     switches to plain (raw) mode and back.
// The live region #ew-doc-live is the accessible channel: highlight paints
// are not reliably exposed to AT. Typing never navigates: only explicit
// actions (match/segment buttons, TOC entries, the view toggle, a q= restore)
// scroll or move focus.

import {
  COUNTS_PAST_CAP_NOTE,
  DRIFT_NOTICE,
  FRONT_MATTER_LABEL,
  HIGHLIGHT_SUPPORT_NOTE,
  MIN_QUERY_HINT,
  SEGMENTS_NOTICE,
  TOC_JUMP_FALLBACK_NOTE,
  VIEW_FORMATTED_LABEL,
  VIEW_RAW_LABEL,
  absenceCopy,
  highlightCapNote,
  highlightCapNoteWhole,
  loadGateLabel,
  loadingText,
  matchCountCopy,
  matchPositionCopy,
  matchPositionLabel,
  segmentLabel,
  viewModeAnnouncement,
} from '../lib/format';
import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import {
  FORCE_PLAIN_SLUGS,
  computeSegments,
  countsByBins,
  findMatches,
  locateSpan,
  needsSegments,
  sanitizeToc,
  segmentForOffset,
  snippetAround,
  type SearchMatches,
  type Segment,
  type TocEntryLike,
} from '../lib/doc-view';
import { renderDocMarkdown } from '../lib/md-render';
import DOMPurify from 'dompurify';
import { fetchDocText, loadManifest, type Manifest } from '../lib/snapshot-client';
import { decodeDocQuery, encodeDocQuery } from '../lib/url-state';
import { renderError, renderNotice, userMessageOf } from './dom';

const GATE_BYTES = 5_000_000;
const HIGHLIGHT_CAP = 2_000;
const TOC_FILTER_THRESHOLD = 100;

const supportsHighlights = typeof CSS !== 'undefined' && 'highlights' in CSS;

// ---- state ----
let rawText: string | null = null;
window.__ewDoc = { getRawText: () => rawText };
let toc: TocEntryLike[] = [];
let segments: Segment[] = [];
let segIndex = 0;
let segmented = false;
let matches: SearchMatches | null = null;
let matchIndex = -1;
// Typing computes results but never navigates; the first Next/Prev (or a
// q= restore) performs the first jump.
let navigated = false;
// The last query actually executed: a trailing debounce tick for an
// unchanged query must not re-run the search (it would reset navigation
// state right after a Next click that landed inside the debounce window).
let lastRanQuery: string | null = null;

// Active-text contract (TEA-929). Every haystack and every offset consumer
// reads `active.text` for the current mode. In plain/segmented mode
// active.text is the full raw string (search spans segment boundaries). In
// rendered mode active.text is the concatenation of the rendered DOM text
// nodes (markdown syntax stripped), indexed 1:1 by the three arrays below;
// offsets map onto renderedNodes so every Range is valid.
let active: { text: string; mode: 'plain' | 'rendered' } = { text: '', mode: 'plain' };
let renderedNodes: Text[] = [];
let renderedStarts: number[] = [];
let renderedLengths: number[] = [];
// Whether rendered mode is available for this doc (drives the toggle) and,
// when it is, whether the formatted view is currently shown.
let renderedEligible = false;
let formatted = true;

// TOC bins align 1:1 with the rendered list rows: a synthetic front-matter
// row exists exactly when text precedes the first entry, so per-section
// counts always sum to the total. In rendered mode the rows are derived from
// the rendered headings (renderedTocRows); in plain mode from the snapshot
// toc (tocRows()).
interface TocRow {
  title: string;
  level: number;
  offset: number;
}
let renderedTocRows: TocRow[] = [];

// One manifest read per page view, shared by the drift check and text load.
let manifestPromise: Promise<Manifest> | null = null;
function getManifest(): Promise<Manifest> {
  manifestPromise ??= loadManifest(PUBLIC_DATA_BASE_URL);
  return manifestPromise;
}

function byId<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

// ---- live region (one per page; updates replace text, 500 ms idle) ----
let announceTimer: number | undefined;
function announce(text: string): void {
  const live = byId<HTMLDivElement>('ew-doc-live');
  if (!live) return;
  window.clearTimeout(announceTimer);
  announceTimer = window.setTimeout(() => {
    live.textContent = text;
  }, 500);
}

async function driftCheck(): Promise<void> {
  try {
    const manifest = await getManifest();
    const stamped = document.body.dataset.buildGeneratedAt;
    if (stamped && manifest.generated_at !== stamped) {
      const notices = byId<HTMLDivElement>('ew-doc-notices');
      if (notices) renderNotice(notices, DRIFT_NOTICE);
    }
  } catch {
    // Advisory; text loading reports manifest errors.
  }
}

// Back to browse: a same-origin referrer from the browse page AND a real
// prior history entry mean history.back() restores filters and scroll via
// bfcache. A new tab (middle-click) has the referrer but history.length 1;
// it must fall through to the plain link or the control is dead.
function wireBackLink(): void {
  const back = byId<HTMLAnchorElement>('ew-back');
  back?.addEventListener('click', (e) => {
    if (!document.referrer || history.length <= 1) return;
    try {
      const ref = new URL(document.referrer);
      if (ref.origin === location.origin && ref.pathname === '/') {
        e.preventDefault();
        history.back();
      }
    } catch {
      // malformed referrer: use the plain link
    }
  });
}

function main(): void {
  void driftCheck();
  wireBackLink();

  const container = byId<HTMLDivElement>('ew-doc-text');
  if (!container) return; // has_text=false pages: drift check + back link only

  const notices = byId<HTMLDivElement>('ew-doc-notices')!;
  const searchInput = byId<HTMLInputElement>('ew-doc-search-input')!;
  const searchPrev = byId<HTMLButtonElement>('ew-doc-search-prev')!;
  const searchNext = byId<HTMLButtonElement>('ew-doc-search-next')!;
  const searchCount = byId<HTMLSpanElement>('ew-doc-search-count')!;
  const searchPos = byId<HTMLSpanElement>('ew-doc-search-pos')!;
  const searchHint = byId<HTMLParagraphElement>('ew-doc-search-hint')!;
  const tocList = byId<HTMLOListElement>('ew-doc-toc')!;
  const tocFilter = byId<HTMLInputElement>('ew-doc-toc-filter')!;
  const segNav = byId<HTMLParagraphElement>('ew-seg-nav')!;
  const segPrev = byId<HTMLButtonElement>('ew-seg-prev')!;
  const segNext = byId<HTMLButtonElement>('ew-seg-next')!;
  const segLabel = byId<HTMLSpanElement>('ew-seg-label')!;
  const segNotice = byId<HTMLDivElement>('ew-seg-notice')!;
  const viewToggle = byId<HTMLButtonElement>('ew-view-toggle')!;
  const viewToggleRow = byId<HTMLParagraphElement>('ew-view-toggle-row')!;

  const slug = container.dataset.slug ?? '';
  const bytes = Number(container.dataset.textBytes ?? 0);
  const textSource = container.dataset.textSource ?? null;

  // Shown BEFORE the user invests in typing a query.
  if (!supportsHighlights) renderNotice(notices, HIGHLIGHT_SUPPORT_NOTE);

  function focusText(): void {
    container!.focus({ preventScroll: true });
  }

  function textNode(): Text | null {
    const node = container!.firstChild;
    return node && node.nodeType === Node.TEXT_NODE ? (node as Text) : null;
  }

  function segStartOffset(): number {
    return Number(container!.dataset.segStart ?? 0);
  }

  function rangeFor(node: Text, segStart: number, start: number, end: number): Range | null {
    const len = node.data.length;
    const localStart = start - segStart;
    const localEnd = Math.min(end - segStart, len); // straddlers clamp to the segment end
    if (localStart < 0 || localStart >= len || localEnd <= localStart) return null;
    const range = document.createRange();
    range.setStart(node, localStart);
    range.setEnd(node, localEnd);
    return range;
  }

  // Mode-aware Range builder over an [start, end) span in active.text. In
  // rendered mode the span maps onto the rendered text-node index (matches can
  // cross node boundaries; Range supports that). In plain mode it delegates to
  // the single-text-node path (segment-windowed), so plain behavior is
  // unchanged.
  function spanRange(start: number, end: number): Range | null {
    if (active.mode === 'rendered') {
      const loc = locateSpan(renderedStarts, renderedLengths, start, end);
      if (!loc) return null;
      const range = document.createRange();
      range.setStart(renderedNodes[loc.startNode], loc.startOffset);
      range.setEnd(renderedNodes[loc.endNode], loc.endOffset);
      return range;
    }
    const node = textNode();
    if (!node) return null;
    return rangeFor(node, segStartOffset(), start, end);
  }

  function lowerBound(arr: number[], target: number): number {
    let lo = 0;
    let hi = arr.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid] < target) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  function selectionFallback(): void {
    // Always clear first: a stale selection visually asserts a match that
    // no longer exists (council PR gate).
    const sel = window.getSelection();
    sel?.removeAllRanges();
    if (!matches || matchIndex < 0 || !navigated) return;
    const r = spanRange(matches.starts[matchIndex], matches.ends[matchIndex]);
    if (r) sel?.addRange(r);
  }

  let capNoteShown = false;
  function updateHint(): void {
    if (matches?.capped) {
      searchHint.textContent = COUNTS_PAST_CAP_NOTE;
      searchHint.hidden = false;
    } else if (capNoteShown) {
      // Rendered mode has no segments, so the cap note must not say
      // "in this segment" (the cap is over the whole document).
      searchHint.textContent =
        active.mode === 'rendered'
          ? highlightCapNoteWhole(HIGHLIGHT_CAP)
          : highlightCapNote(HIGHLIGHT_CAP);
      searchHint.hidden = false;
    } else {
      searchHint.hidden = true;
    }
  }

  function applyHighlights(): void {
    capNoteShown = false;
    if (!supportsHighlights) {
      selectionFallback();
      updateHint();
      return;
    }
    CSS.highlights.delete('ew-match');
    CSS.highlights.delete('ew-match-current');
    // Never build ranges over Loading/error DOM states.
    if (!matches || rawText === null) {
      updateHint();
      return;
    }
    const { starts, ends } = matches;
    const matchHl = new Highlight();
    const currentHl = new Highlight();
    matchHl.priority = 1;
    currentHl.priority = 2;
    if (active.mode === 'rendered') {
      // Whole-document paint in match order from index 0, capped at
      // HIGHLIGHT_CAP; the current match is always painted regardless.
      let painted = 0;
      for (let i = 0; i < starts.length; i++) {
        if (i === matchIndex) continue; // current match lives only in ew-match-current
        if (painted >= HIGHLIGHT_CAP) {
          capNoteShown = true;
          break;
        }
        const r = spanRange(starts[i], ends[i]);
        if (r) {
          matchHl.add(r);
          painted++;
        }
      }
      if (matchIndex >= 0) {
        const r = spanRange(starts[matchIndex], ends[matchIndex]);
        if (r) currentHl.add(r);
      }
    } else {
      const node = textNode();
      if (!node) {
        updateHint();
        return;
      }
      const segStart = segStartOffset();
      const segEnd = segStart + node.data.length;
      let painted = 0;
      for (let i = lowerBound(starts, segStart); i < starts.length && starts[i] < segEnd; i++) {
        if (i === matchIndex) continue; // current match lives only in ew-match-current
        if (painted >= HIGHLIGHT_CAP) {
          capNoteShown = true;
          break;
        }
        const r = rangeFor(node, segStart, starts[i], ends[i]);
        if (r) {
          matchHl.add(r);
          painted++;
        }
      }
      // The CURRENT match is always painted, regardless of the cap.
      if (matchIndex >= 0 && starts[matchIndex] >= segStart && starts[matchIndex] < segEnd) {
        const r = rangeFor(node, segStart, starts[matchIndex], ends[matchIndex]);
        if (r) currentHl.add(r);
      }
    }
    CSS.highlights.set('ew-match', matchHl);
    CSS.highlights.set('ew-match-current', currentHl);
    updateHint();
  }

  function jumpOffsetPx(): number {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--ew-jump-offset');
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : 80;
  }

  function scrollToOffset(off: number): void {
    if (active.mode === 'rendered') {
      // Scroll to the text node holding `off` via a one-unit Range; a Range
      // across nodes is fine here since we only read its top edge.
      const clamped = Math.min(Math.max(off, 0), Math.max(active.text.length - 1, 0));
      const loc = locateSpan(renderedStarts, renderedLengths, clamped, clamped + 1);
      if (!loc) return;
      const range = document.createRange();
      range.setStart(renderedNodes[loc.startNode], loc.startOffset);
      range.setEnd(renderedNodes[loc.endNode], loc.endOffset);
      const rect = range.getBoundingClientRect();
      window.scrollTo({ top: rect.top + window.scrollY - jumpOffsetPx() });
      return;
    }
    const node = textNode();
    if (!node || node.data.length === 0) return;
    const segStart = segStartOffset();
    const local = Math.min(Math.max(off - segStart, 0), node.data.length - 1);
    const range = document.createRange();
    range.setStart(node, local);
    range.setEnd(node, Math.min(local + 1, node.data.length));
    const rect = range.getBoundingClientRect(); // forces layout; correct immediately
    window.scrollTo({ top: rect.top + window.scrollY - jumpOffsetPx() });
  }

  function segmentMatchCount(): number | null {
    if (!matches || matches.capped || matches.starts.length === 0 || !segmented) return null;
    return countsByBins(
      matches.starts,
      segments.map((s) => s.start)
    )[segIndex];
  }

  function updateSegNav(): void {
    if (!segmented) return;
    segNav.hidden = false;
    segPrev.setAttribute('aria-disabled', String(segIndex === 0));
    segNext.setAttribute('aria-disabled', String(segIndex >= segments.length - 1));
    segLabel.textContent = segmentLabel(segIndex + 1, segments.length, segmentMatchCount());
  }

  function renderSegment(i: number): void {
    if (rawText === null) return;
    segIndex = Math.min(Math.max(i, 0), segments.length - 1);
    const seg = segments[segIndex];
    container!.textContent = rawText.slice(seg.start, seg.end);
    container!.dataset.segStart = String(seg.start);
    updateSegNav();
    applyHighlights();
  }

  function jumpToOffset(off: number, label?: string): void {
    if (rawText === null) return;
    if (off < 0 || off >= Math.max(active.text.length, 1)) {
      if (segmented) renderSegment(0);
      renderNotice(notices, TOC_JUMP_FALLBACK_NOTE);
      window.scrollTo({ top: 0 });
      focusText();
      return;
    }
    if (segmented) {
      const target = segmentForOffset(segments, off);
      if (target !== segIndex) renderSegment(target);
    }
    scrollToOffset(off);
    focusText();
    if (label) {
      announce(
        segmented ? `${label}. ${segmentLabel(segIndex + 1, segments.length, null)}` : label
      );
    }
  }

  // Rendered mode derives rows from the rendered headings (built once at
  // inject time, front-matter row included); plain mode derives them from the
  // snapshot toc.
  function tocRows(): TocRow[] {
    if (active.mode === 'rendered') return renderedTocRows;
    if (!toc.length) return [];
    const rows: TocRow[] = [];
    if (toc[0].offset_utf16 > 0) rows.push({ title: FRONT_MATTER_LABEL, level: 2, offset: 0 });
    for (const e of toc) rows.push({ title: e.title, level: e.level, offset: e.offset_utf16 });
    return rows;
  }

  function renderToc(): void {
    tocList.innerHTML = '';
    const rows = tocRows();
    if (!rows.length) {
      tocList.textContent = tocList.dataset.emptyLabel ?? '';
      return;
    }
    const frag = document.createDocumentFragment();
    for (const row of rows) {
      const li = document.createElement('li');
      li.className = `ew-toc-level-${Math.min(Math.max(row.level - 2, 0), 3)}`;
      li.dataset.needle = row.title.toLowerCase(); // cached for the filter
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = row.title;
      btn.addEventListener('click', () => jumpToOffset(row.offset, row.title));
      const count = document.createElement('span');
      count.className = 'ew-toc-count ew-muted';
      li.append(btn, count);
      frag.appendChild(li);
    }
    tocList.appendChild(frag);
    const entryCount = active.mode === 'rendered' ? renderedTocRows.length : toc.length;
    // Reset on every (re)build: a mode toggle can swap in a shorter list, so a
    // left-over value or a still-visible filter would contradict the freshly
    // rebuilt, unfiltered rows (council PR gate).
    tocFilter.value = '';
    tocFilter.hidden = entryCount <= TOC_FILTER_THRESHOLD;
  }

  // Wired ONCE (a gate-retry path re-runs renderToc; a listener there would
  // stack). Debounced: 2,001 rows per raw keystroke is real layout work.
  let tocFilterTimer: number | undefined;
  tocFilter.addEventListener('input', () => {
    window.clearTimeout(tocFilterTimer);
    tocFilterTimer = window.setTimeout(() => {
      const needle = tocFilter.value.trim().toLowerCase();
      for (const li of tocList.children) {
        const el = li as HTMLElement;
        el.hidden = needle !== '' && !(el.dataset.needle ?? '').includes(needle);
      }
    }, 250);
  });

  // Counts update IN PLACE (the list is never rebuilt per keystroke), and
  // are suppressed when the scan capped: a truncated scan would show false
  // zeros on later sections.
  function updateTocCounts(): void {
    const countEls = tocList.querySelectorAll<HTMLSpanElement>('.ew-toc-count');
    if (!matches || matches.starts.length === 0 || matches.capped) {
      for (const el of countEls) el.textContent = '';
      return;
    }
    const rows = tocRows();
    const counts = countsByBins(
      matches.starts,
      rows.map((r) => r.offset)
    );
    countEls.forEach((el, i) => {
      el.textContent = counts[i] > 0 ? ` (${counts[i].toLocaleString('en-US')})` : '';
    });
  }

  function goToMatch(i: number): void {
    if (!matches || matches.starts.length === 0 || rawText === null) return;
    navigated = true;
    const n = matches.starts.length;
    matchIndex = ((i % n) + n) % n; // navigation wraps; the position label keeps it honest
    const off = matches.starts[matchIndex];
    if (segmented) {
      const target = segmentForOffset(segments, off);
      if (target !== segIndex) renderSegment(target);
      else applyHighlights();
    } else {
      applyHighlights();
    }
    scrollToOffset(off);
    focusText();
    updateSegNav();
    searchPos.textContent = matchPositionLabel(matchIndex + 1, n, matches.capped);
    announce(
      matchPositionCopy(
        matchIndex + 1,
        n,
        matches.capped,
        snippetAround(active.text, off, matches.ends[matchIndex])
      )
    );
  }

  function clearSearchUi(): void {
    matches = null;
    matchIndex = -1;
    navigated = false;
    searchCount.textContent = '';
    searchPos.textContent = '';
    searchHint.hidden = true;
    searchPrev.hidden = true;
    searchNext.hidden = true;
    applyHighlights();
    updateTocCounts();
    updateSegNav();
  }

  // Typing path: computes and paints, announces the count, but NEVER
  // scrolls or moves focus (a debounced keystroke stealing focus from the
  // input kills continued typing; council PR gate).
  function runSearch(q: string): void {
    if (rawText === null) return;
    lastRanQuery = q;
    if (!q.trim()) {
      clearSearchUi();
      return;
    }
    const found = findMatches(active.text, q);
    if (found === null) {
      clearSearchUi();
      searchHint.textContent = MIN_QUERY_HINT;
      searchHint.hidden = false;
      announce(MIN_QUERY_HINT);
      return;
    }
    matches = found;
    matchIndex = 0;
    navigated = false;
    const total = found.starts.length;
    if (total === 0) {
      matchIndex = -1;
      searchPrev.hidden = true;
      searchNext.hidden = true;
      searchPos.textContent = '';
      searchCount.textContent = absenceCopy(q);
      announce(absenceCopy(q));
      applyHighlights();
      updateTocCounts();
      updateSegNav();
      return;
    }
    searchCount.textContent = matchCountCopy(total, found.capped, q);
    searchPos.textContent = '';
    announce(matchCountCopy(total, found.capped, q));
    searchPrev.hidden = false;
    searchNext.hidden = false;
    updateTocCounts();
    updateSegNav();
    applyHighlights(); // paints match 1 as current wherever it is; no scroll
  }

  // ONE debounce timer drives both the search and the URL write; cancelled
  // on popstate and pagehide so a stale q never stamps a restored entry.
  let inputTimer: number | undefined;
  function writeQ(q: string): void {
    const qs = encodeDocQuery(location.search, q.trim() ? q : '');
    if (qs === location.search.replace(/^\?/, '')) return; // skip no-op writes
    try {
      history.replaceState(null, '', qs ? `?${qs}` : location.pathname);
    } catch {
      // WebKit rate-limits history writes; the UI must survive.
    }
  }
  searchInput.addEventListener('input', () => {
    window.clearTimeout(inputTimer);
    inputTimer = window.setTimeout(() => {
      const q = searchInput.value;
      if (q !== lastRanQuery) runSearch(q);
      writeQ(q);
    }, 250);
  });
  window.addEventListener('popstate', () => {
    window.clearTimeout(inputTimer);
    const q = decodeDocQuery(location.search);
    searchInput.value = q;
    if (rawText !== null) runSearch(q); // popstate never writes history
  });
  window.addEventListener('pagehide', () => window.clearTimeout(inputTimer));
  // Enter mirrors browser find: run any pending search immediately, then
  // navigate (first activation lands on match 1).
  searchInput.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    window.clearTimeout(inputTimer);
    const q = searchInput.value;
    if (q !== lastRanQuery) {
      runSearch(q);
      writeQ(q);
    }
    if (matches && matches.starts.length > 0) goToMatch(navigated ? matchIndex + 1 : 0);
  });

  // First activation jumps to match 1; after that Prev/Next step and wrap.
  searchPrev.addEventListener('click', () => goToMatch(navigated ? matchIndex - 1 : 0));
  searchNext.addEventListener('click', () => goToMatch(navigated ? matchIndex + 1 : 0));

  segPrev.addEventListener('click', () => {
    // Rendered mode leaves segments empty; the nav is hidden there, but guard
    // against a programmatic click reaching segments[-1] (council PR gate).
    if (!segmented || segPrev.getAttribute('aria-disabled') === 'true') return;
    renderSegment(segIndex - 1);
    announce(segmentLabel(segIndex + 1, segments.length, segmentMatchCount()));
    scrollToOffset(segments[segIndex].start);
    focusText();
  });
  segNext.addEventListener('click', () => {
    if (!segmented || segNext.getAttribute('aria-disabled') === 'true') return;
    renderSegment(segIndex + 1);
    announce(segmentLabel(segIndex + 1, segments.length, segmentMatchCount()));
    scrollToOffset(segments[segIndex].start);
    focusText();
  });

  // ---- rendered mode (markdown docs at or under 1M units) ----

  // Build the text-node index over ALL text nodes of the container, including
  // whitespace-only nodes: the newlines marked emits between block elements
  // become natural word separators in the haystack. NEVER inject synthetic
  // characters into the concatenation; offsets must map 1:1 onto the DOM text
  // nodes or every Range breaks.
  function buildRenderedIndex(): void {
    renderedNodes = [];
    renderedStarts = [];
    renderedLengths = [];
    const parts: string[] = [];
    let acc = 0;
    const walker = document.createTreeWalker(container!, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode()) !== null) {
      const t = node as Text;
      renderedNodes.push(t);
      renderedStarts.push(acc);
      renderedLengths.push(t.data.length);
      parts.push(t.data);
      acc += t.data.length;
    }
    active = { text: parts.join(''), mode: 'rendered' };
  }

  // A heading's offset is its first text node's global start; a heading with
  // no text node of its own uses the next text node in document order.
  function headingOffset(h: HTMLElement, nodeStart: Map<Text, number>): number {
    const w = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    const first = w.nextNode() as Text | null;
    if (first && nodeStart.has(first)) return nodeStart.get(first)!;
    for (const t of renderedNodes) {
      if (h.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING) {
        return nodeStart.get(t) ?? active.text.length;
      }
    }
    return active.text.length;
  }

  function buildRenderedToc(): void {
    renderedTocRows = [];
    const headings = container!.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6');
    if (headings.length === 0) return;
    const nodeStart = new Map<Text, number>();
    for (let i = 0; i < renderedNodes.length; i++) nodeStart.set(renderedNodes[i], renderedStarts[i]);
    const rows: TocRow[] = [];
    headings.forEach((h, i) => {
      h.id = `ew-h-${i}`;
      // Skip headings with no text: they make no meaningful contents entry, and
      // headingOffset would fall back to an O(text-nodes) document scan for each
      // one (quadratic across a run of blank `##` lines in machine-converted
      // text, plus a blank row that mis-scrolls on click; council PR gate).
      const title = h.textContent ?? '';
      if (!title.trim()) return;
      rows.push({ title, level: Number(h.tagName[1]), offset: headingOffset(h, nodeStart) });
    });
    if (rows.length === 0) return;
    // Front-matter row exactly when text precedes the first heading.
    renderedTocRows =
      rows[0].offset > 0 ? [{ title: FRONT_MATTER_LABEL, level: 2, offset: 0 }, ...rows] : rows;
  }

  function renderRendered(): void {
    // Two layers of defense against XSS in untrusted filing text: the renderer
    // never emits raw HTML, and DOMPurify sanitizes the result before it
    // touches the live DOM.
    const clean = DOMPurify.sanitize(renderDocMarkdown(rawText!), { ADD_ATTR: ['rel'] });
    const wrapper = document.createElement('div');
    wrapper.className = 'ew-doc-rendered';
    wrapper.innerHTML = clean;
    container!.replaceChildren(wrapper);
    // The single-text-node / data-seg-start invariant does not hold in
    // rendered mode; drop the stale attribute so plain-mode consumers do not
    // misread it (mode-scoped contract in env.d.ts / ARCHITECTURE.md).
    delete container!.dataset.segStart;
    segmented = false;
    buildRenderedIndex();
    buildRenderedToc();
  }

  function renderPlainFull(): void {
    // Rendered-eligible docs are always at or under 1M units, so plain mode
    // for them is the single-node full render (never segmented).
    segmented = false;
    segments = [{ start: 0, end: rawText!.length }];
    segIndex = 0;
    container!.textContent = rawText!;
    container!.dataset.segStart = '0';
    active = { text: rawText!, mode: 'plain' };
  }

  function updateToggleLabel(): void {
    // The label names the mode the button switches TO (browser find convention).
    // No aria-pressed: a self-describing dynamic label plus a pressed state give
    // assistive tech contradictory cues (council PR gate).
    viewToggle.textContent = formatted ? VIEW_RAW_LABEL : VIEW_FORMATTED_LABEL;
  }

  function showToggle(): void {
    // Unhide the whole row, not just the button: the row is hidden by default so
    // ineligible plain docs do not carry an empty paragraph above the text
    // (frozen-path polish; council PR gate).
    viewToggleRow.hidden = false;
    viewToggle.hidden = false;
    updateToggleLabel();
  }

  // The toggle re-renders the container in the other mode, rebuilds the TOC,
  // re-runs the last executed query with typing-path semantics (no scroll, no
  // focus steal), resets match navigation to un-navigated, and announces the
  // mode change. It is session-local and never written to the URL.
  function setMode(nextFormatted: boolean): void {
    if (nextFormatted === formatted) return;
    formatted = nextFormatted;
    if (formatted) renderRendered();
    else renderPlainFull();
    renderToc();
    updateToggleLabel();
    matches = null;
    matchIndex = -1;
    navigated = false;
    if (lastRanQuery !== null && lastRanQuery.trim()) {
      runSearch(lastRanQuery);
    } else {
      clearSearchUi();
    }
    // The mode announcement replaces any count announcement runSearch queued
    // (announce debounces and replaces the pending live-region text).
    announce(viewModeAnnouncement(formatted));
  }
  viewToggle.addEventListener('click', () => setMode(!formatted));

  function renderGateButton(target: HTMLElement): void {
    target.textContent = '';
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = loadGateLabel(bytes);
    button.addEventListener('click', () => {
      button.remove();
      // Focus rule: the click removed the focused element; the loading
      // announcement + post-load focus hand-off replace it.
      announce(loadingText(bytes));
      void loadText(true);
    });
    target.appendChild(button);
  }

  async function loadText(afterGate: boolean): Promise<void> {
    container!.textContent = loadingText(bytes);
    try {
      const manifest = await getManifest();
      const result = await fetchDocText(PUBLIC_DATA_BASE_URL, slug, manifest.generated_at);

      rawText = result.doc.text;
      toc = sanitizeToc(result.doc.toc ?? [], rawText.length);
      segmented = needsSegments(rawText.length);
      // Rendered mode iff the text is markdown AND fits the full-render
      // ceiling AND is not force-listed. Everything else keeps the plain path
      // with zero behavior change.
      renderedEligible = textSource === 'markdown' && !segmented && !FORCE_PLAIN_SLUGS.has(slug);
      active = { text: rawText, mode: 'plain' }; // default; renderRendered overrides

      // renderMs covers parse + inject + index build in rendered mode, and the
      // segment/full render in plain mode.
      const t0 = performance.now();
      if (renderedEligible) {
        formatted = true;
        renderRendered();
      } else if (segmented) {
        segments = computeSegments(rawText, toc);
        renderNotice(segNotice, SEGMENTS_NOTICE);
        renderSegment(0);
      } else {
        segments = [{ start: 0, end: rawText.length }];
        segIndex = 0;
        container!.textContent = rawText;
        container!.dataset.segStart = '0';
      }
      const renderMs = performance.now() - t0;
      renderToc();
      if (renderedEligible) showToggle();
      searchInput.disabled = false;

      window.__ewDocMetrics = {
        fetchMs: result.fetchMs,
        parseMs: result.parseMs,
        renderMs,
        stringLength: result.stringLength,
      };

      // q restores only after the text exists; on gated docs that means
      // only after the user consented to the download. A q restore IS an
      // explicit navigation; zero-match and too-short restores still need
      // a focus destination after the gate button removed itself.
      const q0 = decodeDocQuery(location.search);
      if (q0) {
        searchInput.value = q0;
        runSearch(q0);
        if (matches && matches.starts.length > 0) {
          goToMatch(0);
        } else if (afterGate) {
          focusText();
        }
      } else if (afterGate) {
        focusText();
      }
    } catch (e) {
      const message = userMessageOf(e, 'Could not load the document text from the data host.');
      searchInput.disabled = true; // search over a failed load stays off
      renderError(container!, message);
      announce(message); // the live region must not stay stuck on "Loading..."
      if (bytes > GATE_BYTES) {
        // Leave a retry affordance; a transient failure on a 29 MB document
        // must not require a full page reload. Focus it: the gate click
        // removed the previously focused element.
        const retry = document.createElement('p');
        container!.appendChild(retry);
        renderGateButton(retry);
        retry.querySelector('button')?.focus();
      }
    }
  }

  if (bytes > GATE_BYTES) {
    renderGateButton(container);
  } else {
    void loadText(false);
  }
}

main();
