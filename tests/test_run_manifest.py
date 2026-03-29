# tests/test_run_manifest.py
"""Tests for run manifest and completion protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from corpus.extraction.run_manifest import (
    create_manifest,
    is_family_complete,
    load_manifest,
    mark_family_complete,
    mark_family_in_progress,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_create_manifest(tmp_path: Path) -> None:
    families = ["governing_law", "sovereign_immunity"]
    manifest = create_manifest(
        run_dir=tmp_path,
        run_id="test_run",
        families=families,
    )
    assert manifest.run_id == "test_run"
    assert manifest.families_pending == families
    assert manifest.families_completed == []
    assert (tmp_path / "RUN_MANIFEST.json").exists()


def test_manifest_round_trips_with_updated_at(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law"])
    m = load_manifest(tmp_path)
    assert m.updated_at != ""
    assert m.run_id == "test"


def test_mark_family_in_progress(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law", "sovereign_immunity"])
    mark_family_in_progress(tmp_path, "governing_law")
    m = load_manifest(tmp_path)
    assert "governing_law" in m.families_in_progress
    assert "governing_law" not in m.families_pending


def test_mark_family_complete(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law"])
    mark_family_in_progress(tmp_path, "governing_law")
    family_dir = tmp_path / "governing_law"
    family_dir.mkdir()
    mark_family_complete(tmp_path, "governing_law")
    m = load_manifest(tmp_path)
    assert "governing_law" in m.families_completed
    assert (family_dir / "COMPLETE.json").exists()


def test_is_family_complete(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law"])
    assert is_family_complete(tmp_path, "governing_law") is False
    mark_family_in_progress(tmp_path, "governing_law")
    (tmp_path / "governing_law").mkdir()
    mark_family_complete(tmp_path, "governing_law")
    assert is_family_complete(tmp_path, "governing_law") is True
