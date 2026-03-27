# Plan Review: Clause Extraction Pipeline Implementation

You are reviewing an implementation plan for a sovereign bond prospectus clause extraction pipeline. The plan has 12 tasks across 4 sessions. Your job is to find bugs, missing steps, wrong assumptions, and sequencing problems before an AI coding agent executes this overnight.

**Your role:** You are the senior engineer doing the final review before handing this to a junior developer who will follow it literally. Every wrong code snippet, missing import, or incorrect assumption becomes a debugging session at 2am.

**Deadline context:** Georgetown Law roundtable is Monday, March 30. Today is Thursday, March 27. This plan executes tonight and tomorrow.

**Critical constraint:** The executing agent will follow steps literally. If a code snippet references a function that doesn't exist yet, or uses the wrong import path, or has a type error — the agent will get stuck and waste time debugging instead of building.

---

## The Existing Codebase (What the Plan Must Integrate With)

### Key Files and Interfaces

**`src/corpus/parsers/base.py`** — ParseResult dataclass:
```python
@dataclass(frozen=True)
class ParseResult:
    pages: list[str]
    text: str
    page_count: int
    parse_tool: str
    parse_version: str
    metadata: dict[str, str] = field(default_factory=dict)
```

**`src/corpus/parsers/pymupdf_parser.py`** — Existing parser:
```python
class PyMuPDFParser:
    def parse(self, path: Path) -> ParseResult:
        doc = fitz.open(str(path))
        try:
            pages = [str(page.get_text()) for page in doc]
            text = "\n\n".join(pages)
            return ParseResult(pages=pages, text=text, page_count=len(pages),
                             parse_tool="pymupdf", parse_version=fitz.VersionBind)
        finally:
            doc.close()
```

**`src/corpus/cli.py`** — CLI stubs (lines 567-594):
```python
@cli.group(invoke_without_command=True)
@click.pass_context
def parse(ctx: click.Context) -> None:
    """Parse downloaded PDFs into text."""
    if ctx.invoked_subcommand is None:
        click.echo("Parse not yet implemented. Use --help for subcommands.")

@cli.group(invoke_without_command=True)
@click.pass_context
def grep(ctx: click.Context) -> None:
    """Run grep-first pattern matching on parsed text."""
    if ctx.invoked_subcommand is None:
        click.echo("Grep not yet implemented. Use --help for subcommands.")
```

**`src/corpus/logging.py`** — CorpusLogger:
```python
class CorpusLogger:
    def __init__(self, log_file: str | Path, *, run_id: str) -> None: ...
    def log(self, *, document_id: str, step: str, duration_ms: int, status: str, **extra) -> None: ...
```

**`sql/001_corpus.sql`** — grep_matches table:
```sql
CREATE TABLE IF NOT EXISTS grep_matches (
    match_id        INTEGER PRIMARY KEY DEFAULT nextval('grep_matches_seq'),
    document_id     INTEGER NOT NULL REFERENCES documents(document_id),
    pattern_name    VARCHAR NOT NULL,
    pattern_version VARCHAR NOT NULL,
    page_number     INTEGER,
    matched_text    VARCHAR NOT NULL,
    context_before  VARCHAR,
    context_after   VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
);
```

**`config.toml`** — Relevant paths:
```toml
[paths]
manifests_dir = "data/manifests"
original_dir = "data/original"
parsed_dir = "data/parsed"
db_path = "data/db/corpus.duckdb"
telemetry_dir = "data/telemetry"
```

**`tests/conftest.py`** — Auto-generates `tests/fixtures/sample.pdf`

**Package conventions:**
- All files use `from __future__ import annotations`
- Type hints throughout, pyright basic mode
- ruff for linting/formatting
- pytest for testing

### PDIP Annotation Data Structure

Each clause object from the API:
```json
{
  "original_width": 2440,
  "item_index": 8,
  "id": "bRblDXsxsA",
  "type": "rectanglelabels",
  "value": {
    "x": 14.06, "y": 36.84, "width": 79.81, "height": 7.65,
    "text": ["\"Indebtedness\" shall mean any obligation..."],
    "rectanglelabels": ["Indebtedness_Definitions"]
  }
}
```

Empirically verified: `item_index` is 0-indexed page number. 28/122 docs start at 0. All satisfy `0 <= item_index < page_count`.

