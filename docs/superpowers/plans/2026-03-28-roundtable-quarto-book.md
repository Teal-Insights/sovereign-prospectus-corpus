# Roundtable Quarto Book + Shiny Eval Explorer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-chapter Quarto book with static visualizations and an embedded Shiny for Python eval explorer app, deployed to GitHub Pages, for the #PublicDebtIsPublic Scoping Roundtable (March 30, 2026).

**Architecture:** Quarto book project in a new `demo/` directory within the existing repo. Static visualizations generated via Python (plotly/matplotlib). Shiny app built in Python (shiny for Python), deployed to shinyapps.io or shinylive, embedded in the Quarto book via iframe. Data for the Shiny app pre-exported as CSV from DuckDB (no database at runtime).

**Tech Stack:** Quarto 1.8, Python 3.12, Shiny for Python, plotly, DuckDB, GitHub Pages

**Two-branch strategy:**

- **Branch 1 (this plan, `feature/26-roundtable-quarto-book`):** Quarto book scaffold, narrative chapters (1 + 3), data export pipeline, placeholder Chapter 2. Gets the text right.
- **Branch 2 (next session):** Pattern optimization, corpus exploration, improved preliminary results, static visualizations, Shiny eval explorer app, final Chapter 2 with real data. Gets the results right.

**Pre-flight:**
```bash
uv add shiny plotly
```

**Spec:** `docs/superpowers/specs/2026-03-28-roundtable-quarto-book-design.md`

---

## File Structure

### New Files (Branch 1 — this plan)

| File | Responsibility |
|------|---------------|
| `demo/_quarto.yml` | Quarto book config (title, chapters, theme, output) |
| `demo/index.qmd` | Landing page / preface |
| `demo/chapter1.qmd` | "What We Built and Why" — narrative + flywheel diagram |
| `demo/chapter2.qmd` | "Preliminary Findings" — placeholder for Branch 2 visualizations |
| `demo/chapter3.qmd` | "A Lawyer-in-the-Loop Flywheel" — co-design ask |
| `demo/references.bib` | Bibliography (Gelpern 2019, Rivetti & Mihalyi 2025) |
| `demo/data/export_data.py` | Python script to export DuckDB data → CSV |
| `demo/data/issuer_country_map.csv` | Hand-curated: issuer_name → country_code mapping |

### New Files (Branch 2 — next session)

| File | Responsibility |
|------|---------------|
| `demo/data/corpus_by_country.csv` | Exported: country, source, document count |
| `demo/data/clause_families.csv` | Exported: label_family, annotation count, doc count |
| `demo/data/grep_candidates.csv` | Exported: grep matches with context for Shiny app |
| `demo/shiny-app/app.py` | Shiny for Python eval explorer |
| `demo/shiny-app/data/` | Copy of exported CSVs for Shiny deployment |
| `.github/workflows/publish-demo.yml` | GitHub Actions to render + deploy Quarto to Pages |

---

## Task 1: Quarto Book Scaffold

**Files:**
- Create: `demo/_quarto.yml`
- Create: `demo/index.qmd`
- Create: `demo/references.bib`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p demo/data demo/shiny-app/data demo/images
```

- [ ] **Step 2: Create Quarto config**

Create `demo/_quarto.yml`:

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
    - chapter1.qmd
    - chapter2.qmd
    - chapter3.qmd
  page-navigation: true

bibliography: references.bib

format:
  html:
    theme: cosmo
    toc: true
    number-sections: false
    link-external-newwindow: true
```

- [ ] **Step 3: Create landing page**

Create `demo/index.qmd`:

```markdown
# Preface {.unnumbered}

This document accompanies a proof of concept presented at the
[#PublicDebtIsPublic](https://publicdebtispublic.mdi.georgetown.edu/)
Scoping Roundtable on March 30, 2026 at Georgetown University Law Center.

It demonstrates how expert clause annotations — like those created by
the #PublicDebtIsPublic initiative — can power a scalable system for
identifying and monitoring key terms in sovereign bond prospectuses.

**What's here:**

- **Chapter 1** explains what we built in one week and why the
  #PublicDebtIsPublic annotated corpus is catalytic
- **Chapter 2** presents preliminary findings with interactive
  exploration
- **Chapter 3** proposes a lawyer-in-the-loop flywheel and outlines
  what collaboration could look like

The code behind this work is open source and available on
[GitHub](https://github.com/Teal-Insights/sovereign-prospectus-corpus).

::: {.callout-note}
This is a proof of concept. Findings are preliminary and the methodology
needs expert review. We present it as evidence that the approach works
and merits further development — not as finished research.
:::
```

