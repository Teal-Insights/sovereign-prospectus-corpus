# Project Deliverables Index
## Sovereign Bond Prospectus Corpus — Complete Documentation

**Last Updated:** March 24, 2026  
**Project Status:** Ready for Phase 1 Execution  
**Next Milestone:** March 30, 2026 — Georgetown Law Roundtable Presentation

---

## Quick Navigation

### 📋 Start Here
- **[Claude.md](./Claude.md)** — Project overview, context, accomplishments to date, data sources
- **[EXECUTION_PLAN.md](./EXECUTION_PLAN.md)** — Day-by-day execution checklist for March 24-29
- **[RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md)** — Background on CACs, restructuring cases, PDIP context

### 📖 Core Strategy Documents
- **[docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md)** (420 lines)
  - Full PoC rationale and design
  - Countries to prioritize & clause extraction strategy
  - Download pipeline architecture
  - Demo & visualization plans
  - Timeline & risk mitigation
  - Success criteria

- **[docs/nsm_api_reference.md](./docs/nsm_api_reference.md)**
  - Complete NSM API documentation
  - Request/response schemas
  - Field reference & type codes
  - Python examples

### 🐍 Production Scripts
- **[scripts/nsm_downloader.py](./scripts/nsm_downloader.py)** (491 lines)
  - Main download pipeline
  - Handles two-hop PDF resolution
  - Resumable with checkpoints
  - Production-ready error handling
  - Status: Ready to run on Mac Mini

- **[scripts/clause_extraction_templates.py](./scripts/clause_extraction_templates.py)** (333 lines)
  - Standardized Claude API prompts
  - Tier 1 clauses (CACs, pari passu, events of default)
  - Tier 2 clauses (negative pledge, governing law)
  - Batch extraction & refinement prompts
  - Status: Ready for integration

- **[scripts/README.md](./scripts/README.md)** (423 lines)
  - Complete scripts documentation
  - Setup instructions & dependencies
  - Usage examples for each script
  - Configuration reference
  - Troubleshooting guide
  - Performance optimization tips

### 📊 Data Directory Structure
```
data/
├── raw/
│   ├── sovereign_issuer_reference.csv        (reference table: countries → LEIs, variants)
│   ├── nsm_sovereign_filings_normalized.csv  (all 1,426 NSM filings)
│   └── nsm_api_sovereign_search_results.json (raw API responses)
├── pdfs/
│   ├── ghana/                                (to be populated)
│   ├── zambia/
│   └── ...
└── processed/
    ├── downloads.jsonl                       (metadata for each downloaded PDF)
    ├── download_checkpoint.json              (resumable checkpoint)
    ├── pdf_texts/                            (extracted text from PDFs)
    └── clauses.jsonl                         (extracted clauses)
```

### 📝 Key Output Files (Generated During Execution)

During Phase 1-4 execution (March 24-29), the following files will be created:

| File | Phase | Purpose | Format |
|------|-------|---------|--------|
| `data/pdfs/{country}/*.pdf` | 1 | Downloaded prospectuses | Binary PDF |
| `data/processed/downloads.jsonl` | 1 | Metadata for each PDF | JSON Lines |
| `data/processed/pdf_texts/{country}/*.txt` | 2 | Extracted text | Plain text |
| `data/processed/clauses.jsonl` | 3 | Extracted clauses | JSON Lines |
| `data/processed/clauses.db` | 3 | SQLite index of clauses | SQLite |
| `analysis/clause_comparison.html` | 4 | Interactive dashboard | HTML + JS |
| `analysis/cac_timeline.html` | 4 | CAC adoption timeline | HTML + D3.js |
| `logs/nsm_downloader_*.log` | 1 | Execution logs | Plain text |

---

## Document Summary by Use Case

### For Executing the PoC (March 24-29)

**Start with:**
1. [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) — Day-by-day checklist
2. [scripts/README.md](./scripts/README.md) — Setup & installation
3. [scripts/nsm_downloader.py](./scripts/nsm_downloader.py) — Main script to run

**Reference during execution:**
- [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) — For understanding pipeline decisions
- `logs/nsm_downloader_*.log` — For monitoring progress & troubleshooting

### For Understanding the Research (Before Roundtable)

**Start with:**
1. [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md) — Policy background & context
2. [Claude.md](./Claude.md) — Project overview
3. [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) — Connection to #PublicDebtIsPublic

