# TEA-989 design note: per-segment rendered mode for >1M markdown docs

Date: 2026-07-11. Author: Fable (architect+builder). Status: approved-to-build
unless Teal objects; no decision below required a stop-and-ask under the
issue's design constraints.

## Problem

Docs over `fullRenderMax = 1_000_000` UTF-16 units fall to the segmented
PLAIN path and print raw markdown. 620 docs affected (502 at 1-2M, 105 at
2-5M, 13 >5M behind the click gate). Goal: give segmented markdown docs a
RENDERED mode via per-segment markdown rendering, keeping the raw toggle,
without touching the at-or-under-1M paths, the 30 pages-source docs, or the
byte-for-byte raw contract.

## Mode matrix (after this change)

| size | markdown source | pages source |
|---|---|---|
| <= 1M units | whole-doc rendered + raw toggle (UNCHANGED) | plain full (UNCHANGED) |
| > 1M units | NEW: segmented rendered (default Formatted) + raw toggle | segmented plain (UNCHANGED) |

Eligibility becomes `renderedEligible = textSource === 'markdown' &&
!FORCE_PLAIN_SLUGS.has(slug)` (the `!segmented` clause is removed);
`segmented` stays `needsSegments(len)`. Raw mode on a segmented doc IS the
existing segmented plain path, byte for byte (`rawText.slice(seg.start,
seg.end)` into one text node with `data-seg-start`).

## Decision 1: markdown-safe segment boundaries

`findCut` today cuts at the last newline before the target (hard cut as
fallback). That can land inside a GFM table or a fenced code block, which
would mangle both adjacent segments' rendering. Verified NOT safe; fixed.

New three-tier cut inside `computeSegments`' oversized-window loop, scanning
the window linearly (O(len) overall) while tracking fence state:

1. Preferred: the start of a line whose previous line is blank, outside any
   ```/~~~ fence. Blank-line cuts can never split a table (GFM tables are
   contiguous non-blank lines) or a paragraph, and fence tracking excludes
   blank lines inside code fences.
2. Fallback (no blank line in the window): a newline outside a fence where
   neither adjacent line starts with `|` (avoids mid-table cuts).
3. Last resort (pathological, e.g. one 500K+ line): the existing
   last-newline-then-hard-cut behavior with the surrogate-pair guard.

Section boundaries taken from TOC offsets are heading line starts and are
markdown-safe by construction (converter-emitted top-level headings).
Segments still tile the text exactly; the raw contract is untouched because
segment boundaries only move, never drop or duplicate text. Unit-tested
against fixtures with a table and a fence straddling the target size, plus
all existing computeSegments tests unchanged.

## Decision 2: offsets and the per-segment rendered index (the crux)

There is no exact raw-to-rendered offset map (marked has no source maps),
and rendering ALL segments up front to build a whole-doc rendered haystack
is exactly the perf wall fullRenderMax exists for. So:

- **Search, counts, TOC counts, match navigation, and segment attribution
  stay in RAW whole-doc space**, exactly as segmented plain mode today
  (`active.text = rawText`). This is what "keep the whole-doc match offsets
  correct" requires; `countsByBins`, `segmentForOffset`, `segmentLabel`
  match counts, and `?q=` restore all work unchanged.
- A new mode value `seg-rendered` joins the active-text contract. The
  ACTIVE segment renders through the same `renderDocMarkdown` ->
  `DOMPurify.sanitize` -> `.ew-doc-rendered` wrapper pipeline, then
  `buildRenderedIndex` (refactored to return the concatenation) builds
  `renderedNodes/renderedStarts/renderedLengths` scoped to the segment plus
  `segRenderedText`.
- **Painting** re-runs the executed query over `segRenderedText`
  (`segMatches`, rendered-local offsets) and paints via `locateSpan` over
  the segment index, capped at HIGHLIGHT_CAP with the existing "in this
  segment" cap note. Every occurrence visible in the rendered segment gets
  painted, including phrases the raw search cannot see (bold-split).
- **Current match** (Next/Prev/Enter/q-restore): the raw match's ordinal
  among raw matches inside the segment maps to a rendered match via a new
  pure `pickRenderedOrdinal(rawOrdinal, rawCount, renderedCount)`: identity
  when counts agree (the overwhelmingly common case), proportional-nearest
  when they diverge, null when the segment has zero rendered matches (then
  scroll falls back to proportional position). Scroll and the live-region
  snippet use the mapped rendered span when it exists (snippet quotes
  rendered text, no `**`), raw text otherwise.

Honest tradeoff, stated: in seg-rendered mode the match COUNT is the raw
count while the PAINT is rendered-truth, so a bold-split phrase can show a
highlight the count missed, and a query over markdown syntax (`## Sect`)
counts raw hits it cannot paint. This is the price of correct whole-doc
offsets without rendering 29 MB of markdown; the raw toggle remains the
exact-machinery view. Documented in code and the PR.

