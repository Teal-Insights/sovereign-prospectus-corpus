# Roundtable Quarto Book + Shiny Eval Explorer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-chapter Quarto book with static visualizations and an embedded Shiny eval explorer app, deployed to GitHub Pages, for the #PublicDebtIsPublic Scoping Roundtable (March 30, 2026).

**Architecture:** Quarto book project in a new `demo/` directory within the existing repo. Static visualizations generated via Python scripts that export PNGs/HTML from DuckDB data. Shiny app built in R, deployed to shinyapps.io, embedded in the Quarto book via iframe. Data for the Shiny app pre-exported as CSV from DuckDB (no database at runtime).

**Tech Stack:** Quarto 1.8, R 4.5 + Shiny/bslib/DT/ggplot2, Python 3.12 (for data export), DuckDB, GitHub Pages

**Pre-flight:**
```bash
# Install R packages (one-time)
Rscript -e 'install.packages(c("shiny", "bslib", "DT", "jsonlite", "ggplot2", "sf", "rnaturalearth", "rnaturalearthdata", "dplyr", "plotly", "countrycode"), repos="https://cloud.r-project.org")'
```

**Spec:** `docs/superpowers/specs/2026-03-28-roundtable-quarto-book-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `demo/_quarto.yml` | Quarto book config (title, chapters, theme, output) |
| `demo/index.qmd` | Landing page / preface |
| `demo/chapter1.qmd` | "What We Built and Why" — narrative + flywheel diagram |
| `demo/chapter2.qmd` | "Preliminary Findings" — visualizations + Shiny embed |
| `demo/chapter3.qmd` | "A Lawyer-in-the-Loop Flywheel" — co-design ask |
| `demo/references.bib` | Bibliography (Gelpern 2019, Rivetti & Mihalyi 2025) |
| `demo/data/export_data.py` | Python script to export DuckDB data → CSV for visualizations and Shiny |
| `demo/data/corpus_by_country.csv` | Exported: country, source, document count |
| `demo/data/clause_families.csv` | Exported: label_family, annotation count, doc count |
| `demo/data/grep_candidates.csv` | Exported: grep matches with context for Shiny app |
| `demo/data/issuer_country_map.csv` | Hand-curated: issuer_name → country_code mapping |
| `demo/shiny-app/app.R` | Shiny eval explorer (single-file app) |
| `demo/shiny-app/data/` | Symlink or copy of exported CSVs for Shiny deployment |
| `demo/images/flywheel.png` | Flywheel diagram (generated or hand-drawn) |
| `.github/workflows/publish-demo.yml` | GitHub Actions to render + deploy Quarto to Pages |

### Modified Files

| File | Change |
|------|--------|
| `README.md` | Add link to demo site (optional) |

---

## Session 1: Data Export + Quarto Scaffold

### Task 1: Export Data from DuckDB to CSV

**Files:**
- Create: `demo/data/export_data.py`
- Create: `demo/data/issuer_country_map.csv`
- Output: `demo/data/corpus_by_country.csv`, `demo/data/clause_families.csv`, `demo/data/grep_candidates.csv`

- [ ] **Step 1: Create the demo directory structure**

```bash
mkdir -p demo/data demo/shiny-app/data demo/images
```

- [ ] **Step 2: Create the issuer-to-country mapping**

NSM and EDGAR manifests have `issuer_name` but no country code. The PDIP corpus has `country` in `pdip_clauses`. We need a mapping file for NSM/EDGAR issuers.

Create `demo/data/issuer_country_map.csv` with the top issuers from NSM and EDGAR manifests:

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
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data/db/corpus.duckdb"
MANIFEST_DIR = PROJECT_ROOT / "data/manifests"
OUTPUT_DIR = Path(__file__).resolve().parent
COUNTRY_MAP_PATH = OUTPUT_DIR / "issuer_country_map.csv"


def load_country_map() -> dict[str, tuple[str, str]]:
    """Load issuer pattern → (country_name, country_code) mapping."""
    mapping: dict[str, tuple[str, str]] = {}
    with COUNTRY_MAP_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["issuer_pattern"].upper()] = (
                row["country_name"],
                row["country_code"],
            )
    return mapping


def match_country(issuer_name: str, country_map: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Match an issuer name to a country using substring matching."""
    upper = issuer_name.upper()
    for pattern, country_info in country_map.items():
        if pattern in upper:
            return country_info
    return None


def export_corpus_by_country() -> None:
    """Export document counts by country and source."""
    country_map = load_country_map()

    # Count from manifests (NSM + EDGAR)
    from collections import Counter
    counts: Counter[tuple[str, str, str]] = Counter()  # (country_name, country_code, source)

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

    # Count from PDIP (pdip_clauses has country directly)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    pdip_rows = con.execute(
        """SELECT country, COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses
           WHERE country IS NOT NULL
           GROUP BY country"""
    ).fetchall()
    con.close()

    # Map PDIP country names to codes
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

    # Write CSV
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

Expected: Three CSV files created in `demo/data/`. Verify row counts look reasonable.

- [ ] **Step 5: Spot-check the exports**

```bash
head -5 demo/data/corpus_by_country.csv
wc -l demo/data/corpus_by_country.csv
head -5 demo/data/clause_families.csv
head -3 demo/data/grep_candidates.csv
wc -l demo/data/grep_candidates.csv
```

- [ ] **Step 6: Copy data for Shiny app**

```bash
cp demo/data/grep_candidates.csv demo/shiny-app/data/
cp demo/data/clause_families.csv demo/shiny-app/data/
```

- [ ] **Step 7: Commit**

```bash
git add demo/data/
git commit -m "feat: data export pipeline for Quarto book and Shiny app"
```

---

### Task 2: Quarto Book Scaffold

**Files:**
- Create: `demo/_quarto.yml`
- Create: `demo/index.qmd`
- Create: `demo/references.bib`

- [ ] **Step 1: Create Quarto config**

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

- [ ] **Step 2: Create landing page**

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

- [ ] **Step 3: Create bibliography**

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

- [ ] **Step 4: Test Quarto renders**

```bash
cd demo && quarto render index.qmd && cd ..
ls demo/_book/index.html
```

Expected: HTML file renders without errors.

- [ ] **Step 5: Commit**

```bash
git add demo/_quarto.yml demo/index.qmd demo/references.bib
git commit -m "feat: Quarto book scaffold with config and landing page"
```

---

## Session 2: Chapters 1 and 3 (Narrative)

### Task 3: Chapter 1 — "What We Built and Why"

**Files:**
- Create: `demo/chapter1.qmd`
- Create: `demo/images/flywheel.png` (or inline Mermaid/dot diagram)

- [ ] **Step 1: Create the flywheel diagram**

Use Quarto's built-in Mermaid support (no external image needed):

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

### Task 4: Chapter 3 — "A Lawyer-in-the-Loop Flywheel"

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

## Session 3: Visualizations + Chapter 2

### Task 5: Static Visualizations

**Files:**
- Create: `demo/chapter2.qmd`

Chapter 2 uses R code chunks in Quarto to generate the map and clause coverage chart inline. This keeps everything in one `.qmd` file — no separate image generation step.

- [ ] **Step 1: Create Chapter 2 with R visualizations**

Create `demo/chapter2.qmd`:

````markdown
# Preliminary Findings

::: {.callout-warning}
These are preliminary results from a one-week proof of concept. We
present them as evidence that the approach works and merits expert
methodology review — not as finished research.
:::

## The Corpus

We collected over 4,800 sovereign bond prospectuses from three public
sources. The map below shows geographic coverage — the number of
documents per country across all three sources.

```{r}
#| label: fig-map
#| fig-cap: "Sovereign bond prospectuses collected from SEC EDGAR, FCA NSM, and #PublicDebtIsPublic"
#| fig-height: 5
#| fig-width: 9
#| message: false
#| warning: false

