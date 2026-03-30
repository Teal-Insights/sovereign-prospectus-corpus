# Roundtable Book and Shiny App Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the Quarto book and update the Shiny app for the Georgetown Law #PublicDebtIsPublic roundtable on March 30, 2026.

**Architecture:** Chapter-by-chapter development with iterative review pipeline (Playwright visual inspection, style review, stakeholder persona review, user feedback via markdown). Data pipeline exports unified CSVs from all extraction sources; chapters use computed variables so numbers update automatically when data changes. Private content (framing docs, persona reviews) stays in `docs/private/` (gitignored).

**Tech Stack:** Quarto 1.8, Python Shiny, pandas, plotly, Playwright (for visual inspection), pre-commit hooks

**Spec:** `docs/superpowers/specs/2026-03-29-roundtable-book-design.md`

**Writing rules (apply to ALL content tasks):**
- No em dashes. Use commas, periods, or restructure.
- No AI-isms: "delve", "leverage", "utilize", "it's important to note", "in terms of", "aims to", "facilitates".
- No fluff or filler sentences. Short, direct sentences. Active voice.
- Specific limitations, not vague hedging.
- Follow `docs/lawyer-centered-design.md` principles.
- Read `docs/private/roundtable-framing.md` for tone and positioning guidance.

---

## File Map

### New files
- `demo/findings.qmd` — Chapter 1: What the Data Shows
- `demo/eval-workflow.qmd` — Chapter 2: The Eval Workflow
- `demo/call-to-action.qmd` — Chapter 3: Call to Action
- `demo/appendix-technical.qmd` — Appendix A: Technical Architecture
- `demo/appendix-validation.qmd` — Appendix B: Validation Approach
- `demo/appendix-coverage.qmd` — Appendix C: Corpus Coverage
- `demo/appendix-sovtech.qmd` — Appendix D: SovTech and the Bigger Picture
- `demo/data/export_all.py` — Unified export script for all families + classification
- `scripts/screenshot_book.py` — Playwright visual inspection script
- `scripts/pre_commit_private_check.py` — Pre-commit hook for private content

### Modified files
- `demo/_quarto.yml` — New chapter list and appendices
- `demo/index.qmd` — Preface rewrite
- `demo/shiny-app/app_v2.py` — New families, country filter, flywheel callouts, lawyer-centered copy
- `demo/references.bib` — Additional references if needed
- `.pre-commit-config.yaml` — Add private content check hook

### Deleted files
- `demo/chapter1.qmd` — Replaced by `findings.qmd`
- `demo/chapter2.qmd` — Replaced by `findings.qmd` (had the charts)
- `demo/chapter3.qmd` — Replaced by `call-to-action.qmd`

---

### Task 0: Infrastructure — Unified Export Script

**Files:**
- Create: `demo/data/export_all.py`
- Reference: `demo/data/export_v2.py` (existing, v1 only)

This script produces the CSVs that both the Quarto book and the Shiny app consume. It must handle v1 extractions, Round 1 family extractions, and document classification.

- [ ] **Step 1: Write the export script**