109 unique labels observed. ~6,200 total clauses across 122 docs. 58 clauses have empty text. 40 docs have zero clauses (annotation pending).

---

## The Implementation Plan

(12 tasks across 4 sessions)

### Session 1: PDIP Clause Extraction (Monday-Critical)

**Task 1: Label Mapping Module**
- Create `src/corpus/extraction/__init__.py`
- Create `src/corpus/extraction/label_mapping.py` with `PDIP_LABEL_TO_FAMILY` dict (109 labels → clause families), `map_label()`, `unmapped_labels()`
- Test: `tests/test_label_mapping.py`

**Task 2: PDIP Clause Extractor**
- Create `src/corpus/extraction/pdip_clause_extractor.py`
- Functions: `extract_clause_record()`, `extract_document_clauses()`, `process_raw_files()`
- Reads raw JSON, extracts text (joins `value.text` array), maps labels, handles empty/missing text with `text_status` field
- Output: one JSONL record per clause
- Test: `tests/test_pdip_clause_extractor.py`

**Task 3: Copy Raw JSON + Run Extraction**
- Copy 162 files from `/var/tmp/pdip_annotations/2026-03-26-full/raw/` to `data/pdip/annotations/raw/`
- Run extractor → `data/pdip/clause_annotations.jsonl`
- Spot-check output

**Task 4: Page Index Validation**
- Script to validate `0 <= item_index < page_count` for all clauses against PyMuPDF

**Task 5: Zero-Clause Investigation + DuckDB Schema + Ingest**
- Investigate 40 zero-clause docs (cluster by country/instrument)
- Add `pdip_clauses` table and `run_id` column to `grep_matches` in schema SQL
- Ingest clause_annotations.jsonl into DuckDB
- Run 5 demo insurance queries
- Verify label mapping with sample texts

### Session 2: Parse Infrastructure (Scaling Path)

**Task 6: Plain Text + HTML Parsers**
- Create `src/corpus/parsers/text_parser.py` — `PlainTextParser` with `<PAGE>` marker splitting, encoding fallback (UTF-8 → Latin-1 → CP1252)
- Create `src/corpus/parsers/html_parser.py` — `HTMLParser` with BeautifulSoup, strip script/style tags
- Tests for both

**Task 7: Implement `corpus parse run` CLI Command**
- Add `parse run` subcommand to CLI
- File type dispatch (.pdf → PyMuPDF, .txt → PlainTextParser, .htm/.html → HTMLParser)
- Output: `data/parsed/{storage_key}.jsonl` with header + per-page records
- Quality flags: parse_ok, parse_partial, parse_empty, parse_failed
- Idempotent (skip existing), telemetry logging
- Update Makefile

### Session 3: Grep Patterns + Runner

**Task 8: ClausePattern Dataclass + Initial Patterns**
- Create `src/corpus/extraction/clause_patterns.py`
- `ClausePattern` frozen dataclass: name, family, version, finder (re.Pattern), description, instrument_scope
- Initial patterns: collective_action, pari_passu, feature__governing_law
- `get_all_patterns()` function

**Task 9: Grep Runner**
- Create `src/corpus/extraction/grep_runner.py`
- `build_searchable_text()` — concatenate pages, return offsets
- `offset_to_page_index()` — bisect-based page mapping
- `grep_document()` — pure function, returns list[GrepMatch]
- `GrepMatch` frozen dataclass: document_id, pattern_name, pattern_version, page_index, matched_text, context_before, context_after, run_id

**Task 10: Grep CLI Commands**
- `corpus grep doc --pattern X --doc Y --verbose` — single-doc dev mode, prints matches
- `corpus grep run --run-id R001` — full corpus mode, writes to DuckDB grep_matches

### Session 4: Validate + Full Corpus

**Task 11: Validation Module**
- Create `src/corpus/extraction/validate.py`
- `load_pdip_presence()` — {doc_id: set of families} from clause_annotations.jsonl
- `load_grep_presence()` — {storage_key: set of patterns} from DuckDB
- `compute_validation_report()` — precision/recall/F1 per family
- `write_validation_report()` — JSON output

**Task 12: Full Corpus Parse + Grep (Overnight)**
- Parse PDIP docs first (validation path)
- Run grep on PDIP docs, run validation
- Parse remaining corpus overnight
- Run grep on full corpus
- Generate output artifacts

