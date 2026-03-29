# Roundtable Book and Shiny App Refresh — Design Spec

## Goal

Rewrite the Quarto book and update the Shiny app for the Georgetown Law
#PublicDebtIsPublic roundtable on March 30, 2026. The book is the primary
deliverable. The Shiny app is a "try it yourself" supplement.

## Tone

Proud but humble. Specific about accomplishments. Equally specific about
limitations. No overclaiming. Let the data and the charts carry the story.
Credit PDIP as the enabler throughout. Frame the work as a proof of concept
built in one week by one person on PDIP's foundation. The call to action
is a genuine invitation to collaborate, not a pitch or a challenge.

Detailed positioning notes are in `docs/private/` (gitignored).

## Writing Rules

- No em dashes. Use commas, periods, or restructure.
- No AI-isms: "delve", "leverage", "utilize", "it's important to note",
  "in terms of", "aims to", "facilitates".
- No fluff or filler sentences.
- Short, direct sentences. Active voice.
- Specific limitations, not vague hedging. "We did not validate against
  documents outside the PDIP corpus" is strong. "More work is needed" is
  weak.
- Follow `docs/lawyer-centered-design.md` principles throughout.

---

## Book Structure

### File Layout

```
demo/
├── _quarto.yml              (updated: new chapters + appendices)
├── index.qmd                (Preface — rewritten)
├── findings.qmd             (Chapter 1: What the Data Shows)
├── eval-workflow.qmd         (Chapter 2: The Eval Workflow)
├── call-to-action.qmd       (Chapter 3: Call to Action)
├── appendix-technical.qmd   (Appendix A: Technical Architecture)
├── appendix-validation.qmd  (Appendix B: Validation Approach)
├── appendix-coverage.qmd    (Appendix C: Corpus Coverage)
├── appendix-sovtech.qmd     (Appendix D: SovTech and the Bigger Picture)
├── references.bib
├── images/
│   ├── teal-insights-logo.png
│   └── naturefinance-logo.png
└── data/
    └── export_v2.py         (updated: unified export for all families)
```

Old files (`chapter1.qmd`, `chapter2.qmd`, `chapter3.qmd`) are replaced
with descriptively named files.

### Preface (`index.qmd`) — ~300 words

What this is, who made it, what it is not. Sets the tone for everything.

Content:
- One person, one week, ~$100 of compute. Built on PDIP expert annotations.
- Open source, MIT licensed. Part of Teal Insights' SovTech initiative,
  supported by NatureFinance.
- This is a proof of concept. It shows the approach works. It is not
  finished research.
- Specific limitations listed upfront (not buried).

Logos: Teal Insights and NatureFinance logos in the Preface or footer.
Present but not dominant.

### Chapter 1: What the Data Shows (`findings.qmd`) — ~800 words + charts

Data-driven findings. Charts carry the story, prose connects them.

Planned visualizations:
- Choropleth map: corpus coverage by country (updated with enriched country
  data across all sources)
- Governing law jurisdiction breakdown (New York vs English vs other)
- CAC prevalence by country/region
- Document type distribution (instrument family, document role, document form)
- Sovereign immunity waiver patterns by country
- Clause family coverage chart (updated with all extracted families)

All numbers computed from data, not hardcoded. When the Mac Mini finishes
more extractions, re-running the export script and re-rendering updates
everything automatically.

### Chapter 2: The Eval Workflow (`eval-workflow.qmd`) — ~500 words

What it looks like to review a clause. How 15 minutes of lawyer time
compounds across thousands of documents. The flywheel in concrete terms.

Content:
- Show what a reviewer sees (screenshot or embedded mockup of the Shiny app)
- Explain the three-step cycle: system surfaces candidate, expert validates,
  system learns
- Time-to-decision framing from lawyer-centered-design.md
- Link to live Shiny app

### Chapter 3: Call to Action (`call-to-action.qmd`) — ~600 words

Three specific asks, framed as invitations:

1. **Lawyers at the roundtable**: Review 20-30 clauses. The tool is
   designed to respect your time. Your expert judgment is the most
   valuable input we can get.

2. **MDI and #PublicDebtIsPublic**: Help build the durable version. This
   prototype demonstrates the concept. A production system needs
   institutional architecture, hosting, and sustained maintenance.

3. **The community**: Help define what "trustworthy" automated clause
   identification means. That question belongs to the sovereign debt
   legal community, not to one technologist.

Tone: Independent but collaborative. An invitation, not a dependency.

### Appendix A: Technical Architecture (`appendix-technical.qmd`) — ~400 words

Pipeline overview: download, parse, locate, extract, verify. Three sources
(SEC EDGAR, FCA NSM, PDIP). Section-aware extraction. Verbatim
verification.

### Appendix B: Validation Approach (`appendix-validation.qmd`) — ~400 words

PDIP holdout recall methodology. Calibration/evaluation split. Verbatim
similarity scoring. Per-family trust metrics. Honest about what this does
and does not prove.

### Appendix C: Corpus Coverage (`appendix-coverage.qmd`) — ~400 words

Full table: documents by source, country, and clause family. Classification
distribution. What we have and where the gaps are.

### Appendix D: SovTech and the Bigger Picture (`appendix-sovtech.qmd`) — ~400 words

What SovTech means. How NatureFinance's support enables this work. How the
sovereign clause corpus connects to the broader vision of open-source
infrastructure for sovereign debt transparency and climate finance.

### Total

Main body: ~2,200 words (skimmable in 10 minutes).
Appendices: ~1,600 words (for the curious).