```python
# demo/data/export_all.py
"""Unified export: all extraction families + document classification.

Reads:
  - data/extracted_v2/cac_verified.jsonl, pp_verified.jsonl (v1)
  - data/extracted_v2/2026-03-29_round1/*/verified.jsonl (Round 1, only if COMPLETE.json exists)
  - data/extracted_v2/2026-03-29_round1/document_classification/classification.jsonl

Outputs:
  - demo/data/all_extractions.csv (clause extractions, all families)
  - demo/data/classification.csv (document classification)
  - demo/data/corpus_summary.csv (per-country, per-family counts)
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent

if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from corpus.extraction.country import guess_country  # noqa: E402

EXTRACTED_DIR = _REPO_ROOT / "data" / "extracted_v2"
ROUND1_DIR = EXTRACTED_DIR / "2026-03-29_round1"


def _resolve_country(rec: dict) -> str:
    """Get country from record, falling back to guess_country."""
    return rec.get("country", "") or guess_country(rec.get("storage_key", ""))


def _read_verified_jsonl(path: Path) -> list[dict]:
    """Read a verified.jsonl file, return list of records."""
    records = []
    with path.open() as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def export_extractions(output_path: Path) -> int:
    """Export all clause extractions to a single CSV."""
    all_records = []

    # v1 files
    for v1_file in sorted(EXTRACTED_DIR.glob("*_verified.jsonl")):
        if v1_file.name.endswith(".bak"):
            continue
        all_records.extend(_read_verified_jsonl(v1_file))

    # Round 1 family directories (only if COMPLETE.json exists)
    if ROUND1_DIR.exists():
        for family_dir in sorted(ROUND1_DIR.iterdir()):
            if not family_dir.is_dir():
                continue
            if family_dir.name == "document_classification":
                continue
            complete_marker = family_dir / "COMPLETE.json"
            verified_file = family_dir / "verified.jsonl"
            if complete_marker.exists() and verified_file.exists():
                all_records.extend(_read_verified_jsonl(verified_file))

    # Build CSV rows
    rows = []
    for rec in all_records:
        ext = rec.get("extraction", {})
        ver = rec.get("verification", {})
        if not ext.get("found"):
            continue

        source_fmt = rec.get("source_format", "")
        page_range = rec.get("page_range", [])
        if (
            isinstance(page_range, list)
            and len(page_range) >= 2
            and source_fmt == "flat_jsonl"
        ):
            page_start = str(page_range[0] + 1)
            page_end = str(page_range[1] + 1)
        else:
            page_start = ""
            page_end = ""

        rows.append({
            "candidate_id": rec.get("candidate_id", ""),
            "storage_key": rec.get("storage_key", ""),
            "country": _resolve_country(rec),
            "document_title": rec.get("document_title") or rec.get("storage_key", ""),
            "section_heading": rec.get("section_heading", ""),
            "page_start": page_start,
            "page_end": page_end,
            "heading_match": "Yes" if rec.get("heading_match") else "No",
            "cue_families": ", ".join(rec.get("cue_families_hit", [])),
            "llm_confidence": ext.get("confidence", ""),
            "llm_reasoning": ext.get("reasoning", ""),
            "clause_text": ext.get("clause_text", ""),
            "clause_length": len(ext.get("clause_text", "")),
            "section_text": rec.get("section_text", ""),
            "verbatim_status": ver.get("status", ""),
            "verbatim_similarity": ver.get("verbatim_similarity", ""),
            "quality_flags": ", ".join(ver.get("quality_flags", [])),
            "source_format": source_fmt,
            "run_id": rec.get("run_id", ""),
            "clause_family": rec.get("clause_family", ""),
        })

    fieldnames = list(rows[0].keys()) if rows else []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} extractions to {output_path}")
    return len(rows)


def export_classification(output_path: Path) -> int:
    """Export document classification to CSV."""
    cls_path = ROUND1_DIR / "document_classification" / "classification.jsonl"
    if not cls_path.exists():
        print(f"No classification file at {cls_path}")
        return 0

    rows = []
    with cls_path.open() as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({
                "storage_key": rec.get("storage_key", ""),
                "instrument_family": rec.get("instrument_family", ""),
                "document_role": rec.get("document_role", ""),
                "document_form": rec.get("document_form", ""),
                "confidence": rec.get("confidence", ""),
            })

    fieldnames = list(rows[0].keys()) if rows else []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} classifications to {output_path}")
    return len(rows)


def export_corpus_summary(extractions_path: Path, output_path: Path) -> None:
    """Build per-country, per-family summary from extractions CSV."""
    import collections
    counts: dict[tuple[str, str], int] = collections.Counter()
    with extractions_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            country = row.get("country", "") or "Unknown"
            family = row.get("clause_family", "") or "Unknown"
            counts[(country, family)] += 1

    rows = [
        {"country": k[0], "clause_family": k[1], "count": v}
        for k, v in sorted(counts.items())
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "clause_family", "count"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} summary rows to {output_path}")


if __name__ == "__main__":
    data_dir = _SCRIPT_DIR
    ext_path = data_dir / "all_extractions.csv"
    cls_path = data_dir / "classification.csv"
    summary_path = data_dir / "corpus_summary.csv"

    export_extractions(ext_path)
    export_classification(cls_path)
    export_corpus_summary(ext_path, summary_path)
```

- [ ] **Step 2: Run the export script and verify output**

Run: `uv run python3 demo/data/export_all.py`

Expected: Three files created with row counts printed. Verify:
```bash
wc -l demo/data/all_extractions.csv demo/data/classification.csv demo/data/corpus_summary.csv
head -1 demo/data/all_extractions.csv
head -3 demo/data/corpus_summary.csv
```

- [ ] **Step 3: Commit**

```bash
git add demo/data/export_all.py
git commit -m "feat: unified export script for all extraction families + classification"
```

---

### Task 1: Infrastructure — Quarto Config and File Scaffolding

**Files:**
- Modify: `demo/_quarto.yml`
- Create: `demo/findings.qmd`, `demo/eval-workflow.qmd`, `demo/call-to-action.qmd`
- Create: `demo/appendix-technical.qmd`, `demo/appendix-validation.qmd`, `demo/appendix-coverage.qmd`, `demo/appendix-sovtech.qmd`
- Delete: `demo/chapter1.qmd`, `demo/chapter2.qmd`, `demo/chapter3.qmd`

