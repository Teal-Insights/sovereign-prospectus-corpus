# Proof of Concept Strategy: Sovereign Bond Prospectus Corpus

**Project:** Sovereign Bond Prospectus Corpus for #PublicDebtIsPublic Roundtable
**Target Event:** March 30, 2026 — Georgetown Law, hosted by Anna Gelpern
**Timeline:** March 24-29, 2026 (6 days, 24/7 processing on Mac Mini)
**Goal:** Demonstrate capability to extract, analyze, and compare sovereign bond contract terms at scale

---

## 1. Strategic Rationale

This PoC connects directly to Anna Gelpern's research agenda and the #PublicDebtIsPublic (PDIP) platform's core mission: making sovereign debt contract terms accessible, intelligible, and accountable to the public.

### Why This Matters Now

1. **CAC Evolution Post-2014:** Since the G20 endorsed enhanced CACs in 2014, the market has substantially adopted aggregated voting clauses (74% of new issuances by 2016). Yet empirical variation across issuers and time remains poorly documented. This corpus would surface patterns.

2. **Recent Restructurings Create Research Opportunity:** Ghana, Zambia, and Sri Lanka completed restructurings in 2024-2025 using the Common Framework. Senegal is heading toward restructuring in late 2026. Analyzing their prospectus terms reveals what contract features proved problematic or effective in practice.

3. **PDIP is Pilot-Stage:** PDIP's current pilot covers 114 documents for 20 countries. This corpus could expand coverage dramatically, especially for EM/frontier sovereigns with NSM filings — providing empirical backing for the platform's transparency goals.

4. **Information Infrastructure Gap:** Researchers cannot currently compare pari passu language, events of default thresholds, or negative pledge scopes across 40+ sovereigns. This corpus closes that gap.

---

## 2. Countries to Prioritize

### Primary Focus: Recently-Restructured + High-Risk Sovereigns

These countries have **concrete, timely policy relevance** and rich NSM data:

| Country | NSM Filings | Recent Events | Priority Reason |
|---------|------------|---------------|-----------------|
| Ghana | 28 | Restructured 2024 (Common Framework) | Completed CF case; prospectus evolution visible |
| Zambia | 28 | Restructured 2024 (Common Framework) | Completed CF case; prospectus evolution visible |
| Sri Lanka | 11 | Restructured 2024 (outside CF) | Alternative restructuring path; smaller dataset |
| Ukraine | 21 | Ongoing; unsustainable debt | Active crisis; prospectus terms under stress |
| Senegal | (absent from NSM) | Restructuring expected H2 2026 | **Critical gap:** not in NSM; may be in Luxembourg or Euronext Dublin |
| Kenya | 19 | Recent issuance activity (Feb 2026) | Active issuer; multiple prospectus types |
| Nigeria | 43 | Active but vulnerable | Largest EM issuer after Israel; stable reference point |

### Secondary Comparators: CAC Variation Study

To demonstrate post-2014 CAC adoption patterns:

| Country | NSM Filings | Comparison Value |
|---------|------------|-------------------|
| Serbia | 41 | Pre-2014 CACs vs. recent enhanced CACs |
| UAE - Abu Dhabi | 37 | Frequent issuer; EMTN programme structure |
| Saudi Arabia | 27 | Large issuances; sovereign sukuk variants |
| Angola | 17 | Post-restructuring issuance (2024-2025) |

### Geographic Coverage Achieved

This selection achieves representation across:
- **Africa:** Ghana, Zambia, Kenya, Nigeria, Angola, Senegal (gap)
- **Middle East/Asia:** Ukraine, Saudi Arabia, UAE, Kenya
- **Developed comparators:** Serbia (lower-middle income)

---

## 3. Which Clauses to Extract

Focus on **value-differentiating terms** that vary meaningfully across issuers and time, informed by Anna Gelpern's published research on CACs, pari passu, and contract design.

### Tier 1 Clauses (High Priority)

