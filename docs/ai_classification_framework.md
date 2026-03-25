# AI-Powered Sovereign Bond Clause Classification Framework
## A Proof-of-Concept for the PublicDebtIsPublic Platform

**Prepared for:** Georgetown Law Sovereign Debt Forum Roundtable
**Hosted by:** Anna Gelpern, Agnes N. Williams Research Professor
**Date:** March 30, 2026
**Status:** Proof-of-Concept Framework

---

## Executive Summary

The #PublicDebtIsPublic initiative has assembled approximately 900 human-annotated sovereign debt documents with legally trained annotations of critical clauses: Collective Action Clauses (CACs), pari passu provisions, events of default, negative pledges, and governing law specifications. This represents an exceptionally rare and valuable "gold-standard" dataset for training AI classification systems.

This document proposes a classification pipeline that:
1. Extracts the human annotations as a validation benchmark
2. Uses few-shot and fine-tuning approaches with large language models (Claude, GPT-4)
3. Applies trained classifiers to the FCA National Storage Mechanism corpus (~1,400+ prospectuses)
4. Demonstrates AI-at-scale capabilities while maintaining human oversight
5. Opens pathways for trend analysis, cross-country comparison, and anomaly detection

**Timeline for proof-of-concept:** 6 days (by March 30, 2026)
**Realistic scope:** 50-100 document pipeline demonstration with 2-3 clause types
**Long-term vision:** All publicly available sovereign bonds globally, real-time monitoring platform

---

## Part 1: The Validation Set Concept

### 1.1 What We Have

The #PublicDebtIsPublic platform currently houses approximately **900 sovereign debt documents** with human-annotated clauses. These documents include:

- Bond prospectuses (various currencies and jurisdictions)
- Loan agreements and facility agreements
- Official statements and supplementary prospectuses
- Annotations by law students, lawyers, and legal specialists trained by the Sovereign Debt Forum

### 1.2 What This Means for AI

Human-annotated legal datasets are extraordinarily rare. Most AI systems in legal tech work with either:
- **No labeled data** (deploying zero-shot models with inherent uncertainty)
- **Small labeled datasets** (<100 examples, subject to overfitting)
- **Proprietary or inaccessible datasets** (Bloomberg Terminal, Thomson Reuters, etc.)

Your 900 documents represent:
- **Rare gold-standard data:** Legally competent human judgment across multiple annotators
- **Documented jurisdiction diversity:** Global coverage (emerging markets, developed economies, bilateral and multilateral creditors)
- **Clause density:** Real-world occurrence of variations (single-limb vs. dual-limb CACs, strict vs. loose pari passu, events of default sub-types)
- **Research foundation:** Basis for measuring AI reliability at scale

### 1.3 Conversion Strategy: Documents → Training/Validation Resource

**Phase 1: Extraction (Days 1-2)**
- Parse human annotations from the 900 documents
- Standardize annotation schema (clause type, location, specific language, variations)
- Build a JSON/CSV index with metadata: document source, date, jurisdiction, currency, clause presence/absence
- **Deliverable:** Structured annotation dataset (~800-900 labeled examples)

**Phase 2: Stratification (Day 3)**
- Randomly stratify by jurisdiction, document type, date, creditor type (bilateral, multilateral, market)
- Create train/validation splits (80/20 or 70/15/15)
- Identify edge cases: documents with zero occurrences, ambiguous annotations, conflicting expert opinions
- **Deliverable:** Train/val/test splits with documented composition

**Phase 3: Baseline Metrics (Day 4)**
- Compute inter-annotator agreement (Cohen's kappa, Fleiss' kappa if >2 annotators per document)
- Establish human performance ceiling on test set
- Document annotation guidelines and variations
- **Deliverable:** Baseline performance report

### 1.4 Why This Matters for Your Pitch

To Anna Gelpern and the roundtable:
> "Your 900 documents are not just a corpus—they're a validation benchmark. We can measure whether AI gets to 85% agreement with human lawyers, 90% agreement, or 95%. That measurement is what funds more work, justifies deployment in policy contexts, and identifies which clause types are AI-ready vs. require human review."

---

## Part 2: Classification Pipeline

### 2.1 Architecture Overview

```
Input: Prospectus (100-200 pages, ~50,000-100,000 tokens)
    ↓
[Document Preprocessing & Chunking]
    ↓
[Few-Shot Classification OR Fine-Tuned Model]
    ↓
[Clause Location & Extraction]
    ↓
[Confidence Scoring & Flagging]
    ↓
Output: Structured Annotations + Confidence Scores
```

### 2.2 Document Preprocessing

**Challenge:** Prospectuses are long documents. Claude Opus and GPT-4 can handle 100k+ tokens, but processing efficiency and cost matter.

**Strategy 1: Strategic Chunking (for large-scale deployment)**
- Split prospectus into logical sections: Cover, Summary, Terms, Risk Factors, Covenants, Events of Default
- Prioritize sections where clauses typically appear (Covenants, Terms, Events of Default, Definitions)
- For each chunk: run classification, return clause locations with line numbers
- **Cost:** ~1-2 API calls per document (vs. 5-10 for brute-force chunking)

**Strategy 2: Hierarchical Approach (for highest accuracy)**
- First pass: Search for clause keywords/patterns (regex, keyword matching)
- Second pass: Send candidate sections + surrounding context to LLM for confirmation
- **Cost:** Lower LLM costs, but requires robust keyword lists

**Strategy 3: Embeddings + Retrieval (for future scale)**
- Embed clause definitions and human-annotated examples
- Use semantic search to find similar text in new documents
- Have LLM confirm/refine matches
- **Cost:** Minimal LLM usage after one-time embedding

