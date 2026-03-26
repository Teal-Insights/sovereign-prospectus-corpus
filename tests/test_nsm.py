"""Tests for the NSM source adapter."""

from __future__ import annotations

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
