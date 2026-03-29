# Full Corpus Extraction — Design Spec (v2, post-review)

**Date:** 2026-03-29
**Goal:** Extract all PDIP clause families + document-level classification across
the full 4,685-document corpus, producing a comprehensive dataset for the
Georgetown Law roundtable (March 30) and ongoing research.

**Approach:** Claude Code as LLM extractor (see `docs/claude-code-as-extractor.md`),
executed in prioritized rounds with learning loops between each round.

**Revision notes:** Updated after 3-model review (Opus, Gemini, ChatGPT).
Addresses: session limits, crash recovery, Round 1 scoping, classification
taxonomy, trust framework, Dropbox isolation, and CLI extensibility.

---

## 1. Machine & Account Allocation

| Machine | Account | Mode | Workstream |
|---------|---------|------|------------|
| Mac Mini | Team Premium ($150/mo) | `--dangerously-skip-permissions` | Extraction rounds |
| MacBook Air | Personal Max 20x ($200/mo) | Interactive | Analysis, Quarto book, Shiny app |

**Monitoring:** iPhone remote control for Mac Mini session. Between-round reviews
done from phone.

**Git coordination:** Mac Mini works on `feature/full-extraction-round-N` branches.
MacBook Air works on `feature/roundtable-demo`. No branch collisions. Both push
to GitHub independently.

**Data isolation:** Only the Mac Mini writes to `data/extracted_v2/`. The MacBook
Air reads extraction results but NEVER writes to that directory. This prevents
Dropbox sync conflicts.

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

# 3. Symlink data (NOT the entire Dropbox folder — just data/)
ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data

# 4. Rebuild venv
uv sync

# 5. Verify
git status          # clean
ls data/parsed/     # files visible via symlink
uv run pytest -v    # tests pass

# 6. Mac Mini only: make data available offline
# Right-click ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/
# → "Make available offline" (prevents Smart Sync eviction)
```

### DuckDB safety

If `corpus.duckdb` exists in `data/db/`, do NOT symlink it through Dropbox.
DuckDB does not support concurrent access over synced drives. Keep it
machine-local or exclude `data/db/` from the symlink.

### Startup check

```python
data_path = Path("data")
if not data_path.is_symlink() or not data_path.resolve().exists():
    raise RuntimeError(
        "Missing or broken data symlink. Expected: data -> ~/Dropbox/.../data"
    )
# Verify actual files are accessible (catches Smart Sync eviction)
parsed_dir = data_path / "parsed_docling"
if parsed_dir.exists() and not any(parsed_dir.iterdir()):
    raise RuntimeError("data/parsed_docling/ exists but is empty — check Dropbox offline status")
```

### Completion protocol for extraction results

Each extraction run writes to an isolated directory:
```
data/extracted_v2/<run_id>/
├── <family>_candidates.jsonl
├── batch_results/
│   └── <family>_batch_NNNN.jsonl
├── <family>_extractions.jsonl
├── <family>_verified.jsonl
└── COMPLETE.json   <- written LAST, signals safe to read
```

The MacBook Air should only analyze directories containing `COMPLETE.json`.

---

## 3. Prerequisites Before Mac Mini Launch

These must exist before the overnight session starts:

1. **Cue families** for all Round 1 clause types in `cue_families.py`
2. **CLI extended** to accept all clause families (not just 2)
3. **Completeness checklist** patterns in `verify.py` for Round 1 families
4. **PDIP calibration/evaluation splits** per Round 1 family
5. **`scripts/round_report.py`** built and tested
6. **`docs/meta-learning-round-0.md`** written (lessons from PR #44)
7. **Migration complete** on both machines
8. **Multi-model review** of the implementation plan

---

## 4. Session Design: Respecting the 5-Hour Limit

Claude Code has a 5-hour session timeout. Round 1 with 4 families + classification
will likely exceed this. Design for it:

**Strategy: One family per session segment.**

```
Session 1: Document classification (fast — pure Python + subagents)
  → generates COMPLETE.json, prints phone-friendly status
  → auto-continues to governing_law if classification >90% high-confidence

Session 1 (continued): Governing law LOCATE→EXTRACT→VERIFY
  → generates round report for governing_law
  → if session time remaining > 2h, continues to sovereign_immunity
  → otherwise: prints status, commits, pushes, session ends