library(dplyr)
library(ggplot2)
library(sf)
library(rnaturalearth)
library(countrycode)

corpus <- read.csv("data/corpus_by_country.csv")

# Aggregate across sources
by_country <- corpus |>
  group_by(country_code, country_name) |>
  summarise(total_docs = sum(doc_count), .groups = "drop")

# Get world map
world <- ne_countries(scale = "medium", returnclass = "sf") |>
  select(iso_a3, name, geometry)

# Join
map_data <- world |>
  left_join(by_country, by = c("iso_a3" = "country_code"))

ggplot(map_data) +
  geom_sf(aes(fill = total_docs), color = "grey80", linewidth = 0.1) +
  scale_fill_gradient(
    low = "#e8f4f8", high = "#1a5276",
    na.value = "#f5f5f5",
    name = "Documents",
    breaks = c(1, 50, 200, 500, 1000),
    trans = "log1p"
  ) +
  theme_minimal() +
  theme(
    legend.position = "bottom",
    panel.grid = element_blank(),
    axis.text = element_blank(),
    axis.title = element_blank(),
    plot.title = element_text(size = 14, face = "bold"),
    plot.subtitle = element_text(size = 11, color = "grey40")
  ) +
  labs(
    title = "4,800+ Sovereign Bond Prospectuses from 3 Public Sources",
    subtitle = "SEC EDGAR · FCA National Storage Mechanism · #PublicDebtIsPublic"
  )
