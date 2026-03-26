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


class TestGetSourceStatus:
    """Tests for source status diffing."""

    def test_diffs_discovery_vs_manifest(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(
            "\n".join(json.dumps({"native_id": f"doc-{i}", "title": f"Doc {i}"}) for i in range(5))
            + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        manifest = manifest_dir / "edgar_manifest.jsonl"
        manifest.write_text(
            "\n".join(
                json.dumps(
                    {
                        "native_id": f"doc-{i}",
                        "file_path": f"data/original/edgar__doc-{i}.htm",
                    }
                )
                for i in range(3)
            )
            + "\n"
        )

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["source"] == "edgar"
        assert status["discovery_count"] == 5
        assert status["manifest_count"] == 3
        assert status["outstanding_count"] == 2
        outstanding_ids = {o["native_id"] for o in status["outstanding"]}
        assert outstanding_ids == {"doc-3", "doc-4"}

    def test_not_discovered(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        status = get_source_status(
            "pdip",
            discovery_path=tmp_path / "nonexistent.jsonl",
            manifest_dir=tmp_path,
            telemetry_dir=tmp_path,
        )

        assert status["status"] == "not_discovered"

    def test_empty_manifest(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(json.dumps({"native_id": "doc-1", "title": "Doc 1"}) + "\n")

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["discovery_count"] == 1
        assert status["manifest_count"] == 0
        assert status["outstanding_count"] == 1

    def test_enriches_with_telemetry_errors(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(json.dumps({"native_id": "fail-doc", "title": "Failed"}) + "\n")

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()
        log = telemetry_dir / "edgar_test-run.jsonl"
        log.write_text(
            json.dumps(
                {
                    "run_id": "test-run",
                    "document_id": "fail-doc",
                    "step": "download",
                    "duration_ms": 100,
                    "status": "error",
                    "error_message": "HTTP 403",
                    "timestamp": "2026-03-26T00:00:00Z",
                }
            )
            + "\n"
        )

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=telemetry_dir,
        )

        assert status["outstanding"][0]["last_error"] == "HTTP 403"

    def test_nsm_uses_disclosure_id(self, tmp_path: Path) -> None:
        """NSM discovery uses disclosure_id, not native_id."""
        from corpus.reporting import get_source_status

        discovery = tmp_path / "nsm_discovery.jsonl"
        discovery.write_text(
            json.dumps({"disclosure_id": "abc-123", "headline": "Kenya Note"})
            + "\n"
            + json.dumps({"disclosure_id": "def-456", "headline": "Ghana Bond"})
            + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        manifest = manifest_dir / "nsm_manifest.jsonl"
        manifest.write_text(json.dumps({"native_id": "abc-123"}) + "\n")

        status = get_source_status(
            "nsm",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["discovery_count"] == 2
        assert status["manifest_count"] == 1
        assert status["outstanding_count"] == 1
        assert status["outstanding"][0]["native_id"] == "def-456"


class TestFormatStatusSummary:
    """Tests for cross-source status formatting."""

    def test_formats_multiple_sources(self) -> None:
        from corpus.reporting import format_status_summary

        statuses = [
            {
                "source": "nsm",
                "status": "ok",
                "discovery_count": 899,
                "manifest_count": 642,
                "outstanding_count": 257,
                "outstanding": [],
            },
            {
                "source": "edgar",
                "status": "ok",
                "discovery_count": 3306,
                "manifest_count": 3301,
                "outstanding_count": 5,
                "outstanding": [],
            },
            {"source": "pdip", "status": "not_discovered"},
        ]

        output = format_status_summary(statuses)

        assert "NSM" in output
        assert "642" in output
        assert "899" in output
        assert "EDGAR" in output
        assert "3301" in output
        assert "PDIP" in output
        assert "not discovered" in output
