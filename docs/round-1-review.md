# Round 1 Extraction Review

**Date:** 2026-03-29
**Families:** governing_law, sovereign_immunity, negative_pledge, events_of_default
**Corpus:** 4,685 documents (1,468 Docling + 3,217 EDGAR)
**Session:** Single session with one Sonnet usage limit interruption (reloaded)

---

## 1. Results Summary

| Family | Candidates | Found | Extraction Rate | Verification | Unique Docs |
|--------|-----------|-------|----------------|-------------|-------------|
| governing_law | 2,442 | 2,320 | 95% | 99.6% verbatim | 1,425 |
| sovereign_immunity | 979 | 872 | 89% | 97.7% verbatim | 601 |
| negative_pledge | 331 | 280 | 85% | 99.3% verbatim | 258 |
| events_of_default | 2,055 | 1,427 | 69% | 89.3% section_located | 983 |
| **Total** | **5,807** | **4,899** | **84%** | — | **~2,100** |

**Document classification:** 4,685 documents classified (3,984 Bond, 410 Loan, 291 Other).

**After deduplication (one best extraction per document):**

| Family | Primary Extractions | Duplicates Removed |
|--------|--------------------|--------------------|
| governing_law | 1,425 | 895 |
| sovereign_immunity | 601 | 271 |
| negative_pledge | 258 | 22 |
| events_of_default | 983 | 444 |

---

## 2. Issues Found & Fixes Applied

### 2.1 Round report bug (P0 — fixed)

**Problem:** `round_report.py` counted only `"verified"` status as passing.
Events of default uses section capture mode, which produces `"section_located"`
status. The report showed 0% verbatim for EoD.

**Fix:** Updated `round_report.py` to count both `"verified"` and
`"section_located"` as passing, and both `"failed"` and `"needs_review"` as
failing.

**Impact:** Display-only. The underlying data was correct.

### 2.2 LLM hallucination in verbatim extraction (P0 — fixed)

**Problem:** 30 of 32 verbatim failures across governing_law (10) and
sovereign_immunity (20) had similarity < 0.85. Inspection showed the LLM
extracted text from a *different section of the same document* — real clause
text, but not from the candidate's `section_text`. The extraction "looked
right" but failed verbatim because it wasn't a substring of the provided text.

**Root cause:** The extraction prompt said "extract exact text" but didn't
explicitly say "from the section_text provided." The LLM sometimes used its
understanding of the document (from seeing multiple candidates) to pull text
from memory rather than the current section.

**Fix:** Added rule #2 to `SYSTEM_PROMPT` in `llm_extractor.py`: "CRITICAL:
Your extracted clause_text MUST be a substring of the provided section_text.
Do not use text from memory or from other sections of the document."

**Impact:** Should reduce verbatim failures in Round 2. The 30 affected
extractions are flagged as `"failed"` in verified.jsonl — they contain real
clause text but from wrong sections.

### 2.3 Heading-only stubs wasting LLM budget (P1 — fixed)

**Problem:** Many LOCATE candidates were heading-only stubs — e.g., a ToC
entry like `"## Events of Default"` with no body text (< 100 characters).
These always produced NOT_FOUND, wasting ~50 subagent invocations.

**Analysis from Round 1:**
- EoD heading-matched candidates had only 52% extraction rate (many stubs)
- EoD body-only candidates had 74% extraction rate (paradoxically higher)

**Fix:** Added post-clustering filter in the CLI locate command that removes
candidates with `section_text < 100 characters`. Applied after clustering
so it doesn't affect the section_filter unit tests.

**Impact:** Fewer wasted LLM calls in Round 2. Estimated savings: ~100-200
candidates per family.

### 2.4 Duplicate extractions per document (P1 — fixed)

**Problem:** 578 governing_law documents had multiple found candidates (e.g.,
both a supplement summary and the base prospectus operative clause). While
not incorrect (both sections genuinely contain governing law text), the
roundtable demo needs one canonical extraction per document.

**Fix:** Created `scripts/dedup_extractions.py` that picks the best candidate
per document using: (1) highest confidence, (2) heading-matched preferred,
(3) longest clause text. Writes `deduplicated.jsonl` alongside `verified.jsonl`.