```

## What #PublicDebtIsPublic Annotations Reveal

The #PublicDebtIsPublic corpus contains 122 documents with over 6,200
expert clause annotations across 25 clause families. The chart below
shows how many documents contain annotations for each family.

```{r}
#| label: fig-families
#| fig-cap: "Clause family coverage in #PublicDebtIsPublic expert-annotated corpus (122 documents)"
#| fig-height: 6
#| fig-width: 8
#| message: false

families <- read.csv("data/clause_families.csv")

# Show top 15 families
top_families <- families |>
  slice_max(docs, n = 15) |>
  mutate(
    label_clean = gsub("_", " ", label_family) |> tools::toTitleCase(),
    label_clean = factor(label_clean, levels = rev(label_clean))
  )

ggplot(top_families, aes(x = docs, y = label_clean)) +
  geom_col(fill = "#2c7bb6", alpha = 0.85) +
  geom_text(aes(label = docs), hjust = -0.3, size = 3.5) +
  theme_minimal() +
  theme(
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    plot.title = element_text(size = 13, face = "bold")
  ) +
  labs(
    title = "Expert-Annotated Clause Families",
    subtitle = "Number of documents containing each clause family",
    x = "Documents",
    y = NULL
  ) +
  xlim(0, max(top_families$docs) * 1.15)