---

## Data Pipeline

### Export Script Updates

`demo/data/export_v2.py` updated to read:
- v1 files: `data/extracted_v2/cac_verified.jsonl`, `pp_verified.jsonl`
- Round 1 family directories: `data/extracted_v2/2026-03-29_round1/*/verified.jsonl`
  (only families with `COMPLETE.json`)
- Document classification: `data/extracted_v2/2026-03-29_round1/document_classification/classification.jsonl`

Outputs unified CSVs consumed by both the Quarto book and the Shiny app.

### Slot-in Architecture

All chapter visualizations use computed variables (`n_docs`, `n_countries`,
etc.), not hardcoded numbers. When new extraction data arrives from the
Mac Mini via Dropbox:

1. Re-run export script: `uv run python3 demo/data/export_v2.py`
2. Re-render Quarto: `quarto render demo/`
3. Numbers, charts, and tables update automatically

---

## Shiny App Updates

### Scope (for March 30)

- Add new clause families to dropdown: governing_law, sovereign_immunity,
  negative_pledge, events_of_default (when complete)
- Add country filter
- Update copy and decision labels per `docs/lawyer-centered-design.md`
- Add three flywheel callout banners (see below)

### Flywheel Callouts

Three callouts placed where they are relevant:

1. **Top of app** (always visible): Brief framing. Proof of concept. Your
   expert judgment builds something bigger.

2. **Detail panel** (when viewing a candidate): "This clause was surfaced
   by [heading match / body cue patterns]. Your assessment teaches the
   system which patterns work and which don't."

3. **After decision submission**: "Your review just improved future
   extractions. The system learns from the boundary between 'correct
   clause' and 'not a clause.'"

### Lawyer-Centered Design Compliance

Per `docs/lawyer-centered-design.md`:
- Extracted clause is the primary visual element
- Document structure preserved (headings, numbered lists, indentation)
- Serif font, readable size, room to breathe
- Triage-friendly table columns (country, section, page, surfaced by,
  confidence)
- Decision options framed as expert judgment, not rating
- Signals shown as components, not a single score
- Trust signals present (provenance, quality warnings, verification status)
- Copy is confident but honest

### Not in Scope

- Split-pane layout redesign (issue #41)
- Keyboard shortcuts and auto-advance (issue #41)
- Boundary editing (issue #36)
- Session resume

---

## Review Pipeline

The same review pipeline applies to both the Quarto book and the Shiny app.

### Per-Chapter / Per-Component Workflow

1. **Write or update** content
2. **Render**: `quarto render demo/` or run Shiny app locally
3. **Playwright visual inspection**: Screenshot rendered pages/app screens.
   Check layout, alignment, chart rendering, font, spacing. Flag visual
   issues before content review.
4. **Style reviewer agent**: Check all writing rules (no em dashes, no
   AI-isms, no fluff, narrative arc, specific limitations).
5. **Stakeholder persona review agents** (all output to `docs/private/`,
   gitignored): Multiple persona agents review from different stakeholder
   perspectives — checking legal accuracy, collaboration tone, and
   positioning. Persona definitions and review criteria are in
   `docs/private/roundtable-framing.md` (not tracked in git).
6. **Fix** all flagged issues
7. **Review markdown**: Create `docs/private/review-round-N.md` with
   summary of changes, flagged issues, and specific questions with blank
   "Your response:" sections for SuperWhisper dictation.
8. **Iterate** until approved, then move to next chapter/component.

### Execution Order

1. Preface (sets tone, most sensitive)
2. Chapter 3: Call to Action (nail the ask)
3. Chapter 1: Findings (data-driven, fill in as data arrives)
4. Chapter 2: Eval Workflow (connects book to app)
5. Shiny app updates (same review pipeline)
6. Appendices A-D (faster iterations, less tone sensitivity)

---

## Private Content Safety Rails

Three layers prevent private framing/positioning content from appearing
in git history or pull requests.

### Layer 1: Gitignore

Already configured in `.gitignore`:
- `docs/private/` — framing docs, persona reviews, review round markdowns
- `demo/reviews/` — Playwright screenshots, visual inspection artifacts

### Layer 2: Pre-commit Hook

A git hook that scans staged files and commit messages for private content
patterns. Blocks commits that contain:
- Content from persona review artifacts accidentally pasted into tracked
  files
- Framing language that belongs in `docs/private/`, not public content
- References to the private review process itself

### Layer 3: PR Verification

Before creating any PR:
- Scan `git diff main...HEAD` for private content patterns
- Confirm no `docs/private/` files are staged
- Confirm commit messages contain no framing language

---

## Completion Criteria

- [ ] All old chapter files replaced with new descriptively-named files
- [ ] Preface sets "proud but humble" tone, reviewed by all stakeholder personas
- [ ] Call to action has three clear asks, approved by all stakeholder personas
- [ ] Findings chapter uses computed variables, charts render correctly
- [ ] Eval workflow chapter links to working Shiny app
- [ ] Shiny app has new clause families, country filter, flywheel callouts
- [ ] Shiny app passes lawyer-centered-design.md compliance check
- [ ] All appendices written
- [ ] Logos present but not dominant
- [ ] Pre-commit hook blocks private content
- [ ] Playwright visual inspection passes for all rendered pages
- [ ] Style review passes (no em dashes, no AI-isms, no fluff)
- [ ] All stakeholder persona reviews pass
- [ ] Export script handles all data sources, re-run produces correct output
- [ ] No private content in any git commit or PR
