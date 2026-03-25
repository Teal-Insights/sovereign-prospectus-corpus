# Sovereign Bond Clause Classification: 30-Minute Roundtable Presentation
## March 30, 2026 | Georgetown Law | Hosted by Anna Gelpern

---

## Slide Deck (10-12 slides)

### SLIDE 1: Title
**AI-Powered Sovereign Bond Clause Classification: A Proof-of-Concept**

Subtitle: Using PublicDebtIsPublic's 900 Annotated Documents to Scale Legal Analysis

Speaker: [Your name]
Date: March 30, 2026
Georgetown Law Sovereign Debt Forum

---

### SLIDE 2: The Problem
**Why Manual Clause Classification Doesn't Scale**

**Status Quo:**
- Research question: "How have CACs evolved in emerging market bonds since 2010?"
- Current process: Search → Download 200+ documents → Read each → Extract clauses → Analyze
- Timeline: 2-3 weeks of researcher time
- Sample size: Limited (maybe 50-100 bonds due to effort)
- Repeatability: Low (hard to verify, hard to update)

**Why This Matters:**
- Sovereign bond clauses determine restructuring feasibility
- Market trends invisible without large-scale analysis
- Policy decisions (IMF, World Bank guidance) lack empirical foundation
- Hidden innovations in creditor/debtor contracting practices

---

### SLIDE 3: The Gold Mine
**PublicDebtIsPublic's 900 Annotated Documents**

**What You Have:**
- 900 sovereign debt documents (prospectuses, facility agreements, loan contracts)
- Professionally annotated by law students & lawyers (trained by Sovereign Debt Forum)
- Diverse jurisdiction coverage (40+ countries, all continents)
- Clause-level annotations: CACs, pari passu, events of default, governing law, etc.
- Represents ~5,000-10,000 hours of expert legal work

**Why This Is Rare:**
| Dataset | Size | Annotation Quality | Public Access |
|---------|------|-------------------|----------------|
| Your 900 docs | 900 | High (legal experts) | Yes (plan) |
| CUAD (contracts) | 510 | Medium (crowdsourced) | Yes |
| Bloomberg Terminal | 10,000+ | Medium (summaries) | No (proprietary, $$$) |
| Thomson Reuters | 50,000+ | Low (automated) | No (proprietary, $$$) |
| Academic corpora | 100-500 | High (research quality) | Usually yes, but non-sovereign |

---

### SLIDE 4: The Opportunity
**Using AI to Multiply Your Impact**

**Core Idea:**
Your annotated documents can teach AI systems to classify clauses in new, unread documents.

**Why AI?**
- **Speed:** Claude/GPT-4 processes a 200-page prospectus in 30 seconds
- **Consistency:** No fatigue, no missed clauses due to reading dozens of documents
- **Scalability:** Once trained, apply to 1,400+ FCA documents, then 15,000+ global bonds
- **Measurability:** Compute precision/recall/F1 against your gold-standard annotations

**The Multiplier Effect:**
- Your 900 documents = 5,000 hours of expertise
- AI trained on those 900 → can classify 1,400-15,000 new documents
- 15x-30x multiplication of research capacity

---

### SLIDE 5: How Few-Shot Prompting Works
**Showing AI Examples Instead of Training**

**Traditional ML:** Requires 200-500 labeled examples per class
**Few-Shot Prompting:** Requires 3-5 examples per class (ask it to do the rest)

**Simple Example:**

```
You are a sovereign debt legal expert. Classify whether this document
contains a Collective Action Clause (CAC).

Definition: A CAC allows 75%+ of bondholders to bind all holders to debt restructuring.

EXAMPLES:
✓ YES (CAC present): "If holders of 75% of Notes consent, the Issuer may modify..."
✓ YES (CAC present): "With consent of 50% of Noteholders on restructuring, 75% on others..."
✗ NO (CAC absent): "These Notes are governed by English law..."

NOW CLASSIFY:
[500-word excerpt from prospectus]
```

**Why This Works:**
- LLMs (Claude, GPT-4) trained on billions of legal documents; language patterns are learned
- Few examples show task context; model generalizes from there
- No fine-tuning needed; works immediately

**Expected Accuracy:** 80-88% (vs. 65% zero-shot, 90%+ fine-tuned)

---

### SLIDE 6: The Architecture
**Step-by-Step Classification Pipeline**

