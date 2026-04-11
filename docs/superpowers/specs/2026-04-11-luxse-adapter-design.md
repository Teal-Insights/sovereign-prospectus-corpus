# LuxSE Source Adapter Design

**Date:** 2026-04-11
**Sprint:** Spring Meetings (deadline 2026-04-13)
**Time-box:** 90-min soft checkpoint (PDF downloaded), 4-hr hard cliff

## Discovery: Validated API

LuxSE runs on Sitecore JSS with an Apollo GraphQL gateway at
`graphqlaz.luxse.com/v1/graphql`. No authentication required for the
document search endpoint.

**Discovery query:** `luxseDocumentsSearch` with sovereign name patterns.
Returns document metadata including encrypted `downloadUrl` tokens.

```graphql
query {
  luxseDocumentsSearch(
    searchTerm: "Republic of"
    size: 100
    page: 0
    sort: "publishDate"
  ) {
    totalHits
    documents {
      id name description publishDate downloadUrl
      documentTypeCode documentPublicTypeCode
      categories complement
    }
  }
}
```

**Search terms** (matching NSM sovereign query patterns):
- "Republic of", "Kingdom of", "Government of"
- "State of", "Emirate of", "Sultanate of"

**Confirmed coverage:** 5,358+ documents for "Republic" alone. Includes
Venezuela, Italy, Turkey, and other sovereign issuers. Documents have ISINs
in the `complement` field.

## Download: Validated Pipeline

Download URL = `https://dl.luxse.com/dl?v={url_encoded_downloadUrl_token}`

Confirmed: 200 OK, `application/pdf`, `%PDF-` magic bytes, 567KB test file.

## Adapter Design

### Two-phase pattern (matches NSM/EDGAR)

1. **`discover_luxse()`** - Query GraphQL with each sovereign name pattern.
   Deduplicate by document `id`. Write discovery JSONL.
2. **`run_luxse_download()`** - Read discovery JSONL, download PDFs via
   dl.luxse.com, validate `%PDF` magic bytes, write manifest JSONL.

### Storage keys

`luxse__{document_id}` (e.g., `luxse__67022`). Document IDs are stable
numeric identifiers from the LuxSE database.

### Discovery JSONL record

```json
{
  "source": "luxse",
  "native_id": "67022",
  "storage_key": "luxse__67022",
  "title": "Prospectus",
  "issuer_name": "VENEZUELA (BOLIVARIAN REPUBLIC OF)",
  "doc_type": "D010",
  "publication_date": "1990-12-15",
  "download_token": "2OSHWb3EcT2b+mRXjEyOQ...",
  "download_url": "https://dl.luxse.com/dl?v=...",
  "file_ext": "pdf",
  "source_metadata": {
    "complement": "VENEZUELA... - XS0029456067...",
    "categories": ["LuxSE"],
    "document_type_code": "D010",
    "document_public_type_code": "D010"
  }
}
```

### Manifest enrichment (same as NSM/EDGAR)

Adds `file_path`, `file_hash` (SHA256), `file_size_bytes`.

### CLI commands

- `corpus discover luxse` - runs discovery
- `corpus download luxse` - reads discovery file, downloads PDFs

### Config (`config.toml`)

```toml
[luxse]
delay = 1.0
max_retries = 3
timeout = 60
graphql_endpoint = "https://graphqlaz.luxse.com/v1/graphql"
download_base_url = "https://dl.luxse.com/dl?v="

[luxse.circuit_breaker]
total_failures_abort = 10
```

### Issuer name extraction

The `complement` field contains the issuer name and ISIN:
`"VENEZUELA (BOLIVARIAN REPUBLIC OF) - XS0029456067 Venezuela 6,75% 90-20"`

Extract issuer name by splitting on ` - ` and taking the first part.

## Risks

- **Rate limiting:** dl.luxse.com has a `/download-limit-reached` page.
  Mitigation: 1s delay between downloads, respect 429s.
- **Token expiry:** download tokens may expire. Mitigation: download
  promptly after discovery; if a token fails, re-discover.
- **GraphQL schema changes:** undocumented API. Mitigation: specific error
  handling for schema changes.