Session 2 (new session, reads previous results): sovereign_immunity + negative_pledge
  → reads COMPLETE.json files from Session 1
  → resumes from where Session 1 left off

Session 3: events_of_default (hardest, saved for last in Round 1)
  → section-level extraction only
```

**Crash recovery:** If a session dies mid-family:
1. Batch results are per-file in `batch_results/` (immutable, not appended)
2. New session reads existing batch files, counts processed candidate_ids
3. Resumes from first unprocessed batch
4. The session prompt includes a "recovery mode" section:

```
If resuming after a crash:
1. Check data/extracted_v2/ for existing batch_results per family
2. Count processed candidates vs total from LOCATE
3. Resume the unfinished family from the next unprocessed batch
4. Do NOT re-run LOCATE — use existing candidates.jsonl
```

---

## 5. Round Structure

### Round 1 — "Foundation" (easiest families first, EoD last)

**Run LOCATE for ALL Round 1 families first.** Check candidate counts and estimate
total EXTRACT time before proceeding. If total exceeds budget, defer EoD to Round 2.

| Priority | Family | PDIP Docs | Difficulty | Notes |
|----------|--------|-----------|------------|-------|
| 1a | Document classification | 0 (new) | Easy | First 10K chars, not page-based |
| 1b | `governing_law` | 71 | Easy | Short clause, ~51 words |
| 1c | `sovereign_immunity` | 41 | Moderate | Waiver language |
| 1d | `negative_pledge` | 51 | Moderate | Pledge + definitions |
| 1e | `events_of_default` | 74 | Hard (simplified) | Full-section only, last in round |

**Budget checkpoint after LOCATE:** If total candidates > 15K, move EoD to Round 2.

### Round 2 — "Expand"

| Family | PDIP Docs | Difficulty |
|--------|-----------|------------|
| `acceleration` | 68 | Moderate |
| `dispute_resolution` | 55 | Moderate |
| `additional_amounts` | 35 | Moderate |
| `redemption` | 38 | Moderate |
| `indebtedness_definition` | 37 | Easy-Moderate |
| (EoD if deferred from Round 1) | 74 | Hard |

### Round 3 — "Breadth"

Remaining 13 families. Some need different extraction modes (see Section 8).

### Between-round transition

**No auto-transition.** Each round ends with a status summary and waits for
phone review. The auto-transition rule from v1 of this spec was removed because:
- Verbatim pass rate alone doesn't measure recall
- Per-family thresholds are needed, not aggregate
- EoD would block the entire round
- The reviewer should see results before committing to the next round

---

## 6. Document Classification Workstream

Separate from clause extraction. Different pipeline, different output format.
Runs first in Round 1 (classification results inform later extraction).

### Multi-axis taxonomy

Reviewers correctly flagged that a single "document_type" field mixes dimensions.
Use three separate fields:

| Field | Values | Notes |
|-------|--------|-------|
| `instrument_family` | Bond, Loan, Other | Coarse instrument type |
| `document_role` | Base document, Supplement, Amendment, Standalone | What role this doc plays |
| `document_form` | Prospectus, Offering Circular, Indenture, Trust Deed, Fiscal Agency Agreement, Loan Agreement, Pricing Supplement, Final Terms, Regulatory Filing, Other | Specific form |

**IMPORTANT CAVEAT:** This taxonomy is a best-effort starting point. Domain
expert review is needed. File a GitHub issue to track this.

### Input strategy (no page numbers for Docling)

Docling markdown has no reliable page mapping. Do NOT use "pages 0-2."

- **Docling markdown:** Read first 10,000 characters of the `.md` file
- **EDGAR flat JSONL:** Read pages 0-2 (real pages exist)
- **EDGAR bonus:** Parse SEC form code from file header (`424B5`, `FWP`, etc.)
- **Edge case:** If first 500 chars start with "IMPORTANT NOTICE" or disclaimer
  boilerplate, extend to first 15,000 chars

### Output format

```json
{
  "storage_key": "nsm__228117819_...",
  "instrument_family": "Bond",
  "document_role": "Base document",
  "document_form": "Base Prospectus",
  "confidence": "high",
  "reasoning": "'Base Prospectus' appears as heading in first paragraph",
  "evidence_text": "BASE PROSPECTUS dated 15 March 2024",
  "evidence_page": null,
  "schema_version": "1.0"
}
```

Written to: `data/extracted_v2/<run_id>/document_classification.jsonl`

### Validation (no ground truth, but sanity checks)

1. **EDGAR cross-check:** SEC form code should agree with text classification.
   Disagreements are flags for review.
2. **Distribution check:** If >30% of documents are "Other", something is wrong.
3. **PDIP metadata cross-check:** PDIP annotations include `instrument_type`
   (Bond/Loan). Our `instrument_family` should agree.

---

## 7. Events of Default: Section Capture Pilot

EoD is treated as a separate "section capture pilot," not standard clause extraction.

### Why different

- PDIP has 334 trigger-level annotations, not section-level gold
- EoD sections are 3-8 pages of dense legal text
- EDGAR page-level parsing will miss middle pages
- Full-section extraction is honest but produces walls of text

### Approach

- **NSM/PDIP (Docling):** LOCATE finds the EoD section heading, extracts full
  section including subsections (E2 boundary rule handles this naturally)
- **EDGAR:** LOCATE finds pages with EoD keywords, but the section may span
  pages that don't independently match cues. **Accept lower recall on EDGAR EoD.**
  Flag EDGAR EoD results with `"source_caveat": "page-level parsing may miss
  middle pages of long EoD sections"`

