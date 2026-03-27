# Clause Extraction Pipeline Design

**Date:** 2026-03-27
**Status:** Draft — pending ratification
**Deadline:** Monday, March 30 (Georgetown roundtable)
**Supersedes:** CAC-only extraction approach from Task 7 spec

---

## Strategic Context

PDIP annotations give us 122 documents with expert-labeled clause text
(text + bounding boxes + labels for ~24,000 clauses across 106 label types).
The previous plan was to build grep patterns first and validate against PDIP
presence labels. The new plan: **use PDIP clause text as the primary
deliverable**, then use grep patterns to scale to the full 4,800+ document
corpus.

This is dramatically less work and produces a more defensible demo — we're
showing expert annotations, not regex output. Grep patterns become the
"scaling" story.

**Two paths, deliberately decoupled:**

- **Validation path (Monday-critical):** PDIP clause extraction → parse 122
  PDIP PDFs → grep patterns → validation against PDIP annotations. This path
  must work by Saturday morning.
- **Scaling path (bonus):** Full corpus parse (PDF + TXT + HTM) → full corpus
  grep. Nice to have for Monday; not required for a defensible demo.

If the scaling path hits problems (encoding issues, malformed files), the
validation path is already demo-ready.

---

## Architecture Overview

```
Raw PDIP JSON files (copied into repo)
        ↓
  pdip_clause_extractor.py
        ↓
  clause_annotations.jsonl  →  DuckDB pdip_clauses table
        ↓                            ↑
  Label family mapping (shared)      |
        ↓                            |
  validate.py  ←  grep_runner.py  ←  clause_patterns.py
                        ↑
                   parsed text (JSONL per doc)
                        ↑
                   corpus parse (PDF + TXT + HTM)
```

---

## Page Number Convention (Global)

All internal storage uses **0-indexed `page_index`**. This includes:

- Parsed text JSONL (`"page": 0`)
- PDIP clause annotations (`page_index` from `item_index`)
- `grep_matches` table
- `pdip_clauses` table

Translation to 1-indexed `page_number` happens **only** at display time:
CLI output, DuckDB views, reports, and exported artifacts. The `+1`
translation is done in exactly one place per output layer.

This convention is documented in `sql/001_corpus.sql` as a schema comment.

---

## Module 1: PDIP Clause Extractor

**File:** `src/corpus/extraction/pdip_clause_extractor.py`

**Input:** Raw JSON files copied from `/var/tmp/pdip_annotations/2026-03-26-full/raw/`
into `data/pdip/annotations/raw/{doc_id}.json` (162 files, version-controlled
path, SHA-256 checksums preserved from harvest).

**Output:** `data/pdip/clause_annotations.jsonl` — one record per clause:

```json
{
    "doc_id": "VEN85",
    "clause_id": "bRblDXsxsA",
    "label": "VotingCollectiveActionModification_AmendmentandWaiver",
    "label_family": "collective_action",
    "page_index": 8,
    "text": "\"Required Noteholders\" shall mean...",
    "text_status": "present",
    "bbox": {"x": 14.06, "y": 36.84, "width": 79.81, "height": 7.65},
    "original_dimensions": {"width": 2440, "height": 3168},
    "country": "Venezuela",
    "instrument_type": "Bond",
    "governing_law": "New York",
    "currency": "USD",
    "document_title": "Petróleos de Venezuela S.A Note..."
}
```

### Text Handling

`value.text` is an array of strings. Join with `"\n"`. 58 of ~6,251
clauses across the corpus have empty text.

**`text_status` field:**
- `"present"` — text extracted successfully
- `"empty"` — `value.text` exists but all elements are empty strings
- `"missing"` — `value.text` key absent

Clauses with empty/missing text are included in clause counts and
document-level presence metrics (the label is still evidence). They are
excluded from verbatim excerpt outputs. Reports show both total clauses
and clauses-with-text.

### Label Family Mapping

**File:** `src/corpus/extraction/label_mapping.py`

Python dict mapping ~109 observed PDIP labels → clause families.
**Strictly one label → one family** (no multi-family mapping for the demo).

