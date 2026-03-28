# Branch 2: Results Optimization + Visualizations + Shiny App

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse the full corpus, optimize grep patterns, build static visualizations and a Python Shiny eval explorer, finalize Chapter 2 of the Quarto book, and deploy to GitHub Pages.

**Architecture:** Ingest EDGAR/NSM manifests into DuckDB (using existing `corpus ingest` CLI), parse remaining documents, run grep across full corpus, analyze false positives/negatives, improve patterns (timeboxed to 2 hours), then build visualizations and Shiny app from the improved data. All visualization data pre-exported as CSV. Deploy early — don't leave deployment to the end.

**Tech Stack:** Python 3.12, uv, DuckDB, Shiny for Python, plotly, Quarto 1.8, GitHub Pages, shinyapps.io

**Review feedback applied:** This plan incorporates feedback from 3 external reviews. Key changes from v1: reordered to build Shiny app earlier, use existing `corpus ingest` CLI instead of ad-hoc scripts, fix export_data.py to filter by run_id and use PDIP inventory for country counts, add jupyter/ipykernel for Quarto Python chunks, timebox pattern optimization, deploy early.

**Pre-flight:**
```bash
# Ensure on the right branch
git checkout feature/26-roundtable-quarto-book

# Install all needed dependencies
uv add shiny htmltools plotly jupyter ipykernel rsconnect-python pandas

# Verify EDGAR/NSM data exists
ls data/manifests/edgar_manifest.jsonl data/manifests/nsm_manifest.jsonl

# Verify Quarto Python chunks work
cd demo && quarto render index.qmd && cd ..

# Verify shinyapps.io credentials (if not already configured)
# Get token from https://www.shinyapps.io/admin/#/tokens
# uv run rsconnect add --account tealinsights --name tealinsights --token YOUR_TOKEN --secret YOUR_SECRET
```

**Context:** Branch 1 created the Quarto book scaffold with narrative chapters 1 and 3 (final), chapter 2 (placeholder), and a data export pipeline. This plan fills in Chapter 2 with real visualizations and the Shiny eval explorer.

**Cut lines (if running behind):**
- Cut first: durable CSV logging, second+ regex iterations, pari passu / governing law tuning
- Keep no matter what: full-corpus map, one clause chart, one working eval UI, one deployed book URL, one local fallback

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
| `demo/data/export_data.py` | Fix: filter by run_id, use PDIP inventory for countries, handle unmapped labels |
| `src/corpus/extraction/clause_patterns.py` | Improved patterns based on FP/FN analysis (timeboxed) |
| `tests/test_clause_patterns.py` | Tests for new pattern variants |

---

## Task 1: Ingest + Parse Full Corpus

**Files:**
- No new files — operational task using existing CLI

- [ ] **Step 1: Ingest EDGAR and NSM manifests into DuckDB**

Use the existing `corpus ingest` CLI (not ad-hoc scripts):

```bash
uv run corpus ingest --run-id ingest-full
```

This reads all `*_manifest.jsonl` files from `data/manifests/` and loads them into the `documents` table.

- [ ] **Step 2: Verify document counts**

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

If EDGAR/NSM counts are 0, the ingest CLI may need the manifests to have the right field names. Check the error output and fall back to the ad-hoc bootstrap if needed:

```bash
# Fallback only if corpus ingest doesn't handle EDGAR/NSM:
uv run python3 -c "
import duckdb, json
from pathlib import Path
con = duckdb.connect('data/db/corpus.duckdb')
for src in ['edgar', 'nsm']:
    manifest = Path(f'data/manifests/{src}_manifest.jsonl')
    inserted = 0
    with manifest.open() as f:
        for line in f:
            r = json.loads(line)
            sk = r['storage_key']
            if con.execute('SELECT 1 FROM documents WHERE storage_key = ?', [sk]).fetchone():
                continue
            con.execute('''INSERT INTO documents (source, native_id, storage_key, title, issuer_name, file_path, is_sovereign, issuer_type, scope_status)
                VALUES (?, ?, ?, ?, ?, ?, true, 'sovereign', 'in_scope')''',
                [src, r.get('native_id'), sk, r.get('title'), r.get('issuer_name'), r.get('file_path')])
            inserted += 1
    con.commit()
    print(f'{src}: inserted {inserted}')
con.close()
"
```

