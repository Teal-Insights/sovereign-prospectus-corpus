# PDIP Source Adapter Design

**Date:** 2026-03-26
**Task:** Task 6 — PDIP source adapter
**Branch:** `feature/source-pdip`

## Overview

Build a PDIP source adapter following the two-phase pattern (discover → download). The Georgetown PDIP platform exposes a search API and per-document PDF endpoint — both accessible with browser-like HTTP headers (no auth token). We download everything fresh with proper logging, telemetry, and metadata. No migration of Phase 0 hand-downloaded files.

## Architecture

Two CLI commands (same pattern as NSM/EDGAR):

1. **`corpus discover pdip`** — POST to PDIP search API, write `data/pdip_discovery.jsonl`.
2. **`corpus download pdip`** — Read discovery JSONL, download PDFs, write `pdip_manifest.jsonl`.

## Discovery

- Endpoint: `POST https://publicdebtispublic.mdi.georgetown.edu/api/search/`
- Requires browser-like headers: `Origin`, `Referer`, `User-Agent` (returns 401 "No session" without them)
- Request body: `{"page": 1, "sortBy": "date", "sortOrder": "asc", "pageSize": 1000}`
- Single call returns all documents (823 as of 2026-03-26) — no pagination needed, but implement page-based pagination as a safety net in case the corpus grows
- Pagination strategy: request `pageSize=100`, increment `page` until `len(results) < pageSize` or total reached
- Output: one JSONL record per document with `native_id` field (EDGAR pattern, per Lesson 12)

### Discovery Record Shape

```json
{
    "native_id": "VEN85",
    "source": "pdip",
    "title": "Loan Agreement between the Republic of Venezuela and...",
    "tag_status": "Annotated",
    "country": "Venezuela",
    "instrument_type": "Loan",
    "creditor_country": "Multilateral; Regional; or Plurilateral Lenders",
    "creditor_type": "Multilateral Official",
    "maturity_date": "December 15, 2005",
    "maturity_year": "2005",
    "metadata": {
        "BorrowerDebttoGDPRatio": null,
        "CommitmentSize": ["To be filled. "],
        "OtherMultilateralRegionalPlurilateralLenders": ["IBRD"]
    }
}
```

Key metadata fields extracted from the API `metadata` object:
- `DebtorCountry` → `country`
- `InstrumentType` → `instrument_type`
- `CreditorCountry` → `creditor_country`
- `CreditorType` → `creditor_type`
- `InstrumentMaturityDate` → `maturity_date`
- `InstrumentMaturityYear` → `maturity_year`
- Remaining metadata fields stored in `metadata` dict

## Download

- Read discovery JSONL, convert to manifest-shaped records
- Skip files that already exist on disk (from previous runs)
- Download URL: `GET https://publicdebtispublic.mdi.georgetown.edu/api/pdf/{native_id}`
- Requires browser-like `User-Agent` header (same 401 issue without it)
- Store at `data/original/pdip__{native_id}.pdf`
- Validate PDF: check `%PDF` magic bytes (unlike EDGAR which has HTML filings, PDIP is PDF-only)
- SHA-256 hash of downloaded content
- Circuit breaker: abort after `total_failures_abort` (from config.toml)
- HTTP 404 logged as `not_found` status — some document IDs may not have downloadable PDFs
- Rate limiting: `delay` seconds between requests (from config.toml `[pdip]`)

### Download Statuses

| Status | Meaning |
|--------|---------|
| `success` | PDF downloaded and validated |
| `skipped_exists` | File already on disk |
| `not_found` | HTTP 404 — no PDF available for this ID |
| `invalid_pdf` | Downloaded but no `%PDF` magic bytes |
| `failed_http` | HTTP error (5xx, timeout, etc.) |
| `failed_other` | Unexpected error |

### Non-Failure Statuses

`skipped_exists` and `not_found` are not counted toward circuit breaker failures. `not_found` should be added to `_NON_FAILURE_STATUSES` in `reporting.py` if not already present.

## Browser-Like Headers

The PDIP API requires specific headers to return data instead of 401. These are set per-request in the adapter, not in the shared `CorpusHTTPClient`:

```python
PDIP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": "https://publicdebtispublic.mdi.georgetown.edu",
    "Referer": "https://publicdebtispublic.mdi.georgetown.edu/search/",
}
```

Note: This means we do NOT use `CorpusHTTPClient` for PDIP (which sets its own User-Agent). Instead, use `requests.Session()` directly with the headers above and manual retry logic, similar to how the shared HTTP client works but with PDIP-specific headers.

## Identifiers

- **Native ID:** PDIP document ID (e.g., `VEN85`, `BRA1`, `ARG23`)
- **Storage key:** `pdip__{native_id}` (no country in path, per decision #7)
- **File extension:** always `.pdf`

## Manifest Record Shape

```json
{
    "source": "pdip",
    "native_id": "VEN85",
    "storage_key": "pdip__VEN85",
    "title": "Loan Agreement between the Republic of Venezuela and...",
    "issuer_name": "Venezuela",
    "doc_type": "Loan",
    "publication_date": null,
    "download_url": "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85",
    "file_ext": "pdf",
    "file_path": "data/original/pdip__VEN85.pdf",
    "file_hash": "<sha256>",
    "file_size_bytes": 5202966,
    "source_metadata": {
        "tag_status": "Annotated",
        "country": "Venezuela",
        "instrument_type": "Loan",
        "creditor_country": "Multilateral; Regional; or Plurilateral Lenders",
        "creditor_type": "Multilateral Official",
        "maturity_date": "December 15, 2005",
        "maturity_year": "2005"
    }
}
```

Notes:
- `issuer_name` set to country name (PDIP documents are sovereign, borrower = country)
- `doc_type` set to instrument type from PDIP metadata
- `publication_date` is null — PDIP API does not provide contract/issue dates in search results
- Rich metadata preserved in `source_metadata`

## Config (config.toml)

Already exists:
```toml
[pdip]
delay = 1.0
max_retries = 3
timeout = 60
```

Add circuit breaker section:
```toml
[pdip.circuit_breaker]
total_failures_abort = 10
```

## Reporting Integration

Already wired in `reporting.py`:
- `DISCOVERY_ID_KEYS["pdip"] = "native_id"`
- `DISCOVERY_PATHS["pdip"] = "data/pdip_discovery.jsonl"`

Call `write_run_report()` from CLI after download completes (per Lesson 16).

## Testing

Unit tests with mocked HTTP responses:
- Search API response parsing → discovery JSONL records
- Pagination handling (multiple pages)
- Discovery dedup (in case API returns duplicates)
- Download with PDF validation
- Download skip logic (file already exists)
- HTTP 404 handling (not_found status)
- Circuit breaker fires at threshold
- Manifest record shape validation
- CLI integration tests (help text, basic invocation)
- Browser-like headers are set correctly

End-to-end validation: actually run `corpus discover pdip` and `corpus download pdip` against real PDIP API as part of task verification (Phase 4).

## Files

- `src/corpus/sources/pdip.py` — adapter module
- `tests/test_pdip.py` — unit tests
- `tests/fixtures/pdip_search_response.json` — fixture (captured from real API)
- CLI commands in `src/corpus/cli.py` (update existing placeholder)
- `config.toml` — add `[pdip.circuit_breaker]` section
