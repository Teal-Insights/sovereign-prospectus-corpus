# CONTEXT PACK FOR COUNCIL OF EXPERTS
## Sovereign Bond Prospectus Corpus for #PublicDebtIsPublic Roundtable

**Prepared:** March 24, 2026  
**For:** Council-of-experts consultation across Claude Opus 4.6, ChatGPT Pro, and Gemini Pro Deep Think  
**Teal Insights** — Research consultancy, sovereign debt and climate finance  
**Deadline:** March 30, 2026 (Georgetown Law Roundtable)

---

## SECTION A: WHAT WE'RE BUILDING — PASTE THIS FIRST, ALWAYS

### The Core Project

**Name:** Sovereign Bond Prospectus Corpus — AI-enabled pipeline to download, process, and analyze sovereign bond prospectuses at scale.

**Core Problem:** Sovereign bond prospectuses are ~90% boilerplate. The ~10% that varies — Collective Action Clauses (CACs), pari passu language, events of default, governing law — is where research and policy value lives. Tracking this evolution across hundreds of near-identical documents currently requires manual review.

**Solution:** Build an automated pipeline that:
1. Downloads prospectuses from multiple venues (FCA NSM, SEC EDGAR, Luxembourg Stock Exchange, Euronext Dublin)
2. Extracts text and identifies contract clauses using Claude Code
3. Creates a searchable, queryable database enabling cross-document analysis
4. Demonstrates what transparency infrastructure for sovereign debt could look like

### Strategic Context: The #PublicDebtIsPublic Connection

**The Catalyst:** #PublicDebtIsPublic (PDIP) is Anna Gelpern's (Georgetown Law) platform covering 900 hand-annotated sovereign debt documents from 45+ countries. PDIP demonstrates proof-of-concept for transparency. BUT: it's a manual operation. Scaling it requires automation.

**Our Insight:** PDIP's 900 documents are a **validation set**. If we can build an AI-powered pipeline that replicates their clause annotations on new documents, we've solved the scaling problem. This corpus demonstrates that solution in practice.

**Why This Matters for the Roundtable:** The roundtable is convened by Anna Gelpern to scope "transparency infrastructure" for sovereign debt. We're proposing: automation is the missing piece. Humans annotated 900 documents. AI can annotate thousands.

### Who We Are

**Teal Insights:** Research consultancy specializing in sovereign debt and climate finance. We've worked on:
- **Q-CRAFT Explorer** (IMF Excel → Python conversion in ~1 week using council-of-experts methodology)
- **LIC-DSF Python Engine** (currently in planning, using the same council-based approach)
- **SovTech projects** (Uganda Ministry of Finance, IMF, World Bank)

**Our Methodology:** Rapid prototyping via AI-augmented development, council-of-experts feedback loops, golden master testing to catch regressions.

### Prior Art: Lessons from Q-CRAFT

The Q-CRAFT Explorer project (Q-Framework for Climate Risk Adaptation Finance Tools) succeeded in converting a complex IMF Excel model to maintainable Python in 7 days using this exact methodology:

1. **Council of experts** — Posed 7 core strategic questions to Claude + ChatGPT, got structured feedback on architecture
2. **Golden master testing** — Built small, high-quality examples first; used them to validate the full pipeline
3. **Thin vertical slices** — Completed one full pathway (Q1 → Q2 → Q3) before expanding to others
4. **Reproducibility** — Documented everything; code was git-tracked and version-controlled from day one

**Result:** In 7 days, we had a Python engine that matched the Excel model's outputs exactly, with comprehensive logging, error handling, and test coverage. The council feedback prevented 3 major architectural mistakes in days 2-3.

**This Project Uses the Same Playbook:** We're following the Q-CRAFT methodology here: council feedback on architecture, golden master examples, thin vertical slices, reproducible code.

### Timeline & Constraints

