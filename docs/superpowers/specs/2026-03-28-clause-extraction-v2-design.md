# Clause Extraction v2: Section-Aware Pipeline with LLM Extraction

**Date**: 2026-03-28
**Status**: Design approved, revised after 4-model external review
**Target**: Georgetown Law roundtable, March 30, 2026
**Clause types**: CAC (primary), pari passu (if time permits), generalizable

## Problem

The current grep-based pipeline finds pages that mention clause keywords but
does not extract clause text. This produces high false positives (table of
contents entries, cross-references, bare mentions) and no clause boundaries.
For the roundtable, lawyers reviewing the Clause Eval Explorer need to see
the actual clause text — not a page that says "collective action" somewhere
on it.

### Current state

- 1,570 CAC candidates, many false positives (ToC references, cross-refs)
- 640 pari passu candidates, similar issues
- Match context is 500 chars before/after the keyword — no clause boundaries
- Shiny explorer shows raw/monospace text, not document-like formatting
- No LLM in the loop — purely regex
- Review unit is a page-level keyword hit, not a clause candidate

### Desired state

- Extracted verbatim clause text with clear start/end boundaries
- High precision: most candidates shown to lawyers are real clauses
- Rendered markdown in the explorer (looks like the document, sanitized)
- Confidence signals displayed separately so lawyers can apply judgment
- Methodologically defensible: transparent, auditable, every step logged
- Review unit is a **clause candidate** with full provenance

## Architecture: Three-Stage Extraction Pipeline

```
Stage 1: LOCATE (cheap, fast, all documents)
  Document → Section Parser → Heading Filter + Body Cues + Negative Rejector
  → Candidate sections tagged with: heading_match, cue_families, neg_signals
  → Adjacent-page candidates clustered into clause-level candidates

Stage 2: EXTRACT (LLM, overnight batch, ~100-300 candidates)
  Multi-shot prompt with ICMA model language + PDIP calibration examples
  → Verbatim clause text with boundaries (or NOT_FOUND)
  → LLM confidence + reasoning
  → Post-validated: assert extracted text in source (fuzzy, 95%+)

Stage 3: VERIFY (cheap, post-LLM)
  → Completeness checklist: does extracted span contain expected components?
  → Verbatim validation against source text
  → Quality flags (OCR suspect, truncation suspect)
```

Each stage is logged, auditable, and independently re-runnable. A reviewer
can trace: "the LLM extracted this text, from this section, found by this
heading pattern, in this document." This is the methodological chain of
custody.

### Defensibility claim

We are not asking the LLM to find clauses in 300-page documents. We use
document structure and pattern matching to narrow the search space, then
ask the LLM to do precise extraction within a small, well-defined context.
The human validates the final output. Every step is transparent.

## Component 1: Section Parser (Source-Agnostic)

A common interface that takes a document and returns a list of sections.

```python
@dataclass
class Section:
    section_id: str       # "{storage_key}__s{index}"
    storage_key: str      # parent document
    heading: str          # "Collective Action Clauses", "Status of the Notes"
    heading_level: int    # 1, 2, 3 (from markdown ## or HTML <h2>)
    text: str             # full section body text (markdown preserved)
    page_range: tuple     # (start_page, end_page)
    source_format: str    # "docling_md" or "edgar_html"
    char_count: int       # for quality/size signals
```

### Docling markdown parser

Split on `#`/`##`/`###` headings from the ~1,468 Docling-parsed `.md` files.
Preserve the markdown formatting within each section (headings, lists,
tables, bold/italic) — this formatting is rendered in the Shiny explorer.

**Heading detection heuristics**: Docling may not always produce consistent
heading markers. Supplement markdown headings with: lines that are ALL CAPS,
short (<80 chars), and followed by body text are candidate section headings.

**Max section size failsafe**: If a section exceeds ~5 pages (~15,000 chars),
split it at sub-headings or paragraph boundaries. This prevents blowing the
LLM context window and diluting the extraction prompt.

### EDGAR flat-parsed JSONL

~3,217 EDGAR filings are already parsed into flat JSONL (one record per
page, no section structure) via `PlainTextParser` and `HTMLParser` in
`src/corpus/parsers/`. The original files are `.htm` (~2,947) and `.txt`
(~275) in `data/original/`.

**Monday scope**: Process EDGAR documents using page-level sections. Each
non-empty page becomes a `Section` with heading `"(page N)"` and
`source_format="flat_jsonl"`. These candidates have no heading match (only
body-cue filtering), which is transparently reflected in their signals.
The LLM receives the page text and extracts the clause.

