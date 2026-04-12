#!/usr/bin/env python3
"""Validate overnight Docling parse output.

Run this in the morning before proceeding with promotion/rebuild.

Checks:
1. JSONL + MD file counts match
2. Every JSONL has a valid header with required fields
3. Every JSONL has page_count pages (no dropped pages)
4. No orphan .md without .jsonl (or vice versa)
5. Parse status distribution
6. Error log summary
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "parsed_docling"
ERRORS_LOG = OUTPUT_DIR / "_errors.log"

REQUIRED_HEADER_FIELDS = {
    "storage_key",
    "page_count",
    "parse_tool",
    "parse_version",
    "parse_status",
}


def validate() -> bool:
    """Run all validation checks. Returns True if all pass."""
    ok = True

    # Count files
    jsonl_files = sorted(f for f in OUTPUT_DIR.glob("*.jsonl") if not f.name.startswith("_"))
    md_files = sorted(f for f in OUTPUT_DIR.glob("*.md") if not f.name.startswith("_"))

    jsonl_keys = {f.stem for f in jsonl_files}
    md_keys = {f.stem for f in md_files}

    print(f"JSONL files: {len(jsonl_files)}")
    print(f"MD files:    {len(md_files)}")

    # Check for orphans
    jsonl_only = jsonl_keys - md_keys
    md_only = md_keys - jsonl_keys
    if jsonl_only:
        print(
            f"WARNING: {len(jsonl_only)} JSONL files without matching MD: {list(jsonl_only)[:5]}..."
        )
        ok = False
    if md_only:
        print(f"WARNING: {len(md_only)} MD files without matching JSONL: {list(md_only)[:5]}...")
        ok = False

    # Validate headers and page counts
    status_counts: Counter[str] = Counter()
    bad_headers = 0
    page_mismatch = 0
    empty_pages = 0
    total_pages = 0

    for jsonl_path in jsonl_files:
        try:
            with jsonl_path.open() as f:
                lines = f.readlines()
        except OSError:
            bad_headers += 1
            continue

        if not lines:
            bad_headers += 1
            continue

        # Validate header
        try:
            header = json.loads(lines[0])
        except json.JSONDecodeError:
            bad_headers += 1
            continue

        missing = REQUIRED_HEADER_FIELDS - set(header.keys())
        if missing:
            print(f"  {jsonl_path.name}: missing header fields: {missing}")
            bad_headers += 1
            continue

        status_counts[header["parse_status"]] += 1
        expected_pages = header["page_count"]
        actual_pages = len(lines) - 1  # Subtract header line
        total_pages += actual_pages

        if actual_pages != expected_pages:
            page_mismatch += 1
            if page_mismatch <= 5:
                print(f"  {jsonl_path.name}: expected {expected_pages} pages, got {actual_pages}")

        # Check page contiguity and empty pages
        page_numbers = []
        for line in lines[1:]:
            try:
                page = json.loads(line)
                if page.get("char_count", 0) == 0:
                    empty_pages += 1
                page_numbers.append(page.get("page", -1))
            except json.JSONDecodeError:
                pass
        expected_seq = list(range(expected_pages))
        if page_numbers and page_numbers != expected_seq:
            page_mismatch += 1
            if page_mismatch <= 5:
                print(f"  {jsonl_path.name}: non-contiguous pages {page_numbers[:5]}...")

    print(f"\nHeader validation: {bad_headers} bad headers out of {len(jsonl_files)}")
    print(f"Page count mismatches: {page_mismatch}")
    print(f"Total pages: {total_pages:,}")
    print(f"Empty pages: {empty_pages}")

    print("\nParse status distribution:")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count}")

    if bad_headers > 0:
        ok = False
    if page_mismatch > 0:
        print(f"WARNING: {page_mismatch} files have page count mismatches!")
        ok = False

    # Check errors log
    if ERRORS_LOG.exists():
        error_lines = ERRORS_LOG.read_text().strip().split("\n")
        error_lines = [line for line in error_lines if line.strip()]
        print(f"\nErrors log: {len(error_lines)} entries")
        if error_lines:
            error_rate = len(error_lines) / max(len(jsonl_files), 1) * 100
            print(f"Error rate: {error_rate:.1f}%")
            if error_rate > 5:
                print("WARNING: Error rate exceeds 5% budget!")
                ok = False
            print("First 5 errors:")
            for line in error_lines[:5]:
                print(f"  {line[:120]}")
    else:
        print("\nNo errors log found (good — no errors)")

    # Compare output count to expected input PDFs
    input_dirs = [
        PROJECT_ROOT / "data" / "original",
        PROJECT_ROOT / "data" / "pdfs" / "pdip",
    ]
    input_pdf_count = 0
    for d in input_dirs:
        if d.exists():
            input_pdf_count += len(list(d.rglob("*.pdf")))
    if input_pdf_count > 0:
        coverage = len(jsonl_files) / input_pdf_count * 100
        print(
            f"\nInput PDFs: {input_pdf_count}, Output JSONL: {len(jsonl_files)} ({coverage:.0f}% coverage)"
        )
        if coverage < 90:
            print(f"WARNING: Only {coverage:.0f}% of input PDFs were parsed!")
            ok = False

    # Check for stale .part files
    part_files = list(OUTPUT_DIR.glob("*.part"))
    if part_files:
        print(f"\nWARNING: {len(part_files)} stale .part files found (incomplete writes)")
        ok = False

    # Summary
    print(f"\n{'=' * 50}")
    if ok:
        print("PASS — all checks passed. Safe to proceed with promotion.")
    else:
        print("FAIL — issues found. Review above before proceeding.")

    return ok


if __name__ == "__main__":
    passed = validate()
    sys.exit(0 if passed else 1)
