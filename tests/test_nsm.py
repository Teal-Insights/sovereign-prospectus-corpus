"""Tests for the NSM source adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from corpus.sources.nsm import parse_hits, query_nsm_api

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestQueryNsmApi:
    """Tests for NSM API query construction and response parsing."""

    def test_query_returns_hits(self) -> None:
        """query_nsm_api returns list of hit dicts from API response."""
        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        hits, total = query_nsm_api(mock_client, from_offset=0, size=100)

        assert len(hits) == 2
        assert total == 2

    def test_query_sends_correct_payload(self) -> None:
        """query_nsm_api sends latest_flag=Y, no country filters."""
        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        query_nsm_api(mock_client, from_offset=0, size=500)

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["from"] == 0
        assert payload["size"] == 500
        criteria_names = [c["name"] for c in payload["criteriaObj"]["criteria"]]
        assert "latest_flag" in criteria_names
        # No company_lei filter — breadth over depth
        assert "company_lei" not in criteria_names

    def test_query_empty_response(self) -> None:
        """query_nsm_api returns empty list when no hits."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"hits": {"total": {"value": 0}, "hits": []}}
        mock_client.post.return_value = mock_response

        hits, total = query_nsm_api(mock_client, from_offset=0, size=100)

        assert hits == []
        assert total == 0


