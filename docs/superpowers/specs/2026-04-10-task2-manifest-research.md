# Task 2 (Provenance URLs) — Manifest Structure Research

**Created:** 2026-04-10
**Task:** Sprint Task 2 — add `source_page_url` and `source_page_kind` to documents table
**Issue:** #52
**Sprint spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md` lines 183-227

This is the prep research for Task 2. It was done during the Task 1 deploy-wait
time and is saved here so the next session can use it directly instead of
re-running exploration agents.

## Schema additions needed

Two columns on `documents` table in `sql/001_corpus.sql`:

```sql
source_page_url VARCHAR,        -- URL to human-facing filing page
source_page_kind VARCHAR,       -- filing_index | artifact_html | artifact_pdf | search_page | none
```

## Ingest pipeline changes

**File: `src/corpus/db/ingest.py`**

Add `source_page_url` and `source_page_kind` to `_DOCUMENT_COLUMNS` frozenset
(currently line 25-46). Without this, the ingest code will merge these fields
into the `source_metadata` JSON blob instead of the top-level columns.

## Current manifest fields, per source

### EDGAR (`data/manifests/edgar_manifest.jsonl`)

Sample record shape:
```json
{
  "source": "edgar",
  "native_id": "0001193125-20-188103",
  "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/d935251d424b5.htm",
  "source_metadata": {
    "cik": "0000914021",
    "accession_number": "0001193125-20-188103",
    "form_type": "424B5",
    "primary_document": "d935251d424b5.htm"
  }
}
```

**Resolver logic for EDGAR:**
- Filing index URL format:
  `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{accession_with_dashes}-index.htm`
- Strip leading zeros from `cik` → `cik_int` (`0000914021` → `914021`)
- Strip dashes from `accession_number` → `accession_no_dashes`
- Keep `accession_number` as-is for the filename portion
- Example: `https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm`
- Kind: `"filing_index"`
- Source code reference: `src/corpus/sources/edgar.py` lines 28-29, 111-117

### NSM (`data/manifests/nsm_manifest.jsonl`)

Sample record shape:
```json
{
  "source": "nsm",
  "native_id": "d5c84201-05ec-4e43-b333-fc8dcbc6ab24",
  "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/d5c84201-05ec-4e43-b333-fc8dcbc6ab24.html",
  "source_metadata": {
    "nsm_source": "RNS",
    "type_name": "Final Terms",
    "seq_id": "d5c84201-05ec-4e43-b333-fc8dcbc6ab24"
  }
}
```

**Resolver logic for NSM:**
- `download_url` IS already the artefact URL (HTML or PDF depending on filing)
- Use `download_url` directly as `source_page_url`
- Determine kind from file extension: `.html` → `artifact_html`, `.pdf` → `artifact_pdf`
- Fallback if artefact URL is missing or unreliable: use `source_page_kind: "search_page"` with URL `https://data.fca.org.uk/search/`
- Source code reference: `src/corpus/sources/nsm.py` lines 191-224
- **Caveat from sprint spec:** FCA site may be a SPA; deep links from `native_id` alone may not work reliably. If fallback needed, document in code.

### PDIP (`data/manifests/pdip_manifest.jsonl`)

Sample record shape:
```json
{
  "source": "pdip",
  "native_id": "VEN85",
  "download_url": "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85",
  "source_metadata": {
    "tag_status": "Annotated",
    "country": "Venezuela",
    "instrument_type": "Loan"
  }
}
```

**Resolver logic for PDIP:**
- No per-document deep links exist
- `source_page_url`: `https://publicdebtispublic.mdi.georgetown.edu/search/`
- `source_page_kind`: `"search_page"`
- **Must document this limitation in code comments.** This is not a bug in the
  adapter — it's how PDIP is structured.
- Source code reference: `src/corpus/sources/pdip.py` lines 102-104, 113-120, 282-304

## Implementation steps (per sprint spec)

1. Add fields to JSONL manifest schema
2. Write resolver functions per source (unit tested)
3. Backfill existing manifests with the new fields
4. Rebuild DuckDB from updated manifests
5. Manually verify 3 random URLs per source resolve correctly

## Completion criteria (from sprint spec)

- [ ] Both columns exist in schema DDL
- [ ] JSONL manifests include `source_page_url` and `source_page_kind`
- [ ] Resolver functions exist per source with unit tests
- [ ] EDGAR URLs use correct accession number format (verified manually)
- [ ] NSM URLs use best available link (artefact URL or search fallback)
- [ ] PDIP documented as `search_page` only
- [ ] DB rebuild from manifests works cleanly
- [ ] 3 URLs per source verified to resolve
- [ ] Pre-commit checks pass
