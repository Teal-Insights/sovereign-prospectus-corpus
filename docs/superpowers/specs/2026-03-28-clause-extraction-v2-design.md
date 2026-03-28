# Clause Extraction v2: Section-Aware Pipeline with LLM Extraction

**Date**: 2026-03-28
**Status**: Design approved, revised after 3-model external review
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

### Desired state

- Extracted verbatim clause text with clear start/end boundaries
- High precision: most candidates shown to lawyers are real clauses
- Rendered markdown in the explorer (looks like the document, sanitized)
- Confidence signals displayed separately so lawyers can apply judgment
- Methodologically defensible: transparent, auditable, every step logged

## Architecture: Two-Stage Extraction Pipeline

*Revised from three stages to two per reviewer consensus: heading filter and
body regex are both cheap regex operations and should be a single stage.*

```
Stage 1: LOCATE (cheap, fast, all documents)
  Document → Section Parser → Heading Filter + Body Regex
  → Candidate sections that might contain the clause
  → Each candidate tagged with: heading_match (bool), body_match (bool)

Stage 2: EXTRACT (LLM, overnight batch, ~100-300 candidates)
  Multi-shot prompt with ICMA model language + PDIP calibration examples
  → Verbatim clause text with boundaries (or NOT_FOUND)
  → LLM confidence + reasoning
  → Post-validated: assert extracted text in source (fuzzy, 95%+)
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
    heading: str          # "Collective Action Clauses", "Status of the Notes"
    heading_level: int    # 1, 2, 3 (from markdown ## or HTML <h2>)
    text: str             # full section body text (markdown preserved)
    page_range: tuple     # (start_page, end_page)
    source_format: str    # "docling_md" or "edgar_html"
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

### EDGAR HTML parser

**Monday scope**: EDGAR documents use body-regex fallback (no heading match
→ low confidence). This is honest and avoids the risk of building a new HTML
section parser under time pressure.

SEC EDGAR HTML has no consistent heading schema — many filings use `<b>`,
`<u>`, or `<font size="+2">` instead of `<h1>`-`<h4>` tags. Building a
robust parser could easily consume the entire sprint.

**Backlog**: Build EDGAR HTML section parser that handles inline-styled
headings. The source-agnostic `Section` interface means the rest of the
pipeline doesn't change.

### Why source-agnostic

Adding a new source (future data partners, alternative parsers) means writing
one new section parser function, not changing the pipeline. The rest of the
pipeline operates on `Section` objects regardless of origin.

## Component 2: Section Filter (Clause-Type Config)

*Merged with regex confirmation into a single LOCATE stage.*

Each clause type defines heading patterns AND body-confirmation patterns:

### CAC

```python
CAC_HEADING_PATTERNS = [
    r"collective\s+action",
    r"modification\s+of\s+(the\s+)?(conditions|terms)",
    r"amendment\s+and\s+waiver",
    r"meetings?\s+of\s+(note|bond)holders",
    r"voting\s+and\s+amendments",
]

CAC_BODY_PATTERNS = [
    r"collective\s+action",
    r"consent\s+of\s+(the\s+)?holders\s+of\s+not\s+less\s+than",
    r"aggregat(ion|ed)\s+(provisions?|voting)",
    r"reserved\s+matter",
    r"single[\s-]+(series|limb)\s+(voting|modification)",
]
```

### Pari passu

```python
PARI_PASSU_HEADING_PATTERNS = [
    r"status\s+of\s+the\s+(notes|bonds|securities)",
    r"ranking",
    r"pari\s+passu",
]

