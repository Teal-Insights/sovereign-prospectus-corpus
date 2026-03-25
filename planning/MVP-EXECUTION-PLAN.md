# MVP Execution Plan — Sovereign Prospectus Corpus

**Created:** March 24, 2026  
**For:** #PublicDebtIsPublic Roundtable (March 30, 2026)  
**Target Scope:** 8-10 core documents with hand-verified extractions  
**Timeline:** March 25-29, 2026 (6 days)  
**Execution Lead:** Teal Emery  
**Time Budget:** 15-20 hours total

---

## The One-Line Summary

**"You are not building a sovereign debt corpus in six days; you are building a credible argument that such a corpus can exist."** — ChatGPT Council

We're demonstrating: (1) a working extraction pipeline, (2) hand-verified accuracy on a small core, (3) proof that this scales to the full inventory of 434 prospectuses.

---

## MVP Scope (Monday Deliverable)

### Category 1: Documents (Must-Have)

**Ghana (2-3 documents)**
- Recent prospectus (pre-restructuring)
- Post-restructuring prospectus (shows evolution)
- Supplementary document (if available)
- Source: NSM API (automated download)
- Rationale: Central case study, well-researched, restructuring narrative clear

**Senegal (2-3 documents)**
- Eurobond 1 (Euronext Dublin)
- Eurobond 2 (Euronext Dublin)
- Optional: additional issuance
- Source: Manual download from Euronext Dublin (validates extensibility beyond NSM)
- Rationale: Demonstrates non-NSM sourcing, forward-looking policy context (H2 2026 restructuring expected)

**Zambia (1-2 documents)**
- Core Eurobond(s)
- Source: NSM API
- Rationale: Completes the geographic + restructuring-status triad

**Control/Vanilla Document (1 optional)**
- UK or European issuance (standard boilerplate)
- Source: NSM API
- Rationale: Proves system handles non-exotic, standard contracts correctly

**Total: 8-10 documents**

---

### Category 2: Extraction Targets (Hand-Verified)

All extractions shown at the roundtable must be hand-verified. No exceptions.

**Core Clauses to Extract (Per Document):**

1. **Collective Action Clauses (CAC)**
   - Aggregated amount + voting threshold
   - Consequences of invocation
   - Page citation + verbatim quote (required)

2. **Pari Passu**
   - Ranking statement
   - Carve-outs or conditions
   - Page citation + verbatim quote

3. **Events of Default**
   - Payment default threshold
   - Acceleration mechanism
   - Cross-default linkage (if any)
   - Page citation + verbatim quote

4. **Governing Law + Jurisdiction**
   - Explicit choice of law
   - Dispute resolution mechanism
   - Page citation

5. **External Indebtedness Definition**
   - What is and is not included
   - Impact on cross-default clauses
   - Page citation

6. **Information Covenants (Optional but Valuable)**
   - Reporting requirements
   - Disclosure frequency
   - Page citation

**Extraction Quality Rules:**
- ✅ Verbatim quote + page number
- ✅ Programmatic assertion: `assert quote in raw_pdf_text`
- ✅ Allow "not found" as valid output
- ✅ Flag any clause that was paraphrased (revert to source)
- ❌ Do NOT force extractions that don't exist

---

### Category 3: Outputs (Demonstrable)