```python
PDIP_LABEL_TO_FAMILY: dict[str, str | None] = {
    "VotingCollectiveActionModification_AmendmentandWaiver": "collective_action",
    "VotingCollectiveActionModification_Double_Limb": "collective_action",
    "StatusofObligationPariPassu_RepresentationsWarranties": "pari_passu",
    "NegativePledge_BorrowerCovenantsUndertakings": "negative_pledge",
    "GoverningLaw_Enforcement": "governing_law",
    # ... remaining labels mapped to a family or set to None (unmapped)
}

# For ambiguous labels that could plausibly belong to multiple families
MAPPING_NOTES: dict[str, str] = {
    "VotingCollectiveActionModification_AmendmentandWaiver":
        "Could be 'amendment' family; mapped to 'collective_action' for demo",
}
```

Unmapped labels stored with `label_family: null` and logged. Emit
unmapped-label report each run. Fail loudly if new observed labels appear
that are not in the mapping dict (mapped, explicitly null, or deferred).

**Verification step (end of Session 1):** For each mapped family, print 5
sample `value.text` snippets. Manually confirm they match the family
definition. This is a 20-minute check that validates the mapping before
any grep patterns are written.

### Page Number Handling

- `item_index` is a **0-indexed page number** (empirically verified:
  28/122 docs start at 0, all 122 satisfy `0 <= item_index < page_count`)
- Stored as `page_index` (0-indexed) in all internal artifacts
- Displayed as `page_index + 1` in human-facing outputs
- **Validation:** Assert `0 <= item_index < page_count` for every clause.
  If violated, quarantine the document and log for manual inspection.
  Do NOT use `max(item_index) + 1 == page_count` — annotations don't
  need to touch the last page.

### Zero-Clause Documents

40 of 162 annotated documents returned zero clauses from the API. Working
hypothesis: annotation is still in progress (PDIP launched fall 2025,
annotation is ongoing).

- Spend 15 minutes investigating: cluster by country/instrument type
- Exclude from validation and clause analysis with documented explanation
- Report transparently: "122 of 162 annotated documents have clause data;
  40 are pending annotation"

### Bounding Box Storage (Future Validation)

Store bounding box coordinates in the JSONL output (`bbox` and
`original_dimensions` fields) but do not use them in the current pipeline.

Future work: extract text from the same PDF region using PyMuPDF
`page.get_text("text", clip=fitz.Rect(...))` and compare against
`value.text` from the API. If they match consistently, it validates that
`value.text` is trustworthy for any Label Studio annotations — enabling
use of `value.text` directly without PDF re-extraction.

### Demo Insurance Queries (End of Session 1)

After ingesting into DuckDB, write and run 5 queries that answer
interesting questions:

1. CAC clause presence by country
2. Governing law distribution across annotated documents
3. Most common clause families by instrument type
4. Label frequency distribution (top 20 labels)
5. Clause density (clauses per document) by country

If these produce interesting results, you have a demo regardless of
whether Sessions 2-4 succeed.

---

## Module 2: Corpus Parser (PDF + TXT + HTM)

**Enhanced:** `corpus parse` CLI command

**Priority order:** Parse PDIP PDFs first (needed for validation path),
then NSM/EDGAR files (scaling path). If TXT/HTM parsing hits problems,
the validation path is unaffected.

### File Type Dispatch

```python
PARSERS = {
    ".pdf": pymupdf_parser,
    ".txt": plain_text_parser,
    ".htm": html_parser,
    ".html": html_parser,
}
```

Unsupported extensions (e.g., `.paper`) are logged and skipped with
`parse_status: "unsupported_format"`.

### Output Format (all types)

`data/text/{storage_key}.jsonl` with:

- Header line: `{"storage_key": "...", "page_count": N, "parse_tool": "...", "parse_version": "...", "parsed_at": "...", "parse_status": "..."}`
- Per-page lines: `{"page": 0, "text": "...", "char_count": N}`

### Parser Details

- **PDF:** Existing PyMuPDF parser. Per-page extraction.
- **TXT:** Single page (page 0) by default. If file contains SEC `<PAGE>`
  markers, split on those. Encoding fallback chain: UTF-8 → Latin-1 →
  CP1252. If all fail, log as `parse_failed`.
