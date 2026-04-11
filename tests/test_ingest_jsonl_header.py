"""Tests for JSONL header reading in ingest."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from corpus.db.ingest import read_jsonl_header

if TYPE_CHECKING:
    from pathlib import Path


def test_reads_header_fields(tmp_path: Path):
    """read_jsonl_header extracts parse_tool, page_count, parse_version."""
    header = {
        "storage_key": "nsm__12345",
        "page_count": 58,
        "parse_tool": "docling",
        "parse_version": "2.86.0",
        "parse_status": "parse_ok",
        "parsed_at": "2026-04-12T02:15:00+00:00",
    }
    jsonl = tmp_path / "nsm__12345.jsonl"
    jsonl.write_text(json.dumps(header) + "\n" + json.dumps({"page": 0, "text": "hi"}) + "\n")

    result = read_jsonl_header(tmp_path, "nsm__12345")
    assert result["parse_tool"] == "docling"
    assert result["page_count"] == 58
    assert result["parse_version"] == "2.86.0"
    # Should NOT include non-header fields
    assert "storage_key" not in result
    assert "parse_status" not in result


def test_missing_file_returns_empty(tmp_path: Path):
    result = read_jsonl_header(tmp_path, "nonexistent")
    assert result == {}


def test_empty_file_returns_empty(tmp_path: Path):
    (tmp_path / "empty.jsonl").write_text("")
    result = read_jsonl_header(tmp_path, "empty")
    assert result == {}


def test_malformed_json_returns_empty(tmp_path: Path):
    (tmp_path / "bad.jsonl").write_text("not json\n")
    result = read_jsonl_header(tmp_path, "bad")
    assert result == {}