class TestParseHits:
    """Tests for parsing raw API hits into manifest records."""

    def test_parse_direct_pdf_hit(self) -> None:
        """Hit with .pdf download_link produces correct manifest record."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][0]  # PDF link

        records = parse_hits([hit])

        assert len(records) == 1
        rec = records[0]
        assert rec["source"] == "nsm"
        assert rec["native_id"] == "abc-123-pdf"
        assert rec["storage_key"] == "nsm__abc-123-pdf"
        assert (
            rec["download_url"]
            == "https://data.fca.org.uk/artefacts/NSM/Portal/NI-000131055/NI-000131055.pdf"
        )
        assert rec["issuer_name"] == "REPUBLIC OF KENYA"
        assert rec["lei"] == "549300VVURQQYU45PR87"
        assert rec["doc_type"] == "PDI"
        assert rec["title"] == "Offering Circular for USD 1bn Notes"

    def test_parse_html_hit(self) -> None:
        """Hit with .html download_link still produces a record with full URL."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][1]  # HTML link

        records = parse_hits([hit])

        assert len(records) == 1
        rec = records[0]
        assert rec["native_id"] == "def-456-html"
        assert rec["download_url"] == "https://data.fca.org.uk/artefacts/NSM/RNS/def-456-html.html"

    def test_parse_preserves_source_metadata(self) -> None:
        """Extra NSM fields go into source_metadata."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][0]

        records = parse_hits([hit])
        meta = records[0].get("source_metadata", {})

        assert meta["nsm_source"] == "FCA"
        assert meta["type_name"] == "Publication of a Prospectus"
        assert meta["classifications_code"] == "3.1"

    def test_parse_hit_missing_download_link(self) -> None:
        """Hit without download_link produces empty download_url."""
        hit = {
            "_id": "no-link",
            "_source": {
                "disclosure_id": "no-link",
                "download_link": "",
                "company": "TEST CORP",
                "lei": "",
                "type_code": "PDI",
                "type": "Test",
                "headline": "No link doc",
                "submitted_date": "2024-01-01T00:00:00Z",
                "publication_date": "2024-01-01T00:00:00Z",
                "source": "FCA",
                "seq_id": "no-link",
                "hist_seq": "1",
                "classifications": "",
                "classifications_code": "",
                "tag_esef": "",
                "lei_remediation_flag": "N",
                "last_updated_date": "2024-01-01T00:00:00Z",
            },
        }
        records = parse_hits([hit])
        assert records[0]["download_url"] == ""


class TestResolvePdfUrl:
    """Tests for two-hop HTML->PDF URL resolution."""

    def test_direct_pdf_url_returned_as_is(self) -> None:
        """URL ending in .pdf is returned unchanged."""
        from corpus.sources.nsm import resolve_pdf_url

        url = "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf"
        result = resolve_pdf_url(url, client=MagicMock())
        assert result == url

    def test_html_url_extracts_pdf_link(self) -> None:
        """HTML page with a PDF link returns the resolved PDF URL."""
        from corpus.sources.nsm import resolve_pdf_url

        html_content = (FIXTURES / "nsm_html_page.html").read_text()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html_content
        mock_client.get.return_value = mock_response

        url = "https://data.fca.org.uk/artefacts/NSM/RNS/def-456.html"
        result = resolve_pdf_url(url, client=mock_client)

        assert result == "https://data.fca.org.uk/artefacts/NSM/RNS/abc-123/prospectus.pdf"

    def test_html_url_no_pdf_link_returns_none(self) -> None:
        """HTML page without any PDF link returns None."""
        from corpus.sources.nsm import resolve_pdf_url

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body>No links here</body></html>"
        mock_client.get.return_value = mock_response

        url = "https://data.fca.org.uk/artefacts/NSM/RNS/no-pdf.html"
        result = resolve_pdf_url(url, client=mock_client)

        assert result is None


class TestDownloadNsmDocument:
    """Tests for single-document download + manifest record creation."""

    def test_downloads_pdf_and_returns_record(self, tmp_path: Path) -> None:
        """Successful PDF download returns manifest record with file_path and file_hash."""
        from corpus.sources.nsm import download_nsm_document

        pdf_bytes = b"%PDF-1.4 fake pdf content here"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = pdf_bytes
        mock_client.get.return_value = mock_response

        record = {
            "source": "nsm",
            "native_id": "abc-123-pdf",
            "storage_key": "nsm__abc-123-pdf",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(record, client=mock_client, output_dir=tmp_path)

        assert result is not None
        assert result["file_path"] == str(tmp_path / "nsm__abc-123-pdf.pdf")
        assert result["file_hash"] == hashlib.sha256(pdf_bytes).hexdigest()
        assert (tmp_path / "nsm__abc-123-pdf.pdf").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        """If the PDF already exists on disk, returns None (skip)."""
        from corpus.sources.nsm import download_nsm_document

        target = tmp_path / "nsm__abc-123-pdf.pdf"
        target.write_bytes(b"%PDF-1.4 already here")

        record = {
            "source": "nsm",
            "native_id": "abc-123-pdf",
            "storage_key": "nsm__abc-123-pdf",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None

    def test_html_link_resolves_then_downloads(self, tmp_path: Path) -> None:
        """HTML download URL triggers resolution before downloading."""
        from corpus.sources.nsm import download_nsm_document

        html_content = '<html><a href="/artefacts/NSM/RNS/real.pdf">PDF</a></html>'
        pdf_bytes = b"%PDF-1.4 real content"

        mock_client = MagicMock()
        html_resp = MagicMock()
        html_resp.text = html_content
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        mock_client.get.side_effect = [html_resp, pdf_resp]

        record = {
            "source": "nsm",
            "native_id": "def-456-html",
            "storage_key": "nsm__def-456-html",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/def-456.html",
        }

        result = download_nsm_document(record, client=mock_client, output_dir=tmp_path)

        assert result is not None
        assert (tmp_path / "nsm__def-456-html.pdf").exists()

    def test_invalid_pdf_returns_none(self, tmp_path: Path) -> None:
        """Non-PDF content (no %PDF header) returns None."""
        from corpus.sources.nsm import download_nsm_document

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"<html>not a pdf</html>"
        mock_client.get.return_value = mock_response

        record = {
            "source": "nsm",
            "native_id": "bad-content",
            "storage_key": "nsm__bad-content",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(record, client=mock_client, output_dir=tmp_path)
        assert result is None


class TestRunNsmDownload:
    """Tests for the full NSM download pipeline orchestrator."""

    def test_writes_manifest_jsonl(self, tmp_path: Path) -> None:
        """run_nsm_download writes one JSONL line per downloaded document."""
        from corpus.logging import CorpusLogger
        from corpus.sources.nsm import run_nsm_download

        fixture = _load_fixture("nsm_api_response.json")
        pdf_bytes = b"%PDF-1.4 fake pdf content"

        mock_client = MagicMock()
        # First call: API query returns fixture; Second+ calls: PDF downloads
        api_resp = MagicMock()
        api_resp.json.return_value = fixture
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        pdf_resp.text = pdf_bytes.decode("utf-8", errors="replace")
        mock_client.post.return_value = api_resp
        mock_client.get.return_value = pdf_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_api=0.0,
            delay_download=0.0,
            page_size=100,
        )

        manifest_file = manifest_dir / "nsm_manifest.jsonl"
        assert manifest_file.exists()
        manifest_lines = [
            json.loads(line)
            for line in manifest_file.read_text().strip().split("\n")
            if line.strip()
        ]
        # Both hits have download URLs, at least the PDF one should succeed
        assert len(manifest_lines) >= 1
        assert stats["downloaded"] >= 1
        assert stats["api_pages_fetched"] == 1

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        """Pipeline aborts after total_failures_abort threshold."""
        from corpus.logging import CorpusLogger
        from corpus.sources.nsm import run_nsm_download

        # Create many hits that will all fail (non-PDF content)
        bad_hits = []
        for i in range(15):
            bad_hits.append(
                {
                    "_id": f"fail-{i}",
                    "_source": {
                        "disclosure_id": f"fail-{i}",
                        "download_link": f"NSM/Portal/fail-{i}.pdf",
                        "company": "BADCORP",
                        "lei": "",
                        "type_code": "PDI",
                        "type": "Test",
                        "headline": f"Fail doc {i}",
                        "submitted_date": "2024-01-01T00:00:00Z",
                        "publication_date": "2024-01-01T00:00:00Z",
                        "source": "FCA",
                        "seq_id": f"fail-{i}",
                        "hist_seq": "1",
                        "classifications": "",
                        "classifications_code": "",
                        "tag_esef": "",
                        "lei_remediation_flag": "N",
                        "last_updated_date": "2024-01-01T00:00:00Z",
                    },
                }
            )

        mock_client = MagicMock()
        api_resp = MagicMock()
        api_resp.json.return_value = {"hits": {"total": {"value": 15}, "hits": bad_hits}}
        mock_client.post.return_value = api_resp
        # All downloads return non-PDF content
        bad_resp = MagicMock()
        bad_resp.content = b"not a pdf"
        mock_client.get.return_value = bad_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_api=0.0,
            delay_download=0.0,
            total_failures_abort=5,
        )

        assert stats["aborted"]
        assert stats["failed"] <= 6  # abort triggers at threshold, may overshoot by 1


class TestNsmCli:
    """Tests for the CLI download nsm command."""

    def test_download_nsm_help(self) -> None:
        """corpus download nsm --help shows options."""
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output

    def test_download_nsm_dry_run(self, tmp_path: Path) -> None:
        """corpus download nsm --dry-run reports total count without downloading."""
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()

        with patch("corpus.sources.nsm.query_nsm_api") as mock_query:
            mock_query.return_value = ([], 42)

            result = runner.invoke(
                cli,
                [
                    "download",
                    "nsm",
                    "--dry-run",
                    "--output-dir",
                    str(tmp_path / "original"),
                    "--manifest-dir",
                    str(tmp_path / "manifests"),
                ],
            )

        assert result.exit_code == 0
        assert "42" in result.output