- **HTML:** `BeautifulSoup(html, "html.parser")`. Strip `<style>` and
  `<script>` tags before `.get_text(separator="\n")`. Same encoding
  fallback chain as TXT.

### Quality Flags

Stored in header record as `parse_status`:

- `parse_ok` — normal extraction
- `parse_partial` — >50% of pages have <50 non-whitespace chars
- `parse_empty` — 100% empty pages (likely scanned image)
- `parse_failed` — parser exception
- `unsupported_format` — file extension not in dispatch table

### Operational

- **Idempotent:** Skip if output JSONL already exists
- **Sequential** to start; add `ProcessPoolExecutor` only if >45 min
- **Error handling:** Catch `fitz.FileDataError` for HTML-disguised-as-PDF.
  Catch `UnicodeDecodeError` for encoding issues. Log and continue.
  Never stop the pipeline.

---

## Module 3: Grep Patterns + Runner

### Pattern Definitions

**File:** `src/corpus/extraction/clause_patterns.py`

```python
@dataclass(frozen=True)
class ClausePattern:
    name: str                    # "collective_action"
    family: str                  # "cac"
    version: str                 # "1.0.0"
    finder: re.Pattern[str]     # compiled regex
    description: str
    instrument_scope: str        # "bond" | "loan" | "both"
```

**Starting patterns:** collective action/modification, pari passu, governing
law. Finder-only — no classifier sub-patterns until post-demo.

**Document-level features** (governing law, currency, document type) use
the same `ClausePattern` dataclass and go in `grep_matches` with a
`feature__` name prefix (e.g., `feature__governing_law`).

