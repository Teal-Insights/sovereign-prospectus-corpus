# CLAUDE.md — Sovereign Bond Prospectus Corpus

This file provides instructions and context for AI sessions working on the Sovereign Bond Prospectus Corpus. Read this file at the start of every session.

## Project Overview

**Goal:** Build a structured, searchable corpus of sovereign bond prospectuses — starting with the FCA's National Storage Mechanism (NSM) — that can systematically surface meaningful variation in contract terms across issuers and over time.

**The Core Problem:** Prospectuses are ~90% boilerplate; the ~10% that varies (CACs, events of default, governing law, pari passu language) is where research and policy value lives. Tracking this evolution across hundreds of near-identical documents requires automation.

**Why It Matters:** Sovereign bond contract terms have evolved significantly post-2014 (enhanced CAC adoption, G20 Common Framework, etc.). A structured, searchable corpus would democratize access to this information for researchers, policymakers, and economists.

**Strategic context:** This is a proof-of-concept for the #PublicDebtIsPublic roundtable at Georgetown Law (March 30, 2026), hosted by Anna Gelpern. The core pitch: PDIP's 900 hand-annotated documents are an expert baseline / gold standard that can enable AI-powered clause extraction at scale.

**Who we are:** Teal Insights — a research consultancy that builds open-source SovTech infrastructure for sovereign debt and climate finance analysis.

