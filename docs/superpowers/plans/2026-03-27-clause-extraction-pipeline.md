# Clause Extraction Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract expert-annotated clause text from PDIP annotations as the primary demo deliverable, then build grep patterns to scale clause identification to the full 4,800+ document corpus.

**Architecture:** Two decoupled paths. Validation path (Monday-critical): process 162 PDIP raw JSON files → extract clause text/labels/page numbers → ingest into DuckDB → parse PDIP PDFs → grep patterns → validate against annotations. Scaling path (bonus): parse full corpus (PDF + TXT + HTM) → run grep across all documents.

**Tech Stack:** Python 3.12+, uv, DuckDB, Polars, Click, PyMuPDF, BeautifulSoup4, ruff, pyright, pytest

**Pre-flight:** Run `uv add beautifulsoup4` before starting. Back up DuckDB before schema changes: `cp data/db/corpus.duckdb data/db/corpus.duckdb.bak`

**Review fixes applied:** Critical bugs found by 3-model review — see `planning/council-of-experts/round-6/2026-03-27_plan-review-synthesis.md`

**Spec:** `docs/superpowers/specs/2026-03-27-clause-extraction-pipeline-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/corpus/extraction/__init__.py` | Package init |
| `src/corpus/extraction/label_mapping.py` | PDIP label → clause family mapping dict |
| `src/corpus/extraction/pdip_clause_extractor.py` | Process raw PDIP JSON → clause JSONL |
| `src/corpus/extraction/grep_runner.py` | Search parsed text with regex patterns |
| `src/corpus/extraction/clause_patterns.py` | ClausePattern dataclass + pattern registry |
| `src/corpus/extraction/validate.py` | Compare grep results vs PDIP annotations |
| `src/corpus/parsers/text_parser.py` | Plain text parser (TXT files) |
| `src/corpus/parsers/html_parser.py` | HTML parser (HTM/HTML files) |
| `tests/test_label_mapping.py` | Label mapping tests |
| `tests/test_pdip_clause_extractor.py` | Clause extractor tests |
| `tests/test_grep_runner.py` | Grep runner tests |
| `tests/test_clause_patterns.py` | Pattern compilation + matching tests |
| `tests/test_text_parser.py` | Plain text parser tests |
| `tests/test_html_parser.py` | HTML parser tests |

### Modified Files

| File | Change |
|------|--------|
| `src/corpus/cli.py` | Implement `parse run`, `grep run`, `grep doc` subcommands |
| `sql/001_corpus.sql` | Add `pdip_clauses` table, `run_id` to `grep_matches`, page convention comment |
| `Makefile` | Update `parse` and `grep` targets |
| `src/corpus/parsers/registry.py` | Register new parsers |
| `tests/conftest.py` | Add extraction test fixtures |

---

## Session 1: PDIP Clause Extraction (Monday-Critical)

### Task 1: Label Mapping Module

**Files:**
- Create: `src/corpus/extraction/__init__.py`
- Create: `src/corpus/extraction/label_mapping.py`
- Test: `tests/test_label_mapping.py`

- [ ] **Step 1: Create the extraction package**

```python
# src/corpus/extraction/__init__.py
"""Clause extraction pipeline."""
```

- [ ] **Step 2: Write failing tests for label mapping**

```python
# tests/test_label_mapping.py
"""Tests for PDIP label → clause family mapping."""

from __future__ import annotations

from corpus.extraction.label_mapping import (
    MAPPING_NOTES,
    PDIP_LABEL_TO_FAMILY,
    map_label,
    unmapped_labels,
)


def test_cac_modification_maps_to_collective_action() -> None:
    assert map_label("VotingCollectiveActionModification_AmendmentandWaiver") == "collective_action"
    assert map_label("VotingCollectiveActionModification_Double_Limb") == "collective_action"


def test_pari_passu_maps() -> None:
    assert map_label("StatusofObligationPariPassu_RepresentationsWarranties") == "pari_passu"


def test_negative_pledge_maps() -> None:
    assert map_label("NegativePledge_BorrowerCovenantsUndertakings") == "negative_pledge"


def test_governing_law_maps() -> None:
    assert map_label("GoverningLaw_Enforcement") == "governing_law"


def test_unmapped_label_returns_none() -> None:
    assert map_label("SomeUnknownLabel_Category") is None


def test_every_label_in_dict_is_string() -> None:
    for label, family in PDIP_LABEL_TO_FAMILY.items():
        assert isinstance(label, str)
        assert family is None or isinstance(family, str)


def test_mapping_notes_only_for_mapped_labels() -> None:
    for label in MAPPING_NOTES:
        assert label in PDIP_LABEL_TO_FAMILY


def test_unmapped_labels_returns_labels_not_in_dict() -> None:
    observed = ["GoverningLaw_Enforcement", "TotallyNewLabel_Unknown"]
    result = unmapped_labels(observed)
    assert "TotallyNewLabel_Unknown" in result
    assert "GoverningLaw_Enforcement" not in result
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_label_mapping.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement label mapping module**

```python
# src/corpus/extraction/label_mapping.py
"""PDIP Label Studio label → clause family mapping.

Each PDIP annotation label maps to exactly one clause family (or None
if unmapped). This mapping is used by both the clause extractor and
the validation module.

The 109 observed labels are from the 2026-03-26 full harvest of 162
annotated PDIP documents.
"""

from __future__ import annotations

# Strictly one label → one family for the demo.
# None = unmapped (not yet assigned to a family).
PDIP_LABEL_TO_FAMILY: dict[str, str | None] = {
    # ── Collective Action / Modification ─────────────────────────
    "VotingCollectiveActionModification_AmendmentandWaiver": "collective_action",
    "VotingCollectiveActionModification_Double_Limb": "collective_action",
    "VotingCollectiveActionModification_Single_Limb": "collective_action",
    "VotingCollectiveActionModification_Supermajority": "collective_action",
    "VotingCollectiveActionModification_UnanimousConsent": "collective_action",
    # ── Acceleration ─────────────────────────────────────────────
    "VotingRequirementforAcceleration_AmendmentandWaiver": "acceleration",
    "Acceleration_Consequences": "acceleration",
    # ── Pari Passu ───────────────────────────────────────────────
    "StatusofObligationPariPassu_RepresentationsWarranties": "pari_passu",
    # ── Negative Pledge ──────────────────────────────────────────
    "NegativePledge_BorrowerCovenantsUndertakings": "negative_pledge",
    # ── Governing Law ────────────────────────────────────────────
    "GoverningLaw_Enforcement": "governing_law",
    # ── Events of Default ────────────────────────────────────────
    "Non-paymentFailuretoPay_EventsofDefaultandConsequences": "events_of_default",
    "CovenantDefault_EventsofDefaultandConsequences": "events_of_default",
    "CrossDefault_EventsofDefaultandConsequences": "events_of_default",
    "Other_EventsofDefaultandConsequences": "events_of_default",
    "UnlawfulnessIllegalityInvalidityBorrower_EventsofDefaultandConsequences": "events_of_default",
    "MoratoriumRepudiationAuthority_EventsofDefaultandConsequences": "events_of_default",
    "InsolvencyBankruptcy_EventsofDefaultandConsequences": "events_of_default",
    "Non-complianceJudgement_EventsofDefaultandConsequences": "events_of_default",
    "MaterialAdverseChange_EventsofDefaultandConsequences": "events_of_default",
    "MisrepresentationRepresentation_EventsofDefaultandConsequences": "events_of_default",
    # ── Amendment and Waiver ─────────────────────────────────────
    "AmendmentandWaiver_AmendmentandWaiver": "amendment_waiver",
    "Meetingsinc.WrittenConsent_AmendmentandWaiver": "amendment_waiver",
    # ── Financial Terms ──────────────────────────────────────────
    "Interest_FinancialTerms": "interest",
    "Commitment_FinancialTerms": "commitment",
    "Fees_FinancialTerms": "fees",
    "Purpose_FinancialTerms": "purpose",
    "CurrencyofDenominationandorPayment_FinancialTerms": "currency",
    # ── Repayment ────────────────────────────────────────────────
    "PaymentMechanics_Repayment": "payment_mechanics",
    "RedemptionRepurchaseEarlyRepayment_Repayment": "redemption",
    "AdditionalAmounts_Repayment": "additional_amounts",
    # ── Enforcement ──────────────────────────────────────────────
    "DisputeResolution_Enforcement": "dispute_resolution",
    "SovereignImmunityWaiver_Enforcement": "sovereign_immunity",
    # ── Conditions ───────────────────────────────────────────────
    "ConditionsUtilization_ConditionsPrecedent": "conditions_precedent",
    "ConditionsEffectiveness_ConditionsPrecedent": "conditions_precedent",
    # ── Borrower Covenants ───────────────────────────────────────
    "Information_BorrowerCovenantsUndertakings": "information_covenants",
    "UseofProceeds_BorrowerCovenantsUndertakings": "use_of_proceeds",
    "BooksandRecords_BorrowerCovenantsUndertakings": "books_records",
    "Other_BorrowerCovenantsUndertakings": None,  # too generic to map
    # ── Coordination / Administration ────────────────────────────
    "DutiesofTrusteeFiscalAgent_CoordinationAdministration": "trustee_duties",
    # ── Definitions ──────────────────────────────────────────────
    "Indebtedness_Definitions": "indebtedness_definition",
    # ── Disbursement ─────────────────────────────────────────────
    "UtilizationBorrowing_Disbursement": "disbursement",
    # ── Internal Reference (not a clause family) ─────────────────
    "InternalReference": None,
    # ── External links (not clause annotations) ──────────────────
    "externallink1": None,
    "externallink2": None,
    "externallink3": None,
}