- [ ] **Step 3: Parse EDGAR corpus (start in background)**

```bash
uv run corpus parse run --run-id parse-edgar-full --source edgar
```

Expected: ~3,217 parsed (2,942 HTM + 275 TXT), ~84 skipped (.paper unsupported). Takes 10-30 min.

- [ ] **Step 4: Verify NSM is already parsed (it should be from prior session)**

```bash
ls data/parsed/nsm__* 2>/dev/null | wc -l
```

Expected: ~645. If not, run:
```bash
uv run corpus parse run --run-id parse-nsm-full --source nsm
```

- [ ] **Step 5: Verify total parse counts**

```bash
uv run python3 -c "
from pathlib import Path
from collections import Counter
parsed = list(Path('data/parsed').glob('*.jsonl'))
by_source = Counter(p.stem.split('__')[0] for p in parsed)
for s, c in by_source.most_common():
    print(f'  {s}: {c}')
print(f'  TOTAL: {len(parsed)}')
"
```

Expected: ~4,600+ total.

- [ ] **Step 6: Run grep across full corpus**

```bash
uv run corpus grep run --run-id grep-full-v2
```

- [ ] **Step 7: Check unmapped issuers**

```bash
uv run python3 -c "
import csv, json, duckdb
from pathlib import Path

# Load country map
mapped_patterns = set()
with open('demo/data/issuer_country_map.csv') as f:
    for row in csv.DictReader(f):
        mapped_patterns.add(row['issuer_pattern'].upper())

# Check which EDGAR/NSM issuers are not mapped
unmapped = {}
for src in ['edgar', 'nsm']:
    manifest = Path(f'data/manifests/{src}_manifest.jsonl')
    with manifest.open() as f:
        for line in f:
            r = json.loads(line)
            issuer = r.get('issuer_name', '')
            upper = issuer.upper()
            if not any(p in upper for p in mapped_patterns):
                unmapped[issuer] = unmapped.get(issuer, 0) + 1

if unmapped:
    print('Unmapped issuers (top 20):')
    for name, cnt in sorted(unmapped.items(), key=lambda x: -x[1])[:20]:
        print(f'  {cnt:4d}  {name}')
else:
    print('All issuers mapped!')
"
```

If major issuers are missing, add them to `demo/data/issuer_country_map.csv`.

- [ ] **Step 8: Commit**

```bash
git commit --allow-empty -m "ops: ingested + parsed full corpus (~4,700 documents)"
```

---

## Task 2: Fix Export Script + Build Shiny App

Build the Shiny app early using whatever data is available. It can be refreshed with better data later.

**Files:**
- Modify: `demo/data/export_data.py`
- Create: `demo/shiny-app/app.py`
- Create: `demo/shiny-app/requirements.txt`

- [ ] **Step 1: Fix export_data.py**

Three fixes from code review:

1. **Use PDIP inventory for country counts** (not just annotated docs in pdip_clauses)
2. **Filter grep_candidates by run_id** (prevent mixing stale and fresh results)
3. **Handle unmapped labels** in clause families export (show total annotations including unmapped)

Read `demo/data/export_data.py` and apply these fixes:

In `export_corpus_by_country()`: Replace the pdip_clauses query with reading from `data/pdip/pdip_document_inventory.csv`:

```python
    # Count from PDIP inventory (all 823 docs, not just annotated)
    inventory_path = PROJECT_ROOT / "data/pdip/pdip_document_inventory.csv"
    if inventory_path.exists():
        with inventory_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                country = row.get("country", "").strip()
                if country:
                    code = pdip_country_to_code.get(country, "")
                    if code:
                        counts[(country, code, "pdip")] += 1
```

In `export_grep_candidates()`: Add a `run_id` parameter and filter:

```python
def export_grep_candidates(run_id: str | None = None) -> None:
    """Export grep match candidates with context for the Shiny eval explorer."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    query = """SELECT d.storage_key, gm.pattern_name, gm.page_number,
                      gm.matched_text, gm.context_before, gm.context_after,
                      gm.run_id, pc.country, pc.document_title, pc.instrument_type
               FROM grep_matches gm
               JOIN documents d ON gm.document_id = d.document_id
               LEFT JOIN (SELECT DISTINCT doc_id, country, document_title, instrument_type
                          FROM pdip_clauses) pc ON d.storage_key = 'pdip__' || pc.doc_id"""

    if run_id:
        query += f" WHERE gm.run_id = '{run_id}'"

    query += " ORDER BY gm.pattern_name, pc.country, d.storage_key"
    rows = con.execute(query).fetchall()
    con.close()
    # ... rest unchanged
```

In `export_clause_families()`: Add a total row or note about unmapped labels:

```python
def export_clause_families() -> None:
    """Export clause family annotation counts from PDIP."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Mapped families
    rows = con.execute("""
        SELECT label_family, COUNT(*) as annotations, COUNT(DISTINCT doc_id) as docs
        FROM pdip_clauses WHERE label_family IS NOT NULL
        GROUP BY label_family ORDER BY docs DESC
    """).fetchall()

    # Also count unmapped
    unmapped = con.execute("""
        SELECT COUNT(*) as annotations, COUNT(DISTINCT doc_id) as docs
        FROM pdip_clauses WHERE label_family IS NULL
    """).fetchone()

    con.close()

    output_path = OUTPUT_DIR / "clause_families.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label_family", "annotations", "docs"])
        for row in rows:
            writer.writerow(row)
        if unmapped and unmapped[0] > 0:
            writer.writerow(["(unmapped)", unmapped[0], unmapped[1]])

    print(f"Wrote {len(rows) + (1 if unmapped and unmapped[0] > 0 else 0)} rows to {output_path}")
```

Update `__main__` to accept run_id:

```python
if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Exporting data (run_id={run_id})...")
    export_corpus_by_country()
    export_clause_families()
    export_grep_candidates(run_id)
    print("Done.")
```

- [ ] **Step 2: Run the fixed export**

```bash
uv run python3 demo/data/export_data.py grep-full-v2
```

Verify: `wc -l demo/data/corpus_by_country.csv` should show more rows than before (PDIP inventory covers more countries).

- [ ] **Step 3: Copy data for Shiny app**

```bash
cp demo/data/grep_candidates.csv demo/shiny-app/data/
cp demo/data/clause_families.csv demo/shiny-app/data/
```

- [ ] **Step 4: Create requirements.txt**

Create `demo/shiny-app/requirements.txt`:

```
shiny
htmltools
pandas
```

- [ ] **Step 5: Create the Shiny app**

Create `demo/shiny-app/app.py`:

```python
"""Clause Eval Explorer — Shiny for Python.

Interactive app for browsing clause candidates identified by automated
retrieval. Users can review candidates (yes/no) and provide feedback.

Note: Uses pandas (not polars) because Shiny's render.DataTable
works best with pandas DataFrames. The rest of the project uses polars.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from htmltools import tags
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

# ── Load data ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"

candidates_df = pd.read_csv(
    DATA_DIR / "grep_candidates.csv",
    na_values=["", "NA"],
)

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

# Feedback log (ephemeral on shinyapps.io — fine for demo)
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
        ui.p(
            "Browse clause candidates identified by automated retrieval. "
            "Click a row to see full context."
        ),
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
                        "thumbs_up",
                        "",
                        icon=ui.tags.i(class_="bi bi-hand-thumbs-up-fill"),
                        class_="btn btn-success btn-sm me-1",
                    ),
                    ui.input_action_button(
                        "thumbs_down",
                        "",
                        icon=ui.tags.i(class_="bi bi-hand-thumbs-down-fill"),
                        class_="btn btn-danger btn-sm me-1",
                    ),
                    ui.input_text(
                        "reason",
                        None,
                        placeholder="Why not? (optional)",
                        width="250px",
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
        df = filtered()[
            ["country", "document_title", "page_display", "matched_text"]
        ].copy()
        df.columns = ["Country", "Document", "Page", "Match"]
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
    def context_display():
        row = selected_row()
        if row is None:
            return ui.p(
                "Click a row above to see the full context.",
                class_="text-muted",
            )

        ctx_before = str(row.get("context_before", "") or "")
        matched = str(row.get("matched_text", "") or "")
        ctx_after = str(row.get("context_after", "") or "")

        return tags.div(
            tags.p(
                ui.HTML(ctx_before.replace("\n", "<br/>")),
                style="color: #666; font-family: Georgia, serif; "
                "font-size: 14px; line-height: 1.6;",
            ),
            tags.p(
                ui.HTML(matched.replace("\n", "<br/>")),
                style="background-color: #fff3cd; padding: 8px 12px; "
                "border-left: 4px solid #ffc107; font-weight: bold; "
                "font-family: Georgia, serif; font-size: 14px;",
            ),
            tags.p(
                ui.HTML(ctx_after.replace("\n", "<br/>")),
                style="color: #666; font-family: Georgia, serif; "
                "font-size: 14px; line-height: 1.6;",
            ),
            tags.hr(),
            tags.small(
                f"{row['storage_key']} · p. {row['page_number']}"
                f" · Pattern: {row['pattern_name']}",
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
            f"{'👍' if decision == 'yes' else '👎'} Recorded",
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

- [ ] **Step 6: Test Shiny app locally**

```bash
cd demo/shiny-app && uv run shiny run app.py --port 3838 &
# Open http://localhost:3838
# Test: select each family, click rows, verify context display, try thumbs up/down
# Kill with: kill %1
cd ../..
```

- [ ] **Step 7: Commit**

```bash
git add demo/data/export_data.py demo/shiny-app/ demo/data/corpus_by_country.csv demo/data/clause_families.csv demo/data/grep_candidates.csv
git commit -m "feat: fixed data export + Python Shiny eval explorer"
```

---

## Task 3: Pattern Optimization (TIMEBOXED — 2 hours max)

**Files:**
- Modify: `src/corpus/extraction/clause_patterns.py`
- Modify: `tests/test_clause_patterns.py`

**Hard timebox: 2 hours.** The goal is modest improvement, not perfection. 92% CAC recall is already the headline. Focus on CAC first, then pari passu if time remains. Skip governing law tuning if behind schedule.

- [ ] **Step 1: Examine false negatives**

```bash
uv run python3 -c "
import json, duckdb
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb', read_only=True)

# PDIP docs with CAC annotations
pdip_cac_docs = set()
with Path('data/pdip/clause_annotations.jsonl').open() as f:
    for line in f:
        r = json.loads(line)
        if r.get('label_family') == 'collective_action':
            pdip_cac_docs.add(r['doc_id'])

# Grep CAC docs
grep_cac_docs = set()
for row in con.execute('''
    SELECT DISTINCT d.storage_key FROM grep_matches gm
    JOIN documents d ON gm.document_id = d.document_id
    WHERE gm.pattern_name = 'collective_action' AND gm.run_id = 'grep-full-v2'
''').fetchall():
    grep_cac_docs.add(row[0])

fn = pdip_cac_docs - {sk.replace('pdip__','') for sk in grep_cac_docs}
print(f'CAC false negatives: {len(fn)} docs')
for doc_id in sorted(fn):
    with Path('data/pdip/clause_annotations.jsonl').open() as f:
        for line in f:
            r = json.loads(line)
            if r['doc_id'] == doc_id and r.get('label_family') == 'collective_action' and r.get('text'):
                print(f'  [{doc_id}] {r[\"text\"][:200]}')
                break
con.close()
"
```

- [ ] **Step 2: Examine sample false positives**

```bash
uv run python3 -c "
import duckdb
con = duckdb.connect('data/db/corpus.duckdb', read_only=True)
rows = con.execute('''
    SELECT d.storage_key, gm.matched_text, gm.page_number
    FROM grep_matches gm
    JOIN documents d ON gm.document_id = d.document_id
    WHERE gm.pattern_name = 'collective_action' AND d.source = 'pdip' AND gm.run_id = 'grep-full-v2'
    LIMIT 15
''').fetchall()
for sk, matched, page in rows:
    print(f'[{sk} p.{page}] {matched}')
