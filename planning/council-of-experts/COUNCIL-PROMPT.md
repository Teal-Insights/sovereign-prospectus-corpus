# COUNCIL-OF-EXPERTS PROMPT
## Sovereign Bond Prospectus Corpus — Strategic Questions for AI Review

**Prepared:** March 24, 2026  
**For:** Council-of-experts consultation across Claude Opus 4.6, ChatGPT Pro, and Gemini Pro Deep Think  
**Context Document:** See CONTEXT-PACK-FOR-COUNCIL.md (paste relevant sections)  
**Deadline:** March 30, 2026  
**Teal's Role:** Rapid prototyping via AI-augmented development; you are helping us avoid mistakes and surface blind spots

---

## HOW TO USE THIS DOCUMENT

1. **For Claude Opus 4.6:** Paste this prompt + CONTEXT-PACK-FOR-COUNCIL.md (Section A always, then relevant section(s) for the question). Ask for structured feedback on the numbered core questions.

2. **For ChatGPT Pro:** Same approach. Ask: "I have 6 days and these constraints. What's your take on the top 3 risks?"

3. **For Gemini Pro Deep Think:** Same. Request: "Extended reasoning on questions 4-6. What failure modes am I missing?"

4. **Council Synthesis:** Read all three responses. Note where they disagree (especially useful). Extract top 3 recommendations from each. This becomes your decision framework for the next 6 days.

---

## CORE QUESTIONS

### 1. Pipeline Architecture: Is This Sound?

**Context to Paste:** Section A + Section E (Pipeline Architecture)

**Sub-Questions:**

- **Download Pipeline:** Three components: (1) NSM API query, (2) two-hop URL resolution (HTML metadata page → PDF link), (3) exponential backoff with resumable checkpoints. Is this the right architecture? What failure modes am I not seeing?
  
- **SQLite as Metadata Store:** We're using SQLite for tracking downloads, extracted clauses, and processing status. It's local, ACID, no DevOps overhead. For a solo researcher on a Mac Mini, is this the right choice? Should we consider PostgreSQL instead (over-engineered?) or ditch the database and just use files + JSON (under-engineered?).

- **Two-Hop URL Problem:** ~55% of NSM links point to HTML metadata pages that require fetching, parsing, and extracting the actual PDF link. This doubles request count. The alternative is browser automation (Selenium) for direct PDF extraction, but that's slower. Should we accept the two-hop latency?

- **Robustness Against Mac Mini Restarts:** We're implementing checkpoint resumability (JSON file tracking last successful download). If the Mac Mini loses power mid-download, we resume from checkpoint. Is this adequate? Should we implement atomic file writes or transaction logs?

**What We're Trying To Get At:** Are we building a robust, maintainable system, or am I over-engineering for a 6-day PoC?

---

### 2. Prioritization: What Do We Focus On First?

**Context to Paste:** Section A + Section H (Constraints and Success Criteria)

**Sub-Questions:**

- **Download Volume vs. Extraction Quality:** We could aim for 500+ PDFs downloaded (breadth) or 2-5 deeply processed documents with hand-verified clause extractions (depth). The roundtable will include sovereign debt lawyers — they'll spot poor quality immediately. Which impresses more: big numbers or high accuracy on a small sample?

- **Which Countries to Prioritize:** We identified Ghana (28 filings, restructured 2024), Zambia (28 filings, restructured 2024), Sri Lanka (11 filings, restructured 2024), and Senegal (absent from NSM, debt distress imminent, case study gold). Should we focus all effort on these 4 (depth + policy relevance) or cast wider net across 10 countries (breadth)?

- **The Senegal Question:** Senegal is NOT in NSM but IS accessible via Euronext Dublin. It's in active debt crisis (131% debt-to-GDP, restructuring expected H2 2026). We can manually download 3 Senegal Eurobonds and process them deeply. Is this worth it given time constraints? Or should we stick with NSM data?

- **Breadth vs. Depth Trade-Off:** Given 6 days, we can either: (a) download 500+ documents and extract clauses from 80% of them (quick prompts, confidence threshold 0.7), or (b) download 150 documents and extract clauses from 100% with hand verification (confidence threshold 0.95). Which sells better at the roundtable?

