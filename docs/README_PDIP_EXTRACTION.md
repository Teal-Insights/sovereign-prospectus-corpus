# PublicDebtIsPublic Data Extraction Project

## Quick Start

This directory contains a complete technical assessment and implementation framework for extracting annotation data from the PublicDebtIsPublic (PDIP) platform.

**Platform**: https://publicdebtispublic.mdi.georgetown.edu/
**Scope**: ~900 sovereign debt documents with ~100+ annotated contract terms
**Goal**: Build validation/training set for AI-powered clause classification

## Documents

### 1. **PDIP_RECONNAISSANCE_SUMMARY.md** (9.9 KB)
**START HERE** - Executive summary of findings
- Platform overview (900 documents, 100+ clauses)
- Data structure and organization
- Three-phase extraction strategy
- URL patterns identified
- Risk assessment and next steps
- **Read this first**: 5-minute overview

### 2. **pdip_data_extraction_assessment.md** (20 KB)
**DETAILED ANALYSIS** - Comprehensive technical report
- Complete platform architecture
- Detailed data structure documentation
- Three extraction approaches (HTML scraping, API, browser automation)
- Data schema and output formats
- Complete implementation roadmap
- Effort estimation (21.5-40.5 hours)
- Obstacle analysis and mitigation
- Proof-of-concept code examples
- **Read this for**: Implementation planning and technical decisions

### 3. **pdip_extraction_script_template.py** (14 KB)
**WORKING CODE** - Python implementation framework
- Phase 1: Document inventory scraper
- Phase 2: Clause extraction framework
- Phase 3: Placeholder for full text extraction
- Includes rate limiting, retry logic, error handling
- Ready to adapt for production use
- **Use this for**: Starting actual implementation

## Three-Phase Extraction Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: Document Inventory (4 hours)                           │
│ ├─ Scrape all ~900 documents from search results               │
│ ├─ Extract metadata (country, creditor, maturity, status)      │
│ └─ Output: documents.csv (900 rows)                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 2: Clause Annotations (6-8 hours)                        │
│ ├─ Load each annotated document (200-300 documents)            │
│ ├─ Extract clause tags from frontend                           │
│ └─ Output: clause_annotations.csv (5,000-10,000 rows)          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 3: Full Clause Text (1-3 days, optional)                │
│ ├─ Extract full text for each clause                           │
│ ├─ Map to page numbers and confidence scores                   │
│ └─ Output: clause_texts.json                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Findings

### Data Organization
- **900 documents** with IDs like VEN85 (Venezuela), BRA12 (Brazil)
- **45+ countries** represented
- **200-300 annotated documents** (status: Annotated)
- **100+ clause types** organized in ~10 categories

### Clause Taxonomy
1. Financial Terms (9 types)
2. Disbursement (1 type)
3. Repayment/Payments (6 types)
4. Definitions (1+ types)
5. Representations and Warranties (7+ types)
6. Conditions Precedent (2+ types)
7. Borrower Covenants/Undertakings (8+ types)
8. Events of Default and Consequences
9. Other (Power and Authority, Sanctions, etc.)

### URL Pattern
```
Search:     /search/?page=1&sortBy=date&sortOrder=asc&labels=[...]
Document:   /pdf/{DOC_ID}/ (e.g., /pdf/VEN85/)
PDF API:    /api/pdf/{DOC_ID}
```

## Implementation Roadmap

### Week 1: Phase 1 Document Inventory
- [ ] Review `/wp/terms_of_use/` for scraping permissions
- [ ] Run Phase 1 on test subset (10 pages)
- [ ] Validate HTML scraping approach
- [ ] Complete Phase 1 full run (900 documents)
- [ ] Generate `documents.csv`

### Week 2: Phase 2 Clause Extraction
- [ ] Identify clause data source (HTML vs. API)
- [ ] Implement Phase 2 scraper (with Playwright if needed)
- [ ] Process all annotated documents (200-300)
- [ ] Generate `clause_annotations.csv`
- [ ] Quality check: verify clause counts vs. platform

### Week 3-4: Phase 3 Full Text (Optional)
- [ ] Reverse engineer API for clause text OR
- [ ] Implement Playwright for full text extraction
- [ ] Extract clause text with page numbers
- [ ] Generate `clause_texts.json`
- [ ] Build final training/validation dataset

## Effort Estimation

| Phase | Task | Duration | Risk |
|-------|------|----------|------|
| 1 | Setup + Document scraping | 4 hours | Low |
| 2 | Clause extraction (HTML/API) | 6-8 hours | Medium |
| 3 | Full text extraction | 8-24 hours | Medium-High |
| **Total** | | **21.5-40.5 hours** | |

## Expected Outputs

### From Phase 1
```csv
doc_id,title,country,creditor,instrument_type,maturity_date,status
VEN85,Petróleos de Venezuela S.A Note January 20 2017,Venezuela,United States,Bond,2020-01-20,Annotated
BRA12,Brazil Bonds 2025,Brazil,Private Creditor(s),Bond,2025-06-15,Annotated
```

### From Phase 2
```csv
doc_id,clause_type,clause_category,is_present
VEN85,Commitment,Financial Terms,1
VEN85,Currency of Denomination,Financial Terms,1
VEN85,Commitment,Financial Terms,0
BRA12,Commitment,Financial Terms,1
```

