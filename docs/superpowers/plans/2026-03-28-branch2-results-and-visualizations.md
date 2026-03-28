# Branch 2: Results Optimization + Visualizations + Shiny App

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the full corpus, optimize grep patterns, build static visualizations and a Python Shiny eval explorer, finalize Chapter 2 of the Quarto book, and deploy to GitHub Pages.

**Architecture:** Parse EDGAR (3,217 HTM/TXT) and NSM (645 PDF) documents, bootstrap all into `documents` table, run grep across full corpus, analyze false positives/negatives, improve patterns, then build visualizations and Shiny app from the improved data. All visualization data pre-exported as CSV.

**Tech Stack:** Python 3.12, uv, DuckDB, Shiny for Python, plotly, Quarto 1.8, GitHub Pages

**Pre-flight:**
```bash
# Ensure on the right branch
git checkout feature/26-roundtable-quarto-book

# Install Python Shiny + plotly
uv add shiny htmltools plotly

# Verify EDGAR/NSM data exists
ls data/manifests/edgar_manifest.jsonl data/manifests/nsm_manifest.jsonl
ls data/original/ | head -5
```

**Context:** Branch 1 created the Quarto book scaffold with narrative chapters 1 and 3 (final), chapter 2 (placeholder), and a data export pipeline. This plan fills in Chapter 2 with real visualizations and the Shiny eval explorer.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `demo/shiny-app/app.py` | Shiny for Python eval explorer |
| `demo/shiny-app/requirements.txt` | Shiny app dependencies for deployment |

### Modified Files

| File | Change |
|------|--------|
| `demo/chapter2.qmd` | Replace placeholder with real visualizations + Shiny embed |
| `demo/data/export_data.py` | Re-run to update CSVs with full corpus data |
| `src/corpus/extraction/clause_patterns.py` | Improved patterns based on FP/FN analysis |
| `tests/test_clause_patterns.py` | Tests for new pattern variants |

---

## Session 1: Full Corpus Parse + Bootstrap

### Task 1: Parse Full EDGAR + NSM Corpus

**Files:**
- No new files — operational task using existing CLI

- [ ] **Step 1: Bootstrap EDGAR documents into `documents` table**

```bash
uv run python3 -c "
import duckdb, json
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')
manifest = Path('data/manifests/edgar_manifest.jsonl')

inserted = 0
skipped = 0
with manifest.open() as f:
    for line in f:
        r = json.loads(line)
        storage_key = r['storage_key']
        existing = con.execute('SELECT 1 FROM documents WHERE storage_key = ?', [storage_key]).fetchone()
        if existing:
            skipped += 1
            continue
        con.execute('''
            INSERT INTO documents (source, native_id, storage_key, title, issuer_name,
                                  file_path, is_sovereign, issuer_type, scope_status)
            VALUES ('edgar', ?, ?, ?, ?, ?, true, 'sovereign', 'in_scope')
        ''', [r.get('native_id'), storage_key, r.get('title'), r.get('issuer_name'), r.get('file_path')])
        inserted += 1

con.commit()
print(f'EDGAR: inserted {inserted}, skipped {skipped}')
con.close()
"
```

- [ ] **Step 2: Bootstrap NSM documents into `documents` table**

```bash
uv run python3 -c "
import duckdb, json
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')
manifest = Path('data/manifests/nsm_manifest.jsonl')

inserted = 0
skipped = 0
with manifest.open() as f:
    for line in f:
        r = json.loads(line)
        storage_key = r['storage_key']
        existing = con.execute('SELECT 1 FROM documents WHERE storage_key = ?', [storage_key]).fetchone()
        if existing:
            skipped += 1
            continue
        con.execute('''
            INSERT INTO documents (source, native_id, storage_key, title, issuer_name,
                                  file_path, is_sovereign, issuer_type, scope_status)
            VALUES ('nsm', ?, ?, ?, ?, ?, true, 'sovereign', 'in_scope')
        ''', [r.get('native_id'), storage_key, r.get('title'), r.get('issuer_name'), r.get('file_path')])
        inserted += 1

con.commit()
print(f'NSM: inserted {inserted}, skipped {skipped}')
con.close()
"
```