- [ ] **Step 1: Update `_quarto.yml`**

```yaml
project:
  type: book
  output-dir: _book

book:
  title: "Sovereign Clause Corpus"
  subtitle: "A Proof of Concept"
  author: "L. Teal Emery, Teal Insights"
  date: "March 2026"
  chapters:
    - index.qmd
    - findings.qmd
    - eval-workflow.qmd
    - call-to-action.qmd
  appendices:
    - appendix-technical.qmd
    - appendix-validation.qmd
    - appendix-coverage.qmd
    - appendix-sovtech.qmd
  page-navigation: true

bibliography: references.bib

format:
  html:
    theme: cosmo
    toc: true
    number-sections: false
    link-external-newwindow: true
```

- [ ] **Step 2: Create placeholder chapter files**

Each placeholder has a title and a one-line note so `quarto render` works immediately. These will be filled in by subsequent tasks.

`demo/findings.qmd`:
```markdown
# What the Data Shows

*Content in progress.*
```

`demo/eval-workflow.qmd`:
```markdown
# The Eval Workflow

*Content in progress.*
```

`demo/call-to-action.qmd`:
```markdown
# A Call for Collaboration

*Content in progress.*
```

`demo/appendix-technical.qmd`:
```markdown
# Technical Architecture {.appendix}

*Content in progress.*
```

`demo/appendix-validation.qmd`:
```markdown
# Validation Approach {.appendix}

*Content in progress.*
```

`demo/appendix-coverage.qmd`:
```markdown
# Corpus Coverage {.appendix}

*Content in progress.*
```

`demo/appendix-sovtech.qmd`:
```markdown
# SovTech and the Bigger Picture {.appendix}

*Content in progress.*
```

- [ ] **Step 3: Delete old chapter files**

```bash
git rm demo/chapter1.qmd demo/chapter2.qmd demo/chapter3.qmd
```

- [ ] **Step 4: Verify Quarto renders**

```bash
quarto render demo/
```

Expected: Builds with no errors. `demo/_book/index.html` exists with new chapter structure.

- [ ] **Step 5: Commit**

```bash
git add demo/_quarto.yml demo/findings.qmd demo/eval-workflow.qmd demo/call-to-action.qmd
git add demo/appendix-technical.qmd demo/appendix-validation.qmd demo/appendix-coverage.qmd demo/appendix-sovtech.qmd
git commit -m "refactor: new chapter structure for roundtable book"
```

---

### Task 2: Infrastructure — Playwright Visual Inspection Script

**Files:**
- Create: `scripts/screenshot_book.py`

This script renders the Quarto book to HTML, then takes screenshots of each page using Playwright. Screenshots go to `demo/reviews/` (gitignored).

- [ ] **Step 1: Install Playwright**

```bash
uv add --dev playwright
uv run playwright install chromium
```

- [ ] **Step 2: Write the screenshot script**

```python
# scripts/screenshot_book.py
"""Take screenshots of rendered Quarto book pages for visual inspection.

Usage:
    uv run python3 scripts/screenshot_book.py

Outputs screenshots to demo/reviews/screenshots/ (gitignored).
Requires: quarto render demo/ to have been run first.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

BOOK_DIR = Path(__file__).resolve().parent.parent / "demo" / "_book"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "demo" / "reviews" / "screenshots"


def screenshot_book() -> None:
    html_files = sorted(BOOK_DIR.glob("*.html"))
    if not html_files:
        print(f"No HTML files in {BOOK_DIR}. Run 'quarto render demo/' first.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        for html_file in html_files:
            url = f"file://{html_file}"
            page.goto(url, wait_until="networkidle")
            out_path = OUTPUT_DIR / f"{html_file.stem}.png"
            page.screenshot(path=str(out_path), full_page=True)
            print(f"  {html_file.name} -> {out_path.name}")

        browser.close()

    print(f"\n{len(html_files)} screenshots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    screenshot_book()
```

- [ ] **Step 3: Run it to verify**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

Expected: PNG files appear in `demo/reviews/screenshots/`. Verify they are gitignored:
```bash
git check-ignore demo/reviews/screenshots/index.png
```

- [ ] **Step 4: Commit**

```bash
git add scripts/screenshot_book.py
git commit -m "feat: Playwright screenshot script for visual book inspection"
```

---

### Task 3: Infrastructure — Pre-commit Hook for Private Content

**Files:**
- Create: `scripts/pre_commit_private_check.py`
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Write the pre-commit check script**

