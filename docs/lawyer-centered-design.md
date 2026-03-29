# Lawyer-Centered Design for the Clause Eval Explorer

Design principles and concrete interaction patterns for a clause evaluation
tool that respects the expertise and time of its users. These lawyers charge
$1,000+/hour in the private sector and are volunteering their time to
annotate sovereign bond clause data. Every design decision should answer:
"does this make their contribution feel valued and efficient?"

---

## Core Design Principle

**The lawyer is validating an extraction, not rating a search result.**

This distinction drives everything. A search result says "we found a
keyword." An extraction says "we believe this is the clause, and here are
the boundaries we propose." The interaction should feel like reviewing a
colleague's draft work product, not triaging a spam filter.

---

## 1. The Primary Object Is the Extracted Clause

### Problem

The current app shows "Grep Candidates" — a list of keyword hits with
surrounding page text. The lawyer has to figure out where the clause starts
and ends within a wall of text. This is the system's job, not theirs.

### Principle

**Show the answer first, then the evidence.** The extracted clause text is
the primary visual element. The full section context is secondary — it's
there for verification, not discovery.

### Concrete design

```
┌─────────────────────────────────────────────────┐
│  CANDIDATE CLAUSE                               │
│                                                 │
│  [Extracted clause text, rendered with           │
│   document-like formatting: headings, numbered   │
│   lists, bold terms. This is what the lawyer     │
│   is validating.]                                │
│                                                 │
├─────────────────────────────────────────────────┤
│  ▸ Section Context (click to expand)            │
│  ▸ Why This Was Surfaced (click to expand)      │
│  ▸ Source Metadata                              │
├─────────────────────────────────────────────────┤
│  DECISION                                       │
│  [Correct] [Wrong Boundaries] [Not a Clause]    │
│  [Partial] [Needs Second Look]                  │
└─────────────────────────────────────────────────┘
```

