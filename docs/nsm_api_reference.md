# FCA National Storage Mechanism (NSM) API Reference

## Overview

The FCA National Storage Mechanism (NSM) provides public access to regulatory filings for securities listed on UK exchanges. The search interface at https://data.fca.org.uk/#/nsm/nationalstoragemechanism is a single-page application backed by an Elasticsearch API that can be queried directly.

This document describes the API endpoint, request/response formats, and usage patterns discovered through reverse engineering.

## API Endpoint

**URL:** `https://api.data.fca.org.uk/search?index=fca-nsm-searchdata`

**Method:** POST

**Content-Type:** `application/json`

**Authentication:** None required (publicly accessible)

**Backend:** Elasticsearch

## Request Format

### Basic Structure

```json
{
  "from": 0,
  "size": 50,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {
    "criteria": [],
    "dateCriteria": []
  }
}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from` | integer | No | Pagination offset (0-based). Default: 0 |
| `size` | integer | No | Number of results per page. Tested up to 10,000. UI default: 50 |
| `sort` | string | No | Sort field. Common: `submitted_date`, `publication_date`. Default: `submitted_date` |
| `sortorder` | string | No | Sort direction: `asc` or `desc`. Default: `desc` |
| `criteriaObj` | object | Yes | Container for filter criteria |

### Criteria Object

The `criteriaObj` contains two arrays:

#### `criteria` Array

Filters for document metadata. Each criterion has a `name` and `value`.

**Organisation Search (company_lei)**
```json
{
  "name": "company_lei",
  "value": ["<org_name>", "<lei>", "<org_type_1>", "<org_type_2>"]
}
```

- Array format: `[organisation_name, LEI, search_scope_1, search_scope_2]`
- `organisation_name` (string): Fuzzy/partial match search. Set to `""` to search by LEI only.
- `lei` (string): Exact LEI match. Set to `""` to search by name only.
- `search_scope_1` and `search_scope_2` (string): One or both of:
  - `"disclose_org"` — Search organisations that filed the document
  - `"related_org"` — Search related organisations linked to the filing
- Examples:
  - By name: `["Republic of Kenya", "", "disclose_org", "related_org"]`
  - By LEI: `["", "549300VVURQQYU45PR87", "disclose_org", ""]`
  - Both: `["Republic of Kenya", "549300VVURQQYU45PR87", "disclose_org", "related_org"]`

**Latest Version Filter (latest_flag)**
```json
{
  "name": "latest_flag",
  "value": "Y"
}
```
Always include this to filter to the latest version of each filing. Omit to see all versions including superseded ones.

**Document Type Filter (headlineCategory)**
```json
{
  "name": "headlineCategory",
  "value": "<type_code>"
}
```
Filter by document type using type codes (PDI, PSP, FCA01, PFT, NOT, NRA, MSCL, RTE, IDE, PSM). **Note:** Testing showed these codes return 0 results; the UI may use different values. Further investigation needed.

**Other Criteria Names**

| Name | Value Format | Description |
|------|--------------|-------------|
| `document_text` | `["<search_text>", "<match_type>"]` | Search document metadata/description. Max 5 words. Match type: `"exact"`, `"all"`, or `"any"`. Does NOT search PDF content. |
| `document_description` | string | Search the headline/description field |
| `sourceList` | string | Filter by source: RNS, FCA, DirectUpload, GNW, BWI, PRN, EQS, MFN |
| `esef_tag` | string | Filter by ESEF type (rarely populated) |

#### `dateCriteria` Array

Filters for date ranges. Each criterion has a `name` and `value` object.

```json
{
  "name": "<date_field>",
  "value": {"from": "2026-03-01T00:00:00Z", "to": "2026-03-23T23:59:00Z"}
}
```

| Name | Description |
|------|-------------|
| `submitted_date` | When the filing was submitted to NSM |
| `publication_date` | When the filing was published |
| `document_date` | Date of the document itself |
| `last_updated_date` | Last update timestamp |

