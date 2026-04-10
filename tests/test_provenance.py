"""Unit tests for per-source provenance URL resolvers."""

from __future__ import annotations

import pytest  # noqa: F401  (reserved for future parametrize)

from corpus.sources.provenance import (
    build_edgar_source_page,
    build_nsm_source_page,
    build_pdip_source_page,
    resolve_source_page,
)

# ── EDGAR ──────────────────────────────────────────────────────────────


def test_edgar_filing_index_url_strips_cik_zeros_and_dashes() -> None:
    """CIK loses leading zeros, accession dashes are stripped for dir path
    but kept for the filename segment."""
    record = {
        "source": "edgar",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    url, kind = build_edgar_source_page(record)
    assert (
        url
        == "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm"
    )
    assert kind == "filing_index"


def test_edgar_handles_source_metadata_as_json_string() -> None:
    """When source_metadata is a JSON string (post-ingest round trip),
    the resolver must still work."""
    record = {
        "source": "edgar",
        "source_metadata": '{"cik": "0000914021", "accession_number": "0001193125-20-188103"}',
    }
    url, kind = build_edgar_source_page(record)
    assert url is not None
    assert "914021" in url
    assert kind == "filing_index"


def test_edgar_missing_cik_returns_none() -> None:
    record = {
        "source": "edgar",
        "source_metadata": {"accession_number": "0001193125-20-188103"},
    }
    url, kind = build_edgar_source_page(record)
    assert url is None
    assert kind == "none"


def test_edgar_missing_accession_returns_none() -> None:
    record = {"source": "edgar", "source_metadata": {"cik": "0000914021"}}
    url, kind = build_edgar_source_page(record)
    assert url is None
    assert kind == "none"


# ── NSM ────────────────────────────────────────────────────────────────


NSM_SEARCH_FALLBACK = "https://data.fca.org.uk/search/"


def test_nsm_html_artefact() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/d5c84201-05ec-4e43-b333-fc8dcbc6ab24.html",
    }
    url, kind = build_nsm_source_page(record)
    assert url == record["download_url"]
    assert kind == "artifact_html"


def test_nsm_htm_artefact_classified_as_html() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.htm",
    }
    url, kind = build_nsm_source_page(record)
    assert kind == "artifact_html"


def test_nsm_pdf_artefact() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/pdf/xyz.pdf",
    }
    url, kind = build_nsm_source_page(record)
    assert url == record["download_url"]
    assert kind == "artifact_pdf"


def test_nsm_case_insensitive_extension() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.HTML",
    }
    url, kind = build_nsm_source_page(record)
    assert kind == "artifact_html"


def test_nsm_missing_download_url_falls_back_to_search() -> None:
    record = {"source": "nsm", "native_id": "unknown"}
    url, kind = build_nsm_source_page(record)
    assert url == NSM_SEARCH_FALLBACK
    assert kind == "search_page"


def test_nsm_unknown_extension_falls_back_to_search() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc",
    }
    url, kind = build_nsm_source_page(record)
    assert url == NSM_SEARCH_FALLBACK
    assert kind == "search_page"


# ── PDIP ───────────────────────────────────────────────────────────────


PDIP_SEARCH_PAGE = "https://publicdebtispublic.mdi.georgetown.edu/search/"


def test_pdip_always_returns_search_page() -> None:
    record = {"source": "pdip", "native_id": "VEN85"}
    url, kind = build_pdip_source_page(record)
    assert url == PDIP_SEARCH_PAGE
    assert kind == "search_page"


def test_pdip_ignores_native_id() -> None:
    """PDIP has no per-document deep links — same URL for every record."""
    record_a = build_pdip_source_page({"source": "pdip", "native_id": "VEN85"})
    record_b = build_pdip_source_page({"source": "pdip", "native_id": "GHA42"})
    assert record_a == record_b


# ── Dispatcher ─────────────────────────────────────────────────────────


def test_dispatcher_routes_by_source() -> None:
    edgar_rec = {
        "source": "edgar",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    nsm_rec = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
    }
    pdip_rec = {"source": "pdip", "native_id": "VEN85"}

    assert resolve_source_page(edgar_rec)[1] == "filing_index"
    assert resolve_source_page(nsm_rec)[1] == "artifact_pdf"
    assert resolve_source_page(pdip_rec)[1] == "search_page"


def test_dispatcher_unknown_source_returns_none() -> None:
    record = {"source": "lse_rns", "native_id": "whatever"}
    url, kind = resolve_source_page(record)
    assert url is None
    assert kind == "none"