This approach has lower precision than section-aware parsing (more
candidates per document) but full recall. The LLM handles the boundary
detection. EDGAR candidates will show "Surfaced By: Body cues" in the
explorer — honest and interpretable.

**Backlog**: Build EDGAR HTML section parser that detects headings from
inline-styled bold/large text (`<b>`, `<font size="+2">`). The
source-agnostic `Section` interface means the rest of the pipeline
doesn't change.

### Why source-agnostic

Adding a new source (future data partners, alternative parsers) means writing
one new section parser function, not changing the pipeline. The rest of the
pipeline operates on `Section` objects regardless of origin.

## Component 2: LOCATE Stage (Filtering + Clustering)

*Heading filter, body cues, negative rejection, and candidate clustering are
a single LOCATE stage. All are cheap regex/heuristic operations.*

### Cue families (not just pattern lists)

Each clause type defines cues organized by **family**, not a flat list.
This enables cue diversity scoring: a section with hits from 3 different
cue families is a much stronger candidate than one with 3 hits from the
same family.

#### CAC cue families

```python
CAC_CUES = {
    "heading": [
        r"collective\s+action",
        r"modification\s+of\s+(the\s+)?(conditions|terms)",
        r"amendment\s+and\s+waiver",
        r"meetings?\s+of\s+(note|bond)holders",
        r"voting\s+and\s+amendments",
    ],
    "voting_threshold": [
        r"consent\s+of\s+(the\s+)?holders\s+of\s+not\s+less\s+than",
        r"holders?\s+of\s+\d+%",
        r"\d+%\s+of\s+the\s+aggregate\s+principal",
        r"extraordinary\s+resolution",
        r"written\s+resolution",
        r"two[\s-]+thirds",
        r"66\s*[⅔2/3]",
    ],
    "aggregation": [
        r"aggregat(ion|ed)\s+(provisions?|voting)",
        r"single[\s-]+(series|limb)\s+(voting|modification)",
        r"cross[\s-]+series",
        r"uniformly\s+applicable",
    ],
    "reserved_matter": [
        r"reserved\s+matter",
        r"reserve[d]?\s+matter\s+modification",
    ],
    "meeting_quorum": [
        r"quorum",
        r"meeting\s+of\s+(note|bond)?holders",
    ],
}
```

#### Pari passu cue families

```python
PARI_PASSU_CUES = {
    "heading": [
        r"status\s+of\s+the\s+(notes|bonds|securities)",
        r"ranking",
        r"pari\s+passu",
    ],
    "ranking": [
        r"pari\s+passu",
        r"rank\s+(equally|pari\s+passu)",
        r"equal\s+(ranking|priority)",
        r"without\s+preference",
    ],
    "obligation": [
        r"unsecured\s+and\s+unsubordinated",
        r"direct,?\s+(unconditional,?\s+)?unsecured",
    ],
}
```

**Pari passu tightening**: `unsecured and unsubordinated` alone is too
permissive. Require co-occurrence with a ranking cue within the same
section, or a matching heading.

### Hard-negative rejector

Before passing candidates to the LLM, apply cheap negative patterns that
eliminate obvious false positives:

```python
NEGATIVE_PATTERNS = {
    "cross_reference": [
        r"(see|refer\s+to|described\s+(under|in))\s+[\"']",
        r"as\s+set\s+forth\s+in",
        r"under\s+[\"'].+[\"']",
    ],
    "table_of_contents": [
        r"\.{4,}",           # dot leaders
        r"^\s*\d+\s*$",      # standalone page numbers
    ],
    "summary_overview": [
        r"(the\s+)?following\s+is\s+a\s+(brief\s+)?summary",
        r"brief\s+description",
        r"summary\s+of\s+(the\s+)?(principal\s+)?provisions",
    ],
}
```

**Rejection logic**:
- Heading-matched sections: never auto-reject (heading is strong enough)
- Body-only candidates: reject if strong negative cues outweigh positive cues
- Body-only candidates with no cue diversity (single cue family): downgrade

### Candidate clustering

The current pipeline deduplicates on `(storage_key, page_number, pattern_name)`.
This is wrong for CACs, which often span multiple consecutive pages.

