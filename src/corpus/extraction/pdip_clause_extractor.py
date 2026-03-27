"""Extract clause-level data from raw PDIP API JSON responses.

Reads the saved raw JSON files from a prior annotations harvest and
produces a structured JSONL file with one record per clause annotation,
including text, bounding box, label family mapping, and document metadata.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from corpus.extraction.label_mapping import map_label, unmapped_labels

if TYPE_CHECKING:
    from pathlib import Path

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
        extract_clause_record(clause=c, doc_id=doc_id, doc_metadata=doc_metadata) for c in clauses
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