### 2.3 Clause Classification Approaches

#### Option A: Few-Shot Prompting (Recommended for MVP)

**Principle:** Provide 3-5 examples of each clause type, ask model to classify new text.

**Prompt Template:**
```
You are a sovereign debt legal expert. Classify the following text snippets
as containing or not containing a [CLAUSE TYPE] clause. Explain your reasoning.

A [CLAUSE TYPE] clause [DEFINITION].

EXAMPLES:
Example 1 (Positive): "[Example text from human annotation]"
→ Classification: YES, [CLAUSE TYPE] present. Reasoning: [...]

Example 2 (Negative): "[Example text]"
→ Classification: NO. Reasoning: [...]

NEW TEXT TO CLASSIFY:
"[Section from prospectus]"

Your classification: [YES/NO/UNCLEAR]
Confidence: [HIGH/MEDIUM/LOW]
Reasoning: [...]
```

**Advantages:**
- No fine-tuning required; works immediately
- Explainable reasoning from model
- Works across clause variations
- Few API calls per document

**Disadvantages:**
- Requires carefully curated examples (from your 900 documents)
- Context length limits how many examples you can provide
- Prone to error on edge cases if examples not comprehensive

**Expected Performance:** 75-85% agreement with human annotations (varies by clause type)

#### Option B: Fine-Tuning (for production deployment)

**Principle:** Train a model-specific classifier on your human-annotated data.

**Approach:**
- Use your 80% training split to fine-tune a model (Claude via API or GPT-4)
- Evaluate on 20% validation split
- Deploy fine-tuned version to new documents

**Advantages:**
- Higher accuracy (85-92%+ depending on clause type)
- Faster inference
- Learns clause-type-specific language patterns
- Can learn subtle variations

**Disadvantages:**
- Requires sufficient data per clause type (200+ examples recommended)
- Takes 1-2 days for training & validation
- More expensive upfront
- Harder to explain individual decisions

**Expected Performance:** 85-92% agreement with human annotations

#### Hybrid Approach (Recommended)

For the March 30 roundtable and beyond:
1. **Immediate (by March 30):** Few-shot approach on 2-3 clauses (CACs, pari passu, events of default)
   - Demo on 50-100 new documents
   - Show human annotation comparisons
   - Measure inter-annotator agreement vs. AI agreement

2. **Next phase (April-May):** Fine-tuning on all 900 documents for all clause types
   - Full classification pipeline for all 1,400+ FCA documents
   - Production-ready system with documented performance

3. **Longer term:** Ensemble approach + active learning
   - Combine multiple classifiers
   - Flag uncertain predictions for human review
   - Gather human feedback to continuously improve

---

## Part 3: Accuracy Metrics & Validation

### 3.1 Metrics to Report

For a domain-expert audience, you need **precision**, **recall**, **F1 score**, and **confidence intervals**—not just accuracy.

#### Binary Classification (Clause Present / Absent)

For each clause type, compute:

```
Precision = TP / (TP + FP)
  → Of clauses AI says are present, how many actually are?
  → High precision = fewer false alarms (good for scanning, bad for missing stuff)

Recall = TP / (TP + FN)
  → Of clauses humans found, how many did AI find?
  → High recall = fewer missed clauses (good for compliance, costs more review time)

F1 = 2 × (Precision × Recall) / (Precision + Recall)
  → Harmonic mean; useful when you want balance

Confidence Interval (95%)
  → "Our CAC classifier is 87% ± 3.2% accurate at 95% confidence"
```

#### Span-Based Extraction (Location & Specific Language)

For clauses where exact location matters:

```
Token-level F1 (average pairwise)
  → Measure how well AI locates exact clause language
  → Metric: overlap of predicted span vs. human span

Partial Match Ratio
  → AI found ~80% of the clause text (coarse-grained)
  → Useful for showing "found it, missed some details"
```

#### Inter-Annotator Agreement (Human Baseline)

Before comparing AI to humans, report how well humans agree with each other:

```
Cohen's Kappa (k) = (observed agreement - expected agreement) / (1 - expected agreement)

Interpretation:
  k < 0.20   → Slight agreement
  0.20-0.40  → Fair agreement
  0.40-0.60  → Moderate agreement
  0.60-0.80  → Substantial agreement
  0.80+      → Almost perfect agreement

Your 900 documents:
  → If human annotators have k=0.78, AI at k=0.74 is nearly human-level
  → If human k=0.85, AI at k=0.74 suggests you need more training data or examples
```

### 3.2 Reporting Template for March 30

```
CLAUSE TYPE: Collective Action Clause (CAC)

Data:
  Train set: 150 documents with CAC, 480 without
  Validation set: 38 documents with CAC, 120 without

Human Baseline (inter-annotator agreement):
  Cohen's Kappa: 0.82 (substantial agreement)

AI Performance (Few-Shot Approach):
  Precision: 0.89 (87% of predicted CACs are correct)
  Recall: 0.84 (AI found 84% of CACs humans marked)
  F1 Score: 0.86
  Confidence Interval (95%): 0.86 ± 0.04

Interpretation:
  "On unseen documents, AI identifies CACs with 89% precision. This means
  it rarely flags non-CACs as CACs. It misses ~16% of CACs, so human review
  is essential for compliance purposes, but for research/scanning/trend
  analysis, AI performance is sufficient."

Failure Analysis:
  [Most common mistakes: dual-limb CACs mistaken for single-limb;
   retroactive restructuring not recognized; jurisdiction-specific variations]
```

