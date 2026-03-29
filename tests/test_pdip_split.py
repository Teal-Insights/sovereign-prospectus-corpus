# tests/test_pdip_split.py
"""Tests for PDIP calibration/evaluation split."""

from __future__ import annotations

import json
from pathlib import Path

from corpus.extraction.pdip_split import create_split, load_split


def test_create_split_returns_two_sets() -> None:
    annotations_path = Path("data/pdip/clause_annotations.jsonl")
    if not annotations_path.exists():
        import pytest

        pytest.skip("PDIP annotations not available")

    split = create_split(annotations_path, clause_family="collective_action", calibration_count=5)
    assert "calibration" in split
    assert "evaluation" in split
    assert len(split["calibration"]) == 5
    assert len(split["evaluation"]) > 0
    # No overlap
    assert set(split["calibration"]).isdisjoint(set(split["evaluation"]))


def test_load_split_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "clause_family": "collective_action",
        "created_at": "2026-03-28",
        "calibration": ["DOC1", "DOC2"],
        "evaluation": ["DOC3", "DOC4", "DOC5"],
    }
    path = tmp_path / "split.json"
    path.write_text(json.dumps(manifest))
    split = load_split(path)
    assert split["calibration"] == ["DOC1", "DOC2"]
    assert split["evaluation"] == ["DOC3", "DOC4", "DOC5"]


def test_create_split_guard_too_few_docs(tmp_path: Path) -> None:
    """E8: Should raise ValueError if not enough docs for calibration."""
    annotations = tmp_path / "test_annotations.jsonl"
    # Only 2 docs but requesting 5 for calibration
    records = [
        {"doc_id": "DOC1", "label_family": "collective_action"},
        {"doc_id": "DOC2", "label_family": "collective_action"},
    ]
    with annotations.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    import pytest

    with pytest.raises(ValueError, match="Only 2 docs found"):
        create_split(annotations, clause_family="collective_action", calibration_count=5)
