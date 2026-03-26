# EDGAR Source Adapter Design

**Date:** 2026-03-26
**Task:** Task 5 — EDGAR source adapter
**Branch:** `feature/source-edgar`

## Overview

Build an EDGAR source adapter following the NSM two-phase pattern (discover → download). No migration of Phase 0 data — EDGAR downloads are fast enough to re-download fresh with proper logging, telemetry, and metadata. EDGAR filings are ~97% HTML, not PDF — the adapter downloads all file types and stores them with original extensions.

## Architecture

Two CLI commands (same pattern as NSM):

1. **`corpus discover edgar`** — Query EDGAR submissions API for each sovereign CIK. Write `data/edgar_discovery.jsonl`.
2. **`corpus download edgar`** — Read discovery JSONL, skip existing files, download remaining, write `edgar_manifest.jsonl`.

## Discovery

- Endpoint: `https://data.sec.gov/submissions/CIK{cik}.json`
- 27 sovereign CIKs across 4 priority tiers (embedded constant from Phase 0 census)
- Filter to prospectus form types: `424B2, 424B5, 424B3, 424B4, 424B1, FWP`
- Paginate through `filings.files[]` for older submissions
- Rate limit: 0.25s between requests (4 req/sec, under SEC 10 req/sec limit)
- Output: one JSONL record per filing with full metadata

## Download

- Read discovery JSONL, convert to manifest records
- Skip files that already exist on disk (from previous runs)
- Download URL pattern: `https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{filename}`
- Store at `data/original/edgar__{accession_number}.{ext}`
- No PDF header validation (HTML filings are expected)
- SHA-256 hash of downloaded content
- Circuit breaker: abort after `total_failures_abort` (default 10, from config.toml)
- SEC 429 handling: sleep 660 seconds then retry

## Rate Limiting

- SEC requires User-Agent with contact info: `sovereign-prospectus-corpus/{version} ({CONTACT_EMAIL})`
- CONTACT_EMAIL read from .env via CorpusHTTPClient
- 0.25s minimum between requests (configurable in config.toml `[edgar] delay`)
- On HTTP 429: sleep `rate_limit_sleep_seconds` (default 660) from config.toml

## Identifiers

- **Native ID:** accession number (e.g., `0000914021-24-000123`)
- **Storage key:** `edgar__{accession_number}` (no country in path, per decision #10)
- **File extension:** preserved from source (`.htm`, `.pdf`, `.paper`, etc.)

## Manifest Record Shape

```json
{
    "source": "edgar",
    "native_id": "0000914021-24-000123",
    "storage_key": "edgar__0000914021-24-000123",
    "title": "424B5 - REPUBLIC OF ARGENTINA",
    "issuer_name": "REPUBLIC OF ARGENTINA",
    "doc_type": "424B5",
    "publication_date": "2024-06-15",
    "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000091402124000123/d12345.htm",
    "file_path": "data/original/edgar__0000914021-24-000123.htm",
    "file_hash": "<sha256>",
    "file_size_bytes": 123456,
    "source_metadata": {
        "cik": "0000914021",
        "accession_number": "0000914021-24-000123",
        "form_type": "424B5",
        "primary_document": "d12345.htm",
        "tier": 1
    }
}
```

## Sovereign CIK List

27 CIKs across 4 tiers (from Phase 0 `edgar_sovereign_census.json`):

| Tier | Countries |
|------|-----------|
| 1 | Nigeria, Argentina, Colombia, Indonesia, Turkey, Brazil, South Africa |
| 2 | Mexico, Chile, Panama, Peru, Uruguay, Philippines, Jamaica (2 CIKs), Belize |
| 3 | Korea, Israel, Hungary, Italy |
| 4 | Greece, Finland, Sweden, Canada, Japan, New Zealand, Portugal |

## Config (config.toml)

Already exists:
```toml
[edgar]
delay = 0.2
max_retries = 3
timeout = 60

[edgar.circuit_breaker]
consecutive_failures_skip = 5
rate_limit_sleep_seconds = 660
total_failures_abort = 10
```

## Testing

Unit tests with mocked HTTP responses (fixture JSON captured from real API):
- Submissions JSON parsing → filing list extraction
- Older filing pagination
- Download skip logic (file already exists)
- Circuit breaker fires at threshold
- SEC 429 rate-limit sleep behavior
- Manifest record shape validation
- CLI integration tests (help text, basic invocation)

End-to-end validation: actually run `corpus discover edgar` and `corpus download edgar` against real SEC API as part of task verification (Phase 4).

## Files

- `src/corpus/sources/edgar.py` — adapter module
- `tests/test_edgar.py` — unit tests
- `tests/fixtures/edgar_submissions_response.json` — fixture
- CLI commands in `src/corpus/cli.py` (update existing stubs)
