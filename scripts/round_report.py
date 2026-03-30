#!/usr/bin/env python3
# scripts/round_report.py
"""Generate round reports for extraction quality metrics.

C1: --run-id is the primary argument; --run-dir is derived from it by default.
I6: Separates api_error from not_found and computes PDIP recall/precision.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def generate_family_report(
    *,
    family: str,
    verified_path: Path,
    annotations_path: Path | None = None,
) -> dict:
    """Generate quality metrics for a single family extraction."""
    records = []
    with verified_path.open() as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    found = [r for r in records if r.get("extraction", {}).get("found")]
    not_found = [
        r
        for r in records
        if not r.get("extraction", {}).get("found")
        and r.get("verification", {}).get("status") != "api_error"
    ]
    api_errors = [r for r in records if r.get("verification", {}).get("status") == "api_error"]
    verified = [
        r
        for r in found
        if r.get("verification", {}).get("status") in ("verified", "section_located")
    ]
    failed = [
        r for r in found if r.get("verification", {}).get("status") in ("failed", "needs_review")
    ]

    # Source mix
    source_mix = Counter(r.get("source_format", "unknown") for r in records)
    heading_match_count = sum(1 for r in records if r.get("heading_match"))

    # Confidence distribution
    confidence_dist = Counter(r.get("extraction", {}).get("confidence", "unknown") for r in found)

    report: dict = {
        "family": family,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_candidates": len(records),
        "found_count": len(found),
        "not_found_count": len(not_found),
        "api_error_count": len(api_errors),
        "verbatim_pass_count": len(verified),
        "verbatim_fail_count": len(failed),
        "verbatim_pass_rate": round(len(verified) / len(found), 3) if found else 0,
        "source_mix": dict(source_mix),
        "heading_match_count": heading_match_count,
        "body_only_count": len(records) - heading_match_count,
        "confidence_distribution": dict(confidence_dist),
    }

    # Compute PDIP recall/precision if annotations available
    if annotations_path and annotations_path.exists():
        pdip_doc_ids = set()
        with annotations_path.open() as f:
            for line in f:
                try:
                    ann = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ann.get("label_family") == family:
                    pdip_doc_ids.add(ann.get("doc_id"))

        if pdip_doc_ids:
            # Match PDIP doc_ids to storage_keys using the suffix after "__"
            # to avoid false substring matches (e.g., "GHA1" matching "GHA10").
            # Use verified (not just found) to exclude hallucinated extractions.
            extracted_doc_ids = {
                k.split("__", 1)[-1] if "__" in k else k
                for k in (r.get("storage_key", "") for r in verified)
            }
            pdip_found = sum(1 for d in pdip_doc_ids if d in extracted_doc_ids)
            report["pdip_recall"] = round(pdip_found / len(pdip_doc_ids), 3) if pdip_doc_ids else 0
            report["pdip_annotated_count"] = len(pdip_doc_ids)
            report["pdip_matched_count"] = pdip_found

    return report


def format_phone_status(reports: list[dict], run_id: str) -> str:
    """Format a concise status for iPhone review."""
    lines = [f"Run {run_id} status:\n"]
    for r in reports:
        fam = r["family"]
        found = r["found_count"]
        total = r["total_candidates"]
        errors = r.get("api_error_count", 0)
        rate = f"{r['verbatim_pass_rate']:.0%}" if r["found_count"] else "N/A"
        error_note = f" ({errors} errors)" if errors else ""
        lines.append(f"  {fam}: {found}/{total} found, {rate} verbatim{error_note}")
    lines.append("\nReady for next family? Reply 'go' or give feedback.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate round report")
    parser.add_argument("--run-id", type=str, required=True)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Override run directory (default: data/extracted_v2/<run-id>)",
    )
    parser.add_argument("--family", type=str, default=None, help="Single family or all")
    parser.add_argument(
        "--annotations",
        type=Path,
        default=None,
        help="Path to PDIP annotations JSONL for recall computation",
    )
    args = parser.parse_args()

    run_dir = args.run_dir or Path(f"data/extracted_v2/{args.run_id}")

    if not run_dir.exists():
        print(f"ERROR: Run directory does not exist: {run_dir}")
        raise SystemExit(1)

    reports = []

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
            print(f"  {family}: no verified.jsonl found, skipping")
            continue
        report = generate_family_report(
            family=family,
            verified_path=verified_path,
            annotations_path=args.annotations,
        )
        reports.append(report)
        errors = report.get("api_error_count", 0)
        error_note = f" ({errors} api_errors)" if errors else ""
        print(
            f"  {family}: {report['found_count']}/{report['total_candidates']} found, "
            f"{report['verbatim_pass_rate']:.0%} verbatim{error_note}"
        )

    # Write JSON report
    report_path = run_dir / "round_report.json"
    report_path.write_text(json.dumps(reports, indent=2) + "\n")
    print(f"\nReport written to {report_path}")

    # Print phone-friendly status
    print("\n" + format_phone_status(reports, args.run_id))


if __name__ == "__main__":
    main()