```python
# scripts/pre_commit_private_check.py
"""Pre-commit hook: block commits containing private framing content.

Scans staged files for patterns that belong in docs/private/ (gitignored),
not in public tracked files.
"""

from __future__ import annotations

import subprocess
import sys

# Patterns that should only appear in gitignored files.
# Keep this list in sync with docs/private/roundtable-framing.md.
BLOCKED_PATTERNS: list[str] = [
    "roundtable-framing.md",
    "review-round-",
    "persona review",
    "Teal persona",
    "Georgetown Law persona",
    "MDI persona",
]


def get_staged_content() -> str:
    """Get the diff of all staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    diff = get_staged_content()
    lower_diff = diff.lower()

    violations = []
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in lower_diff:
            violations.append(pattern)

    if violations:
        print("BLOCKED: Staged files contain private content patterns:")
        for v in violations:
            print(f"  - {v!r}")
        print("\nThese patterns belong in docs/private/ (gitignored).")
        print("Remove them from tracked files before committing.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Add the hook to `.pre-commit-config.yaml`**

Add this block at the end of the `repos:` list in `.pre-commit-config.yaml`:

```yaml
  # === PRIVATE CONTENT GUARD ===
  - repo: local
    hooks:
      - id: private-content-check
        name: block private framing content in public files
        entry: uv run python3 scripts/pre_commit_private_check.py
        language: system
        pass_filenames: false
        stages: [pre-commit]
```

- [ ] **Step 3: Test the hook**

Create a test file with a blocked pattern, stage it, and verify the hook blocks:
```bash
echo "Teal persona review" > /tmp/test_private.txt
cp /tmp/test_private.txt demo/test_private_check.qmd
git add demo/test_private_check.qmd
uv run python3 scripts/pre_commit_private_check.py
# Expected: exit code 1, prints "BLOCKED"
git reset HEAD demo/test_private_check.qmd
rm demo/test_private_check.qmd
```

- [ ] **Step 4: Commit**

```bash
git add scripts/pre_commit_private_check.py .pre-commit-config.yaml
git commit -m "feat: pre-commit hook blocks private framing content in public files"
```

---

### Task 4: Preface Rewrite

**Files:**
- Modify: `demo/index.qmd`
- Reference: `docs/private/roundtable-framing.md` (tone guidance, gitignored)
- Reference: `docs/lawyer-centered-design.md` (design principles)

This is the most tone-sensitive chapter. Sets the "proud but humble" framing for the entire book.

- [ ] **Step 1: Read the framing guidance**

Read `docs/private/roundtable-framing.md` and `docs/lawyer-centered-design.md` before writing.

- [ ] **Step 2: Write the Preface**

Write `demo/index.qmd`. Target ~300 words. Content:

- What this document accompanies (Georgetown Law roundtable, March 30, 2026, #PublicDebtIsPublic)
- What was built: one person, one week, open source pipeline that collects and searches sovereign bond prospectuses from three public sources
- Why PDIP annotations are the key: expert clause annotations are the seed that makes automated identification possible
- What this is NOT: not finished research, not a production system, not a substitute for expert legal analysis
- Specific limitations (list 3-4 concrete ones)
- What the reader will find in each chapter (brief)
- One sentence on Teal Insights / SovTech / NatureFinance support
- Logos: Teal Insights and NatureFinance, small, in an "About" callout or footer

Apply all writing rules from the spec. No em dashes. No AI-isms. Short sentences.

- [ ] **Step 3: Render and screenshot**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

Review the `demo/reviews/screenshots/index.png` screenshot for layout issues.

- [ ] **Step 4: Run review pipeline**

Dispatch four review agents in parallel (all output to `docs/private/`):

1. **Style reviewer**: Check writing rules compliance
2. **Stakeholder persona agents**: Per `docs/private/roundtable-framing.md` persona definitions
3. Collect all feedback into `docs/private/review-round-1-preface.md`

Format of review markdown:
```markdown
# Preface Review — Round 1

## Changes Made
- (list what was written)

## Style Review Findings
- (list any violations)

## Stakeholder Review Findings
- (list by persona)

## Visual Inspection
- (any layout/alignment issues from screenshots)

## Questions for You

### Q1: [specific question]
**Your response:**

