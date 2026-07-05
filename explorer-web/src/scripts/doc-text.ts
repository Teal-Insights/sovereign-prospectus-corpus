// Client script for document pages. Disposable by contract: zero SQL, zero
// raw fetch, zero URL assembly (lib modules own all of it). Renders the raw
// text into the single #ew-doc-text container (one text node; offsets in
// UTF-16 string space map 1:1 to the node), segmented above 1M units, with
// in-document search over the FULL raw string and CSS Custom Highlight
// paints bounded to the rendered segment. The live region #ew-doc-live is
// the accessible channel: highlight paints are not reliably exposed to AT.
// Typing never navigates: only explicit actions (match/segment buttons, TOC
// entries, a q= restore) scroll or move focus.

import {
  COUNTS_PAST_CAP_NOTE,
  DRIFT_NOTICE,
  FRONT_MATTER_LABEL,
  HIGHLIGHT_SUPPORT_NOTE,
  MIN_QUERY_HINT,
  SEGMENTS_NOTICE,
  TOC_JUMP_FALLBACK_NOTE,
  absenceCopy,
  highlightCapNote,
  loadGateLabel,
  loadingText,
  matchCountCopy,
  matchPositionCopy,
  matchPositionLabel,
  segmentLabel,
} from '../lib/format';
import { PUBLIC_DATA_BASE_URL } from '../lib/config';
import {
  computeSegments,
  countsByBins,
  findMatches,
  needsSegments,
  sanitizeToc,
  segmentForOffset,
  snippetAround,
  type SearchMatches,
  type Segment,
  type TocEntryLike,
} from '../lib/doc-view';
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

  const slug = container.dataset.slug ?? '';
  const bytes = Number(container.dataset.textBytes ?? 0);

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
    const node = textNode();
    if (!node) return;
    const segStart = segStartOffset();
    const r = rangeFor(node, segStart, matches.starts[matchIndex], matches.ends[matchIndex]);
    if (r) sel?.addRange(r);
  }

  let capNoteShown = false;
  function updateHint(): void {
    if (matches?.capped) {
      searchHint.textContent = COUNTS_PAST_CAP_NOTE;
      searchHint.hidden = false;
    } else if (capNoteShown) {
      searchHint.textContent = highlightCapNote(HIGHLIGHT_CAP);
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
    const node = textNode();
    // Never build ranges over Loading/error DOM states.
    if (!matches || rawText === null || !node) {
      updateHint();
      return;
    }
    const segStart = segStartOffset();
    const segEnd = segStart + node.data.length;
    const { starts, ends } = matches;
    const matchHl = new Highlight();
    const currentHl = new Highlight();
    matchHl.priority = 1;
    currentHl.priority = 2;
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
    if (off < 0 || off >= Math.max(rawText.length, 1)) {
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

  // TOC bins align 1:1 with the rendered list rows: a synthetic front-matter
  // row exists exactly when text precedes the first entry, so per-section
  // counts always sum to the total.
  interface TocRow {
    title: string;
    level: number;
    offset: number;
  }
  function tocRows(): TocRow[] {
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
    if (toc.length > TOC_FILTER_THRESHOLD) tocFilter.hidden = false;
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
        snippetAround(rawText, off, matches.ends[matchIndex])
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
    const found = findMatches(rawText, q);
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
    if (segPrev.getAttribute('aria-disabled') === 'true') return;
    renderSegment(segIndex - 1);
    announce(segmentLabel(segIndex + 1, segments.length, segmentMatchCount()));
    scrollToOffset(segments[segIndex].start);
    focusText();
  });
  segNext.addEventListener('click', () => {
    if (segNext.getAttribute('aria-disabled') === 'true') return;
    renderSegment(segIndex + 1);
    announce(segmentLabel(segIndex + 1, segments.length, segmentMatchCount()));
    scrollToOffset(segments[segIndex].start);
    focusText();
  });

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

      const t0 = performance.now();
      if (segmented) {
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