con.close()
"
```

- [ ] **Step 3: Add tests for new pattern variants discovered in FN analysis**

Based on what you find, add tests. Example:

```python
def test_cac_pattern_matches_meetings_of_noteholders() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "meetings of the Noteholders may be convened"
    assert p.finder.search(text) is not None
```

- [ ] **Step 4: Update patterns**

Likely additions based on issue #25 and FN analysis. Update `clause_patterns.py`.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_clause_patterns.py -v
uv run ruff check src/corpus/extraction/clause_patterns.py tests/test_clause_patterns.py
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

- [ ] **Step 8: Commit**

```bash
git add src/corpus/extraction/clause_patterns.py tests/test_clause_patterns.py
git commit -m "feat: improved clause patterns (timeboxed optimization)"
```

---

## Task 4: Re-export Data + Update Shiny App

**Files:**
- No new files — re-run export, copy to Shiny

- [ ] **Step 1: Re-export with latest grep run_id**

```bash
uv run python3 demo/data/export_data.py grep-improved
```

If you didn't get to pattern optimization (Task 3), use:
```bash
uv run python3 demo/data/export_data.py grep-full-v2
```

- [ ] **Step 2: Copy updated data to Shiny**

```bash
cp demo/data/grep_candidates.csv demo/shiny-app/data/
cp demo/data/clause_families.csv demo/shiny-app/data/
```

- [ ] **Step 3: Test Shiny app with updated data**

```bash
cd demo/shiny-app && uv run shiny run app.py --port 3838 &
# Verify data looks right
# Kill: kill %1
cd ../..
```

- [ ] **Step 4: Commit**

```bash
git add demo/data/ demo/shiny-app/data/
git commit -m "feat: re-export data with full corpus + improved patterns"
```

---

## Task 5: Finalize Chapter 2 + Deploy

**Files:**
- Modify: `demo/chapter2.qmd`

- [ ] **Step 1: Update Chapter 2 with Python visualizations**

Replace `demo/chapter2.qmd` with the final version using `{python}` code chunks for plotly visualizations:

````markdown
# Preliminary Findings

::: {.callout-warning}
These are preliminary results from a one-week proof of concept. We
present them as evidence that the approach works and merits expert
methodology review — not as finished research.
:::

## The Corpus

We collected over 4,800 sovereign bond prospectuses from three public
sources. The map below shows geographic coverage based on preliminary
matching of issuer names to countries.

```{python}
#| label: fig-map
#| fig-cap: "Sovereign bond prospectuses collected from SEC EDGAR, FCA NSM, and #PublicDebtIsPublic. Geographic coverage is based on preliminary substring matching of issuer names."

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
expert clause annotations. The chart below shows how many documents
contain annotations for each clause family. Some annotation labels
have not yet been mapped to families and are shown separately.

