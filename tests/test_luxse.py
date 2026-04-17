"""Tests for LuxSE source adapter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

from corpus.sources.luxse import (
    _build_download_url,
    _extract_issuer_name,
    discover_luxse,
    download_luxse_document,
)


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


def test_download_skips_existing(tmp_path: Path):
    """Documents that already exist are skipped."""
    record = {"storage_key": "luxse__123", "download_url": "https://example.com"}
    target = tmp_path / "luxse__123.pdf"
    target.write_bytes(b"%PDF-fake")

    result, status = download_luxse_document(record, client=MagicMock(), output_dir=tmp_path)
    assert status == "skipped_exists"
    assert result is None


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
    mock_resp.content = b"%PDF-1.4 fake pdf content"
    mock_client.get.return_value = mock_resp

    result, status = download_luxse_document(record, client=mock_client, output_dir=tmp_path)
    assert status == "downloaded"
    assert result is not None
    assert result["file_hash"]
    assert result["file_size_bytes"] == len(b"%PDF-1.4 fake pdf content")
    assert (tmp_path / "luxse__456.pdf").exists()
