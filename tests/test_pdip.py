"""Tests for the PDIP source adapter."""

from __future__ import annotations

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
