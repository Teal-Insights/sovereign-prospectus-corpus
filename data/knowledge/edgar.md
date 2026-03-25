# Knowledge Base: SEC EDGAR

Last updated: 2026-03-24

## Rate Limits

- **Published limit:** 10 requests per second per IP (source: SEC EDGAR access documentation)
- **Penalty:** 10-minute IP block if exceeded. Continued violation extends block. (source: SEC docs)
- **Recovery:** Automatic after 10 min below threshold (source: SEC docs)
- **Recommended safe rate:** 4-5 req/sec (50% headroom) (source: council of experts consensus)

## User-Agent Requirement

- **Mandatory format:** `"Company Name email@example.com"` (source: SEC EDGAR API docs)
- **Our value:** `"Teal Insights lte@tealinsights.com"`
- SEC uses this to contact developers about issues

## Sovereign Filer Discovery

- SIC code 8888 = "Foreign Governments" (source: SEC SIC code list)
- Known CIKs: Mexico (101368), Brazil (205317) (source: EDGAR search, March 24 2026)
- `company_tickers.json` at sec.gov has ticker/CIK/name associations
- `submission.zip` (~2GB) contains all filing metadata (updated nightly)
- Per-filer submissions: `https://data.sec.gov/submissions/CIK{padded_10_digits}.json`

## Form Types for Sovereign Prospectuses

| Form | Description | Priority |
|------|-------------|----------|
| 424B2 | Prospectus supplement (shelf) | PRIMARY |
| 424B5 | Prospectus supplement (final) | PRIMARY |
| 18-K | Annual report (foreign govt) | SECONDARY |
| 18-K/A | Amendment to 18-K | SECONDARY |
| FWP | Free writing prospectus | TERTIARY |

Source: SEC EDGAR form types documentation + council assessment

## Critical Insight: HTML-First Format

- **EDGAR sovereign prospectuses are frequently HTML, not PDF**
- Recent examples: Mexico 424B5, Colombia 424B5, Indonesia 424B5 — primary document is .htm
- PyMuPDF cannot parse HTML → need BeautifulSoup fallback for text extraction
- Page numbers not available for HTML documents → set page_number = NULL
- Source: ChatGPT 5.4 Pro council assessment with SEC filing examples, March 24 2026

## Filing Package Structure

- Each EDGAR filing is a package: cover letter, primary document, exhibits
- For 424B2/424B5: primary document is usually first in list, `Document Type` matches form
- For 18-K: substantive content in EX-99.* exhibits, not the wrapper document
- Need an `artifacts` table to model one-to-many relationship
- Source: council assessment + SEC filing examples, March 24 2026

## Not Yet Tested

[TO BE UPDATED after EDGAR implementation:
- Actual number of sovereign issuers discoverable via SIC 8888
- Actual filing counts per major issuer
- HTML vs PDF ratio for sovereign filings
- Rate limiting behavior in practice
- Submission.zip parsing workflow]