**Clustering logic**:
1. Group all cue hits by `(storage_key, clause_family)`
2. Merge hits from adjacent pages (gap <= 1 page)
3. Carry forward: all matched cues, page span, cue families hit, section ID
4. Feed the **clustered candidate** to the LLM, not individual page hits

This eliminates duplicate review items (same clause showing up as 5 separate
page hits) and reduces "partial clause" errors from page boundaries.

### Candidate record

Each candidate carries full provenance:

```python
@dataclass
class Candidate:
    candidate_id: str         # unique ID
    storage_key: str          # document
    section_id: str           # which section
    section_heading: str      # heading text
    page_range: tuple         # (start, end)
    heading_match: bool       # was this found by heading pattern?
    cue_families_hit: list    # ["heading", "voting_threshold", "aggregation"]
    cue_hits: list            # [{family, pattern, text, offset}]
    negative_signals: list    # any negative patterns matched
    section_text: str         # full section text (markdown preserved)
    source_format: str        # "docling_md" or "edgar_html"
    run_id: str               # pipeline run identifier
```

### Filtering logic summary

A section becomes a candidate if:
- **Heading match** alone (sufficient), OR
- **Body cues** from 2+ different cue families, with no dominant negative
  signals, OR
- **Body cues** from 1 family, if the cue is strong and specific (e.g.,
  `reserved matter modification`, not just `collective action`)

## Component 3: LLM Clause Extractor

### Input

A shortlisted candidate (section text, typically 0.5-3 pages of markdown),
plus metadata (country, document title, clause type, cue families hit).

### Output

Use Claude's **structured output / tool_use mode** for guaranteed schema
compliance (not free-form JSON generation):

```json
{
  "found": true,
  "clause_text": "The Bonds may be modified...",
  "confidence": "high|medium|low",
  "reasoning": "One sentence on why this is/isn't the clause"
}
```

### Prompt structure (multi-shot)

1. **System**: "You are a legal document analyst specializing in sovereign
   bond contracts. Extract the exact clause text verbatim. Do not
   paraphrase, summarize, or rephrase. Preserve all original formatting,
   whitespace, and punctuation exactly as they appear in the source."

2. **Reference**: The ICMA model CAC language (canonical version), providing
   the baseline for what a CAC clause looks like.

3. **Few-shot examples**: 3-5 PDIP-annotated clauses from the **calibration
   set** (see PDIP Split below) spanning eras:
   - Pre-2003 (old-style, possibly unanimous consent)
   - 2003-2014 (first-generation CAC)
   - Post-2014 (enhanced CAC with aggregation)
   Each example shows: input section text -> extracted clause text.

4. **Negative example**: A cross-reference section that mentions "collective
   action clauses" but only points to another section (e.g., "See
   'Description of the Securities — Collective Action'"). Expected output:
   NOT_FOUND.

5. **Task**: "Here is a section from [country]'s bond prospectus. Extract
   the [clause type] clause verbatim. The clause begins at the section
   heading or where the substantive clause language starts, and ends where
   the subject matter clearly changes or a new section of equal or higher
   heading level begins. Ensure you extract all related sub-paragraphs and
   mechanisms (e.g., aggregation provisions, voting thresholds, notice
   requirements). Do not stop at the first paragraph if the clause continues.
   If this section does not contain a [clause type] clause, return NOT_FOUND
   with a one-sentence explanation."

### Key design choices

- **Verbatim extraction enforced**: The extracted text must appear in the
  source document. Validated with **whitespace-normalized fuzzy match at
  95%+ threshold** (not exact string equality). This accounts for LLM
  whitespace normalization, ligatures (fi -> fi), and minor OCR artifacts
  without allowing paraphrasing.
- **Structured output**: Use tool_use / structured output mode for
  guaranteed JSON schema. No free-form JSON generation.
- **Confidence field**: displayed as a separate signal in the explorer (not
  combined into a grade).
- **Reasoning**: helps the lawyer understand why the system flagged this.
- **NOT_FOUND is a valid answer**: better to say "not found" than force an
  extraction from a cross-reference.
- **Model: Claude Opus 4** (not Sonnet or Haiku). These are billion-dollar
  bond contracts where accuracy on edge cases matters more than cost. Opus
  is better at verbatim extraction, boundary detection, and following
  complex instructions. At ~200-300 candidates, Opus cost is ~$30-50 via
  API — trivial compared to the value of accurate extractions that don't
  waste $1000/hr lawyer time on false positives or truncated clauses.