**Collective Action Clauses (CACs)**
- Type: Single-limb aggregated, series-by-series, or hybrid
- Voting threshold (majority, super-majority definition)
- Scope: single series vs. aggregation across series
- Amendment rights (which clauses can be amended)
- **Research question:** Post-2014 adoption; variation across African sovereigns vs. MENA

**Pari Passu Language**
- Definition: strict vs. modified
- Ratable payments requirement (carve-outs for structural subordination)
- Exceptions (official creditors, DFIs)
- **Research question:** Evolution post-restructurings; how did Ghana/Zambia modify terms?

**Events of Default**
- Cross-default thresholds (amount, "material" definitions)
- Acceleration triggers
- Cure periods
- Force majeure carve-outs
- **Research question:** Do stress-tested sovereigns (Ukraine) use broader definitions?

### Tier 2 Clauses (Medium Priority)

**Negative Pledge**
- Breadth (all assets vs. specific collateral)
- Exceptions (official development finance, trade finance)
- Subordination rights

**Governing Law & Dispute Resolution**
- English law vs. other
- ISDA master agreement reference
- Jurisdiction/arbitration choice

**Subordination Terms**
- Explicit subordination (if any)
- Intercreditor arrangements
- Standstill provisions

### Tier 3 Clauses (Context)

**Boilerplate Structural Terms**
- Bond currency
- Maturity profile
- Coupon structure (fixed, floating)
- Enhancement/guarantee terms

---

## 4. Download & Processing Pipeline

### Phase 1: Data Discovery (Parallel Work)

**NSM Processing (Primary Source)**
1. Query NSM API for top 10 priority countries (Ghana, Zambia, Sri Lanka, Ukraine, Kenya, Nigeria, Serbia, UAE-Abu Dhabi, Saudi Arabia, Angola)
2. Use existing `sovereign_issuer_reference.csv` to get LEIs and name variants
3. Filter by document type = `Publication of a Prospectus` or `Base Prospectus` (exclude supplements, tender offers, issue notices)
4. Pagination: Handle results >10k by issuer+date range

**Secondary Source Research (Luxembourg, Euronext Dublin, SEC)**
- **Senegal:** Search Luxembourg Stock Exchange listing database for Senegal sovereign bonds
- **Euronext Dublin:** Query for any EM sovereigns absent from NSM (Argentina, Brazil, Colombia, Mexico, Indonesia, Philippines mentioned in Phase 0 notes)
- **SEC EDGAR:** Search for any sovereigns with US-listed bonds (typically emerging markets)
- Deliverable: Curated list of additional sources; may be out of scope for initial PoC given time constraints

### Phase 2: PDF Download (Mac Mini, Unattended)

**Implementation: `nsm_downloader.py`**

```python
Architecture:
1. Read sovereign_issuer_reference.csv
2. For each country in priority list:
   a. Query NSM API (POST /search?index=fca-nsm-searchdata)
   b. Filter: latest_flag=Y, document type in [Base Prospectus, Prospectus]
   c. Paginate through results (size=100, from=0/100/200/...)
   d. For each result, capture:
      - Document headline, company name, LEI, filing date, document type
      - Download URL (direct PDF or HTML metadata page)
   e. Two-hop resolution:
      - If URL is HTML: fetch page, extract PDF link via BeautifulSoup
      - If URL is PDF: download directly via requests
   f. Save to data/pdfs/{country}_{date}_{doctype}.pdf
   g. Log metadata to data/processed/downloads.jsonl
3. Error handling & retry logic
4. Graceful shutdown on Mac Mini sleep/network failure
```

**Robustness Features**
- Resumable from checkpoint (track downloaded URLs)
- Exponential backoff for transient failures
- Timeout handling (60s per request)
- File integrity check (PDF header validation)
- Logging: progress + errors to `logs/nsm_downloader_{date}.log`

