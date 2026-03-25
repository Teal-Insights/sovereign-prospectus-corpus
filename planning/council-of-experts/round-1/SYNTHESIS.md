# Council Round 1: Synthesis

**Date:** March 24, 2026
**Models:** ChatGPT 5.4 Pro, Claude Opus 4.6, Gemini 3.1 Pro Deep Think
**Synthesized by:** Claude (Cowork session)
**Status:** Awaiting Teal's domain review and decision confirmation

---

## 1. Points of Strong Agreement (All Three Models)

**These are high-confidence decisions — proceed unless domain expertise says otherwise.**

1. **SQLite as single source of truth.** All three agree: SQLite, not PostgreSQL, not JSON + files. One writer is fine for a solo Mac Mini pipeline. Gemini goes furthest: ditch the JSON checkpoint file entirely; use SQLite status columns (`PENDING`, `DOWNLOADING`, `PARSED`, `EXTRACTED`, `FAILED`) for resumability.

2. **Depth over breadth for the demo.** All three explicitly say: the room cares about accuracy, not inventory size. Download everything (it's automated), but **present only hand-verified extractions.** A lawyer who sees one hallucinated clause will dismiss the entire project.

3. **"Validation set" framing is wrong for this audience.** All three independently flag this as jargon that will land badly. Lawyers will hear "your work is just fuel for my model." Replacement language converges on: "gold standard," "expert baseline," "ground truth benchmark." ChatGPT: "expert-labeled reference corpus." Opus: "PDIP created the gold standard. We built the machine that can apply it at scale." Gemini: "Ground Truth Benchmark" + "High-Speed Triage Paralegal."

4. **No Selenium/browser automation.** Accept the two-hop latency. Selenium is brittle, crashes overnight, and is harder to recover when unattended. The extra 8-12 hours of wall time is within budget on a 24/7 Mac Mini.

5. **No dashboard.** All three say: cut the frontend. ChatGPT: "Kill the shiny interface first." Opus: "Jupyter notebooks for the demo." Gemini: "Lawyers live in Excel; it signals rigorous data." The demo should be a clean notebook or spreadsheet, not a web app.

6. **Clause extraction accuracy is the existential risk.** Not downloads, not rate limiting, not disk space. One page-citation error in front of sovereign debt lawyers = total credibility loss. Every extraction shown at the roundtable must be hand-verified against the source text.

7. **Atomic file writes.** Download to `.part` or temp file, verify hash/readability, then rename. Prevents corrupted PDFs from entering the pipeline after power loss.

8. **Budget for 5-15% unparseable PDFs.** Build a `quarantine/` directory. Don't let one bad file crash the batch. Some NSM "PDFs" will be HTML, password-protected, or corrupted.

## 2. Points of Meaningful Disagreement

### 2a. Country prioritization

| Model | Core Countries | Senegal's Role |
|-------|---------------|----------------|
| ChatGPT | Ghana, Zambia, Sri Lanka | Optional cameo, not a dependency |
| Opus | Ghana, Zambia, Senegal | Core — narrative value of sourcing outside NSM |
| Gemini | Senegal, Zambia, Ghana + 1 control | Non-negotiable — strongest narrative hook |

**The tension:** ChatGPT is cautious about Senegal being "live, politically charged, and easier to overstate." Opus and Gemini both see Senegal as the strongest story because it demonstrates extensibility (Euronext Dublin, not NSM) and forward-looking policy relevance (restructuring expected H2 2026).

**🔍 Domain question for Teal:** How politically sensitive is the Senegal case at the roundtable? Is Anna Gelpern likely to have strong views? If the room includes people involved in Senegal's debt situation, tread carefully. If it's academics and researchers, Senegal is a powerful case study.

**Proposed resolution:** Ghana and Zambia are consensus core. Senegal is high-value if handled carefully — present it as "demonstrating extensibility" and "forward-looking policy relevance," not as a policy recommendation. Include it but don't make it the centerpiece.

### 2b. Extraction target

| Model | Target | Reasoning |
|-------|--------|-----------|
| ChatGPT | 12-15 documents, 3 case studies | More breadth in extraction |
| Opus | 5-8 documents, hand-verified | Fewer but flawless |
| Gemini | 10-15 deeply processed | More ambitious but hand-verified |

**Proposed resolution:** 8-10 documents with hand-verified extractions, producing 2-3 polished case studies. This splits the difference while maintaining the non-negotiable quality standard.

### 2c. API / compute model

| Model | Assessment |
|-------|-----------|
| ChatGPT | Didn't flag API issues |
| Opus | Flags Claude Max ≠ API access; verify API tier |
| Gemini | Calls this a "fatal flaw" — $20/mo is chat UI, not API |

**The tension:** Teal's plan specifies "Claude Code with Max plan, $0 marginal cost." This needs clarification. Claude Code on a Max plan may have different limits than the API. Gemini recommends using Sonnet via API for bulk processing. But Teal's stated preference is to use Claude Code (agentic CLI), not the API directly.

**🔍 Domain question for Teal:** Confirm your intended compute path. Are you planning to:
(a) Use Claude Code CLI with `--dangerously-skip-permissions` to process documents? (This uses Max plan allocation, not API credits.)
(b) Call the Anthropic API programmatically? (This requires API credits, separate from Max.)
(c) Use Claude Code to orchestrate, calling the API for extraction? (Hybrid — needs both.)

**This must be resolved today.** If the answer is (b) or (c), check your API tier, rate limits, and pre-fund accordingly. If (a), confirm that Claude Code can handle the document sizes and volume within Max plan rate limits.

## 3. Unique Insights by Model

### ChatGPT (Unique Contributions)
- **Document families are the blind spot.** Final terms are legally meaningful only when read together with the base prospectus and supplements. Treating every PDF as independent creates false absences and bogus clause statistics. Model base + supplement + final terms as one family.
- **ICMA model package** is not just CACs and pari passu — includes creditor engagement provisions. The World Bank's 2025 report flags collateralized instruments, transparency clauses, and CRDCs.
- **No sovereign-specific AI clause-extraction benchmark exists.** CUAD and LegalBench are adjacent but not sovereign. This gap is both the opportunity and the credibility problem.
- **"You are not building a sovereign debt corpus in six days; you are building a credible argument that such a corpus can exist."** This is the best single-sentence framing of what Monday is about.

### Claude Opus (Unique Contributions)
- **Mark Weidemaier and Mitu Gulati** (Duke/UVA) have the most extensive empirical dataset on sovereign bond contract terms. Reference this lineage — your project is a technological complement to their empirical program.
- **Trust indenture vs. fiscal agency structure** — determines who can enforce, varies systematically between English-law and NY-law bonds. Important extraction target.
- **Information covenants** (reporting requirements) — ironic for a transparency project to miss these.
- **Comparison to Q-CRAFT:** "Q-CRAFT was cleaner because you had a golden master. Here you don't have that. PDIP's annotations could serve as the golden master, but you don't have access yet." This is the core weakness: demoing a capability without a formal accuracy benchmark.
- **Time math reality check:** 15-20 hours across 6 days = 2.5-3.3 hours/day alongside AI Evals, GSDR, and LIC-DSF commitments. If it's actually 10 hours, scope to Ghana + Senegal only.

### Gemini (Unique Contributions)
- **"Split-brain" state management** — JSON checkpoints + SQLite is an anti-pattern. Use SQLite status column as the only resumability mechanism.
- **Silent LLM paraphrasing is the scariest failure mode.** Claude will want to synthesize and normalize clause language. If a bond has a weird carve-out, Claude might replace it with "standard" language from pre-training data, **actively erasing the exact variation you're trying to detect.** Mitigation: require verbatim quotes + programmatic assertion that `exact_quote in raw_pdf_text`.
- **Docling OOM crashes.** Run Docling in a subprocess with 3-minute timeout. If it hangs, kill and fallback to PyMuPDF.
- **Definition of "External Indebtedness"** is where hidden debt lives (Greece's swaps, Mozambique's Tuna Bonds). If the definition excludes bilateral loans or derivatives, cross-default clauses are neutered.
- **Post-Monday vision: "Nutrition label" for prospectuses.** A portal where DMOs upload draft prospectuses and get standardized JSON clause summaries to verify against IMF standards before going to market.
- **Control country needed.** Include one vanilla UK/European issuance to prove the model handles standard boilerplate correctly.

## 4. Risks (Merged and Ranked)

### Risk 1: Clause Extraction Accuracy (CRITICAL)
*Flagged by: All three*
One hallucinated clause or misidentified CAC type in front of sovereign debt lawyers = total credibility loss. LLMs natively want to synthesize, which means they may paraphrase exact legal language, erasing the precise variations you're trying to detect.
**Mitigation:** (1) Require verbatim quotes with page numbers. (2) Programmatic assertion: `assert exact_quote in raw_pdf_text`. (3) Two-pass extraction: extract, then verify. (4) Hand-verify every extraction shown at roundtable. (5) Allow "not found" as valid output.

### Risk 2: API/Compute Model Uncertainty (HIGH → RESOLVE TODAY)
*Flagged by: Opus, Gemini*
Claude Max ≠ API access. If processing requires API calls, TPM limits will throttle bulk processing. Claude Code CLI may have different constraints.
**Mitigation:** Confirm compute path today (Claude Code CLI vs. API vs. hybrid). If API, check tier and pre-fund. If Claude Code, test volume limits.

### Risk 3: PDF Parsing Failures (HIGH)
*Flagged by: All three*
Multi-hundred-page legal PDFs with tables, footnotes, multi-column layouts. Docling may choke. 5-15% failure rate expected.
**Mitigation:** (1) Test Docling on 5 representative prospectuses today. (2) Subprocess with 3-minute timeout. (3) PyMuPDF fallback. (4) `quarantine/` directory. (5) Don't let one bad file crash the batch.

### Risk 4: Document Family Errors (HIGH)
*Flagged by: ChatGPT primarily*
Treating every PDF as independent creates false absences. Final terms + base prospectus + supplements are one legal unit.
**Mitigation:** Model document families in SQLite. Link supplements to base prospectuses. Don't compare clause presence across families without understanding the hierarchy.

### Risk 5: Teal's Time Budget (MEDIUM-HIGH)
*Flagged by: Opus*
15-20 hours across 6 days is 2.5-3.3 hours/day alongside other commitments. If actual time is 10 hours, scope must shrink.
**Mitigation:** Be honest about available time. If <15 hours, scope to Ghana + Senegal only, Jupyter notebook demo, no dashboard.

## 5. Consolidated Action Items

### TODAY (March 24) — Non-Negotiable

1. **Resolve API/compute path.** Claude Code CLI vs. API. Check rate limits.
2. **Hand-download 5 test documents.** 2-3 Ghana, 2-3 Senegal (from Euronext Dublin).
3. **Test Docling on 5 documents.** Measure failure rate, text quality, processing time.
4. **Run Claude extraction on 1 document.** Hand-verify output. Test verbatim quote assertion.
5. **Confirm: does the extraction actually work?** If yes, proceed. If no, you have 5 days to pivot.

### DAYS 2-3 (March 25-26)

6. **Start NSM bulk download overnight.** It's automated, low-risk, runs while you sleep.
7. **Perfect extraction prompts** on 5-8 test documents.
8. **Build the SQLite-only state management** (no JSON checkpoints).

### DAYS 4-5 (March 27-28)

9. **Process 8-10 documents** with hand-verified extractions.
10. **Build 2-3 case studies** (Ghana pre/post restructuring, Senegal, optionally Zambia).
11. **Try A-B comparison** with one PDIP-annotated document if possible.

### DAY 6 (March 29)

12. **Polish narrative.** Jupyter notebook or Excel with clean outputs.
13. **Hand-verify every extraction one final time.**
14. **Prepare talking points** using the framing from Section 5 of the council responses.

## 6. Key Vocabulary Decisions

| Don't Say | Say Instead | Why |
|-----------|-------------|-----|
| Validation set | Gold standard / Expert baseline / Ground truth benchmark | ML jargon alienates lawyers |
| AI legal analyst | Research assistant / Triage paralegal / Discovery engine | Lawyers hear "unauthorized practice of law" |
| We automated clause extraction | We built infrastructure that locates clauses for expert review | Positions AI as complement, not replacement |
| Our model found... | The system extracted verbatim text from page X... | Page citations = credibility |
| 500 documents downloaded | We indexed 434 prospectuses across 46 countries | "Indexed" sounds like infrastructure, not bulk scraping |

## 7. The One-Line Summary (ChatGPT nailed this)

> **"You are not building a sovereign debt corpus in six days; you are building a credible argument that such a corpus can exist."**

If you present it that way — "here's what this looks like when it works, here's the inventory showing scale is possible, and here's what we'd need to make it production-grade" — you can win the room. If you present it as already solved, you will get picked apart.

---

## Open Questions Requiring Teal's Decision

1. **API/compute path:** Claude Code CLI (Max plan) vs. Anthropic API vs. hybrid? → Must resolve today.
2. **Senegal sensitivity:** How politically charged is this at the roundtable? Is Gelpern likely to have views?
3. **Time budget reality:** Is 15-20 hours across 6 days realistic given other commitments?
4. **PDIP A-B comparison:** Can you access one PDIP-annotated document to test extraction accuracy?
5. **Document families:** Should we model base + supplement + final terms linkage in SQLite now, or defer?

---

*Synthesized March 24, 2026*
*Ready for Teal's domain review and decision confirmation*

---

## Teal's Decisions (March 24, 2026)

**Status:** CONFIRMED AND ADOPTED
**Decision Date:** March 24, 2026
**Approved by:** Teal Emery (domain expert review of Council synthesis)

Teal has reviewed the Council of Experts synthesis and made the following confirmed decisions, which supersede any open questions or divergent model opinions.

### Decision 1: Senegal → GO

**Decision:** Include Senegal as a core case study.

**Rationale:** 
- Not politically sensitive for Teal's domain position
- The room wants it (strong preference from Gemini and Opus)
- Demonstrates extensibility (Euronext Dublin sourcing outside NSM)
- Forward-looking policy relevance (H2 2026 restructuring expected)
- Narrative strength: "We can handle non-NSM sources"

**Implementation:**
- Source Senegal Eurobonds from Euronext Dublin (manual download, 2-3 docs)
- Present alongside Ghana + Zambia as the core triad
- Frame as "demonstrating extensibility," not as policy recommendation
- Use PDIP's existing Senegal research for context

### Decision 2: Claude Code CLI on Max Plan (Not API)

**Decision:** Use Claude Code CLI with Max plan allocation, NOT the Anthropic API.

**Rationale:**
- $0 marginal cost via Max plan (already budgeted)
- Aligns with automation-first, command-line-first workflow
- Avoid API rate-limiting complexity; MLOps simpler with CLI
- Can leverage agentic capabilities (markdown-to-code orchestration)

**Implementation:**
- All clause extraction runs via Claude Code CLI
- Max plan provides baseline allocation and throughput
- Use `--dangerously-skip-permissions` flag after good pre-planning and error handling
- Also make runnable via Codex CLI and Gemini CLI (maintain compatibility via CLAUDE.md ↔ AGENTS.md symlink pattern)

**Technical Notes:**
- Claude Code CLI invocations will be orchestrated from Python scripts or Jupyter notebooks
- Document max-concurrent and rate-limit assumptions in architecture docs
- Test throughput on Day 1; adjust scoping if limits are tighter than expected

### Decision 3: `--dangerously-skip-permissions` Enabled (With Safeguards)

**Decision:** Use `--dangerously-skip-permissions` flag to streamline extraction workflows.

**Rationale:**
- Good pre-planning minimizes permission surprise at runtime
- Error handling + assertion checks catch mistakes early
- Time savings on permission dialogs justify the risk
- Allows fully-headless batch processing

**Implementation:**
- All extraction scripts will use `--dangerously-skip-permissions`
- Before any run: document expected outputs, file paths, and failure modes
- Add assertion checks: `assert os.path.exists(output_pdf)` before processing
- Implement detailed logging: log every file written, with timestamp and hash
- Quarantine + manual review for any unexpected file operations

### Decision 4: Time Budget: 15-20 Hours Is Realistic

**Decision:** Allocate 15-20 hours total across March 25-29 (6 days to roundtable on March 30).

**Rationale:**
- ~2.5-3.3 hours per day is manageable alongside AI Evals + GSDR + LIC-DSF
- Opus flagged time realism; Teal confirms this is achievable
- Scope is tight but not impossible (Ghana + Senegal + Zambia + 2 extra)
- Council consensus on "depth > breadth" makes time work

**Implementation:**
- March 25-26 (Days 2-3): NSM downloads overnight, prompt refinement, state management build
- March 27-28 (Days 4-5): Process 8-10 documents, hand-verify, build 2-3 case studies
- March 29 (Day 6): Polish narrative, final verification, preparation
- **If actual available time drops below 12 hours:** Scope to Ghana + Senegal only

### Decision 5: PDIP A-B Comparison → Try All Approaches

**Decision:** Attempt PDIP A-B comparison using whatever extraction methods work best.

**Rationale:**
- Browser automation (NSM scraper) validated and proven
- If systematic approach (API + regex) works, use it
- If only browser automation succeeds, do a few PDIP docs manually
- No single "best" approach; pragmatic fallback matters

**Implementation:**
- **Day 1 (March 25):** Test API-based extraction on 1-2 PDIP docs
- **Fallback (Day 2-3):** If API extraction fails, switch to browser automation on 2-3 PDIP docs
- **Hand verification:** Every A-B comparison result must be human-verified
- **Reporting:** Document which extraction method worked for which doc

**Success Criteria:** At least 1 PDIP document successfully processed and compared (shows that extraction quality can be validated against ground truth)

### Decision 6: Document Families → Defer to Post-Monday

**Decision:** Model document families (base prospectus + supplements + final terms) in database schema, but full implementation deferred post-roundtable.

**Rationale:**
- ChatGPT flagged this as important for accuracy
- Too much complexity for MVP scope (Monday)
- But must capture metadata now to enable future work

**Implementation:**
- SQLite schema includes `parent_id`, `doc_type` (base, supplement, final_terms), `family_id` fields
- During download, tag documents with family relationships
- At roundtable: explain that document families are on the roadmap
- Post-Monday: implement family-aware comparison logic

### Decision 7: Grep-First Clause Finding Strategy

**Decision:** Use regex/grep patterns to locate clause sections before sending to Claude for structured extraction.

**Rationale:**
- Avoids sending 300 pages to Claude (context-efficient)
- Leverage domain knowledge encoded in regex patterns
- Identify clause sections first, then send only relevant pages for extraction
- Compute-efficient: grep on local disk, then targeted LLM processing

**Implementation:**
- Build regex pattern library for common clauses: CAC, pari passu, events of default, governing law, acceleration, cross-default
- Pattern library documented in comments with page references from reference docs
- Workflow: `grep_patterns.find_clause_section(pdf_text, 'CAC') → [start_page, end_page] → extract_only_those_pages() → send_to_claude()`
- Document as a reusable skill: "Can we make a 'find this clause' skill?"

**Pattern Examples:**
```
CAC: r'(?:collective|collective action|CAC|unanimous action|majority|voting|aggregated)'
Pari Passu: r'(?:pari passu|equally|rank equally|same rank|pro-rata)'
Events of Default: r'(?:Event[s]? of Default|default|failure to pay|cross-default)'
Governing Law: r'(?:governing law|governed by|subject to|English law|New York law|NY law)'
```

### Decision 8: MVP + Expansion Plan Structure

**Decision:** Implement tight MVP for Monday roundtable, with documented expansion path if time permits.

**Rationale:**
- Reduces risk of over-scoping
- Clear success criteria for roundtable
- Expansion plan shows scalability path to investors/partners
- Flexibility to capitalize on early wins

**Implementation:**
- **MVP (must-have):** 5 documents, all hand-verified, 2-3 case studies, clean Jupyter notebook
- **Expansion:** Country-scale downloads, more case studies, PDIP comparison, Zambia/Sri Lanka, grep library docs
- **See:** `planning/MVP-EXECUTION-PLAN.md` (detailed breakdown)

### Decision 9: AI Time Estimates Are Unreliable

**Decision:** Plan for tasks potentially being faster than estimated. Build in buffer, but don't assume worst-case timing.

**Rationale:**
- Council notes that AI estimates usually overestimate time
- Docling extraction may be faster than pessimistic scenarios suggest
- NSM downloading is fully automated (no human bottleneck)
- Over-conservative scoping leaves innovation opportunity

**Implementation:**
- **Day 1:** If tests finish early, immediately expand to 10 documents (not 5)
- **Day 2-3:** If downloads + extraction exceeds pace, expand to all 46 countries overnight
- **Day 4:** If case study writing is fast, add Zambia + Sri Lanka comparisons
- **Track actual time spent** in LOG.md per task (document reality vs. estimate)

### Decision 10: The Boilerplate Insight → Central Strategic Theme

**Decision:** Make the boilerplate insight the centerpiece of the roundtable narrative.

**Rationale:**
- Teal's domain expertise: "It's so boring so much of the time because they say exactly the same thing. And then it's trying to find the thing that's like a little bit different."
- Reshapes the entire framing: corpus is a change-detection tool, not just a data compiler
- Positions AI as a complement to human expertise (finding what changed)
- Explains why the project matters: commoditization of prospectus reading

**Implementation:**
- Open the roundtable with this insight
- Use it to explain extraction strategy: "We're not cataloging 100% of every document; we're finding the ~10% that varies"
- Frame the MVP as: "Here's a system that spots that 10% automatically"
- Post-Monday roadmap: "The future product is a change-detection system for sovereign debt contracts"
- Diff-based analysis becomes the strategic pivot

**Talking Point:** 
> "Sovereign bond prospectuses are ~90% boilerplate — literally copy-paste with minor changes. That's not a bug, it's the economics of the market. The value is in systematically finding the ~10% that varies. That's what this corpus is for."

---

## Summary: Why These Decisions Work Together

1. **Senegal** (Decision 1) + **boilerplate insight** (Decision 10) = Strong narrative arc (extensibility + variation-finding)
2. **Claude Code CLI** (Decision 2) + **grep-first approach** (Decision 7) = Efficient, compute-lean extraction
3. **`--dangerously-skip-permissions`** (Decision 3) + **safeguards** = Fast iteration without ceremony
4. **Time budget** (Decision 4) + **MVP+Expansion** (Decision 8) = Flexibility + clear scope
5. **PDIP comparison** (Decision 5) + **hand-verification** (throughout) = Credibility with lawyers
6. **AI time estimates** (Decision 9) = Opportunity for scope expansion if early wins emerge

---

*Decisions ratified March 24, 2026*
*Ready for execution March 25-29*
*Presentation at #PublicDebtIsPublic roundtable March 30, 2026*