### 3.3 Confidence Scoring

For deployment, have the model output confidence:

```json
{
  "document_id": "FCA-NSM-2024-001",
  "clause_type": "pari_passu",
  "present": true,
  "confidence": 0.94,
  "location": "Section 3.1, lines 45-67",
  "excerpt": "The Notes shall at all times rank pari passu...",
  "flagged_for_review": false,
  "reasoning": "Clear pari passu language with standard ranking clause"
}
```

**Threshold Policy:**
- Confidence > 0.90: Auto-approve for research, flag for manual verification
- Confidence 0.70-0.90: Flag for human review before final classification
- Confidence < 0.70: Require human judgment (don't use AI output)

---

## Part 4: Clause Taxonomy & Definitions

### 4.1 Core Clause Types for MVP

For your roundtable demo, focus on 2-3 clause types. Here's a taxonomy:

#### 1. Collective Action Clause (CAC)

**Definition:** A provision allowing a supermajority of bondholders to bind all holders to a debt restructuring.

**Key Variations:**
- **Single-limb CAC:** One vote threshold (often 75%) to bind minority
- **Dual-limb CAC:** Separate thresholds for principal (50%) and interest (25%)
- **Retroactive CAC:** Applies to past debts; current market standard post-2014
- **Modification:** Can clause terms be changed via vote? (affects severity)

**Sample Language:**
```
"If holders of not less than 75 per cent. in aggregate principal amount of
the outstanding Notes consent, the Issuer may, with the consent of the
Fiscal Agent, and notwithstanding the consent of each other Noteholder,
effect any modification of these Terms and Conditions which the Issuer and
the Fiscal Agent deem necessary and desirable..."
```

**Why It Matters:**
- Stronger CACs → easier restructuring → more creditor risk but less default risk
- IMF and World Bank now require CACs in new issuances
- Market evolution: emerging markets adopted post-2014; developed markets still debating

**Classification Challenges:**
- Retrofit CACs (added later) vs. original issuance
- Mutual agreement clauses (easier threshold, but requires all parties)
- Subordination clauses that interact with CACs

---

#### 2. Pari Passu Clause

**Definition:** A promise that the issuer's obligation ranks equally with all other unsecured, unsubordinated debt.

**Key Variations:**
- **Pure Ranking:** "ranks pari passu with..." (no payment obligation)
- **Ranking + Payment:** "...and shall share pro rata in any distribution" (ratable payment)
- **Limited Exceptions:** "except as required by law" vs. broad carve-outs
- **Subordinated Debt Scope:** What counts as "subordinated"? (affects practical ranking)

**Sample Language:**
```
"The Notes will constitute unsubordinated and unsecured obligations of the
Issuer and shall at all times rank pari passu with all other present and
future unsecured and unsubordinated obligations of the Issuer."
```

**Why It Matters:**
- Pari passu clauses protect creditors from being ranked below other creditors
- Litigation risk: Argentina case (2011-2014) over pari passu interpretation
- Modern interpretation: no ratable payment obligation unless explicitly stated
- Interaction with negative pledge: should work together

**Classification Challenges:**
- Negative pari passu ("does not rank junior to...") is technically pari passu
- Implied pari passu through section structure vs. explicit language
- Multiple pari passu statements across prospectus (reconcile to one classification)

---

#### 3. Events of Default

**Definition:** Conditions that, if triggered, allow the issuer or creditor to accelerate debt or trigger remedies.

**Key Variations:**
- **Payment Default:** Non-payment of principal or interest (always present)
- **Covenant Breach:** Violation of other promised terms (cross-default, incurrence tests)
- **Material Adverse Change (MAC):** Broad catch-all; varies in definition
- **Creditor Cross-Default:** Default on other debt triggers default here (ranges from 10M to 500M+ thresholds)
- **Political Events:** Moratorium, expropriation, force majeure (especially in emerging markets)
- **Sovereignty Events:** Change of law, transfer of territory, nationalization

**Sample Language:**
```
"If any principal or interest in respect of the Notes is not paid when due,
or if the Issuer defaults in the performance or observance of any other
obligation under these Conditions and, in the case of the latter, such
default continues for the period of 30 days, any Noteholder may declare
the Notes to be due and payable at their principal amount..."
```

**Why It Matters:**
- Defines when creditors have recourse
- More/stricter events of default → more creditor protection but higher issuer cost
- Political events clauses critical for emerging market bonds
- Threshold amounts (10M payment default vs. 1M) vary widely

**Classification Challenges:**
- Extracting all events, not just payment default
- Identifying cross-default thresholds and other debt categories
- Counting cross-defaults separately (one EoD might trigger multiple events)

---

#### 4. Negative Pledge

**Definition:** A promise that the issuer will not pledge assets as collateral without offering same security to these bondholders.

**Key Variations:**
- **Broad Negative Pledge:** Prohibits all asset pledging (rare, restrictive)
- **Partial/Carve-Outs:** Allows pledging up to X% of assets, or for specific purposes (refinancing, working capital)
- **Pari Passu Remedy:** If issuer does pledge, these bonds rank pari passu with pledged debt
- **Release:** Can collateral be released under certain conditions? (Project completion, ratings upgrade)

**Sample Language:**
```
"So long as any of the Notes remain outstanding, the Issuer shall not,
and shall procure that no Material Subsidiary will, create, assume or
permit to exist any Lien upon any of its properties or assets unless
the Notes shall be equally and ratably secured..."
```

**Why It Matters:**
- Protects unsecured creditors from subordination through pledging
- Works in tandem with pari passu clause
- Often waived for project finance, refinancing
- Enforcement depends on jurisdiction and other creditor agreements

**Classification Challenges:**
- Distinguishing between covenant (negative pledge) and event of default
- Carve-outs: "except for liens existing on the date hereof" (grandfather clauses)
- Cross-references to other sections (definitions, exceptions elsewhere)

---

#### 5. Governing Law & Jurisdiction

**Definition:** Specifies which legal system governs interpretation and enforcement.

**Key Variations:**
- **English Law** (common, predictable, internationally recognized)
- **New York Law** (alternative for US issuers)
- **Issuer's Domestic Law** (higher political risk, less creditor protection)
- **Jurisdiction:** Separate from governing law; where disputes are litigated
  - English courts (UK)
  - New York courts (US)
  - Issuer's domestic courts (political risk)

**Sample Language:**
```
"These Conditions shall be governed by and construed in accordance with
English law, and each of the Issuer and any Noteholder irrevocably submits
to the jurisdiction of the English courts."
```

**Why It Matters:**
- English/New York law = more creditor-friendly, lower political risk
- Issuer's domestic law = more political risk, but may be required by domestic law
- Trend: Emerging markets increasingly opting for English law
- Interaction with CACs: English law enables better enforcement

**Classification Challenges:**
- Dual jurisdictions (English law, NY courts)
- Carve-outs ("except for injunctive relief in any court")
- Changes over time (issuer's domestic law may change; courts may reinterpret)

---

### 4.2 Extended Taxonomy (for later phases)

Once you've mastered the core 5, expand to:

- **Acceleration:** Ability to declare debt immediately due upon default
- **Rollover Clauses / Extension Options:** Can debt maturity be extended? (affects restructuring feasibility)
- **Subordination:** Does this debt rank below others? (reverse of pari passu)
- **Put Options / Mandatory Prepayment:** Can creditors force early repayment?
- **Currency Specifications:** Original issue currency vs. payment currency (FX risk)
- **LIBOR/Benchmark Transitions:** How are interest rates reset post-LIBOR?
- **Stabilization Clauses:** Can creditor's vote be overridden by issuer for policy reasons?

---

## Part 5: The Pitch to Anna Gelpern & the Roundtable

### 5.1 Opening: The Opportunity

> "The #PublicDebtIsPublic platform represents a watershed moment for sovereign debt research. You've assembled ~900 human-annotated documents—a dataset that, to my knowledge, doesn't exist elsewhere in public form.
>
> That dataset is valuable for three reasons:
> 1. **Validation:** It lets us measure whether AI can match human expert judgment
> 2. **Training:** It gives AI systems examples to learn from
> 3. **Scale:** It proves that the legal knowledge embedded in your annotations can extend to thousands of documents currently inaccessible to researchers
>
> Today, I want to show you how."

### 5.2 The Problem Framing

> "Right now, if you want to know: 'How many emerging market bonds issued since 2020 have single-limb CACs vs. dual-limb?' or 'Has the prevalence of pari passu clauses changed in Latin American debt?' you have to:
>
> 1. Manually search FCA filings or Bloomberg Terminal
> 2. Read each prospectus (50-200 pages)
> 3. Find and interpret the relevant clauses
> 4. Manually record results in a spreadsheet
>
> This takes weeks for a moderate-sized research question. Months if you want global coverage.
>
> Meanwhile, your 900 documents contain the legal knowledge to automate this. The question is: can we teach AI to capture that knowledge?"

### 5.3 The Solution: Few-Shot Prompting with Human Oversight

> "Here's how we'd do it:
>
> **Step 1: Extract Your Annotations**
> Take your 900 documents and convert the human annotations into a dataset: 'This document contains a CAC, specifically dual-limb, retroactive.' Extract 50-100 examples per clause type, stratified by region and date.
>
> **Step 2: Teach AI via Examples**
> Use few-shot prompting: give Claude or GPT-4 five good examples of 'CAC present' and five 'CAC absent,' then ask it to classify new documents.
>
> **Step 3: Measure Against Your Gold Standard**
> Run the AI classifier on 100-200 documents that human experts also annotated. Compare:
> - How often does AI agree with humans? (Should be 85-92%)
> - Where does it fail? (Edge cases, jurisdiction-specific language, etc.)
> - Can we improve agreement by refining examples or prompt wording?
>
> **Step 4: Scale Confidently**
> Once AI performance is validated, apply it to the 1,400+ FCA National Storage Mechanism documents. Now you have:
> - Full-text prospectuses with flagged clauses
> - AI confidence scores for each classification
> - Structured data (CAC type, pari passu presence, governing law, etc.) that's machine-readable
>
> **Step 5: Enable New Research**
> Your team can now:
> - Trend analysis: CAC prevalence over time, by region, currency
> - Anomaly detection: 'Which bonds have unusual clause combinations?'
> - Creditor analysis: 'Which issuers have Chinese creditors? What are their governing laws?'
> - Comparative law: 'How does English law vs. NY law affect CAC adoption?'"

### 5.4 Key Message: AI Complements Humans

> "This is not about replacing lawyers. It's about **multiplication**:
>
> Your 900 annotated documents represent maybe 1,000-2,000 hours of expert legal work. That work embedded legal judgment into structured annotations.
>
> With AI, those 1,000-2,000 hours of judgment can now inform the analysis of 1,400 new documents (or 10,000 global bonds). AI surfaces patterns, flags anomalies, and makes comparable data. Human experts then verify the most important findings and make policy decisions.
>
> For a policy roundtable, the honest framing is:
> - AI classification: 85-92% accuracy, good for research & exploration
> - Human expert review: still required for investment decisions, policy statements, litigation
> - Combined: best of both—speed and scale from AI, judgment and accountability from humans"

### 5.5 Addressing Concerns

**"Will AI mistakes harm creditors or debtors?"**

> "No, because we're not automating legal decisions—we're automating document analysis for research purposes. If you were using AI to decide 'should I buy this bond?', that's high-stakes and requires 99%+ accuracy. But if you're using AI to say 'let me analyze trends in 1,400 sovereign bonds to inform my research,' 85% AI accuracy plus human spot-checking is sufficient. We'll measure AI confidence and flag uncertain predictions for human review."

**"What if the AI is trained on only 900 documents? Won't it overfit?"**

> "Good question. That's why we'll:
> 1. Use few-shot prompting (no fine-tuning needed) for the MVP
> 2. Fine-tune only after validating few-shot approach
> 3. Stratify training/validation to detect overfitting
> 4. Test on documents outside the 900 (FCA corpus) to measure real-world performance
> 5. Continuously evaluate as we scale to new bonds"

**"Which clauses are easiest? Hardest?"**

> "Likely easy: CACs and pari passu (explicit language, rarely omitted, high human agreement)
>
> Likely harder: Events of default (multiple types, distributed throughout document, subtle variations)
>
> Unknown until we test: Negative pledge (depends on how consistently it's worded), governing law (should be easy, but may be stated multiple ways)
>
> That's why the validation framework matters. We'll identify which clause types are AI-ready vs. need more work."

---

## Part 6: What Could Be Demoed by Monday, March 30, 2026

### 6.1 Realistic Scope: 6-Day Sprint

Assuming you start now (March 24, 2026) and want a working demo for March 30:

**Days 1-2 (March 24-25):**
- Extract annotations from 5-10 well-annotated documents from PublicDebtIsPublic
- Build a few-shot prompt for CACs and pari passu clauses
- Test prompt on 3-4 human-annotated documents (internal validation)

**Days 3-4 (March 26-27):**
- Apply few-shot classifier to 20-30 NEW documents from FCA National Storage Mechanism
- Have a human lawyer spot-check 5-10 classifications
- Measure basic accuracy: "AI correctly identified 17/20 CACs" (85%), etc.

**Days 5-6 (March 28-29):**
- Prepare demo slideshow:
  - Before/after: document → AI classification → structured output (JSON, table)
  - Accuracy metrics: "87% precision on CACs, 84% recall"
  - 2-3 failure cases: show where AI struggled, explain why
  - Roadmap: "This is the MVP; here's what full version looks like"
- Dry-run presentation with colleagues

### 6.2 Deliverables for March 30

**Technical Deliverables:**
1. **Annotated Dataset:** CSV/JSON of 100-200 human annotations from your 900 documents
   ```csv
   document_id, document_name, clause_type, present, excerpt, jurisdiction, date
   PDP-001, Argentina-2009-Global, CAC, TRUE, "If holders of...", AR, 2009-03-15
   ...
   ```

2. **Few-Shot Prompts:** 2-3 working prompts for CAC, pari passu classification
   ```
   system_prompt: "You are a sovereign debt legal expert..."
   few_shot_examples: [...]
   test_results: {
     precision: 0.87,
     recall: 0.84,
     f1: 0.86
   }
   ```

3. **Classified Documents:** 50 FCA prospectuses with AI classifications
   ```json
   {
     "document_id": "FCA-NSM-2024-001",
     "clauses": {
       "cac": { "present": true, "confidence": 0.94, "type": "dual-limb" },
       "pari_passu": { "present": true, "confidence": 0.89 },
       "governing_law": "English Law"
     },
     "flagged_for_review": false
   }
   ```

4. **Validation Report:** One-pager showing:
   - Accuracy metrics (precision/recall/F1)
   - 2-3 case studies (one success, one failure)
   - Recommendations for next phase

5. **Presentation Deck:**
   - 8-10 slides (15-20 minute talk)
   - Problem framing
   - Architecture diagram
   - Accuracy metrics
   - Live demo (optional: classify a document in real-time)
   - Roadmap & ask

**Policy/Research Outputs:**
- Quick trend analysis: "Of 50 FCA docs analyzed, 72% have CACs (vs. ~60% in 2015)"
- Anomaly report: "These 3 bonds have unusual clause combinations"
- Jurisdictional comparison: "English law: 94% CACs; Issuer domestic law: 32% CACs"

### 6.3 If You Need More Time (Do This Instead)

If 6 days is too tight, reduce scope:
- Focus on ONE clause type (CACs) instead of 2-3
- Use 10 human-annotated examples instead of 50-100
- Demo on 20 documents instead of 50
- Use synthetic examples (write CACs yourself) + real examples (mix)

This still shows the concept and takes 3-4 days.

---

## Part 7: Longer-Term Vision

### 7.1 Months 2-4 (April-June 2026): Production-Ready System

**Expand Scope:**
- Fine-tune on all 900 documents for all 5 clause types
- Classify entire FCA corpus (~1,400 documents)
- Add secondary clauses: rollover clauses, acceleration, subordination
- Build web interface for searching classified documents

**Measure Impact:**
- Complete accuracy report (per clause type, per jurisdiction)
- Comparison to Bloomberg Terminal / Thomson Reuters (if available)
- Identify clause evolution: single-limb → dual-limb CACs, English law prevalence, etc.

**Deliverables:**
- Fully classified FCA database (searchable, downloadable)
- Academic paper: "AI-Assisted Annotation of Sovereign Debt: Validating Large Language Models Against Expert Judgment"
- Capacity-building toolkit for PublicDebtIsPublic: how to use AI classifiers

### 7.2 Months 5-12 (July-December 2026): Global Sovereign Bond Database

**Integrate Multiple Data Sources:**
- FCA National Storage Mechanism (already done)
- Bloomberg Terminal (via API, if available)
- SSRN/BIS working papers (sovereign debt documents)
- IMF Debt Statistics database
- World Bank/ADB project documents
- Historical archives (BIS, World Bank)

**Build a Real-Time Monitoring Platform:**
- Ingest new bond issuances automatically (via Reuters, Bloomberg feeds, official issuer announcements)
- Run AI classification immediately upon issuance
- Alert users to significant changes: "Major shift in CAC types in LatAm sovereigns"
- Track trends: maturity profiles, clause evolution, creditor concentration

**Enable Research & Policy:**
- Quarterly Sovereign Debt Trends report (Gelpern et al., co-authored with AI)
- Early warning system: "These 5 countries have increasing refinancing pressure"
- Negotiation toolkit: "Here's what peers in your region are doing; here are the clause variations you have flexibility on"

### 7.3 Year 2+: Global Scale & Real-Time Governance

**Targets:**
- ~15,000+ sovereign bonds globally (all public sources)
- 50+ jurisdictions
- Real-time ingestion (daily updates)
- Multilingual support (Spanish, French, Chinese, Arabic prospectuses)

**User Base:**
- Policymakers (central banks, finance ministries, debt management offices)
- Creditors (institutional investors, rating agencies)
- Debtors (finance ministries planning issuances)
- Researchers (academics, think tanks, civil society)

**New Capabilities:**
- Generative AI: "Summarize the key terms of this bond vs. peers"
- Anomaly detection: "This clause is unusual given issuer's credit rating; why?"
- Negotiation support: "Here are the most favorable terms in English law bonds; here's your ask"
- Risk monitoring: "Cross-default trigger levels are rising; systemic refinancing risk?"

**Governance:**
- Transparency: document AI confidence, update notes
- Expert oversight: quarterly review by Sovereign Debt Forum legal committee
- Bias monitoring: ensure AI works equally well across regions (not just English-speaking bonds)
- Feedback loop: allow users to flag errors, train model on corrections

---

## Part 8: Technical Stack & Recommendations

### 8.1 Model Selection

**For MVP (few-shot, immediate):**
- **Claude 3.5 Sonnet** or **GPT-4 Turbo**
- Why: Best legal domain performance, few-shot capabilities, cost-effective
- Cost: ~$0.03-0.05 per document (50 documents = $1.50-2.50)
- Speed: 10-15 seconds per document (50 docs in ~10 minutes)

**For Production (fine-tuning):**
- **Fine-tuned Claude** (if available) or **OpenAI fine-tuned GPT-4**
- Why: Better accuracy, faster inference, better control
- Cost: Higher upfront (fine-tuning) + lower per-inference cost
- Speed: 2-5 seconds per document

**For Global Scale (Year 2+):**
- Consider open-source models: **LLaMA 3**, **Mistral**, fine-tuned on your annotations
- Why: Cost, privacy (on-prem), customization
- Trade-off: slightly lower accuracy than Claude/GPT-4, but still 80%+

### 8.2 Infrastructure

**For prototype (Weeks 1-2):**
- Google Colab or local Jupyter notebook
- Manual CSV uploads
- Direct API calls to Claude/OpenAI

**For MVP (Weeks 3-4):**
- Simple web interface (Flask/Streamlit)
- Database: PostgreSQL (CloudSQL or self-hosted)
- API calls to Claude/OpenAI
- GitHub for version control

**For Production (Months 2-4):**
- Cloud infrastructure: Google Cloud / AWS
- Scalable API (FastAPI)
- Vector database for embeddings (Pinecone, Weaviate)
- Monitoring & logging (Cloud Logging, Sentry)
- CI/CD (GitHub Actions)

### 8.3 Cost Estimate

**MVP (March 30 Demo):**
- API calls (100 documents × 2-3 API calls × ~$0.01/call): ~$2-3
- Human review (10 hours at $150/hr): $1,500
- Infrastructure: $0

**Phase 2 (Full FCA Corpus, 1,400 documents):**
- API calls (few-shot or fine-tuning): $300-500
- Human validation (50 hours): $7,500
- Fine-tuning (if done): $2,000-3,000
- Infrastructure (Cloud): $500-1,000

**Year 1 Full Scale (15,000 documents + real-time monitoring):**
- Infrastructure: $50k-100k/year (cloud, monitoring)
- Human oversight (lawyers): $100k-200k/year
- Model fine-tuning & maintenance: $20k-50k/year
- Total: $170k-350k/year (funded by grants, policy institutions, freemium model)

---

## Part 9: Key Risks & Mitigation

### 9.1 Technical Risks

| Risk | Mitigation |
|------|-----------|
| AI hallucination (makes up clauses that don't exist) | Provide strong negative examples in few-shot prompts; require clause location + excerpt; confidence thresholds |
| Jurisdiction-specific language not in training set | Test on diverse jurisdictions; add regional variants to examples; flag low-confidence predictions |
| Long documents (100+ pages) cause context loss | Strategic chunking; focus on high-probability sections first; hierarchical classification |
| Updates to models (Claude 4, GPT-5) change behavior | Version control prompts; continuous validation; retrain when models update |

### 9.2 Legal & Policy Risks

| Risk | Mitigation |
|------|-----------|
| AI classification used for actual legal decisions (litigation, restructuring) | Clear messaging: AI for research only. Human expert review required for decisions. |
| Bias: AI works better for English-language bonds, worse for emerging markets | Evaluate performance per region; add regional examples; external audit |
| Privacy/confidentiality: prospectuses contain identifying information | All inputs already public (FCA NSM); use de-identified outputs in research; document data handling |
| Model misuse: AI-generated classifications presented as authoritative without human review | Require citation of confidence scores; flag uncertain predictions; human sign-off |

### 9.3 Governance Risks

| Risk | Mitigation |
|------|-----------|
| "AI told me the CAC was present, but I didn't verify" (user error) | Strong user education; prominent warnings; default to "flagged for review" for confidence < 0.85 |
| Rapid change in bond market practices | Continuous retraining; user feedback loop; quarterly model updates |
| Creditor misuse: use AI to cherry-pick favorable clauses for argument | Transparent documentation; publish full methodology; independent validation |

---

## Part 10: The Ask

### To Anna Gelpern and the Sovereign Debt Forum:

1. **Validation:** We need access to the 900 annotated documents (or a representative subset) with clear documentation of which annotations are most reliable.

2. **Expertise:** We need 20-30 hours of legal expert time to:
   - Validate our clause taxonomy
   - Review AI classifications (spot-checks)
   - Provide feedback on failure cases

3. **Partnership:** Positions the Sovereign Debt Forum as the authority on sovereign debt clause classification, with AI as a tool to extend your work.

4. **Funding:** For phases 2-4, we'll seek grants from:
   - Gates Foundation (already interested in PublicDebtIsPublic)
   - World Bank / IMF (data infrastructure)
   - Open Society Foundations (fiscal transparency)
   - Academic institutions (research collaborations)

### Longer-term (Year 2+):

If we build a global platform, we propose:
- **Freemium model:** Individual researchers use free; institutions pay
- **Revenue split:** 60% to Sovereign Debt Forum (operational costs, legal review), 40% to developer/tech partner
- **Governance:** Sovereign Debt Forum maintains editorial oversight; changes require legal committee consensus

---

## Appendix A: Sample Few-Shot Prompt

```
You are a sovereign debt legal expert with 10+ years of experience analyzing
bond prospectuses and loan agreements. Your task is to classify whether a
given prospectus excerpt contains a specific clause type.

CLAUSE TYPE: Collective Action Clause (CAC)

DEFINITION: A Collective Action Clause (CAC) is a provision allowing a
supermajority of bondholders (typically 75% or more) to vote to modify the
terms of a bond (including principal amount, interest rate, or maturity date)
in a way that is binding on all bondholders, including those who voted against
it. CACs facilitate debt restructuring by enabling creditors to reach collective
agreement without requiring unanimous consent.

---

EXAMPLES:

Example 1 (POSITIVE - Single-limb CAC):
Document: Brazil Global Bond Prospectus, 2022
"If holders of not less than 75 per cent. in aggregate principal amount of
the outstanding Notes consent by way of an Extraordinary Resolution to any
modification of the terms and conditions hereof or the Trust Deed which shall
be proposed by the Issuer, such modification shall be binding upon all
Noteholders."

Classification: YES, CAC present
Type: Single-limb (75% threshold applies to all modifications)
Confidence: HIGH
Reasoning: Explicit supermajority threshold (75%) that can bind minority holders
to modifications of principal/interest/maturity. Clear language "binding upon all
Noteholders." Standard issuance post-2014.

---

Example 2 (POSITIVE - Dual-limb CAC):
Document: Mexico Global Bond Prospectus, 2020
"The Issuer may request Noteholders holding at least fifty per cent of the
principal amount of outstanding Notes to vote on a Restructuring Proposal.
The Issuer may request Noteholders holding at least two-thirds of the principal
amount of outstanding Notes to vote on any other modification to the Conditions."

Classification: YES, CAC present
Type: Dual-limb (50% for restructuring, 66.7% for other changes)
Confidence: HIGH
Reasoning: Two separate supermajority thresholds for different modification types.
Lower threshold (50%) for restructuring is more creditor-favorable. Language
"vote on" indicates binding effect.

---

Example 3 (NEGATIVE - Mutual Agreement Clause, Not CAC):
Document: Old Bond Prospectus, 1990s
"No modification of these terms shall be made without the written consent of
the Issuer and the Trustee."

Classification: NO, CAC not present
Confidence: HIGH
Reasoning: This is a mutual agreement clause requiring consent of both issuer
and trustee. There is no mention of a supermajority of creditors voting; in fact,
individual creditors have no collective voice. This is not a CAC.

---

Example 4 (NEGATIVE - No CAC language):
Document: Argentina Bond Prospectus, pre-2003
"These Notes are issued in accordance with the laws of the Republic of
Argentina. All matters concerning these Notes shall be governed by Argentine
law."

Classification: NO, CAC not present
Confidence: HIGH
Reasoning: Document discusses governing law but contains no clause allowing
creditors to vote on modifications. No supermajority thresholds mentioned.
Typical of pre-CAC bonds.

---

Example 5 (BORDERLINE - Soft CAC):
Document: Emerging Market Bond, 2015
"The Issuer may, with the consent of Noteholders holding at least 66 per cent
of the outstanding Notes, modify any of the terms of these Notes by way of a
written notice to the Trustee."

Classification: YES, CAC present
Type: Single-limb (66.7% threshold)
Confidence: MEDIUM-HIGH
Reasoning: Supermajority threshold (66.7%) is present and can bind minority.
However, language "the Issuer may...with the consent of" could be interpreted
as requiring issuer consent + noteholder vote (mutual agreement). Standard
interpretation: CAC because supermajority threshold exists. Confidence is
medium-high because language is slightly ambiguous.

---

NOW CLASSIFY THE FOLLOWING:

DOCUMENT: [INSERT PROSPECTUS EXCERPT, ~500-1000 words]

INSTRUCTIONS:
1. Read the excerpt carefully.
2. Look for language about supermajority voting, modifications binding on all
   creditors, or restructuring proposals.
3. If present, identify: (a) type (single-limb, dual-limb, other), (b) thresholds
4. Provide your classification (YES/NO/UNCERTAIN), confidence level, and reasoning.
5. If YES, provide the exact excerpt that establishes the CAC (quoted).

YOUR RESPONSE (JSON):
{
  "classification": "YES" | "NO" | "UNCERTAIN",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "cac_type": "single-limb" | "dual-limb" | "other" | "N/A",
  "threshold_percentage": 75 | null,
  "excerpt": "[exact text from document]",
  "reasoning": "[Your explanation, 2-3 sentences]",
  "notes": "[Optional: edge cases, ambiguities, questions]"
}
```

---

## Appendix B: Validation Report Template

```markdown
# AI Classification Validation Report
## Clause Type: Collective Action Clauses (CACs)
**Date:** March 29, 2026
**Prepared by:** [Name]
**Reviewed by:** [Legal expert]

---

### Dataset Composition

| Category | Count |
|----------|-------|
| Training Examples Used | 12 |
| Validation Set Size | 50 documents |
| Documents with CAC | 36 (72%) |
| Documents without CAC | 14 (28%) |
| Jurisdictions Represented | 8 (LatAm, EM, DM) |

---

### Model Performance

**Few-Shot Approach** (Claude 3.5 Sonnet, 12 examples)

| Metric | Value | Interpretation |
|--------|-------|-----------------|
| Precision | 0.89 | Of 32 docs AI said had CAC, 28 actually did (87.5%) |
| Recall | 0.78 | Of 36 docs with CAC, AI found 28 (77.8%) |
| F1 Score | 0.83 | Harmonic mean; balanced performance |
| Accuracy | 0.84 | Overall: 42/50 correct |
| **Confidence Interval** | ±0.06 (95%) | True performance is 0.77-0.89 with 95% confidence |

**Human Baseline** (Inter-annotator agreement, if multiple annotators)
- Cohen's Kappa: 0.82 (substantial agreement)
- AI vs. Human agreement: 0.78 (comparable to human-vs-human agreement)

---

### Error Analysis

**False Positives (4 errors: AI said CAC, humans said no CAC)**
1. Document FCA-2024-045: Soft mutual agreement clause mistaken for CAC
   - AI quote: "with the consent of Holders of 66% of Notes"
   - Human note: "Issuer consent required; not a true CAC"
   - Fix: Add negative example of mutual agreement clauses

2. Document EM-2020-012: Voting on covenant waivers, not term modifications
   - AI quote: "Holders representing 75% may vote to waive..."
   - Human note: "Waiver ≠ modification of principal/interest"
   - Fix: Clarify definitions in prompt

**False Negatives (6 errors: AI said no CAC, humans said CAC)**
1. Document ARG-2015-088: Dual-limb CAC with 50%/75% thresholds, structured as separate clauses
   - Human found: Two CAC clauses (one for restructuring, one for other changes)
   - AI found: Only the 75% clause; missed the 50% clause
   - Fix: Add examples of dual-limb structures; improve chunking strategy

2-6. [Similar breakdowns for other misses]

---

### Recommendations

1. **Add more negative examples** to distinguish CACs from mutual agreement clauses
2. **Improve prompt clarity** on the difference between waiver clauses and modification clauses
3. **Consider fine-tuning** on the full 900-document training set for >90% accuracy
4. **Test on 2024 issuances** (outside training set) to measure real-world generalization
5. **Document clause location** (section number) in addition to classification

---

### Confidence Threshold Policy

| Confidence | Recommendation |
|------------|-----------------|
| ≥ 0.90 | Accept AI classification; minimal human review needed |
| 0.70–0.89 | Flag for human spot-check; acceptable for bulk research |
| < 0.70 | Require human decision; do not use AI output without verification |

**Under this policy, 42/50 (84%) of our validation set would be AUTO-APPROVED.** This is a reasonable manual review burden for scaling to 1,400 documents.

---

### Next Steps

1. Roll out to FCA National Storage Mechanism corpus (1,400+ documents)
2. Fine-tune on full 900-document training set
3. Target: 90% accuracy on unseen bonds
4. Integrate into PublicDebtIsPublic search platform

```

---

## Conclusion

The convergence of:
- **Your 900 human-annotated documents** (rare gold-standard data)
- **Modern LLMs** (Claude, GPT-4: capable legal classification)
- **Clear measurement frameworks** (precision/recall/F1, confidence intervals)
- **Real-world scale** (1,400+ FCA documents waiting to be classified)

...creates a unique opportunity to demonstrate AI-assisted legal analysis in service of sovereign debt transparency and research.

The proof-of-concept by March 30, 2026, will show:
1. AI can match human expert judgment (85%+ agreement)
2. This can scale to thousands of documents
3. Researchers gain new capabilities (trends, anomalies, comparisons)
4. Human experts remain essential for verification and policy decisions

**The invitation:** Bring your legal expertise, your 900 documents, and your research questions. Bring your skepticism too. We'll show you what AI can do—and where it still needs humans.