- **Duration:** 6 days (March 24-30, 2026)
- **Budget:** ~$0 marginal cost (Claude Max plan, ChatGPT Pro, Gemini — all unlimited)
- **Teal's Time:** Limited (other commitments); computer does heavy lifting
- **Compute:** Mac Mini M-series running 24/7 with unattended processing
- **Deliverable:** Compelling demo for a room of sovereign debt lawyers and policymakers
- **Success Definition:** Demonstrate capability to extract, analyze, and compare contract terms at scale

---

## SECTION B: THE EVENT AND AUDIENCE — PASTE WHEN DISCUSSING POSITIONING

### The Roundtable

**Event:** #PublicDebtIsPublic Scoping Roundtable  
**Date:** Monday, March 30, 2026  
**Venue:** Georgetown Law Center, Washington DC  
**Convener:** Anna Gelpern (Georgetown Law, PIIE), author of "If Boilerplate Could Talk" (seminal work on sovereign bond contract terms)  
**Co-Organizer:** Sovereign Debt Forum (SDF) — Georgetown Law + Queen Mary University of London  
**Audience:** ~40-50 people — sovereign debt lawyers, IMF/World Bank officials, policymakers, civil society researchers, academics  

### The Three Pillars Framework

The roundtable is organized around three "pillars" of transparency infrastructure:

1. **Information Infrastructure** — What counts as "debt"? What gets reported, to whom, in what format? How do we make data meaningful vs. just voluminous?

2. **Technology Infrastructure** — Can debt offices in low-income countries actually produce, store, and share authoritative information? Do the systems exist to handle complex documents, enable bulk export, support API access?

3. **Legal Infrastructure** — What treaties, laws, and institutional norms govern who discloses what? How can we close loopholes (like Goldman Sachs helping Greece hide debt via currency swaps)?

**Our Role:** We're addressing the technology infrastructure pillar. PDIP shows what the platform could look like. We're showing what the backend (AI-powered clause extraction, searchable databases) could enable.

### Key Message for the Room

> "Your 900 hand-annotated documents are a validation set. Here's what AI can do with that foundation. Here's how to scale transparency from 900 documents to 9,000."

---

## SECTION C: THE #PUBLICDEBTISPUBLIC PLATFORM — PASTE WHEN DISCUSSING PDIP

### Current State

**Platform:** https://publicdebtispublic.mdi.georgetown.edu/

**Coverage:** 45+ countries, 900+ debt documents, 100+ annotated contract terms  

**Funding:** $382,609 Gates Foundation grant, additional support from Netherlands Ministry of Finance  

**Pilot Phase:** 114 documents covering 20 countries (Africa, Asia, Europe, Caribbean, South America)  

**Features:**
- Full-text sovereign debt contracts searchable in one place
- Clause explainers — plain-language annotations of complex debt terms
- Search and comparison tools — identify patterns across countries and instruments
- Domestic laws and regulations — borrowing frameworks by country
- Capacity-building hub — tutorials, legal analysis, best practice guidance

### Key Capabilities & Limitations

**Strengths:**
- Authoritative documents, curated by law students and lawyers at Georgetown
- Plain-language explanations of contract terms make law accessible to non-lawyers
- Covers multiple document types: bonds, loans, bilateral agreements
- Geographic diversity (Africa, Asia, LATAM represented)

**Limitations (The Scaling Problem):**
- Manual annotation doesn't scale beyond ~1,000 documents
- No API or bulk export capability
- No cross-document aggregation (can search individual documents but hard to compare specific clauses across 20+ countries)
- Keyword search only; no structured clause extraction
- Closed platform — new documents require manual curation

**Where We Fit:** Our corpus solves these limitations by:
1. Automating clause extraction (Claude API can identify CACs, pari passu language, etc.)
2. Creating structured data (JSON, SQLite, queryable database)
3. Enabling bulk processing (500+ documents in 6 days, can scale to thousands)
4. Building reusable infrastructure (reproducible, open code on GitHub)

### Strategic Alignment

PDIP Director Katherine Shen and Anna Gelpern are aware of this project. The goal is not to compete with PDIP but to extend it — showing a path from 900 carefully-curated documents to AI-assisted analysis at scale.

---

## SECTION D: DATA SOURCES AND WHAT WE'VE FOUND — PASTE WHEN DISCUSSING TECHNICAL PIPELINE

