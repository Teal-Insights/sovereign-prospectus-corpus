"""Tests for the PDIP source adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseSearchResults:
    """Tests for parsing PDIP search API response into discovery records."""

    def test_parses_all_results(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        assert len(records) == 3

    def test_record_has_required_fields(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        r = records[0]

        assert r["native_id"] == "VEN85"
        assert r["source"] == "pdip"
        assert (
            r["title"]
            == "Loan Agreement between the Republic of Venezuela and International Bank for Reconstruction and Development dated December 14, 1990"
        )
        assert r["tag_status"] == "Annotated"
        assert r["country"] == "Venezuela"
        assert r["instrument_type"] == "Loan"
        assert r["creditor_country"] == "Multilateral; Regional; or Plurilateral Lenders"
        assert r["creditor_type"] == "Multilateral Official"
        assert r["maturity_date"] == "December 15, 2005"
        assert r["maturity_year"] == "2005"

    def test_sparse_metadata_uses_none(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        bra = records[1]  # BRA1 has minimal metadata

        assert bra["native_id"] == "BRA1"
        assert bra["country"] == "Brazil"
        assert bra["creditor_type"] is None
        assert bra["maturity_date"] is None

    def test_extra_metadata_preserved(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        r = records[0]

        assert "metadata" in r
        assert "BorrowerDebttoGDPRatio" in r["metadata"]


class TestDiscoverPdip:
    """Tests for the full discovery pipeline."""

    def test_discovers_documents(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, delay=0.0)

        assert stats["total_documents"] == 3
        assert output.exists()
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 3
        assert lines[0]["native_id"] == "VEN85"

    def test_paginates_when_needed(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, page_size=100, delay=0.0)

        assert mock_session.post.call_count == 1
        assert stats["pages_fetched"] == 1

    def test_deduplicates_by_native_id(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        page1 = dict(fixture)
        page2 = {"total": 3, "results": [fixture["results"][0]]}

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp1 = MagicMock()
            mock_resp1.status_code = 200
            mock_resp1.json.return_value = page1
            mock_resp1.raise_for_status = MagicMock()
            mock_resp2 = MagicMock()
            mock_resp2.status_code = 200
            mock_resp2.json.return_value = page2
            mock_resp2.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.side_effect = [mock_resp1, mock_resp2]
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, page_size=3, delay=0.0)

        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        native_ids = [line["native_id"] for line in lines]
        assert len(native_ids) == len(set(native_ids))
        assert stats["total_documents"] == 3

    def test_handles_api_error(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, delay=0.0)

        assert stats["total_documents"] == 0
        assert stats["error"] is not None

    def test_sets_browser_headers(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import PDIP_HEADERS, discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            discover_pdip(output_path=output, delay=0.0)

        mock_session.headers.update.assert_called_once_with(PDIP_HEADERS)


class TestDownloadPdipDocument:
    """Tests for single-document PDF download."""

    def test_downloads_valid_pdf(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        pdf_bytes = b"%PDF-1.6\nfake pdf content"
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = pdf_bytes
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp

        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test Loan Agreement",
            "tag_status": "Annotated",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }

        result, status = download_pdip_document(record, session=mock_session, output_dir=tmp_path)

        assert status == "success"
        assert result is not None
        assert result["file_path"] == str(tmp_path / "pdip__VEN85.pdf")
        assert result["file_hash"] == hashlib.sha256(pdf_bytes).hexdigest()
        assert result["file_size_bytes"] == len(pdf_bytes)
        assert result["source"] == "pdip"
        assert result["storage_key"] == "pdip__VEN85"
        assert (
            result["download_url"] == "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85"
        )
        assert (tmp_path / "pdip__VEN85.pdf").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        target = tmp_path / "pdip__VEN85.pdf"
        target.write_bytes(b"already here")

        record = {"native_id": "VEN85", "source": "pdip"}

        result, status = download_pdip_document(record, session=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_exists"

    def test_handles_404(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session.get.return_value = mock_resp

        record = {"native_id": "MISSING1", "source": "pdip"}

        result, status = download_pdip_document(record, session=mock_session, output_dir=tmp_path)
        assert result is None
        assert status == "not_found"

    def test_rejects_invalid_pdf(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b'{"error": "something went wrong"}'
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp

        record = {"native_id": "BAD1", "source": "pdip"}

        result, status = download_pdip_document(record, session=mock_session, output_dir=tmp_path)
        assert result is None
        assert status == "invalid_pdf"


class TestRunPdipDownload:
    """Tests for the full download pipeline."""

    def test_reads_discovery_and_downloads(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test Loan",
            "tag_status": "Annotated",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.6\ntest content"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.content = pdf_bytes
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        assert stats["downloaded"] == 1
        assert stats["failed"] == 0
        manifest = tmp_path / "manifests" / "pdip_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(line) for line in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "VEN85"

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        lines = []
        for i in range(15):
            lines.append(
                json.dumps(
                    {
                        "native_id": f"FAIL{i}",
                        "source": "pdip",
                        "title": f"Fail {i}",
                        "tag_status": "",
                        "country": "Test",
                        "instrument_type": "",
                        "creditor_country": None,
                        "creditor_type": None,
                        "maturity_date": None,
                        "maturity_year": None,
                        "metadata": {},
                    }
                )
            )
        discovery.write_text("\n".join(lines) + "\n")

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("connection refused")
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
                total_failures_abort=5,
            )

        assert stats["aborted"]
        assert stats["failed"] <= 6

    def test_not_found_does_not_count_as_failure(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "MISSING1",
            "source": "pdip",
            "title": "Missing Doc",
            "tag_status": "",
            "country": "Test",
            "instrument_type": "",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        assert stats["failed"] == 0
        assert stats["not_found"] == 1
        assert not stats["aborted"]

    def test_telemetry_logs_download(self, tmp_path: Path) -> None:

        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test",
            "tag_status": "",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.6\ntest"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.content = pdf_bytes
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        log_entries = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert len(log_entries) == 1
        assert log_entries[0]["status"] == "success"
        assert log_entries[0]["document_id"] == "VEN85"
        assert log_entries[0]["step"] == "download"


class TestPdipCli:
    """Tests for PDIP CLI commands."""

    def test_discover_pdip_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "pdip", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--output" in result.output

    def test_download_pdip_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "pdip", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--discovery-file" in result.output

    def test_discover_pdip_runs(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            runner = CliRunner()
            result = runner.invoke(cli, ["discover", "pdip", "--output", str(output)])

        assert result.exit_code == 0
        assert "3" in result.output
