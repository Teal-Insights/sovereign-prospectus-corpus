# PublicDebtIsPublic Platform Data Extraction Assessment

## Executive Summary

The PublicDebtIsPublic (PDIP) platform at https://publicdebtispublic.mdi.georgetown.edu/ contains ~900 sovereign debt documents with ~100+ annotated contract terms. Technical reconnaissance reveals a structured, browser-based interface with static URL patterns for document access. **The platform is extractable via both direct HTTP requests and browser automation**, though the annotation data appears to be dynamically rendered in the frontend rather than available via a dedicated API.

## Platform Architecture

### Data Organization

#### Document Structure
- **Homepage URL**: `/` (shows 45+ countries, 900+ documents, 100+ annotated terms)
- **Search Interface**: `/search/`
- **Document Viewer**: `/pdf/{DOCUMENT_ID}/` (e.g., `/pdf/VEN85/`)
  - Document ID appears to be a country code + numeric ID (VEN=Venezuela, BRA=Brazil, etc.)
  - URLs support query parameters for search state: `?q=search_term&page=1&sortBy=date&sortOrder=asc&labels=...`

#### URL Pattern Analysis
```
Search Results:
  https://publicdebtispublic.mdi.georgetown.edu/search/?page=1&sortBy=date&sortOrder=asc
  https://publicdebtispublic.mdi.georgetown.edu/search/?q=Brazil&page=1&sortBy=date&sortOrder=asc
  https://publicdebtispublic.mdi.georgetown.edu/search/?page=1&sortBy=date&sortOrder=asc&labels=%5B%22Commitment_FinancialTerms%22%5D

Document View:
  https://publicdebtispublic.mdi.georgetown.edu/pdf/VEN85/?page=1&sortBy=date&sortOrder=asc&labels=%5B%22Commitment_FinancialTerms%22%5D

PDF Download:
  https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85 (HTTP endpoint)
```

### Search & Filter Interface

The search interface provides multiple filter dimensions:

**Borrower Details** (as of contract date):
- Country (dropdown list of 45+)
- Income Classification
- Entity Type
- Geographic Region
- Credit Rating (Fitch, Moody's, S&P)
- Debt Distress Level
- Debt to GDP Ratio

**Creditor Details** (as of contract date):
- Creditor Type
- Jurisdiction
- Entity Type
- Credit Rating

**Document Characteristics**:
- Instrument Type
- Bond Type
- Maturity Date
- Commitment Size

**Tagged Clauses** (100+ clause types organized hierarchically):
- Financial Terms
  - Commitment
  - Currency of Denomination and/or Payment
  - Exchange-eligible debt
  - Final Repayment/Maturity Date(s)
  - Interest
  - Fees
  - Purpose
  - Maturity
  - Use of Proceeds
- Disbursement
  - Utilization/Borrowing
- Repayment/Payments
  - Deferral of Payments
  - Maturity Extension
  - Mandatory Prepayment/Cancellation
  - Voluntary Prepayments
  - Redemption/Repurchase/Early Repayment
  - Additional Amounts
- Definitions
  - Indebtedness
- Power and Authority
- Sanctions (R & W)
- Status of Obligation/Pari Passu (R & W)
- No Security
- No Tax
- Unknown (R & W)
- Representations and Warranties
  - Authorizations and Approvals
  - Exchange Controls (R & W)
  - Commercial Acts
  - Power and Authority
  - Sanctions (R & W)
  - Status of Obligation/Pari Passu (R & W)
  - No Security
- Conditions Precedent
  - Conditions (Effectiveness)
  - Conditions (Utilization)
- Borrower Covenants/Undertakings
  - Anti-corruption/AML
  - Books and Records
  - Compliance with Authorizations
  - Limits on External Indebtedness
  - Negative Pledge
  - Lien/Permitted Lien
  - Information
  - Notification
- Events of Default and Consequences

## Annotation Data Structure

### Document View Layout

Each annotated document presents data in three main sections:

#### 1. Left Panel: PDF Viewer
- Embedded PDF document (77 pages for test document VEN85)
- Page navigation controls
- Search-within-document functionality
- Zoom controls
- Coordinates to specific pages via URL parameters

#### 2. Right Panel: Metadata & Annotations
- **Overview** section with document title, description, document type
- **Tagged Clauses** section showing annotated terms hierarchically
- **Borrower Details** (Country, GDP, etc.)
- **Creditor Details** (Jurisdiction, Entity Type, etc.)
- **Document Characteristics** (Instrument Type, Maturity Date, etc.)

#### 3. Tagged Clauses Format
The annotations are displayed as interactive tags/badges organized by category:
```
Financial Terms:
  - Commitment (orange-outlined tag, clickable)
  - Currency of Denomination and/or Payment (light blue tag)
  - Final Repayment/Maturity Date(s), Interest, Fees (light blue tags)
  - Maturity (light blue tag)

Disbursement:
  - Utilization/Borrowing (light blue tag)

Repayment:
  - Payment Mechanics, Partial Payment (light blue tags)

[And so on...]
```

### Annotation Data Points

Per annotated document, the following data is captured:

1. **Document Metadata**
   - Document ID (e.g., VEN85)
   - Document Title
   - Document Type (Bond, Loan, Note, etc.)
   - Borrower Country
   - Creditor Jurisdiction
   - Contract Date
   - Maturity Date
   - Instrument Type
   - Status (Annotated / Not Annotated)

2. **Clause Tags**
   - Clause Type (e.g., "Commitment")
   - Clause Category (e.g., "Financial Terms")
   - Presence indicator (clause is/is not present)
   - (Potentially) Exact clause text location/page number (not confirmed in UI, but PDF metadata may contain this)

3. **Optional Clause Details**
   - Clause text excerpt (visible when hovering or clicking tag - not observed in current UI)
   - Interpretation/notes (not visible in current UI, may be in backend)

## Data Extractability Assessment

### Technical Approach: Three Options

#### Option 1: HTML Scraping (Lowest Effort, Limited Data)
**Feasibility**: HIGH | **Effort**: LOW | **Data Quality**: MEDIUM

**Approach**:
1. Search interface returns paginated results with searchable metadata
2. Parse search result pages to extract document IDs and metadata
3. For each document, parse the right-panel HTML to extract clause tags

**Pros**:
- No authentication required
- Clean, structured HTML
- Simple to implement with BeautifulSoup/Selenium
- Can extract all document-level metadata

**Cons**:
- Right panel data appears to be client-side rendered (may not be in initial HTML)
- Cannot easily extract the actual annotated clause text from the PDF
- Requires loading each document page to get annotations

**Data Extraction**:
```python
# Pseudocode
for page in search_results:
    for doc in page['documents']:
        doc_id = doc['id']  # e.g., "VEN85"
        metadata = extract_metadata(doc)  # Country, Instrument Type, etc.

        # Load document page
        doc_page = fetch(f'/pdf/{doc_id}/')

        # Extract clause tags from right panel HTML
        tags = parse_tagged_clauses(doc_page)

        # Result: {id, metadata, tags}
```

#### Option 2: API Reverse Engineering (Medium Effort, Higher Data Quality)
**Feasibility**: MEDIUM | **Effort**: MEDIUM | **Data Quality**: HIGH

**Approach**:
1. Monitor network traffic while using the search interface
2. Identify API endpoints for:
   - Document search/filtering
   - Clause annotations by document
   - Document metadata retrieval
3. Reverse engineer API request/response format
4. Build direct API client

**Observations from Current Reconnaissance**:
- Search URL params use JSON encoding: `labels=%5B%22Commitment_FinancialTerms%22%5D` (URL-encoded `["Commitment_FinancialTerms"]`)
- Document IDs follow pattern: `{COUNTRY_CODE}{NUMBER}` (e.g., VEN85, BRA12)
- Appears to be a statically-built site (likely Next.js or Nuxt based on URL structure)
- API endpoint for PDF download: `/api/pdf/{DOC_ID}`

**Next Steps**:
- Monitor browser network tab while:
  - Clicking on clause tags
  - Scrolling through annotated clauses
  - Filtering by specific clauses
- Identify if there's a GraphQL endpoint or REST API for clause data

**Potential Endpoints** (to investigate):
```
/api/documents
/api/documents/{id}
/api/documents/{id}/clauses
/api/search
/api/clauses
/api/pdf/{id}
/api-json (some frameworks expose this)
```

#### Option 3: Browser Automation (Highest Effort, Complete Data)
**Feasibility**: HIGH | **Effort**: HIGH | **Data Quality**: VERY HIGH

**Approach**:
1. Use Playwright/Selenium to automate the search interface
2. Iterate through all documents (900+)
3. For each document:
   - Load `/pdf/{DOC_ID}/`
   - Extract metadata from right panel
   - Extract all clause tags
   - Optionally, click on each clause tag to see if it reveals clause text
   - Optional: Parse PDF to extract full clause text by position

**Pros**:
- Can capture 100% of data including dynamic content
- Can extract clause text by monitoring highlights or popups
- No need to reverse engineer API
- Reliable against UI changes (somewhat)

**Cons**:
- Slow (900 documents × page load time = hours)
- Resource-intensive (browser memory)
- May require headless browser (Docker)
- Risk of being rate-limited

**Python Pseudocode**:
```python
from playwright.async_api import async_playwright

async def extract_pdip_data():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Step 1: Get all document IDs via search
        doc_ids = await get_all_document_ids(page)

        # Step 2: Extract data for each document
        documents = []
        for doc_id in doc_ids:
            await page.goto(f'/pdf/{doc_id}/')

            # Extract metadata
            metadata = await extract_metadata(page)

            # Extract clause tags
            clauses = await extract_clause_tags(page)

            documents.append({
                'id': doc_id,
                'metadata': metadata,
                'clauses': clauses
            })

        return documents
```

### Recommended Approach: **Hybrid Strategy**

1. **Phase 1: HTML Scraping** (2-4 hours)
   - Scrape all search results to get document inventory
   - Extract basic metadata (Country, Instrument Type, Maturity Date, etc.)
   - Result: CSV/JSON of 900 documents with metadata

2. **Phase 2: API Reverse Engineering** (2-6 hours)
   - Monitor network requests while interacting with clause tags
   - Identify if there's a hidden API for clause data
   - If found, implement direct API calls for clause extraction
   - If not found, fall back to browser automation

3. **Phase 3: Clause Text Extraction** (1-3 days for full automation)
   - If API available: Query API for clause text
   - If not: Use Playwright to load documents and extract clause text from PDF
   - Build database linking document → clause type → clause text

## Implementation Roadmap

### Step 1: Document Inventory (4 hours)
```
Input: None
Output: documents.csv with ~900 rows
Columns: doc_id, country, creditor, instrument_type, maturity_date, status (Annotated/Unannotated)
```

**Implementation**:
```python
import requests
from bs4 import BeautifulSoup
import csv

def scrape_search_results():
    base_url = "https://publicdebtispublic.mdi.georgetown.edu/search/"
    documents = []

    for page in range(1, 100):  # Adjust based on total pages
        url = f"{base_url}?page={page}&sortBy=date&sortOrder=asc"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Parse document cards from search results
        for doc_card in soup.find_all('article', class_='document-result'):
            doc = {
                'doc_id': extract_doc_id(doc_card),
                'title': doc_card.find('h2').text,
                'country': extract_metadata(doc_card, 'Borrower'),
                'creditor': extract_metadata(doc_card, 'Creditor'),
                'instrument_type': extract_metadata(doc_card, 'Instrument'),
                'maturity_date': extract_metadata(doc_card, 'Maturity Date'),
                'status': 'Annotated' if 'Status: Annotated' in doc_card.text else 'Unannotated',
            }
            documents.append(doc)

    # Save to CSV
    with open('documents.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=doc.keys())
        writer.writeheader()
        writer.writerows(documents)
```

### Step 2: Annotated Documents & Clause Tags (6-8 hours)
```
Input: documents.csv (filtered to Status='Annotated', ~200-300 documents)
Output: annotations.csv with clause presence data
Columns: doc_id, clause_type, clause_category, is_present
```

**Implementation**:
```python
from playwright.async_api import async_playwright

async def extract_clause_tags():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        annotated_docs = pd.read_csv('documents.csv')[lambda x: x['status'] == 'Annotated']

        results = []
        for _, doc in annotated_docs.iterrows():
            doc_id = doc['doc_id']
            try:
                page = await browser.new_page()
                await page.goto(f'https://publicdebtispublic.mdi.georgetown.edu/pdf/{doc_id}/')

                # Wait for right panel to load
                await page.wait_for_selector('[class*="TaggedClauses"]')

                # Extract all clause tags
                clauses = await page.evaluate('''
                    () => {
                        const tags = document.querySelectorAll('[class*="clause-tag"]');
                        return Array.from(tags).map(t => ({
                            type: t.textContent,
                            category: t.parentElement.previousElementSibling?.textContent || 'Unknown'
                        }));
                    }
                ''')

                for clause in clauses:
                    results.append({
                        'doc_id': doc_id,
                        'clause_type': clause['type'],
                        'clause_category': clause['category'],
                        'is_present': 1
                    })
            except Exception as e:
                print(f"Error processing {doc_id}: {e}")

        # Save results
        pd.DataFrame(results).to_csv('clause_annotations.csv', index=False)
```

### Step 3: Full Text Extraction (2-5 days for full automation)
```
Input: clause_annotations.csv
Output: clause_texts.csv or JSON
Columns: doc_id, clause_type, clause_text, page_number, confidence
```

**Approach**: Once clause tags are identified, either:
1. Query (hypothetical) API endpoint: `/api/documents/{doc_id}/clauses`
2. Or use PDF text extraction with positional hints from viewer

## Terms of Service & Legal Considerations

**Terms of Use**: https://publicdebtispublic.mdi.georgetown.edu/wp/terms_of_use/
- **Status**: NOT YET REVIEWED (should be reviewed before automated scraping)
- **Key Points to Check**:
  - Permission for automated access / web scraping
  - Attribution requirements
  - Data redistribution rights
  - Rate limiting guidelines

**Recommendations**:
1. Review terms of use before implementing scraper
2. Implement respectful rate limiting (1-2 second delays between requests)
3. Identify as bot in User-Agent header
4. Cache results to avoid repeated requests
5. Check `/robots.txt` for scraping guidelines

**robots.txt Check**:
```bash
curl https://publicdebtispublic.mdi.georgetown.edu/robots.txt
```

## Data Schema & Output Format

### Recommended Output Structure

#### documents.csv
```csv
doc_id,title,country,creditor,instrument_type,maturity_date,contract_date,status,url
VEN85,Petróleos de Venezuela S.A Note January 20 2017,Venezuela,United States Private Creditor(s),Bond,2020-01-20,2017-01-20,Annotated,https://publicdebtispublic.mdi.georgetown.edu/pdf/VEN85/
BRA12,Brazil Bonds 2025,Brazil,Private Creditor(s),Bond,2025-06-15,2015-01-10,Annotated,https://publicdebtispublic.mdi.georgetown.edu/pdf/BRA12/
...
```

#### clause_annotations.csv
```csv
doc_id,clause_type,clause_category,is_present
VEN85,Commitment,Financial Terms,1
VEN85,Currency of Denomination and/or Payment,Financial Terms,1
VEN85,Maturity,Financial Terms,1
VEN85,Utilization/Borrowing,Disbursement,0
...
```

#### clause_texts.json (Optional, Full Extraction)
```json
{
  "doc_id": "VEN85",
  "clauses": [
    {
      "type": "Commitment",
      "category": "Financial Terms",
      "text": "Section 2.01 Issuance of Initial Note. (a) The execution and delivery of this Agreement...",
      "page_number": 1,
      "extraction_method": "pdf_text_extraction",
      "confidence": 0.95
    },
    {
      "type": "Currency of Denomination and/or Payment",
      "category": "Financial Terms",
      "text": "The Notes shall be issued in United States Dollars...",
      "page_number": 2,
      "extraction_method": "pdf_text_extraction",
      "confidence": 0.92
    }
  ]
}
```

## Obstacles & Mitigation

| Obstacle | Likelihood | Mitigation |
|----------|-----------|-----------|
| Clause data is client-side rendered (not in HTML) | HIGH | Use Playwright to render before scraping; reverse engineer API |
| Rate limiting / IP blocking | MEDIUM | Implement delays (1-2s), use residential proxy if needed, check robots.txt |
| PDF text extraction inaccuracy | MEDIUM | Use multiple PDF libraries (pdfplumber, pypdf); manual validation on sample |
| URL structure changes | LOW | Document patterns; monitor for changes; use homepage navigation instead |
| Terms of Use prohibit scraping | LOW | Review terms; contact platform if needed; focus on API if available |
| Document IDs not enumerable | LOW | Use search results pagination; document ID patterns appear consistent |
| SSL certificate issues | LOW | Already encountered in WebFetch; use browser automation instead |
| Missing annotations on "Unannotated" documents | N/A | Filter to Status='Annotated' only |

## Effort Estimation

| Phase | Task | Duration | Dependencies |
|-------|------|----------|---|
| 1 | Environment setup (Python, libraries) | 0.5h | None |
| 1 | Document inventory scraping | 1h | None |
| 1 | Metadata extraction & CSV export | 1h | Phase 1 Task 2 |
| 1 | QA & validation | 1h | Phase 1 Task 3 |
| 2 | API reverse engineering | 2-4h | Phase 1 completion |
| 2 | Annotated documents scraping (Playwright) | 4-6h | Phase 1 completion |
| 2 | Clause tags extraction | 2h | Phase 2 Task 2 |
| 3 | Full clause text extraction (if API unavailable) | 8-24h | Phase 2 completion |
| 3 | Database schema & final formatting | 2h | Phase 3 completion |
| **Total** | | **21.5-40.5 hours** | |

**Realistic Timeline**:
- **Week 1**: Complete Phase 1 (document inventory)
- **Week 2**: Complete Phase 2 (clause tags + basic extraction)
- **Week 3-4**: Complete Phase 3 (full text extraction) if needed

## Proof of Concept

### Quick Test: Scraping One Document's Metadata

```python
#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

# Test 1: Fetch search results
print("Test 1: Fetching search results...")
response = requests.get('https://publicdebtispublic.mdi.georgetown.edu/search/?page=1&sortBy=date&sortOrder=asc')
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.content, 'html.parser')
doc_titles = soup.find_all('h2', class_='document-title')
print(f"Found {len(doc_titles)} documents on page 1")

# Test 2: Access specific document
print("\nTest 2: Fetching specific document (VEN85)...")
doc_response = requests.get('https://publicdebtispublic.mdi.georgetown.edu/pdf/VEN85/')
print(f"Status: {doc_response.status_code}")

# Test 3: Download PDF
print("\nTest 3: Testing PDF download endpoint...")
pdf_response = requests.get('https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85')
print(f"Status: {pdf_response.status_code}, Size: {len(pdf_response.content)} bytes")
```

## Conclusion

The PublicDebtIsPublic platform is **highly extractable**. The three-phase approach above balances effort against data completeness:

1. **Phase 1** (4 hours) delivers a complete document inventory suitable for initial validation
2. **Phase 2** (6-8 hours) delivers clause presence annotations for all 100+ clauses
3. **Phase 3** (optional, 1-3 days) delivers full clause text extraction for maximum training data

**Recommendation**: Start with Phase 1 immediately (low risk, high value). Proceed to Phase 2 in parallel with API reverse engineering. Phase 3 can be deferred until full text is needed for ML training.

The resulting validation set will provide:
- **900 documents** with structured metadata
- **200-300 annotated documents** with clause-level labels
- **100+ clause types** each with positive/negative examples
- **Full clause text** (if Phase 3 completed) for fine-tuning clause classification models

