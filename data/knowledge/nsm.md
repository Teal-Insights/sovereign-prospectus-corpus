# Knowledge Base: FCA National Storage Mechanism (NSM)

Last updated: 2026-03-24

## API Endpoint

- **URL:** `POST https://api.data.fca.org.uk/search?index=fca-nsm-searchdata`
- **Auth:** None required
- **Source:** Reverse-engineered from browser network inspector (Phase 0, March 23 2026)

## Rate Limits

- **Published limits:** None found in public documentation
- **Related API (FS Register):** 10 req/10 sec (source: FCA website search results)
- **Empirical (Phase 0):** 156 queries without any throttling (source: experience, March 23 2026)
- **Empirical (Phase 1):** [TO BE UPDATED after overnight run]
- **robots.txt:** `search=yes, ai-train=no`. AI crawlers (ClaudeBot, GPTBot) explicitly blocked. (source: https://data.fca.org.uk/robots.txt, fetched March 24 2026)

## Terms of Use

- `NSM_Terms_of_Use.pdf` and `NSM_General_AUP.pdf` exist at data.fca.org.uk/artefacts/
- AUP prohibits: unauthorized access, DDoS, malicious content
- No explicit prohibition on programmatic research access found
- Source: web search + direct URL check, March 24 2026

## Download Mechanics

- ~44% of links resolve directly to PDF
- ~55% of links resolve to HTML metadata page requiring two-hop resolution
- URL pattern: `https://data.fca.org.uk/artefacts/{download_link}`
- PDF validation: check `b"%PDF"` in first 4 bytes
- Source: experience from Phase 0-1 downloads, March 23-24 2026

## Two-Hop Resolution

- HTML pages contain a link to the actual PDF (or sometimes another HTML page)
- BeautifulSoup parses the HTML to find PDF link
- Known failure mode: some HTML pages have different templates than expected
- Expected failure rate at scale: 5-10% (source: council of experts consensus)
- Source: experience + council assessment, March 24 2026

## Document Type Codes

| Code | Description | Prospectus-relevant? |
|------|-------------|---------------------|
| PDI | Publication of a Prospectus | Yes |
| FCA01 | Base Prospectus | Yes |
| PSP | Publication of a Supplementary Prospectus | Yes |
| PFT | Final Terms | Yes (context for base prospectus) |
| IOD | Issue of Debt | No (gilts, operational) |
| NOT | Notice | No |
| NRA | Notification re. an Acquisition or Disposal | No |
| MSCL | Miscellaneous | Sometimes |
| RTE | Result of Tender Offer | No |
| IDE | Inside Information | No |

Source: NSM API field analysis, March 23 2026

## Pagination

- `from`/`size` parameters work up to 10,000+
- For deeper results: use `search_after` + Point in Time (PIT)
- Source: Elasticsearch documentation + empirical testing

## Known Issues

- SQLite does NOT work on Google Drive File Stream (journal file I/O errors)
- Some NSM "PDFs" are actually HTML, password-protected, or truncated (expect 5-15% quarantine rate)
- Source: experience, March 24 2026

## Overnight Run Learnings (March 24-25)

[TO BE UPDATED after overnight run with empirical data:
- Actual success/failure rates
- Actual throttling behavior
- Two-hop resolution failure patterns
- Download time distribution
- Any new HTML page templates encountered]