---

## Review Questions (answer ALL)

### Code Correctness

**1.** The `parse run` CLI command (Task 7) reads manifests to find files. But PDIP files are in `data/pdfs/pdip/` (legacy layout, organized by country subdirectories), not `data/original/`. The code has a fallback that globs `data/pdfs/pdip/*.pdf` — but the files are in subdirectories like `data/pdfs/pdip/venezuela/VEN85.pdf`. Will the fallback actually find them? Check the glob pattern.

**2.** The `grep run` CLI command (Task 10) inserts into `grep_matches` with `document_id` looked up via `SELECT document_id FROM documents WHERE storage_key = ?`. But PDIP documents may not be in the `documents` table yet (they're legacy files, not ingested through the normal pipeline). What happens when this SELECT returns NULL? Will the INSERT fail silently or crash?

**3.** The plan adds `run_id` to `grep_matches` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. But DuckDB's `ALTER TABLE ADD COLUMN` behavior with existing rows — does it set NULL for existing rows? Is there a risk of breaking existing queries that assume `run_id` is NOT NULL?

**4.** The validation module maps PDIP `doc_id` (e.g., "VEN85") to `storage_key` (e.g., "pdip__VEN85") by prepending `pdip__`. But the parse command constructs storage keys from manifests or from the filesystem. For legacy PDIP files in `data/pdfs/pdip/venezuela/VEN85.pdf`, what storage_key does the parser generate? Is it `pdip__VEN85` or something else? If there's a mismatch, validation will find zero matches.

**5.** The `PlainTextParser` and `HTMLParser` don't implement the `DocumentParser` protocol from `base.py`. Is that intentional? The existing `PyMuPDFParser` is the only one that does. Will pyright flag this?

### Architecture

**6.** The plan puts ~150 lines of CLI code inline in Task 7 (`parse run`) and Task 10 (`grep doc` + `grep run`). `cli.py` is already 600+ lines. Should any logic be extracted into separate modules, or is the inline approach acceptable for the deadline?

**7.** The `pdip_clauses` table has no foreign key to the `documents` table. The `grep_matches` table references `documents(document_id)`. This means PDIP clause queries can't join to documents without going through `storage_key` matching. Is this an intentional simplification or an oversight?

**8.** The grep runner stores `page_index` (0-indexed) in `GrepMatch`, but the SQL INSERT in Task 10 writes it to the `page_number` column (which the existing schema describes without explicit 0/1 convention). The spec says "0-indexed internally" but the existing column is called `page_number`. Will this cause confusion?

### Sequencing and Dependencies

**9.** Task 7 (`parse run`) depends on manifests existing in `data/manifests/`. Does a PDIP manifest exist? The session handoff from Round 5 says there is no `pdip_manifest.jsonl`. If not, the parse command will find zero PDIP files to parse (the fallback glob may also fail per question 1). What's the actual file discovery path for PDIP documents?

**10.** Task 10 (`grep run`) writes to DuckDB, but Task 5 runs the schema migration. If someone runs Tasks 1-4, then jumps to Task 8-10 (skipping Task 5), the `run_id` column won't exist and the INSERT will fail. Are the task dependencies clear enough?

### Testing

**11.** The test for `process_raw_files` (Task 2) checks `summary["clauses_with_text"] == 1` for a 3-clause input. But the sample data has one clause with text, one with empty text `""`, and one with missing text key. Is the expected count correct? Trace through the `extract_clause_record` logic for each case.

**12.** The grep runner tests use hardcoded `SAMPLE_PAGES` but the actual parse output is JSONL with a header line. The `grep doc` CLI command skips the header line by checking `if "page" in record`. Is the test realistic, or does it test a different interface than what the CLI uses?

### Risk

**13.** What is the single most likely failure point that will block the overnight run? Consider: file paths, DuckDB locking, encoding errors, regex performance, missing dependencies (is BeautifulSoup installed?).

**14.** The plan has no rollback strategy. If Task 7 corrupts the DuckDB file (e.g., bad schema migration), what's the recovery path?

**End with:** "If I could change ONE thing about this plan, it would be..."

Be concrete. Every issue you find now saves an hour of debugging tonight.
