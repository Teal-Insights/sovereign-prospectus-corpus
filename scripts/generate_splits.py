#!/usr/bin/env python3
# scripts/generate_splits.py
"""Generate PDIP calibration/evaluation splits for all clause families."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from corpus.extraction.pdip_split import create_split, save_split

ANNOTATIONS_PATH = Path("data/pdip/clause_annotations.jsonl")
SPLITS_DIR = Path("data/pdip/splits")

# Required families for Round 1
REQUIRED_ROUND_1 = {
    "governing_law",
    "sovereign_immunity",
    "negative_pledge",
    "events_of_default",
}

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> None:
    if not ANNOTATIONS_PATH.exists():
        print(f"ERROR: Annotations file not found: {ANNOTATIONS_PATH}")
        sys.exit(1)

    # Discover all families using unique doc_ids per family
    families: dict[str, set[str]] = {}
    with ANNOTATIONS_PATH.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            lf = r.get("label_family")
            doc_id = r.get("doc_id", "unknown")
            if lf:
                if lf not in families:
                    families[lf] = set()
                families[lf].add(doc_id)

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    # Verify label_family names match snake_case
    non_snake = [f for f in families if not _SNAKE_CASE_RE.match(f)]
    if non_snake:
        print(f"WARNING: Non-snake_case label_family names: {non_snake}")
        print("These may need mapping to match clause family names.")

    print(f"Found {len(families)} label families in annotations:")
    for fam in sorted(families):
        print(f"  {fam}: {len(families[fam])} unique docs")

    generated = []
    for family in sorted(families):
        split_path = SPLITS_DIR / f"{family}_split.json"
        if split_path.exists():
            print(f"  {family}: split already exists, skipping")
            generated.append(family)
            continue

        unique_docs = len(families[family])
        cal_count = 2 if unique_docs < 15 else 3 if unique_docs < 40 else 5

        try:
            split = create_split(
                ANNOTATIONS_PATH,
                clause_family=family,
                calibration_count=cal_count,
            )
            save_split(split, split_path, overwrite=False)
            cal = len(split["calibration"])
            eva = len(split["evaluation"])
            print(f"  {family}: {cal} calibration, {eva} evaluation ({unique_docs} unique docs)")
            generated.append(family)
        except ValueError as e:
            print(f"  {family}: SKIPPED -- {e}")

    # Exit non-zero if required Round 1 families are missing
    missing_required = REQUIRED_ROUND_1 - set(generated)
    if missing_required:
        print(f"\nERROR: Required Round 1 families missing: {sorted(missing_required)}")
        sys.exit(1)

    print(f"\nGenerated splits for {len(generated)} families.")


if __name__ == "__main__":
    main()
