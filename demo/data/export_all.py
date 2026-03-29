# demo/data/export_all.py
"""Unified export script for all extraction families and document classification.

Reads:
  - data/extracted_v2/cac_verified.jsonl
  - data/extracted_v2/pp_verified.jsonl
  - data/extracted_v2/2026-03-29_round1/*/verified.jsonl  (families with COMPLETE.json)
  - data/extracted_v2/2026-03-29_round1/document_classification/classification.jsonl

Outputs to demo/data/:
  - all_extractions.csv      — clause extractions (found=True only), all families unified
  - classification.csv       — document classification records
  - corpus_summary.csv       — per-country, per-family counts
"""

from __future__ import annotations

import collections
import csv
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from corpus.extraction.country import guess_country as _guess_country  # noqa: E402

VERIFIED_DIR = _REPO_ROOT / "data" / "extracted_v2"
ROUND1_DIR = VERIFIED_DIR / "2026-03-29_round1"

ALL_EXTRACTIONS_PATH = _SCRIPT_DIR / "all_extractions.csv"
CLASSIFICATION_PATH = _SCRIPT_DIR / "classification.csv"
CORPUS_SUMMARY_PATH = _SCRIPT_DIR / "corpus_summary.csv"

EXTRACTION_FIELDNAMES = [
    "candidate_id",
    "storage_key",
    "country",
    "document_title",
    "section_heading",
    "page_start",
    "page_end",
    "heading_match",
    "cue_families",
    "llm_confidence",
    "llm_reasoning",
    "clause_text",
    "clause_length",
    "section_text",
    "verbatim_status",
    "verbatim_similarity",
    "quality_flags",
    "source_format",
    "run_id",
    "clause_family",
]

CLASSIFICATION_FIELDNAMES = [
    "storage_key",
    "instrument_family",
    "document_role",
    "document_form",
    "confidence",
]


def _page_range(rec: dict) -> tuple[str, str]:
    """Return (page_start, page_end) strings, 1-indexed, only for flat_jsonl source."""
    page_range = rec.get("page_range", [])
    source_fmt = rec.get("source_format", "")
    if isinstance(page_range, list) and len(page_range) >= 2 and source_fmt == "flat_jsonl":
        return str(page_range[0] + 1), str(page_range[1] + 1)
    return "", ""


def _extraction_row(rec: dict) -> dict:
    """Build a single extractions CSV row from a verified JSONL record."""
    ext = rec.get("extraction", {})
    ver = rec.get("verification", {})

    country = rec.get("country", "") or _guess_country(rec.get("storage_key", ""))
    page_start, page_end = _page_range(rec)

    return {
        "candidate_id": rec.get("candidate_id", ""),
        "storage_key": rec.get("storage_key", ""),
        "country": country,
        "document_title": rec.get("document_title") or rec.get("storage_key", ""),
        "section_heading": rec.get("section_heading", ""),
        "page_start": page_start,
        "page_end": page_end,
        "heading_match": "Yes" if rec.get("heading_match") else "No",
        "cue_families": ", ".join(rec.get("cue_families_hit", [])),
        "llm_confidence": ext.get("confidence", ""),
        "llm_reasoning": ext.get("reasoning", ""),
        "clause_text": ext.get("clause_text", ""),
        "clause_length": len(ext.get("clause_text", "")),
        "section_text": rec.get("section_text", ""),
        "verbatim_status": ver.get("status", ""),
        "verbatim_similarity": ver.get("verbatim_similarity", ""),
        "quality_flags": ", ".join(ver.get("quality_flags", [])),
        "source_format": rec.get("source_format", ""),
        "run_id": rec.get("run_id", ""),
        "clause_family": rec.get("clause_family", ""),
    }


def _read_verified_jsonl(path: Path) -> list[dict]:
    """Read a verified JSONL file, returning only records where extraction.found is True."""
    rows = []
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  WARNING: JSON parse error in {path}:{line_no}: {exc}")
                continue
            if rec.get("extraction", {}).get("found"):
                rows.append(_extraction_row(rec))
    return rows


def _read_classification_jsonl(path: Path) -> list[dict]:
    """Read a classification JSONL file."""
    rows = []
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"  WARNING: JSON parse error in {path}:{line_no}: {exc}")
                continue
            rows.append(
                {
                    "storage_key": rec.get("storage_key", ""),
                    "instrument_family": rec.get("instrument_family", ""),
                    "document_role": rec.get("document_role", ""),
                    "document_form": rec.get("document_form", ""),
                    "confidence": rec.get("confidence", ""),
                }
            )
    return rows


def export_all() -> None:
    extraction_rows: list[dict] = []

    # --- v1 flat files ---
    v1_files = [
        VERIFIED_DIR / "cac_verified.jsonl",
        VERIFIED_DIR / "pp_verified.jsonl",
    ]
    for path in v1_files:
        if not path.exists():
            print(f"  SKIP (not found): {path}")
            continue
        rows = _read_verified_jsonl(path)
        print(f"  v1 {path.name}: {len(rows)} found extractions")
        extraction_rows.extend(rows)

    # --- Round 1 family directories ---
    if ROUND1_DIR.exists():
        for family_dir in sorted(ROUND1_DIR.iterdir()):
            if not family_dir.is_dir():
                continue
            if family_dir.name == "document_classification":
                continue  # handled separately
            complete_file = family_dir / "COMPLETE.json"
            verified_file = family_dir / "verified.jsonl"
            if not complete_file.exists():
                print(f"  SKIP (no COMPLETE.json): {family_dir.name}")
                continue
            if not verified_file.exists():
                print(f"  SKIP (no verified.jsonl): {family_dir.name}")
                continue
            rows = _read_verified_jsonl(verified_file)
            print(f"  round1/{family_dir.name}: {len(rows)} found extractions")
            extraction_rows.extend(rows)
    else:
        print(f"  SKIP (round1 dir not found): {ROUND1_DIR}")

    # --- Document classification ---
    classification_rows: list[dict] = []
    classification_file = ROUND1_DIR / "document_classification" / "classification.jsonl"
    if classification_file.exists():
        classification_rows = _read_classification_jsonl(classification_file)
        print(f"  classification: {len(classification_rows)} records")
    else:
        print(f"  SKIP (not found): {classification_file}")

    # --- Corpus summary: count by country + clause_family ---
    counter: dict[tuple[str, str], int] = collections.Counter()
    for row in extraction_rows:
        country = row["country"] or "Unknown"
        family = row["clause_family"] or "unknown"
        counter[(country, family)] += 1

    summary_rows = [
        {"country": country, "clause_family": family, "count": count}
        for (country, family), count in sorted(counter.items())
    ]

    # --- Write outputs ---
    _SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    with ALL_EXTRACTIONS_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXTRACTION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(extraction_rows)
    print(f"\nWrote {len(extraction_rows)} rows -> {ALL_EXTRACTIONS_PATH}")

    with CLASSIFICATION_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CLASSIFICATION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(classification_rows)
    print(f"Wrote {len(classification_rows)} rows -> {CLASSIFICATION_PATH}")

    with CORPUS_SUMMARY_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "clause_family", "count"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote {len(summary_rows)} rows -> {CORPUS_SUMMARY_PATH}")


if __name__ == "__main__":
    export_all()