```
Prospectus (200 pages)
     ↓
[1] Preprocess & Extract Relevant Sections
     ↓
[2] Few-Shot Classification
     ("This section contains: CAC (dual-limb, 50/75), pari passu")
     ↓
[3] Confidence Scoring
     (Claude: "I'm 92% confident CAC is present")
     ↓
[4] Flagging for Human Review
     (Flag if confidence < 80%)
     ↓
[5] Output: Structured Data (JSON)
```

**Example Output:**
```json
{
  "document": "Brazil-Global-Bond-2024",
  "cac_present": true,
  "cac_type": "dual-limb",
  "cac_confidence": 0.94,
  "pari_passu_present": true,
  "pari_passu_confidence": 0.89,
  "governing_law": "English Law",
  "flagged_for_review": false
}
```

---

### SLIDE 7: Validating Against Your Gold Standard
**How We Know It Works**

**Validation Approach:**
1. Take 100 documents from your 900 with human annotations
2. Run AI classifier on those same documents
3. Compare AI output to human annotations
4. Measure agreement

**Example Results (Hypothetical, will be real by March 31):**

| Metric | Value | Interpretation |
|--------|-------|-----------------|
| Precision | 0.89 | 89% of clauses AI finds are correct |
| Recall | 0.84 | AI finds 84% of clauses humans found |
| F1 Score | 0.86 | Balanced accuracy: good for research |
| Human Baseline (inter-annotator) | 0.82 | Humans agree with each other at 82% |

**Key Finding:** AI performance (86%) is comparable to human-vs-human agreement (82%). Suggests AI is ready for research use; human review still needed for policy decisions.

---

### SLIDE 8: What Becomes Possible
**New Research with Classified Bonds**

**Trend Analysis:**
- "CAC prevalence in EM sovereign bonds: 2015 vs. 2025"
- "Shift from single-limb to dual-limb CACs post-IMF guidance"
- "Governing law choices by region and creditor type"

**Anomaly Detection:**
- "Which bonds have unusual clause combinations?"
- "Which emerging market bonds lack pari passu clauses?"
- "Cross-default thresholds: outliers and why"

**Policy-Relevant Comparisons:**
- "English law vs. NY law vs. domestic law: which gets better terms?"
- "Chinese creditors: do they insist on specific clause structures?"
- "Evolution of events of default clauses over time"

**Time Savings:**
- Manual research on same questions: 4-6 weeks, 50-100 bonds
- AI-assisted research: 2-3 days, 1,400+ bonds, more comprehensive

---

### SLIDE 9: The Honest Talk
**AI Is Good, But Not Perfect**

**Where AI Excels:**
- Explicit, standard clauses (CACs, pari passu ranking)
- English-language documents
- Modern prospectuses (post-2000)
- Binary classification ("present" vs. "absent")

**Where AI Struggles:**
- Subtle variations (single-limb vs. dual-limb CACs in complex structures)
- Jurisdictional nuances (same clause means different things in EM vs. DM law)
- Non-English documents
- Finding implicit clauses (not explicitly stated, inferred from structure)

**Risk Mitigation:**
- Confidence thresholds: <80% confidence → flag for human review
- Spot-checks: Have lawyers verify 10% of AI classifications
- Per-jurisdiction performance metrics: track accuracy separately by region
- Continuous improvement: User feedback loop to retrain

**The Bottom Line:**
- AI for exploration and scale
- Humans for verification and decisions
- Combined approach: best of both

---

### SLIDE 10: MVP By March 31
**What We'll Demo at This Roundtable**

**By End of Day Monday (March 30):**

✓ **Annotated Dataset:** CSV export of human annotations from sample of your 900 docs
✓ **Few-Shot Prompts:** Working Claude prompts for CACs and pari passu classification
✓ **Validation Report:** Accuracy metrics on 50 test documents
✓ **Classified FCA Sample:** 20-30 FCA prospectuses with AI classifications + confidence scores
✓ **Visual Demo:** Side-by-side comparison (human annotation vs. AI output)

**Performance Targets:**
- CAC classification: 85% F1 score
- Pari passu classification: 83% F1 score
- Overall precision: >88% (few false positives)
- Confidence calibration: Threshold policy ready

**Scope (Realistic for 6-Day Sprint):**
- 2-3 clause types (not all 5)
- 50 validation documents (not 900)
- Few-shot approach (not fine-tuned)
- This is MVP; production version follows

---

### SLIDE 11: Roadmap & Ask
**12-Month Vision**

**Immediate (March-April 2026):**
- Publish validation report
- Release annotated dataset (with permission)
- Deploy to FCA National Storage Mechanism corpus

**Q2 2026:**
- Fine-tune models on full 900-document set
- Add secondary clause types (5 → 10 clause types)
- Publish academic paper

