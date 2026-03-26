# Domain Context: Sovereign Bond Prospectuses

## The Core Problem
Sovereign bond prospectuses are ~90% boilerplate. The ~10% that varies (CACs, events of default, governing law, pari passu language) is where research and policy value lives.

## Why It Matters
Sovereign bond contract terms have evolved significantly post-2014: enhanced CAC adoption, G20 Common Framework, ICMA model clauses. A structured, searchable corpus democratizes access for researchers, policymakers, and economists.

## Domain Rules
1. Every extraction shown at the roundtable must be hand-verified. No exceptions.
2. Allow "not found" as valid output. Do not force extractions.
3. Page citations are non-negotiable.
4. Silent LLM paraphrasing is the scariest failure mode. Enforce verbatim.
5. Document families matter (base prospectus + supplements + final terms).

## Source of Truth Hierarchy
1. Actual prospectus text (highest authority)
2. PDIP annotations (expert baseline)
3. NSM metadata
4. Pipeline architecture docs
5. Agent reasoning (lowest authority)

## Key Clause Types
- **CAC:** Majority voting thresholds for bond restructuring
- **Pari Passu:** Equal ranking / pro-rata treatment
- **Events of Default:** Trigger conditions for acceleration
- **Governing Law:** Jurisdiction (typically English or New York law)
## Data Sources

### FCA National Storage Mechanism (NSM)
- Free, public, no authentication
- API: POST to `https://api.data.fca.org.uk/search?index=fca-nsm-searchdata`
- Full docs: `docs/nsm_api_reference.md`

### SEC EDGAR
- US-listed sovereign debt filings
- Rate-limited (10 req/sec with User-Agent)

### World Bank PDIP
- 900+ hand-annotated sovereign debt instruments
- Expert annotations are the gold standard for validation
- Full docs: `docs/pdip_data_extraction_assessment.md`

## Extraction Strategy: Grep-First
Don't send 300 pages to an LLM. Use regex patterns to locate clause sections first, then targeted extraction on just those pages.