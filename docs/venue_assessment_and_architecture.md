# Venue Assessment & Architectural Recommendations

**Date:** 2026-03-23
**Status:** Initial assessment — needs validation against actual document downloads

---

## Venue Difficulty Ranking

### Tier 1: Easy — Programmatic API, no auth, structured data

**FCA National Storage Mechanism (NSM)**
- Unauthenticated Elasticsearch API (`api.data.fca.org.uk/search`)
- POST JSON, get structured JSON back, up to 10k results per query
- No rate limiting observed
- Direct PDF links for ~44% of filings; HTML metadata pages for the rest (one extra hop)
- We already have 1,426 sovereign filings catalogued across 46 countries
- **Limitation:** Missing most major EM issuers (Argentina, Brazil, Colombia, Mexico, Indonesia, Philippines, Peru). These list elsewhere.

**SEC EDGAR**
- EFTS search API (`efts.sec.gov/LATEST/search-index`) returns JSON, no auth required
- Just needs a proper User-Agent header with contact info (SEC fair access policy: 10 req/sec)
- 10/10 rapid requests succeeded with zero failures — no aggressive blocking despite what some sources claim
- Filing documents are directly accessible via predictable URL structure: `sec.gov/Archives/edgar/data/{CIK}/{accession}/`
- Form 18-K (annual report for foreign governments) is specifically designed for sovereign issuers
- Prospectuses filed as 424B2/424B5 (supplements) and exhibits to 18-K
- **Massive coverage of the issuers FCA misses:** Argentina (456 filings), Mexico (3,722), Brazil (4,732), Colombia (863), Peru (1,282), Chile (3,811), Indonesia (622), Philippines (451), Turkey (836)
- **Complication:** Many CIKs per search term (e.g., "Oman" returns 34 CIKs) because EDGAR matches broadly. Need to identify the specific sovereign CIK vs. corporate entities that mention the country name. This is a one-time mapping exercise.
- **Key advantage:** Documents are in HTML/HTM format (not PDF) for many filings — potentially easier to parse than scanned PDFs from other venues.

### Tier 2: Moderate — Web interface, some structure, no API

**ESMA Prospectus Register**
- Cross-border register of all EU-approved prospectuses (`registers.esma.europa.eu`)
- Web search interface with keyword and criteria filtering
- CSV export available but throttled for large result sets
- CAPTCHA protection on some queries
- Could serve as a meta-index across Luxembourg, Dublin, and all other EU venues
- **Worth investigating further** as a single access point for EU-listed sovereign prospectuses
- No API documented

**Euronext Dublin (formerly Irish Stock Exchange)**
- Bond listings accessible with CSV export
- Regulatory news archives exist
- No direct prospectus search or download discovered
- No API
- ISE domain fully redirects to Euronext
- Prospectuses may be accessible via individual bond detail pages (JavaScript-rendered)

### Tier 3: Hard — JavaScript-heavy, no API, opaque

**Luxembourg Stock Exchange (LuxSE)**
- World's leading venue for international debt securities (1,700+ issuers, ~100 countries)
- CSSF has delegated prospectus publication to LuxSE
- Entire site is JavaScript-rendered — no static HTML to parse
- No API endpoints discovered
- No documented structured data access
- Would require full Playwright/Selenium browser automation
- **This is where many of the missing EM issuers list their Eurobonds** — it's important but difficult

**Central Bank of Ireland**
- No public prospectus database
- Portal-based access only
- Prospectuses approved by CBI should appear in ESMA register

---

## Coverage Matrix: Which Issuers Are Where?

Based on our FCA findings + EDGAR testing + domain knowledge:

| Issuer | FCA NSM | EDGAR | Luxembourg | Dublin | Notes |
|--------|---------|-------|------------|--------|-------|
| Argentina | ✗ | ✓ (456) | ✓ | | Major NY-law issuer |
| Brazil | ✗ | ✓ (4,732) | ✓ | | |
| Mexico | ✗ | ✓ (3,722) | ✓ | | |
| Colombia | ✗ | ✓ (863) | ✓ | | |
| Peru | ✗ | ✓ (1,282) | ✓ | | |
| Chile | ✗ | ✓ (3,811) | ✓ | | |
| Indonesia | ✗ | ✓ (622) | ✓ | | |
| Philippines | ✗ | ✓ (451) | | | |
| Turkey | ✗ | ✓ (836) | ✓ | | |
| Nigeria | ✓ (43) | ✓ (33) | ✓ | | Dual-listed |
| Egypt | ✓ (36) | ✓ (60) | ✓ | | Dual-listed |
| Saudi Arabia | ✓ (27) | ✓ (2,387) | ✓ | | |
| Kenya | ✓ (19) | ✓ (5) | | | Primarily LSE |
| Ghana | ✓ (28) | ✓ (40) | | | |
| Israel | ✓ (148) | ✓ (9,725) | | | Huge EDGAR presence |
| Serbia | ✓ (41) | ✗ | ✓ | ✓ | EU-law issuance |
| Albania | ✓ (7) | ✗ | | | LSE-listed |
| Zambia | ✓ (28) | ✗ | | ✓ | |
| Uzbekistan | ✓ (63) | ✗ | ✓ | | |
| Sri Lanka | ✓ (11) | ✓ (913) | | | |
| Cote d'Ivoire | ✗ | ✗ | ✓ | ✓ | Francophone → Luxembourg |
| Senegal | ✗ | ✗ | ✓ | | Francophone → Luxembourg |
| Cameroon | ✓ (2) | ✗ | ✓ | | |
| Rwanda | ✓ (2) | ✗ | ✓ | | |
| Gabon | ✓ (3) | ✗ | ✓ | | |

**Key insight:** FCA + EDGAR together cover the vast majority of sovereign issuers that matter for contract term research. Luxembourg fills in the Francophone African and some European frontier issuers.

---

## Revised Architecture Recommendations

Given what we now know, here are my suggestions for evolving the initial plan.

### 1. Start with FCA + EDGAR, defer Luxembourg

The original plan assumed Luxembourg would be Phase 2. I'd actually recommend:

- **Phase 0 (now):** Manual clause analysis on a handful of prospectuses (already planned)
- **Phase 1:** FCA NSM automated pipeline (API is trivial)
- **Phase 1.5:** EDGAR automated pipeline (API is also easy, just different)
- **Phase 2:** Luxembourg (only if you need Francophone Africa or European frontier markets)

The reasoning: FCA + EDGAR together give you ~80% of the sovereign issuers that matter for restructuring research, and both have easy APIs. Luxembourg adds marginal coverage at significantly higher engineering cost. The issuers you'd pick up from Luxembourg (Cote d'Ivoire, Senegal, Benin) issue under French law with OHADA-influenced contract terms — interesting but a different research question than the English/NY law CAC evolution you're primarily tracking.

### 2. EDGAR changes the document format story

The original plan centered on Docling for PDF extraction. But EDGAR filings are often in HTML/HTM format, not PDF. This is actually better — HTML preserves structure natively, no OCR needed, no layout analysis needed. For EDGAR documents:

- Parse HTML directly (Beautiful Soup, lxml)
- Section headers are actual HTML tags
- Tables are actual HTML tables
- No Docling needed for most EDGAR filings

This means the extraction pipeline should be format-aware:
- **FCA/Luxembourg PDFs → Docling → structured Markdown → Claude API for clause extraction**
- **EDGAR HTML → direct HTML parsing → structured text → Claude API for clause extraction**

Two input paths, same downstream clause extraction. The Claude API clause extraction prompt should be the same regardless of source format.

### 3. The "sovereign CIK directory" is a one-time investment

The EDGAR search returns many CIKs per country because it matches broadly. But each sovereign has exactly one CIK. Building a verified `{country → sovereign_CIK}` mapping is a one-time task that dramatically simplifies everything downstream. You could:

1. Search EDGAR for each sovereign name
2. Look at which CIK files 18-K forms (only sovereign governments file 18-K)
3. Manually verify the ~50-70 mappings
4. Store this as a reference table alongside the FCA name-variant mapping

This pairs nicely with the FCA sovereign issuer reference table we already built (which maps name variants → country → LEIs).

### 4. Reconsider the database architecture

The original plan called for PostgreSQL. For the exploration phase with Claude Code on your Mac Mini, I'd suggest starting simpler:

- **DuckDB** for analytical queries (embedded, no server, reads CSV/Parquet directly, excellent for the kind of "show me all CAC clauses where the aggregation threshold changed between 2014 and 2024" queries you'll want to run)
- **Flat files** (CSV/Parquet) for the metadata catalog, organized by source and country
- **SQLite** if you want relational constraints but don't want to run a Postgres server
- **Promote to PostgreSQL** when/if you build the Moss automated pipeline and need concurrent access

The key data you need to persist is actually pretty simple: a filing catalog (source, country, document type, date, URL, local path) and an extracted clause table (filing_id, clause_type, clause_text, key_parameters). Both fit comfortably in DuckDB or SQLite.

### 5. ColBERT might be premature — start with structured extraction

The original plan included ColBERT via RAGatouille for semantic search. This makes sense eventually, but for the exploration phase, I'd suggest:

1. **Start with Claude API structured extraction** — given your domain expertise, you can write very precise prompts for clause identification and parameter extraction. Structured JSON output from Claude is probably more useful than semantic search for the initial research questions.

2. **Use text diff for change detection** — `difflib` comparisons between the same issuer's prospectuses over time will surface the meaningful variation you care about (CAC threshold changes, aggregation mechanism evolution, pari passu language shifts).

3. **Add ColBERT later** when you have enough extracted clauses to make search useful (probably Phase 3, once you have 100+ prospectuses processed).

The research value is in the structured extraction, not the search. You already know which clauses matter — you need to extract them reliably and compare them systematically.

### 6. Claude's PDF vision vs. Docling: a hybrid approach

For the FCA prospectuses (which are PDFs), there's a question about extraction strategy:

- **Docling** is good for batch processing and gives you structured Markdown with table extraction. Run it on the Mac Mini for the bulk corpus.
- **Claude's PDF vision** is better for one-off analysis and for the high-value "is this clause actually a single-limb CAC?" classification step.

Suggested hybrid: Docling for bulk PDF → Markdown conversion (cheap, local, fast), then Claude API for the expensive clause identification and parameter extraction on the Markdown output. This matches the original plan but I'd emphasize that the Claude API step needs your domain expertise to prompt well — the difference between a single-limb and two-limb CAC, or between "ratable payment" and "ranking only" pari passu language, is subtle enough that generic prompts will miss it.

### 7. The POATR question is less urgent than it seems

The original plan flagged the UK POATR regime change (Jan 2026) as a risk. Based on what we see in the data — sovereign filings continue in the NSM through March 2026 — it seems like the transition is gradual. And since EDGAR covers the same issuers for USD-denominated bonds, even if London listings decline, the prospectus documents remain accessible. The contract terms in a USD bond prospectus filed with the SEC are substantively identical to those in a GBP bond prospectus filed with the FCA (same issuer, same law firms drafting the terms).

### 8. Workflow for the exploration phase

Given your setup (Mac Mini + Claude Cowork + Claude Code + domain expertise), here's what I'd suggest for the next few sessions:

**Next session:** Download 10-15 actual prospectus PDFs from the FCA (we have the URLs). Pick a diverse set: a few English-law (Kenya, Nigeria, Ghana) and a few that might be interesting (Albania's first issuance, Uzbekistan, Fiji). Manually review them in Claude to validate the clause taxonomy.

**Session after that:** Write the Claude API prompt for clause extraction. This is where your expertise is critical — you need to define precisely what counts as a "single-limb CAC" vs. "two-limb CAC" vs. "classic CAC" in the prompt, with examples from actual prospectuses. Test it against the 10-15 manually reviewed docs.

**Then:** Build the automated pipeline (download → Docling → Claude extraction → structured output) for FCA, then extend to EDGAR.

---

## Open Questions for Teal

1. **Governing law scope:** Start with English-law and NY-law bonds only? Or include other governing laws from the start? (Relevant because Francophone African issuers use French law, which has different clause structures.)

2. **Historical depth:** How far back do you want to go? The CAC evolution story really starts with Mexico's 2003 NY-law CACs, accelerates with the 2014 ICMA model clauses, and the most interesting recent developments are the G20 Common Framework era (2020+). Going back to 2003 would mean heavy EDGAR use; focusing on 2014+ is more manageable.

3. **Issuer priority:** If you could only process 20 sovereigns deeply (every prospectus, full clause extraction), which 20? This would help prioritize which venues to build pipelines for first.

4. **Collaboration with Gulati/Weidemaier:** Have they published any structured clause data that could bootstrap the taxonomy? Their work on CAC adoption rates would be a natural complement — and they might be interested in the tool itself.

5. **SAIS teaching use case:** Does the timeline matter? If this feeds into a course, that might affect prioritization.