- [ ] **Step 3: Verify document counts**

```bash
uv run python3 -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb', read_only=True)
for r in con.execute('SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY source').fetchall():
    print(f'  {r[0]}: {r[1]}')
total = con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
print(f'  TOTAL: {total}')
con.close()
"
```

Expected: ~823 PDIP + ~3,301 EDGAR + ~645 NSM = ~4,769 total.

- [ ] **Step 4: Parse EDGAR corpus**

```bash
uv run corpus parse run --run-id parse-edgar-full --source edgar
```

Expected: ~3,217 parsed (2,942 HTM + 275 TXT), ~84 failed (.paper files unsupported). Takes 10-20 minutes.

- [ ] **Step 5: Parse NSM corpus**

```bash
uv run corpus parse run --run-id parse-nsm-full --source nsm
```

Expected: ~645 PDFs parsed. Takes 5-10 minutes.

- [ ] **Step 6: Verify parse counts**

```bash
ls data/parsed/ | wc -l
ls data/parsed/edgar__* 2>/dev/null | wc -l
ls data/parsed/nsm__* 2>/dev/null | wc -l
ls data/parsed/pdip__* 2>/dev/null | wc -l
```

Expected: ~4,600+ total parsed files.

- [ ] **Step 7: Commit (empty — no code changes, data is gitignored)**

```bash
git commit --allow-empty -m "ops: parsed full EDGAR + NSM corpus (~4,600 documents)"
```

---

### Task 2: Run Grep Across Full Corpus + Re-run Validation

**Files:**
- No new files — operational task

- [ ] **Step 1: Run grep across full corpus**

```bash
uv run corpus grep run --run-id grep-full-v2
```

Expected: Significantly more matches than before (was 3,882 from PDIP-only). Now scanning ~4,600 documents.

- [ ] **Step 2: Re-run validation with corrected code**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.validate import load_pdip_presence, load_grep_presence, compute_validation_report
import json

pdip = load_pdip_presence(Path('data/pdip/clause_annotations.jsonl'))
grep = load_grep_presence(db_path=Path('data/db/corpus.duckdb'), run_id='grep-full-v2')

report = compute_validation_report(pdip, grep)

# Show key families
for fam in ['collective_action', 'pari_passu', 'governing_law']:
    d = report['families'].get(fam, {})
    print(f'{fam}: recall={d.get(\"recall\",0)}, precision={d.get(\"precision\",0)}, TP={d[\"true_positives\"]}, FP={d[\"false_positives\"]}, FN={d[\"false_negatives\"]}')

# Save
Path('data/output').mkdir(parents=True, exist_ok=True)
with open('data/output/validation_report.json', 'w') as f:
    json.dump(report, f, indent=2)
print('Saved validation report')
"
```

- [ ] **Step 3: Examine false negatives for key families**

```bash
uv run python3 -c "
import json, duckdb
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb', read_only=True)

# Find PDIP docs with CAC annotations but no grep match
pdip_cac_docs = set()
with Path('data/pdip/clause_annotations.jsonl').open() as f:
    for line in f:
        r = json.loads(line)
        if r.get('label_family') == 'collective_action':
            pdip_cac_docs.add(r['doc_id'])

grep_cac_docs = set()
for row in con.execute('''
    SELECT DISTINCT d.storage_key FROM grep_matches gm
    JOIN documents d ON gm.document_id = d.document_id
    WHERE gm.pattern_name = 'collective_action' AND gm.run_id = 'grep-full-v2'
''').fetchall():
    grep_cac_docs.add(row[0])

