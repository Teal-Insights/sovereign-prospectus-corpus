# src/corpus/extraction/pdip_split.py
"""PDIP calibration/evaluation split management.

Creates and loads a frozen split of PDIP-annotated documents for prompt
development (calibration) vs. metric reporting (evaluation). The split
must be frozen and committed before any LLM extraction runs.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in function bodies


def create_split(
    annotations_path: Path,
    *,
    clause_family: str,
    calibration_count: int = 5,
    seed: int = 42,
) -> dict:
    """Create a calibration/evaluation split from PDIP annotations."""
    doc_ids: set[str] = set()
    with annotations_path.open() as f:
        for line in f:
            record = json.loads(line)
            if record.get("label_family") == clause_family:
                doc_ids.add(record["doc_id"])

    doc_list = sorted(doc_ids)

    # E8: Guard against insufficient docs
    if len(doc_list) < calibration_count:
        raise ValueError(
            f"Only {len(doc_list)} docs found for {clause_family}, "
            f"need {calibration_count}. Check label_family field name."
        )

    rng = random.Random(seed)
    rng.shuffle(doc_list)

    calibration = doc_list[:calibration_count]
    evaluation = doc_list[calibration_count:]

    return {
        "clause_family": clause_family,
        "created_at": datetime.now(UTC).isoformat(),
        "seed": seed,
        "calibration": sorted(calibration),
        "evaluation": sorted(evaluation),
    }


def save_split(split: dict, path: Path) -> None:
    """Save split manifest to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=2) + "\n")


def load_split(path: Path) -> dict:
    """Load split manifest from JSON file."""
    return json.loads(path.read_text())