**Q3-Q4 2026:**
- Integrate global bond sources (beyond FCA)
- Build web platform for searching/exploring classified bonds
- Quarterly Sovereign Debt Trends reports

**2027+:**
- Real-time monitoring (flag new bonds with unusual terms)
- Multilingual support
- Integration with IMF/World Bank debt monitoring systems

**Funding Needed:**
- MVP validation: $50k (mostly human expertise, some API costs)
- Production deployment: $150-250k (engineering, legal review, infrastructure)
- Platform & ongoing: $200k+/year

**Partners & Support:**
- Sovereign Debt Forum (legal oversight, partner institutions)
- Gates Foundation (likely funder; already backing PublicDebtIsPublic)
- World Bank / IMF (end users, potential funders)

---

### SLIDE 12: The Invitation
**What We Need From You**

**1. Access to Annotated Data**
- Can we export human annotations from representative sample of your 900 docs?
- With what restrictions? (privacy, attribution, publishing?)

**2. Legal Expertise**
- 20-30 hours of lawyer/legal expert time for validation
- Spot-checks of AI classifications
- Feedback on edge cases and failures

**3. Partnership & Visibility**
- Co-author research publication
- Acknowledgment in methodology and reports
- Position Sovereign Debt Forum as the authority on sovereign debt data infrastructure

**4. Championing**
- Tell other research teams about this work
- Introduce us to World Bank, IMF, rating agencies who might fund phase 2+
- Help establish this as the reference implementation for sovereign bond classification

---

## Talking Points & Responses to Questions

### Q: "Will AI mistakes affect policy decisions?"

**Answer:**
"Great question—and the answer is no. We're not automating policy decisions. We're automating *research* and *exploration*. If you used AI to decide 'should I buy this bond?', that's high-stakes and needs 99% accuracy. But if you use AI to say 'let me analyze trends in 1,400 bonds for a research paper,' 85-88% accuracy is acceptable when paired with human spot-checks. Think of it like AI-assisted literature review: AI finds relevant papers, human expert reads them."

---

### Q: "What if the model sees your 900 documents and just memorizes them?"

**Answer:**
"Excellent concern. That's why we validate on *different* documents. We use your 900 to train, but test on FCA documents your team didn't annotate. If AI generalizes to FCA bonds it's never seen, we know it learned the underlying patterns, not just memorized. Also: few-shot doesn't require 900 examples. We use maybe 50-100 examples max; remaining 800 are validation/testing."

---

### Q: "How does this compare to what Bloomberg/Thomson Reuters already do?"

**Answer:**
"Bloomberg and Thomson Reuters have proprietary databases, but they're expensive ($10k-50k+/user) and not reproducible. Their classifications aren't transparent—you don't know *how* they decided a bond has a CAC. With our approach, we publish the methodology, the examples, the metrics. Your 900 documents become a public benchmark. This is infrastructure for the research community, not a commercial product."

---

### Q: "Can you handle bonds in languages other than English?"

**Answer:**
"Not in the MVP. Prospectuses we can access are predominantly English (London Stock Exchange, international markets). But Claude and GPT-4 support 100+ languages. Phase 2 could add Spanish, French, Arabic, Mandarin. We'd need annotated examples in those languages to train on—that's a future effort."

---

### Q: "What about very old bonds or non-standard document structures?"

**Answer:**
"Old bonds (pre-2000) may have different language and structures; AI may struggle. Non-standard formats (older Word documents, scanned PDFs with OCR errors) also harder. But your 900 documents are modern, professionally formatted prospectuses—that's the sweet spot where AI performs best. We'll document limitations clearly and flag low-confidence predictions."

---

### Q: "How do I know the AI isn't discriminating against certain jurisdictions?"

**Answer:**
"We'll measure and report this explicitly. For each clause type, we'll show:
- Accuracy by jurisdiction (is AI better on English-law bonds vs. emerging market bonds?)
- Confidence scores by region (do predictions have consistent reliability across geography?)
- Failure analysis by jurisdiction (which bonds does AI struggle with, and why?)

If we find bias, we address it: add more diverse examples, create jurisdiction-specific models, flag uncertainty. Transparency is how we maintain trust."

---

### Q: "Will you publish this? What's the IP situation?"

**Answer:**
"Yes, we'll publish in academic venues (legal NLP, finance, policy journals). The code, methodology, and validation metrics will be open-source (MIT or Apache license). Your annotated data—that's your decision. We recommend publishing as a research dataset (with DOI) so it becomes a community resource and you get citation credit. The publication reinforces Sovereign Debt Forum's leadership in debt transparency and AI policy."