fn_docs = pdip_cac_docs - {sk.replace('pdip__','') for sk in grep_cac_docs}
print(f'CAC false negatives ({len(fn_docs)} docs):')
for doc_id in sorted(fn_docs):
    # Show what text the annotation has
    with Path('data/pdip/clause_annotations.jsonl').open() as f:
        for line in f:
            r = json.loads(line)
            if r['doc_id'] == doc_id and r.get('label_family') == 'collective_action' and r.get('text'):
                print(f'  [{doc_id}] {r[\"text\"][:150]}...')
                break

con.close()
"
```

Review the false negative texts. Note any phrasing variants not captured by current patterns.

- [ ] **Step 4: Examine sample false positives**

```bash
uv run python3 -c "
import duckdb

con = duckdb.connect('data/db/corpus.duckdb', read_only=True)

# Sample FPs: docs with grep CAC match but no PDIP annotation
# (Only meaningful for PDIP docs — non-PDIP docs are unlabeled, not FPs)
rows = con.execute('''
    SELECT d.storage_key, gm.matched_text, gm.context_before, gm.context_after, gm.page_number
    FROM grep_matches gm
    JOIN documents d ON gm.document_id = d.document_id
    WHERE gm.pattern_name = 'collective_action'
      AND d.source = 'pdip'
      AND gm.run_id = 'grep-full-v2'
    LIMIT 20
''').fetchall()

for sk, matched, before, after, page in rows:
    print(f'[{sk} p.{page}] {matched}')
    print(f'  BEFORE: ...{before[-100:]}')
    print(f'  AFTER:  {after[:100]}...')
    print()

con.close()
"
```

Review the false positives. Note which pattern alternatives are too broad.

- [ ] **Step 5: Document findings**

Write brief notes about what you observed:
- Which FN texts use phrasing not in current patterns?
- Which FP matches are caused by overly broad patterns?
- What pattern changes would improve results?

---

### Task 3: Improve Grep Patterns

**Files:**
- Modify: `src/corpus/extraction/clause_patterns.py`
- Modify: `tests/test_clause_patterns.py`

Based on the FP/FN analysis in Task 2, update the patterns. The specific changes will depend on what the analysis reveals, but here is the framework:

- [ ] **Step 1: Add tests for new pattern variants**

Add tests to `tests/test_clause_patterns.py` for any new phrasing variants discovered in the FN analysis. For example, if "meetings of noteholders" appears in FN texts:

```python
def test_cac_pattern_matches_meetings_of_noteholders() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "meetings of the Noteholders may be convened"
    assert p.finder.search(text) is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_clause_patterns.py -v
```

- [ ] **Step 3: Update patterns in `clause_patterns.py`**

Likely additions based on issue #25 suggestions and FN analysis:

For `collective_action`:
- Add: `meeting(?:s)?\s+of\s+(?:the\s+)?(?:note|bond)holders`
- Consider tightening `modification\s+of\s+(?:the\s+)?terms` by requiring follow-on context

For `pari_passu`:
- Add: `rank\s+without\s+(?:any\s+)?preference\s+among\s+themselves`
- Add: `unsecured\s+and\s+unsubordinated\s+(?:public\s+)?(?:external\s+)?(?:indebtedness|obligations)`

For `feature__governing_law`:
- Add: `laws?\s+of\s+England\s+and\s+Wales`
- Add bare: `governing\s+law` as a broader catch-all

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_clause_patterns.py -v
```

- [ ] **Step 5: Run full checks**

```bash
uv run ruff check src/corpus/extraction/clause_patterns.py tests/test_clause_patterns.py
uv run pyright src/corpus/extraction/
```

- [ ] **Step 6: Re-run grep with improved patterns**

```bash
uv run corpus grep run --run-id grep-improved
```

- [ ] **Step 7: Re-run validation**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.validate import load_pdip_presence, load_grep_presence, compute_validation_report
import json

pdip = load_pdip_presence(Path('data/pdip/clause_annotations.jsonl'))
grep = load_grep_presence(db_path=Path('data/db/corpus.duckdb'), run_id='grep-improved')
report = compute_validation_report(pdip, grep)