**Impact:** Cleaner data for the Shiny app and Quarto book. The raw
`verified.jsonl` preserves all extractions for research use.

---

## 3. Negative Pledge EDGAR Gap (P2 — investigated)

**Problem:** LOCATE found 331 negative_pledge candidates — all from Docling
(NSM/PDIP), zero from EDGAR (3,217 documents). This is a significant coverage
gap.

**Root cause (under investigation):** The negative pledge cue patterns require
2+ non-heading family hits for body-only candidates. On EDGAR page-level text,
the pledge language and exception language may appear on different pages, so
no single page hits both families. Additionally, EDGAR section_parser creates
one "section" per page — if "Negative Pledge" is a sub-heading within a
larger "Covenants" page, the heading pattern may not match the page-level
heading.

**Recommended fix for Round 2:**
- Add broader body cues that can match on a single page (e.g., standalone
  `"security interest"`, `"permitted lien"`)
- Consider reducing the non-heading family threshold from 2 to 1 for
  families where EDGAR recall is known to be zero
- Accept that some clause types inherently have lower EDGAR recall due to
  page-level parsing limitations

---

## 4. Document Classification "Other" Rate (P2 — investigated)

**Problem:** 1,889 documents (40%) were classified as `document_form = "Other"`.
Breakdown: 1,613 EDGAR, 151 PDIP, 125 NSM.

**Root cause (under investigation):** Most EDGAR "Other" documents have
`confidence: high` (1,592) — meaning an SEC form code was matched, but the
code mapped to "Other" in `_EDGAR_FORM_MAP`. The map only covers 424B1-5,
FWP, and F-4. Common unmapped form codes include 18-K (annual report for
foreign private issuers), S-3 (registration statement), and others.

**Recommended fix:**
- Expand `_EDGAR_FORM_MAP` with 18-K, S-3, and other common sovereign filing
  types
- Add text patterns for "annual report", "registration statement", etc.
- The 270 `confidence: low` documents (no pattern matched at all) need
  separate investigation — some may be non-English documents or unusual
  filing types

---

## 5. Zero-Extraction Documents (P3 — investigated)

**Problem:** 3,107 of 4,685 documents (66%) had zero extractions across all
4 Round 1 families.

**Expected composition:**
- Pricing supplements and final terms (540 + 338 = 878): These typically
  contain only brief term sheets, not full operative clauses. Zero
  extractions is correct.
- "Other" form documents (1,889): Many are regulatory filings, tender offers,
  or non-prospectus documents. Zero extractions expected.
- Some prospectuses and offering circulars may have been missed due to the
  negative pledge EDGAR gap or cue pattern limitations.

**Recommendation:** Spot-check a sample of zero-extraction documents
classified as "Prospectus" or "Indenture" to verify they genuinely lack
clause language vs. our LOCATE missed them.

---

## 6. Events of Default: Section Capture Observations

EoD is the hardest family — full section capture (Mode 3) rather than
clause extraction (Modes 1-2).

**Key metrics:**
- 1,274 section_located (89% of found)
- 153 needs_review (11% of found)
- Average similarity for needs_review: 0.593

**needs_review root causes:**
- Mid-section page splits (EDGAR): EoD section starts on one page, triggers
  continue on the next. The extracted text captures triggers (c)-(f) but
  misses (a)-(b). Similarity drops because the extraction doesn't start at
  the same point as the source section.
- OCR artifacts in PDIP documents (Docling): Minor character-level noise
  from PDF extraction reduces similarity below the 0.85 threshold.
- Legitimate partial captures: Some sections are genuinely very long (3-8
  pages) and the LLM correctly extracted the substantive portion.

**Recommendation:** For the roundtable, treat `needs_review` EoD extractions
as valid but flag them with `"source_caveat": "page-level parsing may miss
middle pages of long EoD sections"` per the design spec.

---

## 7. Throughput & Budget

