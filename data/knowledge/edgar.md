# Knowledge Base: SEC EDGAR

Last updated: 2026-03-24 (empirical research session)

## Rate Limits

- **Published limit:** 10 requests per second per IP (source: SEC EDGAR access documentation)
- **Penalty:** 10-minute IP block if exceeded. Continued violation extends block. (source: SEC docs)
- **Recovery:** Automatic after 10 min below threshold (source: SEC docs)
- **Recommended safe rate:** 4-5 req/sec (50% headroom) (source: council of experts consensus)
- **Empirical observation:** 27 submissions.json fetches at 0.25s spacing completed without issues (source: this session, March 24 2026)

## User-Agent Requirement

- **Mandatory format:** `"Company Name email@example.com"` (source: SEC EDGAR API docs)
- **Our value:** `"Teal Insights lte@tealinsights.com"`
- SEC uses this to contact developers about issues

## Sovereign Filer Discovery

### SIC Code 8888

- SIC code 8888 = "Foreign Governments & Certain International Organizations" (source: SEC SIC code list)
- **74 total entities** registered under SIC 8888 (source: browse-edgar query, March 24 2026)
- Breakdown by category:
  - **27 sovereign nations** (actual government issuers)
  - **20 DFIs / MDBs / agencies** (KfW, EIB, ADB, Korea Development Bank, etc.)
  - **9 sub-sovereign** (Canadian provinces, City of Naples, Region of Lombardy)
  - **11 unclassified / corporate** (some misclassified entities like Johnson Matthey PLC)

### Discovery Method

- Primary: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC=8888&count=100`
- Returns HTML table with CIK, company name, state
- One-time scrape, no pagination needed (all 74 fit on one page)
- Source: empirical query, March 24 2026

### Sovereign Nations on EDGAR (27 filers, 22 with prospectus filings)

| Country | CIK | Prospectus Filings | Annual Reports | Date Range |
|---------|-----|-------------------|----------------|------------|
| Argentina | 0000914021 | 40 | 38 | 2004-2025 |
| Belize | 0001179453 | 1 | 0 | 2002 |
| Brazil | 0000205317 | 220 | 117 | 2002-2026 |
| Canada | 0000230098 | 62 | 123 | 2002-2025 |
| Chile | 0000019957 | 186 | 75 | 2002-2026 |
| Colombia | 0000917142 | 246 | 89 | 2002-2026 |
| Finland | 0000035946 | 3 | 0 | 2002-2006 |
| Greece | 0000931106 | 0 | 0 | 2011-2018 |
| Hungary | 0000889414 | 30 | 31 | 2004-2022 |
| Indonesia | 0001719614 | 92 | 44 | 2017-2026 |
| Israel | 0000052749 | 877 | 63 | 2006-2026 |
| Italy | 0000052782 | 43 | 76 | 2002-2024 |
| Jamaica | 0001163395 / 0000053078 | 44 | 57 | 2002-2025 |
| Japan | 0000837056 | 0 | 24 | 2003-2025 |
| Korea | 0000873465 | 55 | 0 | 2003-2026 |
| Mexico | 0000101368 | 266 | 173 | 2002-2026 |
| New Zealand | 0000216105 | 0 | 27 | 2002-2011 |
| Nigeria | 0001627521 | 2 | 0 | 2017 |
| Panama | 0000076027 | 126 | 84 | 2002-2026 |
| Peru | 0000077694 | 85 | 38 | 2002-2025 |
| Philippines | 0001030717 | 171 | 41 | 2002-2026 |
| Portugal | 0000911076 | 0 | 1 | 2002-2005 |
| South Africa | 0000932419 | 68 | 69 | 2002-2022 |
| Sweden | 0000225913 | 0 | 15 | 2002-2013 |
| Turkey | 0000869687 | 261 | 133 | 2002-2026 |
| Uruguay | 0000102385 | 150 | 90 | 2002-2025 |

**Total: 3,028 prospectus-type filings across 22 sovereign nations.**

Source: submissions.json queries for each CIK, March 24 2026. Full data in `data/raw/edgar_sovereign_census.json`.

### Jamaica Note

Jamaica has TWO CIKs: 0001163395 ("GOVERNMENT OF JAMICA" [sic]) with 43 prospectus filings, and 0000053078 ("JAMAICA GOVERNMENT OF") with 1 prospectus filing. Both should be queried. The misspelling is in SEC's records.

### Overlap with NSM Priority Countries

Countries appearing on BOTH NSM and EDGAR:
- **Nigeria** (Tier 2): 2 EDGAR prospectus filings + NSM filings
- **Hungary** (Tier 4): 30 EDGAR + NSM filings
- **Israel** (Tier 4): 877 EDGAR + 148 NSM filings
- **Finland** (Tier 4): 3 EDGAR + NSM filings
- **Sweden** (Tier 4): 0 EDGAR prospectus + NSM filings
- **Canada** (Tier 4): 62 EDGAR + NSM filings

Countries on EDGAR but NOT our NSM priority list (new coverage):
- Argentina (40), Brazil (220), Chile (186), Colombia (246), Indonesia (92),
  Italy (43), Jamaica (44), Korea (55), Mexico (266), Panama (126),
  Peru (85), Philippines (171), South Africa (68), Turkey (261), Uruguay (150)

## Submissions API (Bulk Metadata)

### Endpoint

`https://data.sec.gov/submissions/CIK{padded_10_digits}.json`