for fam in ['collective_action', 'pari_passu', 'governing_law']:
    d = report['families'].get(fam, {})
    print(f'{fam}: recall={d.get(\"recall\",0)}, precision={d.get(\"precision\",0)}, TP={d[\"true_positives\"]}, FP={d[\"false_positives\"]}, FN={d[\"false_negatives\"]}')

with open('data/output/validation_report.json', 'w') as f:
    json.dump(report, f, indent=2)
"
```

Compare with pre-improvement numbers. If significantly better, proceed. If not, iterate.

- [ ] **Step 8: Commit**

```bash
git add src/corpus/extraction/clause_patterns.py tests/test_clause_patterns.py
git commit -m "feat: improved clause patterns based on FP/FN analysis"
```

---

## Session 2: Visualizations + Shiny App

### Task 4: Re-export Data with Full Corpus

**Files:**
- Modify: `demo/data/export_data.py` (re-run, not modify)

- [ ] **Step 1: Re-run data export with full corpus**

```bash
uv run python3 demo/data/export_data.py
```

- [ ] **Step 2: Verify coverage**

```bash
uv run python3 -c "
import csv
from collections import Counter

with open('demo/data/corpus_by_country.csv') as f:
    reader = csv.DictReader(f)
    countries = set()
    total = 0
    for row in reader:
        countries.add(row['country_code'])
        total += int(row['doc_count'])
print(f'Countries: {len(countries)}')
print(f'Total documents mapped: {total}')
"
```

Expected: 30+ countries, 4,000+ documents mapped.

- [ ] **Step 3: Copy updated data to Shiny app**

```bash
cp demo/data/grep_candidates.csv demo/shiny-app/data/
cp demo/data/clause_families.csv demo/shiny-app/data/
```

- [ ] **Step 4: Commit**

```bash
git add demo/data/
git commit -m "feat: re-export data with full corpus coverage"
```

---

### Task 5: Build Python Shiny Eval Explorer

**Files:**
- Create: `demo/shiny-app/app.py`
- Create: `demo/shiny-app/requirements.txt`

- [ ] **Step 1: Install Shiny for Python**

```bash
uv add shiny htmltools
```

- [ ] **Step 2: Create requirements.txt for deployment**

Create `demo/shiny-app/requirements.txt`:

```
shiny
htmltools
pandas
```

- [ ] **Step 3: Create the Shiny app**

Create `demo/shiny-app/app.py`:

```python
"""Clause Eval Explorer — Shiny for Python.

Interactive app for browsing clause candidates identified by automated
retrieval. Users can review candidates (yes/no) and provide feedback.
"""

from __future__ import annotations

import csv
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
from htmltools import Tag, tags
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

# ── Load data ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"

candidates_df = pd.read_csv(DATA_DIR / "grep_candidates.csv", na_values=["", "NA"])

# Clean up for display
FAMILY_LABELS = {
    "collective_action": "Collective Action (CAC)",
    "pari_passu": "Pari Passu",
    "feature__governing_law": "Governing Law",
}

candidates_df["family_label"] = candidates_df["pattern_name"].map(
    lambda x: FAMILY_LABELS.get(x, x)
)
candidates_df["country"] = candidates_df["country"].fillna("Unknown")
candidates_df["document_title"] = candidates_df["document_title"].fillna(
    candidates_df["storage_key"]
)
candidates_df["page_display"] = "p. " + candidates_df["page_number"].astype(str)

# Feedback log
FEEDBACK_PATH = DATA_DIR / "feedback_log.csv"
if not FEEDBACK_PATH.exists():
    with FEEDBACK_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "storage_key", "family", "matched_text",
            "decision", "reason", "timestamp",
        ])

