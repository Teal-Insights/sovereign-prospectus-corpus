# NSM Two-Phase Sovereign Discovery + Download

**Date:** 2026-03-26
**Status:** Draft

## Problem

The current NSM adapter queries the entire NSM (5.2M filings) with no filters. It should only target sovereign bond filings (~1,500-2,000 documents across ~46 countries). "Breadth over depth" means no filtering by doc type or country *within* sovereign issuers — not downloading all corporate filings.

## Design

### Phase 1: Discovery (`corpus discover nsm`)

Fast metadata-only phase. Runs sovereign-scoped API queries, deduplicates results, saves to `data/nsm_discovery.jsonl`. Takes minutes.

Three query categories, all with `latest_flag=Y` and `size=10000`:

**A) Name pattern queries** (catches most sovereigns including ones not in reference CSV):
- "Republic of"
- "Kingdom of"
- "State of"
- "Government of"
- "Sultanate of"
- "Emirate of"

Each query: `{"name": "company_lei", "value": ["<pattern>", "", "disclose_org", "related_org"]}`

**B) LEI queries** (most reliable, one per LEI):
Parse LEIs from `data/raw/sovereign_issuer_reference.csv` (leis column, semicolon-separated). Query each LEI separately — this fixes the Phase 0 multi-LEI AND bug.

Each query: `{"name": "company_lei", "value": ["", "<lei>", "disclose_org", ""]}`

Exclude UK sovereign LEI `ECTRVYYCEF89VWYS6K36` (gilt Issue of Debt notices, not bond prospectuses).

**C) Edge case name queries** (countries not caught by patterns A):
- "Georgia" — appears as "Georgia(acting through MoF Georgia)"
- "Min of Finance" — catches Chile: "Min of Finance of the Rep. of Chile"

Each query: same format as name patterns.

**Deduplication:** All hits collected, deduplicated by `disclosure_id`. A hit found by multiple queries is stored once.

**Output:** `data/nsm_discovery.jsonl` — one JSON line per unique filing with all `_source` fields from the API. Overwritten on each discovery run (not appended).

**Logging:**
- Hits per query (query label, hit count)
- Total unique disclosure_ids after dedup
- New issuers not in reference CSV (by company name)
- Summary to stdout

**Expected results:** ~1,500-2,000 unique sovereign filings.

### Phase 2: Download (`corpus download nsm`)

Slow PDF download phase. Reads `data/nsm_discovery.jsonl`, downloads each document. Takes hours.

- Iterates discovery results, calls existing `download_nsm_document` for each
- Two-hop HTML→PDF resolution (existing `resolve_pdf_url`)
- `safe_write()` with `.part` → rename
- Produces `data/manifests/nsm_manifest.jsonl` (one record per downloaded document)
- Respects `config.toml` delays and circuit breaker
- Logs to JSONL structured log
- Skips already-downloaded files (idempotent)

### CLI Structure

```
corpus discover nsm [--run-id ID] [--output PATH]
corpus download nsm [--run-id ID] [--discovery-file PATH] [--output-dir PATH] [--manifest-dir PATH] [--dry-run]
```

`discover` is a new CLI group (peer to `download`). `download nsm` reads from the discovery file instead of querying the API directly.

### File Structure

```
src/corpus/sources/nsm.py          # Refactor: add discovery functions, update download to read discovery file
tests/test_nsm.py                  # Update tests for new discovery + download flow
src/corpus/cli.py                  # Add discover group, update download nsm
```

### What stays the same

- `parse_hits` — converts API hits to manifest records
- `resolve_pdf_url` — two-hop HTML→PDF resolution
- `download_nsm_document` — single-doc download with safe_write, PDF validation, hash
- `_load_config` — config.toml loading
- All existing test infrastructure and fixtures

### What changes

- `query_nsm_api` — now accepts optional criteria (name pattern or LEI) instead of always querying unfiltered
- `run_nsm_download` — reads from discovery JSONL instead of querying API directly
- New: `discover_nsm` — orchestrates all discovery queries, deduplicates, writes discovery JSONL
- New: `build_sovereign_queries` — reads reference CSV + hardcoded patterns, returns list of (label, criteria) tuples
- CLI: new `discover` group with `nsm` command; `download nsm` updated to read discovery file

### Config

Existing `config.toml [nsm]` section applies to download phase. Discovery uses the same HTTP client config (retries, backoff, timeout) but with `delay_api` between queries only (no `delay_download` since no PDFs are fetched).

### Reference CSV format

```
country,issuer_types,filing_count,name_variant_count,name_variants,leis,doc_types,earliest,latest
```

LEIs column: semicolon-separated, some empty. Each LEI is 20-char alphanumeric. Filter to valid LEIs only.