# For ambiguous labels that could belong to multiple families
MAPPING_NOTES: dict[str, str] = {
    "VotingCollectiveActionModification_AmendmentandWaiver": (
        "Could be 'amendment_waiver' family; mapped to 'collective_action' "
        "because the CAC voting mechanism is the primary semantic content"
    ),
    "Acceleration_Consequences": (
        "Could be 'events_of_default'; mapped to 'acceleration' because "
        "acceleration is the specific mechanism, not just any default consequence"
    ),
}


def map_label(label: str) -> str | None:
    """Map a PDIP label to a clause family. Returns None if unmapped."""
    return PDIP_LABEL_TO_FAMILY.get(label)


def unmapped_labels(observed: list[str]) -> list[str]:
    """Return labels not present in the mapping dict."""
    return [lbl for lbl in observed if lbl not in PDIP_LABEL_TO_FAMILY]
```

Note: This is an initial mapping covering the top ~45 labels by frequency.
During implementation, the engineer should check all 109 observed labels
against the raw data and add any missing ones. Labels not yet mapped should
be set to `None` explicitly.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_label_mapping.py -v`
Expected: All PASS

- [ ] **Step 6: Run full checks**

Run: `uv run ruff check src/corpus/extraction/ tests/test_label_mapping.py && uv run ruff format --check src/corpus/extraction/ tests/test_label_mapping.py && uv run pyright src/corpus/extraction/`
Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add src/corpus/extraction/ tests/test_label_mapping.py
git commit -m "feat: PDIP label → clause family mapping module"
```

---

### Task 2: PDIP Clause Extractor

**Files:**
- Create: `src/corpus/extraction/pdip_clause_extractor.py`
- Test: `tests/test_pdip_clause_extractor.py`

- [ ] **Step 1: Write failing tests for clause extraction**

```python
# tests/test_pdip_clause_extractor.py
"""Tests for PDIP clause extractor."""

from __future__ import annotations

import json
from pathlib import Path

from corpus.extraction.pdip_clause_extractor import (
    extract_clause_record,
    extract_document_clauses,
    process_raw_files,
)


SAMPLE_CLAUSE = {
    "original_width": 2440,
    "item_index": 8,
    "to_name": "pdf",
    "origin": "manual",
    "original_height": 3168,
    "id": "bRblDXsxsA",
    "type": "rectanglelabels",
    "from_name": "Clauses",
    "value": {
        "rotation": 0,
        "x": 14.06,
        "width": 79.81,
        "y": 36.84,
        "text": [
            '"Indebtedness" shall mean any obligation',
        ],
        "rectanglelabels": [
            "Indebtedness_Definitions",
        ],
        "height": 7.65,
    },
    "image_rotation": 0,
}

SAMPLE_CLAUSE_EMPTY_TEXT = {
    **SAMPLE_CLAUSE,
    "id": "emptyText1",
    "value": {
        **SAMPLE_CLAUSE["value"],
        "text": [""],
        "rectanglelabels": ["GoverningLaw_Enforcement"],
    },
}

SAMPLE_CLAUSE_MISSING_TEXT = {
    **SAMPLE_CLAUSE,
    "id": "missingText1",
    "value": {
        "rotation": 0,
        "x": 10.0,
        "width": 80.0,
        "y": 20.0,
        "rectanglelabels": ["NegativePledge_BorrowerCovenantsUndertakings"],
        "height": 5.0,
    },
}

SAMPLE_API_RESPONSE = {
    "document_title": "Republic of Testland Bond 2025",
    "source_url": "https://example.com/test.pdf",
    "metadata": {
        "DebtorCountry": ["Testland"],
        "InstrumentType": ["Bond"],
        "GoverningLaw": ["NY"],
        "CurrencyDenomination": ["USD"],
    },
    "clauses": [SAMPLE_CLAUSE, SAMPLE_CLAUSE_EMPTY_TEXT, SAMPLE_CLAUSE_MISSING_TEXT],
}


def test_extract_clause_record_with_text() -> None:
    record = extract_clause_record(
        clause=SAMPLE_CLAUSE,
        doc_id="TEST1",
        doc_metadata={
            "country": "Testland",
            "instrument_type": "Bond",
            "governing_law": "NY",
            "currency": "USD",
            "document_title": "Republic of Testland Bond 2025",
        },
    )
    assert record["doc_id"] == "TEST1"
    assert record["clause_id"] == "bRblDXsxsA"
    assert record["label"] == "Indebtedness_Definitions"
    assert record["label_family"] == "indebtedness_definition"
    assert record["page_index"] == 8
    assert record["text"] == '"Indebtedness" shall mean any obligation'
    assert record["text_status"] == "present"
    assert record["bbox"]["x"] == 14.06
    assert record["country"] == "Testland"


def test_extract_clause_record_empty_text() -> None:
    record = extract_clause_record(
        clause=SAMPLE_CLAUSE_EMPTY_TEXT,
        doc_id="TEST1",
        doc_metadata={
            "country": "Testland",
            "instrument_type": "Bond",
            "governing_law": "NY",
            "currency": "USD",
            "document_title": "Test",
        },
    )
    assert record["text_status"] == "empty"
    assert record["text"] is None


def test_extract_clause_record_missing_text() -> None:
    record = extract_clause_record(
        clause=SAMPLE_CLAUSE_MISSING_TEXT,
        doc_id="TEST1",
        doc_metadata={
            "country": "Testland",
            "instrument_type": "Bond",
            "governing_law": "NY",
            "currency": "USD",
            "document_title": "Test",
        },
    )
    assert record["text_status"] == "missing"
    assert record["text"] is None


def test_extract_document_clauses() -> None:
    records = extract_document_clauses(
        doc_id="TEST1",
        api_response=SAMPLE_API_RESPONSE,
    )
    assert len(records) == 3
    assert records[0]["label"] == "Indebtedness_Definitions"
    assert records[1]["text_status"] == "empty"
    assert records[2]["text_status"] == "missing"


def test_extract_document_metadata_from_response() -> None:
    records = extract_document_clauses(
        doc_id="TEST1",
        api_response=SAMPLE_API_RESPONSE,
    )
    assert records[0]["country"] == "Testland"
    assert records[0]["instrument_type"] == "Bond"
    assert records[0]["governing_law"] == "NY"
    assert records[0]["currency"] == "USD"


def test_process_raw_files(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "TEST1.json").write_text(json.dumps(SAMPLE_API_RESPONSE))

    output_path = tmp_path / "clause_annotations.jsonl"
    summary = process_raw_files(raw_dir=raw_dir, output_path=output_path)

    assert output_path.exists()
    lines = output_path.read_text().strip().split("\n")
    assert len(lines) == 3  # 3 clauses
    assert summary["documents_processed"] == 1
    assert summary["total_clauses"] == 3
    assert summary["clauses_with_text"] == 1