**What We're Trying To Get At:** In a constrained timeline, quality and relevance beat quantity. What's the minimum viable set for credibility?

---

### 3. The "Validation Set" Pitch: Is This Compelling?

**Context to Paste:** Section A + Section B (Event and Audience) + Section C (PDIP Platform)

**The Core Claim:** "PDIP's 900 hand-annotated documents are a validation set that catalyzes AI-powered classification at scale. Here's what that means: you annotate the contract terms in 900 documents. We train (or few-shot prompt) an AI model on those 900. That model can then accurately extract the same terms from thousands more documents. That's how you scale from 900 to 9,000."

**Sub-Questions:**

- **Audience Reception:** The roundtable includes sovereign debt lawyers, IMF/World Bank economists, policymakers, and civil society researchers. Will lawyers be skeptical of AI doing clause extraction ("You can't trust machines with legal interpretation")? Will economists find the transparency angle compelling? How do we frame the pitch for each audience segment?

- **The Counterarguments:** What are the weakest points in this pitch that a skeptical lawyer will attack?
  - "AI can't be trusted for legal analysis"
  - "You need human experts to catch nuance"
  - "This is just automating work that requires human judgment"
  - "What about liability if the AI misses something?"
  
  How do we preempt or address each?

- **Validation Set as Metaphor:** Is "validation set" the right framing for a lawyer/policymaker audience? Would "gold standard" or "foundation for scaling" resonate better? Does the machine-learning terminology land or confuse?

- **What Would Make This Stronger:** Beyond downloading documents, what would make the pitch unassailable? 
  - A-B comparison: AI extraction vs. PDIP's manual annotations (accuracy metrics)?
  - Case study showing AI caught something PDIP missed (or vice versa)?
  - Lawyers endorsing the approach (get Anna Gelpern on record?)?

**What We're Trying To Get At:** We have a theoretically sound idea (AI-assisted scaling). Does it play well in the room we're in?

---

### 4. Technical Risks: What Will Go Wrong?

**Context to Paste:** Section E (Pipeline Architecture) + Section D (Data Sources)

**Major Risk Areas:**

- **PDF Parsing Failure Rate:** Prospectuses are complex, multi-hundred-page legal documents with varied formatting, embedded tables, footnotes, boilerplate sections. What's a realistic failure rate for Docling? Should we budget for 5% of PDFs being unreadable (due to scans, images, OCR-heavy pages)? How do we handle failures gracefully?

- **Clause Extraction Accuracy:** Claude can identify and extract structured clauses from legal text. But prospectuses have variations:
  - CACs might be buried in nested sections
  - Pari passu language might be modified or absent (not all bonds have it)
  - Events of default can be scattered across multiple sections
  - Language varies widely (some bonds are US-style, some are English, some are Sharia-compliant)
  
  What's a realistic extraction accuracy? How do we measure it? What confidence thresholds should we use for the roundtable demo?

- **Rate Limiting (NSM):** We haven't actually hammered the NSM API at scale. We reverse-engineered it with 156 queries, but bulk downloading 300+ documents means 300+ download requests. What if NSM implements rate limiting mid-project? Fallback: Euronext Dublin and Luxembourg have more friction (no direct API), slower.

- **Data Quality Issues:** We know NSM data is messy (name variants, metadata gaps, some broken links). How much manual exception handling should we budget for? If 5% of links are broken/stale, that's 15-20 documents we can't download — is that acceptable?

- **False Positives in Clause Extraction:** Claude might hallucinate clause language that doesn't exist ("I don't see the pari passu clause in this prospectus" vs. Claude saying "The pari passu clause says X" when it doesn't). How do we catch and prevent this? What's our verification strategy?

**What We're Trying To Get At:** Where will this pipeline actually break? What's a realistic degradation path?

---

### 5. The Roundtable Pitch: How Do We Frame This?

