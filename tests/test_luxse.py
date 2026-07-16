"""Tests for LuxSE source adapter."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from corpus.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

from corpus.sources.luxse import (
    _build_download_url,
    _extract_issuer_name,
    discover_luxse,
    download_luxse_document,
)


def _write_valid_pdf(path: Path, text: str) -> bytes:
    import fitz

    document = fitz.open()
    document.new_page().insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_extract_issuer_name_with_isin():
    comp = "VENEZUELA (BOLIVARIAN REPUBLIC OF) - XS0029456067 Venezuela 6,75% 90-20"
    assert _extract_issuer_name(comp) == "VENEZUELA (BOLIVARIAN REPUBLIC OF)"


def test_extract_issuer_name_no_separator():
    assert _extract_issuer_name("PLAIN NAME") == "PLAIN NAME"


def test_extract_issuer_name_empty():
    assert _extract_issuer_name("") == ""


def test_build_download_url_encodes_special_chars():
    token = "abc+def/ghi="
    url = _build_download_url(token)
    assert url.startswith("https://dl.luxse.com/dl?v=")
    assert "+" not in url.split("?v=")[1]
    assert "/" not in url.split("?v=")[1]


def test_build_download_url_simple():
    url = _build_download_url("simpletoken")
    assert url == "https://dl.luxse.com/dl?v=simpletoken"


def test_discover_deduplicates(tmp_path: Path):
    """Duplicate document IDs across search terms are deduplicated."""
    mock_client = MagicMock()

    # Both queries return the same document
    doc = {
        "id": "12345",
        "name": "Prospectus",
        "description": None,
        "publishDate": "2020-01-01T00:00:00Z",
        "downloadUrl": "token123",
        "documentTypeCode": "D010",
        "documentPublicTypeCode": "D010",
        "categories": ["LuxSE"],
        "complement": "TEST REPUBLIC OF X - XS000",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "luxseDocumentsSearch": {
                "totalHits": 1,
                "documents": [doc],
            }
        }
    }
    mock_client.post.return_value = mock_response

    output = tmp_path / "discovery.jsonl"
    stats = discover_luxse(
        client=mock_client,
        output_path=output,
        delay=0,
    )

    # All sovereign patterns return the same doc → only 1 unique
    assert stats["unique_filings"] == 1
    lines = output.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["storage_key"] == "luxse__12345"
    assert record["source"] == "luxse"


def test_discover_uses_only_explicit_search_terms(tmp_path: Path):
    mock_client = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "data": {"luxseDocumentsSearch": {"totalHits": 0, "documents": []}}
    }
    mock_client.post.return_value = response

    stats = discover_luxse(
        client=mock_client,
        output_path=tmp_path / "discovery.jsonl",
        search_terms=["BOLIVIA (PLURINATIONAL STATE OF)"],
        delay=0,
    )

    assert stats["queries_run"] == 1
    assert mock_client.post.call_args.kwargs["json"]["variables"]["term"] == (
        "BOLIVIA (PLURINATIONAL STATE OF)"
    )


def test_targeted_discovery_filters_nonmatching_issuer(tmp_path: Path):
    mock_client = MagicMock()
    issuer_response = MagicMock()
    issuer_response.json.return_value = {
        "data": {
            "luxseIssuersSearch": {
                "totalHits": 1,
                "issuers": [{"id": "29689", "name": "BOLIVIA (PLURINATIONAL STATE OF)"}],
            }
        }
    }
    response = MagicMock()
    response.json.return_value = {
        "data": {
            "luxseDocumentsSearch": {
                "totalHits": 2,
                "documents": [
                    {
                        "id": "bolivia",
                        "name": "Offering Memorandum",
                        "publishDate": "2026-06-03",
                        "downloadUrl": "bolivia-token",
                        "complement": "BOLIVIA (PLURINATIONAL STATE OF) - US29731QAF46",
                    },
                    {
                        "id": "venezuela",
                        "name": "THE BOLIVIAN REPUBLIC OF VENEZUELA",
                        "publishDate": "2014-09-17",
                        "downloadUrl": "venezuela-token",
                        "complement": "VENEZUELA (BOLIVARIAN REPUBLIC OF) - XS000",
                    },
                ],
            }
        }
    }
    mock_client.post.side_effect = [issuer_response, response]
    term = "BOLIVIA (PLURINATIONAL STATE OF)"

    stats = discover_luxse(
        client=mock_client,
        output_path=tmp_path / "discovery.jsonl",
        search_terms=[term],
        exact_issuer_terms={term},
        delay=0,
    )

    assert stats["unique_filings"] == 1
    assert stats["per_query"][0]["issuer_id"] == "29689"
    assert stats["per_query"][0]["filtered_issuer_mismatch"] == 1
    record = json.loads((tmp_path / "discovery.jsonl").read_text())
    assert record["issuer_name"] == term
    document_variables = mock_client.post.call_args_list[1].kwargs["json"]["variables"]
    assert document_variables["term"] == ""
    assert document_variables["issuerId"] == "29689"
    assert record["source_metadata"]["issuer_id"] == "29689"
    assert record["source_metadata"]["issuer_resolution_method"] == "exact_issuer_id"
    assert record["source_metadata"]["queried_issuer_name"] == term


def test_targeted_discovery_fails_when_no_exact_documents_are_accepted(tmp_path: Path):
    from corpus.sources.luxse import LuxseQueryError

    mock_client = MagicMock()
    issuer_response = MagicMock()
    issuer_response.json.return_value = {
        "data": {
            "luxseIssuersSearch": {
                "totalHits": 1,
                "issuers": [{"id": "29689", "name": "BOLIVIA (PLURINATIONAL STATE OF)"}],
            }
        }
    }
    documents_response = MagicMock()
    documents_response.json.return_value = {
        "data": {
            "luxseDocumentsSearch": {
                "totalHits": 1,
                "documents": [
                    {
                        "id": "renamed",
                        "name": "Offering Memorandum",
                        "publishDate": "2026-06-03",
                        "downloadUrl": "token",
                        "complement": "PLURINATIONAL STATE OF BOLIVIA - US29731QAF46",
                    }
                ],
            }
        }
    }
    mock_client.post.side_effect = [issuer_response, documents_response]
    term = "BOLIVIA (PLURINATIONAL STATE OF)"

    with pytest.raises(LuxseQueryError, match="accepted no exact issuer documents"):
        discover_luxse(
            client=mock_client,
            output_path=tmp_path / "discovery.jsonl",
            search_terms=[term],
            exact_issuer_terms={term},
            fail_on_query_error=True,
            delay=0,
        )


def test_reduced_page_fallback_restarts_with_effective_size(tmp_path: Path):
    mock_client = MagicMock()
    error_response = MagicMock()
    error_response.json.return_value = {"errors": [{"message": "null publishDate"}]}

    def documents(start: int, count: int) -> list[dict]:
        return [
            {
                "id": str(index),
                "name": "Offering Memorandum",
                "publishDate": "2020-01-01",
                "downloadUrl": f"token-{index}",
                "complement": "TEST REPUBLIC - XS000",
            }
            for index in range(start, start + count)
        ]

    first = MagicMock()
    first.json.return_value = {
        "data": {"luxseDocumentsSearch": {"totalHits": 75, "documents": documents(0, 50)}}
    }
    second = MagicMock()
    second.json.return_value = {
        "data": {"luxseDocumentsSearch": {"totalHits": 75, "documents": documents(50, 25)}}
    }
    mock_client.post.side_effect = [error_response, first, second]

    stats = discover_luxse(
        client=mock_client,
        output_path=tmp_path / "discovery.jsonl",
        search_terms=["TEST REPUBLIC"],
        delay=0,
        page_size=100,
    )

    variables = [call.kwargs["json"]["variables"] for call in mock_client.post.call_args_list]
    assert [(item["size"], item["page"]) for item in variables] == [(100, 0), (50, 0), (50, 1)]
    assert stats["unique_filings"] == 75
    assert stats["query_failures"] == 0


def test_targeted_discovery_fails_when_all_query_retries_fail(tmp_path: Path):
    from corpus.sources.luxse import LuxseQueryError

    mock_client = MagicMock()
    issuer_response = MagicMock()
    issuer_response.json.return_value = {
        "data": {
            "luxseIssuersSearch": {
                "totalHits": 1,
                "issuers": [{"id": "29689", "name": "BOLIVIA (PLURINATIONAL STATE OF)"}],
            }
        }
    }
    error_response = MagicMock()
    error_response.json.return_value = {"errors": [{"message": "unresolved"}]}
    mock_client.post.side_effect = [
        issuer_response,
        error_response,
        error_response,
        error_response,
    ]

    with pytest.raises(LuxseQueryError, match="BOLIVIA"):
        term = "BOLIVIA (PLURINATIONAL STATE OF)"
        discover_luxse(
            client=mock_client,
            output_path=tmp_path / "discovery.jsonl",
            search_terms=[term],
            exact_issuer_terms={term},
            fail_on_query_error=True,
            delay=0,
        )

    assert mock_client.post.call_count == 4


def test_normal_discovery_tolerates_configured_exact_term_failure(tmp_path: Path):
    mock_client = MagicMock()
    error_response = MagicMock()
    error_response.json.return_value = {"errors": [{"message": "unresolved"}]}
    mock_client.post.return_value = error_response
    term = "BOLIVIA (PLURINATIONAL STATE OF)"
    output = tmp_path / "discovery.jsonl"

    stats = discover_luxse(
        client=mock_client,
        output_path=output,
        search_terms=[term],
        exact_issuer_terms={term},
        fail_on_query_error=False,
        delay=0,
    )

    assert stats["query_failures"] == 1
    assert stats["unique_filings"] == 0
    assert output.read_text() == ""


def test_issuer_lookup_handles_null_graphql_data() -> None:
    from corpus.sources.luxse import LuxseQueryError, resolve_luxse_issuer_id

    client = MagicMock()
    response = MagicMock()
    response.json.return_value = {"data": None}
    client.post.return_value = response

    with pytest.raises(LuxseQueryError, match="Expected one exact LuxSE issuer"):
        resolve_luxse_issuer_id(client, issuer_name="BOLIVIA (PLURINATIONAL STATE OF)")


def test_download_reconciles_existing(tmp_path: Path):
    """Existing documents return enough metadata to repair the manifest."""
    record = {"storage_key": "luxse__123", "download_url": "https://example.com"}
    target = tmp_path / "luxse__123.pdf"
    content = _write_valid_pdf(target, "Existing prospectus")

    result, status = download_luxse_document(record, client=MagicMock(), output_dir=tmp_path)
    assert status == "skipped_exists"
    assert result is not None
    assert result["file_hash"] == hashlib.sha256(content).hexdigest()


def test_download_rejects_truncated_existing_pdf(tmp_path: Path):
    record = {"storage_key": "luxse__123", "download_url": "https://example.com"}
    (tmp_path / "luxse__123.pdf").write_bytes(b"%PDF-truncated")

    result, status = download_luxse_document(record, client=MagicMock(), output_dir=tmp_path)

    assert result is None
    assert status == "failed_invalid_pdf"


def test_download_skips_no_url(tmp_path: Path):
    record = {"storage_key": "luxse__123", "download_url": ""}
    _result, status = download_luxse_document(record, client=MagicMock(), output_dir=tmp_path)
    assert status == "skipped_no_url"


def test_download_validates_pdf_header(tmp_path: Path):
    """Non-PDF responses are rejected."""
    record = {"storage_key": "luxse__123", "download_url": "https://example.com/doc"}
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"<html>Not a PDF</html>"
    mock_client.get.return_value = mock_resp

    _result, status = download_luxse_document(record, client=mock_client, output_dir=tmp_path)
    assert status == "failed_invalid_pdf"


def test_download_success(tmp_path: Path):
    """Successful download returns enriched record with hash."""
    record = {
        "storage_key": "luxse__456",
        "download_url": "https://dl.luxse.com/dl?v=token",
        "source": "luxse",
    }
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = _write_valid_pdf(tmp_path / "valid-source.pdf", "Fresh prospectus")
    mock_client.get.return_value = mock_resp

    result, status = download_luxse_document(record, client=mock_client, output_dir=tmp_path)
    assert status == "downloaded"
    assert result is not None
    assert result["file_hash"]
    assert result["file_size_bytes"] == len(mock_resp.content)
    assert (tmp_path / "luxse__456.pdf").exists()


def test_download_rejects_truncated_fresh_pdf_before_promotion(tmp_path: Path):
    record = {
        "storage_key": "luxse__truncated-fresh",
        "download_url": "https://dl.luxse.com/dl?v=token",
    }
    response = MagicMock(status_code=200, url=record["download_url"])
    response.content = b"%PDF-truncated"
    client = MagicMock()
    client.get.return_value = response

    result, status = download_luxse_document(record, client=client, output_dir=tmp_path)

    assert result is None
    assert status == "failed_invalid_pdf"
    assert not (tmp_path / "luxse__truncated-fresh.pdf").exists()


def test_run_download_repairs_manifest_and_is_idempotent(tmp_path: Path):
    from corpus.logging import CorpusLogger
    from corpus.sources.luxse import run_luxse_download

    record = {
        "source": "luxse",
        "native_id": "105422819",
        "storage_key": "luxse__105422819",
        "download_url": "https://example.test/bolivia.pdf",
    }
    discovery = tmp_path / "discovery.jsonl"
    discovery.write_text(json.dumps(record) + "\n")
    output_dir = tmp_path / "data" / "original"
    output_dir.mkdir(parents=True)
    _write_valid_pdf(output_dir / "luxse__105422819.pdf", "Existing prospectus")
    manifest_dir = tmp_path / "data" / "manifests"
    logger = CorpusLogger(tmp_path / "telemetry.jsonl", run_id="resume")

    first = run_luxse_download(
        client=MagicMock(),
        discovery_file=discovery,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id="resume",
        delay=0,
    )
    manifest = manifest_dir / "luxse_manifest.jsonl"
    first_bytes = manifest.read_bytes()
    second = run_luxse_download(
        client=MagicMock(),
        discovery_file=discovery,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id="resume-2",
        delay=0,
    )

    records = [json.loads(line) for line in manifest.read_text().splitlines()]
    assert first["skipped"] == second["skipped"] == 1
    assert manifest.read_bytes() == first_bytes
    assert len(records) == 1
    assert records[0]["file_path"] == "data/original/luxse__105422819.pdf"
    telemetry = [
        json.loads(line) for line in (tmp_path / "telemetry.jsonl").read_text().splitlines()
    ]
    assert [entry["status"] for entry in telemetry] == [
        "skipped_exists",
        "skipped_exists",
    ]


def test_run_download_rejects_same_key_hash_conflict(tmp_path: Path):
    from corpus.io.manifest import ManifestConflictError
    from corpus.logging import CorpusLogger
    from corpus.sources.luxse import run_luxse_download

    record = {
        "source": "luxse",
        "native_id": "conflict",
        "storage_key": "luxse__conflict",
        "download_url": "https://example.test/conflict.pdf",
    }
    discovery = tmp_path / "discovery.jsonl"
    discovery.write_text(json.dumps(record) + "\n")
    output_dir = tmp_path / "data" / "original"
    output_dir.mkdir(parents=True)
    current = _write_valid_pdf(output_dir / "luxse__conflict.pdf", "Current prospectus")
    manifest_dir = tmp_path / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    assert current
    stale = {**record, "file_hash": hashlib.sha256(b"stale").hexdigest()}
    (manifest_dir / "luxse_manifest.jsonl").write_text(json.dumps(stale) + "\n")

    with pytest.raises(ManifestConflictError, match="luxse__conflict"):
        run_luxse_download(
            client=MagicMock(),
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=CorpusLogger(tmp_path / "telemetry.jsonl", run_id="conflict"),
            run_id="conflict",
            delay=0,
        )


def test_run_download_rate_limit_trips_circuit_breaker(tmp_path: Path):
    from corpus.logging import CorpusLogger
    from corpus.sources.luxse import run_luxse_download

    record = {
        "source": "luxse",
        "native_id": "limited",
        "storage_key": "luxse__limited",
        "download_url": "https://example.test/limited.pdf",
    }
    discovery = tmp_path / "discovery.jsonl"
    discovery.write_text(json.dumps(record) + "\n")
    response = MagicMock(status_code=429, url="https://example.test/limited.pdf")
    client = MagicMock()
    client.get.return_value = response

    stats = run_luxse_download(
        client=client,
        discovery_file=discovery,
        output_dir=tmp_path / "data" / "original",
        manifest_dir=tmp_path / "data" / "manifests",
        logger=CorpusLogger(tmp_path / "telemetry.jsonl", run_id="limited"),
        run_id="limited",
        delay=0,
        total_failures_abort=1,
        rate_limit_sleep=0,
    )

    assert stats["failed"] == 1
    assert stats["aborted"] is True
    entries = [
        json.loads(line) for line in (tmp_path / "telemetry.jsonl").read_text().splitlines()
    ]
    assert entries[-1]["status"] == "failed_rate_limited"


def test_run_download_treats_missing_url_as_failure(tmp_path: Path):
    from corpus.logging import CorpusLogger
    from corpus.sources.luxse import run_luxse_download

    record = {
        "source": "luxse",
        "native_id": "missing-url",
        "storage_key": "luxse__missing-url",
        "download_url": "",
    }
    discovery = tmp_path / "discovery.jsonl"
    discovery.write_text(json.dumps(record) + "\n")

    stats = run_luxse_download(
        client=MagicMock(),
        discovery_file=discovery,
        output_dir=tmp_path / "data" / "original",
        manifest_dir=tmp_path / "data" / "manifests",
        logger=CorpusLogger(tmp_path / "telemetry.jsonl", run_id="missing-url"),
        run_id="missing-url",
        delay=0,
    )

    assert stats["failed"] == 1
    assert stats["skipped"] == 0


def test_discover_luxse_cli_supports_explicit_exact_terms(tmp_path: Path):
    output = tmp_path / "discovery.jsonl"
    with patch("corpus.sources.luxse.discover_luxse") as mock_discover:
        mock_discover.return_value = {
            "unique_filings": 0,
            "total_hits_raw": 0,
            "per_query": [],
            "query_failures": 0,
        }
        result = CliRunner().invoke(
            cli,
            [
                "discover",
                "luxse",
                "--search-term",
                "BOLIVIA (PLURINATIONAL STATE OF)",
                "--output",
                str(output),
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_discover.call_args.kwargs["search_terms"] == ["BOLIVIA (PLURINATIONAL STATE OF)"]
    assert mock_discover.call_args.kwargs["exact_issuer_terms"] == {
        "BOLIVIA (PLURINATIONAL STATE OF)"
    }
    assert mock_discover.call_args.kwargs["fail_on_query_error"] is True


def test_discover_luxse_cli_adds_configured_terms(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "corpus.cli._load_config",
        lambda: {"luxse": {"additional_search_terms": ["BOLIVIA (PLURINATIONAL STATE OF)"]}},
    )
    with patch("corpus.sources.luxse.discover_luxse") as mock_discover:
        mock_discover.return_value = {
            "unique_filings": 0,
            "total_hits_raw": 0,
            "per_query": [],
            "query_failures": 0,
        }
        result = CliRunner().invoke(
            cli,
            ["discover", "luxse", "--output", str(tmp_path / "discovery.jsonl")],
        )

    assert result.exit_code == 0, result.output
    assert "BOLIVIA (PLURINATIONAL STATE OF)" in mock_discover.call_args.kwargs["search_terms"]


def test_discover_luxse_cli_tolerates_generic_query_failure(tmp_path: Path):
    with patch("corpus.sources.luxse.discover_luxse") as mock_discover:
        mock_discover.return_value = {
            "unique_filings": 2,
            "total_hits_raw": 2,
            "per_query": [],
            "query_failures": 1,
        }
        result = CliRunner().invoke(
            cli,
            ["discover", "luxse", "--output", str(tmp_path / "discovery.jsonl")],
        )

    assert result.exit_code == 0, result.output