- **Boundary verification**: For medium-confidence results, optionally
  run a second LLM call: "Here is the text I extracted. Here is the full
  section. Did I capture the complete clause? Are the boundaries correct?"
  Backlog item if time is tight.

### ICMA model language as reference

The ICMA model CAC language serves as the canonical reference in the prompt.
This is methodologically defensible: the model language is the industry
standard that all modern sovereign CACs derive from. Real-world clauses vary
from it — some closely, some substantially — but it anchors the LLM's
understanding of what it is looking for.

**Important**: The ICMA reference is for the LLM's understanding, not for
scoring. Pre-2014 clauses look fundamentally different from ICMA model
language but are valid CACs. Similarity to ICMA is informational only.

## Component 4: VERIFY Stage (Post-LLM Validation)

### Verbatim validation

Whitespace-normalized fuzzy match (95%+ threshold) of extracted text against
source section text. Extractions that fail are flagged as `verification_failed`
and shown with a warning in the explorer rather than being silently displayed.

### Completeness checklist

For each extracted CAC, run a cheap component scan on the extracted span:

| Component | Pattern | Significance |
|---|---|---|
| Voting threshold | `holders of not less than`, `\d+%` | Core mechanism |
| Reserved matter | `reserved matter` | Key carve-out |
| Meeting/resolution | `meeting`, `written resolution`, `quorum` | Procedural mechanism |
| Aggregation | `aggregat`, `cross-series`, `single limb` | Modern CAC marker |

This is a **diagnostic**, not a scoring rule. If a section headed "Collective
Action Clauses" produces an extraction with none of these components except
one threshold sentence, it is probably a partial extraction. Flag it.

For pari passu:

| Component | Pattern | Significance |
|---|---|---|
| Ranking verb | `rank`, `ranking` | Core assertion |
| Comparator | `equally`, `pari passu`, `without preference` | Ranking standard |
| Obligation type | `unsecured`, `unsubordinated`, `direct` | What is being ranked |

### Quality flags

| Flag | Trigger | Display |
|---|---|---|
| `ocr_suspect` | High newline density, non-alpha ratio, suspicious line-length variance | "OCR quality may affect text" |
| `truncation_suspect` | Extraction ends mid-sentence | "May be incomplete" |
| `verification_failed` | Fuzzy match < 95% | "Could not verify against source" |
| `partial_extraction` | Completeness checklist mostly empty | "May be partial" |

## PDIP Data Split (Calibration vs. Evaluation)

*Critical methodological requirement: using the same PDIP documents for
few-shot prompt examples and evaluation contaminates the validation. The
split must be frozen before any LLM runs.*

### Split strategy

Partition the 162 PDIP-annotated documents into:

- **Calibration set (~15-20 docs)**: Used for prompt development. Few-shot
  examples come from here. Select for diversity: different countries,
  different eras, different clause structures.
- **Evaluation set (~140+ docs)**: Never seen by the LLM during prompt
  development. Used exclusively for measuring precision/recall. This is the
  number we report at the roundtable.

The split is by **document** (not by clause), so no information from an
evaluation document leaks into the prompt. Document the split in a
manifest file and commit it before running any LLM extraction.

### Calibration set stratification: CAC types

PDIP annotations only tag CAC *presence* — they don't sub-classify by
variant. But CAC language varies substantially across types, and the
calibration set must cover the spread so the LLM and regex patterns
don't have blind spots.

**Three major CAC variants:**

1. **Traditional / Simple (pre-2003)**: Series-by-series voting only,
   typically 75% threshold. Language: "holders of not less than 75% in
   principal amount of the outstanding Notes of this Series." No
   aggregate or cross-series mechanism.

2. **Two-Limb (Euro area 2013+, English law 2003-2014)**: Two separate
   votes — series-level (75%) AND cross-series aggregate (66 2/3%).
   Language: "modification of this series" + "modification across all
   affected series" or "aggregate collective action."

3. **Single-Limb / ICMA 2014+ (most new issuances)**: One aggregate vote
   across all series (75%), "uniformly applicable." Language: "single
   aggregated voting" + "uniformly applicable" + "aggregate principal
   amount of outstanding debt securities."

**How to select calibration documents:**

Use governing law + date as the primary discriminator:
- English law pre-2014 → likely two-limb
- English law post-2014 → likely single-limb (ICMA)
- NY law post-2014 → modified ICMA
- Euro area sovereign post-2013 → model CAC (standardized two-limb)
- Pre-2003 any law → likely traditional/simple

