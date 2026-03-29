# demo/data/export_v2.py
"""Export v2 extraction results for the Shiny clause eval explorer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
VERIFIED_DIR = Path("data/extracted_v2")
OUTPUT_PATH = DATA_DIR / "clause_candidates_v2.csv"


def export_v2_candidates(
    verified_dir: Path = VERIFIED_DIR,
    output_path: Path = OUTPUT_PATH,
) -> None:
    """Export verified extractions to CSV for Shiny app."""
    records = []

    # Process all verified JSONL files
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

                records.append(
                    {
                        "candidate_id": rec["candidate_id"],
                        "storage_key": rec["storage_key"],
                        "country": rec.get("country", ""),
                        "document_title": rec.get("document_title", rec["storage_key"]),
                        "section_heading": rec["section_heading"],
                        "page_start": rec["page_range"][0] if rec.get("page_range") else "",
                        "page_end": rec["page_range"][1] if rec.get("page_range") else "",
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if records:
        with output_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)

    print(f"Exported {len(records)} verified extractions to {output_path}")


if __name__ == "__main__":
    export_v2_candidates()