### Trust badge

EoD gets a distinct badge: **"SECTION LOCATED"** (not "HIGH TRUST"). The Shiny
explorer shows EoD as a collapsed/expandable section, not inline clause text.

Roundtable narrative: "We located the Events of Default sections. Trigger-level
parsing requires annotation investment — here's exactly how much."

### Metadata enrichment (lightweight)

Even without trigger parsing, count numbered sub-paragraphs as a heuristic:
```python
trigger_count_estimate = len(re.findall(r"\(\w\)|\b\d+\.\d+\b", eod_text))
```
This gives "approximately N default triggers" which is useful for comparison.

---

## 8. Extraction Modes (Not All Families Are the Same)

Reviewers correctly noted that 22 families include different task types.

### Mode 1: Clause boundary extraction (existing v2 pipeline)
Standard LOCATE→EXTRACT→VERIFY. The clause has clear boundaries.

Families: `sovereign_immunity`, `negative_pledge`, `additional_amounts`,
`redemption`, `acceleration`, `dispute_resolution`, `amendment_waiver`

### Mode 2: Short field extraction
The "clause" is 1-3 sentences. Extraction is near-trivial.

Families: `governing_law`, `pari_passu`, `commitment`

### Mode 3: Full-section capture
Long structured sections. Extract the whole section verbatim.

Families: `events_of_default`, `conditions_precedent`, `payment_mechanics`,
`trustee_duties`, `disbursement`

### Mode 4: Structured field extraction
Multiple related data points from one section (e.g., interest rate type,
rate value, day count convention).

Families: `interest`, `currency`, `fees`, `purpose`, `use_of_proceeds`,
`information_covenants`, `books_records`, `indebtedness_definition`

**Implementation note:** Modes 1 and 2 use the existing pipeline. Mode 3 needs
a relaxed verbatim threshold (long sections will have minor variations).
Mode 4 may need a different output schema (key-value pairs, not just clause_text).
Round 3 families should be evaluated for which mode they need before extraction.

---

## 9. Trust Framework (Revised)

The original "HIGH/MEDIUM/LOW based on PDIP count" was too coarse. Revised:

### Per-family trust card

```json
{
  "family": "governing_law",
  "trust_level": "HIGH",
  "evidence": {
    "pdip_docs": 71,
    "holdout_recall": 0.94,
    "holdout_precision": 0.98,
    "verbatim_pass_rate": 0.97,
    "source_diversity": {"nsm": 420, "edgar": 312, "pdip": 71},
    "instrument_diversity": {"bond": 650, "loan": 153}
  },
  "evaluation_type": "held-out PDIP evaluation set",
  "caveats": []
}
```

### Trust level criteria

| Level | Criteria |
|-------|----------|
| HIGH | >30 PDIP holdout docs, recall >90%, precision >90%, 2+ sources |
| MEDIUM | 10-30 PDIP holdout docs, recall >80%, or single-source |
| LOW | <10 PDIP holdout docs, or recall <80%, or precision <85% |
| SECTION LOCATED | Full-section capture only (EoD, conditions_precedent) |
| UNVALIDATED | No PDIP ground truth (document classification) |

