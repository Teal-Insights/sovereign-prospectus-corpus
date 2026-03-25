# CONTEXT PACK FOR COUNCIL OF EXPERTS — ROUND 2
## Scaling Aggressively: Parallel Bulk Download from FCA + EDGAR Overnight

**Prepared:** March 24, 2026 (evening)
**For:** Council consultation across Claude Opus 4.6, ChatGPT Pro, and Gemini Pro Deep Think
**Teal Insights** — Research consultancy, sovereign debt and climate finance
**Deadline:** March 30, 2026 (Georgetown Law Roundtable)

---

## HOW THIS DIFFERS FROM ROUND 1

Round 1 addressed architecture, prioritization, and framing. Those decisions are ratified and implemented. Round 2 is purely operational: **how to download hundreds of documents overnight from two different sources, running in parallel, and process them at scale.**

---

## SECTION A: WHAT WE'VE BUILT (PASTE FIRST, ALWAYS)

### Pipeline Status: Validated End-to-End

```
Download PDF → Extract text (PyMuPDF, 0.65s/252pp) → Grep-locate clauses (regex) →
Extract verbatim quotes → Verify (assert exact_quote in raw_pdf_text)
```

**Corpus (current):** 7 documents, 3 countries (Ghana, Senegal, Zambia), 1,219 pages, 740,633 words, 67 verified clause extractions (100% verification rate).

**Cost:** $0 for extraction (Claude Code CLI on Max plan + PyMuPDF + regex). $1.50 for LLM classification of 18,000 Chinese lending records in a comparable project (ODI paper). Scale is cheap.

### Current Code

**`nsm_downloader.py` (~490 lines):**
- `requests.Session` with retry adapter (5 retries, 0.5s backoff, retries on 429/500/502/503/504)
- Pagination: `from`/`size` with size=100
- Two-hop URL resolution: HEAD check → if HTML, parse with BeautifulSoup for PDF link
- PDF validation: `b"%PDF"` header check
- Checkpointing: JSON file, saved after each document
- Metadata logging: JSONL
- Delays: 0.1s between docs, 2s between countries
- User-Agent: `"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"`

**`clause_extractor.py` (~570 lines):**
- 10 clause types with compiled regex patterns
- Page clustering for section identification
- Verbatim extraction with sentence-boundary trimming (max 3000 chars)
- Verification: `assert first_200_chars in full_text`
- SQLite with WAL mode: `documents`, `clause_extractions`, `grep_matches`, `pipeline_log`
- Status tracking: PENDING → DOWNLOADING → DOWNLOADED → PARSING → PARSED → EXTRACTING → EXTRACTED

---

## SECTION B: FCA NSM — FULL TECHNICAL DETAILS (PASTE FOR FCA QUESTIONS)

### API
- **Endpoint:** `POST https://api.data.fca.org.uk/search?index=fca-nsm-searchdata`
- **Auth:** None required
- **Pagination:** `from`/`size` — tested up to 10,000+. For deeper: `search_after` + PIT
- **Rate limits:** None published. Related FCA API (FS Register) = 10 req/10 sec. Our Phase 0 ran 156 queries without any throttling

### robots.txt (Fetched today)
```
User-agent: *
Content-Signal: search=yes, ai-train=no
Allow: /

User-agent: ClaudeBot
Disallow: /
User-agent: GPTBot
Disallow: /
```
**Interpretation:** Search/research OK. AI model training prohibited. We're extracting for policy research.

### Terms of Use
- `NSM_Terms_of_Use.pdf` and `NSM_General_AUP.pdf` exist
- AUP prohibits: unauthorized access, DDoS, malicious content
- No explicit prohibition on programmatic research access
- No published rate limit numbers

### Download Mechanics
- ~44% of links → direct PDF download
- ~55% of links → HTML metadata page → parse → find PDF link
- URL pattern: `https://data.fca.org.uk/artefacts/{download_link}`
- PDF validation: `b"%PDF"` in first 4 bytes

### Document Type Codes (Prospectus-Relevant)
| Code | Type | Count in Corpus |
|------|------|----------------|
| PDI | Publication of a Prospectus | ~200 |
| FCA01 | Base Prospectus | ~80 |
| PSP | Supplementary Prospectus | ~50 |
| PFT | Final Terms | ~120 |

### Full NSM Inventory by Country (Prospectus-Type Docs Only)

**Tier 1 — Defaulted / Distressed:**
- Ghana: 20 prospectus docs (28 total filings)
- Ukraine: 4 (21 total)
- Zambia: 2 (28 total) — already downloaded both
- Belarus: 2 (2 total)
- Gabon: 1 (3 total)
- Sri Lanka: 0 prospectus docs (11 total filings — other types only)
- Congo: 0 (3 total)