# ── UI ─────────────────────────────────────────────────────────────
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select(
            "family",
            "Clause Family",
            choices={v: v for v in sorted(candidates_df["family_label"].unique())},
        ),
        ui.hr(),
        ui.p("Browse clause candidates identified by automated retrieval. "
             "Click a row to see full context."),
        ui.p(
            ui.strong("Try it:"),
            " Would you mark each candidate as a real clause "
            "(thumbs up) or not (thumbs down)?",
        ),
        ui.hr(),
        ui.p(
            "Proof of concept for the #PublicDebtIsPublic roundtable.",
            ui.br(),
            "Findings are preliminary.",
            class_="text-muted small",
        ),
        width=300,
    ),
    ui.card(
        ui.card_header("Candidates"),
        ui.output_data_frame("candidates_table"),
    ),
    ui.card(
        ui.card_header(
            ui.div(
                ui.span("Context"),
                ui.span(
                    ui.input_action_button(
                        "thumbs_up", "", icon=ui.tags.i(class_="bi bi-hand-thumbs-up-fill"),
                        class_="btn btn-success btn-sm me-1",
                    ),
                    ui.input_action_button(
                        "thumbs_down", "", icon=ui.tags.i(class_="bi bi-hand-thumbs-down-fill"),
                        class_="btn btn-danger btn-sm me-1",
                    ),
                    ui.input_text(
                        "reason", None, placeholder="Why not? (optional)", width="250px",
                    ),
                ),
                class_="d-flex justify-content-between align-items-center",
            )
        ),
        ui.output_ui("context_display"),
    ),
    title="Clause Eval Explorer",
    fillable=True,
)


# ── Server ─────────────────────────────────────────────────────────
def server(input: Inputs, output: Outputs, session: Session) -> None:

    @reactive.calc
    def filtered() -> pd.DataFrame:
        return candidates_df[
            candidates_df["family_label"] == input.family()
        ].reset_index(drop=True)

    @render.data_frame
    def candidates_table():
        df = filtered()[["country", "document_title", "page_display", "matched_text"]].copy()
        df.columns = ["Country", "Document", "Page", "Match"]
        # Truncate matched text for table display
        df["Match"] = df["Match"].str[:80] + "..."
        return render.DataTable(df, selection_mode="row", height="300px")

    @reactive.calc
    def selected_row() -> pd.Series | None:
        idx = candidates_table.cell_selection()
        if idx is None or "rows" not in idx or not idx["rows"]:
            return None
        row_idx = idx["rows"][0]
        return filtered().iloc[row_idx]

    @render.ui
    def context_display() -> Tag:
        row = selected_row()
        if row is None:
            return ui.p("Click a row above to see the full context.", class_="text-muted")

        ctx_before = str(row.get("context_before", "") or "")
        matched = str(row.get("matched_text", "") or "")
        ctx_after = str(row.get("context_after", "") or "")

        return tags.div(
            tags.p(
                ui.HTML(ctx_before.replace("\n", "<br/>")),
                style="color: #666; font-family: Georgia, serif; font-size: 14px; line-height: 1.6;",
            ),
            tags.p(
                ui.HTML(matched.replace("\n", "<br/>")),
                style="background-color: #fff3cd; padding: 8px 12px; border-left: 4px solid #ffc107; font-weight: bold; font-family: Georgia, serif; font-size: 14px;",
            ),
            tags.p(
                ui.HTML(ctx_after.replace("\n", "<br/>")),
                style="color: #666; font-family: Georgia, serif; font-size: 14px; line-height: 1.6;",
            ),
            tags.hr(),
            tags.small(
                f"{row['storage_key']} · p. {row['page_number']} · Pattern: {row['pattern_name']}",
                class_="text-muted",
            ),
        )

    def log_feedback(decision: str) -> None:
        row = selected_row()
        if row is None:
            return
        with FEEDBACK_PATH.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                row["storage_key"],
                input.family(),
                str(row.get("matched_text", ""))[:200],
                decision,
                input.reason(),
                datetime.now(UTC).isoformat(),
            ])
        ui.notification_show(
            f"{'👍' if decision == 'yes' else '👎'} Recorded for {row['storage_key']}",
            type="message" if decision == "yes" else "warning",
            duration=2,
        )
        ui.update_text("reason", value="")

    @reactive.effect
    @reactive.event(input.thumbs_up)
    def _on_thumbs_up():
        log_feedback("yes")

    @reactive.effect
    @reactive.event(input.thumbs_down)
    def _on_thumbs_down():
        log_feedback("no")


