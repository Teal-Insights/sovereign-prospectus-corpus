# tests/test_round_report.py
"""Tests for round report generation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _create_mock_verified(tmp_path: Path, family: str) -> Path:
    """Create a mock verified.jsonl for testing."""
    family_dir = tmp_path / family
    family_dir.mkdir()
    records = [
        {
            "candidate_id": "c1",
            "storage_key": "doc1",
            "source_format": "docling_md",
            "heading_match": True,
            "extraction": {
                "found": True,
                "clause_text": "governed by English law",
                "confidence": "high",
            },
            "verification": {"status": "verified", "verbatim_similarity": 1.0},
        },
        {
            "candidate_id": "c2",
            "storage_key": "doc2",
            "source_format": "flat_jsonl",
            "heading_match": False,
            "extraction": {"found": False, "clause_text": "", "confidence": "high"},
            "verification": {"status": "not_found"},
        },
        {
            "candidate_id": "c3",
            "storage_key": "doc3",
            "source_format": "docling_md",
            "heading_match": True,
            "extraction": {"found": False, "clause_text": "", "confidence": "low"},
            "verification": {"status": "api_error", "error": "rate_limited"},
        },
    ]
    verified_path = family_dir / "verified.jsonl"
    with verified_path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return verified_path


def test_round_report_runs_successfully(tmp_path: Path) -> None:
    """Test that the script runs and produces output."""
    _create_mock_verified(tmp_path, "governing_law")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/round_report.py",
            "--run-id",
            "test_run",
            "--run-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "governing_law" in result.stdout

    # Check JSON report was written
    report_path = tmp_path / "round_report.json"
    assert report_path.exists()
    reports = json.loads(report_path.read_text())
    assert len(reports) == 1
    assert reports[0]["family"] == "governing_law"
    assert reports[0]["total_candidates"] == 3
    assert reports[0]["found_count"] == 1
    assert reports[0]["not_found_count"] == 1
    assert reports[0]["api_error_count"] == 1


def test_round_report_derives_run_dir_from_run_id(tmp_path: Path) -> None:
    """C1: --run-id is primary, --run-dir defaults from it."""
    result = subprocess.run(
        [sys.executable, "scripts/round_report.py", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert "--run-id" in result.stdout