**Tier 2 — Frontier/EM Sub-Investment Grade:**
- Nigeria: 40 (43 total) — LARGEST EM issuer in NSM
- Egypt: 35 (36 total)
- Angola: 14 (17 total)
- Montenegro: 12 (16 total)
- Kenya: 5 (19 total)
- Bahrain: 5 (9 total)
- Albania: 3 (7 total)
- Jordan: 2 (4 total)
- Cameroon: 2 (2 total)
- Morocco: 2 (2 total)
- Rwanda: 1 (2 total)
- Bosnia and Herzegovina: 1 (1 total)
- Srpska: 1 (1 total)

**Tier 3 — EM Investment Grade / Gulf:**
- UAE - Abu Dhabi: 35 (37 total)
- Serbia: 24 (41 total)
- Saudi Arabia: 23 (27 total)
- Kazakhstan: 22 (29 total)
- Uzbekistan: 21 (63 total)
- Oman: 16 (25 total)
- Qatar: 10 (10 total)
- Kuwait: 4 (5 total)

**Tier 4 — Developed Markets (control group):**
- Israel: 126 (148 total) — BY FAR largest single issuer
- Sweden: 7 (64 total)
- Hungary: 5 (30 total)
- Cyprus: 5 (24 total)
- Canada: 2 (2 total)
- Finland: 2 (36 total)
- Iceland: 1 (36 total)

**UK excluded:** 560 filings, 0 prospectus-type (all gilt "Issue of Debt")

**TOTAL: ~455 prospectus-type documents to download**

---

## SECTION C: SEC EDGAR — WHAT WE KNOW (PASTE FOR EDGAR QUESTIONS)

### Rate Limits (Strictly Enforced)
- **10 requests per second** — IP-based, hard limit
- **Penalty:** 10-minute IP block. Continued violation extends block
- **Recovery:** Automatic after 10 min below threshold

### User-Agent (Mandatory)
```
User-Agent: Teal Insights lte@tealinsights.com
```
SEC requires company/project name + contact email. They use it to contact developers.

### Sovereign Filer Discovery
- **SIC code 8888** = "Foreign Governments" — filter for sovereign issuers
- **Known CIKs:** Mexico (101368), Brazil (205317)
- **Submission data:** `data.sec.gov/submissions/CIK##########.json` per filer
- **Bulk archive:** `submission.zip` at data.sec.gov (all filing metadata, updated nightly)
- **Full-text search:** EFTS API for finding sovereign filings

### Form Types
| Form | Description | Relevance |
|------|-------------|-----------|
| 424B2 | Prospectus supplement (shelf registration) | PRIMARY — contains actual bond terms |
| 424B5 | Prospectus supplement (final) | PRIMARY — final terms |
| 18-K | Annual report (foreign governments) | Context — debt composition, economy |
| 18 | Registration statement | Context — initial filing |
| F-1/F-3 | Registration (foreign private) | Less common for sovereigns |

### Key Differences from FCA NSM
| Feature | FCA NSM | SEC EDGAR |
|---------|---------|-----------|
| Auth | None | User-Agent mandatory |
| Rate limit | None observed | 10 req/sec (enforced) |
| Penalty | Unknown | 10-min IP block |
| URL resolution | 2-hop (HTML→PDF) | Multi-step (CIK→Submissions→File) |
| Governing law | English law | New York law |
| Expected sovereign docs | 455 identified | Unknown — likely 200-500 |

### Expected EDGAR Sovereign Issuers
Major EM issuers NOT in FCA NSM: Argentina, Brazil, Mexico, Colombia, Indonesia, Philippines, Peru, Chile, Turkey, South Africa, Panama, Dominican Republic, El Salvador, Jamaica, Trinidad & Tobago, Ecuador, Bolivia, Paraguay, Costa Rica, Guatemala, Honduras.

These are primarily New York law bonds — the other major governing law jurisdiction. Comparing English law (NSM) vs. New York law (EDGAR) across the same issuer is analytically valuable.

---

## SECTION D: CURRENT DATABASE SCHEMA (PASTE FOR ARCHITECTURE QUESTIONS)