The section context is available but collapsed. The cue analysis ("why
surfaced") is collapsed. The decision bar is always visible. The lawyer
can validate a clear correct extraction in 5-10 seconds without expanding
anything.

---

## 2. Preserve Document Structure Faithfully

### Problem

The current app collapses single newlines into spaces, destroying numbered
structure and indentation. For legal documents, this is catastrophic.
Numbered paragraphs, lettered sub-clauses, and indentation levels are how
lawyers read clause structure. They communicate scope, hierarchy, and the
relationship between provisions.

### Principle

**The text should look like it does in the document.** Numbered lists
should be numbered. Indentation should be preserved. Headings should be
headings. When a lawyer looks at the extracted clause, they should
recognize it as the same text they would see in the prospectus.

### Concrete design

- Render Docling markdown as sanitized HTML (headings, lists, tables, bold)
- Preserve paragraph breaks and list structure
- Use a serif font (Georgia, Times New Roman) at readable size (14-15px)
- Line height of 1.6-1.7 for comfortable reading
- Provide a "Raw text" toggle for OCR-suspect sections where the markdown
  rendering may be misleading

### What NOT to do

- Do not collapse newlines into spaces
- Do not strip numbered list formatting
- Do not display in monospace/code font (this is a legal document, not code)
- Do not wrap in a tiny scrollable box — give it room to breathe

---

## 3. Table Columns Should Support Triage, Not Just Identification

### Problem

The current table shows: Country, Document, Page, Match. "Match" (the
first 80 chars of the keyword hit) is the least useful column. A lawyer
scanning 200 candidates needs to quickly identify which ones deserve
attention and which are obviously wrong.

### Principle

**Every visible column should help the lawyer decide whether to click.**
If a column doesn't change their decision, it shouldn't be in the default
view.

### Concrete design

| Column | Why it helps triage |
|---|---|
| Country | Groups issuers, sets expectations for clause style |
| Document | Identifies the prospectus |
| Section | "Collective Action Clauses" is reassuring; "Table of Contents" is a red flag |
| Page | Page 47 is plausible for a CAC; page 2 is suspicious |
| Surfaced By | "Heading" is high confidence; "Body cues only" warrants more scrutiny |
| LLM Confidence | Quick signal from the extractor |
| Clause Preview | First 80 chars of the extracted clause (not the keyword hit) |

### What NOT to show in the table

- The raw regex match text (grep artifact)
- Internal IDs or storage keys (developer information)
- Combined confidence scores (obscures the individual signals)

---

## 4. Feedback Should Acknowledge Expertise

### Problem

The current app says "Rate the match with thumbs up / down." This frames
the lawyer as a binary labeler — a mechanical task that doesn't leverage
their expertise. It's also imprecise: "not relevant" could mean "wrong
section," "partial clause," "correct clause but wrong boundaries," or
"this document doesn't have a CAC."

### Principle

**Frame the interaction as expert judgment, not rating.** The copy, the
options, and the interaction pattern should communicate: "we value your
legal expertise and want your specific assessment."

### Concrete design

**Sidebar copy**:
> "Validate clause boundaries. Your expert judgment helps build the first
> open dataset of sovereign bond contract terms."

**Decision options** (not "feedback"):

| Option | Meaning | Color |
|---|---|---|
| Correct Clause | Boundaries are right, this is the clause | Green |
| Wrong Boundaries | It's the clause but starts/ends wrong | Amber |
| Not a Clause | This section doesn't contain the clause | Red |
| Partial Match | Only part of the clause was extracted | Amber |
| Needs Second Look | Uncertain, skip for now | Gray |

**Optional notes field** (collapsed by default, not always visible):
> "If you'd like to explain your assessment (e.g., 'missing aggregation
> sub-clauses'), your notes help improve the system."

### Backlog: boundary editing

When a lawyer selects "Wrong Boundaries" or "Partial Match," offer
paragraph-level boundary controls:

- Extend upward one paragraph
- Extend downward one paragraph
- "Starts here" / "Ends here" markers

This turns the lawyer into a high-value editor rather than a binary
labeler. Their boundary corrections directly improve the training data.

---

## 5. Workflow Should Minimize Friction

### Problem

The current three-card vertical layout encourages scrolling. There is no
keyboard navigation, no auto-advance after a decision, no progress
indicator, and no way to resume where you left off.

A lawyer with 15 minutes to spare should be able to review 20-30
candidates without friction. Currently the interaction pattern is:
scroll table → click row → scroll to context → scroll to feedback →
click button → scroll back to table → find next row.

### Principle

**Optimize for flow state.** The interaction should feel like flipping
through a deck of well-organized briefs, not navigating a web form.

### Concrete design for Monday (minimum)

- **Split-pane layout**: table on left, candidate detail on right
- **Auto-advance**: after a decision, automatically show the next candidate
- **Progress indicator**: "12 of 47 reviewed" visible at all times

### Should-have (if time permits)

- **Keyboard shortcuts**: j/k for next/previous, 1-5 for verdict options
- **Session resume**: remember which candidates have been reviewed
- **Sort by confidence**: show uncertain candidates first (where expert
  judgment adds the most value)

### Backlog

- Estimated time remaining based on rolling average decision time
- "Quick review" mode for high-confidence candidates (show clause only,
  no section context, one-click confirm)
- Batch operations for obviously correct items

---

## 6. Trust Signals Matter

### Problem

The current detail view ends with: "In a production version, each candidate
would link to the original source document." This tells the lawyer: "this
is not a real tool." It undermines trust in the system and in the data.

### Principle

**Every element should build trust, not erode it.** The tool should feel
like it was built by people who care about getting the law right, not by
engineers who think legal documents are interchangeable blobs of text.

### Concrete trust signals

| Signal | Implementation |
|---|---|
| Source link | Link to the original PDF/HTML filing. Even if the link goes to a file on disk, it communicates: "you can verify this yourself." |
| Provenance chain | "Found in section 'Collective Action' (heading match) on pages 47-49 of [document]." |
| Quality warnings | "OCR quality may affect text accuracy" — honest, not hidden. |
| Verification status | "Extracted text verified against source document" — shows the system checks itself. |
| Methodology note | Brief footnote: "Candidates were identified using document structure analysis and verified by Claude Sonnet. Your review is the final validation." |

### What NOT to do

- Do not show internal error messages or stack traces
- Do not say "production version" — this IS the tool
- Do not show developer-facing metadata (run_id, prompt_hash) in the
  default view
- Do not auto-hide quality warnings — transparency builds trust

---

## 7. Copy and Tone

### Problem

The current sidebar says "Proof of concept for the #PublicDebtIsPublic
roundtable. Findings are preliminary." This is accurate but positions the
tool as something not worth taking seriously.

### Principle

**Confident but honest.** The tool should communicate competence and
seriousness about the legal domain, while being transparent about its
limitations.

### Concrete copy guidelines

| Element | Current | Proposed |
|---|---|---|
| App title | "Clause Eval Explorer" | "Clause Eval Explorer" (keep) |
| Subtitle | "Proof of concept... Findings are preliminary." | "Sovereign bond clause extraction for expert review. Part of the #PublicDebtIsPublic initiative." |
| Sidebar instruction | "Rate the match with thumbs up / down." | "Validate clause boundaries. Your expert judgment improves the dataset." |
| How to use | "1. Select... 2. Click... 3. Rate..." | "1. Select a clause type. 2. Review candidates in order. 3. Validate or correct the extraction." |
| Feedback label | "Feedback" | "Your Assessment" |
| Empty state | "Click a row..." | "Select a candidate from the table to review the extracted clause." |

---

## 8. Signals, Not Scores

### Problem

Combining heading match, LLM confidence, and other signals into a single
"high/medium/low" confidence score obscures information. When a lawyer asks
"why does the system think this is high confidence?", the answer should be
specific, not "because the algorithm said so."

### Principle

**Show the components, let the expert synthesize.** Lawyers are trained to
weigh multiple factors. Give them the factors, not a weighted average.

### Concrete design

In the detail view, show a signal panel:

```
Signals
────────────────────────────────
Section:     "Collective Action Clauses" (heading match)
Page range:  47-49
Surfaced by: Heading pattern + 3 body cue families
LLM:         High confidence — "Complete CAC with aggregation provisions"
Length:      2,847 characters (typical clause range)
Components:  ✓ Voting threshold  ✓ Reserved matter
             ✓ Aggregation       ✓ Meeting provisions
```

Each signal has a clear, human-readable meaning. The lawyer can see at a
glance why this candidate was surfaced and how complete the extraction
appears.

---

## 9. Time-to-Decision as a Design Metric

### Principle

If the tool is well-designed, the median time from "candidate displayed"
to "decision made" should be:

- **< 10 seconds** for obviously correct high-confidence extractions
- **30-60 seconds** for uncertain candidates requiring section context
- **2-3 minutes** for complex boundary judgment calls

### How to measure

The feedback log captures `elapsed_seconds` (time from candidate display
to decision submission). Report this as a distribution in the evaluation.

This is not a performance metric for the lawyer — it's a quality metric
for the tool. If median time-to-decision is 3 minutes, the tool is
failing to present information effectively.

---

## Summary: The Don Norman Checklist

| Norman Principle | Application |
|---|---|
| **Visibility** | Show the extracted clause prominently. Show signals, not hidden scores. Show progress. |
| **Feedback** | Immediate visual confirmation of decisions. Auto-advance to next candidate. |
| **Constraints** | Structured decision options (not free text). Keyboard shortcuts for common actions. |
| **Mapping** | Section heading → document location. Cue badges → why surfaced. Confidence signals → what the system knows. |
| **Consistency** | Same layout for every candidate. Same decision flow. Same signal presentation. |
| **Affordance** | Buttons look like decisions, not ratings. Expandable sections invite exploration. Clause text invites reading. |
| **Error prevention** | "Needs second look" prevents forced binary decisions on ambiguous cases. Session resume prevents lost work. |