- [ ] **Step 4: Create bibliography**

Create `demo/references.bib`:

```bibtex
@article{gelpern2019boilerplate,
  title={If Boilerplate Could Talk: The Work of Standard Terms in Sovereign Bond Contracts},
  author={Gelpern, Anna},
  journal={Law \& Social Inquiry},
  volume={44},
  number={3},
  pages={617--646},
  year={2019}
}

@report{rivetti2025radical,
  title={Radical Debt Transparency},
  author={Rivetti, Diego and Mihalyi, David},
  institution={World Bank},
  year={2025},
  url={https://www.worldbank.org/en/publication/2025-debt-transparency-report}
}
```

- [ ] **Step 5: Test Quarto renders**

```bash
cd demo && quarto render index.qmd && cd ..
ls demo/_book/index.html
```

Expected: HTML file renders without errors.

- [ ] **Step 6: Commit**

```bash
git add demo/_quarto.yml demo/index.qmd demo/references.bib
git commit -m "feat: Quarto book scaffold with config and landing page"
```

---

## Task 2: Chapter 1 — "What We Built and Why"

**Files:**
- Create: `demo/chapter1.qmd`

- [ ] **Step 1: Create Chapter 1**

Create `demo/chapter1.qmd`:

````markdown
# What We Built and Why

Sovereign bond prospectuses are public documents — filed with the SEC in
New York, the FCA in London. But in practice, doing cross-country,
cross-regional research on contract terms is cumbersome and
time-consuming. A researcher studying how collective action clauses vary
across African, Latin American, and European issuers would need to
navigate multiple filing systems, download documents one by one, and
read through hundreds of pages of boilerplate to find the 10% that
varies.

## One Week, Three Sources, 4,800+ Documents

In one week, we built an open-source pipeline that collected over 4,800
sovereign bond prospectuses from three public sources:

| Source | Documents | Description |
|--------|-----------|-------------|
| SEC EDGAR | ~3,300 | US securities filings by sovereign issuers |
| FCA National Storage Mechanism | ~900 | UK regulatory filings |
| #PublicDebtIsPublic | ~823 | Expert-annotated sovereign debt corpus |
| **Total** | **~4,800+** | |

All documents are parsed into searchable text and stored in a single
database. The pipeline handles PDFs, HTML filings, and plain text — with
encoding detection for documents filed across different systems and eras.

## Why #PublicDebtIsPublic Annotations Are Catalytic

The #PublicDebtIsPublic corpus is special. It contains 122 documents
where legal experts have hand-annotated specific clause types —
collective action clauses, pari passu, governing law, events of default,
and many more. Across these documents, experts identified over 6,200
individual clause annotations spanning 25 clause families.

These expert annotations are the seed that makes everything else
possible. We used them to build retrieval patterns that find similar
clauses across the much larger SEC and FCA corpora. The more clauses
experts review and validate, the more accurate automated identification
becomes.

## The Flywheel

```{mermaid}
%%| fig-cap: "Each expert review improves the next round of automated identification"
%%| fig-width: 6
flowchart LR
    A["Expert<br/>Annotation"] --> B["Pattern<br/>Extraction"]
    B --> C["Candidate Retrieval<br/>Across Full Corpus"]
    C --> D["Expert Review<br/>(yes / no + why)"]
    D --> E["Improved<br/>Patterns"]
    E --> B
```

This is a proof of concept built in one week. The findings are
preliminary and the methodology needs expert review. But the
infrastructure is open source, and it demonstrates how expert legal
knowledge can be made catalytic — scaling the impact of every annotation
across thousands of documents.
````

- [ ] **Step 2: Test render**

```bash
cd demo && quarto render chapter1.qmd && cd ..
```

Expected: Renders with Mermaid diagram.

- [ ] **Step 3: Commit**

```bash
git add demo/chapter1.qmd
git commit -m "feat: Chapter 1 — what we built and why"
```

