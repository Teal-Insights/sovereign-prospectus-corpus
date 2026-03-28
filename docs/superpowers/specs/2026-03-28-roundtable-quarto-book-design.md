# Design Spec: Sovereign Clause Corpus — A Proof of Concept

**Quarto book + Shiny eval explorer for the #PublicDebtIsPublic Scoping Roundtable**

**Event:** March 30, 2026, Georgetown University Law Center
**Audience:** Legal scholars, sovereign debt practitioners, policymakers, civil society — mostly lawyers, not technologists
**Format:** Quarto book (like [QCraft Companion Guide](https://teal-insights.github.io/QCraft-App/)), deployed to GitHub Pages
**Tone:** Confident but humble. Show, don't tell. "Proud but modest" — a proof of concept built in one week, not a finished product.

---

## Purpose

Demonstrate to the #PublicDebtIsPublic community that:

1. Their expert-annotated corpus can be **catalytic** — powering a system that scales clause identification far beyond what manual annotation alone can achieve
2. A working proof of concept already exists — built in one week, open source, using only publicly filed documents
3. There is a clear path from here to a living, trustworthy system for monitoring sovereign debt contract terms — if legal experts help set rigorous evaluation standards

The deliverable is a shareable URL that a roundtable participant can open on their phone or laptop during or after the event.

---

## Structure

### Chapter 1: "What We Built and Why"

**Length:** ~600 words. No code, no jargon.

**Content:**

- Sovereign bond prospectuses are public documents — filed with the SEC in New York, the FCA in London — but in practice, doing cross-country, cross-regional research on contract terms is cumbersome and time-consuming. A researcher studying how collective action clauses vary across African, Latin American, and European issuers would need to navigate multiple filing systems, download documents one by one, and read through hundreds of pages of boilerplate to find the 10% that varies.

- In one week, we built an open-source pipeline that collected 4,800+ sovereign bond prospectuses from three public sources — SEC EDGAR (~3,300 filings), FCA National Storage Mechanism (~900 filings), and the #PublicDebtIsPublic annotated corpus (~823 documents). All parsed, searchable, stored in a single database.

- The #PublicDebtIsPublic corpus is special. It contains 122 documents where legal experts have hand-annotated specific clause types — collective action clauses, pari passu, governing law, events of default, and many more. These expert annotations are the seed that makes everything else possible. We used them to build retrieval patterns that find similar clauses across the much larger SEC and FCA corpora. The more clauses experts review and validate, the more accurate automated identification becomes.

- **Flywheel diagram** (simple, visual):
  ```
  Expert annotation → Pattern extraction → Candidate retrieval across full corpus
       ↑                                                          ↓
  Improved patterns ← Expert review (yes/no + why) ← Candidates served to reviewer
  ```

- Closing: "This is a proof of concept built in one week. The findings are preliminary and the methodology needs expert review. But the infrastructure is open source, and it demonstrates how expert legal knowledge can be made catalytic — scaling the impact of every annotation across thousands of documents."

**Visuals:** One diagram (the flywheel loop). Possibly a small "by the numbers" callout box: 4,800+ documents, 3 sources, 122 expert-annotated, 6,200+ clause annotations.

---

### Chapter 2: "Preliminary Findings"

**Length:** ~400 words of narrative + visualizations + the Shiny app embed.

**Key framing:** "We show these not as findings but as evidence that the approach works and merits expert methodology review."

**Element 1: Static choropleth map — "The Corpus"**

A world map shaded by document count per country across all three sources. Title: something like "4,800+ Sovereign Bond Prospectuses Collected from 3 Public Sources."

- Data source: DuckDB `documents` table + `pdip_clauses` (for country mapping)
- Color: gradient by document count, or color-coded by source
- Caption: "Countries with sovereign bond filings in SEC EDGAR, FCA NSM, and #PublicDebtIsPublic"
- This is the "wow, you already have all of this?" moment for a room of people who work across dozens of countries

**Element 2: Static chart — "What #PublicDebtIsPublic Annotations Reveal"**

A bar chart or summary table showing clause family coverage across the 122 annotated documents. For example: "Experts identified collective action clauses in 37 documents, pari passu in 29, governing law in 71..."

Below it, the retrieval validation summary for 2-3 key families: recall and precision against the #PublicDebtIsPublic ground truth. Clearly labeled "Preliminary — methodology under review."

- Data source: `pdip_clauses` table (annotation counts), `validation_report.json` (precision/recall)
- Show actual numbers, not just percentages: "Found 34 of 37 annotated CAC documents (92% recall)"

**Element 3: Embedded Shiny app — "The Eval Explorer"**

The centerpiece. A small interactive app where someone can:

1. **Pick a clause family** from a dropdown (collective action, pari passu, governing law)
2. **See a table** of candidate matches: country, document title, page number, short excerpt
3. **Click a row** to see full context: text before + **highlighted match** + text after
4. **Click thumbs up / thumbs down** — this IS the eval. The reviewer is doing it right now.
5. If thumbs down, an optional text field: "why not?" (e.g., "mentions CAC but isn't the clause itself")

The app makes the flywheel visceral. A lawyer clicks through 5 matches, thinks "yes, yes, that's not quite right, yes, no" — and they've just experienced what scaled validation feels like. The thumbs up/down makes the feedback loop concrete and tangible.

**Technical notes for the Shiny app:**
- Data: read from `data/pdip/clause_annotations.jsonl` and/or DuckDB `grep_matches` + `pdip_clauses`
- Feedback logging: append to a simple CSV/JSONL (`storage_key, family, matched_text, decision, reason, timestamp`)
- Deployment: embedded in Quarto via `shinylive` or deployed separately and iframe'd
- Keep it minimal — one dropdown, one table, one detail panel, two buttons

---

### Chapter 3: "A Lawyer-in-the-Loop Flywheel"

**Length:** ~800 words. The co-design ask.

**Opening frame:**

#PublicDebtIsPublic has already built something remarkable — 900+ documents from 45+ countries with expert-annotated contract terms. The initiative's five-year plan envisions comprehensive global coverage. This proof of concept demonstrates an approach that could help amplify that rare and valuable legal expertise — making every annotation reach further across the corpus.

**The inversion:**

Today, a legal expert searching for a collective action clause in a prospectus might Control+F for "collective action" or navigate to the section where it typically appears — then read carefully to confirm. Multiply that across hundreds of documents and dozens of clause types. Now imagine: the system surfaces a candidate clause in a browser window. The expert clicks yes or no, and if no, briefly says why. That "why" gets embedded in the system — surfacing better candidates next time. The expert's tacit knowledge about what makes a clause a real CAC (versus something that just mentions collective action in passing) gradually becomes part of the infrastructure itself.

**How evaluation works** (translated for lawyers, drawing on evals research):

- **Binary judgments with reasoning** — a candidate appears on screen. Is this a collective action clause? Yes or no. If no, a brief note on why (wrong section, mentions CAC but isn't one, truncated). These corrections are what make the system learn. Over time, the tacit knowledge that experienced sovereign debt lawyers carry — knowing at a glance that a passage is boilerplate versus a meaningful clause — gets embedded in the evaluation data.

- **When reviewers disagree, that's a finding** — if two lawyers look at the same passage and disagree, that's research signal. It likely means the clause uses novel language — exactly the kind of variation that matters for understanding how contract terms evolve across markets (cf. Gelpern 2019, "If Boilerplate Could Talk").

- **The flywheel compounds** — with traditional annotation, reviewing 100 documents gives you 100 annotated documents. With this approach, reviewing 100 documents trains a system that can surface high-quality candidates across thousands. The expert's time compounds rather than being spent once and forgotten.

**The long-term vision:**

In the early stages, legal experts review many candidates — building the system's understanding of what counts as a real collective action clause versus a passing mention. But as edge cases get worked through and patterns accumulate, standard cases resolve automatically. A contract with a textbook ICMA model CAC doesn't need human review — the system recognizes it with high confidence. Expert attention focuses only on the genuinely ambiguous cases, which is where it's most valuable anyway.

The end state is a system that ingests new prospectuses as they're filed with the SEC and FCA, automatically identifies and tags key clauses with high confidence, and flags the ones that are unusual or novel for expert review. That's when things get really interesting. Building on Anna Gelpern's work on how sovereign debt boilerplate evolves (Gelpern 2019), we'd be able to see — in near-real-time — when clause language changes in ways that should raise eyebrows. A new CAC formulation from a frequent issuer. A pari passu clause that departs from market standard. An unusual governing law choice. These are the signals that matter for oversight, for research, and for the markets.

And at scale, we'd be able to see aggregated trends across time, geography, and issuer type — how contract terms are actually evolving across the sovereign debt landscape, not based on a sample of hand-reviewed documents, but across the full universe of publicly filed prospectuses.

**What we're proposing:**

*What would help:*

- A shared methodology for what "trustworthy" means — the sovereign debt legal, academic, and policy communities all need to be able to rely on automated clause identification. If it's not seen as credible, no one will use it. If it is, it becomes an extraordinary shared resource. So the first step is investing in rigorous evaluation standards together — what does it mean for an automated identification to be good enough to trust?
- A small group to run the first structured evaluation round — #PublicDebtIsPublic as the organizing secretariat, drawing reviewers from the broader sovereign debt community: law students, sovereign debt lawyers interested in pro bono contributions, legal scholars
- Guidance on which clause families matter most for accountability and oversight

*What we don't need:*

- Money — this work is grant-funded and open source (MIT licensed, meaning anyone can use it for free — it's a public resource)
- Official endorsement — we understand institutional constraints
- Access to confidential materials — we work exclusively with publicly filed documents

*A note on the author:* I spent seven years as a sovereign debt analyst at Morgan Stanley Investment Management before pivoting to building open-source tools for sovereign debt analysis — which is a polite way of saying I'm a sovereign debt nerd who now spends most of his time writing code and wrangling data. I'd be glad to help with the technical side of this as a collaborating partner.

**Closing:**

#PublicDebtIsPublic has identified that transparency requires infrastructure — information, technology, and legal frameworks working together. This proof of concept is a small contribution to the technology pillar: demonstrating how expert legal knowledge can be made catalytic, so that every annotation reaches further across the growing universe of publicly filed sovereign debt documents.

---

## Technical Implementation

### Quarto Book

- **Framework:** Quarto book project, rendered to HTML, deployed to GitHub Pages
- **Repo:** New repo (e.g., `Teal-Insights/sovereign-clause-corpus-demo`) or subdirectory of current repo
- **Chapters:** 3 `.qmd` files + `index.qmd` (preface/landing)
- **Static visualizations:** Generated from DuckDB queries, rendered as Observable JS or Python (matplotlib/plotly) in Quarto
- **References:** Gelpern 2019, Rivetti & Mihalyi 2025 (World Bank Radical Debt Transparency)

### Shiny Eval Explorer App

- **Framework:** Shiny for Python (or R) — whichever is faster to build
- **Deployment:** shinylive embedded in Quarto, OR separate shinyapps.io deployment iframe'd into the book
- **Data source:** Pre-exported JSONL/CSV from DuckDB (grep_matches + pdip_clauses + parsed text)
  - App should NOT require DuckDB at runtime — ship with flat files
- **Components:**
  1. Dropdown: clause family selector (collective_action, pari_passu, governing_law)
  2. Data table: filtered matches (country, document title, page, excerpt)
  3. Detail panel: full context (context_before + highlighted match + context_after)
  4. Two buttons: thumbs up / thumbs down
  5. Optional text input: "why not?" (appears on thumbs down)
  6. Feedback logger: appends to CSV/JSONL
- **Scope:** Minimal. One dropdown, one table, one detail view, two buttons. No auth, no database, no deployment complexity.

### Static Visualizations

**Map (Chapter 2, Element 1):**
- World choropleth, countries shaded by document count
- Data: aggregate from DuckDB `documents` table by country (need country mapping — PDIP has it in `pdip_clauses.country`, NSM/EDGAR will need mapping)
- Fallback if country mapping is incomplete for NSM/EDGAR: show PDIP-only map with a note that the full corpus spans 3 sources
- Library: Observable JS `Plot` in Quarto, or Python `plotly`

**Clause coverage chart (Chapter 2, Element 2):**
- Horizontal bar chart or summary table: clause families × document count from PDIP annotations
- Below: precision/recall table for 2-3 families
- Library: Observable JS or simple Quarto table with styling

### Data Preparation

Before building visualizations, export the needed data from DuckDB:

```sql
-- For the map: country document counts
SELECT country, COUNT(DISTINCT doc_id) as docs
FROM pdip_clauses
WHERE country IS NOT NULL
GROUP BY country ORDER BY docs DESC;

-- For the clause coverage chart
SELECT label_family, COUNT(*) as annotations, COUNT(DISTINCT doc_id) as docs
FROM pdip_clauses
WHERE label_family IS NOT NULL
GROUP BY label_family ORDER BY docs DESC;

-- For the Shiny app: export grep matches with context
SELECT gm.*, d.storage_key
FROM grep_matches gm
JOIN documents d ON gm.document_id = d.document_id
WHERE d.source = 'pdip';
```

---

## Weekend Schedule

### Saturday (primary work day)

1. **Morning:** Set up Quarto book project, write Chapter 1 narrative, create flywheel diagram
2. **Midday:** Generate static visualizations (map + clause coverage chart) from DuckDB data
3. **Afternoon:** Build the Shiny eval explorer app (MVP — dropdown + table + detail + buttons)
4. **Evening:** Write Chapter 3 narrative, integrate everything, deploy to GitHub Pages

### Sunday (polish + test)

1. Test the deployed book on mobile (roundtable participants will likely check on phones)
2. Polish visualizations and narrative
3. Run through the Shiny app with real data to make sure it tells a compelling story
4. Final review of tone — proud but humble, show don't tell

---

## Success Criteria

- [ ] Shareable GitHub Pages URL works on desktop and mobile
- [ ] Chapter 1 explains the approach in under 3 minutes of reading
- [ ] Map makes immediate visual impact — "4,800+ documents, dozens of countries"
- [ ] Shiny app lets someone click through 5 clause candidates in under 60 seconds
- [ ] Chapter 3 has a clear, specific ask that doesn't sound like a pitch
- [ ] A roundtable participant who is not technical can understand the entire book
- [ ] Tone is "I built this in a week, it's preliminary, but look what's possible"

---

## What This Is NOT

- Not a finished product or production system
- Not a pitch for money or a contract
- Not claiming automated clause extraction is solved
- Not presenting findings as definitive — everything is "preliminary, methodology under review"
- Not trying to replace or compete with #PublicDebtIsPublic — extending and amplifying it
