"""Tests for the PDIP source adapter."""

from __future__ import annotations

import json
from pathlib import Path

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
        assert r["title"] == "Loan Agreement between the Republic of Venezuela and International Bank for Reconstruction and Development dated December 14, 1990"
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