**Expected Output**
- ~250-350 PDFs (28+28+11+21+19+43+41+37+27+17 = 272 filings, ~80% prospectus type)
- Directory structure: `data/pdfs/{country}/{filename}`
- Metadata: `data/processed/downloads.jsonl` (one JSON object per downloaded document)

### Phase 3: PDF Processing & Clause Extraction

**Tool Stack**
- **PDF Text Extraction:** Docling (superior to PyPDF2 for layout-aware extraction)
- **Clause Identification:** Claude API (3.5 Sonnet or Opus) for few-shot prompting
- **Storage:** JSONL for streaming, SQLite for indexing

**Processing Pipeline**

1. **Batch Text Extraction** (Docling)
   - Convert each PDF to structured text + layout metadata
   - Preserve section headers (Key Terms, Conditions, Events of Default)
   - Output: `data/processed/pdf_texts/{country}_{date}_{doctype}.txt`

2. **Clause Extraction via Claude API**
   - Prompt template: "Extract the following clauses: [Tier 1]. Return as structured JSON."
   - Input: Full prospectus text (batched if >100k tokens)
   - Output: JSON object with clause keys, extracted text, confidence score
   - Batch processing: 10 PDFs in parallel (Mac Mini has capacity)

3. **Storage & Indexing**
   - Append to `data/processed/clauses.jsonl`
   - SQLite index: `data/processed/clauses.db` with FTS (full-text search)

**Processing Cost & Timeline**
- 250 PDFs × Claude API pricing (input ~50k avg, ~10k output)
- Est. $150-300 for full corpus extraction
- Timeline: 48 hours unattended processing (batch size 10, 10-min processing per batch, staggered)

---

## 5. Demo & Visualizations

### Deliverables for Roundtable

**A. Interactive Clause Comparison Dashboard**

A simple web-based tool (HTML + React or plain JS) that allows:
- **Filter by country:** Ghana, Zambia, Sri Lanka, Ukraine, Kenya, Nigeria
- **Filter by clause type:** CACs, Pari Passu, Events of Default, etc.
- **View extracted clause text** side-by-side with metadata
- **Timeline view:** Show evolution of same clause across issuances from same country
- **Diff view:** Highlight changes in language between consecutive issuances

**Technical stack:** Static HTML/JS, served locally or GitHub Pages; data from `clauses.db`

**Key insight to surface:** 
> "Ghana's CAC language in 2023 prospectuses vs. 2024 post-restructuring terms reveals [specific changes]. Compare to Zambia's 2023→2024 evolution."

**B. CAC Adoption Timeline**

A timeline visualization showing:
- Which countries adopted enhanced CACs post-2014
- Which filings in the corpus show full aggregation clauses
- Which still use older series-by-series voting
- **Finding:** Expected to show strong post-2014 adoption among major issuers

**C. Pari Passu Language Taxonomy**

Catalog extracted pari passu language and classify by degree of "modification":
- Strict pari passu (rare)
- Modified with official creditor carve-out (common)
- Modified with subordination to specific creditors (emerging)

**D. Events of Default Comparison Matrix**

