"""Tests for structured JSONL logging."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from corpus.logging import CorpusLogger


class TestCorpusLogger:
    """Tests for JSONL structured logging."""

    def test_log_entry_has_required_fields(self, tmp_path: Path) -> None:
        """Every log entry must have run_id, document_id, step, duration_ms, status."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-001")

        logger.log(
            document_id="nsm__12345",
            step="download",
            duration_ms=150,
            status="success",
        )

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["run_id"] == "run-001"
        assert entry["document_id"] == "nsm__12345"
        assert entry["step"] == "download"
        assert entry["duration_ms"] == 150
        assert entry["status"] == "success"

    def test_log_includes_timestamp(self, tmp_path: Path) -> None:
        """Each entry has an ISO timestamp."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-002")

        logger.log(document_id="edgar__99", step="parse", duration_ms=0, status="skip")

        entry = json.loads(log_file.read_text().strip())
        assert "timestamp" in entry
        # ISO format check: contains T separator
        assert "T" in entry["timestamp"]

    def test_append_only(self, tmp_path: Path) -> None:
        """Multiple log calls append, never overwrite."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-003")

        logger.log(document_id="doc1", step="download", duration_ms=100, status="success")
        logger.log(document_id="doc2", step="download", duration_ms=200, status="error")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["document_id"] == "doc1"
        assert json.loads(lines[1])["document_id"] == "doc2"

    def test_extra_fields_preserved(self, tmp_path: Path) -> None:
        """Arbitrary extra fields are included in the log entry."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-004")

        logger.log(
            document_id="doc1",
            step="download",
            duration_ms=50,
            status="error",
            error_message="HTTP 404",
            url="https://example.com/doc.pdf",
        )

        entry = json.loads(log_file.read_text().strip())
        assert entry["error_message"] == "HTTP 404"
        assert entry["url"] == "https://example.com/doc.pdf"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Logger creates parent dirs if they don't exist."""
        log_file = tmp_path / "sub" / "dir" / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-005")

        logger.log(document_id="doc1", step="parse", duration_ms=10, status="success")

        assert log_file.exists()

    def test_timer_context_manager(self, tmp_path: Path) -> None:
        """Timer context manager logs duration automatically."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-006")

        with logger.timed("doc1", "download"):
            pass  # instant

        entry = json.loads(log_file.read_text().strip())
        assert entry["document_id"] == "doc1"
        assert entry["step"] == "download"
        assert entry["status"] == "success"
        assert isinstance(entry["duration_ms"], int)
        assert entry["duration_ms"] >= 0

    def test_timer_logs_error_and_reraises(self, tmp_path: Path) -> None:
        """Timer context manager logs error status and re-raises the exception."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-007")

        with pytest.raises(RuntimeError, match="parse failed"), logger.timed("doc1", "parse"):
            raise RuntimeError("parse failed")

        entry = json.loads(log_file.read_text().strip())
        assert entry["status"] == "error"
        assert "parse failed" in entry["error_message"]

    def test_timed_ignores_reserved_extra_keys(self, tmp_path: Path) -> None:
        """Reserved keys passed as extras to timed() are silently dropped."""
        log_file = tmp_path / "pipeline.jsonl"
        logger = CorpusLogger(log_file, run_id="run-008")

        # Passing 'status' as extra should not override the auto-set status
        with logger.timed("doc1", "download", status="custom", source="nsm"):
            pass

        entry = json.loads(log_file.read_text().strip())
        assert entry["status"] == "success"  # not "custom"
        assert entry["source"] == "nsm"  # non-reserved extra preserved