**Context to Paste:** Section B (Event and Audience) + Section A (What We're Building)

**Three Versions:**

- **One-Sentence:** Give us the tightest, most memorable sentence that captures this project for someone walking out of the roundtable.

- **Five-Minute Pitch:** Assume we have 5 minutes at the mic. Anna Gelpern wrote "If Boilerplate Could Talk" — how do we frame our work as extending hers? The roundtable scoping document emphasizes three pillars (information, technology, legal infrastructure). Where do we fit? What's the 5-minute story that makes the lawyers in the room lean forward?

- **Differentiated Messaging:**
  - **For Sovereign Debt Lawyers:** How does this make their research easier? What problems does it solve?
  - **For Policymakers/IMF/World Bank:** How does this support better policy and debt management?
  - **For Civil Society/Transparency Advocates:** How does this advance the transparency agenda?

**Narrative Arc:** What's the story we're telling?
  - Problem: Prospectuses are 90% boilerplate. The 10% that varies is where policy value lives. Can't compare that variation at scale.
  - Solution: AI extraction + searchable database.
  - Proof: We built it in 6 days and it works.
  - Vision: This is what "transparency infrastructure" could look like.

**What If:** What if Anna Gelpern or someone in the room asks, "But aren't you just automating something that should stay manual?" How do you answer?

**What We're Trying To Get At:** How do we tell this story compellingly to a room of experts who are skeptical of technology?

---

### 6. What Are We Missing?

**Context to Paste:** All sections (this is a meta-question, no specific context)

**Open-Ended Questions:**

- **Important Aspects of Sovereign Debt Contracts We're Not Thinking About:** Beyond CACs, pari passu, and events of default, what else matters? 
  - Subordination structures?
  - Collateral provisions (especially relevant post-China lending)?
  - Carve-outs for official creditors?
  - Amendment mechanics?
  - Intercreditor arrangements?
  
  Which should we prioritize if we're thinking beyond this PoC?

- **Other Researchers/Projects Doing Similar Work:** Are there other groups building AI-powered contract analysis? Are there academic papers on automated clause extraction in sovereign debt? Should we reference or cite prior work?

- **Data Sources We Haven't Considered:** SEC EDGAR, Luxembourg Stock Exchange, Euronext Dublin are on our Phase 2 list. Are there other venues we're missing? Central banks' bond registers? International depositories (Euroclear, Clearstream)?

- **Analytical Capabilities Beyond Clause Extraction:** Once we have extracted clauses, what else could we do?
  - Clause evolution over time (track how Ghana's CACs changed from 2019 → 2024)?
  - Correlation analysis (do countries with strict CACs have lower default rates)?
  - Anomaly detection (flag unusual language that differs from market standard)?
  - Natural language comparison (measure linguistic distance between Ghana's CAC and Nigeria's)?

- **Post-Monday: Path from PoC to Something Real:** What would a funded version look like? PDIP has $382k from Gates Foundation. If we got similar funding, what would be the roadmap? What's the sustainable business model / institutional home?

**What We're Trying To Get At:** We've designed a 6-day sprint. Are we solving the right problem? Are there adjacent opportunities we should keep in mind?

---

### 7. Honest Assessment

**Context to Paste:** Section H (Constraints and Success Criteria)

**Brutal Questions:**

- **Confidence Level (1-10):** On a scale of 1-10, how likely is it that we have something genuinely impressive for Monday? By "impressive," I mean:
  - Technically sound (code works, no crashes)
  - Substantively interesting (lawyers think "this is clever")
  - Connected to the roundtable agenda (advances the conversation on transparency infrastructure)

- **Single Biggest Risk:** If I had to bet on ONE thing going wrong, what would it be?
  - NSM API blocks bulk requests (rate limiting)
  - Clause extraction is too inaccurate to show off
  - We run out of Mac Mini disk space
  - Something else I'm not seeing

- **What Would You Cut:** If we run out of time, what's the least critical component?
  - Multi-country comparison (focus on just Ghana + Zambia case study)?
  - Dashboard mockup (just show data in CSV + Jupyter)?
  - Secondary data source research (stick with NSM only)?
  - Clause extraction accuracy verification (skip hand-checking)?

- **What Would You Add:** If we had 2 extra days (March 24-May 2), what's the one thing that would make this much stronger?
  - Full PDIP integration (access their 900 documents, compare AI extraction to their manual annotations)?
  - SEC EDGAR integration (add US-listed sovereigns)?
  - Trained classification model (rather than few-shot prompting)?
  - Interactive dashboard?

- **Honest Comparison to Q-CRAFT:** The Q-CRAFT project succeeded in 7 days because the problem was well-scoped, the domain was narrow, and we had a clear validation set (the Excel model to match against). Do we have the same clarity here? Or is this messier?

- **If You Were Teal, What Would You Do Differently:**
  - More aggressive scoping (fewer countries, deeper analysis)?
  - Different tool choices (different PDF parser, different LLM, different database)?
  - Different framing for the roundtable (play up transparency infrastructure vs. play up AI capability)?

**What We're Trying To Get At:** Reality check. Are we being too ambitious? Too conservative? Are we solving the right problem the right way?

---

## DESIRED OUTPUT

Please think through these seven questions carefully. I'd like your response in this format:

### 1. Pipeline Architecture Assessment
- **Sound / Needs Changes / Fundamentally Wrong** [Pick one]
- **Key decision:** SQLite vs. PostgreSQL vs. files?
- **Recommendation:** [1-2 sentence]

### 2. Recommended Prioritization for Next 6 Days
- **Countries to focus on:** [List, with rationale]
- **Download target:** [# of documents]
- **Extraction target:** [# with verified clauses]
- **Breadth vs. Depth:** [Your recommendation]

### 3. "Validation Set" Pitch Assessment
- **Strong / Weak / Needs Reframing** [Pick one]
- **Main vulnerability:** [What skeptics will attack]
- **Fix:** [How to address it]

### 4. Top 3 Technical Risks & Mitigation
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Risk 1 | High/Med/Low | High/Med/Low | [Action] |
| Risk 2 | ... | ... | ... |
| Risk 3 | ... | ... | ... |

### 5. Recommended Roundtable Framing
- **One-Sentence:** [Your version]
- **Five-Minute Narrative:** [Brief summary of story arc]
- **For Skeptics:** "But isn't this just automation?" [Your answer]

### 6. What We Might Be Missing
- **Important contract dimensions we haven't considered:** [List]
- **Other projects/researchers doing similar work:** [If you know of any]
- **Post-Monday roadmap:** [1-2 key next steps if this works]

### 7. Your Honest Assessment
- **Confidence Level (1-10):** [Your number, with brief why]
- **Single Biggest Risk:** [The one thing I should worry about most]
- **What I'd Cut:** [If time pressure hits, sacrifice this]
- **What I'd Add:** [If we had 2 more days]
- **If You Were Teal:** [One recommendation]

---

## A Note on Tone

Please be **direct and disagreeable**. This isn't cheerleading; it's strategic advice.

If you think we're missing something obvious, say it.  
If you think the timeline is unrealistic, say it.  
If you'd recommend a completely different approach, say it.  
If you spot a flaw in the "validation set" framing that will land badly in the room, flag it now, not on Monday.

We have 6 days and we'd rather hear hard truths now than discover problems on Sunday night.

---

## How the Council Works (Process Notes)

1. **Three Models, Three Perspectives:**
   - Claude Opus 4.6 (architectural reasoning, system thinking)
   - ChatGPT Pro (domain knowledge, creativity)
   - Gemini Pro Deep Think (extended reasoning, problem decomposition)

2. **Synthesis:**
   - Read all three responses
   - Note disagreements (most valuable signal)
   - Extract top 3-5 recommendations
   - Make decisions accordingly

3. **Iteration:**
   - Monday (March 24): Council feedback → architectural decisions
   - Tuesday-Wednesday: Execution
   - Thursday: Mid-course council check-in if needed
   - Friday: Presentation prep

4. **Trust the Process:**
   - Q-CRAFT used this methodology successfully
   - Three models catch what one model misses
   - Disagreement > consensus (forces you to think deeper)

---

**Prepared by Teal Insights**  
**For the Sovereign Bond Prospectus Corpus Project**  
**March 24, 2026**

*"We're not asking for permission. We're asking for perspective. Help us see what we're missing."*