**Jupyter Notebook** (Primary Demo)
- Clean, reproducible cells
- One section per country (Ghana, Senegal, Zambia)
- Clause extractions shown with page citations
- Formatted for lawyer audience (clear, non-technical)
- Includes timing metrics (extraction time per document)
- Shows failure cases (PDFs that didn't parse, clauses not found)

**Excel Workbook** (Alternative/Supplement)
- One sheet per document
- Columns: Clause Type | Found? | Verbatim Quote | Page Number | Notes
- Summary sheet: Comparative table (Ghana pre/post, Senegal vs. Zambia, etc.)
- **One-liner inventory stat:** "We indexed 434 prospectuses across 46 countries from the FCA NSM"

**One-Paragraph Summary**
- What this demo shows
- What the full corpus would enable
- What's needed for production-grade accuracy

---

## Execution Timeline (March 25-29)

### Day 1: March 25 — Validation & Prep

**Morning (1-1.5 hours)**
- [ ] Manually download 2 Ghana + 2 Senegal + 1 Zambia documents
- [ ] Quick visual inspection: Is text extractable? (No OCR-only PDFs)
- [ ] Test Docling on these 5 documents: measure parsing time, text quality, failure rate
- [ ] Log results: timing, quality, any crashes

**Midday (1 hour)**
- [ ] Run Claude extraction on 1 test document (Ghana)
- [ ] Hand-verify: Does output match source text? Are quotes accurate?
- [ ] Test verbatim assertion: `assert quote in raw_pdf_text` (should pass)
- [ ] Document any hallucinations or paraphrasing

**Afternoon (1-1.5 hours)**
- [ ] If validation passed: approve extraction workflow, proceed to batch
- [ ] If validation failed: pivot on methodology (grepping, different LLM, manual review)
- [ ] Build extraction prompts for all 6 target clauses
- [ ] Prepare SQLite schema for results

**End of Day:**
- [ ] Confirm: Does extraction actually work? Yes/No decision point
- [ ] If yes: proceed; if no, reassess scope on March 26 morning

**Day 1 Success Metric:** Extract 1 document successfully, hand-verified, ready for batch processing

---

### Days 2-3: March 26-27 — Scale & Refine

**March 26 Morning (1-1.5 hours)**
- [ ] Start NSM bulk download overnight (fully automated, low-risk)
- [ ] Submit download jobs for all Ghana + Senegal + Zambia documents
- [ ] Monitor first few completions for errors

**March 26 Afternoon (1.5-2 hours)**
- [ ] Refine extraction prompts on 2-3 test documents
- [ ] Test grepping for clause location (regex patterns for CAC, pari passu, etc.)
- [ ] Document which grep patterns work best
- [ ] Measure extraction time per document

**March 27 Morning (1.5 hours)**
- [ ] Build SQLite schema with columns for doc metadata + extraction results + validation status
- [ ] No JSON checkpoints; SQLite status columns only: `DOWNLOADED`, `PARSED`, `EXTRACTED`, `VERIFIED`, `FAILED`
- [ ] Test atomicity: write-to-temp-file, verify, rename

**March 27 Afternoon (2 hours)**
- [ ] Process 8-10 documents through the full pipeline
- [ ] Extraction → hand-verification loop (most time-intensive step)
- [ ] Log any failures, re-extractions, manual fixes
- [ ] Measure cumulative timing

**Days 2-3 Success Metric:** 8-10 documents processed, 90%+ extraction success rate, clear failure log

---

### Days 4-5: March 28-29 — Polish & Package

**March 28 Morning (1.5-2 hours)**
- [ ] Hand-verify every extraction one final time
- [ ] Spot-check page citations (does quote match page number?)
- [ ] Flag any need for re-extraction

**March 28 Afternoon (1.5-2 hours)**
- [ ] Build 2-3 case studies:
  - Case Study 1: Ghana pre-restructuring → post-restructuring CAC evolution
  - Case Study 2: Senegal vs. Zambia governing law comparison
  - Case Study 3 (optional): Vanilla control document vs. restructuring-exposed bond

**March 29 Morning (1-1.5 hours)**
- [ ] Polish Jupyter notebook: clean cells, clear narrative, lawyer-friendly language
- [ ] Create Excel companion sheet with comparative table
- [ ] Write one-paragraph summary: "What this shows, what it enables, what's next"

**March 29 Afternoon (1 hour)**
- [ ] Prepare talking points:
  - Opening: boilerplate insight ("~90% identical, ~10% varies")
  - How extraction works: grepping → LLM → verification
  - What we learned: common patterns, surprising variations, failure modes
  - Why this matters: change-detection for sovereign debt contracts
- [ ] Practice delivery

**Days 4-5 Success Metric:** Polished notebook + Excel, case studies ready, talking points prepared

---

## Technical Architecture

### Pipeline Flow

```
Raw PDFs
  ↓
[Docling] → Extract text (timeout: 3 min, fallback to PyMuPDF)
  ↓
[Grep Patterns] → Locate clause sections (no text outside clause regions)
  ↓
[Claude Code CLI] → Extract structured clause data (verbatim quotes required)
  ↓
[Assertion Checks] → Verify quote in raw text, page numbers valid
  ↓
[Hand-Verification] → Human review (non-negotiable)
  ↓
SQLite Status Update → VERIFIED or FAILED
  ↓
[Jupyter Notebook] → Final deliverable (clean, presenter-ready)
```

### Database Schema (SQLite)

```sql
CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY,
  source TEXT,              -- 'NSM', 'Euronext', etc.
  issuer TEXT,
  country TEXT,
  doc_type TEXT,            -- 'base', 'supplement', 'final_terms'
  currency TEXT,
  issue_date TEXT,
  maturity_date TEXT,
  download_url TEXT,
  local_filepath TEXT,
  download_status TEXT,     -- PENDING, DOWNLOADING, DOWNLOADED, FAILED
  download_timestamp TEXT,
  download_hash TEXT
);

CREATE TABLE extractions (
  extraction_id TEXT PRIMARY KEY,
  doc_id TEXT FOREIGN KEY,
  clause_type TEXT,         -- 'CAC', 'PARI_PASSU', 'EOD', 'GOVERNING_LAW', etc.
  found BOOLEAN,
  verbatim_quote TEXT,
  page_number INT,
  confidence REAL,          -- 0.0-1.0 (for diff extraction, not for hand-verified)
  extraction_status TEXT,   -- EXTRACTED, VERIFIED, FAILED, PARAPHRASED
  llm_model TEXT,           -- 'claude-opus-4.6', etc.
  extraction_timestamp TEXT,
  hand_verified BOOLEAN,
  verified_by TEXT,         -- 'Teal' or agent ID
  verified_timestamp TEXT,
  notes TEXT
);

CREATE TABLE grep_patterns (
  pattern_id TEXT PRIMARY KEY,
  clause_type TEXT,
  regex_pattern TEXT,
  context_lines INT,        -- how many lines before/after to include
  success_rate REAL,        -- empirical match rate
  notes TEXT
);
```

### Key Tools

- **Text Extraction:** Docling (primary), PyMuPDF fallback
- **Clause Location:** Python `re` module (regex grep)
- **Extraction Engine:** Claude Code CLI with Max plan
- **Database:** SQLite (single file, local)
- **Scripting:** Python 3.12+ with uv, polars, sqlalchemy
- **Presentation:** Jupyter notebook (primary), Excel (secondary)

### Fail-Safe Mechanisms

1. **Docling Timeout:** 3-minute subprocess timeout; kill + fallback to PyMuPDF
2. **Quarantine Directory:** Failed PDFs → `data/quarantine/`, never re-attempted
3. **Atomic Writes:** Download to `.part` file, verify hash, rename to `.pdf`
4. **Assertion Checks:** `assert extracted_quote in raw_pdf_text` (programmatic verification)
5. **Hand-Verification:** Every extraction shown at roundtable is manually reviewed
6. **Logging:** Every operation logged with timestamp, file path, result code

---

## Expansion Plan (If MVP Completes Early)

**These are contingent on Days 1-5 finishing ahead of schedule.**

### Expansion 1: Country-Scale NSM Downloads

**If:** Extraction pipeline stable by March 27 afternoon
**Then:** Start overnight download of all 46 countries (full 434 prospectuses)
**Timing:** 8-24 hours of wall-clock time (parallel downloads)
**Outcome:** Full inventory download complete by roundtable (can show final count)

### Expansion 2: PDIP A-B Comparison

**If:** Can access 1-2 PDIP-annotated documents
**Then:** Extract + compare against PDIP ground truth
**Timing:** 2-4 hours per document
**Outcome:** Quantified accuracy metric (e.g., "87% exact match on CAC extraction")

### Expansion 3: Zambia + Sri Lanka Case Studies

**If:** Extraction speed allows (>1 doc/hour)
**Then:** Add Zambia restructuring narrative + Sri Lanka control comparison
**Timing:** 3-4 hours cumulative
**Outcome:** 4-5 case studies instead of 2-3

### Expansion 4: Grep Pattern Library Documentation

**If:** Patterns prove reliable
**Then:** Document all regex patterns in reusable skill format
**Timing:** 2 hours
**Outcome:** Publishable "Find This Clause" skill for future corpus work

### Expansion 5: Advanced Analysis (Diffs & Change Detection)

**If:** Time permits
**Then:** Implement diff-based comparison (Senegal 2023 vs. 2026, Ghana pre/post-restructuring)
**Timing:** 3-4 hours
**Outcome:** "Here's what changed" analysis (the boilerplate insight made concrete)

---

## Roundtable Narrative Arc

### Opening (2 min)
> "Sovereign bond prospectuses are ~90% boilerplate — literally copy-paste with minor changes. That's not a bug; it's the economics of the market. The value is in finding the ~10% that varies. Here's what that looks like in practice."

### The System (5 min)
- "We built a pipeline: download → extract text → find clause locations → send to Claude → verify."
- "The key insight: we don't send all 300 pages to Claude. We use regex patterns to find the clause sections first, then send only those."
- "Every extraction you see has been hand-verified. We don't present anything without a lawyer reviewing it."

### The Evidence (8 min)
- **Case Study 1 (Ghana):** Show pre/post-restructuring CAC evolution. "What changed, why it matters."
- **Case Study 2 (Senegal):** Show Euronext Dublin sourcing (not just NSM). "This system works for non-NSM bonds too."
- **Case Study 3 (optional):** Vanilla UK bond. "Here's what the system does with standard boilerplate."
- For each: verbatim quotes, page citations, what we found, what we learned.

### The Scale (3 min)
- **Inventory stat:** "We indexed 434 prospectuses across 46 countries from the FCA NSM."
- "We haven't processed all 434 yet. That would take 2-3 weeks on our Mac Mini, 24/7."
- "But the 8-10 you see here show that the system works."

### The Vision (2 min)
- "What this enables: automated change-detection for sovereign debt contracts."
- "PDIP's 900 hand-annotated documents are an expert baseline. We've shown that AI can apply that expertise at scale."
- "This is Phase 1. Phase 2 would be: integrate with PDIP, build the full-scale corpus, offer it to the research community."

### Closing (1 min)
- "The nervous question: 'How do I know the extraction is right?' Answer: Because every extraction you see is hand-verified. We're not replacing lawyers; we're augmenting them."
- "That's what this project is: proof that this augmentation is possible."

---

## Success Criteria

### Must-Have for Roundtable

- [ ] 5-8 core documents successfully downloaded + parsed
- [ ] ≥80% extraction success rate (at least 4 out of 5 target clauses per document)
- [ ] 100% of shown extractions hand-verified
- [ ] Jupyter notebook: clean, reproducible, presenter-ready
- [ ] Zero hallucinated clauses in final output
- [ ] Talking points polished, practiced
- [ ] One-liner inventory stat ready ("434 prospectuses across 46 countries")

### Nice-to-Have (Expansion)

- [ ] PDIP A-B comparison (1+ document)
- [ ] Country-scale downloads complete
- [ ] 3+ case studies (instead of 2)
- [ ] Grep pattern library documented
- [ ] Diff-based change analysis (Ghana/Senegal examples)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Docling crashes on multi-column tables | Subprocess timeout (3 min), PyMuPDF fallback |
| LLM hallucination (paraphrases clauses) | Require verbatim quotes + programmatic assertion |
| Extraction slower than expected | Prioritize hand-verification over volume; scope down to 5 docs if needed |
| NSM API rate-limiting | Download all documents on Day 1-2 (before potential limits); observe behavior |
| PDIP documents not accessible | Fallback to manual Euronext downloads; skip A-B comparison if needed |
| Roundtable prep time insufficient | Pre-record Jupyter notebook demos; make slides backup |

---

## File Outputs

### Primary
- `data/exports/mvp_notebook_2026-03-29.ipynb` — Jupyter notebook (demo-ready)
- `data/exports/mvp_extractions_2026-03-29.xlsx` — Excel summary + case studies
- `data/exports/mvp_summary.txt` — One-paragraph description

### Supporting
- `data/db/corpus_mvp.sqlite` — SQLite database (all metadata + extraction results)
- `data/quarantine/` — Failed PDF files (for post-mortem analysis)
- `data/logs/extraction_timings_2026-03-29.json` — Performance metrics
- `LOG.md` — Append-only session log (what was done, when, by whom)

---

## Daily Standup Template

Each day, append to `LOG.md`:

```markdown
### March 25 (Day 1)

**Morning:** Downloaded 5 test documents, Docling parsing [✓/✗]
**Time spent:** 1.5 hours
**Blockers:** [none / LLM hallucination / ...]
**Next:** [continue to Day 2 plan]

**Today's Key Results:**
- [ ] Documents downloaded & inspected
- [ ] Docling tested (timing: X minutes per doc)
- [ ] 1 document extracted end-to-end
- [ ] Hand-verification passed
```

---

## Contingency: If Time Runs Short

**If only 10 hours available (instead of 15-20):**

**Scope:** Ghana only (2 docs) + Senegal (1 doc) = 3 documents

**What to cut:**
- Zambia case study (defer to expansion)
- PDIP comparison (defer)
- Advanced grep patterns (defer)
- Country-scale downloads (too time-consuming)

**What to keep (non-negotiable):**
- Hand-verified extractions
- Verbatim quotes + page numbers
- Clean Jupyter notebook
- One-paragraph summary
- Boilerplate insight framing

**Roundtable still works:** 3 documents × 2 countries + boilerplate insight = credible PoC

---

## Post-Monday Roadmap (April 2026+)

Once roundtable concludes, this project enters Phase 2:

1. **Document families:** Implement base + supplement + final terms linkage in SQLite
2. **PDIP integration:** Access full PDIP dataset, build A-B comparison at scale
3. **Batch processing:** Process all 434 documents (2-3 weeks on Mac Mini 24/7)
4. **Analysis suite:** Diffs, change-detection, comparative tables, statistical summaries
5. **Product roadmap:** "Nutrition label" portal for prospectuses (Gemini's vision)

---

*Created March 24, 2026 by Teal Emery*
*Ready for execution March 25, 2026*
*Deliverable for roundtable: March 30, 2026*
