# Shiny for Python Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the Sovereign Bond Prospectus Explorer from Streamlit to Shiny for Python, deploying to Posit Connect Cloud alongside the existing Streamlit app.

**Architecture:** Shiny for Python Core API app (`shiny/app.py`) that imports the existing `explorer/` query layer directly. Two reactive values (`current_view` and `selected_doc_id`) drive navigation between browse and detail views via `@render.ui`. MotherDuck connection via `MOTHERDUCK_TOKEN` environment variable.

**Tech Stack:** Shiny for Python 1.x, DuckDB 1.4.4, Pandas, Posit Connect Cloud

**Spec:** `docs/superpowers/specs/2026-04-12-shiny-explorer-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `explorer/display.py` | Create | Shared display helpers (source names, ext_link) extracted from `explorer/app.py` |
| `explorer/app.py` | Modify | Import from `explorer/display.py` instead of defining locally |
| `shiny/app.py` | Create | Shiny for Python app -- all UI code |
| `shiny/requirements.txt` | Create | Deploy dependencies for Posit Connect Cloud |
| `tests/test_display.py` | Create | Tests for shared display helpers |

---

### Task 1: Extract Shared Display Helpers

The Streamlit app defines `_SOURCE_DISPLAY_NAMES`, `_source_display()`, and `ext_link()` inside `explorer/app.py`. The Shiny app needs these too. Extract them to a shared module.

**Files:**
- Create: `explorer/display.py`
- Modify: `explorer/app.py`
- Create: `tests/test_display.py`

- [ ] **Step 1: Create `explorer/display.py`**

```python
"""Shared display helpers for Streamlit and Shiny explorer apps."""

from __future__ import annotations

import html as html_mod

SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "edgar": "SEC EDGAR",
    "nsm": "FCA NSM",
    "luxse": "Luxembourg Stock Exchange",
    "pdip": "#PublicDebtIsPublic",
}

GITHUB_URL = "https://github.com/Teal-Insights/sovereign-prospectus-corpus"
QCRAFT_URL = "https://teal-insights.github.io/QCraft-App/"
PROTOTYPE_URL = "https://teal-insights.github.io/sovereign-prospectus-corpus/"


def source_display(source: str) -> str:
    """Convert internal source key to human-readable name."""
    return SOURCE_DISPLAY_NAMES.get(source, source)


def ext_link(url: str, text: str) -> str:
    """HTML for an external link that opens in a new tab."""
    return (
        f'<a href="{html_mod.escape(url)}" target="_blank"'
        f' rel="noopener noreferrer">{html_mod.escape(text)} \u2197</a>'
    )
```

- [ ] **Step 2: Write tests**

Create `tests/test_display.py`:

```python
"""Tests for shared display helpers."""

from __future__ import annotations


def test_source_display_known():
    from explorer.display import source_display

    assert source_display("edgar") == "SEC EDGAR"
    assert source_display("nsm") == "FCA NSM"
    assert source_display("luxse") == "Luxembourg Stock Exchange"
    assert source_display("pdip") == "#PublicDebtIsPublic"


def test_source_display_unknown():
    from explorer.display import source_display

    assert source_display("unknown_source") == "unknown_source"


