"""Per-source resolvers for provenance URL fields.

For each document record, these functions return ``(source_page_url, source_page_kind)``
where ``source_page_url`` links to the human-facing filing page on the original
source and ``source_page_kind`` is one of:

    filing_index | artifact_html | artifact_pdf | search_page | none

These are pure functions over the manifest-record dict. They're safe to call
during manifest backfill and during resolver unit tests.

See ``docs/superpowers/specs/2026-04-10-task2-manifest-research.md`` for the
per-source field layouts and URL formats.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

Resolution = tuple[str | None, str]

_EDGAR_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/"
    "{accession_with_dashes}-index.htm"
)

NSM_SEARCH_FALLBACK = "https://data.fca.org.uk/search/"

# PDIP has no per-document deep links. The only stable public entry point is
# the search interface. All PDIP documents share this source_page_url.
# Revisit if/when Georgetown publishes per-document permalinks.
PDIP_SEARCH_PAGE = "https://publicdebtispublic.mdi.georgetown.edu/search/"


def _coerce_source_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return source_metadata as a dict regardless of whether it's stored
    as a nested dict or a JSON string in the record."""
    meta = record.get("source_metadata")
    if meta is None:
        return {}
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(meta, dict):
        return meta
    return {}


def build_edgar_source_page(record: dict[str, Any]) -> Resolution:
    """EDGAR: construct the filing-index URL from cik + accession_number.

    Example output:
        https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm
    """
    meta = _coerce_source_metadata(record)
    cik = meta.get("cik")
    accession = meta.get("accession_number")
    if not cik or not accession:
        return None, "none"
    try:
        cik_int = str(int(str(cik)))  # strip leading zeros
    except ValueError:
        return None, "none"
    accession_no_dashes = str(accession).replace("-", "")
    url = _EDGAR_INDEX_URL.format(
        cik_int=cik_int,
        accession_no_dashes=accession_no_dashes,
        accession_with_dashes=accession,
    )
    return url, "filing_index"


def build_nsm_source_page(record: dict[str, Any]) -> Resolution:
    """NSM: the ``download_url`` IS the artefact URL on the FCA site.
    Classify by extension; fall back to the NSM search page if absent or
    unknown.

    The FCA site is a SPA for the search UI but artefact URLs themselves
    are direct file downloads, so they do resolve as deep links.

    Classification uses the URL path only (via ``urllib.parse.urlparse``)
    so that query strings or fragments — not present today but cheap
    insurance against a future FCA URL format — don't defeat the
    extension check.
    """
    download_url = record.get("download_url")
    if not download_url:
        return NSM_SEARCH_FALLBACK, "search_page"
    path = urlparse(str(download_url)).path.lower()
    if path.endswith(".pdf"):
        return download_url, "artifact_pdf"
    if path.endswith(".html") or path.endswith(".htm"):
        return download_url, "artifact_html"
    return NSM_SEARCH_FALLBACK, "search_page"


def build_pdip_source_page(_record: dict[str, Any]) -> Resolution:
    """PDIP: no per-document deep links exist. Always return the search page."""
    return PDIP_SEARCH_PAGE, "search_page"


_RESOLVERS = {
    "edgar": build_edgar_source_page,
    "nsm": build_nsm_source_page,
    "pdip": build_pdip_source_page,
}


def resolve_source_page(record: dict[str, Any]) -> Resolution:
    """Dispatch to the per-source resolver. Returns ``(None, "none")`` for
    unknown sources so the backfill script can still write the record
    without crashing."""
    source = record.get("source")
    resolver = _RESOLVERS.get(str(source))
    if resolver is None:
        return None, "none"
    return resolver(record)