| Phase | Duration | Items | Rate |
|-------|----------|-------|------|
| Prerequisites (Tasks 0-13) | ~45 min | 15 files | — |
| LOCATE (4 families) | ~8 min | 4,685 docs x 4 | ~39 docs/sec |
| Document classification | ~2 min | 4,685 docs | ~39 docs/sec |
| EXTRACT governing_law | ~90 min | 2,442 candidates | ~27/min |
| EXTRACT sovereign_immunity | ~60 min | 979 candidates | ~16/min |
| EXTRACT negative_pledge | ~20 min | 331 candidates | ~17/min |
| EXTRACT events_of_default | ~90 min | 2,055 candidates | ~23/min |
| VERIFY (all families) | ~1 min | 5,807 records | ~97/sec |
| **Total session** | **~5 hours** | **5,807 candidates** | — |

**Budget usage:**
- Hit Sonnet usage limit once at ~75% through governing_law (reloaded)
- No further limits hit after reload
- Mega-agent strategy (8 batches per agent) used for EoD to reduce
  dispatch overhead — processed 31 batches across 4 agents

---

## 8. Recommendations for Round 2

### Before starting extraction

1. **Fix negative pledge EDGAR cues** — add broader patterns or lower the
   family-hit threshold for known-zero-recall families
2. **Expand EDGAR form code map** — reduce "Other" classification rate
3. **Apply stub filter** (already done) — heading-only candidates < 100 chars
   are now filtered at LOCATE time

### During extraction

4. **Use reinforced extraction prompt** (already done) — substring constraint
   is now explicit in the system prompt
5. **Use mega-agent batching for large families** — dispatching 8 batches per
   agent reduces overhead significantly (EoD went from ~7 waves to 4 agents)
6. **Monitor medium-confidence extractions** — these are often page-boundary
   artifacts. Consider a post-extraction step that flags medium-confidence
   results from truncated pages.

### After extraction

7. **Run dedup immediately** — generate `deduplicated.jsonl` as part of the
   standard post-extraction pipeline
8. **Spot-check zero-extraction "Prospectus" documents** — verify LOCATE isn't
   missing genuine clause content

### Round 2 families

| Family | Expected Difficulty | Notes |
|--------|-------------------|-------|
| acceleration | Moderate | Overlaps with EoD triggers — may have high false positive rate |
| dispute_resolution | Moderate | Overlaps with governing_law — jurisdiction vs. dispute resolution |
| additional_amounts | Moderate | Tax gross-up clauses, well-bounded |
| redemption | Moderate | Multiple redemption types in one section |
| indebtedness_definition | Easy-Moderate | Short definition clause |

---

## 9. Data File Locations

All extraction data is in `data/extracted_v2/2026-03-29_round1/`:

```
2026-03-29_round1/
├── RUN_MANIFEST.json
├── round_report.json
├── document_classification/
│   ├── classification.jsonl    (4,685 records)
│   └── COMPLETE.json
├── governing_law/
│   ├── candidates.jsonl        (2,442 records)
│   ├── batches/                (61 batch files)
│   ├── batch_results/          (61 result files)
│   ├── extractions.jsonl       (2,442 merged)
│   ├── verified.jsonl          (2,442 verified)
│   ├── deduplicated.jsonl      (1,547 primary + not_found)
│   └── COMPLETE.json
├── sovereign_immunity/         (same structure, 23 batches)
├── negative_pledge/            (same structure, 7 batches)
└── events_of_default/          (same structure, 55 batches)
```

---

## 10. Code Changes in This Session

| File | Change |
|------|--------|
| `src/corpus/extraction/cue_families.py` | 9 new clause families (Round 1 + Round 2) |
| `src/corpus/extraction/verify.py` | Completeness patterns + section_capture_similarity |
| `src/corpus/extraction/llm_extractor.py` | Clause descriptions, instrument-aware prompts, substring constraint |
| `src/corpus/extraction/document_classifier.py` | New: document classification pipeline |
| `src/corpus/extraction/run_manifest.py` | New: run manifest + completion protocol |
| `src/corpus/cli.py` | All families in CLI, run_id dirs, classify command, stub filter |
| `scripts/round_report.py` | New: round report + section_located fix |
| `scripts/generate_splits.py` | New: PDIP calibration/evaluation splits |
| `scripts/dedup_extractions.py` | New: best-candidate deduplication |
| `docs/meta-learning-round-0.md` | New: lessons from CAC + pari passu |
| All test files | Tests for new modules |