Table: Countries × Event Types, with representative language extracted
- Cross-default thresholds (e.g., Ukraine vs. Nigeria vs. Saudi Arabia)
- Force majeure language (Ukraine's war carve-outs?)
- Acceleration mechanics

**E. Summary Briefing Document (1-page)**

One-page summary suitable for roundtable discussion:
1. Corpus stats (# docs, countries, date range)
2. Key finding #1: CAC adoption milestone achieved
3. Key finding #2: Ghana/Zambia restructuring impact on terms
4. Key finding #3: Identifying gaps (Senegal, Argentina, etc.)
5. Proposal: Integration with PDIP platform

---

## 6. Connection to #PublicDebtIsPublic

### Current State of PDIP

- **Pilot:** 114 documents for 20 countries
- **Geographic focus:** Africa, Asia, Caribbean, South America, Europe
- **Document types:** Full debt contracts, term sheets
- **Features:** Clause explainers, capacity-building links, search & comparison

### Proposed Integration

This corpus extends PDIP in three dimensions:

1. **Scale:** From 114 to potentially 350+ documents (near 3x expansion)

2. **Granularity:** PDIP focuses on full-contract access. This corpus makes **specific clauses searchable and comparable** at scale — addressing the "intelligibility" pillar of PDIP's transparency definition.

3. **Coverage Expansion:** PDIP's pilot includes some African sovereigns (Ghana, Zambia, Kenya) but is sparse on others (Nigeria, Angola) and **missing entire countries** (Senegal, Uruguay, others). NSM fills these gaps for UK-listed sovereigns; secondary sources fill gaps for others.

4. **Research Infrastructure:** PDIP currently lacks automated clause extraction and comparative analytics. This corpus demonstrates what's possible, providing a template for PDIP's future tooling.

### Specific PDIP-Aligned Deliverables

1. **Curated clause library:** Extract CACs, pari passu, events of default from PDIP-included countries, cross-reference with PDIP's existing documents
2. **Comparison tool mockup:** Demonstrate how PDIP could offer "compare clause X across 10 sovereigns"
3. **Gap analysis:** Identify which countries/documents PDIP is missing (especially Senegal, Argentina)
4. **Integration roadmap:** Propose how NSM + secondary sources could feed future PDIP expansions

---

## 7. Timeline & Realistic Scope (March 24-29, 2026)

### Monday, March 23 — Planning & Setup
- [ ] Finalize this strategy document
- [ ] Write `nsm_downloader.py`
- [ ] Test PDF download pipeline on 5 sample countries
- [ ] Set up logging, error handling, resumability

### Tuesday, March 24 — Download & Initial Processing
- [ ] Start `nsm_downloader.py` on Mac Mini (leave running 24/7)
- [ ] Target: Complete downloads for top 10 countries by EOD Wednesday
- [ ] Begin Docling text extraction in parallel (small batches)

### Wednesday-Thursday, March 25-26 — Clause Extraction
- [ ] Continue downloads (complete by Thu afternoon)
- [ ] Full Docling processing of downloaded PDFs
- [ ] Begin Claude API clause extraction (batched, 10 PDFs/batch)
- [ ] Target: 80% of PDFs processed by EOD Thursday

### Friday, March 27 — Finalization & Demo Prep
- [ ] Complete remaining clause extraction
- [ ] Build SQLite index and queries
- [ ] Draft HTML/JS comparison dashboard
- [ ] Generate 4-5 key findings and visualizations

### Weekend, March 28-29 — Presentation Prep
- [ ] Polish dashboard
- [ ] Write 1-page PDIP integration summary
- [ ] Prepare demo script and talking points
- [ ] Generate example outputs for offline demo (in case network fails at roundtable)

### Monday, March 30 — Presentation

**Proposed Talking Points:**
1. **Opening:** "Prospectuses are 90% boilerplate. The 10% that varies—CACs, pari passu, events of default—is where policy and research value lives. This corpus makes that variation visible."
2. **Core finding:** "Post-2014 CAC adoption is nearly universal among major issuers, yet implementation varies. Ghana and Zambia's recent restructurings reveal exactly which clause features proved problematic."
3. **PDIP connection:** "This corpus demonstrates what information infrastructure for public debt transparency could look like—machine-readable, searchable, comparative. It's a template for PDIP's next phase."
4. **Call to action:** "We can expand this to cover Argentina, Brazil, Colombia, and other sovereigns absent from NSM by querying Luxembourg Stock Exchange and Euronext Dublin. Full transparency is achievable."

---

## 8. Risk Mitigation & Contingencies

### Technical Risks

| Risk | Mitigation |
|------|-----------|
| NSM API rate limiting kicks in | Start downloads immediately; batch small (size=50 initially); implement backoff |
| Two-hop PDF links fail (broken HTML) | Keep list of failures; fall back to manual curation for <5% |
| Mac Mini crashes/sleeps | Set "never sleep" mode; wrap script with watchdog process |
| Claude API quota exhausted | Budget $300 max; use 3.5 Sonnet instead of Opus if needed; process smaller batch |
| Docling fails on some PDFs (scanned images) | Accept ~5-10% loss; log failures separately; focus on text-native PDFs |

### Scope Risks

| Risk | Mitigation |
|------|-----------|
| Senegal prospectuses absent from NSM | Acknowledge in demo; show that secondary sources (Luxembourg) are required; propose as Phase 2 |
| Limited time for deep analysis | Focus on **demonstration of capability**, not definitive research findings. "We extracted CAC language from 250 prospectuses; here's what it shows..." |
| Dashboard feels incomplete | Prepare offline demo (screenshots + recorded video) as backup |

---

## 9. Success Criteria

By Monday, March 30, Teal should be able to demonstrate:

1. **Data capability:** "We downloaded 250+ prospectuses from 10 sovereigns in 72 hours using NSM API."
2. **Clause extraction at scale:** "We extracted CAC, pari passu, and events of default language from all 250 prospectuses using Claude API."
3. **Comparative insight:** "Here's how Ghana's CAC language evolved from pre-restructuring (2023) to post-restructuring (2024)."
4. **PDIP alignment:** "This corpus expands PDIP coverage by 3x and demonstrates what automated clause comparison could unlock."
5. **Technical reproducibility:** "The pipeline is scripted, logged, and resumable. You can re-run it on other sovereigns."

This positions Teal as having **real, working infrastructure** for the transparent access to sovereign debt information that the roundtable (and PDIP) are advocating for.

---

## 10. Appendix: Tool Stack & Dependencies

**Download Phase**
- Python 3.10+
- `requests` (HTTP client, PDF downloads)
- `beautifulsoup4` (HTML parsing for two-hop links)
- `python-dotenv` (API key management)
- Logging: built-in `logging` module

**Processing Phase**
- `docling` (PDF text extraction with layout preservation)
- `anthropic` (Claude API client for clause extraction)
- `sqlite3` (built-in; indexing)
- `pandas` (optional; data export to CSV)

**Demo Phase**
- Vanilla HTML/CSS/JavaScript (no build step required)
- Optional: `dash` or `streamlit` if interactive app preferred

**Cost Estimate**
- NSM API: free
- Claude API: $150-300 (250 PDFs × ~60k tokens per prospectus)
- Infrastructure: Mac Mini hardware (already owned)
- **Total:** ~$300 (one-time)

---

## 11. Repository Structure (Deliverables)

```
2026-03_Sovereign-Prospectus-Corpus/
├── docs/
│   ├── proof_of_concept_strategy.md          (this document)
│   ├── nsm_api_reference.md                  (existing API doc)
│   └── pdip_integration_proposal.md          (to be written)
├── scripts/
│   ├── nsm_downloader.py                     (to be written)
│   ├── docling_extract.py                    (to be written)
│   ├── clause_extraction_prompts.py          (Claude API templates)
│   └── build_dashboard.py                    (demo generation)
├── data/
│   ├── raw/
│   │   └── (existing reference CSVs)
│   ├── pdfs/                                 (to be populated)
│   │   ├── ghana/
│   │   ├── zambia/
│   │   └── ...
│   └── processed/
│       ├── pdf_texts/                        (extracted text)
│       ├── clauses.jsonl                     (extracted clauses)
│       ├── clauses.db                        (SQLite index)
│       └── downloads.jsonl                   (metadata log)
├── analysis/
│   ├── cac_timeline.html                     (demo visualization)
│   ├── clause_comparison.html                (demo dashboard)
│   └── key_findings.md                       (summary)
├── logs/
│   └── nsm_downloader_2026-03-25.log         (processing logs)
└── Claude.md                                 (updated project state)
```

---

**Status:** Ready for Phase 1 (download pipeline) implementation.
**Next Action:** Write and test `nsm_downloader.py` on March 23, deploy to Mac Mini on March 24.