PARI_PASSU_BODY_PATTERNS = [
    r"pari\s+passu",
    r"rank\s+(equally|pari\s+passu)",
    r"unsecured\s+and\s+unsubordinated",
]
```

### Filtering logic

A section is a candidate if:
- **Heading match**: section heading matches a heading pattern, OR
- **Body match**: section body has a strong regex hit (substantial clause
  language, not just a keyword mention)

Both signals are recorded on the candidate for display in the explorer.
Heading match is a strong positive signal; body-only match without heading
is valid but lower confidence.

**Key insight (from reviewer)**: If a section has a matching heading like
"Collective Action Clauses", do NOT additionally require a body regex match.
The heading alone is sufficient. Body regex serves as the fallback for
documents without standard headings.

### Adding new clause types

Define heading patterns and body-confirmation regex. The pipeline handles
the rest. This is how we generalize to governing law, negative pledge,
events of default, etc.

## Component 3: LLM Clause Extractor

### Input

A shortlisted section (typically 0.5-3 pages of markdown text), plus
metadata (country, document title, clause type).

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
   Each example shows: input section text → extracted clause text.

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
  whitespace normalization, ligatures (fi → fi), and minor OCR artifacts
  without allowing paraphrasing.
- **Structured output**: Use tool_use / structured output mode for
  guaranteed JSON schema. No free-form JSON generation.
- **Confidence field**: displayed as a separate signal in the explorer (not
  combined into a grade).
- **Reasoning**: helps the lawyer understand why the system flagged this.
- **NOT_FOUND is a valid answer**: better to say "not found" than force an
  extraction from a cross-reference.
- **Model: Claude Sonnet** (not Haiku). All three reviewers agree: Haiku
  paraphrases more and follows complex extraction instructions less
  reliably. At ~200-300 candidates, Sonnet cost is ~$2-5 total. Use Sonnet.
- **Boundary verification**: For medium-confidence results, optionally
  run a second LLM call: "Here is the text I extracted. Here is the full
  section. Did I capture the complete clause? Are the boundaries correct?"
  This is cheap and catches the most common LLM error (truncating long
  clauses). Backlog item if time is tight.

### ICMA model language as reference

The ICMA model CAC language serves as the canonical reference in the prompt.
This is methodologically defensible: the model language is the industry
standard that all modern sovereign CACs derive from. Real-world clauses vary
from it — some closely, some substantially — but it anchors the LLM's
understanding of what it is looking for.

**Important**: The ICMA reference is for the LLM's understanding, not for
scoring. Pre-2014 clauses look fundamentally different from ICMA model
language but are valid CACs. Similarity to ICMA is informational only.

## PDIP Data Split (Calibration vs. Evaluation)

*Critical methodological requirement identified in review: using the same
PDIP documents for few-shot prompt examples and evaluation contaminates
the validation. The split must be frozen before any LLM runs.*

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

### What we report

For the evaluation set:
1. **Recall**: Of documents where PDIP found a CAC, did our pipeline also
   find one? (And the denominator matters — report "found clauses in Y of
   Z PDIP-annotated documents.")
2. **Boundary precision**: Is the extracted text the same as PDIP's
   annotation? (Fuzzy match score.)
3. **False positives**: How many of our extractions are NOT in PDIP?
   (May include clauses PDIP missed — note this.)

## Component 4: Confidence Signals (Displayed Separately)

*Revised per reviewer consensus: show individual signals, not a combined
grade. Lawyers can apply their own judgment to what the signals mean.
A combined "high/medium/low" score obscures information and is hard to
defend when asked "what does high confidence mean?"*

### Signals shown in the explorer

| Signal | What it means |
|---|---|
| **Heading match** | Was the section found by heading pattern? (yes/no + the heading text) |
| **LLM confidence** | What did the LLM report? (high/medium/low + reasoning) |
| **Page range** | Where in the document? (page 47 is plausible; page 2 is suspicious) |
| **Section heading** | What section is this in? (lawyer uses this as a heuristic) |
| **Clause length** | How long is the extracted text? (< 200 chars is likely a cross-ref; 500-5000 chars is a typical clause) |

### Backlog signals

- ICMA similarity tag (informational, not a penalty): "ICMA-aligned" vs.
  "non-standard formulation"
- Embedding-based semantic similarity
- Cross-document consistency (same issuer, different issuances)

## Component 5: Shiny Explorer Updates

### Rendered markdown (sanitized)

The context panel renders section markdown as HTML (headings, lists, tables,
bold/italic) so it looks like the legal document.

**Critical**: All text must be HTML-sanitized before rendering via
`ui.HTML()`. Use a whitelist-based sanitizer (e.g., `bleach` or manual
escaping) that allows formatting tags (`<h1>`-`<h6>`, `<p>`, `<strong>`,
`<em>`, `<ul>`, `<ol>`, `<li>`, `<table>`) but strips anything else.
This prevents the same XSS class we fixed in the current Shiny app.

### Updated table columns

| Column | Content |
|---|---|
| Country | Issuer country |
| Document | Document title (truncated) |
| Section | Heading of the matched section |
| Page | Page range in the document |
| Heading Match | Yes/No — was this found by heading pattern? |
| LLM Confidence | High / Medium / Low |
| Clause Preview | First 80 chars of extracted clause text |

### Updated detail view

- **Section context**: Full section rendered as sanitized markdown/HTML
- **Extracted clause**: Shown separately below the section context (not
  highlighted inline — inline highlighting in rendered HTML is fiddly and
  not worth the time for Monday)
- **LLM reasoning**: Why the system thinks this is/isn't the clause
- **Signal breakdown**: Heading match, LLM confidence, page range, clause
  length — displayed as individual values, not a combined score
- **Source metadata**: Storage key, source format, page range

### Updated feedback options

Replace "Relevant / Not relevant" with more precise feedback:

- **Correct clause**: The extracted text is the clause, boundaries are right
- **Wrong boundaries**: It is the clause but starts/ends in the wrong place
- **Not a clause**: This section does not contain the clause
- **Partial match**: Only part of the clause was extracted

## Data Flow

```
data/parsed_docling/*.md  ─→ Section Parser ─→ sections.jsonl
(EDGAR: body-regex fallback, no section parse for Monday)

sections.jsonl + heading_patterns + body_regex ─→ LOCATE ─→ candidates.jsonl

candidates.jsonl + prompt ─→ LLM Extractor ─→ extractions.jsonl

extractions.jsonl + verbatim check ─→ verified_extractions.jsonl

verified_extractions.jsonl + pdip_eval_set ─→ Scorer ─→ scored.jsonl

scored.jsonl ─→ Shiny Explorer CSV export
```

Each intermediate file is JSONL, append-only, re-runnable. The pipeline can
be resumed at any stage.

## Scope: Monday vs. Backlog

### Monday (March 30) — Must Have

1. Docling markdown section parser (with ALL CAPS heading heuristic, max
   section size failsafe)
2. Section filter with CAC heading + body patterns (single LOCATE stage)
3. PDIP calibration/evaluation split (frozen manifest, committed)
4. LLM extraction with Sonnet, multi-shot prompt, structured output
5. Verbatim post-validation (fuzzy match, 95%+ threshold)
6. Results loaded into Shiny explorer with signal columns
7. PDIP evaluation metrics (run Saturday morning, not Sunday night)

### Monday — Should Have (if time permits)

8. Pari passu patterns (heading patterns already defined — mostly a second
   pipeline run)
9. Rendered markdown in explorer (single `markdown.markdown()` call +
   sanitizer)
10. Updated feedback options

### Cut for Monday

- EDGAR HTML section re-parse (use body-regex fallback → low confidence)
- ICMA string similarity scoring (informational tag, not needed for PoC)
- Highlighted clause within rendered section context (show separately)
- Boundary verification second LLM call
- Embedding-based similarity

### Backlog

- EDGAR HTML section parser with inline-style heading detection
- ICMA similarity as informational tag
- Auto-pass gate via string/embedding similarity threshold
- Additional clause types (governing law, negative pledge, events of default)
- Cross-document consistency checks
- Active learning: lawyer feedback → improved prompt/patterns
- Clause diff across issuances (same issuer, different dates)
- Boundary verification LLM pass

## Failure Modes to Monitor

Ranked by likelihood x embarrassment at the roundtable:

1. **Docling OCR artifacts break verbatim check**. If source markdown has
   character corruption, the LLM either reproduces it (technically verbatim
   but unreadable) or silently fixes it (correct but fails validation).
   *Mitigation*: Fuzzy match at 95%+ threshold. Flag OCR quality in explorer.

2. **LLM truncates long clauses**. CAC clauses can span 2-3 pages with
   sub-sections (aggregation, voting, meetings). Claude may stop at the
   first paragraph break. *Mitigation*: Explicit prompt instruction to
   extract all sub-paragraphs. Set max_tokens high (4096+). If extraction
   ends mid-sentence, flag for review.

3. **Missed clauses under generic headings**. Some prospectuses put CAC
   language under "Terms and Conditions" or "Modification" without a
   specific heading. Body-regex fallback catches these but at low confidence.
   *Mitigation*: Ensure body-regex fallback is implemented, not just spec'd.

4. **Paraphrased extraction shown to lawyers**. Even one non-verbatim
   extraction undermines the "verbatim" claim. *Mitigation*: Run fuzzy
   match validation on every extraction before loading into explorer. Show
   "extraction failed verification" rather than paraphrased text.

5. **PDIP validation numbers are bad**. If recall is <50%, the story becomes
   "this doesn't work." *Mitigation*: Run PDIP validation early (Saturday).
   Investigate root causes. Fix before Sunday night.

6. **Oversized section blows LLM context**. Docling misses a heading tag,
   lumps 40 pages into one section. *Mitigation*: Max section size failsafe
   (split at ~5 pages / 15,000 chars).

## Storyline for Monday

"LLMs + human (lawyer) validation = scalable annotation."

1. We built a transparent, auditable pipeline that uses document structure
   and pattern matching to narrow the search space.
2. An LLM does precise extraction within well-defined context — not reading
   entire documents.
3. The result is a set of candidate clauses with individual confidence
   signals — not a black-box score.
4. Lawyers review candidates in an explorer that shows document-like
   formatting and clear clause boundaries.
5. Their feedback improves the system. This scales.

The proof is in the numbers: "Of N PDIP-annotated documents in our holdout
set, we found clauses in Y. Our extracted text matched expert annotations
at Z% boundary precision. We reduced the review burden from 1,570 raw
matches to M well-extracted clauses."