Aim for at least one doc from each major variant in the calibration set.
If only 4 variants are represented, 4 calibration docs is fine — coverage
of variant diversity matters more than the exact count.

### What to freeze before evaluation

- Prompt version (text + few-shot examples)
- Regex/pattern version (cue families, negative patterns)
- Candidate clustering rules
- Verifier threshold (95%)
- Scoring code
- Feedback taxonomy

### Three-level evaluation

**Level 1: Document-level retrieval** (recall story)
Did the pipeline surface at least one plausible candidate for each
gold-positive document?

Report: "Found clauses in Y of Z PDIP-annotated documents."

**Level 2: Candidate-level precision** (review burden story)
Of the surfaced candidates, how many are real clauses?

Report: "X% of candidates shown to reviewers were genuine clauses."

**Level 3: Span-level boundary accuracy** (extraction quality story)
Among true positives, how close is the extracted span to the gold span?

Report: Character-level precision/recall/F1 against PDIP annotations.
Start-boundary and end-boundary error in characters.

Note: A long clause can clear 95% fuzzy match while still missing an
important tail section. Boundary metrics catch this.

### Review-burden funnel

Report the reduction at each stage:

```
Raw grep hits across corpus           → 1,570 (CAC)
After section-aware LOCATE            → N candidates
After negative rejection              → M candidates
After LLM extraction (found=true)     → K extractions
After verbatim verification           → J verified
Shown to lawyers for review           → J candidates

Review burden: J candidates vs. 1,570 raw hits = X% reduction
Median candidates per accepted clause = Y
```

This makes the operational value legible.

### PDIP disagreements

Some system "false positives" may be real clauses PDIP missed or annotated
differently. Use three bins:

- **True false positive**: system extracted non-clause text
- **Agreement with gold negative**: both agree no clause present
- **System/gold disagreement**: requires manual adjudication

Manually adjudicate a small sample of disagreements. This protects against
overstating either success or failure.

## Component 5: Shiny Explorer Updates

*See `docs/lawyer-centered-design.md` for the full human-centered design
rationale. Key changes summarized here.*

### Mental model shift

The app reframes from grep-hit review to clause validation:

| Old (grep-hit) | New (clause candidate) |
|---|---|
| "Grep Candidates" | "Candidate Clauses" |
| "Match Context" | "Section Context" |
| "Feedback" | "Decision" |
| "Rate the match" | "Validate the clause boundary" |

### Rendered markdown (sanitized)

The context panel renders section markdown as HTML (headings, lists, tables,
bold/italic) so it looks like the legal document. Numbered structure and
indentation are preserved — this is how lawyers judge clause completeness.

**Critical**: All text must be HTML-sanitized before rendering via
`ui.HTML()`. Use a whitelist-based sanitizer that allows formatting tags
(`<h1>`-`<h6>`, `<p>`, `<strong>`, `<em>`, `<ul>`, `<ol>`, `<li>`,
`<table>`) but strips anything else.

**Raw text toggle**: For OCR-suspect sections, provide a toggle to see
the unprocessed source text.

### Updated table columns

| Column | Content |
|---|---|
| Country | Issuer country |
| Document | Document title (truncated) |
| Section | Heading of the matched section |
| Page | Page range in the document |
| Surfaced By | Heading / Body cues / Both |
| LLM Confidence | High / Medium / Low |
| Clause Preview | First 80 chars of extracted clause text |

### Updated detail view

- **Extracted clause** (primary): The proposed clause text, rendered with
  document-like formatting. This is the first thing the lawyer sees.
- **Section context** (secondary): Full section for context, scrollable.
- **Why surfaced** (collapsed by default): Which heading patterns and body
  cues triggered this candidate. Cue family badges.
- **LLM reasoning**: Why the system thinks this is/isn't the clause.
- **Signal breakdown**: Heading match, LLM confidence, page range, clause
  length, completeness checklist, quality flags — displayed as individual
  values, not a combined score.
- **Source metadata**: Storage key, source format, page range, candidate ID,
  run ID.

### Updated feedback options

Replace "Relevant / Not relevant" with structured validation:

- **Correct clause**: The extracted text is the clause, boundaries are right
- **Wrong boundaries**: It is the clause but starts/ends in the wrong place
- **Not a clause**: This section does not contain the clause
- **Partial match**: Only part of the clause was extracted
- **Needs second look**: Uncertain, come back later

### Enhanced feedback logging