def test_process_raw_files_skips_zero_clause_docs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    empty_response = {**SAMPLE_API_RESPONSE, "clauses": []}
    (raw_dir / "EMPTY1.json").write_text(json.dumps(empty_response))

    output_path = tmp_path / "clause_annotations.jsonl"
    summary = process_raw_files(raw_dir=raw_dir, output_path=output_path)

    assert summary["documents_processed"] == 1
    assert summary["zero_clause_documents"] == 1
    assert summary["total_clauses"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdip_clause_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement clause extractor**

```python
# src/corpus/extraction/pdip_clause_extractor.py
"""Extract clause-level data from raw PDIP API JSON responses.

Reads the saved raw JSON files from a prior annotations harvest and
produces a structured JSONL file with one record per clause annotation,
including text, bounding box, label family mapping, and document metadata.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from corpus.extraction.label_mapping import map_label, unmapped_labels

logger = logging.getLogger(__name__)


def _extract_metadata(api_response: dict[str, Any]) -> dict[str, str | None]:
    """Extract document-level metadata from API response."""
    meta = api_response.get("metadata", {})

    def _first(key: str) -> str | None:
        val = meta.get(key)
        if isinstance(val, list) and val:
            return str(val[0])
        if isinstance(val, str):
            return val
        return None

    return {
        "country": _first("DebtorCountry"),
        "instrument_type": _first("InstrumentType"),
        "governing_law": _first("GoverningLaw"),
        "currency": _first("CurrencyDenomination"),
        "document_title": api_response.get("document_title"),
    }


def extract_clause_record(
    *,
    clause: dict[str, Any],
    doc_id: str,
    doc_metadata: dict[str, str | None],
) -> dict[str, Any]:
    """Extract a single clause record from a Label Studio annotation."""
    value = clause.get("value", {})

    # Text: join array elements with newline
    text_array = value.get("text")
    if text_array is None:
        text = None
        text_status = "missing"
    elif isinstance(text_array, list):
        joined = "\n".join(str(t) for t in text_array).strip()
        if joined:
            text = joined
            text_status = "present"
        else:
            text = None
            text_status = "empty"
    else:
        text = str(text_array).strip() or None
        text_status = "present" if text else "empty"

    # Label: first rectanglelabel
    rect_labels = value.get("rectanglelabels", [])
    label = rect_labels[0] if rect_labels else None

    return {
        "doc_id": doc_id,
        "clause_id": clause.get("id"),
        "label": label,
        "label_family": map_label(label) if label else None,
        "page_index": clause.get("item_index"),
        "text": text,
        "text_status": text_status,
        "bbox": {
            "x": value.get("x"),
            "y": value.get("y"),
            "width": value.get("width"),
            "height": value.get("height"),
        },
        "original_dimensions": {
            "width": clause.get("original_width"),
            "height": clause.get("original_height"),
        },
        **doc_metadata,
    }


def extract_document_clauses(
    *,
    doc_id: str,
    api_response: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract all clause records from a single document's API response."""
    doc_metadata = _extract_metadata(api_response)
    clauses = api_response.get("clauses", [])
    return [
        extract_clause_record(clause=c, doc_id=doc_id, doc_metadata=doc_metadata)
        for c in clauses
    ]


def process_raw_files(
    *,
    raw_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Process all raw JSON files and write clause annotations JSONL.

    Returns a summary dict with processing statistics.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_clauses = 0
    clauses_with_text = 0
    documents_processed = 0
    zero_clause_documents = 0
    all_observed_labels: list[str] = []

    json_files = sorted(raw_dir.glob("*.json"))

    with output_path.open("w") as f:
        for json_file in json_files:
            doc_id = json_file.stem
            documents_processed += 1

            with json_file.open() as jf:
                api_response = json.load(jf)

            records = extract_document_clauses(doc_id=doc_id, api_response=api_response)

            if not records:
                zero_clause_documents += 1
                logger.info("Zero clauses for %s", doc_id)
                continue

            for record in records:
                total_clauses += 1
                if record["text_status"] == "present":
                    clauses_with_text += 1
                if record["label"]:
                    all_observed_labels.append(record["label"])
                f.write(json.dumps(record) + "\n")

    # Report unmapped labels
    unknown = unmapped_labels(all_observed_labels)
    if unknown:
        unique_unknown = sorted(set(unknown))
        logger.warning(
            "Unmapped labels (%d unique): %s",
            len(unique_unknown),
            ", ".join(unique_unknown),
        )

    return {
        "documents_processed": documents_processed,
        "zero_clause_documents": zero_clause_documents,
        "total_clauses": total_clauses,
        "clauses_with_text": clauses_with_text,
        "clauses_empty_text": total_clauses - clauses_with_text,
        "unmapped_labels": sorted(set(unknown)) if unknown else [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdip_clause_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Run full checks**

Run: `uv run ruff check src/corpus/extraction/ tests/test_pdip_clause_extractor.py && uv run pyright src/corpus/extraction/`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/corpus/extraction/pdip_clause_extractor.py tests/test_pdip_clause_extractor.py
git commit -m "feat: PDIP clause extractor — text, labels, bounding boxes"
```

---

### Task 3: Copy Raw JSON into Repo + Run Extraction

**Files:**
- Modify: `data/pdip/annotations/` (new directory)
- No test file — operational task

- [ ] **Step 1: Copy raw JSON files into version-controlled path**

```bash
mkdir -p data/pdip/annotations/raw
cp /var/tmp/pdip_annotations/2026-03-26-full/raw/*.json data/pdip/annotations/raw/
ls data/pdip/annotations/raw/ | wc -l
# Expected: 162
```

Verify `.gitignore` excludes `data/` (it should already — check with
`grep data .gitignore`). These files are tracked by the pipeline, not git.

- [ ] **Step 2: Run the clause extractor**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.pdip_clause_extractor import process_raw_files
summary = process_raw_files(
    raw_dir=Path('data/pdip/annotations/raw'),
    output_path=Path('data/pdip/clause_annotations.jsonl'),
)
import json
print(json.dumps(summary, indent=2))
"
```

Expected output: ~122 documents processed, ~6,200 total clauses, ~6,140
with text, 40 zero-clause documents.

- [ ] **Step 3: Spot-check output**

```bash
# Check first 3 records
head -3 data/pdip/clause_annotations.jsonl | python3 -m json.tool

# Count records
wc -l data/pdip/clause_annotations.jsonl

# Check label family distribution
uv run python3 -c "
import json
from collections import Counter
families = Counter()
with open('data/pdip/clause_annotations.jsonl') as f:
    for line in f:
        r = json.loads(line)
        families[r['label_family']] += 1
for fam, cnt in families.most_common(20):
    print(f'{cnt:5d}  {fam}')
"
```

- [ ] **Step 4: Commit**

```bash
git add src/corpus/extraction/
git commit -m "feat: run PDIP clause extraction — 122 docs, ~6,200 clauses"
```

---

### Task 4: Page Index Validation

**Files:**
- No new files — validation script run inline

- [ ] **Step 1: Validate page indices against PyMuPDF page counts**

```bash
uv run python3 -c "
import json, glob, fitz
from pathlib import Path

raw_dir = Path('data/pdip/annotations/raw')
pdf_dirs = [Path('data/pdfs/pdip'), Path('data/original')]

violations = []
checked = 0

for json_path in sorted(raw_dir.glob('*.json')):
    doc_id = json_path.stem
    with json_path.open() as f:
        data = json.load(f)
    clauses = data.get('clauses', [])
    if not clauses:
        continue

    # Find matching PDF
    pdfs = []
    for d in pdf_dirs:
        pdfs.extend(glob.glob(str(d / '**' / f'{doc_id}.*'), recursive=True))
    pdfs = [p for p in pdfs if p.endswith('.pdf')]
    if not pdfs:
        continue

    doc = fitz.open(pdfs[0])
    page_count = doc.page_count
    doc.close()
    checked += 1

    for c in clauses:
        idx = c.get('item_index')
        if idx is not None and not (0 <= idx < page_count):
            violations.append((doc_id, idx, page_count))

print(f'Checked {checked} documents')
print(f'Violations (item_index >= page_count): {len(violations)}')
if violations:
    for doc_id, idx, pc in violations[:10]:
        print(f'  {doc_id}: item_index={idx}, page_count={pc}')
else:
    print('All page indices valid.')
"
```

Expected: 0 violations (empirically verified: all 122 docs pass
`0 <= item_index < page_count`).

- [ ] **Step 2: Document the result**

If all pass, no action needed beyond the log output. If any violations,
add those doc_ids to a quarantine list and exclude from downstream analysis.

---

### Task 5: Zero-Clause Investigation + DuckDB Schema + Ingest

**Files:**
- Modify: `sql/001_corpus.sql`

- [ ] **Step 1: Investigate zero-clause documents (15 min)**

```bash
uv run python3 -c "
import json
from pathlib import Path
from collections import Counter

raw_dir = Path('data/pdip/annotations/raw')
zeros = []
for json_path in sorted(raw_dir.glob('*.json')):
    with json_path.open() as f:
        data = json.load(f)
    if not data.get('clauses'):
        meta = data.get('metadata', {})
        country = meta.get('DebtorCountry', ['?'])[0] if isinstance(meta.get('DebtorCountry'), list) else '?'
        itype = meta.get('InstrumentType', ['?'])[0] if isinstance(meta.get('InstrumentType'), list) else '?'
        zeros.append((json_path.stem, country, itype))

print(f'Zero-clause documents: {len(zeros)}')
print()
print('By country:')
for country, cnt in Counter(c for _, c, _ in zeros).most_common():
    print(f'  {cnt:3d}  {country}')
print()
print('By instrument type:')
for itype, cnt in Counter(t for _, _, t in zeros).most_common():
    print(f'  {cnt:3d}  {itype}')
"
```

Document the findings in a brief note. Expected: mostly Venezuelan loans.

- [ ] **Step 2: Back up DuckDB before schema changes**

```bash
cp data/db/corpus.duckdb data/db/corpus.duckdb.bak
```

- [ ] **Step 3: Add `pdip_clauses` table and `run_id` to `grep_matches` schema**

Add to `sql/001_corpus.sql` after the `grep_matches` table definition:

```sql
-- Page convention: all page_index columns are 0-indexed internally.
-- Display layers (CLI, views, reports) translate to 1-indexed page_number.

ALTER TABLE grep_matches ADD COLUMN IF NOT EXISTS run_id VARCHAR;

CREATE SEQUENCE IF NOT EXISTS pdip_clauses_seq START 1;

CREATE TABLE IF NOT EXISTS pdip_clauses (
    pdip_clause_id  INTEGER PRIMARY KEY DEFAULT nextval('pdip_clauses_seq'),
    doc_id          VARCHAR NOT NULL,
    storage_key     VARCHAR,               -- e.g. pdip__VEN85 (joins to documents)
    clause_id       VARCHAR NOT NULL,      -- Label Studio annotation ID
    label           VARCHAR NOT NULL,
    label_family    VARCHAR,               -- mapped clause family (nullable)
    page_index      INTEGER,               -- 0-indexed page number
    text            VARCHAR,               -- clause text (nullable if empty/missing)
    text_status     VARCHAR NOT NULL,       -- present | empty | missing
    bbox            VARCHAR,               -- JSON: {x, y, width, height}
    original_dims   VARCHAR,               -- JSON: {width, height}
    country         VARCHAR,
    instrument_type VARCHAR,
    governing_law   VARCHAR,
    currency        VARCHAR,
    document_title  VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
);
```

- [ ] **Step 4: Write DuckDB ingest script**

```bash
uv run python3 -c "
import json
import duckdb
from pathlib import Path

db_path = Path('data/db/corpus.duckdb')
jsonl_path = Path('data/pdip/clause_annotations.jsonl')

con = duckdb.connect(str(db_path))

# Run schema updates
con.execute(open('sql/001_corpus.sql').read())

# Clear existing pdip_clauses
con.execute('DELETE FROM pdip_clauses')

# Load JSONL
records = []
with jsonl_path.open() as f:
    for line in f:
        records.append(json.loads(line))

print(f'Loading {len(records)} clause records...')

for r in records:
    storage_key = f'pdip__{r[\"doc_id\"]}'
    con.execute('''
        INSERT INTO pdip_clauses (doc_id, storage_key, clause_id, label,
            label_family, page_index, text, text_status, bbox, original_dims,
            country, instrument_type, governing_law, currency, document_title)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        r['doc_id'], storage_key, r['clause_id'], r['label'],
        r.get('label_family'), r.get('page_index'), r.get('text'),
        r['text_status'], json.dumps(r.get('bbox')),
        json.dumps(r.get('original_dimensions')),
        r.get('country'), r.get('instrument_type'),
        r.get('governing_law'), r.get('currency'), r.get('document_title'),
    ])

con.commit()

# Verify
result = con.execute('SELECT COUNT(*) FROM pdip_clauses').fetchone()
print(f'Loaded {result[0]} records into pdip_clauses')

con.close()
"
```

- [ ] **Step 5: Run demo insurance queries**

```bash
uv run python3 -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb')

print('=== CAC presence by country ===')
print(con.execute('''
    SELECT country, COUNT(DISTINCT doc_id) as docs,
           COUNT(*) as clauses
    FROM pdip_clauses
    WHERE label_family = 'collective_action'
    GROUP BY country ORDER BY docs DESC
''').fetchall())

print()
print('=== Governing law distribution ===')
print(con.execute('''
    SELECT governing_law, instrument_type, COUNT(DISTINCT doc_id) as docs
    FROM pdip_clauses
    WHERE text_status = 'present'
    GROUP BY governing_law, instrument_type ORDER BY docs DESC
''').fetchall())

print()
print('=== Top 15 clause families ===')
print(con.execute('''
    SELECT label_family, COUNT(*) as count, COUNT(DISTINCT doc_id) as docs
    FROM pdip_clauses
    WHERE label_family IS NOT NULL
    GROUP BY label_family ORDER BY count DESC
    LIMIT 15
''').fetchall())

print()
print('=== Clause density by country ===')
print(con.execute('''
    SELECT country, COUNT(DISTINCT doc_id) as docs,
           COUNT(*) as total_clauses,
           ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT doc_id), 1) as clauses_per_doc
    FROM pdip_clauses
    GROUP BY country ORDER BY docs DESC
