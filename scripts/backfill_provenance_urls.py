"""Backfill source_page_url and source_page_kind into existing JSONL manifests.

For each ``data/manifests/*_manifest.jsonl`` file, read every record, call
``resolve_source_page`` from ``corpus.sources.provenance``, and write the
record back with the two new fields. Atomic ``.part`` → rename per file.
Idempotent — records that already have both fields set are preserved as-is.

Usage:
    uv run python scripts/backfill_provenance_urls.py
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from corpus.sources.provenance import resolve_source_page


def _backfill_one(path: Path) -> tuple[int, int]:
    """Rewrite a single manifest file with provenance URL fields added.

    Returns ``(records_total, records_updated)``.
    """
    part = path.with_suffix(path.suffix + ".part")
    total = 0
    updated = 0
    with path.open() as src, part.open("w") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            total += 1
            record: dict[str, Any] = json.loads(line)
            if record.get("source_page_url") and record.get("source_page_kind"):
                # Already has both fields — preserve as-is.
                dst.write(json.dumps(record) + "\n")
                continue
            url, kind = resolve_source_page(record)
            record["source_page_url"] = url
            record["source_page_kind"] = kind
            dst.write(json.dumps(record) + "\n")
            updated += 1
    os.replace(part, path)
    return total, updated


def backfill_manifests(*, manifest_dir: Path) -> dict[str, int]:
    """Backfill all ``*_manifest.jsonl`` files in the given directory."""
    files = sorted(manifest_dir.glob("*_manifest.jsonl"))
    totals = {"files_rewritten": 0, "records_total": 0, "records_updated": 0}
    for path in files:
        total, updated = _backfill_one(path)
        totals["files_rewritten"] += 1
        totals["records_total"] += total
        totals["records_updated"] += updated
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifests"),
        help="Directory containing *_manifest.jsonl files",
    )
    args = parser.parse_args()
    stats = backfill_manifests(manifest_dir=args.manifest_dir)
    print(
        f"Rewrote {stats['files_rewritten']} manifest file(s): "
        f"{stats['records_updated']} / {stats['records_total']} records updated."
    )


if __name__ == "__main__":
    main()
