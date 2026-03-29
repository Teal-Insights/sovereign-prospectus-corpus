#!/usr/bin/env python3
# scripts/dedup_extractions.py
"""Deduplicate extractions: pick best candidate per document per family.

Many documents produce multiple candidates (e.g., supplement summary + base
prospectus operative clause). This script picks the "primary" extraction per
document and flags others as duplicates.

Selection criteria (in priority order):
1. Highest confidence (high > medium > low)
2. Heading-matched over body-only
3. Longest clause_text (more complete extraction)
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}


def _sort_key(record: dict) -> tuple:
    """Sort key for selecting the best candidate. Higher = better."""
    ext = record.get("extraction", {})
    confidence = _CONFIDENCE_RANK.get(ext.get("confidence", "low"), 0)
    heading = 1 if record.get("heading_match") else 0
    clause_len = len(ext.get("clause_text", ""))
    return (confidence, heading, clause_len)


def dedup_family(verified_path: Path, output_path: Path) -> dict:
    """Deduplicate a single family's verified.jsonl.

    Returns summary stats.
    """
    records = []
    with verified_path.open() as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Group found extractions by storage_key
    by_doc: dict[str, list[dict]] = defaultdict(list)
    not_found = []
    for r in records:
        if r.get("extraction", {}).get("found"):
            by_doc[r["storage_key"]].append(r)
        else:
            not_found.append(r)

    # Select best per document
    primary = []
    duplicates = []
    for storage_key, candidates in by_doc.items():
        candidates.sort(key=_sort_key, reverse=True)
        best = candidates[0]
        best["dedup"] = {"is_primary": True, "duplicates_count": len(candidates) - 1}
        primary.append(best)
        for dup in candidates[1:]:
            dup["dedup"] = {"is_primary": False, "primary_candidate_id": best["candidate_id"]}
            duplicates.append(dup)

    # Write deduplicated output (primary + not_found only)
    with output_path.open("w") as f:
        for r in primary + not_found:
            f.write(json.dumps(r) + "\n")

    return {
        "total_records": len(records),
        "unique_docs_found": len(by_doc),
        "primary_extractions": len(primary),
        "duplicates_removed": len(duplicates),
        "not_found": len(not_found),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate extractions per document")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--family", type=str, default=None, help="Single family or all")
    args = parser.parse_args()

    run_dir = args.run_dir or Path(f"data/extracted_v2/{args.run_id}")

    if not run_dir.exists():
        print(f"ERROR: Run directory does not exist: {run_dir}")
        raise SystemExit(1)

    if args.family:
        families = [args.family]
    else:
        families = [
            d.name
            for d in sorted(run_dir.iterdir())
            if d.is_dir() and (d / "verified.jsonl").exists()
        ]

    for family in families:
        verified_path = run_dir / family / "verified.jsonl"
        if not verified_path.exists():
            print(f"  {family}: no verified.jsonl, skipping")
            continue
        output_path = run_dir / family / "deduplicated.jsonl"
        stats = dedup_family(verified_path, output_path)
        print(
            f"  {family}: {stats['primary_extractions']} primary extractions "
            f"({stats['duplicates_removed']} duplicates removed, "
            f"{stats['not_found']} not_found)"
        )

    print("\nDone. Deduplicated files written as deduplicated.jsonl per family.")


if __name__ == "__main__":
    main()