```{python}
#| label: fig-families
#| fig-cap: "Clause family coverage in #PublicDebtIsPublic expert-annotated corpus (122 documents)"

families = pd.read_csv("data/clause_families.csv")
# Exclude the (unmapped) row for the main chart, note it separately
mapped = families[families["label_family"] != "(unmapped)"].head(15).copy()
mapped["label_clean"] = mapped["label_family"].str.replace("_", " ").str.title()

fig = px.bar(
    mapped.sort_values("docs"),
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
| Collective Action | 37 | — | — | Primary clause of interest |
| Pari Passu | 29 | — | — | Equal ranking in right of payment |
| Governing Law | 71 | — | — | NY vs English law |

: Retrieval performance against #PublicDebtIsPublic expert annotations (preliminary) {#tbl-validation}

*Update this table with actual numbers from the latest validation run.*

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

Note: Update the validation table numbers and Shiny URL after deployment.

- [ ] **Step 2: Test Quarto render with Python chunks**

```bash
cd demo && quarto render chapter2.qmd && cd ..
```

If this fails with a Python/Jupyter error, ensure `jupyter` and `ipykernel` are installed:
```bash
uv add jupyter ipykernel
```

- [ ] **Step 3: Deploy Shiny app to shinyapps.io**

```bash
uv run rsconnect deploy shiny demo/shiny-app/ --account tealinsights --title clause-eval-explorer
```

After deployment, test: open the URL, verify all three clause families work, test iframe embedding (some servers block X-Frame-Options).

If iframe is blocked, change Chapter 2 to use a direct link instead:
```markdown
[**Open the Eval Explorer →**](https://tealinsights.shinyapps.io/clause-eval-explorer/)
```

- [ ] **Step 4: Update Chapter 2 with actual validation numbers and Shiny URL**

Read `data/output/validation_report.json` and fill in the "—" placeholders in the validation table. Update the iframe `src` if the Shiny URL differs.

- [ ] **Step 5: Render full book**

```bash
cd demo && quarto render && cd ..
```

- [ ] **Step 6: Deploy to GitHub Pages**

```bash
cd demo && quarto publish gh-pages --no-prompt && cd ..
```

If `quarto publish` needs setup, first enable GitHub Pages in repo settings (Settings → Pages → Source: gh-pages branch).

- [ ] **Step 7: Verify deployed site**

Check:
- [ ] All 3 chapters load
- [ ] Map renders with 30+ countries shaded
- [ ] Clause family bar chart renders
- [ ] Shiny iframe or link works
- [ ] Mermaid flywheel diagram in Chapter 1
- [ ] Works on mobile (test on phone)
- [ ] Callout boxes in Chapter 3

- [ ] **Step 8: Commit and push**

```bash
git add demo/
git commit -m "feat: finalized Chapter 2 + deployed book and Shiny app"
git push
```

---

## Monday Morning Checklist

- [ ] **8:00am:** Open Shiny app URL to wake from cold start
- [ ] **8:05am:** Open Quarto book URL, verify GitHub Pages is up
- [ ] **8:10am:** If either is down, switch to local fallback:
  ```bash
  cd demo/shiny-app && uv run shiny run app.py --port 3838 &
  cd demo && quarto preview &
  ```
- [ ] Have the Quarto book URL ready to share (phone/laptop)
- [ ] Know the 3 numbers: "4,800+ documents, 3 sources, 6,200+ expert annotations"

---

## Self-Review Checklist

**Spec coverage:**
- [x] Parse full EDGAR + NSM corpus → Task 1
- [x] Bootstrap all sources into documents table → Task 1
- [x] Check unmapped issuers → Task 1
- [x] Run grep across full corpus → Task 1
- [x] Fix export_data.py (run_id filter, PDIP inventory, unmapped labels) → Task 2
- [x] Python Shiny eval explorer → Task 2
- [x] Analyze false positives/negatives → Task 3
- [x] Improve grep patterns (timeboxed) → Task 3
- [x] Re-export data → Task 4
- [x] Choropleth map → Task 5
- [x] Clause family bar chart → Task 5
- [x] Validation table → Task 5
- [x] Shiny embed in Chapter 2 → Task 5
- [x] Deploy Shiny to shinyapps.io → Task 5
- [x] Deploy Quarto to GitHub Pages → Task 5
- [x] Monday morning checklist → included
- [x] Local fallback plan → included

**Review feedback addressed:**
- [x] Timebox pattern optimization to 2 hours
- [x] Build Shiny app earlier (Task 2, not Task 5)
- [x] Install jupyter/ipykernel for Quarto Python chunks
- [x] Fix export_data.py run_id filter
- [x] Use PDIP inventory for country counts
- [x] Use existing `corpus ingest` CLI
- [x] rsconnect uses `--account` not `--name`
- [x] Test iframe embedding
- [x] Local fallback for Monday morning
- [x] Note about ephemeral CSV on shinyapps.io
- [x] Note about pandas vs polars in Shiny app
- [x] Country mapping disclaimer on map
- [x] Handle unmapped labels in clause families export

**Placeholder scan:** Validation table has "—" — noted with explicit instruction to fill after Task 3.