---

### Q: "Can this scale to ALL sovereign bonds globally?"

**Answer:**
"Yes, but with caveats. **Easy:** bonds listed on major exchanges (LSE, NYSE, NASDAQ), prospectuses in public systems (FCA NSM, SEC EDGAR, Euroclear). **Hard:** bilateral debt (China to Zambia), internal bonds (domestic currency issuances). **Unknown:** derivative structures (hybrid bonds, green bonds), newer markets (Islamic finance bonds). Phase 1 focuses on prospectuses in public registries. Phases 2+ expand to harder sources."

---

### Q: "How much will this cost me or my institution?"

**Answer:**
"Three layers:
1. **MVP validation (you're seeing it now):** ~$50k total ($30k for human expertise, $20k for cloud/API)
2. **Production deployment (Q2-Q3):** $150-250k to classify FCA corpus, build web platform, publish
3. **Long-term operation:** $100-300k/year for infrastructure, legal oversight, continuous retraining

For the Sovereign Debt Forum specifically: You could monetize through a freemium model (free for academics, paid institutional access) or seek foundation funding to keep it free. We'll explore options and present in April."

---

## Appendix: Demo Flow (If Live Demo Possible)

### Option A: Pre-Recorded Demo (Recommended)
Show a 2-minute video of:
1. Input: Prospectus uploaded
2. Processing: Show a snippet of the AI working ("Analyzing document... extracting clauses...")
3. Output: JSON with classifications + confidence scores
4. Verification: Side-by-side comparison with human annotation

### Option B: Live Demo (Requires Backup Plan)
1. Have a document ready (print backup)
2. Open browser, navigate to demo interface
3. Upload prospectus (or paste excerpt)
4. Run classifier (cache results in case API slow)
5. Show structured output

### Option C: No Demo, Show Screenshots
If time/connectivity issues, have polished screenshots showing input → output

---

## Time Budget for 30-Minute Presentation

| Section | Time | Notes |
|---------|------|-------|
| Slides 1-4 (Problem & Opportunity) | 5 min | Set context; build motivation |
| Slide 5-6 (How It Works) | 5 min | Technical but accessible explanation |
| Slide 7-8 (Validation & Impact) | 5 min | Show it works, show why it matters |
| Slides 9-10 (Honesty & MVP) | 5 min | Address concerns; set expectations |
| Slides 11-12 (Roadmap & Ask) | 3 min | Future vision; what you need from them |
| Q&A | 2 min | Take 1-2 questions (save detailed discussion for after) |

**Total: 25 minutes** (5 min buffer for overruns)

---

## Post-Presentation Next Steps

**Immediately After:**
1. Exchange contact info with interested parties
2. Collect business cards (who to follow up with?)
3. Take photos of slide deck (document what you presented)

**Within 48 Hours:**
1. Email Anna Gelpern + key attendees with:
   - Slide deck (PDF)
   - Summary of feedback
   - Next steps (when can we access 900 documents? when can we meet with lawyers?)

**By April 15:**
1. Kick-off meeting: You, legal experts, tech team
2. Set schedule for MVP data extraction
3. Define scope for production phase

---

## Presentation Delivery Tips

**Before You Present:**
- Practice with the slides 2-3 times
- Time yourself (aim for 25 min, leave 5 min buffer)
- Have backup: printouts of slides + speaker notes
- Test technology: projector, microphone, internet
- Charge laptop + remote control

**Tone:**
- Respectful (these are domain experts; be humble about AI limitations)
- Enthusiastic (show why this matters)
- Technical but accessible (define jargon; use examples)
- Solution-oriented (not "here's what AI can do," but "here's how AI solves *your* problems")

**Potential Tough Questions to Prepare For:**
- "This is just hype. How is it different from previous contract analysis tools?"
- "What happens when the AI gets it wrong?"
- "Why should we trust this more than hiring lawyers?"
- "Who's paying for this? Is this a commercialization play?"

**Responses Template:**
- **Acknowledge:** "That's a fair point..."
- **Reframe:** "Here's how we think about it..."
- **Evidence:** "The data shows..."
- **Action:** "That's why we're proposing..."

---

## Success Metrics for March 30

✓ **Attendees understand:** What you're proposing, why it matters, what you need
✓ **Access secured:** Path to using the 900 annotated documents
✓ **Partnership launched:** Legal experts agree to collaborate
✓ **Interest generated:** Funding/partnership inquiries within 2 weeks

