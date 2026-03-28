# Shiny Display Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Shiny eval explorer display — reflow broken PyMuPDF text, deduplicate matches, show full page context with highlighted matches — so the Monday roundtable demo looks professional.

**Architecture:** Modify the data export script to (1) reflow broken single-word lines from PyMuPDF output, (2) deduplicate matches per document/page/pattern, and (3) include full page text from parsed JSONL files. Update the Shiny app to display full page text in a scrollable panel with the match highlighted. No changes to the grep runner, parsers, or pipeline code.

**Tech Stack:** Python 3.12, uv, DuckDB, Shiny for Python, pandas

**Pre-flight:**
```bash
git checkout feature/29-shiny-display-fixes
```

**Spec:** `docs/superpowers/specs/2026-03-28-shiny-display-and-docling-reparse-design.md` (Workstream A)

---

## File Structure

### Modified Files

| File | Change |
|------|--------|
| `demo/data/export_data.py` | Add reflow_text(), dedup, full page text export |
| `demo/shiny-app/app.py` | Display full page text with highlighted match, scrollable panel |

---

## Task 1: Text Reflow + Dedup in Export Script

**Files:**
- Modify: `demo/data/export_data.py`

- [ ] **Step 1: Add the reflow_text function**

Add this function near the top of `demo/data/export_data.py` (after imports):

```python
def reflow_text(text: str) -> str:
    """Reflow broken PyMuPDF text where words are split across lines.

    PyMuPDF sometimes extracts multi-column PDFs word-by-word, producing
    'The\\nBonds\\ncontain\\n"collective\\naction"' instead of flowing prose.
    This heuristic joins short lines that look like broken fragments.

    Only apply to PyMuPDF-parsed text (PDIP/NSM PDFs), NOT EDGAR HTML.
    """
    # Fix hyphenation across lines
    text = text.replace("-\n", "")

    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line = paragraph break, keep it
        if not stripped:
            result.append("")
            i += 1
            continue

        # Accumulate fragments
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line:
                break  # paragraph break
            # Current line is short and doesn't end with terminal punctuation
            if (len(stripped) < 60
                    and not stripped.endswith((".", ":", ";", "?", "!"))
                    and (next_line[0].islower() or len(stripped) < 15)):
                stripped = stripped + " " + next_line
                i += 1
            else:
                break

        result.append(stripped)
        i += 1

    return "\n".join(result)
```

- [ ] **Step 2: Add full page text loading**

Add this function after `reflow_text`:

```python
def load_page_text(storage_key: str, page_number: int) -> str | None:
    """Load the full text for a specific page from parsed JSONL.

    Args:
        storage_key: e.g. 'pdip__IDN1'
        page_number: 1-indexed page number (as stored in grep_matches)
    """
    parsed_path = PROJECT_ROOT / "data" / "parsed" / f"{storage_key}.jsonl"
    if not parsed_path.exists():
        return None

    page_index = page_number - 1  # Convert to 0-indexed
    with parsed_path.open() as f:
        for line in f:
            record = json.loads(line)
            if record.get("page") == page_index:
                return record.get("text", "")
    return None
```

- [ ] **Step 3: Update export_grep_candidates to include full page text and dedup**

Replace the `export_grep_candidates` function body. Key changes:
- Load full page text for each match
- Apply reflow to page text for PDF sources (pdip__, nsm__)
- Deduplicate by (storage_key, page_number, pattern_name)
- Add `page_text` column to CSV output