### Q2: [specific question]
**Your response:**
```

- [ ] **Step 5: Iterate based on user feedback**

User responds via SuperWhisper voice dictation in the review markdown. Fix all flagged issues. Re-render, re-screenshot, re-review if needed. Repeat until approved.

- [ ] **Step 6: Commit**

```bash
git add demo/index.qmd
git commit -m "docs: rewrite Preface — proud but humble tone for roundtable"
```

---

### Task 5: Chapter 3 — Call to Action

**Files:**
- Modify: `demo/call-to-action.qmd`
- Reference: `docs/private/roundtable-framing.md`

Written second because the tone of the ask needs to be locked before we write findings. Target ~600 words.

- [ ] **Step 1: Write the Call to Action chapter**

Content (three specific asks, framed as invitations):

1. **Lawyers**: Review clauses. The tool is designed to respect your time (reference time-to-decision from lawyer-centered-design.md). Your expert judgment is the most valuable input.

2. **MDI / #PublicDebtIsPublic**: Help build the durable version. This prototype shows the concept works. A production system needs institutional architecture, hosting, sustained maintenance. Frame as complementary to their existing work.

3. **The community**: Help define what "trustworthy" automated clause identification means. This is a question for sovereign debt legal scholars and practitioners, not for one technologist.

Include the "About the Author" section: Teal's background (7 years sovereign debt analyst at Morgan Stanley IM, now building open source SovTech tools). Brief, factual, no puffery.

End with a closing paragraph: what #PublicDebtIsPublic has built is rare. Expert annotations of sovereign bond contract terms. This proof of concept shows one way those annotations can be made catalytic.

- [ ] **Step 2: Render and screenshot**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

- [ ] **Step 3: Run review pipeline**

Same four-agent review as Task 4. Output to `docs/private/review-round-1-call-to-action.md`.

The stakeholder persona review is especially important here. The MDI persona should confirm this reads as an invitation, not a challenge.

- [ ] **Step 4: Iterate based on user feedback**

Fix issues, re-render, re-review until approved.

- [ ] **Step 5: Commit**

```bash
git add demo/call-to-action.qmd
git commit -m "docs: Call to Action — three asks for roundtable collaboration"
```

---

### Task 6: Chapter 1 — Findings

**Files:**
- Modify: `demo/findings.qmd`
- Reference: `demo/data/all_extractions.csv`, `demo/data/classification.csv`, `demo/data/corpus_summary.csv`

Data-driven chapter. Charts carry the story. Target ~800 words + 5-6 visualizations. All numbers computed from data.

- [ ] **Step 1: Re-run the export script to get latest data**

```bash
uv run python3 demo/data/export_all.py
```

- [ ] **Step 2: Write the Findings chapter**

Structure:

**The Corpus** (~150 words)
- How many documents, from where, covering which countries
- Choropleth map (plotly) showing geographic coverage
- Brief note on document classification (instrument families, document roles)

**Governing Law** (~150 words)
- Jurisdiction breakdown chart (New York vs English vs other)
- What this tells us about the corpus and the market

**Collective Action Clauses** (~150 words)
- CAC prevalence by country (bar chart, top 15 countries)
- Brief observation about which countries appear most

**Pari Passu** (~100 words)
- Similar country breakdown
- Any interesting comparison with CAC distribution

**Sovereign Immunity Waivers** (~100 words)
- Waiver prevalence by country
- Which countries appear and which don't (interesting signal)

**Negative Pledge** (~100 words)
- Coverage and any notable patterns

**What We Don't Know Yet** (~100 words)
- Specific limitations: no inter-rater reliability check, no validation outside PDIP holdout, no temporal analysis, document classification not independently validated
- Frame as "what the next round of work should address"

All Python code blocks use pandas + plotly. Example pattern for each chart:

```python
#| label: fig-governing-law
#| fig-cap: "Governing law jurisdiction across extracted clauses"

import pandas as pd
import plotly.express as px

df = pd.read_csv("data/all_extractions.csv", dtype=str)
gl = df[df["clause_family"] == "governing_law"].copy()

# Extract jurisdiction from clause text
def classify_jurisdiction(text):
    t = str(text).lower()
    if "new york" in t:
        return "New York"
    elif "english law" in t:
        return "English"
    else:
        return "Other"

gl["jurisdiction"] = gl["clause_text"].apply(classify_jurisdiction)
counts = gl["jurisdiction"].value_counts().reset_index()
counts.columns = ["Jurisdiction", "Count"]

