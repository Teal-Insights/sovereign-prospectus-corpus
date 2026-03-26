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

        result, status = download_nsm_document(record, client=mock_client, output_dir=tmp_path)

        assert status == "downloaded"
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

        result, status = download_nsm_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_exists"

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

        result, status = download_nsm_document(record, client=mock_client, output_dir=tmp_path)

        assert status == "downloaded"
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

        result, status = download_nsm_document(record, client=mock_client, output_dir=tmp_path)
        assert result is None
        assert status == "failed_invalid_pdf"


class TestRunNsmDownloadFromDiscovery:
    """Tests for run_nsm_download reading from a discovery JSONL file."""

    def test_reads_discovery_file_and_downloads(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.nsm import run_nsm_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "disclosure_id": "test-doc-001",
            "download_link": "NSM/Portal/test.pdf",
            "company": "REPUBLIC OF TESTLAND",
            "lei": "549300TEST00000000",
            "type_code": "PDI",
            "type": "Publication of a Prospectus",
            "headline": "Test Prospectus",
            "submitted_date": "2024-01-01T00:00:00Z",
            "publication_date": "2024-01-01T00:00:00Z",
            "source": "FCA",
            "seq_id": "test-doc-001",
            "hist_seq": "1",
            "classifications": "",
            "classifications_code": "",
            "tag_esef": "",
            "lei_remediation_flag": "N",
            "last_updated_date": "2024-01-01T00:00:00Z",
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.4 test content"
        mock_client = MagicMock()
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        mock_client.get.return_value = pdf_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_download=0.0,
        )

        assert stats["downloaded"] == 1
        manifest = manifest_dir / "nsm_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(line) for line in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "test-doc-001"

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.nsm import run_nsm_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "disclosure_id": "existing-doc",
            "download_link": "NSM/Portal/test.pdf",
            "company": "TESTCORP",
            "lei": "",
            "type_code": "PDI",
            "type": "Test",
            "headline": "Existing",
            "submitted_date": "2024-01-01T00:00:00Z",
            "publication_date": "2024-01-01T00:00:00Z",
            "source": "FCA",
            "seq_id": "existing-doc",
            "hist_seq": "1",
            "classifications": "",
            "classifications_code": "",
            "tag_esef": "",
            "lei_remediation_flag": "N",
            "last_updated_date": "2024-01-01T00:00:00Z",
        }
        discovery.write_text(json.dumps(record) + "\n")

        output_dir = tmp_path / "original"
        output_dir.mkdir(parents=True)
        (output_dir / "nsm__existing-doc.pdf").write_bytes(b"%PDF already here")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=MagicMock(),
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=tmp_path / "manifests",
            logger=logger,
            run_id="test-run",
            delay_download=0.0,
        )

        assert stats["downloaded"] == 0
        assert stats["skipped"] == 1


class TestRelatedOrgParsing:
    """Tests for parsing related_org field from NSM API hits."""

    def test_related_org_included_in_source_metadata(self) -> None:
        """Related organisations are included in source_metadata."""
        hit = {
            "_id": "rel-org-test",
            "_source": {
                "disclosure_id": "rel-org-test",
                "download_link": "NSM/Portal/test.pdf",
                "company": "REPUBLIC OF KENYA",
                "lei": "549300VVURQQYU45PR87",
                "type_code": "PDI",
                "type": "Publication of a Prospectus",
                "headline": "Test doc",
                "submitted_date": "2024-01-01T00:00:00Z",
                "publication_date": "2024-01-01T00:00:00Z",
                "source": "RNS",
                "seq_id": "rel-org-test",
                "hist_seq": "1",
                "classifications": "",
                "classifications_code": "",
                "tag_esef": "",
                "lei_remediation_flag": "N",
                "last_updated_date": "2024-01-01T00:00:00Z",
                "related_org": [{"lei": "ABC123", "company": "Some Bank Ltd"}],
            },
        }

        records = parse_hits([hit])
        meta = records[0]["source_metadata"]
        assert meta["related_org"] == [{"lei": "ABC123", "company": "Some Bank Ltd"}]