## Decision 3: TOC

Segmented docs keep the snapshot-toc offset rows in BOTH modes (whole-doc
`renderedTocRows` derivation stays exclusive to the <=1M rendered mode). A
TOC click still runs `jumpToOffset(off)` -> `segmentForOffset` ->
`renderSegment(target)` (now rendered) -> scroll. Scroll target inside the
rendered segment: anchor on the heading ELEMENT whose whitespace-normalized
text matches the clicked title, picking the k-th among same-title snapshot
rows within the segment (pure helper `nthTitleIndex`); proportional
fallback if no heading matches. Front-matter row and out-of-range offsets
keep today's fallback behavior.

## Decision 4: wrapper and sanitization per segment

Each rendered segment goes through `DOMPurify.sanitize(renderDocMarkdown(
slice), { ADD_ATTR: ['rel'] })` (both XSS layers, same as whole-doc
rendered mode) and injects inside `<div class="ew-doc-rendered">`, so the
Stage 5 I-1 white-space reset and all B1/B6 rendered typography apply
untouched. `data-seg-start` is deleted in seg-rendered (single-text-node
invariant is plain-mode-only); restored by the raw toggle.

## Decision 5: toggle

`showToggle()` now fires for ALL rendered-eligible docs including segmented
ones; default Formatted. Toggling on a segmented doc re-renders the CURRENT
segment in the other mode (segments, segIndex, and raw match state are
mode-invariant), re-runs the last executed query with typing-path
semantics, and announces the mode change. Pages-source docs: never
eligible, no toggle, zero behavior change.

## Decision 6: frozen contracts

- <=1M rendered and plain paths: code paths untouched (`renderRendered`,
  `renderPlainFull` unchanged; the only condition change is eligibility no
  longer excluding segmented docs).
- Raw byte-for-byte: raw mode renders `rawText.slice(seg.start, seg.end)`
  verbatim; smoke asserts container.textContent equals the slice.
- `window.__ewDoc.getRawText()` unchanged. `__ewDocMetrics` gains
  `segRenderMs` (last segment render, parse+sanitize+inject+index).
- `env.d.ts` / `ARCHITECTURE.md` mode-scoped contract amended: rendered
  mode extends to >1M markdown docs per-segment; detection stays "the
  `.ew-doc-rendered` child is present".

## Test plan

- Unit (vitest): three-tier cut safety (table straddle, fence straddle,
  blank-line preference, fallback tiers, surrogate guard, tiling
  invariant); `pickRenderedOrdinal`; `nthTitleIndex`; fixture-shape test
  asserting the new >1M fixture's DEFAULT-config segment boundaries land on
  markdown-safe cuts.
- Fixture: new `synthetic-seg-rich` (~1.05M chars, committed ~1.05 MB,
  fixture total stays under the 3 MB budget): a 20K-char table straddling
  the 500K cut, a fence straddling the ~990K cut, a bold-split phrase in
  segment 1, a unique needle sentence and a `## Final Provisions` heading
  in the last segment.
- Smoke (append-only zone): new scenario (n): seg-rendered doc shows
  `.ew-doc-rendered` + `Segment 1 of N` + toggle; NO literal `## ` text
  node in the rendered container; cross-segment search (needle in the last
  segment -> Next -> segment switches, current highlight painted, live
  region announces); TOC click to `Final Provisions` renders the right
  segment and scrolls; toggle to raw shows the byte-exact segment slice,
  toggle back re-renders; `?q=` deep link lands cross-segment; axe zero
  serious/critical on the seg-rendered page. Scenario (d) updated:
  synthetic-large (markdown >1M) now defaults to Formatted, so (d) first
  asserts the toggle appears, clicks to Raw, then runs ALL existing plain
  segmented assertions unchanged (plain-path regression lock).
- Perf: real-snapshot dev run on the largest 1-2M doc; record
  `segRenderMs` for its largest segment and long-task profile in
  `measurements/NOTES.md`. Expectation from B1 baselines: ~1M-char
  whole-doc renderMs was 294 ms, so a 500K segment should land well under
  ~200 ms.
- Lighthouse accessibility 100 on the seg-rendered doc page (same CLI
  invocation as S3/B1: system Chrome headless against served dist).
