"""Tests for the EDGAR source adapter."""

from __future__ import annotations

import json
from pathlib import Path

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