- Use ISO 8601 format: `"YYYY-MM-DDTHH:MM:SSZ"`
- Use `null` for unbounded bounds: `{"from": null, "to": "2026-03-23T23:59:00Z"}`

### Example Requests

**Search by sovereign name (latest filings)**
```json
{
  "from": 0,
  "size": 50,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {
    "criteria": [
      {"name": "company_lei", "value": ["Republic of Kenya", "", "disclose_org", "related_org"]},
      {"name": "latest_flag", "value": "Y"}
    ]
  }
}
```

**Search by LEI (most reliable for sovereigns)**
```json
{
  "from": 0,
  "size": 500,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {
    "criteria": [
      {"name": "company_lei", "value": ["", "549300VVURQQYU45PR87", "disclose_org", ""]},
      {"name": "latest_flag", "value": "Y"}
    ]
  }
}
```

**Search with date range**
```json
{
  "from": 0,
  "size": 100,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {
    "criteria": [
      {"name": "latest_flag", "value": "Y"}
    ],
    "dateCriteria": [
      {"name": "submitted_date", "value": {"from": "2026-03-01T00:00:00Z", "to": "2026-03-23T23:59:00Z"}}
    ]
  }
}
```

**Broad sovereign search with pagination**
```json
{
  "from": 0,
  "size": 10000,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {
    "criteria": [
      {"name": "company_lei", "value": ["Republic of", "", "disclose_org", ""]},
      {"name": "latest_flag", "value": "Y"}
    ]
  }
}
```

## Response Format

The API returns Elasticsearch query results in standard format:

```json
{
  "took": 11,
  "timed_out": false,
  "_shards": {
    "failed": 0,
    "skipped": 0,
    "successful": 4,
    "total": 4
  },
  "hits": {
    "total": {"relation": "eq", "value": 6},
    "hits": [
      {
        "_index": "fca-nsm-searchdata",
        "_id": "<uuid>",
        "_source": {
          "submitted_date": "2026-02-26T15:33:25Z",
          "publication_date": "2026-02-26T15:22:22Z",
          "company": "REPUBLIC OF KENYA",
          "lei": "549300VVURQQYU45PR87",
          "type_code": "PDI",
          "headline": "Publication of an Offering Circular",
          "download_link": "NSM/RNS/5e419992-ba5d-48db-80b0-21c6bf576821.html",
          "disclosure_id": "5e419992-ba5d-48db-80b0-21c6bf576821",
          "latest_flag": "Y"
        }
      }
    ]
  }
}
```

### Response Metadata

| Field | Description |
|-------|-------------|
| `took` | Query execution time in milliseconds |
| `timed_out` | Whether the query timed out |
| `_shards` | Shard statistics (failed, skipped, successful, total) |
| `hits.total.value` | Total number of matching documents |
| `hits.total.relation` | Whether count is exact (`eq`) or lower bound (`gte`) |

## Response Fields

Each result in `hits.hits[].\_source` contains the following fields:

### Date Fields

| Field | Type | Description |
|-------|------|-------------|
| `submitted_date` | ISO datetime | When the filing was submitted to NSM |
| `publication_date` | ISO datetime | When the filing was published |
| `document_date` | ISO datetime | Date of the document itself |
| `last_updated_date` | ISO datetime | Last update timestamp |

### Organization Fields

| Field | Type | Description |
|-------|------|-------------|
| `company` | string | Name of the disclosing organisation |
| `lei` | string | Legal Entity Identifier of the disclosing organisation |
| `related_org` | array | Related organisations (array of `{lei: string, company: string}` objects) |

### Document Type Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Human-readable document type (e.g., "Publication of a Prospectus") |
| `type_code` | string | Machine-readable type code (PDI, PSP, FCA01, PFT, NOT, NRA, MSCL, RTE, IDE, PSM) |
| `headline` | string | Filing headline or description |
| `classifications` | string | Regulatory classification text |
| `classifications_code` | string | Classification code (e.g., "3.1", "1.1", "0.0") |

