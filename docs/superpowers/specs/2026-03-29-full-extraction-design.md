# Full Corpus Extraction — Design Spec

**Date:** 2026-03-29
**Goal:** Extract all PDIP clause families + document-level classification across
the full 4,685-document corpus, producing a comprehensive dataset for the
Georgetown Law roundtable (March 30) and ongoing research.

**Approach:** Claude Code as LLM extractor (see `docs/claude-code-as-extractor.md`),
executed in prioritized rounds with learning loops between each round.

---

## 1. Machine & Account Allocation

| Machine | Account | Mode | Workstream |
|---------|---------|------|------------|
| Mac Mini | Team Premium ($150/mo) | `--dangerously-skip-permissions` | Extraction Rounds 1-3 |
| MacBook Air | Personal Max 20x ($200/mo) | Interactive | Analysis, Quarto book, Shiny app |

**Monitoring:** iPhone remote control for Mac Mini session. Between-round reviews
done from phone.

**Git coordination:** Mac Mini works on `feature/full-extraction-round-N` branches.
MacBook Air works on `feature/roundtable-demo`. No branch collisions. Both push
to GitHub independently. Data flows through Dropbox automatically.

---

## 2. Migration: Repo Out of Dropbox

**Current state:** Repo at `/Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus/`
(code and data mixed in Dropbox — causes havoc with two machines).

**Target state:** GitHub moves code, Dropbox moves data. They never cross.

### Target directory layout (each machine)

```
~/Projects/sovereign-prospectus-corpus/    <- git clone, NOT in Dropbox
├── src/
├── tests/
├── pyproject.toml
├── .venv/                                 <- machine-local, gitignored
└── data -> ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/  <- symlink

~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/  <- Dropbox-synced
├── raw/
├── parsed/
├── parsed_docling/
├── extracted_v2/
└── pdip/
```

### Migration script (run on each machine)

```bash
# 1. Ensure everything is pushed
cd ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus
git status  # must be clean
git push

# 2. Clone fresh
mkdir -p ~/Projects
cd ~/Projects
git clone git@github.com:Teal-Insights/sovereign-prospectus-corpus.git
cd sovereign-prospectus-corpus

# 3. Symlink data
ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data

# 4. Rebuild venv
uv sync

# 5. Verify
git status          # clean
ls data/parsed/     # files visible via symlink
uv run pytest -v    # tests pass
uv run corpus extract-v2 locate --help  # CLI works

# 6. Mac Mini only: make data available offline
# Right-click ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/
# → "Make available offline" (prevents Smart Sync eviction)
```

### Startup check (add to codebase)

```python
# In src/corpus/__init__.py or similar
if not Path("data").exists() and not Path("data").is_symlink():
    raise RuntimeError(
        "Missing data directory. See docs/superpowers/specs/"
        "2026-03-29-full-extraction-design.md for setup."
    )
```

---

## 3. Round Structure

### Round 1 — "Foundation"

**Clause families:**

| Family | PDIP Ground Truth | Difficulty | Approach |
|--------|-------------------|------------|----------|
| `governing_law` | 71 docs | Easy | Short clause, heading + body cues |
| `sovereign_immunity` | 41 docs | Moderate | Waiver language with carve-outs |
| `negative_pledge` | 51 docs | Moderate | Pledge text + definitions |
| `events_of_default` | 74 docs | Hard (simplified) | Full-section extraction only |

**Document classification** (separate workstream, same round):

| Task | Ground Truth | Difficulty | Approach |
|------|-------------|------------|----------|
| Document type | 0 (new task) | Easy | Pages 0-2 scan, keyword + SEC form codes |

Round 1 produces: empirical throughput numbers, verbatim pass rates, and the
first round report. These become the basis for estimating Rounds 2-3.

### Round 2 — "Expand"

| Family | PDIP Ground Truth | Difficulty |
|--------|-------------------|------------|
| `acceleration` | 68 docs | Moderate |
| `dispute_resolution` | 55 docs | Moderate |
| `additional_amounts` | 35 docs | Moderate |
| `redemption` | 38 docs | Moderate |
| `indebtedness_definition` | 37 docs | Easy-Moderate |

### Round 3 — "Breadth"