```python
def export_grep_candidates(run_id: str | None = None) -> None:
    """Export grep match candidates with context and full page text."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    query = """SELECT d.storage_key,
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
               LEFT JOIN (SELECT DISTINCT doc_id, country, document_title, instrument_type
                          FROM pdip_clauses) pc ON d.storage_key = 'pdip__' || pc.doc_id
               WHERE d.source = 'pdip'"""

    params: list[str] = []
    if run_id:
        query += " AND gm.run_id = ?"
        params.append(run_id)

    query += " ORDER BY gm.pattern_name, pc.country, d.storage_key"
    rows = con.execute(query, params).fetchall()
    con.close()

    # Deduplicate: keep first (longest matched_text) per (storage_key, page, pattern)
    seen: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        storage_key = row[0]
        pattern_name = row[1]
        page_number = str(row[2])
        key = (storage_key, page_number, pattern_name)

        record = {
            "storage_key": storage_key,
            "pattern_name": pattern_name,
            "page_number": page_number,
            "matched_text": row[3],
            "context_before": row[4] or "",
            "context_after": row[5] or "",
            "run_id": row[6] or "",
            "country": row[7] or "",
            "document_title": row[8] or "",
            "instrument_type": row[9] or "",
        }

        if key not in seen or len(record["matched_text"]) > len(seen[key]["matched_text"]):
            seen[key] = record

    # Load full page text and apply reflow for PDF sources
    deduped = list(seen.values())
    for record in deduped:
        page_text = load_page_text(record["storage_key"], int(record["page_number"]))
        is_pdf = record["storage_key"].startswith(("pdip__", "nsm__"))

        if page_text and is_pdf:
            page_text = reflow_text(page_text)

        record["page_text"] = page_text or ""

        # Also reflow context fields for PDF sources
        if is_pdf:
            record["context_before"] = reflow_text(record["context_before"])
            record["context_after"] = reflow_text(record["context_after"])

    output_path = OUTPUT_DIR / "grep_candidates.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "storage_key", "pattern_name", "page_number",
            "matched_text", "context_before", "context_after",
            "run_id", "country", "document_title", "instrument_type",
            "page_text",
        ])
        for record in deduped:
            writer.writerow([record[k] for k in [
                "storage_key", "pattern_name", "page_number",
                "matched_text", "context_before", "context_after",
                "run_id", "country", "document_title", "instrument_type",
                "page_text",
            ]])

    print(f"Wrote {len(deduped)} rows to {output_path} (deduped from {len(rows)})")
```

- [ ] **Step 4: Run the updated export**

```bash
uv run python3 demo/data/export_data.py grep-improved
```

Expected: fewer rows than before (deduped), and each row now has a `page_text` column.

- [ ] **Step 5: Verify dedup and reflow worked**

```bash
uv run python3 -c "
import csv
with open('demo/data/grep_candidates.csv') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'Total rows: {len(rows)}')
# Check a PDF row has reflowed page text
for r in rows:
    if r['storage_key'].startswith('pdip__IDN') and 'collective action' in r['matched_text'].lower():
        print(f'Page text sample ({len(r[\"page_text\"])} chars):')
        print(r['page_text'][:300])
        break
"
```

Verify: page text should have flowing paragraphs (not single-word lines).

- [ ] **Step 6: Copy to Shiny app**

```bash
cp demo/data/grep_candidates.csv demo/shiny-app/data/
```

- [ ] **Step 7: Commit**

```bash
git add demo/data/export_data.py demo/data/grep_candidates.csv demo/shiny-app/data/grep_candidates.csv
git commit -m "feat: reflow broken text, deduplicate matches, add full page text to export"
```

---

## Task 2: Update Shiny App Display

**Files:**
- Modify: `demo/shiny-app/app.py`

- [ ] **Step 1: Update the Shiny app to display full page text**

Read `demo/shiny-app/app.py` and make these changes:

**In the data loading section:** The CSV now has a `page_text` column. No changes needed to loading — pandas reads it automatically.

**In the context display render function:** Replace the current context_before/matched/context_after display with full page text display. Find the matched text within the page text and highlight it.

Replace the context display function with:

```python
    @render.ui
    def context_display():
        row = selected_row()
        if row is None:
            return ui.p(
                "Click a row above to see the full context.",
                class_="text-muted",
            )

        page_text = str(row.get("page_text", "") or "")
        matched = str(row.get("matched_text", "") or "")
        country = str(row.get("country", "") or "Unknown")
        doc_title = str(row.get("document_title", "") or row.get("storage_key", ""))
        page_num = str(row.get("page_number", "") or "?")

        # Highlight matched text within page text
        if page_text and matched:
            # Normalize whitespace for matching
            import re
            # Create a pattern that matches the text with flexible whitespace
            escaped = re.escape(matched)
            flex_pattern = re.sub(r'\\ ', r'\\s+', escaped)
            highlighted = re.sub(
                f'({flex_pattern})',
                r'<mark style="background-color: #fff3cd; padding: 2px 4px; font-weight: bold;">\1</mark>',
                page_text,
                count=0,  # highlight all occurrences
                flags=re.IGNORECASE,
            )
            display_html = highlighted.replace("\n\n", "</p><p>").replace("\n", " ")
            display_html = f"<p>{display_html}</p>"
        elif page_text:
            display_html = page_text.replace("\n\n", "</p><p>").replace("\n", " ")
            display_html = f"<p>{display_html}</p>"
        else:
            # Fallback to old context_before/after display
            ctx_before = str(row.get("context_before", "") or "")
            ctx_after = str(row.get("context_after", "") or "")
            display_html = (
                f'<p style="color: #666;">{ctx_before}</p>'
                f'<p><mark style="background-color: #fff3cd; padding: 2px 4px; font-weight: bold;">{matched}</mark></p>'
                f'<p style="color: #666;">{ctx_after}</p>'
            )

        return tags.div(
            tags.h6(
                f"{country} — {doc_title} (page {page_num})",
                style="margin-bottom: 12px;",
            ),
            tags.div(
                ui.HTML(display_html),
                style=(
                    "font-family: Georgia, 'Times New Roman', serif; "
                    "font-size: 14px; line-height: 1.7; "
                    "max-height: 500px; overflow-y: auto; "
                    "padding: 16px; background: #fafafa; "
                    "border: 1px solid #eee; border-radius: 4px;"
                ),
            ),
            tags.hr(),
            tags.small(
                f"{row['storage_key']} · Pattern: {row['pattern_name']}",
                class_="text-muted",
            ),
            tags.p(
                tags.em(
                    "In a production version, each candidate would link "
                    "to the original source document."
                ),
                class_="text-muted small mt-2",
            ),
        )
```

- [ ] **Step 2: Test locally**

```bash
cd demo/shiny-app && uv run shiny run app.py --port 3838 &
# Open http://localhost:3838
# Test: click an Indonesia CAC match — should show flowing text with yellow highlight
# Test: check dedup — should not see 6 identical Indonesia rows
# Kill: kill %1
cd ../..
```

- [ ] **Step 3: Run ruff check**

```bash
uv run ruff check demo/shiny-app/app.py demo/data/export_data.py
```

- [ ] **Step 4: Commit**

```bash
git add demo/shiny-app/app.py
git commit -m "feat: Shiny app — full page text display with highlighted matches"
```

---

## Task 3: Re-deploy

**Files:**
- No new files — deployment

- [ ] **Step 1: Re-deploy Shiny app**

```bash
uv run rsconnect deploy shiny demo/shiny-app/ \
  -A tealinsights \
  -T YOUR_TOKEN \
  -S "YOUR_SECRET" \
  --title clause-eval-explorer
```

(Use the credentials from the rsconnect servers.json file.)

- [ ] **Step 2: Verify deployed app**

Open https://tealinsights.shinyapps.io/clause-eval-explorer/

Check:
- [ ] No duplicate Indonesia rows for the same page
- [ ] Full page text shows in context panel
- [ ] Match is highlighted in yellow within the page text
- [ ] Text flows as paragraphs (not single-word lines)
- [ ] Scrollable context panel works

- [ ] **Step 3: Re-render and deploy Quarto book**

```bash
cd demo && quarto render && quarto publish gh-pages --no-browser --no-prompt && cd ..
```

- [ ] **Step 4: Push and commit**

```bash
git push
```

---

## Self-Review

**Spec coverage:**
- [x] Fix 1: Reflow broken text → Task 1 (reflow_text function)
- [x] Fix 2: Deduplicate matches → Task 1 (dedup logic)
- [x] Fix 3: Full page text → Task 1 (load_page_text) + Task 2 (Shiny display)
- [x] Only reflow PyMuPDF output, not EDGAR HTML → Task 1 (is_pdf check)
- [x] Don't reflow matched_text → Task 1 (only reflows context and page_text)
- [x] Proportional font → Task 2 (Georgia serif)
- [x] Scrollable panel → Task 2 (max-height + overflow-y)
- [x] "Link to original" note → Task 2
- [x] Re-deploy → Task 3

**Placeholder scan:** No TBDs. Token/secret in deploy command noted as placeholder — user has credentials.