```sql
documents (
    id TEXT PRIMARY KEY,
    country TEXT,
    issuer TEXT,
    lei TEXT,
    doc_type TEXT,
    headline TEXT,
    source TEXT,           -- 'nsm', 'edgar', 'euronext'
    source_url TEXT,
    pdf_url TEXT,
    local_path TEXT,
    text_path TEXT,
    filing_date TEXT,
    submitted_date TEXT,
    file_size_bytes INTEGER,
    file_hash TEXT,
    page_count INTEGER,
    word_count INTEGER,
    status TEXT,           -- PENDING/DOWNLOADING/DOWNLOADED/PARSED/EXTRACTED/FAILED
    quarantine_reason TEXT,
    family_id TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

grep_matches (
    document_id TEXT REFERENCES documents(id),
    clause_type TEXT,
    page_number INTEGER,
    match_count INTEGER,
    sample_matches TEXT   -- JSON array
)

clause_extractions (
    id INTEGER PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    clause_type TEXT,
    verbatim_quote TEXT,
    page_number INTEGER,
    page_range_start INTEGER,
    page_range_end INTEGER,
    context_before TEXT,
    context_after TEXT,
    confidence REAL,
    verified_by TEXT,
    verified_at TIMESTAMP,
    extraction_model TEXT,
    extraction_prompt_version TEXT,
    notes TEXT,
    created_at TIMESTAMP
)

pipeline_log (
    document_id TEXT REFERENCES documents(id),
    action TEXT,
    status TEXT,
    details TEXT,          -- JSON
    duration_seconds REAL
)
```

**Pragmas:** `PRAGMA journal_mode=WAL`

**Known issue:** SQLite does NOT work on Google Drive File Stream (I/O errors). Must use local disk.

---

## SECTION E: EMPIRICAL TIMING DATA (PASTE FOR PERFORMANCE QUESTIONS)

### From the 7-Document Run

| Step | Time per Doc | Notes |
|------|-------------|-------|
| NSM API query | ~1-2s | Per country, 100 results |
| PDF download | 5-30s | 78KB to 2.1MB |
| Two-hop resolution | 2-5s | Extra HTTP + HTML parse |
| PyMuPDF text extraction | 0.3-0.7s | Linear with page count |
| Grep scan (10 types) | <0.1s | Pure regex |
| Clause extraction (per type) | 0.5-2s | Section size dependent |
| Verification | <0.01s | String containment |
| Full pipeline (download→extract) | 30-90s | Download-dominated |

### Projected at 455 NSM Documents
- **Download (sequential, 1 req/sec):** ~2-3 hours
- **Text extraction:** ~4 minutes
- **Grep + Group A:** ~8 minutes
- **Total (sequential):** ~3 hours
- **With parallel NSM + EDGAR:** Both could finish overnight easily

### File Sizes (from 7 docs)
- Smallest: 78KB (1 page)
- Largest: 2.1MB (232 pages)
- Average: ~1.2MB (~170 pages)
- Estimated total for 455 docs: ~500MB-800MB

---

## SECTION F: PROCESSING TIERS (PASTE FOR PIPELINE QUESTIONS)

### Group A — Bulk (all documents, no LLM, regex + PyMuPDF only)

| Feature | Method | Time/Doc |
|---------|--------|----------|
| Text extraction | PyMuPDF | 0.3-0.7s |
| Page count, word count | Built-in | <0.01s |
| Grep scan (10 clause types) | Compiled regex | <0.1s |
| Governing law | Regex | <0.01s |
| Law firm (issuer) | Regex | <0.01s |
| Law firm (managers) | Regex | <0.01s |
| Fiscal agent | Regex | <0.01s |
| ISINs | Regex | <0.01s |
| Listing exchange | Regex | <0.01s |
| File hash (MD5) | hashlib | <0.01s |

**Total Group A for 455 docs: ~8 minutes**

### Group B — Deep Analysis (selected documents, may use LLM)

- Verbatim clause extraction (5-20s per doc)
- Risk factor analysis (LLM, 30-60s)
- Debt composition tables (Docling, 30-120s)
- Chinese lending mentions (grep + context)
- Cross-document diffing

### Group A → Rectangular Dataset

After Group A on all documents:
```
doc_id | source | country | issuer | filing_date | doc_type | pages | words |
governing_law | law_firm_issuer | law_firm_managers | fiscal_agent |
listing_exchange | isins | arrangers | currency | credit_tier |
has_cac | cac_pages | has_pari_passu | has_eod | has_neg_pledge |
has_sov_immunity | has_cross_default | has_ext_indebtedness |
has_acceleration | has_trustee_fa | estimated_tokens
```

This alone — before any Group B work — is analytically interesting and demonstrable at the roundtable.

---

**END OF CONTEXT PACK — ROUND 2**

*Focused on what the council needs: API details, data inventory, timing, architecture. Domain questions are handled by the domain expert.*
