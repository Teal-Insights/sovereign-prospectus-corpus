"""Tests for the PDIP annotations harvester."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _make_inventory_csv(path: Path, rows: list[dict[str, str]] | None = None) -> Path:
    """Create a minimal valid inventory CSV."""
    headers = [
        "id",
        "document_title",
        "tag_status",
        "country",
        "instrument_type",
        "creditor_country",
        "creditor_type",
        "entity_type",
        "document_date",
        "maturity_date",
    ]

    if rows is None:
        # Use real inventory
        import shutil

        real = Path("data/pdip/pdip_document_inventory.csv")
        if real.exists():
            shutil.copy(real, path)
            return path
        raise FileNotFoundError("No real inventory and no rows provided")

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            # Fill in defaults for missing fields
            full_row = {h: row.get(h, "") for h in headers}
            writer.writerow(full_row)

    return path


def _make_annotated_rows(count: int = 162, bonds: int = 58) -> list[dict[str, str]]:
    """Generate annotated inventory rows matching expected counts."""
    rows: list[dict[str, str]] = []

    # Smoke test IDs first
    smoke_ids = ["VEN85", "NLD21", "KEN68", "JAM22", "VEN59"]
    for sid in smoke_ids:
        rows.append(
            {
                "id": sid,
                "document_title": f"Test doc {sid}",
                "tag_status": "Annotated",
                "country": "Test",
                "instrument_type": "Bond" if sid != "VEN59" else "Loan",
            }
        )

    # Fill bonds (already have 4 from smoke IDs)
    for i in range(bonds - 4):
        rows.append(
            {
                "id": f"BOND{i:03d}",
                "document_title": f"Bond {i}",
                "tag_status": "Annotated",
                "country": "Test",
                "instrument_type": "Bond",
            }
        )

    # Fill remaining with non-bond annotated
    remaining = count - len(rows)
    for i in range(remaining):
        rows.append(
            {
                "id": f"LOAN{i:03d}",
                "document_title": f"Loan {i}",
                "tag_status": "Annotated",
                "country": "Test",
                "instrument_type": "Loan",
            }
        )

    return rows


class TestLoadInventory:
    def test_loads_annotated_only(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_inventory

        rows = _make_annotated_rows()
        # Add a non-annotated row
        rows.append(
            {
                "id": "EXTRA1",
                "document_title": "Not annotated",
                "tag_status": "Not Annotated",
                "country": "Test",
                "instrument_type": "Bond",
            }
        )
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)

        result = load_inventory(csv_path, annotated_only=True)
        assert len(result) == 162
        assert all(r["tag_status"] == "Annotated" for r in result)

    def test_loads_all(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_inventory

        rows = _make_annotated_rows()
        rows.append(
            {
                "id": "EXTRA1",
                "document_title": "Not annotated",
                "tag_status": "Not Annotated",
                "country": "Test",
                "instrument_type": "Bond",
            }
        )
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)

        result = load_inventory(csv_path, annotated_only=False)
        assert len(result) == 163

    def test_rejects_wrong_headers(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_inventory

        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("wrong,headers\na,b\n")

        with pytest.raises(ValueError, match="headers mismatch"):
            load_inventory(csv_path)


class TestPreflight:
    def test_passes_with_correct_counts(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_inventory, run_preflight

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        loaded = load_inventory(csv_path)
        run_preflight(loaded)  # Should not raise

    def test_fails_wrong_annotated_count(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_preflight

        rows = _make_annotated_rows(count=100, bonds=58)
        with pytest.raises(ValueError, match="Expected 162"):
            run_preflight(rows)

    def test_fails_wrong_bond_count(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_preflight

        rows = _make_annotated_rows(count=162, bonds=30)
        with pytest.raises(ValueError, match="Expected 58"):
            run_preflight(rows)

    def test_fails_missing_smoke_id(self) -> None:
        from corpus.sources.pdip_annotations import run_preflight

        rows = _make_annotated_rows()
        # Remove VEN85
        rows = [r for r in rows if r["id"] != "VEN85"]
        # Add replacement to maintain count
        rows.append(
            {
                "id": "REPLACEMENT",
                "document_title": "Replacement",
                "tag_status": "Annotated",
                "country": "Test",
                "instrument_type": "Bond",
            }
        )
        with pytest.raises(ValueError, match="VEN85"):
            run_preflight(rows)

    def test_validates_requested_doc_ids(self) -> None:
        from corpus.sources.pdip_annotations import run_preflight

        rows = _make_annotated_rows()
        with pytest.raises(ValueError, match="NOTEXIST"):
            run_preflight(rows, doc_ids=["VEN85", "NOTEXIST"])


class TestLoadCompletedIds:
    def test_empty_when_no_file(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_completed_ids

        result = load_completed_ids(tmp_path / "nonexistent.jsonl")
        assert result == set()

    def test_loads_valid_records(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_completed_ids

        path = tmp_path / "annotations.jsonl"
        records = [
            {"doc_id": "VEN85", "status": "success"},
            {"doc_id": "NLD21", "status": "annotated_zero_clauses"},
        ]
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        result = load_completed_ids(path)
        assert result == {"VEN85", "NLD21"}

    def test_tolerates_truncated_trailing_line(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_completed_ids

        path = tmp_path / "annotations.jsonl"
        content = json.dumps({"doc_id": "VEN85", "status": "success"}) + "\n"
        content += '{"doc_id": "NLD21", "status":'  # truncated
        path.write_text(content)

        result = load_completed_ids(path)
        assert result == {"VEN85"}

    def test_skips_empty_lines(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import load_completed_ids

        path = tmp_path / "annotations.jsonl"
        content = (
            json.dumps({"doc_id": "VEN85"}) + "\n\n\n" + json.dumps({"doc_id": "NLD21"}) + "\n"
        )
        path.write_text(content)

        result = load_completed_ids(path)
        assert result == {"VEN85", "NLD21"}


def _clause(label: str) -> dict:
    """Helper to build a Label Studio clause annotation."""
    return {"value": {"rectanglelabels": [label]}}


class TestExtractLabels:
    def test_extracts_modification_labels(self) -> None:
        from corpus.sources.pdip_annotations import extract_labels

        clauses = [
            _clause("VotingCollectiveActionModification_AmendmentandWaiver"),
            _clause("VotingRequirementforAcceleration_Default"),
            _clause("GoverningLaw_English"),
        ]
        result = extract_labels(clauses)

        assert result["clause_count"] == 3
        assert len(result["cac_modification_labels"]) == 1
        assert len(result["cac_acceleration_labels"]) == 1
        assert result["cac_candidate"] is True

    def test_acceleration_only_not_cac_candidate(self) -> None:
        from corpus.sources.pdip_annotations import extract_labels

        clauses = [
            _clause("VotingRequirementforAcceleration_Default"),
        ]
        result = extract_labels(clauses)

        assert result["cac_candidate"] is False
        assert len(result["cac_acceleration_labels"]) == 1

    def test_no_clauses(self) -> None:
        from corpus.sources.pdip_annotations import extract_labels

        result = extract_labels([])
        assert result["clause_count"] == 0
        assert result["cac_candidate"] is False

    def test_empty_label_skipped(self) -> None:
        from corpus.sources.pdip_annotations import extract_labels

        clauses = [{"value": {"rectanglelabels": [""]}}, _clause("GoverningLaw_English")]
        result = extract_labels(clauses)
        assert len(result["raw_clause_labels"]) == 1


class TestGenerateSummary:
    def test_summary_fields(self) -> None:
        from corpus.sources.pdip_annotations import generate_summary

        records = [
            {
                "status": "success",
                "attempts_used": 1,
                "raw_clause_labels": ["VotingCollectiveActionModification_X"],
                "cac_candidate": True,
                "country": "Venezuela",
                "instrument_type": "Bond",
            },
            {
                "status": "annotated_zero_clauses",
                "attempts_used": 2,
                "raw_clause_labels": [],
                "cac_candidate": False,
                "country": "Brazil",
                "instrument_type": "Loan",
            },
        ]
        summary = generate_summary(records, selected_total=5, skipped_via_resume=1)

        assert summary["selected_total"] == 5
        assert summary["new_attempted"] == 1  # 2 records - 1 skipped
        assert summary["skipped_via_resume"] == 1
        assert summary["terminal_total"] == 2
        assert summary["status_counts"]["success"] == 1
        assert summary["status_counts"]["annotated_zero_clauses"] == 1
        assert summary["zero_clause_on_annotated_count"] == 1
        assert summary["cac_candidate_count"] == 1
        assert "VotingCollectiveActionModification_X" in summary["distinct_raw_labels"]


class TestWriteCacCandidatesCsv:
    def test_writes_candidates(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import write_cac_candidates_csv

        records = [
            {
                "doc_id": "VEN85",
                "document_title": "Test",
                "country": "Venezuela",
                "instrument_type": "Bond",
                "clause_count": 3,
                "cac_modification_labels": ["VotingCollectiveActionModification_X"],
                "cac_acceleration_labels": [],
                "cac_candidate": True,
                "source_url": "https://example.com",
                "api_url": "https://example.com/api",
            },
            {
                "doc_id": "NLD21",
                "cac_candidate": False,
            },
        ]
        path = tmp_path / "cac.csv"
        count = write_cac_candidates_csv(records, path)

        assert count == 1
        assert path.exists()
        with path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["doc_id"] == "VEN85"

    def test_returns_zero_when_no_candidates(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import write_cac_candidates_csv

        records = [{"doc_id": "X", "cac_candidate": False}]
        count = write_cac_candidates_csv(records, tmp_path / "cac.csv")
        assert count == 0


class TestCircuitBreaker:
    def test_aborts_after_consecutive_failures(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_annotations_harvest

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        output_dir = tmp_path / "output"

        # Mock session that always fails
        mock_session = MagicMock()
        mock_session.get.side_effect = ConnectionError("refused")

        with patch("corpus.sources.pdip_annotations._make_session") as mock_make:
            mock_make.return_value = (
                mock_session,
                {"tls_mode": "test", "tls_verify": False, "tls_reason": "test"},
            )

            summary = run_annotations_harvest(
                inventory_path=csv_path,
                output_dir=output_dir,
                run_id="test-cb",
                doc_ids=["VEN85", "NLD21", "KEN68", "JAM22", "VEN59"],
                delay=0.0,
                consecutive_failures_pause=2,
                consecutive_failures_abort=3,
            )

        assert summary["aborted"] is True
        assert "circuit breaker" in summary["abort_reason"].lower()


class TestResumeBehavior:
    def test_skips_completed_docs(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_annotations_harvest

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True)

        # Pre-populate annotations.jsonl with one completed doc
        annotations = output_dir / "annotations.jsonl"
        existing = {"doc_id": "VEN85", "status": "success", "run_id": "test"}
        annotations.write_text(json.dumps(existing) + "\n")

        # Mock session that returns success
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "clauses": [{"value": {"rectanglelabels": ["Test_Label"]}}],
            "source_url": "",
        }
        mock_session.get.return_value = mock_resp

        with patch("corpus.sources.pdip_annotations._make_session") as mock_make:
            mock_make.return_value = (
                mock_session,
                {"tls_mode": "test", "tls_verify": False, "tls_reason": "test"},
            )

            summary = run_annotations_harvest(
                inventory_path=csv_path,
                output_dir=output_dir,
                run_id="test-resume",
                doc_ids=["VEN85", "NLD21"],
                delay=0.0,
            )

        assert summary["skipped_via_resume"] == 1
        # Only NLD21 should have been fetched
        assert mock_session.get.call_count == 1

    def test_overwrites_orphaned_raw_payload(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_annotations_harvest

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        output_dir = tmp_path / "output"
        raw_dir = output_dir / "raw"
        raw_dir.mkdir(parents=True)

        # Create orphaned raw payload (no JSONL record)
        orphan = raw_dir / "VEN85.json"
        orphan.write_text('{"old": "data"}')

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "clauses": [{"value": {"rectanglelabels": ["NewLabel"]}}],
            "source_url": "",
        }
        mock_session.get.return_value = mock_resp

        with patch("corpus.sources.pdip_annotations._make_session") as mock_make:
            mock_make.return_value = (
                mock_session,
                {"tls_mode": "test", "tls_verify": False, "tls_reason": "test"},
            )

            run_annotations_harvest(
                inventory_path=csv_path,
                output_dir=output_dir,
                run_id="test-orphan",
                doc_ids=["VEN85"],
                delay=0.0,
            )

        # Raw payload should be overwritten with new data
        new_content = json.loads(orphan.read_text())
        assert "NewLabel" in json.dumps(new_content)


class TestAnnotatedZeroClauses:
    def test_not_counted_as_transport_failure(self, tmp_path: Path) -> None:
        from corpus.sources.pdip_annotations import run_annotations_harvest

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        output_dir = tmp_path / "output"

        # Return empty clauses for all docs
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"clauses": [], "source_url": ""}
        mock_session.get.return_value = mock_resp

        with patch("corpus.sources.pdip_annotations._make_session") as mock_make:
            mock_make.return_value = (
                mock_session,
                {"tls_mode": "test", "tls_verify": False, "tls_reason": "test"},
            )

            # Process 3 docs - should NOT trip circuit breaker (set to 2)
            summary = run_annotations_harvest(
                inventory_path=csv_path,
                output_dir=output_dir,
                run_id="test-zero",
                doc_ids=["VEN85", "NLD21", "KEN68"],
                delay=0.0,
                consecutive_failures_abort=2,
            )

        # Should complete without abort since zero-clause isn't a transport failure
        assert summary["aborted"] is False
        assert summary["status_counts"].get("annotated_zero_clauses", 0) == 3


class TestCli:
    def test_scrape_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["scrape", "pdip-annotations", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--insecure" in result.output
        assert "--doc-id" in result.output
        assert "--limit" in result.output
        assert "--annotated-only" in result.output

    def test_scrape_runs(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        rows = _make_annotated_rows()
        csv_path = _make_inventory_csv(tmp_path / "inv.csv", rows)
        output_dir = tmp_path / "output"

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "clauses": [
                {"value": {"rectanglelabels": ["VotingCollectiveActionModification_Test"]}}
            ],
            "source_url": "",
        }
        mock_session.get.return_value = mock_resp

        with patch("corpus.sources.pdip_annotations._make_session") as mock_make:
            mock_make.return_value = (
                mock_session,
                {"tls_mode": "test", "tls_verify": False, "tls_reason": "test"},
            )

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "scrape",
                    "pdip-annotations",
                    "--run-id",
                    "test",
                    "--inventory-file",
                    str(csv_path),
                    "--output-dir",
                    str(output_dir),
                    "--doc-id",
                    "VEN85",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "Results" in result.output
