"""Tests for PDIP clause extractor."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from corpus.extraction.pdip_clause_extractor import (
    extract_clause_record,
    extract_document_clauses,
    process_raw_files,
)

if TYPE_CHECKING:
    from pathlib import Path

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
