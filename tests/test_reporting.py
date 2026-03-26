"""Tests for download run reports and status."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class TestWriteRunReport:
    """Tests for run report generation."""

    def test_writes_report_file(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()
        log_file = telemetry_dir / "edgar_edgar-test.jsonl"
        log_file.write_text(
            json.dumps(
                {
                    "run_id": "edgar-test",
                    "document_id": "doc-1",
                    "step": "download",
                    "duration_ms": 100,
                    "status": "success",
                    "timestamp": "2026-03-26T00:00:00Z",
                }
            )
            + "\n"
            + json.dumps(
                {
                    "run_id": "edgar-test",
                    "document_id": "doc-2",
                    "step": "download",
                    "duration_ms": 200,
                    "status": "error",
                    "error_message": "Connection reset",
                    "timestamp": "2026-03-26T00:00:01Z",
                }
            )
            + "\n"
        )

        stats = {
            "downloaded": 1,
            "skipped": 0,
            "failed": 1,
            "total_in_discovery": 2,
            "aborted": False,
        }

        report_path = write_run_report(
            source="edgar",
            run_id="edgar-test",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        assert report_path.exists()
        content = report_path.read_text()
        assert "Downloaded: 1" in content
        assert "Failed: 1" in content
        assert "doc-2" in content
        assert "Connection reset" in content

    def test_report_includes_retry_command(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        stats = {
            "downloaded": 5,
            "skipped": 0,
            "failed": 0,
            "total_in_discovery": 5,
            "aborted": False,
        }

        report_path = write_run_report(
            source="edgar",
            run_id="test-run",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        content = report_path.read_text()
        assert "corpus download edgar" in content

    def test_report_shows_aborted_warning(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        stats = {
            "downloaded": 3,
            "skipped": 0,
            "failed": 10,
            "total_in_discovery": 100,
            "aborted": True,
        }

        report_path = write_run_report(
            source="nsm",
            run_id="test-run",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        content = report_path.read_text()
        assert "ABORTED" in content

    def test_report_handles_missing_telemetry(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        stats = {
            "downloaded": 5,
            "skipped": 0,
            "failed": 2,
            "total_in_discovery": 7,
            "aborted": False,
        }

        report_path = write_run_report(
            source="edgar",
            run_id="no-telemetry",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        assert report_path.exists()
        content = report_path.read_text()
        assert "Failed: 2" in content