The feedback log captures:

- `candidate_id`, `run_id`
- `timestamp`
- `reviewer_session_id`
- `elapsed_seconds` (time since candidate was displayed)
- `verdict`
- `notes` (optional free text)

This enables reporting **median time to confident decision** — a
human-centered metric that demonstrates the tool respects reviewer time.

## Data Flow

```
data/parsed_docling/*.md  ─→ Docling Section Parser ─→ sections.jsonl
data/parsed/edgar__*.jsonl ─→ Flat JSONL Parser    ─→ (appended to sections.jsonl)

sections.jsonl ─→ LOCATE (heading + cue families + neg reject + cluster)
              ─→ candidates.jsonl

candidates.jsonl + prompt ─→ LLM Extractor ─→ extractions.jsonl

extractions.jsonl ─→ VERIFY (verbatim + completeness + quality flags)
                  ─→ verified_extractions.jsonl

verified_extractions.jsonl + pdip_eval_set ─→ Scorer ─→ scored.jsonl

scored.jsonl ─→ Shiny Explorer CSV export
```

Each intermediate file is JSONL, append-only, re-runnable. The pipeline can
be resumed at any stage. Every record carries `candidate_id`, `run_id`, and
`prompt_hash` for full reproducibility.

## Scope: Monday vs. Backlog

### Monday (March 30) — Must Have

1. Docling markdown section parser (ALL CAPS heuristic, max size failsafe)
2. LOCATE stage: cue families, negative rejector, candidate clustering
3. PDIP calibration/evaluation split (frozen manifest, committed)
4. LLM extraction with Sonnet, multi-shot prompt, structured output
5. VERIFY stage: verbatim validation, completeness checklist, quality flags
6. Shiny explorer: clause-first layout, signal columns, structured feedback
7. PDIP three-level evaluation + review-burden funnel
8. Run evaluation Saturday morning, not Sunday night

### Monday — Should Have (if time permits)

9. Pari passu cue families (heading patterns already defined — second run)
10. Rendered markdown in explorer (markdown.markdown() + sanitizer)
11. Hotkeys (j/k navigation, 1/2/3/4 for verdicts, auto-advance)
12. Time-to-decision instrumentation in feedback log
13. Link to original source document

### Cut for Monday

- EDGAR HTML section-aware re-parse (page-level fallback is used instead)
- ICMA string similarity scoring
- Inline clause highlighting within rendered section
- Boundary verification second LLM call
- Embedding-based similarity
- Paragraph-level boundary editing in explorer

### Backlog

See GitHub issues for each item with full context.

## Failure Modes to Monitor

Ranked by likelihood x embarrassment at the roundtable:

1. **Docling OCR artifacts break verbatim check**. *Mitigation*: Fuzzy match
   at 95%+ threshold. Flag OCR quality in explorer.

2. **LLM truncates long clauses**. CAC clauses can span 2-3 pages.
   *Mitigation*: Explicit prompt instruction. Set max_tokens high (4096+).
   Completeness checklist catches partials.

3. **Missed clauses under generic headings**. *Mitigation*: Body-regex
   fallback with cue diversity requirement.

4. **Paraphrased extraction shown to lawyers**. *Mitigation*: Verbatim
   validation on every extraction. Show "verification failed" rather than
   paraphrased text.

5. **PDIP validation numbers are bad**. *Mitigation*: Run evaluation early
   (Saturday). Investigate root causes before Sunday night.

6. **Oversized section blows LLM context**. *Mitigation*: Max section size
   failsafe (split at ~5 pages / 15,000 chars).

## Storyline for Monday

"LLMs + human (lawyer) validation = scalable annotation."

1. We built a transparent, auditable pipeline that uses document structure
   and pattern matching to narrow the search space.
2. An LLM does precise extraction within well-defined context — not reading
   entire documents.
3. We reduced 1,570 raw keyword hits to M verified clause candidates.
4. The result includes individual confidence signals — not a black-box
   score — so lawyers can apply their judgment.
5. Lawyers review candidates in an explorer designed for their workflow:
   document-like formatting, clear clause boundaries, structured feedback.
6. Their feedback improves the system. This scales.

The proof is in the numbers: "Of N PDIP-annotated documents in our holdout
set, we found clauses in Y (Z% recall). Our extracted text matched expert
annotations at W% boundary precision. Lawyers reviewed M candidates instead
of 1,570 raw hits — a Q% reduction in review burden."
