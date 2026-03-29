# demo/data/export_v2.py
"""Export v2 extraction results for the Shiny clause eval explorer."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
# Ensure corpus package is importable when run as a script
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

VERIFIED_DIR = _REPO_ROOT / "data" / "extracted_v2"
OUTPUT_PATH = _SCRIPT_DIR / "clause_candidates_v2.csv"

from corpus.extraction.country import guess_country as _guess_country  # noqa: E402


def export_v2_candidates(
    verified_dir: Path = VERIFIED_DIR,
    output_path: Path = OUTPUT_PATH,
) -> None:
    """Export verified extractions to CSV for Shiny app."""
    records = []

    for verified_path in sorted(verified_dir.glob("*_verified.jsonl")):
        with verified_path.open() as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ext = rec.get("extraction", {})
                ver = rec.get("verification", {})

                if not ext.get("found"):
                    continue

                # Determine page display
                page_range = rec.get("page_range", [])
                source_fmt = rec.get("source_format", "")
                if (
                    isinstance(page_range, list)
                    and len(page_range) >= 2
                    and source_fmt == "flat_jsonl"  # EDGAR has real pages
                ):
                    # Display as 1-indexed
                    page_start = str(page_range[0] + 1)
                    page_end = str(page_range[1] + 1)
                else:
                    # Docling pages are placeholders
                    page_start = ""
                    page_end = ""

                country = rec.get("country", "") or _guess_country(rec.get("storage_key", ""))

                records.append(
                    {
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
                        "components_present": ver.get("components_present", ""),
                        "components_total": ver.get("components_total", ""),
                        "quality_flags": ", ".join(ver.get("quality_flags", [])),
                        "completeness": json.dumps(ver.get("completeness", {})),
                        "source_format": rec.get("source_format", ""),
                        "run_id": rec.get("run_id", ""),
                        "clause_family": rec.get("clause_family", ""),
                    }
                )

    # Always overwrite — even if zero records (prevents stale data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "components_present",
        "components_total",
        "quality_flags",
        "completeness",
        "source_format",
        "run_id",
        "clause_family",
    ]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Exported {len(records)} verified extractions to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export v2 extraction results")
    parser.add_argument(
        "--input",
        type=Path,
        default=VERIFIED_DIR,
        help="Directory containing *_verified.jsonl files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Output CSV path",
    )
    args = parser.parse_args()
    export_v2_candidates(verified_dir=args.input, output_path=args.output)