| Family | PDIP Ground Truth | Difficulty |
|--------|-------------------|------------|
| `interest` | 114 docs | Moderate |
| `currency` | 90 docs | Moderate |
| `commitment` | 66 docs | Easy |
| `fees` | 69 docs | Easy |
| `amendment_waiver` | 54 docs | Hard |
| `use_of_proceeds` | 57 docs | Moderate |
| `purpose` | 56 docs | Moderate |
| `information_covenants` | 62 docs | Moderate |
| `books_records` | 42 docs | Moderate |
| `conditions_precedent` | 66 docs | Hard |
| `disbursement` | 69 docs | Hard |
| `payment_mechanics` | 116 docs | Hard |
| `trustee_duties` | 20 docs | Hard |

### Auto-transition rule

If Round N verbatim pass rate is >85% across all families and zero errors,
proceed to Round N+1 automatically. Otherwise stop and wait for phone review.

---

## 4. Document Classification Workstream

**Separate from clause extraction.** Different pipeline, different output format.
Runs as part of Round 1 but is its own process.

### Classification schema

| Category | Keywords / Signals |
|----------|-------------------|
| Base Prospectus | "Base Prospectus", "Offering Circular", "Base Offering Circular" |
| Prospectus Supplement | "Prospectus Supplement", "Pricing Supplement", "Final Terms" |
| Preliminary Prospectus | "Preliminary Prospectus" |
| Indenture / Trust Deed | "Indenture", "Trust Deed", "Fiscal Agency Agreement" |
| Loan Agreement | "Loan Agreement", "Financing Agreement", "Loan Contract" |
| Amendment | "Amendment Agreement", "Supplement Number N to..." |
| Regulatory Filing | "Tender Offer", press releases, regulatory announcements |
| Other | Anything that doesn't fit cleanly |

**IMPORTANT CAVEAT:** This classification schema is a best-effort starting point.
Domain expert review (legal scholars, practitioners) is needed to validate whether
these categories are the right ones and whether the boundaries between them are
drawn correctly. File a GitHub issue to track this.

### EDGAR fast path

Parse SEC form code from file header before text analysis:
- `424B5` / `424B4` / `424B2` → Prospectus Supplement
- `424B1` / `424B3` → Prospectus
- `FWP` → Free Writing Prospectus
- `F-4` → Registration Statement

### Page scan strategy

- **Primary:** Pages 0-2 (concatenated text, first ~3 pages)
- **Fast path:** Page 0, first 500 chars (catches ~90%)
- **EDGAR bonus:** SEC form code in file header
- **Edge case:** If page 0 starts with "IMPORTANT NOTICE" or disclaimer,
  skip to page 2 for the actual cover

### Output format

```json
{
  "storage_key": "nsm__228117819_...",
  "document_type": "Base Prospectus",
  "document_subtype": "Global Medium Term Note Programme",
  "confidence": "high",
  "reasoning": "'Base Prospectus' appears as heading on page 1",
  "source_signal": "page_0_heading",
  "pages_examined": [0, 1, 2]
}
```

Written to: `data/extracted_v2/document_classification.jsonl`

---

## 5. Clause Extraction Pipeline

Reuses the v2 pipeline from PR #44 with extensions for new clause families.

### Per-family requirements

For each new clause family, define:

1. **Cue families** in `cue_families.py` — heading patterns + body cues
2. **PDIP calibration split** — freeze calibration/evaluation sets
3. **Extraction prompt guidance** — what constitutes this clause, what doesn't
4. **Completeness checklist** in `verify.py` — expected components

### Events of default: full-section approach

EoD is extracted as a complete section, not parsed into individual triggers.
The extraction prompt says: "Extract the full Events of Default section verbatim.
Do not attempt to parse individual triggers — just capture the complete section."

Confidence annotation: "Full-section extraction. Individual trigger parsing
requires additional annotation data — a small investment in EoD annotations
would significantly improve granularity."

### Confidence and trust levels

Every extraction carries a trust level based on PDIP ground truth depth:

| Trust Level | Criteria | Display |
|-------------|----------|---------|
| HIGH | >50 PDIP docs for this family, >90% verbatim pass | Green badge |
| MEDIUM | 20-50 PDIP docs, >85% verbatim pass | Yellow badge |
| LOW | <20 PDIP docs or <85% verbatim pass | Red badge + caveat |

The Shiny explorer and Quarto book display trust levels prominently.
The roundtable narrative: "Here's what we know well, here's where more
annotation would help, and here's exactly how much."

---

## 6. Round Reports & Learning Loop

### Round report script

`scripts/round_report.py` auto-generates after each round:

```markdown
## Round N Report — {timestamp}

### Coverage
- Documents scanned: X
- Candidates generated per family
- Clauses extracted per family
- Verbatim verified per family

### Quality by Family
| Family | Candidates | Found | Verbatim Pass | Confidence Dist | PDIP Docs | Trust |
|--------|-----------|-------|---------------|-----------------|-----------|-------|

### Throughput
- Wall time
- Candidates/minute
- Session usage (% of weekly limit)
- Estimated budget for Round N+1

### Pattern Learnings
- Cue patterns that worked / missed
- Common NOT_FOUND reasons
- Heading patterns to add for next round

### Recommended Adjustments
- [auto-generated based on metrics]

### Quick Status (phone-friendly)
Round N COMPLETE. [summary].
Ready to proceed? Reply "go" or give feedback.
```

### Meta-learning report (one-time, from PR #44 session)

Before Round 1, generate `docs/meta-learning-round-0.md` capturing:
- Code review bug patterns (E20, clustering gap, logger args)
- What reviewers got wrong (pushing for API SDK)
- What worked well (batching, Sonnet subagents, priority ordering)
- Throughput actuals vs estimates
- Cue pattern effectiveness for CAC and pari passu

This becomes the reference for all future extraction sessions.

### Learning between rounds

After each round report:
1. **Quality metrics** — tune prompts/cues if verbatim pass rate < 90%
2. **Cue refinement** — add heading patterns discovered during extraction
3. **Batch sizing** — adjust based on throughput data
4. **Throughput estimation** — update time/usage projections for next round

---

## 7. Mac Mini Session Structure

### Pre-launch (MacBook Air)

1. Multi-model review of the implementation plan (Opus + Gemini + ChatGPT)
2. Fix any issues identified
3. Push to GitHub
4. Verify Mac Mini can pull and run

### Session prompt

```
Read the implementation plan at docs/superpowers/plans/2026-03-29-full-extraction.md.
Read the meta-learning report at docs/meta-learning-round-0.md.

Execute Round 1:
- Document classification (separate workstream)
- Governing law, sovereign immunity, negative pledge, events of default

After Round 1 completes:
1. Run scripts/round_report.py to generate the round report
2. Commit the report to git and push
3. Print the Quick Status summary
4. STOP and wait for my review

Auto-transition rule: If Round 1 verbatim pass rate is >85% across all
families and zero errors, proceed to Round 2 automatically.

Use subagent-driven development. Use caffeinate -d -i to prevent sleep.
Process both clause families using the Claude Code as extractor approach.
```

### Between-round checkpoint (phone-friendly)

The session prints a concise summary and waits. You see it on iPhone remote
control and reply "go" or give feedback.

### Resilience

- All results written incrementally via safe_write to data/extracted_v2/
- Round reports committed to git
- If session dies: new session reads round report, checks existing batch
  results, resumes from where it left off

---

## 8. MacBook Air Workstream (Parallel)

While the Mac Mini extracts, the MacBook Air:

1. **Quarto book** — structure the roundtable narrative
   - Chapter per clause family showing extraction results
   - Confidence/trust level display
   - "Where more annotation would help" callouts
2. **Shiny app** — extend app_v2.py with new families as results arrive
3. **Analysis** — explore patterns in the data we already have
   - CAC variation across issuers and eras
   - Pari passu language evolution
   - Governing law distribution
4. **Round report review** — when Mini finishes a round, review on Air

Data arrives automatically via Dropbox. No git coordination needed for data.
Code changes on the Air go to a different branch.

---

## 9. Deliverables for Roundtable (March 30)

| Deliverable | Source |
|-------------|--------|
| Extraction coverage table (families x documents) | Round reports |
| Trust level matrix (which families have strong ground truth) | PDIP annotation counts |
| Shiny explorer with all extracted families | app_v2.py extended |
| Quarto book with narrative + findings | MacBook Air workstream |
| "Claude Code as extractor" methodology doc | Already written |
| Cost comparison (Max plan vs API) | Already written |
| "Where annotation would help" recommendations | Round reports + trust levels |
| Document classification results | Round 1 output |

---

## 10. Open Questions for Domain Experts

To be filed as GitHub issues after implementation:

1. **Document classification schema** — Are the categories (Base Prospectus,
   Supplement, Indenture, Loan Agreement, etc.) the right ones? Are the
   boundaries drawn correctly? Domain expert input needed.
2. **Events of default granularity** — Full-section extraction is the current
   approach. Would trigger-by-trigger parsing be more useful? How much
   annotation effort would that require?
3. **Trust level thresholds** — Is 50 PDIP docs the right cutoff for HIGH
   trust? Should some families have different thresholds based on their
   inherent variation?
4. **Cross-instrument comparability** — Bond CACs vs loan amendment provisions
   serve similar functions but look very different. Should they be compared
   or kept separate?