class TestDiscoverNsmCli:
    def test_discover_nsm_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--output" in result.output

    def test_discover_nsm_runs(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        fixture = _load_fixture("nsm_api_response.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        output = tmp_path / "discovery.jsonl"

        with patch("corpus.io.http.CorpusHTTPClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            result = runner.invoke(
                cli,
                [
                    "discover",
                    "nsm",
                    "--output",
                    str(output),
                ],
            )

        assert result.exit_code == 0
        assert "unique" in result.output.lower()


class TestDownloadNsmCliUpdated:
    def test_download_nsm_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--discovery-file" in result.output

    def test_download_nsm_requires_discovery_file(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "download",
                "nsm",
                "--discovery-file",
                str(tmp_path / "nonexistent.jsonl"),
            ],
        )
        assert result.exit_code != 0


class TestBuildSovereignQueries:
    def test_includes_name_patterns(self) -> None:
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        labels = [q[0] for q in queries]
        assert "name:Republic of" in labels
        assert "name:Kingdom of" in labels
        assert "name:State of" in labels
        assert "name:Government of" in labels
        assert "name:Sultanate of" in labels
        assert "name:Emirate of" in labels

    def test_includes_edge_cases(self) -> None:
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        labels = [q[0] for q in queries]
        assert "name:Georgia" in labels
        assert "name:Min of Finance" in labels

    def test_parses_leis_from_csv(self, tmp_path: Path) -> None:
        from corpus.sources.nsm import build_sovereign_queries

        csv_path = tmp_path / "ref.csv"
        csv_path.write_text(
            "country,issuer_types,filing_count,name_variant_count,name_variants,leis,doc_types,earliest,latest\n"
            "Kenya,sovereign,19,1,REPUBLIC OF KENYA,549300VVURQQYU45PR87,,2021-06-29,2026-02-26\n"
            "Uzbekistan,sovereign,63,1,Republic of Uzbekistan,253400TZJ7T1YULTGN68; 213800L6VDKUM3TCM927,,2019-02-04,2025-10-09\n"
        )
        queries = build_sovereign_queries(reference_csv=csv_path)
        labels = [q[0] for q in queries]
        assert "lei:549300VVURQQYU45PR87" in labels
        assert "lei:253400TZJ7T1YULTGN68" in labels
        assert "lei:213800L6VDKUM3TCM927" in labels

    def test_excludes_uk_gilt_lei(self, tmp_path: Path) -> None:
        from corpus.sources.nsm import build_sovereign_queries

        csv_path = tmp_path / "ref.csv"
        csv_path.write_text(
            "country,issuer_types,filing_count,name_variant_count,name_variants,leis,doc_types,earliest,latest\n"
            "United Kingdom,uk_sovereign,560,2,HIS MAJESTY'S TREASURY,ECTRVYYCEF89VWYS6K36,Issue of Debt,2023-07-05,2026-03-18\n"
        )
        queries = build_sovereign_queries(reference_csv=csv_path)
        labels = [q[0] for q in queries]
        assert "lei:ECTRVYYCEF89VWYS6K36" not in labels

    def test_query_criteria_format(self) -> None:
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        for label, criteria in queries:
            assert isinstance(label, str)
            assert isinstance(criteria, list)
            names = [c["name"] for c in criteria]
            assert "latest_flag" in names
            assert "company_lei" in names


class TestQueryWithCriteria:
    def test_query_with_lei_criteria(self) -> None:
        from corpus.sources.nsm import _lei_criteria, query_nsm_api

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response
        criteria = _lei_criteria("549300VVURQQYU45PR87")
        hits, _total = query_nsm_api(mock_client, criteria=criteria, from_offset=0, size=100)
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        sent_criteria = payload["criteriaObj"]["criteria"]
        names = [c["name"] for c in sent_criteria]
        assert "company_lei" in names
        assert "latest_flag" in names
        assert len(hits) == 2


class TestDiscoverNsm:
    def test_deduplicates_by_disclosure_id(self, tmp_path: Path) -> None:
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response
        queries = [
            (
                "test:q1",
                [
                    {"name": "latest_flag", "value": "Y"},
                    {"name": "company_lei", "value": ["test", "", "disclose_org", ""]},
                ],
            ),
            (
                "test:q2",
                [
                    {"name": "latest_flag", "value": "Y"},
                    {"name": "company_lei", "value": ["test2", "", "disclose_org", ""]},
                ],
            ),
        ]
        output = tmp_path / "discovery.jsonl"
        stats = discover_nsm(client=mock_client, queries=queries, output_path=output, delay=0.0)
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 2  # 2 unique, not 4
        assert stats["unique_filings"] == 2
        assert stats["total_hits_raw"] == 4
        assert stats["queries_run"] == 2

    def test_writes_discovery_jsonl(self, tmp_path: Path) -> None:
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response
        queries = [
            (
                "test:q1",
                [
                    {"name": "latest_flag", "value": "Y"},
                    {"name": "company_lei", "value": ["test", "", "disclose_org", ""]},
                ],
            )
        ]
        output = tmp_path / "discovery.jsonl"
        discover_nsm(client=mock_client, queries=queries, output_path=output, delay=0.0)
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 2
        assert "disclosure_id" in lines[0]
        assert "company" in lines[0]

    def test_logs_per_query_stats(self, tmp_path: Path) -> None:
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response
        queries = [
            (
                "test:q1",
                [
                    {"name": "latest_flag", "value": "Y"},
                    {"name": "company_lei", "value": ["t", "", "disclose_org", ""]},
                ],
            )
        ]
        output = tmp_path / "discovery.jsonl"
        stats = discover_nsm(client=mock_client, queries=queries, output_path=output, delay=0.0)
        assert len(stats["per_query"]) == 1
        assert stats["per_query"][0]["label"] == "test:q1"
        assert stats["per_query"][0]["hits"] == 2