### The FCA National Storage Mechanism (NSM)

**What It Is:** UK regulatory repository for all prospectuses/debt securities listed on UK exchanges or traded in the UK market.

**Access:** Free, public API (POST to https://api.data.fca.org.uk/search?index=fca-nsm-searchdata), no authentication required.

**Key Statistics:**
- **1,426 sovereign filings** across 46 countries
- **434 prospectus-type documents** (base prospectuses, supplements, final terms) from EM/frontier sovereigns
- **Top 5 EM Issuers:** Israel (148), Uzbekistan (63), Nigeria (43), Serbia (41), UAE-Abu Dhabi (37)

### Major Gaps: Sovereigns NOT in NSM

**Missing Major Issuers:** Argentina, Brazil, Colombia, Mexico, Indonesia, Philippines, Peru, Thailand, Vietnam

**Why?** These countries list in alternative venues:
- **SEC EDGAR** (US-registered 144A/Reg S offerings)
- **Luxembourg Stock Exchange** (primary venue for many LATAM sovereigns)
- **Euronext Dublin** (secondary venue for many issuers)

**Example: Senegal**
- Senegal NOT in NSM despite being a sovereign issuer
- Has three active Eurobonds listed on Euronext Dublin
- Located via separate research: XS1790104530 (EUR 1B, 4.75%, due 2028), XS1790134362 (USD 1B, 6.75%, due 2048), XS1619155564 (USD 1.1B, 6.25%, due 2033)
- Accessible directly from Euronext Dublin (no registration required)
- **Policy Relevance:** Senegal is in debt distress (131% debt-to-GDP, USD 13B hidden debt scandal March 2025); restructuring expected H2 2026. Having current prospectuses is critical.

### Secondary Venues (Phase 2)

1. **SEC EDGAR** — US Treasuries, Brazilian Eurobonds, Mexican bonds, etc.
2. **Luxembourg Stock Exchange** — European primary venue for many sovereigns
3. **Euronext Dublin** — Growing venue for West African, Caribbean sovereigns (Senegal, Côte d'Ivoire, Benin)

**For PoC (6 days):** Focus on NSM (easiest API). Mention secondary sources as expansion roadmap.

---

## SECTION E: PIPELINE ARCHITECTURE — PASTE WHEN DISCUSSING TECHNICAL DECISIONS

### Three-Stage Pipeline

**Stage 1: Download**
- Input: Sovereign issuer reference table (46 countries, 1,426 filings)
- Process: Query NSM API, handle two-hop URL resolution (HTML metadata page → actual PDF), download with exponential backoff and resumable checkpoints
- Output: 250-350 PDF files organized as `data/pdfs/{country}/{filename}`
- Metadata: SQLite database tracking download status, file hashes, errors

**Stage 2: Text Extraction & Clause Identification**
- Input: PDF files
- Tools: Docling (local PDF parser, superior to PyPDF2) + Claude Code (Opus 4.6) for clause identification
- Process: Extract full text from PDF (preserving section structure), prompt Claude to identify and extract CACs, pari passu, events of default, etc.
- Output: Structured JSON objects (one per document) with extracted clauses, confidence scores, page references
- Storage: `data/processed/clauses.jsonl` + SQLite index for querying

**Stage 3: Analysis & Visualization**
- Input: Extracted clause database
- Process: Cross-document comparison, timeline analysis (how do Ghana's CACs change pre- vs. post-restructuring?), statistical summaries
- Output: JSON exports, CSV files, HTML dashboard mockup, markdown case studies

### Storage Architecture

**File Organization:**
```
data/pdfs/{source}/{country}/
  ├── nsm/ghana/GH_2024-01-15_Base_Prospectus.pdf
  ├── nsm/zambia/ZM_2023-12-10_Prospectus.pdf
  └── ...

data/text/{source}/{country}/
  ├── nsm/ghana/GH_2024-01-15_Base_Prospectus.txt
  └── ...

data/processed/
  ├── clauses.jsonl (one JSON object per clause extraction)
  ├── clauses.db (SQLite FTS index)
  └── downloads.jsonl (metadata log)

data/db/
  └── prospectus_metadata.db (comprehensive record of all downloads)
```

**Metadata Database Schema:**
- `documents` table — one row per downloaded prospectus (source, country, issuer, date, file hash, processing status)
- `extracted_clauses` table — one row per identified clause (type, text, confidence, model used)
- `download_log` table — audit trail of all download attempts (timestamps, HTTP status, backoff delays)

### Development Practices

- **Language:** Python 3.10+
- **Package Manager:** uv (fast, reliable)
- **Linter/Formatter:** ruff
- **Version Control:** Git, trunk-based development (main branch always stable)
- **Dependencies:** requests, beautifulsoup4, docling, anthropic (Claude API), sqlite3
- **IDE:** VS Code
- **Style:** PEP 8, clean code, comprehensive logging

**Reproducibility:** Every download, extraction, and analysis step is logged. Checkpoint system allows resume from last successful download. Full command-line interface with help text and error messages.

---

## SECTION F: KEY REFERENCE PAPERS — PASTE FOR DOMAIN CONTEXT

### 9 Downloaded Papers: What Each Contributes

**1. Gelpern, "If Boilerplate Could Talk" (2019)**
- **Author:** Anna Gelpern (Georgetown Law)
- **Journal:** Law & Social Inquiry, Vol. 44, No. 3
- **Key Finding:** Standard terms in sovereign bonds change glacially (15+ years for pari passu reform) due to principal-agent misalignment, coordination problems, and fear that contract changes signal distress
- **Relevance to Corpus:** Explains why documenting contract term variation matters — standardization is path-dependent. Our corpus will show exactly this variation.

**2. World Bank Radical Debt Transparency Report (2025)**
- **Authors:** Diego Rivetti & David Mihalyi (World Bank)
- **Key Finding:** Major transparency deficiencies persist in developing countries. More information + robust data infrastructure can reduce risk premia, facilitate investment, reduce corruption
- **Relevance:** Directly frames the transparency infrastructure problem. Our corpus is a technology-infrastructure solution.

**3. Borensztein & Panizza, "Costs of Sovereign Default" (2009)**
- **Journal:** Journal of Development Economics
- **Key Finding:** Sovereigns repay not because courts can enforce (they can't — sovereigns are immune), but because defaults impose reputational costs. This constrains incentives endogenously.
- **Relevance:** Explains why transparency matters — information about default risk, contract terms, and hidden obligations directly affects default incentives through market signals.

**4. Der Spiegel, "How Goldman Sachs Helped Greece Mask Its True Debt" (2010)**
- **Key Finding:** Currency swaps and financial engineering enabled Greece to hide ~€2.8B debt from Eurostat, satisfying Maastricht criteria while concealing true fiscal position
- **Relevance:** Canonical example of why transparency infrastructure matters. Prospectuses themselves may not reveal hidden debt.

**5. Chatterjee & Eyigungor, "A Seniority Arrangement for Sovereign Debt" (2015)**
- **Journal:** Journal of Economic Theory
- **Key Finding:** Creditors worry about debt dilution (future borrowing that reduces repayment probability). Explicit seniority rules could reduce default rates.
- **Relevance:** Contract design matters for incentives. Our corpus will show how seniority language varies (or doesn't).

**6. Flandreau, Pietrosanti & Schuster, "Sovereign Collateral" (2024)**
- **Journal:** Journal of Economic History, Vol. 84, No. 1
- **Key Finding:** Collateralization in 19th-century sovereign debt functioned as information signal, not asset seizure (sovereignty prevents seizure). Modern collateralization persists despite these constraints.
- **Relevance:** Historical perspective on how contract design addresses information asymmetry. Our corpus will show modern collateral language.

**7. IMF/World Bank, "Collateralized Transactions" (2023)**
- **Prepared for:** G20
- **Key Finding:** Collateral in sovereign lending can be problematic if it weakens debt sustainability. Transparency and negative pledge clauses are essential.
- **Relevance:** Policy framework for responsible collateral use. Our corpus can measure collateral prevalence across sovereigns.

**8. Goldman Sachs/Der Spiegel, Greece Hidden Debt Case Study**
- **Key Finding:** (See #4 above) Canonical example of information opacity in sovereign debt
- **Relevance:** Real-world consequence of lack of transparency infrastructure

**9. World Bank, "Bank Failures Amid Sovereign Defaults" (2025)**
- **Authors:** Miquel Dijkman, Rafel Moyà Porcel, Cédric Mousset (World Bank)
- **Key Finding:** Sovereign fiscal stress and banking-sector vulnerability are interconnected in emerging markets. Opacity in sovereign obligations exacerbates financial contagion.
- **Relevance:** Explains why sovereign debt transparency has systemic implications beyond government finances.

### Connection to Our Work

All 9 papers converge on one point: **Information asymmetry in sovereign debt is the root problem.** Contract terms, hidden obligations, and complex instruments conceal true fiscal positions. Our corpus makes those contract terms visible, comparable, and analyzable.

---

## SECTION G: WHAT'S BEEN DONE SO FAR — PASTE TO AVOID RE-DERIVING

### Phase 0: Complete (March 23, 2026)

**What We've Accomplished:**

1. **API Discovery & Documentation**
   - Reverse-engineered FCA NSM Elasticsearch API
   - Documented full endpoint, request/response formats, field reference
   - Confirmed: public, unauthenticated, no rate limiting observed
   - Full reference doc in `docs/nsm_api_reference.md`

2. **Sovereign Issuer Census**
   - Executed 156 unique search queries covering sovereigns worldwide
   - Found: 1,426 sovereign filings across 46 countries
   - Built canonical `sovereign_issuer_reference.csv` with name variants, LEIs, filing counts
   - Classified 1,426 filings into 7 issuer types (sovereign, SPV, agency, quasi-sovereign, EU, UK, DM)

3. **Gap Analysis**
   - Identified major sovereigns NOT in NSM: Argentina, Brazil, Colombia, Mexico, Indonesia, Philippines, Peru, Thailand, Vietnam
   - Located secondary sources: SEC EDGAR, Luxembourg Stock Exchange, Euronext Dublin
   - Senegal research complete — all 3 Eurobonds accessible via Euronext Dublin

4. **Documentation**
   - `Claude.md` — Project overview and context (this is the source of this section)
   - `LOG.md` — Detailed session log of all Phase 0 work
   - `docs/nsm_api_reference.md` — Full API documentation
   - `docs/senegal_west_africa_research.md` — Regional sovereign bond landscape
   - `docs/proof_of_concept_strategy.md` — Full PoC strategy for roundtable
   - `docs/pipeline_architecture.md` — Technical architecture document (predecessor to this council brief)

5. **Data Files Created**
   - `data/raw/sovereign_issuer_reference.csv` — Country reference table (46 countries, 108 name variants, LEI mappings)
   - `data/raw/nsm_sovereign_filings_normalized.csv` — All 1,426 filings with normalization
   - `data/raw/nsm_sovereign_filings_all.json` — Raw API results

### Key Phase 0 Findings

**Prospectus-Type Documents:** 434 found (base prospectuses, supplements, final terms) from EM/frontier sovereigns. These are the highest-value targets for clause analysis.

**Name Normalization Challenge:** Same sovereign appears under 2-5+ name variants in NSM. This must be solved before bulk processing.

**LEI as Deduplication Key:** 52% of sovereign filings have LEIs. Where present, LEI is the most reliable deduplication mechanism.

**Senegal Discovery:** Outside NSM but fully accessible via Euronext Dublin. Three active bonds (2028, 2033, 2048 maturities) with complete prospectus packages publicly downloadable. High policy relevance: debt distress, restructuring imminent, hidden debt scandal.

### Ready for Phase 1

All groundwork complete. We have:
- [ ] Complete sovereign issuer mapping
- [ ] API fully reverse-engineered and documented
- [ ] Secondary data source paths identified
- [ ] Senegal case study ready to download
- [ ] Architectural decisions made (SQLite, Docling, Claude API)

**Phase 1 (March 24-26):** Download pipeline implementation and execution  
**Phase 2 (March 27-29):** Clause extraction and analysis  
**Phase 3 (March 30):** Demo prep and roundtable presentation

---

## SECTION H: CONSTRAINTS AND SUCCESS CRITERIA — PASTE WHEN DISCUSSING PRIORITIZATION

### Hard Constraints

**Timeline:** 6 days (March 24-30, 2026)
- Monday morning through Sunday evening
- Roundtable presentation Monday, March 30

**Budget:** ~$0 marginal cost
- Claude Max plan (unlimited, $20/month) — already subscribed
- ChatGPT Pro (unlimited, $20/month) — already subscribed
- Gemini Pro (unlimited via research access)
- Mac Mini hardware (already owned, running 24/7)
- No external infrastructure costs

**Human Time:** Limited
- Teal has other committed work (AI Evals course, GSDR, LIC-DSF Python project)
- Computer does heavy lifting via unattended processing
- Teal involvement: architecture decisions, exception handling, demo rehearsal
- Estimated: 15-20 hours total from Teal

**Compute:** Mac Mini M-series, 24/7 operation
- Must support parallel downloads + text extraction + API calls
- Reliable power (configured to not sleep)
- Network connectivity essential

**Tools:** Python 3.10+, uv, ruff, VS Code, Claude Code, ChatGPT Pro

### Success Criteria for March 30

**Threshold Requirements (MUST HAVE):**
1. **Sheer scale demonstrated:** 500+ prospectuses downloaded, inventory visible
2. **Quality examples:** 2-5 deeply processed documents with extracted clauses shown
3. **Narrative connection to PDIP:** Clear explanation of how corpus extends PDIP's 900 documents
4. **Technical credibility:** Documented architecture, reproducible pipeline, code available on GitHub

**Desirable (NICE TO HAVE):**
- Senegal or Ghana case study with clause evolution analysis
- Comparison: PDIP's manual annotations vs. AI-extracted clauses (accuracy assessment)
- Searchable database prototype (Jupyter notebook or simple web interface)
- Timeline visualization: CAC adoption post-2014

**Stretch Goal:**
- All 434 prospectus-type documents processed with clause extractions ready for live query
- Dashboard showing cross-country clause variation
- Integration roadmap proposing how PDIP could adopt this infrastructure

### What We're NOT Doing (Out of Scope)

- Full-text search engine or large-scale deployment
- Proprietary model training (using Claude API, not custom models)
- SEC EDGAR integration (Phase 2)
- Live web app (static exports and Jupyter notebooks sufficient)
- Comprehensive validation against PDIP's 900 documents (that's post-roundtable work)

### Why This Timeline Works

**Physics of the Pipeline:**
- **Download:** 250-350 PDFs, average 2 MB each = ~750 MB total. At 100 KB/s (conservative), ~2 hours for all downloads. Exponential backoff adds wait time; total 36-48 hours of wall time, but machine runs 24/7.
- **Text Extraction:** 350 PDFs × Docling (~30 seconds per document) = 3 hours of serial computation. Can parallelize somewhat.
- **Clause Extraction:** 350 PDFs × Claude API (~2-3 minutes per document, accounting for token counting and model latency) = 1,000-1,750 minutes = 17-29 hours of serial time. Batching 10 documents in parallel reduces to 2-3 hours wall time.
- **Total Wall Time:** 36-48 hours for downloads + 2-3 hours extraction + 17-29 hours clause extraction ≈ 60 hours. With 24/7 Mac Mini, this completes by Thursday evening.
- **Buffer:** Friday (March 27) + weekend for analysis, dashboard, and rehearsal.

**No Bottlenecks:** The limiting factor is not human time or compute; it's API latency (Claude, NSM). We've accounted for both.

---

**END OF CONTEXT PACK**

*This document is designed to be modular. Paste the relevant section(s) when consulting the council on specific topics. Each section is self-contained and labeled for ease of reference.*