''').fetchall())

print()
print('=== Label frequency (top 20) ===')
print(con.execute('''
    SELECT label, COUNT(*) as count
    FROM pdip_clauses
    ORDER BY count DESC LIMIT 20
''').fetchall())

con.close()
"
```

Review these results. If they're interesting, you have a demo regardless
of Sessions 2-4.

- [ ] **Step 6: Verify label mapping with sample texts**

```bash
uv run python3 -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb')

families = ['collective_action', 'pari_passu', 'negative_pledge', 'governing_law', 'events_of_default']
for family in families:
    print(f'\\n=== {family} — sample texts ===')
    rows = con.execute('''
        SELECT doc_id, label, page_index + 1 as page,
               SUBSTRING(text, 1, 200) as excerpt
        FROM pdip_clauses
        WHERE label_family = ? AND text_status = 'present'
        LIMIT 5
    ''', [family]).fetchall()
    for doc_id, label, page, excerpt in rows:
        print(f'  [{doc_id} p.{page}] {label}')
        print(f'    {excerpt}...')
        print()

con.close()
"
```

Manually review: do the sample texts match the family definition?

- [ ] **Step 7: Commit**

```bash
git add sql/001_corpus.sql
git commit -m "feat: pdip_clauses table + run_id on grep_matches + demo queries"
```

---

### Task 5.5: Bootstrap PDIP Documents into `documents` Table

**CRITICAL:** Without this, `grep run` will crash on NOT NULL constraint
when inserting into `grep_matches`. PDIP docs must exist in `documents`.

**Files:**
- No new files — operational script

- [ ] **Step 1: Bootstrap PDIP documents into the documents table**

```bash
uv run python3 -c "
import duckdb
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')

# Scan legacy PDIP PDFs
pdip_dir = Path('data/pdfs/pdip')
pdf_files = sorted(pdip_dir.rglob('*.pdf'))
print(f'Found {len(pdf_files)} PDIP PDFs')

inserted = 0
skipped = 0
for pdf_path in pdf_files:
    doc_id = pdf_path.stem
    storage_key = f'pdip__{doc_id}'

    # Skip if already exists
    existing = con.execute(
        'SELECT 1 FROM documents WHERE storage_key = ?', [storage_key]
    ).fetchone()
    if existing:
        skipped += 1
        continue

    con.execute('''
        INSERT INTO documents (source, native_id, storage_key, file_path,
                              is_sovereign, issuer_type, scope_status)
        VALUES ('pdip', ?, ?, ?, true, 'sovereign', 'in_scope')
    ''', [doc_id, storage_key, str(pdf_path)])
    inserted += 1

con.commit()
total = con.execute('SELECT COUNT(*) FROM documents WHERE source = ?', ['pdip']).fetchone()[0]
print(f'Inserted {inserted}, skipped {skipped} (already existed)')
print(f'Total PDIP documents in table: {total}')
con.close()
"
```

Expected: ~823 PDIP documents inserted.

- [ ] **Step 2: Verify**

```bash
uv run python3 -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb')
for source, cnt in con.execute('SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY source').fetchall():
    print(f'  {source}: {cnt}')
con.close()
"
```

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m 'ops: bootstrap 823 PDIP documents into documents table'
```

---

## Session 2: Parse Infrastructure (Scaling Path)

### Pre-flight: Install BeautifulSoup4

- [ ] **Step 0: Add beautifulsoup4 dependency**

```bash
uv add beautifulsoup4
```

---

### Task 6: Plain Text + HTML Parsers

**Files:**
- Create: `src/corpus/parsers/text_parser.py`
- Create: `src/corpus/parsers/html_parser.py`
- Test: `tests/test_text_parser.py`
- Test: `tests/test_html_parser.py`

- [ ] **Step 1: Write failing tests for text parser**

```python
# tests/test_text_parser.py
"""Tests for plain text parser."""

from __future__ import annotations

from pathlib import Path

from corpus.parsers.text_parser import PlainTextParser


def test_parse_simple_text(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("This is a test document.\nWith two lines.", encoding="utf-8")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count == 1
    assert "This is a test document." in result.pages[0]
    assert result.parse_tool == "plaintext"


def test_parse_sec_page_markers(tmp_path: Path) -> None:
    f = tmp_path / "edgar.txt"
    f.write_text("Page 1 content\n<PAGE>\nPage 2 content\n<PAGE>\nPage 3", encoding="utf-8")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count == 3
    assert "Page 1 content" in result.pages[0]
    assert "Page 2 content" in result.pages[1]
    assert "Page 3" in result.pages[2]


def test_parse_latin1_encoding(tmp_path: Path) -> None:
    f = tmp_path / "latin1.txt"
    f.write_bytes("Côte d'Ivoire prospectus".encode("latin-1"))
    parser = PlainTextParser()
    result = parser.parse(f)
    assert "Côte d'Ivoire" in result.text


def test_parse_windows_1252_encoding(tmp_path: Path) -> None:
    f = tmp_path / "win.txt"
    # Windows-1252 smart quotes
    f.write_bytes(b"\x93smart quotes\x94")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count >= 1
    assert len(result.text) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_text_parser.py -v`
Expected: FAIL

- [ ] **Step 3: Implement text parser**

```python
# src/corpus/parsers/text_parser.py
"""Plain text parser for .txt files.

Handles SEC EDGAR <PAGE> markers and encoding fallback.
"""

from __future__ import annotations

from pathlib import Path

from corpus.parsers.base import ParseResult

_ENCODINGS = ("utf-8", "cp1252", "latin-1")
_PAGE_MARKER = "<PAGE>"


class PlainTextParser:
    """Parse plain text files into page-segmented results."""

    def parse(self, path: Path) -> ParseResult:
        """Read text file with encoding fallback, split on <PAGE> markers."""
        raw_bytes = path.read_bytes()
        text = self._decode(raw_bytes)

        if _PAGE_MARKER in text:
            pages = [p.strip() for p in text.split(_PAGE_MARKER)]
            # Remove empty trailing page from final marker
            if pages and not pages[-1]:
                pages.pop()
        else:
            pages = [text]

        return ParseResult(
            pages=pages,
            text="\n\n".join(pages),
            page_count=len(pages),
            parse_tool="plaintext",
            parse_version="1.0.0",
        )

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        # Last resort: replace errors
        return raw.decode("utf-8", errors="replace")
```

- [ ] **Step 4: Run text parser tests**

Run: `uv run pytest tests/test_text_parser.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for HTML parser**

```python
# tests/test_html_parser.py
"""Tests for HTML parser."""

from __future__ import annotations

from pathlib import Path

from corpus.parsers.html_parser import HTMLParser


def test_parse_simple_html(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_text("<html><body><p>Hello world</p></body></html>", encoding="utf-8")
    parser = HTMLParser()
    result = parser.parse(f)
    assert result.page_count == 1
    assert "Hello world" in result.pages[0]
    assert result.parse_tool == "beautifulsoup"


def test_strips_script_and_style_tags(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_text(
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>alert('hi')</script><p>Content</p></body></html>",
        encoding="utf-8",
    )
    parser = HTMLParser()
    result = parser.parse(f)
    assert "color:red" not in result.text
    assert "alert" not in result.text
    assert "Content" in result.text


def test_parse_latin1_html(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_bytes("<html><body>Côte d'Ivoire</body></html>".encode("latin-1"))
    parser = HTMLParser()
    result = parser.parse(f)
    assert "Côte d'Ivoire" in result.text
```

- [ ] **Step 6: Implement HTML parser**

```python
# src/corpus/parsers/html_parser.py
"""HTML parser for .htm/.html files.

Strips script/style tags, extracts text with BeautifulSoup.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from corpus.parsers.base import ParseResult

_ENCODINGS = ("utf-8", "cp1252", "latin-1")


class HTMLParser:
    """Parse HTML files into text."""

    def parse(self, path: Path) -> ParseResult:
        """Read HTML, strip script/style, extract text."""
        raw_bytes = path.read_bytes()
        html = self._decode(raw_bytes)

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # Collapse excessive blank lines
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        return ParseResult(
            pages=[text],
            text=text,
            page_count=1,
            parse_tool="beautifulsoup",
            parse_version="1.0.0",
        )

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode("utf-8", errors="replace")
```

- [ ] **Step 7: Run HTML parser tests**

Run: `uv run pytest tests/test_html_parser.py -v`
Expected: All PASS

- [ ] **Step 8: Run full checks**

Run: `uv run ruff check src/corpus/parsers/text_parser.py src/corpus/parsers/html_parser.py tests/test_text_parser.py tests/test_html_parser.py && uv run pyright src/corpus/parsers/`
Expected: No errors

- [ ] **Step 9: Commit**

```bash
git add src/corpus/parsers/text_parser.py src/corpus/parsers/html_parser.py tests/test_text_parser.py tests/test_html_parser.py
git commit -m "feat: plain text and HTML parsers with encoding fallback"
```

---

### Task 7: Implement `corpus parse run` CLI Command

**Files:**
- Modify: `src/corpus/cli.py:567-572`
- Modify: `Makefile`

- [ ] **Step 1: Implement `parse run` subcommand**

Add after the `parse` group in `src/corpus/cli.py` (after line 572):

```python
@parse.command("run")
@click.option("--run-id", required=True, help="Unique run identifier.")
@click.option(
    "--source",
    type=click.Choice(["nsm", "edgar", "pdip", "all"]),
    default="all",
    help="Which source to parse.",
)
@click.option("--limit", type=int, default=None, help="Max documents to parse.")
def parse_run(run_id: str, source: str, limit: int | None) -> None:
    """Parse downloaded documents into per-page text JSONL."""
    import json as _json
    import time
    from datetime import datetime, UTC

    from corpus.parsers.pymupdf_parser import PyMuPDFParser
    from corpus.parsers.text_parser import PlainTextParser
    from corpus.parsers.html_parser import HTMLParser

    config = _load_config()
    text_dir = Path(config.get("paths", {}).get("parsed_dir", "data/parsed"))
    text_dir.mkdir(parents=True, exist_ok=True)

    log_path = Path(config.get("paths", {}).get("telemetry_dir", "data/telemetry")) / "parse.jsonl"
    logger = CorpusLogger(log_path, run_id=run_id)

    parsers = {
        ".pdf": PyMuPDFParser(),
        ".txt": PlainTextParser(),
        ".htm": HTMLParser(),
        ".html": HTMLParser(),
    }

    # Collect files to parse from manifests
    manifest_dir = Path(config.get("paths", {}).get("manifests_dir", "data/manifests"))
    files_to_parse: list[tuple[str, Path]] = []

    for manifest_path in sorted(manifest_dir.glob("*_manifest.jsonl")):
        source_name = manifest_path.stem.replace("_manifest", "")
        if source != "all" and source_name != source:
            continue
        with manifest_path.open() as f:
            for line in f:
                record = _json.loads(line)
                storage_key = record.get("storage_key", "")
                file_path = record.get("file_path")
                if file_path:
                    files_to_parse.append((storage_key, Path(file_path)))

    # Also check legacy PDIP path
    if source in ("pdip", "all"):
        pdip_pdf_dir = Path("data/pdfs/pdip")
        if pdip_pdf_dir.exists():
            for pdf_path in pdip_pdf_dir.rglob("*.pdf"):
                storage_key = f"pdip__{pdf_path.stem}"
                if not any(sk == storage_key for sk, _ in files_to_parse):
                    files_to_parse.append((storage_key, pdf_path))

    if limit:
        files_to_parse = files_to_parse[:limit]

    click.echo(f"Parsing {len(files_to_parse)} documents...")

    parsed = 0
    skipped = 0
    failed = 0

    for storage_key, file_path in files_to_parse:
        output_path = text_dir / f"{storage_key}.jsonl"

        # Idempotent: skip if already parsed
        if output_path.exists():
            skipped += 1
            continue

        if not file_path.exists():
            logger.log(
                document_id=storage_key, step="parse",
                duration_ms=0, status="file_not_found",
            )
            failed += 1
            continue

        suffix = file_path.suffix.lower()
        parser = parsers.get(suffix)
        if parser is None:
            logger.log(
                document_id=storage_key, step="parse",
                duration_ms=0, status="unsupported_format",
                file_ext=suffix,
            )
            failed += 1
            continue

        start = time.monotonic()
        try:
            result = parser.parse(file_path)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Determine quality status
            if result.page_count == 0:
                parse_status = "parse_empty"
            else:
                empty_pages = sum(
                    1 for p in result.pages
                    if len(p.strip()) < 50
                )
                if empty_pages == result.page_count:
                    parse_status = "parse_empty"
                elif empty_pages > result.page_count / 2:
                    parse_status = "parse_partial"
                else:
                    parse_status = "parse_ok"

            # Write output JSONL
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w") as out:
                header = {
                    "storage_key": storage_key,
                    "page_count": result.page_count,
                    "parse_tool": result.parse_tool,
                    "parse_version": result.parse_version,
                    "parse_status": parse_status,
                    "parsed_at": datetime.now(UTC).isoformat(),
                }
                out.write(_json.dumps(header) + "\n")
                for i, page_text in enumerate(result.pages):
                    page_record = {
                        "page": i,
                        "text": page_text,
                        "char_count": len(page_text),
                    }
                    out.write(_json.dumps(page_record) + "\n")

            logger.log(
                document_id=storage_key, step="parse",
                duration_ms=elapsed_ms, status=parse_status,
                page_count=result.page_count, file_ext=suffix,
            )
            parsed += 1

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.log(
                document_id=storage_key, step="parse",
                duration_ms=elapsed_ms, status="parse_failed",
                error_message=str(exc), file_ext=suffix,
            )
            failed += 1

    click.echo(f"Done. Parsed: {parsed}, Skipped: {skipped}, Failed: {failed}")
```

Also add the necessary import at the top of `cli.py` if not already present:

```python
from corpus.logging import CorpusLogger
```

- [ ] **Step 2: Update Makefile parse target**

Replace the `parse` target in the Makefile:

```makefile
parse:
	uv run corpus parse run --run-id $(RUN_ID) --source all
```

- [ ] **Step 3: Test with a small parse run**

```bash
uv run corpus parse run --run-id test-parse --source pdip --limit 5
ls data/parsed/ | head -10
# Verify JSONL files created
head -2 data/parsed/pdip__*.jsonl | head -20
```

- [ ] **Step 4: Run full checks**

Run: `uv run ruff check src/corpus/cli.py && uv run pytest tests/test_cli.py -v -k parse`
Expected: No lint errors, existing CLI tests still pass

- [ ] **Step 5: Commit**

```bash
git add src/corpus/cli.py Makefile
git commit -m "feat: corpus parse run — PDF, TXT, HTM with quality flags"
```

---

## Session 3: Grep Patterns + Runner

### Task 8: ClausePattern Dataclass + Initial Patterns

**Files:**
- Create: `src/corpus/extraction/clause_patterns.py`
- Test: `tests/test_clause_patterns.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_clause_patterns.py
"""Tests for clause pattern definitions."""

from __future__ import annotations

import re

from corpus.extraction.clause_patterns import (
    CLAUSE_PATTERNS,
    FEATURE_PATTERNS,
    ClausePattern,
    get_all_patterns,
)


def test_clause_pattern_dataclass() -> None:
    p = ClausePattern(
        name="test",
        family="test_family",
        version="1.0.0",
        finder=re.compile(r"test pattern", re.IGNORECASE),
        description="A test pattern",
        instrument_scope="both",
    )
    assert p.name == "test"
    assert p.family == "test_family"


def test_cac_pattern_family_matches_label_mapping() -> None:
    """Pattern family must match PDIP label mapping family name."""
    p = CLAUSE_PATTERNS["collective_action"]
    assert p.family == "collective_action"  # Must match label_mapping.py


def test_all_patterns_compile() -> None:
    for name, pattern in {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}.items():
        assert isinstance(pattern.finder, re.Pattern), f"{name} finder is not compiled"


def test_cac_pattern_matches_known_text() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = (
        "The Terms and Conditions of the Notes may be amended, modified or "
        "waived with the consent of holders of not less than 75% in aggregate "
        "principal amount (collective action clauses)."
    )
    assert p.finder.search(text) is not None


def test_cac_pattern_matches_modification_text() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "modification of the terms of the Notes requires the consent of holders"
    assert p.finder.search(text) is not None


def test_pari_passu_pattern_matches() -> None:
    p = CLAUSE_PATTERNS["pari_passu"]
    text = "The Notes rank pari passu in right of payment with all other unsecured obligations"
    assert p.finder.search(text) is not None


def test_governing_law_pattern_matches_ny() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York"
    assert p.finder.search(text) is not None


def test_governing_law_pattern_matches_english() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "governed by English law"
    assert p.finder.search(text) is not None


def test_get_all_patterns() -> None:
    all_patterns = get_all_patterns()
    assert len(all_patterns) >= 3
    names = [p.name for p in all_patterns]
    assert "collective_action" in names
    assert "pari_passu" in names
    assert "feature__governing_law" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_clause_patterns.py -v`
Expected: FAIL

- [ ] **Step 3: Implement clause patterns**

```python
# src/corpus/extraction/clause_patterns.py
"""Clause pattern definitions for grep-first extraction.

Patterns are defined in code (not config) because they require complex
regex with flags, inline comments, and per-pattern logic. Each pattern
is a finder that locates candidate sections in document text.

Page convention: all page references use 0-indexed page_index internally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClausePattern:
    """A regex pattern for finding clause sections in document text."""

    name: str  # unique identifier, e.g. "collective_action"
    family: str  # grouping, e.g. "cac"
    version: str  # semver for tracking changes
    finder: re.Pattern[str]  # compiled regex
    description: str
    instrument_scope: str  # "bond" | "loan" | "both"


CLAUSE_PATTERNS: dict[str, ClausePattern] = {
    "collective_action": ClausePattern(
        name="collective_action",
        family="collective_action",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"collective\s+action"
            r"|modification\s+of\s+(?:the\s+)?terms"
            r"|amendment\s+(?:of|to)\s+(?:the\s+)?(?:terms|conditions)"
            r"|consent\s+of\s+(?:the\s+)?holders?\s+of\s+not\s+less\s+than"
            r"|aggregation\s+provisions?"
            r"|single[- ]limb\s+voting"
            r"|two[- ]limb\s+voting"
            r"|double[- ]limb\s+voting"
            r"|reserved\s+matter"
            r")",
            re.IGNORECASE,
        ),
        description="Collective action clauses — modification of bond terms by majority vote",
        instrument_scope="both",
    ),
    "pari_passu": ClausePattern(
        name="pari_passu",
        family="pari_passu",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"pari\s+passu"
            r"|rank(?:s|ing)?\s+(?:at\s+least\s+)?equal(?:ly)?\s+(?:in\s+right\s+of\s+payment|and\s+ratab)"
            r"|equal\s+ranking\s+(?:with|to)"
            r")",
            re.IGNORECASE,
        ),
        description="Pari passu — equal ranking in right of payment",
        instrument_scope="both",
    ),
}

FEATURE_PATTERNS: dict[str, ClausePattern] = {
    "feature__governing_law": ClausePattern(
        name="feature__governing_law",
        family="governing_law",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"governed\s+by\s+(?:and\s+(?:construed|interpreted)\s+in\s+accordance\s+with\s+)?(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+State\s+of\s+)?(?:New\s+York|England|English)"
            r"|subject\s+to\s+(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+State\s+of\s+)?(?:New\s+York|England|English)"
            r")",
            re.IGNORECASE,
        ),
        description="Governing law identification — NY vs English law",
        instrument_scope="both",
    ),
}


def get_all_patterns() -> list[ClausePattern]:
    """Return all registered patterns (clause + feature)."""
    return list(CLAUSE_PATTERNS.values()) + list(FEATURE_PATTERNS.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_clause_patterns.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/clause_patterns.py tests/test_clause_patterns.py
git commit -m "feat: clause patterns — CAC, pari passu, governing law"
```

---

### Task 9: Grep Runner

**Files:**
- Create: `src/corpus/extraction/grep_runner.py`
- Test: `tests/test_grep_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_grep_runner.py
"""Tests for grep runner."""

from __future__ import annotations

import re

from corpus.extraction.clause_patterns import ClausePattern
from corpus.extraction.grep_runner import (
    GrepMatch,
    build_searchable_text,
    grep_document,
    offset_to_page_index,
)


SAMPLE_PAGES = [
    "Republic of Testland\nSovereign Bond Prospectus\n\nThis offering relates to bonds.",
    (
        "Collective Action Clauses\n\n"
        "The terms of the Notes may be modified with the consent of holders of "
        "not less than 75% in aggregate principal amount."
    ),
    (
        "The Notes rank pari passu in right of payment with all other "
        "unsecured and unsubordinated obligations of the Issuer."
    ),
    (
        "This Agreement shall be governed by and construed in accordance "
        "with the laws of the State of New York."
    ),
]

TEST_PATTERN = ClausePattern(
    name="test_cac",
    family="cac",
    version="1.0.0",
    finder=re.compile(r"collective\s+action", re.IGNORECASE),
    description="test",
    instrument_scope="both",
)


def test_build_searchable_text() -> None:
    full_text, offsets = build_searchable_text(SAMPLE_PAGES)
    assert len(offsets) == 4
    assert offsets[0] == 0
    assert "Republic of Testland" in full_text
    assert "pari passu" in full_text


def test_offset_to_page_index() -> None:
    _, offsets = build_searchable_text(SAMPLE_PAGES)
    # Offset 0 should be page 0
    assert offset_to_page_index(0, offsets) == 0
    # Offset in the middle of page 1 should be page 1
    assert offset_to_page_index(offsets[1] + 10, offsets) == 1
    # Offset in page 3 should be page 3
    assert offset_to_page_index(offsets[3] + 5, offsets) == 3


def test_grep_document_finds_matches() -> None:
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    assert len(matches) >= 1
    assert matches[0].pattern_name == "test_cac"
    assert matches[0].page_index == 1  # CAC is on page index 1


def test_grep_document_captures_context() -> None:
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    match = matches[0]
    assert len(match.context_before) > 0
    assert len(match.context_after) > 0
    assert len(match.context_before) <= 600  # ~500 + some slack
    assert len(match.context_after) <= 600


def test_grep_document_verbatim_assertion() -> None:
    """Matched text must appear verbatim in the page text."""
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    for match in matches:
        full_text = "\n\n".join(SAMPLE_PAGES)
        assert match.matched_text in full_text


def test_grep_document_no_matches_returns_empty() -> None:
    no_match_pattern = ClausePattern(
        name="no_match",
        family="test",
        version="1.0.0",
        finder=re.compile(r"xyzzy_will_not_match"),
        description="",
        instrument_scope="both",
    )
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[no_match_pattern],
        document_id="TEST1",
        run_id="test-run",
    )
    assert len(matches) == 0


def test_grep_document_multiple_patterns() -> None:
    pari_pattern = ClausePattern(
        name="pari_passu",
        family="pari_passu",
        version="1.0.0",
        finder=re.compile(r"pari\s+passu", re.IGNORECASE),
        description="",
        instrument_scope="both",
    )
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN, pari_pattern],
        document_id="TEST1",
        run_id="test-run",
    )
    names = {m.pattern_name for m in matches}
    assert "test_cac" in names
    assert "pari_passu" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_grep_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement grep runner**

```python
# src/corpus/extraction/grep_runner.py
"""Grep runner — search parsed document text with regex patterns.

Core function grep_document() is pure: takes pages and patterns,
returns matches. Used by both single-doc CLI mode and full-corpus mode.

Page convention: all page_index values are 0-indexed.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

from corpus.extraction.clause_patterns import ClausePattern

CONTEXT_CHARS = 500


@dataclass(frozen=True)
class GrepMatch:
    """A single regex match in a document."""

    document_id: str
    pattern_name: str
    pattern_version: str
    page_index: int  # 0-indexed
    matched_text: str
    context_before: str
    context_after: str
    run_id: str


def build_searchable_text(pages: list[str]) -> tuple[str, list[int]]:
    """Concatenate pages with separators and return page start offsets.

    Returns:
        (full_text, page_start_offsets) where page_start_offsets[i] is
        the character offset where page i begins in full_text.
    """
    offsets: list[int] = []
    parts: list[str] = []
    pos = 0
    for page_text in pages:
        offsets.append(pos)
        parts.append(page_text)
        pos += len(page_text) + 2  # +2 for "\n\n" separator
    return "\n\n".join(parts), offsets


def offset_to_page_index(offset: int, page_offsets: list[int]) -> int:
    """Map a character offset to a 0-indexed page number."""
    return bisect.bisect_right(page_offsets, offset) - 1


def grep_document(
    *,
    pages: list[str],
    patterns: list[ClausePattern],
    document_id: str,
    run_id: str,
) -> list[GrepMatch]:
    """Search document text with all patterns. Returns matches."""
    if not pages:
        return []

    full_text, page_offsets = build_searchable_text(pages)
    matches: list[GrepMatch] = []

    for pattern in patterns:
        for m in pattern.finder.finditer(full_text):
            start, end = m.start(), m.end()
            page_idx = offset_to_page_index(start, page_offsets)

            context_before = full_text[max(0, start - CONTEXT_CHARS) : start]
            context_after = full_text[end : end + CONTEXT_CHARS]

            matches.append(
                GrepMatch(
                    document_id=document_id,
                    pattern_name=pattern.name,
                    pattern_version=pattern.version,
                    page_index=page_idx,
                    matched_text=m.group(),
                    context_before=context_before,
                    context_after=context_after,
                    run_id=run_id,
                )
            )

    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_grep_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Run full checks**

Run: `uv run ruff check src/corpus/extraction/grep_runner.py tests/test_grep_runner.py && uv run pyright src/corpus/extraction/`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/corpus/extraction/grep_runner.py tests/test_grep_runner.py
git commit -m "feat: grep runner — document-wide search with page mapping"
```

---

### Task 10: Grep CLI Commands (Single-Doc + Full Corpus)

**Files:**
- Modify: `src/corpus/cli.py:578-583`
- Modify: `Makefile`

- [ ] **Step 1: Implement `grep doc` subcommand (single-doc dev mode)**

Add after the `grep` group in `src/corpus/cli.py`:

```python
@grep.command("doc")
@click.option("--pattern", "pattern_name", required=True, help="Pattern name to search for.")
@click.option("--doc", "doc_id", required=True, help="Document ID (storage_key).")
@click.option("--verbose", is_flag=True, help="Show full context around matches.")
def grep_doc(pattern_name: str, doc_id: str, verbose: bool) -> None:
    """Search a single document with a pattern (dev mode)."""
    import json as _json

    from corpus.extraction.clause_patterns import CLAUSE_PATTERNS, FEATURE_PATTERNS
    from corpus.extraction.grep_runner import grep_document

    all_patterns = {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}
    if pattern_name not in all_patterns:
        click.echo(f"Unknown pattern: {pattern_name}", err=True)
        click.echo(f"Available: {', '.join(sorted(all_patterns.keys()))}", err=True)
        raise SystemExit(1)

    pattern = all_patterns[pattern_name]

    # Find parsed text file
    config = _load_config()
    text_dir = Path(config.get("paths", {}).get("parsed_dir", "data/parsed"))
    text_path = text_dir / f"{doc_id}.jsonl"
    if not text_path.exists():
        click.echo(f"Parsed text not found: {text_path}", err=True)
        raise SystemExit(1)

    # Load pages from JSONL
    pages: list[str] = []
    with text_path.open() as f:
        for line in f:
            record = _json.loads(line)
            if "page" in record:  # skip header line
                pages.append(record["text"])

    matches = grep_document(
        pages=pages,
        patterns=[pattern],
        document_id=doc_id,
        run_id="dev",
    )

    if not matches:
        click.echo(f"No matches for '{pattern_name}' in {doc_id}")
        return

    click.echo(f"Found {len(matches)} match(es) for '{pattern_name}' in {doc_id}:\n")
    for i, m in enumerate(matches, 1):
        page_display = m.page_index + 1  # 1-indexed for display
        click.echo(f"--- Match {i} (page {page_display}) ---")
        if verbose:
            click.secho(f"  ...{m.context_before[-200:]}", dim=True)
        click.secho(f"  >>> {m.matched_text}", fg="green", bold=True)
        if verbose:
            click.secho(f"  {m.context_after[:200]}...", dim=True)
        click.echo()
```

- [ ] **Step 2: Implement `grep run` subcommand (full corpus mode)**

Add after `grep doc`:

```python
@grep.command("run")
@click.option("--run-id", required=True, help="Unique run identifier.")
@click.option("--pattern", "pattern_names", multiple=True, help="Specific pattern(s) to run. Omit for all.")
@click.option("--source", type=click.Choice(["nsm", "edgar", "pdip", "all"]), default="all")
@click.option("--limit", type=int, default=None, help="Max documents to process.")
def grep_run(run_id: str, pattern_names: tuple[str, ...], source: str, limit: int | None) -> None:
    """Run patterns across all parsed documents, write to DuckDB."""
    import json as _json
    import time

    import duckdb

    from corpus.extraction.clause_patterns import get_all_patterns, CLAUSE_PATTERNS, FEATURE_PATTERNS
    from corpus.extraction.grep_runner import grep_document

    config = _load_config()
    text_dir = Path(config.get("paths", {}).get("parsed_dir", "data/parsed"))
    db_path = Path(config.get("paths", {}).get("db_path", "data/db/corpus.duckdb"))
    log_path = Path(config.get("paths", {}).get("telemetry_dir", "data/telemetry")) / "grep.jsonl"
    logger = CorpusLogger(log_path, run_id=run_id)

    # Select patterns
    all_registered = {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}
    if pattern_names:
        patterns = [all_registered[n] for n in pattern_names if n in all_registered]
    else:
        patterns = get_all_patterns()

    if not patterns:
        click.echo("No patterns selected.", err=True)
        raise SystemExit(1)

    click.echo(f"Running {len(patterns)} pattern(s) across parsed documents...")

    # Collect parsed text files
    text_files = sorted(text_dir.glob("*.jsonl"))
    if source != "all":
        text_files = [f for f in text_files if f.stem.startswith(f"{source}__")]
    if limit:
        text_files = text_files[:limit]

    con = duckdb.connect(str(db_path))

    # Delete old results for these patterns
    for p in patterns:
        con.execute(
            "DELETE FROM grep_matches WHERE pattern_name = ?",
            [p.name],
        )

    total_matches = 0
    docs_with_matches = 0

    for text_path in text_files:
        doc_id = text_path.stem

        # Load pages
        pages: list[str] = []
        with text_path.open() as f:
            for line in f:
                record = _json.loads(line)
                if "page" in record:
                    pages.append(record["text"])

        if not pages:
            continue

        start = time.monotonic()
        matches = grep_document(
            pages=pages, patterns=patterns, document_id=doc_id, run_id=run_id,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if matches:
            # Look up document_id (may be NULL if not ingested)
            row = con.execute(
                "SELECT document_id FROM documents WHERE storage_key = ?",
                [doc_id],
            ).fetchone()
            if row is None:
                logger.log(
                    document_id=doc_id, step="grep",
                    duration_ms=elapsed_ms, status="skipped_no_document",
                    match_count=len(matches),
                )
                continue
            document_id = row[0]

            docs_with_matches += 1
            for m in matches:
                con.execute(
                    """INSERT INTO grep_matches
                       (document_id, pattern_name, pattern_version,
                        page_number, matched_text, context_before,
                        context_after, run_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        document_id, m.pattern_name, m.pattern_version,
                        m.page_index + 1,  # Store 1-indexed in DB
                        m.matched_text,
                        m.context_before, m.context_after, m.run_id,
                    ],
                )
            total_matches += len(matches)

        logger.log(
            document_id=doc_id, step="grep",
            duration_ms=elapsed_ms, status="success",
            match_count=len(matches),
        )

    con.commit()
    con.close()

    click.echo(
        f"Done. {total_matches} matches across {docs_with_matches} documents "
        f"(of {len(text_files)} scanned)."
    )
```

- [ ] **Step 3: Update Makefile**

```makefile
grep:
	uv run corpus grep run --run-id $(RUN_ID)
```

- [ ] **Step 4: Test single-doc mode**

```bash
# First make sure at least one PDIP doc is parsed
uv run corpus parse run --run-id test --source pdip --limit 5
# Then test grep
uv run corpus grep doc --pattern collective_action --doc pdip__VEN85 --verbose
```

- [ ] **Step 5: Commit**

```bash
git add src/corpus/cli.py Makefile
git commit -m "feat: corpus grep doc + corpus grep run CLI commands"
```

---

## Session 4: Validate + Full Corpus

### Task 11: Validation Module

**Files:**
- Create: `src/corpus/extraction/validate.py`

- [ ] **Step 1: Implement validation module**

```python
# src/corpus/extraction/validate.py
"""Validate grep results against PDIP annotations.

Computes document-level presence precision and recall per clause family.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from corpus.extraction.label_mapping import PDIP_LABEL_TO_FAMILY


def load_pdip_presence(
    clause_annotations_path: Path,
) -> dict[str, set[str]]:
    """Load PDIP annotations as {doc_id: set of label_families}.

    Only includes families that are not None (mapped families).
    """
    doc_families: dict[str, set[str]] = defaultdict(set)
    with clause_annotations_path.open() as f:
        for line in f:
            record = json.loads(line)
            family = record.get("label_family")
            if family:
                doc_families[record["doc_id"]].add(family)
    return dict(doc_families)


def load_grep_presence(
    parsed_dir: Path,
    grep_matches_path: Path | None = None,
    *,
    db_path: Path | None = None,
) -> dict[str, set[str]]:
    """Load grep results as {storage_key: set of pattern_names}.

    Reads from DuckDB if db_path is provided, otherwise from a JSONL file.
    """
    doc_patterns: dict[str, set[str]] = defaultdict(set)

    if db_path:
        import duckdb

        con = duckdb.connect(str(db_path), read_only=True)
        rows = con.execute(
            """SELECT d.storage_key, gm.pattern_name
               FROM grep_matches gm
               JOIN documents d ON gm.document_id = d.document_id"""
        ).fetchall()
        con.close()
        for storage_key, pattern_name in rows:
            doc_patterns[storage_key].add(pattern_name)
    return dict(doc_patterns)


def compute_validation_report(
    pdip_presence: dict[str, set[str]],
    grep_presence: dict[str, set[str]],
    *,
    pdip_doc_id_to_storage_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compute precision and recall per family.

    Args:
        pdip_presence: {doc_id: set of families} from PDIP
        grep_presence: {storage_key: set of pattern families} from grep
        pdip_doc_id_to_storage_key: mapping from PDIP doc_id to storage_key
            (e.g., "VEN85" -> "pdip__VEN85"). If None, assumes
            storage_key = f"pdip__{doc_id}".
    """
    families_in_scope = set()
    for fams in pdip_presence.values():
        families_in_scope.update(fams)
    for pats in grep_presence.values():
        families_in_scope.update(pats)

    results: dict[str, Any] = {}

    for family in sorted(families_in_scope):
        # Documents where PDIP says this family is present
        pdip_positive_docs = {
            doc_id for doc_id, fams in pdip_presence.items() if family in fams
        }

        # Map PDIP doc_ids to storage_keys for comparison
        if pdip_doc_id_to_storage_key:
            pdip_storage_keys = {
                pdip_doc_id_to_storage_key.get(d, f"pdip__{d}")
                for d in pdip_positive_docs
            }
        else:
            pdip_storage_keys = {f"pdip__{d}" for d in pdip_positive_docs}

        # Documents where grep says this family is present
        grep_positive_docs = {
            sk for sk, pats in grep_presence.items() if family in pats
        }

        tp = len(pdip_storage_keys & grep_positive_docs)
        fn = len(pdip_storage_keys - grep_positive_docs)
        fp = len(grep_positive_docs - pdip_storage_keys)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        results[family] = {
            "true_positives": tp,
            "false_negatives": fn,
            "false_positives": fp,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "pdip_docs": len(pdip_positive_docs),
            "grep_docs": len(grep_positive_docs),
        }

    return {
        "families": results,
        "total_pdip_docs": len(pdip_presence),
        "total_grep_docs": len(grep_presence),
    }


def write_validation_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    """Write validation report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
```

- [ ] **Step 2: Run validation against PDIP**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.validate import (
    load_pdip_presence, compute_validation_report, write_validation_report,
)
import json

pdip = load_pdip_presence(Path('data/pdip/clause_annotations.jsonl'))
print(f'PDIP docs with families: {len(pdip)}')

# For now, compare against grep results if available
# (This will be empty until grep run completes)
from corpus.extraction.validate import load_grep_presence
grep = load_grep_presence(
    parsed_dir=Path('data/parsed'),
    db_path=Path('data/db/corpus.duckdb'),
)
print(f'Grep docs with matches: {len(grep)}')

report = compute_validation_report(pdip, grep)
write_validation_report(report, Path('data/output/validation_report.json'))
print(json.dumps(report, indent=2))
"
```

- [ ] **Step 3: Commit**

```bash
git add src/corpus/extraction/validate.py
git commit -m "feat: validation module — precision/recall per family vs PDIP"
```

---

### Task 12: Full Corpus Parse + Grep (Overnight)

**No new files — operational task.**

- [ ] **Step 1: Parse PDIP documents first (validation path)**

```bash
uv run corpus parse run --run-id parse-pdip --source pdip
```

- [ ] **Step 2: Run grep on PDIP documents**

```bash
uv run corpus grep run --run-id grep-pdip --source pdip
```

- [ ] **Step 3: Run validation**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.validate import *
import json

pdip = load_pdip_presence(Path('data/pdip/clause_annotations.jsonl'))
grep = load_grep_presence(parsed_dir=Path('data/parsed'), db_path=Path('data/db/corpus.duckdb'))
report = compute_validation_report(pdip, grep)
write_validation_report(report, Path('data/output/validation_report.json'))
print(json.dumps(report, indent=2))
"
```

Review precision/recall. Refine patterns if recall < 80% on key families.

- [ ] **Step 4: Parse remaining corpus (overnight, scaling path)**

```bash
uv run corpus parse run --run-id parse-full --source all
```

- [ ] **Step 5: Run grep on full corpus**

```bash
uv run corpus grep run --run-id grep-full
```

- [ ] **Step 6: Generate output artifacts**

```bash
uv run python3 -c "
import duckdb, json
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')

# Corpus summary
summary = {
    'total_documents': con.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
    'pdip_annotated_clauses': con.execute('SELECT COUNT(*) FROM pdip_clauses').fetchone()[0],
    'grep_matches': con.execute('SELECT COUNT(*) FROM grep_matches').fetchone()[0],
    'documents_with_matches': con.execute('SELECT COUNT(DISTINCT document_id) FROM grep_matches').fetchone()[0],
}

Path('data/output').mkdir(parents=True, exist_ok=True)
with open('data/output/corpus_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print(json.dumps(summary, indent=2))
con.close()
"
```

- [ ] **Step 7: Commit**

```bash
git add data/output/validation_report.json data/output/corpus_summary.json
git commit -m "feat: validation report and corpus summary artifacts"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] PDIP clause extraction with text, labels, bounding boxes → Tasks 1-5
- [x] Page number validation (0-indexed internal, 1-indexed display) → Task 4
- [x] Zero-clause investigation → Task 5
- [x] Label family mapping with unmapped report → Task 1
- [x] Demo insurance queries → Task 5
- [x] PDF + TXT + HTM parsers with encoding fallback → Task 6
- [x] Parse CLI command with quality flags → Task 7
- [x] ClausePattern dataclass + starter patterns → Task 8
- [x] Grep runner with document-wide search + page mapping → Task 9
- [x] Single-doc grep CLI mode → Task 10
- [x] Full corpus grep CLI mode → Task 10
- [x] Validation module with precision/recall → Task 11
- [x] Full corpus parse + grep overnight → Task 12
- [x] Copy raw JSON into repo → Task 3
- [x] DuckDB schema additions (pdip_clauses, run_id) → Task 5
- [x] `text_status` field (present/empty/missing) → Task 2
- [x] Governing law: evidence only, not resolution → Task 8 (pattern stores all hits)
- [x] Decoupled validation path vs scaling path → Sessions ordered correctly

**Placeholder scan:** No TBD, TODO, or "implement later" found.

**Type consistency:** `GrepMatch`, `ClausePattern`, `ParseResult` used consistently. `page_index` (0-indexed) used in all internal data. `grep_document()` signature consistent between test and implementation.