**For deep dives:**
- [docs/nsm_api_reference.md](./docs/nsm_api_reference.md) — If you want to understand NSM data
- Individual sovereign case studies — See RESEARCH_CONTEXT.md sections 3-4

### For Extending the Project (Phase 2+)

**Start with:**
1. [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) sections 8-10 (timeline, success criteria, repository structure)
2. [scripts/README.md](./scripts/README.md) section "Contributing & Extending"
3. [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) section "Post-Roundtable"

**For secondary sources (Luxembourg, Euronext, SEC):**
- See Phase 0 notes in [Claude.md](./Claude.md) for known gaps

---

## Data Sources & Coverage

### Primary Source: FCA NSM (Phase 0 Complete)

| Metric | Value | Status |
|--------|-------|--------|
| Total filings searched | 1,426 | Complete |
| Countries represented | 46 | Complete |
| Prospectus-type documents | 434 | Subset for PoC |
| Coverage by PoC countries | 272 prospectuses | Ready for download |
| Date range | 2013-2026 | Includes recent issuances |

**Priority countries identified:**
- Ghana (28 filings) — Restructured 2024
- Zambia (28 filings) — Restructured 2024
- Sri Lanka (11 filings) — Restructured 2024
- Ukraine (21 filings) — Ongoing crisis
- Kenya (19 filings) — Active issuer
- Nigeria (43 filings) — Largest EM issuer
- Serbia (41 filings) — Strong CAC example
- UAE-Abu Dhabi (37 filings) — GCC sovereign
- Saudi Arabia (27 filings) — Major issuer
- Angola (17 filings) — Post-restructuring

### Secondary Sources (Phase 0, Identified but not yet integrated)

| Source | Countries | Status | Notes |
|--------|-----------|--------|-------|
| Luxembourg Stock Exchange | 70+ countries | Identified | Requires web scraping or API |
| Euronext Dublin | 30+ countries | Identified | Requires web scraping or API |
| SEC EDGAR | Mainly US-listed EM bonds | Identified | API available |
| National debt offices | Country-specific | Not systematically addressed | Future research |

**Key missing countries (for future phases):**
- Argentina, Brazil, Colombia, Mexico, Indonesia, Philippines

---

## Research Questions & Expected Findings

### Q1: How widely adopted are enhanced CACs post-2014?

**Expected answer:** 80-90% of post-2014 issuances use enhanced aggregated CACs, but implementation varies (some weak hybrids remain).

**Deliverable:** Timeline visualization showing CAC type distribution over time.

---

### Q2: Did recent restructurings (Ghana, Zambia, Sri Lanka) change sovereign bond contract terms?

**Expected answer:** Yes. Post-restructuring sovereigns show modified pari passu language (more creditor-favorable) but maintain or strengthen CACs.

**Deliverable:** Side-by-side comparison of pre/post-restructuring prospectus excerpts.

---

### Q3: What are the most common pari passu implementations?

**Expected answer:** 70% use modified pari passu with official creditor carve-outs; 25% have stricter language; 5% subordinated.

**Deliverable:** Pie chart & taxonomy of pari passu language variants.

---

### Q4: Is transparent, machine-readable sovereign debt infrastructure feasible?

**Expected answer:** Yes, at ~$300 for 250 documents, with 48-hour processing time and < 1 week total pipeline time.

**Deliverable:** Cost/timeline estimates and proof-of-concept dashboard.

---

## Key Metrics & Success Criteria

### By March 29, 2026, Success Looks Like:

| Metric | Target | Status |
|--------|--------|--------|
| Prospectuses downloaded | 250-350 | In progress (Phase 1) |
| Clauses extracted | 200+ (80% coverage) | In progress (Phase 3) |
| Dashboard interactive | Yes | Planned (Phase 4) |
| Research findings documented | 3-4 key findings | Planned (Phase 4) |
| PDIP integration proposal | 1-page document | Planned (Phase 4) |
| Scripts tested & logged | All 3 scripts | Tested (nsm_downloader.py) |
| Repository complete & documented | All files + README | In progress |

### By March 30, 2026, Roundtable Presentation Success Looks Like:

- [ ] Live demo of dashboard with 3-4 example comparisons
- [ ] 1-minute summary of key finding #1 (CAC adoption)
- [ ] 1-minute summary of key finding #2 (restructuring impact)
- [ ] 1-minute explanation of PDIP integration opportunity
- [ ] 2-3 minutes Q&A with Anna Gelpern and roundtable participants
- [ ] Offline backup demo (PDFs, screenshots) in case network fails

