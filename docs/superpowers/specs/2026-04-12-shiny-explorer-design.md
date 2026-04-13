# Shiny for Python Explorer -- Design Spec

**Date:** 2026-04-12
**Author:** Teal Emery + Claude
**Target:** Deploy alongside Streamlit app, sunset Streamlit once confirmed
**Branch:** `feature/explorer-v2`

## Context

The Streamlit explorer is live on Streamlit Cloud + MotherDuck for the
IMF/World Bank Spring Meetings demo. It works. But the team has more
experience with Shiny, already pays for shinyapps.io ($119/mo Standard
plan), and Posit Connect Cloud offers encrypted secrets, git-based
deployment, and auto-publish on push.

This spec defines a Shiny for Python port of the explorer that reuses the
existing query layer and deploys to Posit Connect Cloud in parallel. The
Streamlit app stays live until the Shiny version is confirmed working.

## Architecture

One Shiny for Python app (`shiny/app.py`) that imports directly from the
existing `explorer/` package. No code duplication -- the query layer,
highlight module, country metadata, and source display names are shared.

```
explorer/              # Shared data layer (existing)
  queries.py           # All DuckDB queries
  highlight.py         # Text highlighting + snippets
  country_metadata.py  # World Bank classifications
  issuer_country_map.py # Issuer-to-country mapping

shiny/                 # New Shiny UI layer
  app.py               # Shiny for Python app
  requirements.txt     # Deploy dependencies
```

### Connection

Same MotherDuck database (`sovereign_corpus`) as the Streamlit app.
Token read from `os.environ["MOTHERDUCK_TOKEN"]` -- set as an encrypted
secret variable in Posit Connect Cloud's publish UI.

Fallback to local `data/db/corpus.duckdb` for development. Same pattern
as the Streamlit app.

### Navigation

Three views matching the Streamlit app:

1. **Browse** (default) -- logos, stats, About expander, filters, document
   table with pagination
2. **Document Detail** -- metadata, filing link, hybrid markdown/page-by-page
   rendering, in-document search
3. **Search Results** -- hidden for now (FTS not available on MotherDuck).
   Can be added when a search solution is ready.

Navigation via Shiny reactive values, not session state hacks. Clicking
an issuer name sets `current_doc_id()`, which triggers the detail view.
Back button clears it, returning to browse.

## UI Components

### Browse View

**Header:** Teal Insights logo (left), title + subtitle (center),
NatureFinance logo (right). Use `ui.layout_columns()`.

**Stats row:** Three value boxes -- Documents, Sources, Issuers. Use
`ui.value_box()`.

**About expander:** Collapsible panel (`ui.accordion_panel()`) with:
- What this is, MIT license link, GitHub link
- Beta framing + co-design invitation
- What's next (3 bullets)
- 3 feedback questions + contact link

Content matches the Streamlit version exactly.

**Filters:** `ui.layout_columns()` with 4 columns:
1. Country (selectize input, searchable)
2. Region (multi-select)
3. Income group (multi-select)
4. Source (multi-select, human-readable names)

Plus "Include high-income countries" checkbox, unchecked by default.

**Document table:** Use `ui.output_data_frame()` with
`render.DataTable` or `render.DataGrid`. Columns: Issuer, Source, Date.
Clickable rows navigate to detail view. Pagination built-in (50 per page).

Issuer names displayed using `COALESCE(issuer_name, title, storage_key)`.
Source names mapped to human-readable: edgar -> "SEC EDGAR", nsm -> "FCA NSM",
luxse -> "Luxembourg Stock Exchange", pdip -> "#PublicDebtIsPublic".
Dates formatted as YYYY-MM-DD (no time).

Sort indicator: "newest first" shown above the table.

### Document Detail View

**Back button:** Returns to browse view.

**Header:** Document display name as heading.

**Metadata row:** Source, Date (or "undated"), Type (if present), Country,
Region.

**Filing link:** "View original filing" opening in new tab. Uses
`COALESCE(source_page_url, download_url)`.

**In-document search:** Text input that searches within the current
document using ILIKE (works on MotherDuck). Shows match count and
page list for page-by-page mode, highlights for full-markdown mode.

**Document body (hybrid rendering):**
- Full markdown mode: docs under 200KB markdown. Rendered as HTML.
  Table of Contents from `##` and `###` headings.
- Page-by-page mode: docs at or over 200KB, or docs with pages but no
  markdown. Number input for page selection. Prev/Next buttons.
- Unparsed docs: "Full text not yet available" + filing link.

### External Links

All external links open in new tabs. Use `ui.HTML()` with
`target="_blank" rel="noopener noreferrer"`.

## Shared Code

The Shiny app imports directly from the `explorer` package:

```python
from explorer.queries import (
    browse_documents, count_documents, get_corpus_stats,
    get_filter_options, get_document_detail, get_markdown,
    get_markdown_size, get_max_page, get_page_text,
    search_pages_in_document,
)
from explorer.highlight import highlight_text, extract_snippet
from explorer.app import _source_display, _SOURCE_DISPLAY_NAMES
```

The `_source_display` helper and `_SOURCE_DISPLAY_NAMES` dict should be
moved from `explorer/app.py` to `explorer/queries.py` (or a new
`explorer/display.py`) so both apps can import them without importing
Streamlit.

## Deployment

**Platform:** Posit Connect Cloud (free tier, migrating from shinyapps.io)

**Configuration:**
- Repository: `Teal-Insights/sovereign-prospectus-corpus`
- Branch: `feature/explorer-v2`
- Main file: `shiny/app.py`
- Python version: 3.12
- Auto-publish on push: enabled
- Sharing: Public

**Secret variables:**
- `MOTHERDUCK_TOKEN`: the MotherDuck access token

**Dependencies (`shiny/requirements.txt`):**
```
shiny>=1.0
duckdb==1.4.4
pandas>=2.0
```

**sys.path:** Same pattern as Streamlit -- add the repo root to sys.path
at the top of `shiny/app.py` so `from explorer.queries import ...` works.

## Null Handling

Same as Streamlit app:
- `COALESCE(issuer_name, title, storage_key)` for display names
- `NULLS LAST` in sort order
- "undated" for null publication_date
- "Unknown" for null country/region/income group
- LEFT JOIN sovereign_issuers (unmapped docs don't vanish)

## What This Is Not

- Not a rewrite of the query layer (reused as-is)
- Not a replacement for the Streamlit app (runs in parallel until confirmed)
- Not adding new features (parity with Streamlit, then iterate)

## Success Criteria

1. Browse view loads with logos, stats, About expander, filters, document table
2. Filters work (country, region, income group, source, high-income toggle)
3. Click into a document shows metadata, filing link, and document text
4. In-document search highlights matches
5. "View original filing" opens source website in new tab
6. Back navigation works without state bugs
7. Unparsed documents show fallback message
8. Deployed on Posit Connect Cloud with public URL
9. MotherDuck connection works via encrypted secret variable
10. Streamlit app continues working unchanged
