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

---

## Architecture Overview

```
Raw PDIP JSON files (on disk)
        ↓
  pdip_clause_extractor.py
        ↓
  clause_annotations.jsonl  →  DuckDB pdip_clauses table
        ↓
  Label family mapping (shared)
        ↓
  validate.py  ←  grep_runner.py  ←  clause_patterns.py
                        ↑
                   parsed text (JSONL per doc)
                        ↑
                   corpus parse (PDF + TXT + HTM)
```

---

## Module 1: PDIP Clause Extractor

**File:** `src/corpus/extraction/pdip_clause_extractor.py`

**Input:** 162 raw JSON files at `/var/tmp/pdip_annotations/2026-03-26-full/raw/{doc_id}.json`

**Output:** `data/pdip/clause_annotations.jsonl` — one record per clause:

```json
{
    "doc_id": "VEN85",
    "clause_id": "bRblDXsxsA",
    "label": "VotingCollectiveActionModification_AmendmentandWaiver",
    "label_family": "collective_action",
    "page_number": 9,
    "text": "\"Required Noteholders\" shall mean...",
    "bbox": {"x": 14.06, "y": 36.84, "width": 79.81, "height": 7.65},
    "original_dimensions": {"width": 2440, "height": 3168},
    "country": "Venezuela",
    "instrument_type": "Bond",
    "governing_law": "New York",
    "currency": "USD",
    "document_title": "Petróleos de Venezuela S.A Note..."
}
```

### Label Family Mapping

Python dict in a dedicated module (`src/corpus/extraction/label_mapping.py`).
Maps ~106 PDIP labels → clause families. Many-to-one. Shared by both the
clause extractor and the validator.

```python
PDIP_LABEL_TO_FAMILY: dict[str, str | None] = {
    "VotingCollectiveActionModification_AmendmentandWaiver": "collective_action",
    "VotingCollectiveActionModification_Double_Limb": "collective_action",
    "StatusofObligationPariPassu_RepresentationsWarranties": "pari_passu",
    "NegativePledge_BorrowerCovenantsUndertakings": "negative_pledge",
    "GoverningLaw_Enforcement": "governing_law",
    # ... remaining labels mapped or set to None (unmapped)
}
```

Unmapped labels stored with `label_family: null` and logged. Emit
unmapped-label report each run.

### Page Number Handling

- `item_index` treated as 0-indexed page number
- Output as 1-indexed (`item_index + 1`) for all human-facing contexts
- Validation: cross-reference `max(item_index)` against PyMuPDF page count
  for each document. Log mismatches.

### Zero-Clause Documents

40 of 162 annotated documents returned zero clauses from the API. Working
hypothesis: annotation is still in progress (PDIP launched fall 2025).

- Spend 15 minutes investigating: cluster by country/instrument type
- Exclude from validation and clause analysis with documented explanation
- Report transparently: "122 of 162 annotated documents have clause data"

### Bounding Box Storage (Future Validation)

Store bounding box coordinates in the JSONL output (`bbox` and
`original_dimensions` fields) but do not use them in the current pipeline.

Future work: extract text from the same PDF region using PyMuPDF
`page.get_text("text", clip=fitz.Rect(...))` and compare against
`value.text` from the API. If they match consistently, it validates that
`value.text` is trustworthy for any Label Studio annotations — enabling
use of `value.text` directly without PDF re-extraction.

---

## Module 2: Corpus Parser (PDF + TXT + HTM)

**Enhanced:** `corpus parse` CLI command

### File Type Dispatch

```python
PARSERS = {
    ".pdf": pymupdf_parser,
    ".txt": plain_text_parser,    # ~15 lines
    ".htm": html_parser,          # ~15 lines (BeautifulSoup)
    ".html": html_parser,
}
```

### Output Format (all types)

`data/text/{storage_key}.jsonl` with:

- Header line: `{"storage_key": "...", "page_count": N, "parse_tool": "...", "parse_version": "...", "parsed_at": "..."}`
- Per-page lines: `{"page": 0, "text": "...", "char_count": N}`