fig = px.bar(
    counts,
    x="Jurisdiction",
    y="Count",
    text="Count",
    title="Governing Law Jurisdiction",
    color="Jurisdiction",
    color_discrete_map={"New York": "#2c7bb6", "English": "#d7191c", "Other": "#999"},
)
fig.update_layout(
    height=400,
    showlegend=False,
    margin=dict(l=0, r=20, t=40, b=0),
)
fig.update_traces(textposition="outside")
fig.show()
```

Follow this pattern for each chart. Use `pd.read_csv("data/all_extractions.csv")` or `pd.read_csv("data/classification.csv")` as the data source. Compute everything from the CSV, never hardcode numbers.

- [ ] **Step 3: Render and screenshot**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

- [ ] **Step 4: Run review pipeline**

Four-agent review. Style review focuses on chart titles, axis labels, and prose connections between charts. Stakeholder personas check that findings are presented honestly without overclaiming.

Output to `docs/private/review-round-1-findings.md`.

- [ ] **Step 5: Iterate based on user feedback**

User may want different chart types, different orderings, or different emphasis. Fix and re-render.

- [ ] **Step 6: Commit**

```bash
git add demo/findings.qmd
git commit -m "docs: Findings chapter — data-driven charts for all extracted families"
```

---

### Task 7: Chapter 2 — Eval Workflow

**Files:**
- Modify: `demo/eval-workflow.qmd`
- Reference: `docs/lawyer-centered-design.md`

Connects the book to the Shiny app. Shows what it looks like to review a clause. Target ~500 words.

- [ ] **Step 1: Write the Eval Workflow chapter**

Content:

**What a reviewer sees** (~200 words)
- Screenshot or mockup of the Shiny app showing a candidate clause
- Walk through the interface: extracted clause (primary), section context (expandable), decision buttons
- Emphasize: the system did the search, the expert does the judgment

**The flywheel in concrete terms** (~150 words)
- Step 1: System finds candidates using patterns derived from expert annotations
- Step 2: Expert reviews and validates (or corrects)
- Step 3: Corrections improve the patterns for next round
- Include the mermaid diagram from the existing chapter (keep it, it's good)

**Time-to-decision** (~100 words)
- A well-designed tool means 10 seconds for obvious cases, 30-60 for uncertain ones
- 15 minutes of lawyer time = 20-30 validated clauses
- Each validation teaches the system something

**Try it yourself** (~50 words)
- Link to the Shiny app (iframe embed or direct link)
- Brief instruction: pick a clause family, click through candidates, submit your assessment

- [ ] **Step 2: Render and screenshot**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

- [ ] **Step 3: Run review pipeline**

Output to `docs/private/review-round-1-eval-workflow.md`. Georgetown Law persona is especially important here: does this frame the interaction as expert judgment (not labeling)?

- [ ] **Step 4: Iterate based on user feedback**

- [ ] **Step 5: Commit**

```bash
git add demo/eval-workflow.qmd
git commit -m "docs: Eval Workflow chapter — flywheel and reviewer experience"
```

---

### Task 8: Shiny App Updates

**Files:**
- Modify: `demo/shiny-app/app_v2.py`
- Reference: `docs/lawyer-centered-design.md`
- Reference: `docs/private/roundtable-framing.md`
- Data source: `demo/data/all_extractions.csv` (from Task 0 export)

- [ ] **Step 1: Update the Shiny app**

Changes to `demo/shiny-app/app_v2.py`:

**a) Update data path to use unified CSV:**

Change `CANDIDATES_PATH` to point to `all_extractions.csv`:
```python
CANDIDATES_PATH = DATA_DIR / "all_extractions.csv"
```

**b) Add all clause family labels:**
```python
CLAUSE_FAMILY_LABELS: dict[str, str] = {
    "collective_action": "Collective Action Clause (CAC)",
    "pari_passu": "Pari Passu",
    "governing_law": "Governing Law",
    "sovereign_immunity": "Sovereign Immunity",
    "negative_pledge": "Negative Pledge",
    "events_of_default": "Events of Default",
}
```

**c) Add country filter to sidebar:**

After the clause family selector, add:
```python
ui.input_select(
    "country_filter",
    "Country",
    choices={"": "All Countries"},
    selected="",
),
```

Then in the server, dynamically populate country choices and apply the filter:
```python
@reactive.Effect
def _update_country_choices() -> None:
    family = input.clause_family()
    df = ALL_CANDIDATES[ALL_CANDIDATES["clause_family"] == family]
    countries = sorted(df["country"].dropna().unique().tolist())
    countries = [c for c in countries if c]
    choices = {"": "All Countries"}
    choices.update({c: c for c in countries})
    ui.update_select("country_filter", choices=choices, selected="")
```

In `filtered_df()`, add country filtering:
```python
country = input.country_filter()
if country:
    df = df[df["country"] == country]