---

## Task 3: Chapter 3 — "A Lawyer-in-the-Loop Flywheel"

**Files:**
- Create: `demo/chapter3.qmd`

- [ ] **Step 1: Create Chapter 3**

Create `demo/chapter3.qmd`:

````markdown
# A Lawyer-in-the-Loop Flywheel

#PublicDebtIsPublic has already built something remarkable — over 900
documents from 45+ countries with expert-annotated contract terms. The
initiative's five-year plan envisions comprehensive global coverage.
This proof of concept demonstrates an approach that could help amplify
that rare and valuable legal expertise — making every annotation reach
further across the corpus.

## Inverting the Workflow

Today, a legal expert searching for a collective action clause in a
prospectus might Control+F for "collective action" or navigate to the
section where it typically appears — then read carefully to confirm.
Multiply that across hundreds of documents and dozens of clause types.

Now imagine: the system surfaces a candidate clause in a browser window.
The expert clicks yes or no, and if no, briefly says why. That "why"
gets embedded in the system — surfacing better candidates next time. The
expert's tacit knowledge about what makes a clause a real CAC (versus
something that just mentions collective action in passing) gradually
becomes part of the infrastructure itself.

## How Evaluation Works

We borrow the concept of "evals" from AI development — systematic
quality measurement that improves with every round of expert feedback.
Three key ideas:

### Binary Judgments with Reasoning

A candidate appears on screen. Is this a collective action clause? Yes
or no. If no, a brief note on why — wrong section, mentions CAC but
isn't the clause itself, truncated. These corrections are what make the
system learn.

Over time, the tacit knowledge that experienced sovereign debt lawyers
carry — knowing at a glance that a passage is boilerplate versus a
meaningful clause — gets embedded in the evaluation data.

### Disagreement as Signal

If two lawyers look at the same passage and disagree, that's not noise —
it's research signal. It likely means the clause uses novel language.
That's exactly the kind of variation that matters for understanding how
contract terms evolve across markets [see @gelpern2019boilerplate].

### The Flywheel Compounds

With traditional annotation, reviewing 100 documents gives you 100
annotated documents. With this approach, reviewing 100 documents trains
a system that can surface high-quality candidates across thousands. The
expert's time compounds rather than being spent once and forgotten.

## The Long-Term Vision

In the early stages, legal experts review many candidates — building the
system's understanding of what counts as a real collective action clause
versus a passing mention. But as edge cases get worked through and
patterns accumulate, standard cases resolve automatically. A contract
with a textbook ICMA model CAC doesn't need human review — the system
recognizes it with high confidence. Expert attention focuses only on the
genuinely ambiguous cases, which is where it's most valuable anyway.

The end state is a system that ingests new prospectuses as they're filed
with the SEC and FCA, automatically identifies and tags key clauses with
high confidence, and flags the ones that are unusual or novel for expert
review. That's when things get really interesting.

Building on work studying how sovereign debt boilerplate evolves
[@gelpern2019boilerplate], we'd be able to see — in near-real-time —
when clause language changes in ways that should raise eyebrows. A new
CAC formulation from a frequent issuer. A pari passu clause that departs
from market standard. An unusual governing law choice. These are the
signals that matter for oversight, for research, and for the markets.

And at scale, we'd be able to see aggregated trends across time,
geography, and issuer type — how contract terms are actually evolving
across the sovereign debt landscape, not based on a sample of
hand-reviewed documents, but across the full universe of publicly filed
prospectuses.

## What We're Proposing

::: {.callout-tip}
## What would help

- **A shared methodology for what "trustworthy" means.** The sovereign
  debt legal, academic, and policy communities all need to be able to
  rely on automated clause identification. If it's not seen as credible,
  no one will use it. If it is, it becomes an extraordinary shared
  resource. The first step is investing in rigorous evaluation standards
  together — what does it mean for an automated identification to be
  good enough to trust?

- **A small group to run the first structured evaluation round.**
  #PublicDebtIsPublic as the organizing secretariat, drawing reviewers
  from the broader sovereign debt community: law students, sovereign
  debt lawyers interested in pro bono contributions, legal scholars.

- **Guidance on which clause families matter most** for accountability
  and oversight research.
:::

::: {.callout-note}
## What we don't need