```

## Retrieval Validation

Using patterns derived from #PublicDebtIsPublic annotations, we searched
the full PDIP corpus for three key clause families. The table below
shows how our automated retrieval compares against the expert
annotations.

| Clause Family | Expert-Annotated Docs | Retrieved Docs | Recall | Notes |
|:---|:---:|:---:|:---:|:---|
| Collective Action | 37 | 177 | 92% | High recall; many candidates in unannotated docs need review |
| Pari Passu | 29 | 162 | 28% | Pattern needs expansion; many phrasing variants |
| Governing Law | 71 | 130 | 34% | Currently matches NY/English law only |

: Retrieval performance against #PublicDebtIsPublic expert annotations (preliminary) {#tbl-validation}

**Reading this table:** High recall means we're finding most of the
clauses that experts annotated. The "Retrieved Docs" column is larger
than "Expert-Annotated Docs" because the retrieval runs across all 823
#PublicDebtIsPublic documents, while expert annotations cover 122
documents. Retrieved matches in unannotated documents are candidates
for expert review — which is exactly the point of the flywheel.

## Try It Yourself: The Eval Explorer

The interactive explorer below lets you browse clause candidates from
the corpus. Pick a clause family, click through the matches, and see
what a reviewer's experience would look like.

<iframe
  src="https://tealinsights.shinyapps.io/clause-eval-explorer/"
  width="100%"
  height="700px"
  style="border: 1px solid #ddd; border-radius: 4px;"
></iframe>

*If the interactive explorer doesn't load, visit it directly at
[tealinsights.shinyapps.io/clause-eval-explorer](https://tealinsights.shinyapps.io/clause-eval-explorer/).*
````

Note: The validation table numbers will need to be updated after re-running grep with the latest code. The current numbers are from the most recent validation run.

- [ ] **Step 2: Test render (may fail on Shiny iframe — that's expected)**

```bash
cd demo && quarto render chapter2.qmd && cd ..
```

Expected: Renders with map and bar chart. Iframe will show empty box until Shiny app is deployed.

- [ ] **Step 3: Commit**

```bash
git add demo/chapter2.qmd
git commit -m "feat: Chapter 2 — map, clause coverage chart, validation table"
```

---

## Session 4: Shiny Eval Explorer

### Task 6: Build the Shiny App

**Files:**
- Create: `demo/shiny-app/app.R`

- [ ] **Step 1: Install R packages (if not already done)**

```bash
Rscript -e 'install.packages(c("shiny", "bslib", "DT", "dplyr", "jsonlite"), repos="https://cloud.r-project.org")'
```

- [ ] **Step 2: Create the Shiny app**

Create `demo/shiny-app/app.R`:

```r
library(shiny)
library(bslib)
library(DT)
library(dplyr)

# ── Load data ──────────────────────────────────────────────────────
candidates <- read.csv("data/grep_candidates.csv",
                        stringsAsFactors = FALSE,
                        na.strings = c("", "NA"))

# Clean up pattern names for display
candidates <- candidates |>
  mutate(
    family = case_when(
      pattern_name == "collective_action" ~ "Collective Action",
      pattern_name == "pari_passu" ~ "Pari Passu",
      pattern_name == "feature__governing_law" ~ "Governing Law",
      TRUE ~ pattern_name
    ),
    country = ifelse(is.na(country), "Unknown", country),
    document_title = ifelse(is.na(document_title), storage_key, document_title),
    page_display = paste("p.", page_number)
  )

# Feedback log file
feedback_file <- "feedback_log.csv"
if (!file.exists(feedback_file)) {
  write.csv(
    data.frame(
      storage_key = character(),
      family = character(),
      matched_text = character(),
      decision = character(),
      reason = character(),
      timestamp = character(),
      stringsAsFactors = FALSE
    ),
    feedback_file,
    row.names = FALSE
  )
}