### Key Fields in `filings.recent`

| Field | Description | Example |
|-------|-------------|---------|
| `form` | Filing form type | "424B2", "424B5", "18-K" |
| `filingDate` | Date filed | "2026-01-14" |
| `accessionNumber` | Unique filing ID | "0001193125-26-013087" |
| `primaryDocument` | Main document filename | "d10056d424b5.htm" |
| `primaryDocDescription` | Description | "PROSPECTUS SUPPLEMENT" |

### Pagination

- `filings.recent` contains up to ~1000 most recent filings
- For filers with more, `filings.files` lists additional JSON files
- Example: Israel has 1001 recent + 298 in `CIK0000052749-submissions-001.json`
- Additional files at: `https://data.sec.gov/submissions/{filename}`
- Source: Israel submissions query, March 24 2026

## Form Types for Sovereign Prospectuses

| Form | Description | Count (across all sovereigns) | Priority |
|------|-------------|-------------------------------|----------|
| 424B2 | Prospectus supplement (shelf) | ~1200 | PRIMARY |
| 424B5 | Prospectus supplement (final) | ~800 | PRIMARY |
| 424B3 | Prospectus (often amendments) | ~200 | PRIMARY |
| 424B4 | Prospectus (final, non-shelf) | ~50 | PRIMARY |
| FWP | Free writing prospectus | ~500 | SECONDARY |
| 18-K | Annual report (foreign govt) | ~800 | SECONDARY |
| 18-K/A | Amendment to 18-K | ~300 | SECONDARY |
| S-B | Schedule B registration | ~20 | TERTIARY |

Source: form type distribution from submissions queries, March 24 2026

### Indonesia-Specific Forms

Indonesia uses 424B5 (20 filings) and 424B3 (20 filings) as primary prospectus types. Also 51 FWPs. Source: Indonesia submissions query, March 24 2026.

### Nigeria-Specific Forms

Nigeria has only 14 total filings: 1 S-B registration, 1 424B4 prospectus, 1 FWP, and various correspondence. Only 2 filings are prospectus-type. Source: Nigeria submissions query, March 24 2026.

## Document Format: HTML, Not PDF

### Critical Finding: 97% HTML

Survey of 926 prospectus-type filings across 5 major sovereign filers:

| Country | HTM | PDF | Other | % HTML |
|---------|-----|-----|-------|--------|
| Mexico | 265 | 0 | 1 | 100% |
| Colombia | 239 | 0 | 7 | 97% |
| Turkey | 249 | 0 | 12 | 95% |
| Peru | 81 | 0 | 4 | 95% |
| Indonesia | 92 | 0 | 0 | 100% |
| **TOTAL** | **926** | **0** | **24** | **97%** |

**Zero PDFs in the entire sample.** The "other" category is likely XML or TXT format filings.

Source: primaryDocument extension analysis from submissions.json, March 24 2026

### HTML Structure

EDGAR filing HTML is wrapped in a `<DOCUMENT>` tag with metadata headers:
```
<DOCUMENT>
<TYPE>424B2
<SEQUENCE>1
<FILENAME>d424b2.htm
<DESCRIPTION>PROSPECTUS SUPPLEMENT
<TEXT>
<HTML>...actual content...</HTML>
</TEXT>
</DOCUMENT>
```