app = App(app_ui, server)
```

- [ ] **Step 4: Test locally**

```bash
cd demo/shiny-app && uv run shiny run app.py --port 3838 &
# Open http://localhost:3838 in browser
# Test: select each family, click rows, try thumbs up/down
# Kill with: kill %1
cd ../..
```

- [ ] **Step 5: Commit**

```bash
git add demo/shiny-app/
git commit -m "feat: Python Shiny eval explorer with feedback logging"
```

---

### Task 6: Finalize Chapter 2 with Visualizations

**Files:**
- Modify: `demo/chapter2.qmd`

- [ ] **Step 1: Update Chapter 2 with Python visualizations**

Replace `demo/chapter2.qmd` with the final version. Uses Python code chunks for plotly visualizations:

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

```{python}
#| label: fig-map
#| fig-cap: "Sovereign bond prospectuses collected from SEC EDGAR, FCA NSM, and #PublicDebtIsPublic"

import pandas as pd
import plotly.express as px

corpus = pd.read_csv("data/corpus_by_country.csv")
by_country = corpus.groupby(["country_code", "country_name"])["doc_count"].sum().reset_index()

fig = px.choropleth(
    by_country,
    locations="country_code",
    color="doc_count",
    hover_name="country_name",
    hover_data={"doc_count": True, "country_code": False},
    color_continuous_scale="Blues",
    labels={"doc_count": "Documents"},
    title="4,800+ Sovereign Bond Prospectuses from 3 Public Sources",
)
fig.update_layout(
    geo=dict(showframe=False, showcoastlines=True, projection_type="natural earth"),
    margin=dict(l=0, r=0, t=40, b=0),
    coloraxis_colorbar=dict(title="Documents"),
    height=450,
)
fig.show()
```

## What #PublicDebtIsPublic Annotations Reveal

The #PublicDebtIsPublic corpus contains 122 documents with over 6,200
expert clause annotations across 25 clause families. The chart below
shows how many documents contain annotations for each family.

```{python}
#| label: fig-families
#| fig-cap: "Clause family coverage in #PublicDebtIsPublic expert-annotated corpus (122 documents)"

families = pd.read_csv("data/clause_families.csv")
top = families.head(15).copy()
top["label_clean"] = top["label_family"].str.replace("_", " ").str.title()