# ── UI ─────────────────────────────────────────────────────────────
ui <- page_sidebar(
  title = "Clause Eval Explorer",
  theme = bs_theme(bootswatch = "flatly"),

  sidebar = sidebar(
    width = 300,
    selectInput("family", "Clause Family",
                choices = sort(unique(candidates$family)),
                selected = "Collective Action"),
    hr(),
    p("Browse clause candidates identified by automated
      retrieval. Click a row to see full context."),
    p(tags$strong("Try it:"), "Would you mark each candidate as a
      real clause (thumbs up) or not (thumbs down)?"),
    hr(),
    p(class = "text-muted small",
      "Proof of concept for the #PublicDebtIsPublic roundtable.",
      tags$br(),
      "Findings are preliminary.")
  ),

  layout_columns(
    col_widths = c(12),

    card(
      card_header("Candidates"),
      DTOutput("candidates_table")
    ),

    card(
      card_header(
        class = "d-flex justify-content-between align-items-center",
        span("Context"),
        span(
          actionButton("thumbs_up", "", icon = icon("thumbs-up"),
                       class = "btn-success btn-sm me-1"),
          actionButton("thumbs_down", "", icon = icon("thumbs-down"),
                       class = "btn-danger btn-sm me-1"),
          textInput("reason", NULL, placeholder = "Why not? (optional)",
                    width = "250px") |>
            tagAppendAttributes(style = "display:inline-block; margin:0;")
        )
      ),
      uiOutput("context_display")
    )
  )
)

# ── Server ─────────────────────────────────────────────────────────
server <- function(input, output, session) {

  filtered <- reactive({
    candidates |>
      filter(family == input$family) |>
      select(country, document_title, page_display,
             matched_text, context_before, context_after,
             storage_key, pattern_name)
  })

  output$candidates_table <- renderDT({
    df <- filtered() |>
      select(Country = country,
             Document = document_title,
             Page = page_display,
             Match = matched_text)

    datatable(df,
              selection = "single",
              options = list(
                pageLength = 10,
                scrollX = TRUE,
                columnDefs = list(
                  list(targets = 3, width = "300px",
                       render = JS(
                         "function(data, type, row) {",
                         "  if (type === 'display' && data && data.length > 80) {",
                         "    return data.substr(0, 80) + '...';",
                         "  }",
                         "  return data;",
                         "}"
                       ))
                )
              ),
              rownames = FALSE)
  })

  selected_row <- reactive({
    idx <- input$candidates_table_rows_selected
    if (is.null(idx)) return(NULL)
    filtered()[idx, ]
  })

  output$context_display <- renderUI({
    row <- selected_row()
    if (is.null(row)) {
      return(p(class = "text-muted", "Click a row above to see the full context."))
    }

    ctx_before <- gsub("\n", "<br/>", row$context_before)
    matched <- gsub("\n", "<br/>", row$matched_text)
    ctx_after <- gsub("\n", "<br/>", row$context_after)

    tags$div(
      style = "font-family: 'Georgia', serif; font-size: 14px; line-height: 1.6;",
      tags$p(
        style = "color: #666;",
        HTML(ctx_before)
      ),
      tags$p(
        style = "background-color: #fff3cd; padding: 8px 12px; border-left: 4px solid #ffc107; font-weight: bold;",
        HTML(matched)
      ),
      tags$p(
        style = "color: #666;",
        HTML(ctx_after)
      ),
      tags$hr(),
      tags$small(
        class = "text-muted",
        paste0(row$storage_key, " · ", row$page_display,
               " · Pattern: ", row$pattern_name)
      )
    )
  })

  # Feedback handlers
  log_feedback <- function(decision) {
    row <- selected_row()
    if (is.null(row)) return()

    entry <- data.frame(
      storage_key = row$storage_key,
      family = input$family,
      matched_text = substr(row$matched_text, 1, 200),
      decision = decision,
      reason = input$reason,
      timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%S"),
      stringsAsFactors = FALSE
    )
    write.table(entry, feedback_file, append = TRUE,
                sep = ",", row.names = FALSE, col.names = FALSE)

    showNotification(
      paste0(ifelse(decision == "yes", "\U1F44D", "\U1F44E"),
             " Recorded for ", row$storage_key),
      type = ifelse(decision == "yes", "message", "warning"),
      duration = 2
    )
    updateTextInput(session, "reason", value = "")
  }

  observeEvent(input$thumbs_up, log_feedback("yes"))
  observeEvent(input$thumbs_down, log_feedback("no"))
}

shinyApp(ui, server)
```

- [ ] **Step 3: Test locally**

```bash
cd demo/shiny-app && Rscript -e 'shiny::runApp(".", port=3838, launch.browser=TRUE)' &
# Open http://localhost:3838 in browser
# Test: select each family, click rows, try thumbs up/down
# Kill with: kill %1
cd ../..
```

- [ ] **Step 4: Commit**

```bash
git add demo/shiny-app/
git commit -m "feat: Shiny eval explorer — clause candidate browser with feedback"
```

---

### Task 7: Deploy Shiny App to shinyapps.io

**Files:**
- No new files — deployment step

- [ ] **Step 1: Install rsconnect**

```bash
Rscript -e 'install.packages("rsconnect", repos="https://cloud.r-project.org")'
```

- [ ] **Step 2: Configure shinyapps.io account**

```bash
# Get token from https://www.shinyapps.io/admin/#/tokens
Rscript -e 'rsconnect::setAccountInfo(name="tealinsights", token="YOUR_TOKEN", secret="YOUR_SECRET")'
```

Note: If you don't have a shinyapps.io account, create one at https://www.shinyapps.io/. The free tier allows 5 apps and 25 active hours/month — more than enough for a demo.

- [ ] **Step 3: Deploy**

```bash
Rscript -e 'rsconnect::deployApp("demo/shiny-app", appName="clause-eval-explorer", account="tealinsights")'
```

Expected: App deploys to `https://tealinsights.shinyapps.io/clause-eval-explorer/`

- [ ] **Step 4: Verify the deployed app**

Open `https://tealinsights.shinyapps.io/clause-eval-explorer/` in browser. Test all three clause families. Verify context display and feedback buttons work.

- [ ] **Step 5: Update Chapter 2 iframe URL if needed**

If the deployed URL differs from the one in `chapter2.qmd`, update the `src` attribute in the iframe tag.

---

## Session 5: Full Render + Deploy

### Task 8: Render Full Book + Deploy to GitHub Pages

**Files:**
- Create: `.github/workflows/publish-demo.yml` (optional — can also deploy manually)

- [ ] **Step 1: Install remaining R packages for rendering**

```bash
Rscript -e 'install.packages(c("sf", "rnaturalearth", "rnaturalearthdata", "countrycode"), repos="https://cloud.r-project.org")'
```

- [ ] **Step 2: Render the full book**

```bash
cd demo && quarto render && cd ..
```

Expected: All 4 chapters render. `demo/_book/` directory contains the full HTML site.

- [ ] **Step 3: Preview locally**

```bash
cd demo && quarto preview &
# Opens in browser at http://localhost:PORT
# Review all chapters, check map, chart, iframe
# Kill with Ctrl+C
cd ..
```

- [ ] **Step 4: Deploy to GitHub Pages**

Option A — manual (simplest):

```bash
cd demo && quarto publish gh-pages --no-prompt && cd ..
```

Option B — if that doesn't work or you want a separate repo:

```bash
# Create a new repo for the demo
gh repo create Teal-Insights/sovereign-clause-corpus-demo --public
# Push _book contents there
cd demo/_book
git init
git add .
git commit -m "Deploy Quarto book"
git remote add origin https://github.com/Teal-Insights/sovereign-clause-corpus-demo.git
git push -u origin main
# Enable Pages in repo settings → Source: main branch, / (root)
cd ../..
```

- [ ] **Step 5: Verify deployed site**

Open the GitHub Pages URL. Test:
- [ ] All 3 chapters load
- [ ] Map renders with country shading
- [ ] Clause family bar chart renders
- [ ] Shiny iframe loads and is interactive
- [ ] Works on mobile (test on phone)
- [ ] Mermaid flywheel diagram renders

- [ ] **Step 6: Commit any final adjustments**

```bash
git add demo/ .github/
git commit -m "feat: full Quarto book rendered and deployed to GitHub Pages"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Chapter 1: narrative + flywheel diagram → Task 3
- [x] Chapter 2: choropleth map → Task 5
- [x] Chapter 2: clause family bar chart → Task 5
- [x] Chapter 2: validation table → Task 5
- [x] Chapter 2: Shiny eval explorer embed → Task 5 + 6
- [x] Chapter 3: flywheel concept, evals, co-design ask → Task 4
- [x] Shiny app: dropdown + table + context + thumbs up/down + feedback log → Task 6
- [x] Data export from DuckDB → Task 1
- [x] Country mapping for NSM/EDGAR → Task 1
- [x] Deployment to GitHub Pages → Task 8
- [x] Shiny deployment to shinyapps.io → Task 7
- [x] Bibliography → Task 2
- [x] "Proud but humble" tone throughout → Tasks 3, 4, 5

**Placeholder scan:** No TBD, TODO, or "implement later" found. Validation table numbers may need updating after re-running grep — noted in Task 5.

**Type consistency:** CSV column names match between export script (Task 1) and R code (Tasks 5, 6). Pattern names (`collective_action`, `pari_passu`, `feature__governing_law`) used consistently.