Text extraction approach: `BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True)`

**Tested on Colombia 424B2:** 438KB HTML → 128,724 chars / 20,805 words of clean text. All clause patterns (CAC, pari passu, events of default, governing law, sovereign immunity) matched successfully.

Source: empirical extraction test, March 24 2026

### Implications for Pipeline

1. **PyMuPDF not needed** — HTML text extraction via BeautifulSoup is simpler and more reliable
2. **No page numbers** — HTML documents don't have page breaks. Must use section-level citations instead (heading text, paragraph index, or character offset)
3. **Clause patterns work unchanged** — Same regex patterns that work on PDF-extracted text work on HTML-extracted text
4. **Smaller files** — HTM prospectuses are 300-800KB vs. 1-3MB for NSM PDFs
5. **Faster processing** — No PDF rendering/parsing overhead

## Filing Package Structure

Each EDGAR filing is a package with multiple files. Typical structure:

| File | Purpose |
|------|---------|
| `{accession}-index.html` | Filing index page |
| `{accession}-index-headers.html` | SGML header index |
| `{accession}.txt` | Complete SGML submission text |
| `d{id}d424b5.htm` | **Primary document (the prospectus)** |
| `g{id}logo.jpg` | Embedded images/logos |

**Key insight:** The `primaryDocument` field in submissions.json reliably identifies the actual prospectus within the package. No heuristic parsing needed.

Source: filing index inspection for Colombia, Israel, Brazil, March 24 2026

## URL Construction

### Document URL Pattern
```
https://www.sec.gov/Archives/edgar/data/{cik_no_padding}/{accession_no_dashes}/{primary_document}
```

Where:
- `cik_no_padding`: CIK with leading zeros stripped (e.g., "917142" not "0000917142")
- `accession_no_dashes`: Accession number with dashes removed (e.g., "000119312526013087")
- `primary_document`: Filename from submissions.json (e.g., "d10056d424b5.htm")

**Verified working** for Colombia, Mexico, and Brazil (HTTP 200 on HEAD requests). Source: URL construction test, March 24 2026.

### Filing Index URL Pattern
```
https://www.sec.gov/Archives/edgar/data/{cik_no_padding}/{accession_no_dashes}/index.json
```

Returns JSON with `directory.item[]` listing all files in the package with names and sizes.

## Pipeline Architecture Implications

### What's Different from NSM

| Aspect | NSM | EDGAR |
|--------|-----|-------|
| Document format | PDF (100%) | HTML (97%) |
| Discovery | API search per country | submissions.json per CIK |
| Rate limits | None observed | 10 req/sec enforced |
| URL resolution | Two-hop (55% need HTML parsing) | Direct (primaryDocument field) |
| Text extraction | PyMuPDF | BeautifulSoup |
| Page citations | Page numbers from PDF | Section headings / char offsets |
| Volume | ~434 prospectuses | ~3,028 prospectuses |

### Recommended Download Strategy

1. **Fetch submissions.json** for each of the 27 sovereign CIKs (27 requests)
2. **Filter** to 424B* and FWP form types
3. **Save metadata to SQLite** (reuse CorpusDB schema with source='edgar')
4. **Download HTML documents** using constructed URLs
5. **Extract text** with BeautifulSoup (no PyMuPDF)
6. **Run clause patterns** (same CLAUSE_PATTERNS dict, works on HTML text)
7. **Pace at 4 req/sec** (250ms between requests) to stay under limit

### Estimated Download Time

- 3,028 filings × 0.25s/request = ~12.6 minutes for metadata
- 3,028 filings × 0.5s/download = ~25 minutes for documents
- Total: ~40 minutes (vs. NSM overnight run)
- EDGAR is *much faster* because: direct URLs (no two-hop), smaller files (HTML), known rate limits

## Not Yet Tested

[TO BE UPDATED after EDGAR pipeline implementation:]
- Actual download throughput at scale
- Rate limiting behavior under sustained load
- 18-K annual report structure (exhibits vs. wrapper)
- Older filings in pagination files (e.g., Israel's 298 older filings)
- Text extraction quality across different HTML vintages (2002 vs. 2026)
- Edge cases: filings with XML primary documents (the "other" 3%)