```

**d) Update sidebar copy per lawyer-centered-design.md:**

Replace the sidebar header and instructions:
```python
ui.sidebar(
    ui.h5("Clause Eval Explorer"),
    ui.tags.div(
        ui.p(
            "Sovereign bond clause extraction for expert review.",
            style="font-size: 0.9em; font-weight: 500; margin-bottom: 4px;",
        ),
        ui.p(
            "Part of the #PublicDebtIsPublic initiative.",
            style="font-size: 0.85em; color: #666; margin-bottom: 0;",
        ),
        style="margin-bottom: 12px;",
    ),
    ui.hr(),
    # ... filters ...
    ui.hr(),
    ui.output_text("record_count"),
    ui.hr(),
    ui.p(
        ui.strong("How to use:"),
        ui.tags.ol(
            ui.tags.li("Select a clause type and filters."),
            ui.tags.li("Review candidates in order."),
            ui.tags.li("Validate or correct the extraction."),
        ),
        style="font-size: 0.85em;",
    ),
    width=300,
),
```

**e) Add flywheel callout at top of page (above the table):**
```python
ui.card(
    ui.tags.div(
        ui.tags.p(
            ui.tags.strong("How this works: "),
            "This tool surfaces clause candidates found by automated "
            "pattern matching. Your expert judgment validates each one. "
            "Every review improves future identification across the "
            "full corpus.",
            style="font-size: 0.9em; margin: 0;",
        ),
        style="background: #e8f4f8; padding: 12px 16px; border-radius: 4px; "
              "border-left: 4px solid #2c7bb6;",
    ),
),
```

**f) Update feedback section copy:**

Change "Rating extraction for candidate" to:
```python
ui.tags.p(
    "Validate clause boundaries. Your expert judgment improves the dataset.",
    style="font-size:0.85em;color:#555;margin-bottom:8px;",
),
```

Change `FEEDBACK_OPTIONS` labels to match lawyer-centered-design.md:
```python
FEEDBACK_OPTIONS: dict[str, str] = {
    "correct": "Correct Clause",
    "wrong_boundaries": "Wrong Boundaries",
    "not_a_clause": "Not a Clause",
    "partial": "Partial Match",
    "needs_second_look": "Needs Second Look",
}
```

**g) Update table columns per lawyer-centered-design.md:**

Replace the `display_df()` function to show triage-friendly columns:
```python
@reactive.Calc
def display_df() -> pd.DataFrame:
    df = filtered_df()
    result = pd.DataFrame(
        {
            "Country": df["country"],
            "Document": df["document_title"].str[-40:],
            "Section": df["section_heading"].str[:50],
            "Page": df.apply(
                lambda r: f"p. {r['page_start']}" if r["page_start"] else "",
                axis=1,
            ),
            "Surfaced By": df["heading_match"].map(
                {"Yes": "Heading", "No": "Body cues"}
            ),
            "Confidence": df["llm_confidence"].str.capitalize(),
            "Preview": df["clause_text"].str[:80],
        }
    )
    return result
```

- [ ] **Step 2: Update the Shiny data symlink or path**

Make sure the Shiny app can find the new CSV. The app already reads from `demo/data/`, and `export_all.py` writes there. Verify:
```bash
ls -la demo/data/all_extractions.csv
```

- [ ] **Step 3: Run the Shiny app locally and test**

```bash
cd demo/shiny-app && uv run shiny run app_v2.py --port 8080
```

Open `http://localhost:8080` in browser. Verify:
- All clause families appear in dropdown
- Country filter populates dynamically
- Flywheel callout is visible at top
- Table columns match spec
- Decision labels match lawyer-centered-design.md

- [ ] **Step 4: Take Playwright screenshots of the running app**

Write a quick script or manually screenshot key states:
- Landing page with flywheel callout
- A selected clause (detail panel)
- Feedback panel

Save to `demo/reviews/screenshots/`.

- [ ] **Step 5: Run review pipeline**

Same four-agent review as chapters. Output to `docs/private/review-round-1-shiny.md`. Pay special attention to:
- Callout copy (flywheel framing)
- Decision labels (expert judgment, not rating)
- Table columns (triage-friendly)

- [ ] **Step 6: Iterate based on user feedback**

- [ ] **Step 7: Commit**

```bash
git add demo/shiny-app/app_v2.py
git commit -m "feat: Shiny app — new families, country filter, flywheel callouts, lawyer-centered copy"
```

---

### Task 9: Appendices

**Files:**
- Modify: `demo/appendix-technical.qmd`, `demo/appendix-validation.qmd`, `demo/appendix-coverage.qmd`, `demo/appendix-sovtech.qmd`

Less tone-sensitive than the main chapters. Faster iteration.

- [ ] **Step 1: Write Appendix A — Technical Architecture**

~400 words. Content:
- Pipeline overview: download (SEC EDGAR, FCA NSM, PDIP) -> parse (PyMuPDF for PDF, native for HTML/text) -> locate (section-aware cue matching) -> extract (LLM verbatim extraction) -> verify (fuzzy string matching)
- Three data sources with document counts
- Section-aware extraction: heading-based and body-cue-based clause identification
- Verbatim verification: extracted text checked against source document
- Brief tech stack: Python, DuckDB, Click CLI, open source (MIT)

- [ ] **Step 2: Write Appendix B — Validation Approach**