### Filing Metadata

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Source system (RNS, FCA, DirectUpload, GNW, BWI, PRN, EQS, MFN) |
| `disclosure_id` | string | Unique filing identifier (UUID or NSM ID) |
| `seq_id` | string | Sequence ID (typically same as disclosure_id) |
| `hist_seq` | string | Version number within filing history |
| `latest_flag` | string | Whether this is the latest version ("Y" or "N") |
| `lei_remediation_flag` | string | LEI remediation status ("Y" or "N") |
| `tag_esef` | string | ESEF tag (usually empty) |

### Download Links

| Field | Type | Description |
|-------|------|-------------|
| `download_link` | string | Relative path to the document (see Download Links section) |

## Document Types

### Type Codes

| Code | Human-Readable Type | Description |
|------|---------------------|-------------|
| `PDI` | Publication of a Prospectus | Full prospectus or offering circular |
| `PSP` | Publication of a Supplementary Prospectus | Supplements to existing prospectuses |
| `FCA01` | Base Prospectus | Base prospectus for EMTN/debt programmes |
| `PFT` | Final Terms | Pricing supplements / final terms for individual tranches |
| `NOT` | Official List Notice | FCA administrative notices |
| `NRA` | Non Regulatory Announcement | Non-regulatory disclosures |
| `MSCL` | Miscellaneous | Miscellaneous filings |
| `RTE` | Result of Tender Offer | Results of debt tender offers |
| `IDE` | Issue of Debt | Debt issuance announcements |
| `PSM` | Prospectus Summary | Summary section of a prospectus |

## Download Links

The `download_link` field contains a relative path. Construct the full URL as:

```
https://data.fca.org.uk/artefacts/{download_link}
```

### Link Types

**Direct PDF** (~44% of filings)
- End with `.pdf`
- Example: `https://data.fca.org.uk/artefacts/NSM/Portal/NI-000131055/NI-000131055.pdf`
- Can be downloaded directly

**HTML Metadata Page** (~55% of filings)
- End with `.html`
- Example: `https://data.fca.org.uk/artefacts/NSM/RNS/5e419992-ba5d-48db-80b0-21c6bf576821.html`
- Requires a second HTTP request to extract the actual PDF link from the HTML content

### URL Path Prefixes (by Source)

| Prefix | Source |
|--------|--------|
| `NSM/RNS/` | Regulatory News Services |
| `NSM/Portal/` or `NSM/FCA/` | FCA direct / Portal uploads |
| `NSM/DirectUpload/` | Direct uploads by issuers |
| `NSM/GNW/` | GlobeNewswire |
| `NSM/BWI/` | Business Wire |
| `NSM/PRN/` | PR Newswire |
| `NSM/EQS/` | EQS Group |
| `NSM/MFN/` | Modular Finance |

## Pagination

Use the `from` and `size` parameters to paginate through large result sets:

```json
{
  "from": 0,
  "size": 1000,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {...}
}
```

To retrieve the next page:
```json
{
  "from": 1000,
  "size": 1000,
  "sort": "submitted_date",
  "sortorder": "desc",
  "criteriaObj": {...}
}
```

**Notes:**
- The `size` parameter has been tested up to 10,000 and works reliably
- No observed rate limiting with sequential queries (156+ tested)
- Add small delays between batch queries as a courtesy
- The web UI's CSV export caps at 4,000 rows; the API has no such limitation

## Known Limitations

### Search Behavior

1. **Organisation name search is fuzzy/partial match.** Searching "Kenya" returns any filing where "Kenya" appears in the org name. This produces noise for generic country names (Egypt, Georgia, Turkey) that match corporate issuers.