**Governing law specifically:** Store all evidence hits (every mention of
"New York law", "English law", etc.) as separate `grep_matches` rows.
Do NOT resolve to one governing law per document. Output artifacts report
presence ("has governing law mention: yes/no") not resolution ("which
law"). Resolution is post-demo work.

### Grep Runner

**File:** `src/corpus/extraction/grep_runner.py`

Core function is pure:
```python
def grep_document(
    pages: list[str],
    patterns: list[ClausePattern],
) -> list[GrepMatch]:
```

**Search approach:**
- Concatenate all pages with `"\n\n"` separator
- Build `page_start_offsets` list
- Run regex on full concatenated text
- Map match offsets to 0-indexed `page_index` via `bisect.bisect_right`
- Store ~500 chars context before and after each match

**GrepMatch dataclass:**
- `document_id`, `pattern_name`, `pattern_version`
- `page_index` (0-indexed), `matched_text`
- `context_before` (~500 chars), `context_after` (~500 chars)
- `run_id`

### CLI Modes

- **Single-doc dev mode:**
  `corpus grep --pattern cac --doc VEN85 --verbose`
  Prints highlighted matches to stdout with 1-indexed page numbers.
  No DuckDB writes. This is the primary pattern development tool.

- **Full corpus mode:**
  `corpus grep --run-id R001`
  Runs all patterns across all parsed documents. Writes to `grep_matches`
  table. Logs pattern_name, documents_matched, documents_scanned, duration.

- **Full re-run strategy:** Delete existing rows for the pattern, re-insert.
  No incremental logic. Grep is fast (minutes).

---

## Module 4: Validation + Demo Outputs

### Validation

**File:** `src/corpus/extraction/validate.py`

For the 122 annotated PDIP documents with clause data:
- Run grep patterns against parsed text
- Compare at document-level presence per clause family (yes/no)
- Compute per-pattern precision and recall
- Segment by instrument type (bond vs loan)
- Output: `data/output/validation_report.json`

### Output Artifacts

1. **`data/pdip/clause_annotations.jsonl`** — Expert-annotated clause corpus
   (headline deliverable). ~6,200 clause records across 122 documents.
   (~58 have empty text, noted with `text_status`.)

2. **`data/output/validation_report.json`** — Precision/recall per pattern
   against PDIP annotations.

3. **`data/output/corpus_summary.json`** — Counts by source, country, clause
   type, file type, document type.

4. **`data/output/clause_presence.parquet`** — Full corpus clause presence
   matrix (document x pattern x found). Polars-native, queryable.

5. **DuckDB views** for live querying (display 1-indexed page numbers):
   - `clause_presence_by_country`
   - `validation_summary`

### DuckDB Schema Additions

- **`pdip_clauses` table** — ingested from `clause_annotations.jsonl`.
  Columns: doc_id, clause_id, label, label_family, page_index, text,
  text_status, bbox (JSON), country, instrument_type, governing_law,
  currency, document_title.

- **`grep_matches` addition** — `run_id` column.

- **Views** as listed above. Views translate `page_index` to
  `page_index + 1 AS page_number` for human consumption.

---

## Demo Narrative Flow

1. "162 expert-annotated documents from PDIP — here are the actual clause
   texts, labeled by Georgetown researchers" (pdip_clauses)
2. "We validated our automated patterns against these expert annotations"
   (validation report with precision/recall)
3. "Then applied those patterns to 4,800+ documents across 3 sources"
   (full corpus grep results)
4. "Here's clause presence by country and source" (DuckDB queries)
5. "The scaling path: LLM judge layer + human evals flywheel"

---

## Implementation Sessions

### Session 1: PDIP Clause Extraction (~2-3 hrs) — MONDAY-CRITICAL
- Copy raw JSON from `/var/tmp/` to `data/pdip/annotations/raw/`
- Build `pdip_clause_extractor.py` and `label_mapping.py`
- Process 162 raw JSON files → `clause_annotations.jsonl`
- Validate page indices against PyMuPDF page counts
- Investigate 40 zero-clause documents (15 min)
- Ingest into DuckDB `pdip_clauses` table
- Verify label mapping: print 5 sample texts per mapped family (20 min)
- Write and run 5 demo insurance DuckDB queries
- Also parse the 122 PDIP PDFs (needed for Session 3 validation)

### Session 2: Full Corpus Parse (~2-3 hrs) — SCALING PATH (bonus)
- Implement `corpus parse` with PDF + TXT + HTM dispatch
- Add `PlainTextParser` and `HTMLParser` with encoding fallback
- Quality flags on all output
- Run across all downloaded files (both `data/original/` for NSM/EDGAR
  and `data/pdfs/` for legacy PDIP files; use manifests to locate files)
- Add `make parse` target
- If encoding issues stall this session, skip and proceed to Session 3
  using only the PDIP PDFs parsed in Session 1

### Session 3: Grep Patterns + Runner (~3-4 hrs)
- Build `clause_patterns.py` and `grep_runner.py`
- Single-doc CLI mode first
- Start with CAC, pari passu patterns (governing law presence only)
- Test against 5 known PDIP documents
- Build validation module, compute precision/recall against PDIP

### Session 4: Scale + Output Artifacts (~2 hrs + overnight)
- Run full corpus parse (if not done in Session 2) overnight
- Run all patterns across full corpus
- Generate output artifacts (Parquet, JSON, DuckDB views)
- Add document type as a feature pattern if time permits

---

## Monday-Critical vs Post-Demo

**Monday-critical (must work by Saturday morning):**
- PDIP clause corpus with text + labels + page numbers (Session 1)
- 5 interesting DuckDB queries on PDIP data (Session 1)
- 2-3 grep patterns validated against PDIP (Session 3)
- Validation report with precision/recall (Session 3)

**Scaling path (nice to have for Monday):**
- Full corpus parse including TXT/HTM (Session 2)
- Full corpus grep results (Session 4)
- Clause presence matrix across 4,800+ documents (Session 4)

**Post-demo:**
- Governing law resolution (which law, not just presence)
- Multi-family label mapping
- Bounding box → PDF text validation
- LLM judge layer
- Human evals flywheel
- MotherDuck deployment
- Visualization notebook / slides

---

## What This Design Does NOT Include

- LLM judge layer (post-demo)
- Human evals infrastructure (post-demo)
- Visualization notebook (Saturday/Sunday, separate from pipeline)
- Slides or one-pager (Sunday)
- Bounding box → PDF text extraction validation (future work)
- Pattern classifier sub-patterns (post-demo)
- MotherDuck deployment (post-Monday)
- Governing law resolution to a single value per document (post-demo)