**Prior art:** Q-CRAFT Explorer (https://github.com/Teal-Insights/QCraft-App) — successfully converted from Excel to Python using council-of-experts + golden master testing. LIC-DSF Python Engine (in planning, same methodology).

---

## Source of Truth Hierarchy

1. Actual prospectus text (highest authority)
2. PDIP annotations (expert baseline)
3. NSM metadata
4. Pipeline architecture docs
5. Agent reasoning (lowest authority)

When sources conflict, follow this order.

---

## Key Architecture Decisions (from Council Round 1)

These decisions are confirmed by consensus of ChatGPT 5.4 Pro, Claude Opus 4.6, and Gemini 3.1 Pro Deep Think (March 24, 2026). See `planning/council-of-experts/round-1/SYNTHESIS.md`.

1. **SQLite as single source of truth.** No PostgreSQL, no JSON checkpoints. SQLite status columns for resumability.
2. **Depth over breadth for demo.** Download everything (automated), but present only hand-verified extractions.
3. **No Selenium/browser automation.** Accept two-hop latency. Selenium is brittle overnight.
4. **No dashboard.** Demo via Jupyter notebook or Excel. Lawyers live in Excel.
5. **Atomic file writes.** Download to `.part`, verify, then rename. Prevents corrupted PDFs.
6. **Quarantine directory** for unparseable PDFs. Budget 5-15% failure rate.
7. **Verbatim quote extraction.** All clause extractions must include exact verbatim text + page number. Programmatic assertion: `assert exact_quote in raw_pdf_text`.
8. **Document families.** Model base prospectus + supplement + final terms as one family in SQLite.

---

## Domain Rules

1. **Every extraction shown at the roundtable must be hand-verified.** No exceptions.
2. **Allow "not found" as valid output.** Do not force extractions that aren't there.
3. **Page citations are non-negotiable.** If no page number, it doesn't exist.
4. **Do not use ML jargon at the roundtable.** Say "gold standard" not "validation set." Say "research assistant" not "AI legal analyst."
5. **Silent LLM paraphrasing is the scariest failure mode.** Claude will want to synthesize clause language into "standard" forms, erasing the exact variations we're trying to detect. Enforce verbatim extraction.
6. **Document families matter.** Final terms are legally meaningful only when read with the base prospectus and supplements.
7. **The boilerplate insight is the core strategic theme.** Sovereign prospectuses are ~90% identical; the value is in finding the ~10% that varies. Frame all work around this insight.

---

## Teal's Confirmed Decisions (March 24, 2026)

**Status:** DECISION RATIFIED — These override any earlier open questions

See `planning/council-of-experts/round-1/SYNTHESIS.md` for full rationale and context.

### Compute Model: Claude Code CLI on Max Plan

- Use Claude Code CLI with Max plan allocation (not Anthropic API directly)
- $0 marginal cost via Max plan budgeting
- Invoke via command-line orchestration from Python scripts
- All extraction runs use `--dangerously-skip-permissions` flag (with safeguards)
- Make extraction pipeline runnable via Codex CLI and Gemini CLI as well (CLAUDE.md ↔ AGENTS.md symlink pattern for cross-model compatibility)

**Testing:** Day 1 (March 25) validates extraction throughput and rate limits

### Geographic Scope: Senegal + Ghana + Zambia

- **Senegal** (core): Demonstrates extensibility beyond NSM (Euronext Dublin sourcing)
- **Ghana** (core): Restructuring narrative (pre/post comparison)
- **Zambia** (core): Completes geographic + economic-condition triad
- **Optional:** Vanilla UK/European control document

**Rationale:** Senegal not politically sensitive for Teal; demonstrates non-NSM sourcing; forward-looking policy relevance (H2 2026 restructuring expected)

### Extraction Strategy: Grep-First Clause Finding

**Core principle:** Don't send 300 pages to Claude. Use regex patterns to locate clause sections first.

**Workflow:**
```
grep_patterns.find_clause_section(pdf_text, 'CAC') → [start_page, end_page]
  ↓
extract_only_those_pages()
  ↓
send_to_claude_code(pages)
  ↓
return verbatim_quote + page_number
```

**Pattern Library (Regex Examples):**
```python
PATTERNS = {
    'CAC': r'(?:collective|collective action|CAC|unanimous action|majority|voting|aggregated)',
    'PARI_PASSU': r'(?:pari passu|equally|rank equally|same rank|pro-rata)',
    'EVENTS_OF_DEFAULT': r'(?:Event[s]? of Default|default|failure to pay|cross-default)',
    'GOVERNING_LAW': r'(?:governing law|governed by|subject to|English law|New York law)',
    'ACCELERATION': r'(?:acceleration|accelerate|immediate payment|immediately due)',
    'CROSS_DEFAULT': r'(?:cross-default|cross default|cross[- ]?default|other obligations)',
}
```

**Benefits:**
- Context-efficient (no huge token usage)
- Compute-efficient (grep on local disk, targeted LLM processing)
- Pattern library is reusable skill ("Find This Clause")
- Encodes domain knowledge (lawyer expertise → regex)

### Time Budget & Scope

- **Realistic allocation:** 15-20 hours across March 25-29
- **Daily pace:** 2.5-3.3 hours/day (manageable with AI Evals + GSDR + LIC-DSF)
- **Contingency:** If actual time <12 hours, scope to Ghana + Senegal only
- **Expansion:** If tasks finish early, scale to country-level processing and PDIP comparison

### Hand-Verification (Non-Negotiable)

- Every extraction shown at roundtable is manually reviewed
- Programmatic assertion: `assert exact_quote in raw_pdf_text`
- Fallback to manual extraction if AI paraphrases
- Log all hand-verifications: who, when, what changed

### PDIP A-B Comparison

- **Attempt:** Try all approaches that work (API, browser automation, manual)
- **If systematic approach works:** Use it
- **If only browser automation works:** Process a few PDIP docs manually
- **Success metric:** 1+ PDIP document successfully extracted and compared (validates accuracy)

### Document Families

- **MVP (by Monday):** Capture metadata in SQLite schema (parent_id, doc_type, family_id)
- **Post-Monday:** Implement full family-aware comparison logic
- **Why defer:** Too complex for MVP scope; metadata capture enables future work

---

## Grep-First Clause Finding: A Reusable Skill

This is not just a temporary extraction hack. The grep-first approach is a **reusable skill** that can be extracted and shared:

**Skill Name:** `find-this-clause`

**Capability:** Given a clause type (CAC, pari passu, events of default, etc.), locate the clause section in a prospectus and return:
- Page range
- Verbatim quote
- Surrounding context (5 lines before/after)
- Confidence level

**Pattern Library:**
- Built into `scripts/grep_patterns.py`
- Documented with examples + edge cases
- Shared with research community (open-source)

**Training Data:**
- 434 prospectuses (if full corpus processed)
- Pattern performance metrics (which regex works best for which bond type)
- Failure log (clauses that are hard to find, unusual phrasings)

**Future Enhancement:**
- Combine with ML model (clause locator neural net) if regex patterns reach <85% precision
- Update patterns dynamically based on misses

---

## The Boilerplate Insight (Core Strategic Theme)

**Teal's Key Domain Insight:**
> "It's so boring so much of the time because they say exactly the same thing. And then it's trying to find the thing that's like a little bit different."

**Why this matters:**
- Prospectuses are ~90% boilerplate (copy-paste across issuers)
- ~10% varies in legally meaningful ways (CACs, events of default, definitions)
- AI + automation can find that 10% faster than a lawyer reading 300 pages
- The future product is a **change-detection system**, not just a corpus

**Roundtable framing:**
- Open with this insight
- Explain extraction strategy through this lens ("We're not cataloging everything; we're finding what changed")
- Show case studies highlighting variation
- Close with: "The corpus is a tool for finding the 10% that matters"

**Post-Monday vision:**
- Diff-based analysis: "Here's what Senegal 2023 vs. 2026 changed"
- Canonical template approach: "This is the standard; here are the deviations"
- Change-detection product: "Upload draft, get flagged deviations from market practice"

---

## Council of Experts Process

This project uses a cross-model review process (the "Council of Experts") for strategic planning. The process:

1. **CONTEXT-PACK-FOR-COUNCIL.md** — Comprehensive, self-contained context document. Organized into labeled sections (A-H) that can be pasted selectively.
2. **COUNCIL-PROMPT.md** — Structured strategic prompt with numbered core questions. Designed to elicit actionable, disagreeable feedback.
3. **Round N responses** — Saved as individual markdown files per model: `round-N/YYYY-MM-DD_Council_{Model}.md`
4. **SYNTHESIS.md** — Merged analysis noting agreements, disagreements, unique insights, and open questions for Teal.

### File Locations
```
planning/council-of-experts/
├── CONTEXT-PACK-FOR-COUNCIL.md    # Context pack (Sections A-H)
├── COUNCIL-PROMPT.md               # Strategic prompt (7 core questions)
├── README.md                       # Usage guide
└── round-1/
    ├── 2026-03-24_Council_ChatGPT-5.4-Pro.md
    ├── 2026-03-24_Council_Claude-Opus-4.6.md
    ├── 2026-03-24_Council_Gemini-3.1-Pro-Deep-Think.md
    └── SYNTHESIS.md
```

### When to Run a New Council Round
- Before major architectural decisions
- When stuck on prioritization or scoping
- After discovering unexpected technical obstacles
- Before the roundtable (final framing review)

---

## Data Source: FCA National Storage Mechanism

- **URL:** https://data.fca.org.uk/#/nsm/nationalstoragemechanism
- **Access:** Free, public, no authentication required
- **API Endpoint:** POST to `https://api.data.fca.org.uk/search?index=fca-nsm-searchdata`
- **Key Finding:** Unauthenticated Elasticsearch API, no observed rate limiting, size parameter works up to 10,000+
- **Status:** Phase 0 complete (API discovery and sovereign identification)

---

## What's Been Accomplished

### Phase 0: API Discovery & Sovereign Census (Complete)
- NSM API reverse-engineered and documented
- 1,426 sovereign filings identified across 46 countries
- 434 prospectus-type documents tagged for download
- Sovereign issuer reference table built with name variants and LEIs

### Phase 0.5: Strategic Planning (Complete)
- Council of Experts Round 1 completed (ChatGPT, Claude, Gemini)
- Pipeline architecture designed (SQLite, checkpoints, atomic writes)
- Senegal research completed (3 Eurobonds on Euronext Dublin, policy context mapped)
- PDIP platform assessed (extractable, no auth, structured annotations)
- Clause extraction templates designed

---

## Directory Structure

```
2026-03_Sovereign-Prospectus-Corpus/
├── Claude.md                          # This file — project context & rules
├── LOG.md                             # Detailed session log
├── docs/
│   ├── nsm_api_reference.md          # Full API documentation
│   ├── pipeline_architecture.md       # Download + processing pipeline design
│   ├── senegal_west_africa_research.md # Senegal prospectus locations
│   ├── proof_of_concept_strategy.md   # PoC strategy for roundtable
│   ├── pdip_data_extraction_assessment.md # PDIP platform technical recon
│   └── ai_classification_framework.md # Classification approach
├── planning/
│   └── council-of-experts/           # Council of Experts documents
│       ├── CONTEXT-PACK-FOR-COUNCIL.md
│       ├── COUNCIL-PROMPT.md
│       └── round-1/                  # Round 1 responses + synthesis
├── scripts/
│   ├── nsm_downloader.py            # NSM download pipeline
│   └── clause_extraction_templates.py # Claude prompt templates
├── data/
│   ├── raw/                          # Raw API results and CSVs
│   ├── pdfs/                         # Downloaded PDFs (by source/country)
│   ├── text/                         # Extracted text
│   ├── db/                           # SQLite database
│   └── exports/                      # Analysis outputs
└── tests/                            # (future: extraction validation tests)
```

---

## Key Data Files

### `sovereign_issuer_reference.csv`
Canonical reference table. Each row is a country with: normalized name, name variants, LEIs, filing count, document types, date range.

### `nsm_sovereign_filings_normalized.csv`
Every sovereign filing with: original NSM fields + normalized country + issuer_type classification.

### `docs/nsm_api_reference.md`
Complete API documentation: request/response schemas, field reference, type codes, behavioral notes, Python examples.

---

## Coding Style & Preferences

- **Python:** PEP 8, Python 3.12+
- **Project management:** uv, ruff, pyright, pytest
- **DataFrames:** Polars preferred (consistent with Q-CRAFT)
- **Git:** Trunk-based development, feature branches, small PRs
- **Editor:** VS Code
- **Also uses R:** tidyverse, `|>` pipe, purrr (for analysis/visualization)
- **Audience:** Graduate students, policymakers, economists, sovereign debt researchers
- **Tone:** Practical, technical, reproducible

---

## Session Protocol

1. **Read this file first.**
2. **Read the relevant docs** before implementing.
3. **Log what you did** at the end: append to `LOG.md`.
4. **If stuck after 5 attempts:** Document the blocker, move on.

---

## How to Pick Up Where We Left Off

1. **Read this file** for architecture decisions and domain rules
2. **Read `planning/council-of-experts/round-1/SYNTHESIS.md`** for strategic context
3. **Check `LOG.md`** for what's been done
4. **Inspect `data/raw/sovereign_issuer_reference.csv`** for country/LEI data
5. **Read `docs/pipeline_architecture.md`** for technical pipeline design

---

## Cross-Model Compatibility (AGENTS.md Symlink)

This project is designed to work with multiple AI model providers, not just Claude. The core extraction pipeline is model-agnostic.

### CLAUDE.md ↔ AGENTS.md Pattern

- **CLAUDE.md** (this file): Claude-specific configuration, prompts, and context
- **AGENTS.md** (symlink): Identical or equivalent content for non-Claude models (Codex, Gemini, GPT)

**Practical implementation:**
```bash
# In scripts/ directory:
ln -s ../Claude.md ../AGENTS.md
```

Or, maintain separate `AGENTS.md` with identical structure but model-specific notes:
```markdown
# AGENTS.md — Sovereign Bond Prospectus Corpus (Multi-Model Edition)

This file applies to Claude Code CLI, Codex CLI, Gemini CLI, and GPT CLI.

## Key Differences by Model

### Claude (via Claude Code CLI)
- Use Claude Code CLI with Max plan
- Verbatim extraction prompt: [prompt_v1]

### Codex (via Codex CLI)
- Use Codex CLI with credits
- Verbatim extraction prompt: [prompt_v1]

### Gemini (via Gemini CLI)
- Use Gemini CLI with credits
- Verbatim extraction prompt: [prompt_v1]

### GPT (via GPT CLI)
- Use GPT CLI with API key
- Verbatim extraction prompt: [prompt_v1]
```

**Why this matters:**
- The clause-finding logic is language-agnostic (regex, Python)
- The extraction prompts can be adapted to any LLM
- The verification step (assert quote in text) is model-independent
- Enables future switching between models without rewriting architecture

---

## References & Documentation

- **NSM API:** `docs/nsm_api_reference.md`
- **Session Log:** `LOG.md`
- **Council Synthesis:** `planning/council-of-experts/round-1/SYNTHESIS.md`
- **MVP Execution Plan:** `planning/MVP-EXECUTION-PLAN.md`
- **Pipeline Design:** `docs/pipeline_architecture.md`
- **Senegal Research:** `docs/senegal_west_africa_research.md`
- **Teal's Confirmed Decisions:** `planning/council-of-experts/round-1/SYNTHESIS.md#Teal's Decisions`
- **Source Data:** `data/raw/`

---

**Last Updated:** 2026-03-24
**Phase:** 0.5 (Strategic planning complete, Council Round 1 done, Teal's decisions ratified)
**Next Phase:** 1 (March 25-29: Golden Path validation → bulk download → hand-verified extraction → roundtable demo on March 30)