fig = px.bar(
    top.sort_values("docs"),
    x="docs",
    y="label_clean",
    orientation="h",
    labels={"docs": "Documents", "label_clean": ""},
    title="Expert-Annotated Clause Families",
    text="docs",
)
fig.update_layout(
    height=500,
    margin=dict(l=0, r=20, t=40, b=0),
    showlegend=False,
    yaxis=dict(tickfont=dict(size=12)),
)
fig.update_traces(marker_color="#2c7bb6", textposition="outside")
fig.show()
```

## Retrieval Validation

Using patterns derived from #PublicDebtIsPublic annotations, we searched
the full corpus for three key clause families. The table below shows
how our automated retrieval compares against the expert annotations.

| Clause Family | Expert Docs | Retrieved | Recall | Notes |
|:---|:---:|:---:|:---:|:---|
| Collective Action | 37 | — | — | Primary clause of interest for CAC research |
| Pari Passu | 29 | — | — | Equal ranking in right of payment |
| Governing Law | 71 | — | — | NY vs English law identification |

: Retrieval performance against #PublicDebtIsPublic expert annotations (preliminary) {#tbl-validation}

*Note: Update this table with actual numbers after running Task 3 (pattern optimization).*

**Reading this table:** High recall means we're finding most of the
clauses that experts annotated. The "Retrieved" column may be larger
than "Expert Docs" because retrieval runs across all 823
#PublicDebtIsPublic documents, while expert annotations cover 122.
Retrieved matches in unannotated documents are candidates for expert
review — which is exactly the point of the flywheel.

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

Note: The validation table numbers and the Shiny app URL should be updated with actual values after Tasks 3 and 7.

- [ ] **Step 2: Test render**

```bash
cd demo && quarto render chapter2.qmd && cd ..
```

- [ ] **Step 3: Commit**

```bash
git add demo/chapter2.qmd
git commit -m "feat: Chapter 2 — map, clause chart, validation table, Shiny embed"
```

---

### Task 7: Deploy Shiny App + Quarto Book

**Files:**
- No new files — deployment task

- [ ] **Step 1: Deploy Shiny app to shinyapps.io**

Option A — using rsconnect-python:
```bash
uv add rsconnect-python
uv run rsconnect deploy shiny demo/shiny-app/ --name tealinsights --title clause-eval-explorer
```

Option B — if rsconnect doesn't work, use shinylive to embed directly:
```bash
# Alternative: convert to shinylive and embed statically
uv add shinylive
cd demo/shiny-app && uv run shinylive export . ../shinylive-app && cd ../..
# Then update chapter2.qmd iframe to point to local shinylive-app/
```

- [ ] **Step 2: Verify deployed Shiny app**

Open the deployed URL in a browser. Test all three clause families, context display, and feedback buttons.

- [ ] **Step 3: Update Chapter 2 with actual validation numbers**

Read the latest validation report and update the table in `demo/chapter2.qmd` with real numbers.

- [ ] **Step 4: Update Chapter 2 iframe URL if needed**

If the Shiny app URL differs from the placeholder, update the `src` attribute.

- [ ] **Step 5: Render full book**

```bash
cd demo && quarto render && cd ..
```

- [ ] **Step 6: Deploy to GitHub Pages**

```bash
cd demo && quarto publish gh-pages --no-prompt && cd ..
```

If `quarto publish` doesn't work (needs repo setup), alternative:
```bash
cd demo/_book
git init
git add .
git commit -m "Deploy Quarto book"
git remote add origin https://github.com/Teal-Insights/sovereign-clause-corpus-demo.git
git push -u origin main --force
cd ../..
# Enable GitHub Pages in repo settings
```

- [ ] **Step 7: Verify deployed site**

Check:
- [ ] All 3 chapters load
- [ ] Map renders with 30+ countries shaded
- [ ] Clause family bar chart renders
- [ ] Shiny iframe loads and is interactive
- [ ] Works on mobile
- [ ] Mermaid flywheel diagram renders in Chapter 1
- [ ] Callout boxes display in Chapter 3

- [ ] **Step 8: Final commit and push**

```bash
git add demo/
git commit -m "feat: deploy Quarto book + Shiny eval explorer to GitHub Pages"
git push
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Parse full EDGAR + NSM corpus → Task 1
- [x] Bootstrap all sources into documents table → Task 1
- [x] Run grep across full corpus → Task 2
- [x] Analyze false positives/negatives → Task 2
- [x] Improve grep patterns → Task 3
- [x] Re-export data with full corpus → Task 4
- [x] Python Shiny eval explorer with feedback → Task 5
- [x] Choropleth map → Task 6
- [x] Clause family bar chart → Task 6
- [x] Validation table → Task 6
- [x] Shiny embed in Chapter 2 → Task 6
- [x] Deploy Shiny to shinyapps.io → Task 7
- [x] Deploy Quarto to GitHub Pages → Task 7

**Placeholder scan:** Validation table has "—" placeholders — noted with instruction to fill after Task 3.

**Type consistency:** CSV column names match between export script and Shiny app. Pattern names (`collective_action`, `pari_passu`, `feature__governing_law`) consistent throughout.