- **Money** — this work is grant-funded and open source (MIT licensed,
  meaning anyone can use it for free — it's a public resource).
- **Official endorsement** — we understand institutional constraints.
- **Access to confidential materials** — we work exclusively with
  publicly filed documents.
:::

## A Note on the Author

I spent seven years as a sovereign debt analyst at Morgan Stanley
Investment Management before pivoting to building open-source tools for
sovereign debt analysis — which is a polite way of saying I'm a
sovereign debt nerd who now spends most of his time writing code and
wrangling data. I'd be glad to help with the technical side of this as a
collaborating partner.

## Closing

#PublicDebtIsPublic has identified that transparency requires
infrastructure — information, technology, and legal frameworks working
together. This proof of concept is a small contribution to the
technology pillar: demonstrating how expert legal knowledge can be made
catalytic, so that every annotation reaches further across the growing
universe of publicly filed sovereign debt documents.

## References
````

- [ ] **Step 2: Test render**

```bash
cd demo && quarto render chapter3.qmd && cd ..
```

- [ ] **Step 3: Commit**

```bash
git add demo/chapter3.qmd
git commit -m "feat: Chapter 3 — lawyer-in-the-loop flywheel and co-design ask"
```

---

## Task 4: Chapter 2 Placeholder + Data Export Script

**Files:**
- Create: `demo/chapter2.qmd` (placeholder)
- Create: `demo/data/export_data.py`
- Create: `demo/data/issuer_country_map.csv`

- [ ] **Step 1: Create Chapter 2 placeholder**

Create `demo/chapter2.qmd`:

````markdown
# Preliminary Findings

::: {.callout-warning}
These are preliminary results from a one-week proof of concept. We
present them as evidence that the approach works and merits expert
methodology review — not as finished research.
:::

## The Corpus

*Visualization: world map of corpus coverage — coming soon.*

We collected over 4,800 sovereign bond prospectuses from three public
sources. The map below shows geographic coverage — the number of
documents per country across all three sources.

## What #PublicDebtIsPublic Annotations Reveal

*Visualization: clause family coverage chart — coming soon.*

The #PublicDebtIsPublic corpus contains 122 documents with over 6,200
expert clause annotations across 25 clause families.

## Retrieval Validation

*Table: precision/recall for key clause families — coming soon.*

## Try It Yourself: The Eval Explorer

*Interactive Shiny app — coming soon.*
````

- [ ] **Step 2: Create the issuer-to-country mapping**

Create `demo/data/issuer_country_map.csv`:

```csv
issuer_pattern,country_name,country_code
ISRAEL,Israel,ISR
MEXICO,Mexico,MEX
TURKEY,Turkey,TUR
COLOMBIA,Colombia,COL
BRAZIL,Brazil,BRA
CHILE,Chile,CHL
PHILIPPINES,Philippines,PHL
URUGUAY,Uruguay,URY
PANAMA,Panama,PAN
INDONESIA,Indonesia,IDN
PERU,Peru,PER
SOUTH AFRICA,South Africa,ZAF
CANADA,Canada,CAN
KOREA,Korea Republic of,KOR
JAMAICA,Jamaica,JAM
SWEDEN,Sweden,SWE
NIGERIA,Nigeria,NGA
ABU DHABI,United Arab Emirates,ARE
EGYPT,Egypt,EGY
FINLAND,Finland,FIN
CYPRUS,Cyprus,CYP
HUNGARY,Hungary,HUN
KAZAKHSTAN,Kazakhstan,KAZ
GHANA,Ghana,GHA
ICELAND,Iceland,ISL
SERBIA,Serbia,SRB
SAUDI ARABIA,Saudi Arabia,SAU
ARGENTINA,Argentina,ARG
DOMINICAN REPUBLIC,Dominican Republic,DOM
ECUADOR,Ecuador,ECU
KENYA,Kenya,KEN
ALBANIA,Albania,ALB
SIERRA LEONE,Sierra Leone,SLE
MOLDOVA,Moldova,MDA
CAMEROON,Cameroon,CMR
RWANDA,Rwanda,RWA
SENEGAL,Senegal,SEN
ITALY,Italy,ITA
NETHERLANDS,Netherlands,NLD
JAPAN,Japan,JPN
LEBANON,Lebanon,LBN
COSTA RICA,Costa Rica,CRI
BARBADOS,Barbados,BRB
BAHAMAS,Bahamas,BHS
BERMUDA,Bermuda,BMU
TRINIDAD,Trinidad and Tobago,TTO
SRI LANKA,Sri Lanka,LKA
PAKISTAN,Pakistan,PAK
EL SALVADOR,El Salvador,SLV
VENEZUELA,Venezuela,VEN
JORDAN,Jordan,JOR
MOROCCO,Morocco,MAR
```

- [ ] **Step 3: Create the data export script**

Create `demo/data/export_data.py`:

```python
"""Export DuckDB data to CSV for Quarto visualizations and Shiny app."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data/db/corpus.duckdb"
MANIFEST_DIR = PROJECT_ROOT / "data/manifests"
OUTPUT_DIR = Path(__file__).resolve().parent
COUNTRY_MAP_PATH = OUTPUT_DIR / "issuer_country_map.csv"


def load_country_map() -> dict[str, tuple[str, str]]:
    """Load issuer pattern -> (country_name, country_code) mapping."""
    mapping: dict[str, tuple[str, str]] = {}
    with COUNTRY_MAP_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["issuer_pattern"].upper()] = (
                row["country_name"],
                row["country_code"],
            )
    return mapping


def match_country(
    issuer_name: str, country_map: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Match an issuer name to a country using substring matching."""
    upper = issuer_name.upper()
    for pattern, country_info in country_map.items():
        if pattern in upper:
            return country_info
    return None


def export_corpus_by_country() -> None:
    """Export document counts by country and source."""
    country_map = load_country_map()
    counts: Counter[tuple[str, str, str]] = Counter()

    for manifest_name in ["nsm_manifest.jsonl", "edgar_manifest.jsonl"]:
        manifest_path = MANIFEST_DIR / manifest_name
        if not manifest_path.exists():
            continue
        source = manifest_name.split("_")[0]
        with manifest_path.open() as f:
            for line in f:
                record = json.loads(line)
                issuer = record.get("issuer_name", "")
                match = match_country(issuer, country_map)
                if match:
                    counts[(match[0], match[1], source)] += 1

    con = duckdb.connect(str(DB_PATH), read_only=True)
    pdip_rows = con.execute(
        """SELECT country, COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses
           WHERE country IS NOT NULL
           GROUP BY country"""
    ).fetchall()
    con.close()

    pdip_country_to_code = {
        "Indonesia": "IDN", "Jamaica": "JAM", "Kenya": "KEN",
        "Philippines": "PHL", "Netherlands": "NLD", "Sierra Leone": "SLE",
        "Peru": "PER", "Ecuador": "ECU", "Moldova": "MDA",
        "Cameroon": "CMR", "Venezuela": "VEN", "Italy": "ITA",
        "Senegal": "SEN", "Rwanda": "RWA", "Albania": "ALB",
    }
    for country_name, doc_count in pdip_rows:
        code = pdip_country_to_code.get(country_name, "")
        if code:
            counts[(country_name, code, "pdip")] += doc_count

    output_path = OUTPUT_DIR / "corpus_by_country.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["country_name", "country_code", "source", "doc_count"])
        for (country_name, country_code, source), count in sorted(counts.items()):
            writer.writerow([country_name, country_code, source, count])

    print(f"Wrote {len(counts)} rows to {output_path}")


def export_clause_families() -> None:
    """Export clause family annotation counts from PDIP."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        """SELECT label_family,
                  COUNT(*) as annotations,
                  COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses
           WHERE label_family IS NOT NULL
           GROUP BY label_family
           ORDER BY docs DESC"""
    ).fetchall()
    con.close()

    output_path = OUTPUT_DIR / "clause_families.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label_family", "annotations", "docs"])
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


def export_grep_candidates() -> None:
    """Export grep match candidates with context for the Shiny eval explorer."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        """SELECT d.storage_key,
                  gm.pattern_name,
                  gm.page_number,
                  gm.matched_text,
                  gm.context_before,
                  gm.context_after,
                  gm.run_id,
                  pc.country,
                  pc.document_title,
                  pc.instrument_type
           FROM grep_matches gm
           JOIN documents d ON gm.document_id = d.document_id
           LEFT JOIN (
               SELECT DISTINCT doc_id, country, document_title, instrument_type
               FROM pdip_clauses
           ) pc ON d.storage_key = 'pdip__' || pc.doc_id
           WHERE d.source = 'pdip'
           ORDER BY gm.pattern_name, pc.country, d.storage_key"""
    ).fetchall()
    con.close()

    output_path = OUTPUT_DIR / "grep_candidates.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "storage_key", "pattern_name", "page_number",
            "matched_text", "context_before", "context_after",
            "run_id", "country", "document_title", "instrument_type",
        ])
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    print("Exporting data for Quarto book and Shiny app...")
    export_corpus_by_country()
    export_clause_families()
    export_grep_candidates()
    print("Done.")
```

- [ ] **Step 4: Run the export**

```bash
uv run python3 demo/data/export_data.py
```

Expected: Three CSV files created in `demo/data/`.

- [ ] **Step 5: Spot-check the exports**

```bash
head -5 demo/data/corpus_by_country.csv
wc -l demo/data/corpus_by_country.csv
head -5 demo/data/clause_families.csv
wc -l demo/data/grep_candidates.csv
```

- [ ] **Step 6: Commit**

```bash
git add demo/chapter2.qmd demo/data/
git commit -m "feat: Chapter 2 placeholder + data export pipeline + country mapping"
```

---

## Task 5: Full Book Render + Test

**Files:**
- No new files — integration test

- [ ] **Step 1: Render the full book**

```bash
cd demo && quarto render && cd ..
```

Expected: All 4 chapters render. `demo/_book/` directory contains the full HTML site.

- [ ] **Step 2: Preview locally**

```bash
cd demo && quarto preview &
# Opens in browser — review all chapters
# Check: Mermaid diagram renders, callout boxes display, navigation works
# Kill with Ctrl+C
cd ..
```

- [ ] **Step 3: Commit any render fixes**

```bash
git add demo/
git commit -m "fix: Quarto render adjustments"
```

---

## What Happens in Branch 2 (Next Session)

Branch 2 picks up where this one leaves off. Before building visualizations, spend time exploring the corpus and improving results:

1. **Corpus exploration** — What do we actually have? Look at the NSM and EDGAR documents by country, issuer, date. What's the coverage story? Are there interesting patterns even before clause extraction?

2. **Pattern optimization** — The current grep patterns have CAC recall of 92% but pari passu only 28% and governing law 34%. Spend time looking at actual false negatives and false positives. Expand patterns. Test against PDIP ground truth. Aim for results interesting enough to show.

3. **Static visualizations** — Generate the choropleth map and clause coverage chart from the exported CSVs. Embed in Chapter 2 using plotly or matplotlib.

4. **Shiny eval explorer** — Build the Python Shiny app (dropdown + table + context + thumbs up/down). Deploy to shinyapps.io. Embed in Chapter 2 via iframe.

5. **Update Chapter 2** — Replace placeholder text with real visualizations, updated validation table, and Shiny embed.

6. **Deploy to GitHub Pages** — `quarto publish gh-pages`

---

## Self-Review Checklist

**Spec coverage (Branch 1):**
- [x] Quarto scaffold + config → Task 1
- [x] Landing page / preface → Task 1
- [x] Bibliography → Task 1
- [x] Chapter 1: narrative + flywheel diagram → Task 2
- [x] Chapter 3: flywheel concept, evals, co-design ask → Task 3
- [x] Chapter 2: placeholder for Branch 2 → Task 4
- [x] Data export pipeline → Task 4
- [x] Country mapping for NSM/EDGAR → Task 4
- [x] Full render test → Task 5

**Deferred to Branch 2:**
- [ ] Corpus exploration + pattern optimization
- [ ] Static visualizations (map, clause chart)
- [ ] Shiny eval explorer app
- [ ] Final Chapter 2 with real data
- [ ] Deployment to GitHub Pages
- [ ] Shiny deployment to shinyapps.io

**Placeholder scan:** No TBD/TODO in implementation code. Chapter 2 has intentional "coming soon" placeholders that will be filled in Branch 2.

**Type consistency:** CSV column names in export script match what Branch 2 visualization and Shiny code will expect.
