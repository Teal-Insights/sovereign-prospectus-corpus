"""Tests for portable paths and batched manifest updates."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path


def test_portable_path_requires_explicit_data_root(tmp_path: Path) -> None:
    from corpus.io.manifest import portable_data_path

    target = tmp_path / "custom" / "data" / "original" / "document.pdf"

    assert portable_data_path(target) == str(target)


def test_portable_path_is_relative_under_explicit_data_root(tmp_path: Path) -> None:
    from corpus.io.manifest import portable_data_path

    data_root = tmp_path / "shadow" / "data"
    target = data_root / "original" / "document.pdf"

    assert portable_data_path(target, data_root=data_root) == "data/original/document.pdf"


def test_shared_data_root_requires_directory_named_data(tmp_path: Path) -> None:
    from corpus.io.manifest import shared_data_root

    run_root = tmp_path / "run"

    assert shared_data_root(run_root / "original", run_root / "manifests") is None


def test_shared_data_root_accepts_standard_data_layout(tmp_path: Path) -> None:
    from corpus.io.manifest import shared_data_root

    data_root = tmp_path / "run" / "data"

    assert shared_data_root(data_root / "original", data_root / "manifests") == data_root


def test_bulk_upsert_rewrites_manifest_once(tmp_path: Path) -> None:
    from corpus.io.manifest import upsert_manifest_records

    manifest = tmp_path / "manifest.jsonl"
    records = [
        {"storage_key": f"source__{index}", "file_hash": str(index)} for index in range(100)
    ]

    with patch("corpus.io.manifest.safe_write") as write:
        upsert_manifest_records(manifest, records)

    write.assert_called_once()
    payload = write.call_args.args[1].decode()
    assert len([json.loads(line) for line in payload.splitlines()]) == 100