---

## File Manifest (Complete List)

### Documentation Files
- [ ] Claude.md (project overview)
- [ ] LOG.md (session-by-session log from Phase 0)
- [ ] EXECUTION_PLAN.md (day-by-day checklist)
- [ ] RESEARCH_CONTEXT.md (policy background)
- [ ] INDEX.md (this file)

### Strategy & Reference
- [ ] docs/proof_of_concept_strategy.md (420 lines)
- [ ] docs/nsm_api_reference.md (existing, comprehensive)
- [ ] docs/ROUNDTABLE_BRIEFING.md (to be written during Phase 4)
- [ ] docs/pdip_integration_proposal.md (to be written during Phase 4)

### Scripts
- [ ] scripts/nsm_downloader.py (491 lines, production-ready)
- [ ] scripts/clause_extraction_templates.py (333 lines, production-ready)
- [ ] scripts/README.md (423 lines, complete)
- [ ] scripts/docling_extract.py (to be written during Phase 2)
- [ ] scripts/extract_clauses.py (to be written during Phase 3)
- [ ] scripts/build_dashboard.py (to be written during Phase 4)

### Data Files
- [ ] data/raw/sovereign_issuer_reference.csv
- [ ] data/raw/nsm_sovereign_filings_normalized.csv
- [ ] data/raw/nsm_api_sovereign_search_results.json
- [ ] (Generated during execution: PDFs, metadata, clauses, etc.)

### Generated Outputs (To Be Created)
- [ ] analysis/clause_comparison.html
- [ ] analysis/cac_timeline.html
- [ ] analysis/events_of_default_matrix.html
- [ ] logs/nsm_downloader_*.log
- [ ] data/processed/clauses.db
- [ ] data/processed/clauses.jsonl

---

## How to Use This Index

### Scenario 1: "I'm Teal. I need to execute starting tomorrow."

1. Read [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) — covers everything you need to do
2. Read [scripts/README.md](./scripts/README.md) — setup instructions
3. Run: `python scripts/nsm_downloader.py`
4. Reference [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) if you have questions about design

### Scenario 2: "I'm attending the roundtable. I want to understand the research."

1. Read [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md) — sections 1-6
2. Skim [Claude.md](./Claude.md) — for project scope
3. Read section 9 of [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md) — "Talking Points for the Roundtable"

### Scenario 3: "I'm a policymaker. I want to know what this enables."

1. Read [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md) section 6 — "PDIP Integration"
2. Read [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) section 5 — "Demo & Visualizations"
3. See section 9 of [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md) — "Key Findings" and "Call to Action"

### Scenario 4: "I want to extend this to secondary sources (Luxembourg, etc.)."

1. Read [EXECUTION_PLAN.md](./EXECUTION_PLAN.md) section "Post-Roundtable"
2. Review [docs/proof_of_concept_strategy.md](./docs/proof_of_concept_strategy.md) section 4 — "Download & Processing Pipeline" for secondary sources
3. Study [scripts/README.md](./scripts/README.md) section "Contributing & Extending"
4. Reference [Claude.md](./Claude.md) Phase 0 notes for research on other venues

---

## Contact & Support

**Project Lead:** Teal Emery  
**Email:** lte@tealinsights.com  

**For Questions About:**
- **Execution & scripts:** See [scripts/README.md](./scripts/README.md) troubleshooting section
- **Research & policy context:** See [RESEARCH_CONTEXT.md](./RESEARCH_CONTEXT.md)
- **Project scope & rationale:** See [Claude.md](./Claude.md)
- **Timeline & deliverables:** See [EXECUTION_PLAN.md](./EXECUTION_PLAN.md)

---

## Acknowledgments

**This PoC is built on:**
- Anna Gelpern's research on sovereign debt contracts and CACs
- The #PublicDebtIsPublic platform's transparency mission
- The FCA National Storage Mechanism's public data
- The Anthropic Claude API for clause extraction

**Special thanks to:**
- Anna Gelpern (Georgetown Law) — for the roundtable opportunity and research inspiration
- The Sovereign Debt Forum community — for context on recent restructurings

---

**Project Status:** ✅ Ready for Phase 1 Execution  
**Next Update:** March 25, 2026 (first progress report during Phase 1)