def test_ext_link_escapes_html():
    from explorer.display import ext_link

    result = ext_link('http://example.com/"test"', "Click <here>")
    assert "&quot;" in result
    assert "&lt;" in result
    assert 'target="_blank"' in result
    assert 'rel="noopener noreferrer"' in result
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_display.py -v
```

Expected: 3 PASSED.

- [ ] **Step 4: Update `explorer/app.py` to import from `display.py`**

Replace the local definitions in `explorer/app.py`. Remove:
- `_SOURCE_DISPLAY_NAMES` dict
- `_source_display()` function
- `ext_link()` function
- `_GITHUB_URL`, `_QCRAFT_URL`, `_PROTOTYPE_URL` constants

Add at the top (after the `sys.path` block):

```python
from explorer.display import (
    GITHUB_URL,
    PROTOTYPE_URL,
    QCRAFT_URL,
    ext_link,
    source_display,
)
```

Then find-and-replace throughout `explorer/app.py`:
- `_source_display(` -> `source_display(`
- `_SOURCE_DISPLAY_NAMES` -> `SOURCE_DISPLAY_NAMES`
- `_GITHUB_URL` -> `GITHUB_URL`
- `_QCRAFT_URL` -> `QCRAFT_URL`
- `_PROTOTYPE_URL` -> `PROTOTYPE_URL`

Also remove the `import html` inside `ext_link` since it's now in `display.py`.

- [ ] **Step 5: Run existing tests to verify no breakage**

```bash
uv run pytest tests/test_highlight.py tests/test_explorer_queries.py tests/test_issuer_mapping.py tests/test_display.py -v
```

Expected: All pass (15 existing + 3 new = 18).

- [ ] **Step 6: Verify Streamlit app still works**

```bash
uv run streamlit run explorer/app.py --server.headless true --server.port 8501 &
sleep 4
curl -s http://localhost:8501/_stcore/health
kill $(lsof -ti:8501) 2>/dev/null
```

Expected: `ok`.

- [ ] **Step 7: Commit**

```bash
git add explorer/display.py explorer/app.py tests/test_display.py
git commit -m "refactor: extract shared display helpers for Streamlit/Shiny reuse"
```

---

### Task 2: Create Shiny App -- Browse View

**Files:**
- Create: `shiny/app.py`
- Create: `shiny/requirements.txt`

- [ ] **Step 1: Create `shiny/requirements.txt`**

```
shiny>=1.0
duckdb==1.4.4
pandas>=2.0
```

- [ ] **Step 2: Write `shiny/app.py` with browse view**

```python
"""Sovereign Bond Prospectus Explorer -- Shiny for Python.

Shiny port of the Streamlit explorer. Reuses the query layer from
explorer/ and deploys to Posit Connect Cloud.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `from explorer.queries import ...`
# works on Posit Connect Cloud.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from explorer.display import (
    GITHUB_URL,
    PROTOTYPE_URL,
    QCRAFT_URL,
    ext_link,
    source_display,
)
from explorer.queries import (
    browse_documents,
    count_documents,
    get_corpus_stats,
    get_document_detail,
    get_filter_options,
    get_markdown,
    get_markdown_size,
    get_max_page,
    get_page_text,
    search_pages_in_document,
)

# ── Constants ────────────────────────────────────────────────────────

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")
ASSETS_DIR = Path(__file__).resolve().parent.parent / "explorer" / "assets"
MARKDOWN_SIZE_LIMIT = 200_000


# ── Database connection ──────────────────────────────────────────────


def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to MotherDuck or local DuckDB."""
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
    if LOCAL_DB_PATH.exists():
        return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
    raise RuntimeError(
        "No database available. Set MOTHERDUCK_TOKEN or ensure "
        "data/db/corpus.duckdb exists."
    )


# ── Cached data (loaded once at startup) ─────────────────────────────

_con = get_connection()
_stats = get_corpus_stats(_con)
_filter_opts = get_filter_options(_con)

_source_choices = {s: source_display(s) for s in _filter_opts["sources"]}
_region_choices = _filter_opts["regions"]
_income_choices = _filter_opts["income_groups"]
_country_choices = {code: name for code, name in _filter_opts["countries"]}


# ── About expander content ───────────────────────────────────────────


def _about_content() -> ui.Tag:
    """Build the About section content as Shiny UI tags."""
    return ui.div(
        ui.HTML(
            "<p>An open-source corpus of sovereign bond prospectuses collected "
            "from the FCA National Storage Mechanism, SEC EDGAR, "
            "the Sovereign Debt Forum's #PublicDebtIsPublic Dataset, and the "
            "Luxembourg Stock Exchange. Built by "
            + ext_link("https://tealinsights.com", "Teal Insights")
            + " with support from "
            + ext_link("https://naturefinance.net", "NatureFinance")
            + ". "
            + ext_link(GITHUB_URL, "GitHub")
            + " | "
            + ext_link(GITHUB_URL + "/blob/main/LICENSE", "MIT License")
            + ".</p>"
        ),
        ui.HTML(
            "<p>This is an early-stage beta with plenty of rough edges. "
            "It grew out of community feedback on a "
            + ext_link(PROTOTYPE_URL, "prototype proposal")
            + " for scaling clause identification in sovereign bond contracts. "
            "That feedback pointed to an immediate pain point: just finding and "
            "navigating prospectuses across multiple sources is hard. "
            "This explorer is a first down payment on what could become something "
            "much more powerful, with your input.</p>"
        ),
        ui.h5("What's next?"),
        ui.tags.ul(
            ui.tags.li("Automated updates as new prospectuses are filed"),
            ui.tags.li(
                ui.HTML(
                    "Filtering by document type (base prospectus, supplement, "
                    "final terms, etc.)"
                )
            ),
            ui.tags.li(
                ui.HTML(
                    "Automated clause identification with expert validation ("
                    + ext_link(PROTOTYPE_URL, "learn more")
                    + ")"
                )
            ),
            ui.tags.li(
                ui.HTML(
                    "Part of a growing open-source SovTech ecosystem alongside "
                    "tools like the "
                    + ext_link(QCRAFT_URL, "Q-CRAFT Explorer")
                    + " -- open-source tools that elevate the sovereign debt "
                    "conversation by eliminating analytical toil"
                )
            ),
        ),
        ui.h5("Help shape this tool"),
        ui.p(
            "We're building this with the people who use sovereign debt data. "
            "If you have 2 minutes, we'd love to hear from you:"
        ),
        ui.tags.ol(
            ui.tags.li(
                "What are your biggest pain points in working with sovereign "
                "bond prospectuses?"
            ),
            ui.tags.li(
                'Are you a sovereign debt lawyer who might be interested in '
                '"lawyer-in-the-loop" validation to help automatically identify '
                "key clauses?"
            ),
            ui.tags.li(
                "Would you be willing to have a short conversation about how "
                "this tool could be more useful for your work?"
            ),
        ),
        ui.HTML(
            "<p>"
            + ext_link("mailto:lte@tealinsights.com", "Get in touch")
            + " or open an issue on "
            + ext_link(GITHUB_URL + "/issues", "GitHub")
            + ".</p>"
        ),
    )


# ── UI ───────────────────────────────────────────────────────────────

app_ui = ui.page_fillable(
    ui.head_content(
        ui.tags.title("Sovereign Bond Prospectus Explorer"),
    ),
    # Main content -- dynamically rendered based on view state
    ui.output_ui("main_view"),
    title="Sovereign Bond Prospectus Explorer",
)


# ── Server ───────────────────────────────────────────────────────────


def server(input: Inputs, output: Outputs, session: Session):
    # ── Navigation state ─────────────────────────────────────────
    current_view = reactive.value("browse")
    selected_doc_id = reactive.value(None)
    browse_page = reactive.value(0)

    # ── Main view router ─────────────────────────────────────────
    @render.ui
    def main_view():
        if current_view() == "detail" and selected_doc_id() is not None:
            return _build_detail_view(input, selected_doc_id())
        return _build_browse_view()

    # ── Browse view builder ──────────────────────────────────────
    def _build_browse_view() -> ui.Tag:
        return ui.div(
            # Header with logos
            ui.layout_columns(
                ui.div(
                    ui.img(
                        src="teal-insights-logo.png",
                        width="120px",
                    )
                    if (ASSETS_DIR / "teal-insights-logo.png").exists()
                    else ui.div(),
                ),
                ui.div(
                    ui.h1("Sovereign Bond Prospectus Explorer"),
                    ui.p(
                        ui.em(
                            "Browse 9,700+ sovereign bond prospectuses from "
                            "4 public sources. Open-source SovTech infrastructure "
                            "for sovereign debt research."
                        )
                    ),
                ),
                ui.div(
                    ui.img(
                        src="naturefinance-logo.png",
                        width="120px",
                    )
                    if (ASSETS_DIR / "naturefinance-logo.png").exists()
                    else ui.div(),
                ),
                col_widths=(2, 8, 2),
            ),
            # Stats
            ui.layout_columns(
                ui.value_box(
                    "Documents",
                    f"{_stats['docs']:,}",
                ),
                ui.value_box(
                    "Sources",
                    str(_stats["sources"]),
                ),
                ui.value_box(
                    "Issuers",
                    f"{_stats['issuers']:,}",
                ),
                col_widths=(4, 4, 4),
            ),
            # About expander
            ui.accordion(
                ui.accordion_panel("About this project", _about_content()),
                id="about_accordion",
                open=False,
            ),
            # Filters
            ui.input_checkbox("include_hi", "Include high-income countries", False),
            ui.layout_columns(
                ui.input_selectize(
                    "filter_country",
                    "Country",
                    choices=dict(sorted(_country_choices.items(), key=lambda x: x[1])),
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_region",
                    "Region",
                    choices=_region_choices,
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_income",
                    "Income group",
                    choices=_income_choices,
                    multiple=True,
                ),
                ui.input_selectize(
                    "filter_source",
                    "Source",
                    choices=_source_choices,
                    multiple=True,
                ),
                col_widths=(3, 3, 3, 3),
            ),
            # Document table
            ui.output_ui("doc_count_label"),
            ui.output_data_frame("doc_table"),
            # Pagination
            ui.layout_columns(
                ui.input_action_button("prev_page", "\u2190 Previous", width="100%"),
                ui.div(),
                ui.input_action_button("next_page", "Next \u2192", width="100%"),
                col_widths=(2, 8, 2),
            ),
        )

    # ── Filter state helper ──────────────────────────────────────
    def _current_filters() -> dict:
        sources = list(input.filter_source()) if input.filter_source() else None
        regions = list(input.filter_region()) if input.filter_region() else None
        income = list(input.filter_income()) if input.filter_income() else None
        codes = list(input.filter_country()) if input.filter_country() else None
        return {
            "sources": sources,
            "regions": regions,
            "income_groups": income,
            "country_codes": codes,
            "include_high_income": input.include_hi(),
        }

    # ── Document count label ─────────────────────────────────────
    @render.ui
    def doc_count_label():
        filters = _current_filters()
        total = count_documents(_con, **filters)
        page = browse_page()
        offset = page * 50
        end = min(offset + 50, total)
        return ui.p(
            ui.strong(f"{total:,} documents"),
            f", newest first (showing {offset + 1}--{end})",
        )

    # ── Document table ───────────────────────────────────────────
    @render.data_frame
    def doc_table():
        filters = _current_filters()
        page = browse_page()
        df = browse_documents(_con, limit=50, offset=page * 50, **filters)
        if df.empty:
            return render.DataGrid(pd.DataFrame({"Issuer": [], "Source": [], "Date": []}))
        display_df = pd.DataFrame(
            {
                "Issuer": df["display_name"],
                "Source": df["source"].map(source_display),
                "Date": df["publication_date"].apply(
                    lambda d: str(d)[:10] if pd.notna(d) else "undated"
                ),
            }
        )
        # Store document_ids for row click lookup
        display_df.attrs["_doc_ids"] = df["document_id"].tolist()
        return render.DataGrid(display_df, selection_mode="row", width="100%")

    # ── Row click -> detail view ─────────────────────────────────
    @reactive.effect
    def _handle_row_click():
        sel = doc_table.cell_selection()
        if sel and sel.get("rows"):
            row_idx = list(sel["rows"])[0]
            filters = _current_filters()
            page = browse_page()
            df = browse_documents(_con, limit=50, offset=page * 50, **filters)
            if row_idx < len(df):
                doc_id = int(df.iloc[row_idx]["document_id"])
                selected_doc_id.set(doc_id)
                current_view.set("detail")

    # ── Pagination ───────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.prev_page)
    def _prev():
        if browse_page() > 0:
            browse_page.set(browse_page() - 1)

    @reactive.effect
    @reactive.event(input.next_page)
    def _next():
        filters = _current_filters()
        total = count_documents(_con, **filters)
        if (browse_page() + 1) * 50 < total:
            browse_page.set(browse_page() + 1)

    # Reset page when filters change
    @reactive.effect
    def _reset_page():
        # Access all filter inputs to create dependency
        input.filter_source()
        input.filter_region()
        input.filter_income()
        input.filter_country()
        input.include_hi()
        browse_page.set(0)

    # ── Detail view builder ──────────────────────────────────────
    def _build_detail_view(inp: Inputs, doc_id: int) -> ui.Tag:
        detail = get_document_detail(_con, doc_id)
        if detail is None:
            return ui.div(
                ui.input_action_button("back_missing", "\u2190 Back to browse"),
                ui.p("Document not found."),
            )

        # Metadata
        meta_parts = [f"**Source:** {source_display(detail['source'])}"]
        pub_date = detail["publication_date"]
        if pub_date:
            meta_parts.append(f"**Date:** {str(pub_date)[:10]}")
        else:
            meta_parts.append("**Date:** undated")
        if detail["doc_type"]:
            meta_parts.append(f"**Type:** {detail['doc_type']}")
        meta_parts.append(f"**Country:** {detail['country_name']}")
        meta_parts.append(f"**Region:** {detail['region']}")

        filing_link = ""
        if detail["filing_url"]:
            filing_link = ext_link(detail["filing_url"], "View original filing")

        return ui.div(
            ui.input_action_button("back_btn", "\u2190 Back to browse"),
            ui.h1(detail["display_name"]),
            ui.markdown(" | ".join(meta_parts)),
            ui.HTML(filing_link) if filing_link else ui.div(),
            ui.hr(),
            # In-document search
            ui.input_text(
                "doc_search",
                "Search within this document",
                placeholder="Find text in this prospectus...",
            ),
            # Document body
            ui.output_ui("doc_body"),
        )

    # ── Back button ──────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.back_btn)
    def _back():
        current_view.set("browse")
        selected_doc_id.set(None)

    @reactive.effect
    @reactive.event(input.back_missing)
    def _back_missing():
        current_view.set("browse")
        selected_doc_id.set(None)

    # ── Document body rendering ──────────────────────────────────
    @render.ui
    def doc_body():
        doc_id = selected_doc_id()
        if doc_id is None:
            return ui.div()

        md_size = get_markdown_size(_con, doc_id)
        max_page = get_max_page(_con, doc_id)
        search_q = input.doc_search() if "doc_search" in input else ""

        has_markdown = md_size > 0
        has_pages = max_page > 0
        use_full_markdown = has_markdown and md_size < MARKDOWN_SIZE_LIMIT

        if not has_markdown and not has_pages:
            detail = get_document_detail(_con, doc_id)
            filing_url = detail["filing_url"] if detail else None
            parts = [ui.p(ui.em(
                "Full text not yet available -- this document is being processed."
            ))]
            if filing_url:
                parts.append(
                    ui.HTML(
                        "<p>In the meantime, you can "
                        + ext_link(filing_url, "view the original filing")
                        + ".</p>"
                    )
                )
            return ui.div(*parts)

        if use_full_markdown:
            return _render_full_markdown(doc_id, search_q)
        if has_pages:
            return _render_page_by_page(doc_id, max_page, search_q, input)
        # Markdown-only, over size limit
        return _render_full_markdown(doc_id, search_q)

    def _render_full_markdown(doc_id: int, search_query: str) -> ui.Tag:
        import re

        from explorer.highlight import highlight_text

        md_text = get_markdown(_con, doc_id)
        if not md_text:
            return ui.p(ui.em("No markdown available."))

        parts: list[ui.Tag] = []

        # ToC from headings
        headings = re.findall(r"^(#{2,3})\s+(.+)$", md_text, re.MULTILINE)
        if headings:
            toc_items = []
            for marker, title in headings:
                level = len(marker) - 2
                indent = "\u00a0\u00a0\u00a0\u00a0" * level
                toc_items.append(ui.tags.li(f"{indent}{title}"))
            parts.append(
                ui.accordion(
                    ui.accordion_panel(
                        "Table of Contents",
                        ui.tags.ul(*toc_items),
                    ),
                    open=False,
                )
            )

        if search_query:
            highlighted, count = highlight_text(
                md_text, search_query, return_count=True
            )
            if count > 100:
                parts.append(
                    ui.p(ui.em(f"{count} matches found -- showing first 100 highlights."))
                )
            elif count > 0:
                parts.append(ui.p(ui.em(f"{count} matches found.")))
            else:
                parts.append(ui.p(ui.em(f'"{search_query}" not found in this document.')))
            parts.append(ui.HTML(highlighted))
        else:
            parts.append(ui.markdown(md_text))

        return ui.div(*parts)

    def _render_page_by_page(
        doc_id: int, max_page: int, search_query: str, inp: Inputs
    ) -> ui.Tag:
        import html as html_mod

        from explorer.highlight import highlight_text

        parts: list[ui.Tag] = []

        # Search results
        if search_query:
            matching_pages = search_pages_in_document(_con, doc_id, search_query)
            if matching_pages:
                page_list = ", ".join(str(p) for p in matching_pages[:20])
                suffix = "..." if len(matching_pages) > 20 else ""
                parts.append(
                    ui.p(
                        ui.em(
                            f'Found "{search_query}" on '
                            f"{len(matching_pages)} pages: {page_list}{suffix}"
                        )
                    )
                )
            else:
                parts.append(
                    ui.p(ui.em(f'"{search_query}" not found in this document.'))
                )

        # Page selector
        page_key = f"page_sel_{doc_id}"
        parts.append(
            ui.input_numeric(page_key, f"Page (1--{max_page})", value=1, min=1, max=max_page)
        )

        page_num = inp[page_key]() if page_key in inp else 1
        page_num = max(1, min(page_num, max_page))

        text = get_page_text(_con, doc_id, page_num)
        if text:
            if search_query:
                escaped = html_mod.escape(text)
                highlighted, count = highlight_text(
                    escaped, search_query, return_count=True
                )
                parts.append(
                    ui.p(
                        ui.strong(f"Page {page_num} of {max_page}"),
                        f" ({count} matches on this page)",
                    )
                )
                if count > 0:
                    parts.append(ui.HTML(highlighted))
                else:
                    parts.append(ui.tags.pre(text))
            else:
                parts.append(ui.p(ui.strong(f"Page {page_num} of {max_page}")))
                parts.append(ui.tags.pre(text))
        else:
            parts.append(ui.p(ui.em(f"No text available for page {page_num}.")))

        return ui.div(*parts)


# ── App ──────────────────────────────────────────────────────────────

app = App(app_ui, server)
```

- [ ] **Step 3: Test locally**

Install shiny in the dev environment:

```bash
uv add --dev shiny
```

Run the app:

```bash
uv run shiny run shiny/app.py --port 8502
```

Open http://localhost:8502. Verify:
- Title and subtitle render
- Stats show (9,729 docs, 4 sources, 261 issuers)
- About expander opens and shows all content
- Filters appear (Country, Region, Income group, Source)
- Document table loads with Issuer, Source, Date columns
- Clicking a row navigates to detail view
- Back button returns to browse
- Pagination works

- [ ] **Step 4: Commit**

```bash
git add shiny/app.py shiny/requirements.txt
git commit -m "feat: Shiny for Python explorer with browse and detail views"
```

---

### Task 3: Test and Fix Edge Cases

**Files:**
- Modify: `shiny/app.py` (if fixes needed)

- [ ] **Step 1: Test the detail view**

Run the Shiny app and click into documents. Verify:
- Metadata row shows source, date, country, region
- "View original filing" link opens in new tab
- Full-markdown rendering with ToC for small docs
- Page-by-page rendering for large docs
- In-document search highlights matches
- Unparsed docs show "not yet available" message
- Back button works

- [ ] **Step 2: Test filters**

- Uncheck "Include high-income countries" -- Israel, UniCredit disappear
- Select a country -- table filters
- Select a source -- table filters
- Select multiple filters -- they AND together
- Clear filters -- table resets

- [ ] **Step 3: Fix any issues found**

Apply fixes directly to `shiny/app.py`.

- [ ] **Step 4: Run ruff**

```bash
uv run ruff check shiny/app.py
uv run ruff format --check shiny/app.py
```

Fix any issues.

- [ ] **Step 5: Commit**

```bash
git add shiny/app.py
git commit -m "fix: edge cases in Shiny explorer"
```

---

### Task 4: Deploy to Posit Connect Cloud

**Files:** No new files. This is deployment configuration.

- [ ] **Step 1: Push the branch**

```bash
git push origin feature/explorer-v2
```

- [ ] **Step 2: Deploy on Posit Connect Cloud**

1. Go to https://connect.posit.cloud
2. Click "Publish" -> "From GitHub"
3. Select framework: **Shiny**
4. Repository: `Teal-Insights/sovereign-prospectus-corpus`
5. Branch: `feature/explorer-v2`
6. Main file: `shiny/app.py`
7. Enable "Automatically publish on push"
8. Advanced settings:
   - Python version: 3.12
9. Configure variables:
   - Click "+ Add variable"
   - Name: `MOTHERDUCK_TOKEN`
   - Value: (paste the token from `.env`)
10. Sharing: **Public** (not Disabled)
11. Click **Publish**

- [ ] **Step 3: Verify the deployed app**

Open the public URL. Verify:
- Browse view loads with stats and filters
- Document table populates from MotherDuck
- Click into a document -- detail view renders
- In-document search works
- Back navigation works
- About expander content renders with all links

- [ ] **Step 4: Commit any deployment fixes**

If any fixes were needed, commit and push. Posit Connect Cloud
auto-deploys on push.

```bash
git add -A
git commit -m "fix: Posit Connect Cloud deployment adjustments"
git push
```

---

## Self-Review Checklist

**Spec coverage:**
- Browse view with logos, stats, About, filters, table: Task 2
- Detail view with metadata, filing link, hybrid rendering: Task 2
- In-document search: Task 2
- Shared display helpers: Task 1
- Posit Connect Cloud deployment: Task 4
- MotherDuck connection via env var: Task 2 (`get_connection`)
- Streamlit app unchanged: Task 1 Step 6 verifies

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code provided.

**Type consistency:** `source_display()` used consistently (not `_source_display`). `ext_link()` signature matches. All query imports match `explorer/queries.py`.