Display trust cards prominently in Shiny explorer and Quarto book.

### Calibration/evaluation integrity

- Calibration docs: used for prompt development and cue tuning
- Evaluation docs: NEVER seen during development, used only for metrics
- Between-round cue tuning uses ONLY calibration set
- If cues are tuned after seeing evaluation results, re-split and re-label
  the trust level as "exploratory, not validated"

---

## 10. Round Reports & Learning Loop

### Round report script (`scripts/round_report.py`)

Must be built as a prerequisite. Consumes:
- `data/extracted_v2/<run_id>/<family>_candidates.jsonl`
- `data/extracted_v2/<run_id>/<family>_verified.jsonl`
- `data/pdip/clause_annotations.jsonl` (for recall calculation)

Produces:

```markdown
## Round N Report — {timestamp}

### Per-Family Results
| Family | Candidates | Found | Verbatim Pass | PDIP Recall | PDIP Precision | Trust |

### Diagnostics (per family)
- Source mix (NSM/EDGAR/PDIP)
- Heading-match vs body-only ratio
- Confidence distribution
- Section length distribution
- OCR/truncation flag rates
- Sample of 5 disagreements (system found, PDIP didn't / PDIP found, system didn't)

### Throughput
- Wall time, candidates/minute, session usage %

### Pattern Learnings
- Cue patterns that worked / missed (from calibration set only)
- Common NOT_FOUND reasons

### Recommended Adjustments
- [auto-generated, applied to calibration set only]

### Quick Status (phone-friendly)
[concise summary for iPhone review]
```

### Meta-learning report (one-time)

`docs/meta-learning-round-0.md` captures lessons from PR #44:
- Bug patterns from code review (E20, clustering gap, logger args)
- What worked (batching, Sonnet subagents, priority ordering)
- Throughput actuals vs estimates
- Reviewer pushback patterns (API SDK insistence)

---

## 11. Mac Mini Session Prompt Template

```
Read the implementation plan at docs/superpowers/plans/2026-03-29-full-extraction.md.
Read docs/meta-learning-round-0.md for lessons from the previous extraction.

Execute Round 1 family by family in priority order:
1. Document classification
2. governing_law
3. sovereign_immunity
4. negative_pledge
5. events_of_default (if budget allows after LOCATE count check)

BEFORE any EXTRACT work: run LOCATE for ALL Round 1 families and report
candidate counts. If total candidates > 15K, defer events_of_default.

After EACH family completes:
- Run: uv run python3 scripts/round_report.py --family <family> --run-id <run_id>
- Print the Quick Status summary
- Continue to next family

After ALL Round 1 families complete:
- Run the full round report
- Commit reports to git and push
- STOP and wait for my review before Round 2

Use subagent-driven development for EXTRACT stage.
Use caffeinate -d -i to prevent sleep.

If session is approaching the 5-hour limit:
- Finish the current family (do not abandon mid-extraction)
- Generate partial round report for completed families
- Commit, push, print status
- The next session will resume from the unfinished family

CRASH RECOVERY: If resuming after a crash:
1. Check data/extracted_v2/<run_id>/ for existing batch_results
2. Count processed candidates vs total from LOCATE
3. Resume the unfinished family from next unprocessed batch
4. Do NOT re-run LOCATE — use existing candidates.jsonl
```

---

## 12. MacBook Air Workstream (Parallel)

While the Mac Mini extracts:

1. **Quarto book** — roundtable narrative with trust cards per family
2. **Shiny app** — extend with new families as results arrive (only from
   directories with COMPLETE.json)
3. **Analysis** — patterns in existing CAC + pari passu data
4. **Round report review** — when Mini finishes, review on Air

**Write isolation:** The Air NEVER writes to `data/extracted_v2/`. It reads only.

---

## 13. Open Questions for Domain Experts

File as GitHub issues after implementation:

1. **Document classification taxonomy** — Are instrument_family / document_role /
   document_form the right axes? Domain expert input needed.
2. **Events of default granularity** — Trigger-level parsing requires annotation.
   How much effort? Which triggers matter most?
3. **Trust level thresholds** — Are the criteria credible to legal scholars?
4. **Cross-instrument comparability** — Bond CACs vs loan amendment provisions.
5. **Mode 4 families** — Interest, fees, currency need structured extraction.
   What fields matter for comparative analysis?
