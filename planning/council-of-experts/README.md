# Council of Experts Documents — Sovereign Bond Prospectus Corpus

## Overview

This directory contains the two strategic planning documents for council-of-experts consultation on the Sovereign Bond Prospectus Corpus project (deadline: March 30, 2026).

## Files

### 1. CONTEXT-PACK-FOR-COUNCIL.md (24 KB, 429 lines)

**Purpose:** Pre-digested context pack designed so AI models (and Teal) can spend thinking time on strategy, not background re-reading.

**Structure:** 8 labeled sections (A-H), each self-contained and labeled for when to paste:

- **Section A:** What We're Building (paste this first, always)
- **Section B:** The Event and Audience (paste when discussing positioning)
- **Section C:** The #PublicDebtIsPublic Platform (paste when discussing PDIP)
- **Section D:** Data Sources and What We've Found (paste when discussing technical pipeline)
- **Section E:** Pipeline Architecture (paste when discussing technical decisions)
- **Section F:** Key Reference Papers (paste for domain context)
- **Section G:** What's Been Done So Far (paste to avoid re-deriving)
- **Section H:** Constraints and Success Criteria (paste when discussing prioritization)

**Key Features:**
- Specific technical details (API endpoints, file counts, LEI numbers, URLs)
- Prior art (Q-CRAFT lessons, specifically what worked before)
- What others have already concluded (findings from Phase 0 research)
- Written for someone reading it cold who needs to give strategic advice

### 2. COUNCIL-PROMPT.md (17 KB, 305 lines)

**Purpose:** Structured strategic prompt designed to elicit disagreeable, actionable feedback — not cheerleading.

**Structure:** 7 core questions with sub-questions, each probing a specific decision or risk:

1. **Pipeline Architecture: Is This Sound?** — SQLite, two-hop URLs, checkpointing
2. **Prioritization: What Do We Focus On First?** — Breadth vs. depth, countries to prioritize
3. **The "Validation Set" Pitch: Is This Compelling?** — Will lawyers/policymakers buy it? What are the counterarguments?
4. **Technical Risks: What Will Go Wrong?** — PDF parsing, clause extraction accuracy, rate limiting
5. **The Roundtable Pitch: How Do We Frame This?** — One-sentence version, five-minute narrative, audience-specific messaging
6. **What Are We Missing?** — Important contract dimensions, other researchers, post-Monday roadmap
7. **Honest Assessment** — 1-10 confidence, single biggest risk, what to cut, what to add

**Desired Output Format:** Structured response with pipeline assessment, prioritization recommendation, pitch assessment, risk matrix, framing, missing pieces, honest assessment.

**Key Features:**
- Clear sub-questions probing exactly what decision is needed
- Explicit "what we're trying to get at" for each question
- Tone: direct and disagreeable, not polite
- Output format specified so responses are comparable across models
- References back to context pack sections for easy navigation

## How to Use

### For Strategic Consultation

1. **Select a question** from COUNCIL-PROMPT.md (e.g., "Question 1: Pipeline Architecture")

2. **Identify relevant context sections** from CONTEXT-PACK-FOR-COUNCIL.md (e.g., Section A + Section E)

3. **Paste the prompt** to your chosen model (Claude Opus, ChatGPT Pro, Gemini Pro Deep Think):
   ```
   [COUNCIL-PROMPT.md content]
   
   ---
   
   ## CONTEXT (paste relevant sections)
   
   [Section A from CONTEXT-PACK-FOR-COUNCIL.md]
   [Section E from CONTEXT-PACK-FOR-COUNCIL.md]
   ```

4. **Ask for feedback** on the numbered question(s)

5. **Synthesize responses** from multiple models, noting where they disagree (most valuable)

### For New Team Members

If bringing someone new up to speed quickly:
1. Have them read CONTEXT-PACK-FOR-COUNCIL.md (full, 15-20 minute read)
2. Have them skim COUNCIL-PROMPT.md to understand what decisions are pending
3. Have them review the council responses to see how the team thinks about tradeoffs

## Methodology

This follows the **Q-CRAFT pattern** successfully used in the IMF Excel-to-Python conversion (7 days):

1. Council of experts (multiple models) → structural feedback on architecture
2. Golden master testing → validate pipeline on small, high-quality examples
3. Thin vertical slices → complete one full pathway before expanding
4. Reproducible code → everything git-tracked, logged, version-controlled

The council-of-experts approach prevents architectural mistakes that would be expensive to fix after 2-3 days of implementation.

## Key Constraints

- **Timeline:** 6 days (March 24-30, 2026)
- **Budget:** $0 marginal cost (Claude Max, ChatGPT Pro, Gemini — all unlimited)
- **Teal's Time:** Limited (other commitments); computer does heavy lifting
- **Compute:** Mac Mini M-series, 24/7 operation
- **Success Metric:** Compelling demo + navigable code for roundtable on March 30

## Strategic Questions Being Addressed

1. Is the technical architecture sound?
2. What's the minimum viable scope for 6 days?
3. Will the "validation set" pitch resonate with lawyers/policymakers?
4. What technical risks will derail us?
5. How do we tell the story compellingly?
6. What are we missing?
7. What's my honest confidence level? (1-10)

## Related Documents

- **CONTEXT-PACK-FOR-COUNCIL.md** — This directory
- **COUNCIL-PROMPT.md** — This directory
- **proof_of_concept_strategy.md** — PoC strategy document (more detailed)
- **pipeline_architecture.md** — Technical architecture (predecessor to context pack)
- **Claude.md** — Project overview
- **LOG.md** — Phase 0 session log

## Workflow

Typical workflow for March 24-30:

- **Monday (March 24):** Council feedback on all 7 questions → decide architecture + prioritization
- **Tuesday-Wednesday (March 25-26):** Implementation (downloads + extraction)
- **Thursday (March 27):** Mid-course check-in if needed; begin analysis
- **Friday-Weekend (March 27-29):** Analysis + demo prep
- **Monday (March 30):** Roundtable presentation

## Questions?

This is a strategic planning document, not a development roadmap. For implementation details, see `proof_of_concept_strategy.md` and `pipeline_architecture.md`.

---

**Prepared:** March 24, 2026  
**For:** Council-of-experts review cycle  
**By:** Teal Insights