### From Phase 3 (Optional)
```json
{
  "doc_id": "VEN85",
  "clauses": [
    {
      "type": "Commitment",
      "category": "Financial Terms",
      "text": "Section 2.01 Issuance of Initial Note...",
      "page_number": 1,
      "confidence": 0.95
    }
  ]
}
```

## Validation Set Characteristics

The resulting dataset will be suitable for training clause classification models:

✓ **Diverse**: 45+ countries, multiple creditor types
✓ **Structured**: Hierarchical taxonomy with 100+ clause types
✓ **Annotated**: Manually labeled by law students and lawyers at Georgetown
✓ **Scalable**: 200-300 documents = 5,000-10,000 clause examples
✓ **High-quality**: Authoritative source (Georgetown Law + Massive Data Institute)

## Risks & Mitigation

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Clause data is client-side rendered | High | Use Playwright; attempt API reverse engineering |
| Rate limiting | Medium | Implement delays (1-2s); check ToS |
| ToS prohibits scraping | Low | Review terms before automation |
| PDF text extraction inaccuracy | Medium | Use pdfplumber; validate sample |
| Slow extraction (900 docs) | Medium | Parallelize; focus on annotated docs first |

## Technical Stack

**Recommended Libraries**:
```
requests          # HTTP requests
beautifulsoup4    # HTML parsing
pandas            # Data processing
playwright        # Browser automation (if needed)
pdfplumber        # PDF text extraction (if needed)
```

**Installation**:
```bash
pip install requests beautifulsoup4 pandas playwright
playwright install chromium  # If using browser automation
```

## Getting Started

### Step 1: Review Assessment Documents
1. Read `PDIP_RECONNAISSANCE_SUMMARY.md` (5 min overview)
2. Review `pdip_data_extraction_assessment.md` (implementation details)

### Step 2: Check Legal Requirements
1. Review https://publicdebtispublic.mdi.georgetown.edu/wp/terms_of_use/
2. Check https://publicdebtispublic.mdi.georgetown.edu/robots.txt

### Step 3: Run Phase 1 (Test)
```bash
python pdip_extraction_script_template.py --phase 1 --max-pages 10 --output test_documents.csv
```

### Step 4: Validate & Scale
- Verify output format and completeness
- Run full Phase 1: `--max-pages 999999` for all documents
- Proceed to Phase 2 and 3 as needed

## Project Contact

**Platform**: PublicDebtIsPublic (https://publicdebtispublic.mdi.georgetown.edu/)
**Ownership**: Sovereign Debt Forum, Massive Data Institute, Georgetown Law
**Feedback**: https://docs.google.com/forms/d/e/1FAIpQLSf6MYIZX50Dlhd1JD0r104an0wI_bK9F44Pcn5xtQzzjuSNww/viewform

## License & Attribution

The PDIP platform data is provided by Georgetown Law and the Massive Data Institute. Any extracted data should include appropriate attribution:

> Data extracted from PublicDebtIsPublic (https://publicdebtispublic.mdi.georgetown.edu/),
> a Sovereign Debt Forum Initiative of the Massive Data Institute at Georgetown University.

## Appendix: Platform Details

### Clause Categories (Complete List)

**Financial Terms**
- Commitment, Currency of Denomination and/or Payment, Exchange-eligible debt, Final Repayment/Maturity Date(s), Interest, Fees, Purpose, Maturity, Use of Proceeds

**Disbursement**
- Utilization/Borrowing

**Repayment/Payments**
- Deferral of Payments, Maturity Extension, Mandatory Prepayment/Cancellation, Voluntary Prepayments, Redemption/Repurchase/Early Repayment, Additional Amounts

**Definitions**
- Indebtedness

**Representations and Warranties**
- Authorizations and Approvals, Exchange Controls (R & W), Commercial Acts, Power and Authority, Sanctions (R & W), Status of Obligation/Pari Passu (R & W), No Security

**Conditions Precedent**
- Conditions (Effectiveness), Conditions (Utilization)

**Borrower Covenants/Undertakings**
- Anti-corruption/AML, Books and Records, Compliance with Authorizations, Limits on External Indebtedness, Negative Pledge, Lien/Permitted Lien, Information, Notification

**Events of Default and Consequences**
- (Varies by document)

### Document ID Examples

| ID | Country | Notes |
|----|---------|-------|
| VEN85 | Venezuela | Petróleos de Venezuela S.A Note (2017) |
| BRA12 | Brazil | Various bonds and loans |
| EGY45 | Egypt | Government bonds |
| IND20 | India | Sovereign debt instruments |

### Important URLs

- Homepage: https://publicdebtispublic.mdi.georgetown.edu/
- Search: https://publicdebtispublic.mdi.georgetown.edu/search/
- Terms of Use: https://publicdebtispublic.mdi.georgetown.edu/wp/terms_of_use/
- Resources: https://publicdebtispublic.mdi.georgetown.edu/wp/additional-resources/

---

**Last Updated**: March 24, 2026
**Status**: Complete Technical Reconnaissance
**Next Action**: Review findings and begin Phase 1 implementation