2. **Name inconsistency is pervasive.** The same sovereign issuer appears under multiple name variants:
   - Kenya: "REPUBLIC OF KENYA", "Kenya (The Republic of)", "Republic of Kenya (The)", "THE REPUBLIC OF KENYA"
   - Nigeria: "THE FEDERAL REPUBLIC OF NIGERIA", "Nigeria (Federal Republic of) (The)", "Federal Republic Of Nigeria (The)", "The Federal Republic of Nigeria"
   - Saudi Arabia: "Kingdom of Saudi Arabia (The)", "Kingdom of Saudi Arabia", "The Kingdom of Saudi Arabia acting through the Ministry of Finance"

3. **LEI search is more comprehensive than name search.** For Kenya, name search returned 6 results while LEI search returned 19 results due to name variants.

### Content Search

4. **The `document_text` search does NOT search inside PDF content.** It searches document metadata and descriptions only. Full-text search of prospectus content requires downloading and processing PDFs separately.

5. **The `headlineCategory` filter may not work as expected.** Testing showed type codes returned 0 results; the UI may use different values internally.

### Web UI Differences

6. **CSV export limitation.** The FCA web UI's "Export as CSV" button caps at 4,000 rows. The API has no such limitation.

## Known Sovereign LEIs

These LEIs have been discovered through NSM research (52% LEI coverage on sovereign filings):

| Country | LEI |
|---------|-----|
| Albania | 254900EDM43U3SGRND29 |
| Abu Dhabi (UAE) | 213800FER4348CINTA77 |
| Iceland | 549300K5GD3JPA2LLG98 |
| Jordan | 5493000JZ4MYPVMBVN50 |
| Kazakhstan | 5493007OEK8EF02UO833 |
| Kenya | 549300VVURQQYU45PR87 |
| Kuwait | 549300FSC1YD0D9XX589 |
| Nigeria | 549300GSBZD84TNEQ285 |
| Oman Sovereign Sukuk | 549300KM6RUZQLK8LU36 |

**Note:** Additional LEIs should be sourced from GLEIF for issuers without LEIs in the NSM data.

## Implementation Tips

### For Sovereign Bond Research

**Use LEI for reliability:** LEI-based searches return more comprehensive results than name-based searches.

```python
# Python pseudocode
def search_sovereign_by_lei(lei):
    payload = {
        "from": 0,
        "size": 10000,
        "sort": "submitted_date",
        "sortorder": "desc",
        "criteriaObj": {
            "criteria": [
                {"name": "company_lei", "value": ["", lei, "disclose_org", ""]},
                {"name": "latest_flag", "value": "Y"}
            ]
        }
    }
    response = requests.post(
        "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata",
        json=payload
    )
    return response.json()
```

### For Monitoring New Filings

Filter by submitted date to find recent filings:

```python
def monitor_recent_filings(days=7):
    from datetime import datetime, timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    payload = {
        "from": 0,
        "size": 1000,
        "criteriaObj": {
            "criteria": [
                {"name": "latest_flag", "value": "Y"}
            ],
            "dateCriteria": [
                {
                    "name": "submitted_date",
                    "value": {"from": cutoff_iso, "to": None}
                }
            ]
        }
    }
    # Execute query...
```

### Handling HTML Download Links

For documents with `.html` download links, extract the PDF URL from the HTML:

```python
def get_pdf_url(html_url):
    response = requests.get(html_url)
    # Look for <a> tags or form submissions pointing to .pdf files
    # Construct full URL using https://data.fca.org.uk/artefacts/ as base
    # Return the extracted PDF URL
```

## API Behavior Notes

1. The API accepts very large result sets (tested up to 10,000 per request without issues)
2. No authentication is required; the API is fully public
3. Rate limiting appears minimal but should be respected with small delays between batch requests
4. Responses follow standard Elasticsearch JSON format
5. The `_id` field is a UUID representing the filing
6. The related_org field returns structured array data (unlike CSV export which concatenates with semicolons)