### Parser Details

- **PDF:** Existing PyMuPDF parser. Per-page extraction.
- **TXT:** Single page (page 0). If file contains SEC `<PAGE>` markers,
  split on those.
- **HTML:** `BeautifulSoup(html, "html.parser").get_text(separator="\n")`.
  Single page.

### Quality Flags

Stored in header record:

- `parse_ok` — normal extraction
- `parse_partial` — >50% of pages have <50 non-whitespace chars
- `parse_empty` — 100% empty pages (likely scanned image)
- `parse_failed` — PyMuPDF or parser exception

### Operational

- **Idempotent:** Skip if output JSONL already exists
- **Sequential** to start; add `ProcessPoolExecutor` only if >45 min
- **Error handling:** Catch `fitz.FileDataError` for HTML-disguised-as-PDF.
  Log and continue. Never stop the pipeline.

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
- Map match offsets to 1-indexed page numbers via `bisect.bisect_right`
- Store ~500 chars context before and after each match

**GrepMatch dataclass:**
- `document_id`, `pattern_name`, `pattern_version`
- `page_number` (1-indexed), `matched_text`
- `context_before` (~500 chars), `context_after` (~500 chars)
- `run_id`

### CLI Modes

- **Single-doc dev mode:**
  `corpus grep --pattern cac --doc VEN85 --verbose`
  Prints highlighted matches to stdout. No DuckDB writes. This is the
  primary pattern development tool.

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
   (headline deliverable). ~24,000 clause records across 122 documents.

2. **`data/output/validation_report.json`** — Precision/recall per pattern
   against PDIP annotations.

3. **`data/output/corpus_summary.json`** — Counts by source, country, clause
   type, file type, document type.

4. **`data/output/clause_presence.parquet`** — Full corpus clause presence
   matrix (document x pattern x found). Polars-native, queryable.

5. **DuckDB views** for live querying:
   - `clause_presence_by_country`
   - `validation_summary`

### DuckDB Schema Additions

- **`pdip_clauses` table** — ingested from `clause_annotations.jsonl`.
  Columns: doc_id, clause_id, label, label_family, page_number, text,
  bbox (JSON), country, instrument_type, governing_law, currency,
  document_title.

- **`grep_matches` addition** — `run_id` column.

- **Views** as listed above.

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

### Session 1: PDIP Clause Extraction (~2 hrs)
- Build `pdip_clause_extractor.py` and `label_mapping.py`
- Process 162 raw JSON files → `clause_annotations.jsonl`
- Validate page numbers against PyMuPDF
- Investigate 40 zero-clause documents (15 min)
- Ingest into DuckDB `pdip_clauses` table

### Session 2: Parse Infrastructure (~2-3 hrs)
- Implement `corpus parse` with PDF + TXT + HTM dispatch
- Add `PlainTextParser` and `HTMLParser`
- Quality flags on all output
- Run across all downloaded files (both `data/original/` for NSM/EDGAR
  and `data/pdfs/` for legacy PDIP files; use manifests to locate files)
- Add `make parse` target

### Session 3: Grep Patterns + Runner (~3-4 hrs)
- Build `clause_patterns.py` and `grep_runner.py`
- Single-doc CLI mode first
- Start with CAC, pari passu, governing law patterns
- Test against 5 known PDIP documents
- Add document type as a feature pattern

### Session 4: Validate + Full Corpus (~3-4 hrs + overnight)
- Build `validate.py`
- Compare grep vs PDIP annotations
- Refine patterns based on false negatives
- Run full corpus parse + grep overnight
- Generate all output artifacts

---

## What This Design Does NOT Include

- LLM judge layer (post-demo)
- Human evals infrastructure (post-demo)
- Visualization notebook (Saturday/Sunday, separate from pipeline)
- Slides or one-pager (Sunday)
- Bounding box → PDF text extraction validation (future work)
- Pattern classifier sub-patterns (post-demo)
- MotherDuck deployment (post-Monday)