~400 words. Content:
- PDIP holdout methodology: calibration/evaluation split (seed=42, 5 calibration docs)
- What we measure: recall against PDIP expert annotations on the evaluation set
- Verbatim similarity: fuzzy string matching with 0.95 threshold, windowed approach for OCR noise
- Per-family trust metrics from round report (use computed values from CSVs)
- Specific limitations: small holdout set, single annotator baseline, no inter-rater reliability, no precision measurement (we don't know false positive rate without expert review)
- "This is why we need lawyer evals" (connects to Chapter 3)

- [ ] **Step 3: Write Appendix C — Corpus Coverage**

~400 words + tables. Content:
- Full table: documents by source (EDGAR, NSM, PDIP) with counts
- Document classification distribution table (instrument family x document role)
- Clause family coverage table: per-family extraction counts, by source
- Geographic coverage: countries with most documents
- All tables generated from CSVs using pandas, not hardcoded

Example Python block:
```python
#| label: tbl-coverage
#| tbl-cap: "Clause extraction coverage by family"

import pandas as pd

summary = pd.read_csv("data/corpus_summary.csv")
by_family = summary.groupby("clause_family")["count"].sum().reset_index()
by_family.columns = ["Clause Family", "Extractions Found"]
by_family["Clause Family"] = by_family["Clause Family"].str.replace("_", " ").str.title()
by_family = by_family.sort_values("Extractions Found", ascending=False)

from IPython.display import Markdown
Markdown(by_family.to_markdown(index=False))
```

- [ ] **Step 4: Write Appendix D — SovTech and the Bigger Picture**

~400 words. Content:
- What SovTech means: open-source technology infrastructure for sovereign debt transparency and climate finance
- How this project fits: the sovereign clause corpus is one component of a broader toolkit
- NatureFinance support: grant-funded work enabling open-source development
- Connection to climate finance: sovereign debt terms affect restructuring capacity, which affects climate investment
- The open-source model: MIT licensed, anyone can use, fork, extend
- Brief vision: continuous monitoring of new prospectus filings, automatic clause identification, community-validated methodology

- [ ] **Step 5: Render and screenshot all appendices**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

- [ ] **Step 6: Run review pipeline on all appendices**

Style review only (no persona review needed for appendices unless content touches positioning). Output to `docs/private/review-round-1-appendices.md`.

- [ ] **Step 7: Iterate based on user feedback**

- [ ] **Step 8: Commit**

```bash
git add demo/appendix-technical.qmd demo/appendix-validation.qmd demo/appendix-coverage.qmd demo/appendix-sovtech.qmd
git commit -m "docs: four appendices — technical, validation, coverage, SovTech"
```

---

### Task 10: Final Integration and Visual Polish

**Files:**
- Possibly modify: any chapter file for cross-references, consistency
- Reference: all screenshots from previous tasks

- [ ] **Step 1: Full render and visual inspection**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

Review all screenshots for:
- Consistent heading styles across chapters
- Chart sizing and spacing
- No broken cross-references
- Logos render correctly
- Appendices are properly separated from main chapters
- Table of contents looks right
- Page navigation works

- [ ] **Step 2: Cross-chapter consistency check**

Read all chapters in sequence. Check:
- Numbers match between chapters (findings) and appendices (coverage)
- Tone is consistent (proud but humble throughout)
- No repeated content between chapters
- Cross-references work ("as shown in Appendix B")
- The narrative arc flows: what we found -> how validation works -> what we're asking for

- [ ] **Step 3: Full review pipeline**

Run all four review agents on the complete book. This is the final quality gate. Output to `docs/private/review-round-final.md`.

- [ ] **Step 4: Fix any remaining issues**

- [ ] **Step 5: Run pre-commit hook manually**

```bash
git add -A
uv run python3 scripts/pre_commit_private_check.py
```

Verify no private content leaked into tracked files.

- [ ] **Step 6: Final commit**

```bash
git add demo/
git commit -m "docs: final polish — visual consistency, cross-references, integration"
```

---

### Task 11: Data Refresh (run when Mac Mini finishes)

This task is executed whenever new extraction data arrives from the Mac Mini via Dropbox.

**Files:**
- No code changes — just re-run export and re-render

- [ ] **Step 1: Verify new data is complete**

Check for COMPLETE.json markers:
```bash
for dir in data/extracted_v2/2026-03-29_round1/*/; do
    name=$(basename "$dir")
    if [ -f "$dir/COMPLETE.json" ]; then
        echo "$name: COMPLETE"
    else
        echo "$name: IN PROGRESS"
    fi
done
```

- [ ] **Step 2: Re-run export**

```bash
uv run python3 demo/data/export_all.py
```

- [ ] **Step 3: Re-render**

```bash
quarto render demo/ && uv run python3 scripts/screenshot_book.py
```

- [ ] **Step 4: Verify numbers updated**

Check that the findings chapter shows updated counts in the rendered HTML. Spot-check a few numbers against the export script output.

- [ ] **Step 5: Commit if numbers changed significantly**

```bash
git add demo/data/*.csv
git commit -m "data: refresh extraction exports with latest Round 1 results"
```
