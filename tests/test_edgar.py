"""Tests for the EDGAR source adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestSovereignCiks:
    """Tests for the sovereign CIK constant list."""

    def test_cik_list_has_all_tiers(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        assert set(SOVEREIGN_CIKS.keys()) == {1, 2, 3, 4}

    def test_cik_entries_have_required_fields(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        for tier, entries in SOVEREIGN_CIKS.items():
            for entry in entries:
                assert "cik" in entry, f"Missing cik in tier {tier}: {entry}"
                assert "country" in entry, f"Missing country in tier {tier}: {entry}"
                assert "name" in entry, f"Missing name in tier {tier}: {entry}"

    def test_total_cik_count(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        total = sum(len(entries) for entries in SOVEREIGN_CIKS.values())
        assert total == 27


class TestBuildFilingList:
    """Tests for extracting prospectus filings from submissions JSON."""

    def test_filters_to_prospectus_forms(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)

        # Fixture has: 424B5, FWP, 18-K, 424B2, 424B5
        # 18-K is NOT a prospectus form, so it should be excluded
        assert len(filings) == 4
        form_types = {f["form_type"] for f in filings}
        assert "18-K" not in form_types
        assert "424B5" in form_types
        assert "FWP" in form_types
        assert "424B2" in form_types

    def test_filing_record_fields(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        f = filings[0]

        assert f["source"] == "edgar"
        assert f["native_id"] == "0000914021-24-000123"
        assert f["storage_key"] == "edgar__0000914021-24-000123"
        assert f["issuer_name"] == "REPUBLIC OF ARGENTINA"
        assert f["doc_type"] == "424B5"
        assert f["publication_date"] == "2024-06-15"
        assert f["title"] == "Prospectus Supplement"
        assert "download_url" in f
        assert "source_metadata" in f

    def test_download_url_construction(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        url = filings[0]["download_url"]

        assert "sec.gov/Archives/edgar/data/914021/" in url
        assert "000091402124000123" in url
        assert "d12345.htm" in url

    def test_source_metadata_fields(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        meta = filings[0]["source_metadata"]

        assert meta["cik"] == "0000914021"
        assert meta["accession_number"] == "0000914021-24-000123"
        assert meta["form_type"] == "424B5"
        assert meta["primary_document"] == "d12345.htm"

    def test_empty_submissions(self) -> None:
        from corpus.sources.edgar import build_filing_list

        empty = {
            "cik": "0000000001",
            "name": "EMPTY COUNTRY",
            "filings": {
                "recent": {
                    "accessionNumber": [],
                    "filingDate": [],
                    "form": [],
                    "primaryDocument": [],
                    "primaryDocDescription": [],
                },
                "files": [],
            },
        }
        filings = build_filing_list(empty)
        assert filings == []

    def test_skips_entries_without_accession_or_document(self) -> None:
        from corpus.sources.edgar import build_filing_list

        sparse = {
            "cik": "0000000001",
            "name": "SPARSE COUNTRY",
            "filings": {
                "recent": {
                    "accessionNumber": ["", "0000000001-24-000001"],
                    "filingDate": ["2024-01-01", "2024-01-02"],
                    "form": ["424B5", "424B5"],
                    "primaryDocument": ["doc.htm", ""],
                    "primaryDocDescription": ["Test", "Test"],
                },
                "files": [],
            },
        }
        filings = build_filing_list(sparse)
        assert len(filings) == 0


class TestFetchSubmissions:
    """Tests for fetching submissions JSON from EDGAR API."""

    def test_fetches_and_returns_json(self) -> None:

        from corpus.sources.edgar import fetch_submissions

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        result = fetch_submissions(mock_client, cik="0000914021")

        assert result is not None
        assert result["name"] == "REPUBLIC OF ARGENTINA"
        mock_client.get.assert_called_once()
        url = mock_client.get.call_args[0][0]
        assert "CIK0000914021" in url

    def test_returns_none_on_error(self) -> None:

        from corpus.sources.edgar import fetch_submissions

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("network error")

        result = fetch_submissions(mock_client, cik="0000914021")
        assert result is None


class TestDiscoverEdgar:
    """Tests for the full discovery pipeline."""

    def test_discovers_filings_for_cik_entries(self, tmp_path: Path) -> None:

        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 1
        assert stats["total_filings"] == 4
        assert output.exists()
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 4

    def test_deduplicates_across_ciks(self, tmp_path: Path) -> None:

        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 2
        assert stats["total_filings"] == 4
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 4

    def test_paginates_older_filings(self, tmp_path: Path) -> None:

        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        older_page = {
            "accessionNumber": ["0000914021-15-000999"],
            "filingDate": ["2015-06-01"],
            "form": ["424B5"],
            "primaryDocument": ["older.htm"],
            "primaryDocDescription": ["Old Prospectus"],
        }

        mock_client = MagicMock()
        main_resp = MagicMock()
        main_resp.json.return_value = fixture
        older_resp = MagicMock()
        older_resp.json.return_value = older_page
        mock_client.get.side_effect = [main_resp, older_resp]

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["total_filings"] == 5
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        native_ids = {line["native_id"] for line in lines}
        assert "0000914021-15-000999" in native_ids

    def test_handles_failed_cik(self, tmp_path: Path) -> None:

        from corpus.sources.edgar import discover_edgar

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("network error")

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 1
        assert stats["ciks_failed"] == 1
        assert stats["total_filings"] == 0


class TestDownloadEdgarDocument:
    """Tests for single-document download."""

    def test_downloads_and_returns_record(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        html_bytes = b"<html><body>Prospectus content</body></html>"
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = html_bytes
        mock_client.get.return_value = mock_resp

        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000091402124000123/d12345.htm",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=mock_client, output_dir=tmp_path)

        assert status == "downloaded"
        assert result is not None
        assert result["file_path"] == str(tmp_path / "edgar__0000914021-24-000123.htm")
        assert result["file_hash"] == hashlib.sha256(html_bytes).hexdigest()
        assert result["file_size_bytes"] == len(html_bytes)
        assert (tmp_path / "edgar__0000914021-24-000123.htm").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        target = tmp_path / "edgar__0000914021-24-000123.htm"
        target.write_bytes(b"already here")

        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "download_url": "https://example.com/doc.htm",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_exists"

    def test_skips_no_url(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        record = {
            "source": "edgar",
            "native_id": "no-url",
            "storage_key": "edgar__no-url",
            "download_url": "",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_no_url"


class TestRunEdgarDownload:
    """Tests for the full download pipeline."""

    def test_reads_discovery_and_downloads(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "title": "Prospectus Supplement",
            "issuer_name": "REPUBLIC OF ARGENTINA",
            "doc_type": "424B5",
            "publication_date": "2024-06-15",
            "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000091402124000123/d12345.htm",
            "file_ext": "htm",
            "source_metadata": {
                "cik": "0000914021",
                "accession_number": "0000914021-24-000123",
                "form_type": "424B5",
                "primary_document": "d12345.htm",
            },
        }
        discovery.write_text(json.dumps(record) + "\n")

        html_bytes = b"<html>Prospectus</html>"
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = html_bytes
        mock_client.get.return_value = mock_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_edgar_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay=0.0,
        )

        assert stats["downloaded"] == 1
        manifest = manifest_dir / "edgar_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(line) for line in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "0000914021-24-000123"

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        lines = []
        for i in range(15):
            lines.append(
                json.dumps(
                    {
                        "source": "edgar",
                        "native_id": f"fail-{i:03d}",
                        "storage_key": f"edgar__fail-{i:03d}",
                        "title": f"Fail {i}",
                        "issuer_name": "TEST",
                        "doc_type": "424B5",
                        "publication_date": "2024-01-01",
                        "download_url": f"https://example.com/fail-{i}.htm",
                        "file_ext": "htm",
                        "source_metadata": {},
                    }
                )
            )
        discovery.write_text("\n".join(lines) + "\n")

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("connection refused")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_edgar_download(
            client=mock_client,
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

    def test_telemetry_logs_failure(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "source": "edgar",
            "native_id": "err-doc",
            "storage_key": "edgar__err-doc",
            "title": "Error Doc",
            "issuer_name": "TEST",
            "doc_type": "424B5",
            "publication_date": "2024-01-01",
            "download_url": "https://example.com/err.htm",
            "file_ext": "htm",
            "source_metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("timeout")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        run_edgar_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=tmp_path / "original",
            manifest_dir=tmp_path / "manifests",
            logger=logger,
            run_id="test-run",
            delay=0.0,
        )

        log_entries = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert len(log_entries) == 1
        assert log_entries[0]["status"] == "error"
        assert log_entries[0]["duration_ms"] >= 0
