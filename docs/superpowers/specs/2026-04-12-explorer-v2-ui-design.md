# Explorer V2 UI Design Spec

**Date:** 2026-04-12
**Author:** Teal Emery + Claude
**Target:** IMF/World Bank Spring Meetings demo, Monday 2026-04-13 afternoon
**Branch:** `feature/explorer-v2`

## Context

Two weeks ago, Teal presented a V1 prototype at the Georgetown roundtable --
a Quarto book proposing a way to scale clause identification using PDIP's
expert annotations as a foundation. The feedback was clear: "Give us a way to
navigate and find new prospectuses in one spot." This explorer is the response.

The audience tomorrow is the IMF Legal Department and the Deputy Division
Chief of the Monetary and Capital Markets Department. Friendly, informal,
already interested. They currently use expensive subscription services that
give them prospectus access but no search, no structured navigation -- just
PDFs they have to download and Ctrl+F manually.

The goal is not to look "done." The goal is to show momentum: I heard you, I
built it, here it is. And to invite co-design: the people who use this data
should shape how it works.

## Framing

This is open-source SovTech -- public infrastructure for sovereign debt
markets, not a product pitch. The tone matches the V1 Quarto book: confident,
collaborative, public-interest. "This is public infrastructure being built in
the open."

## Data Available

- 9,729 documents across 4 sources (LuxSE 4,955, EDGAR 3,301, PDIP 823, NSM 650)
- 4,857 docs with page-level text (196,699 pages total)
- 4,862 docs with Docling markdown
- Dates from 1990 to April 2026
- Provenance URLs for EDGAR (SEC filing index), NSM (FCA artifact page),
  PDIP (Georgetown search page) -- 4,774 docs. LuxSE has PDF download URLs
  but no source page URLs.
- No country metadata yet (document_countries table is empty). Will be built
  as part of this work via a sovereign issuer lookup table.

## Architecture: Three Views

One Streamlit app, three views managed via `st.session_state`. No multi-page
routing.

### View 1: Browse (landing/default)

**Above the fold, top to bottom:**

1. **Header bar:** Teal Insights logo (left) + NatureFinance logo (right),
   small and professional.
2. **Title:** "Sovereign Bond Prospectus Explorer"
3. **One-liner:** "Search and browse 9,700+ sovereign bond prospectuses from
   4 public sources. Open-source SovTech infrastructure for sovereign debt
   research."
4. **Stats row:** three `st.metric` cards -- document count, source count,
   issuers count.
5. **Search bar:** prominent, full-width. Placeholder: "Search prospectus
   text (e.g., collective action clause, governing law)". Pressing enter
   transitions to search results.
6. **Filter row:** below search bar.
   - Source multi-select (NSM, EDGAR, PDIP, LuxSE)
   - Region dropdown (World Bank regions + "All")
   - Income group dropdown
   - "Include high-income countries" checkbox -- **unchecked by default**.
     One click to include. This filters out Israel (1,155 docs),
     Bank of Cyprus (~619), UniCredit (~789), and other high-income/corporate
     noise that isn't relevant to this audience.
   - Country searchable dropdown (type-ahead)
7. **Document table:** newest first. Columns: issuer name, source, date,
   doc type. Clickable rows open the document detail view. Paginated, 50 per
   page.

**Below the table -- About section:**

> **What is this?** An open-source, searchable corpus of sovereign bond
> prospectuses collected from the FCA National Storage Mechanism, SEC EDGAR,
> the Sovereign Debt Forum's #PublicDebtIsPublic Dataset, and the Luxembourg
> Stock Exchange. Built by [Teal Insights](https://tealinsights.com) with
> support from [NatureFinance](https://naturefinance.net), as part of an
> emerging "SovTech" approach -- open-source infrastructure for sovereign debt
> markets.
>
> This explorer grew out of community feedback on a
> [prototype proposal](https://teal-insights.github.io/sovereign-prospectus-corpus/)
> for scaling up clause identification in sovereign bond contracts. That
> feedback pointed to lower-hanging fruit that solves real pain points
> immediately: make it easy to find and navigate the prospectuses themselves.
>
> **Why?** The contract terms that govern how nations borrow, restructure,
> and default are buried in dense prospectuses scattered across multiple
> websites. This explorer brings them together in one searchable place.
>
> **This is public infrastructure being built in the open.** We're building
> this with the people who use this data. What would make this useful for your
> work? [Get in touch.](mailto:teal@tealinsights.com)

Teal will wordsmith the About section text. The structure and tone are the
target.

### View 2: Search Results

Triggered when user enters a query in the search bar.

- **BM25 full-text search** via DuckDB FTS on `document_pages.page_text`
- Results **grouped by document** using a CTE with window function:
  `ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY score DESC)` to get
  the best-matching page per document, then fetch only the top 50 snippets.
  This ordering (rank first, fetch snippets second) is critical -- the
  reverse (snippets first, then rank) measured 12x slower in testing.
- Each result shows: issuer name (with `COALESCE(issuer_name, title,
  storage_key)` fallback for 215 docs with no issuer), source badge,
  publication date, and a 2-3 line text snippet with the search term in
  context. Snippets extracted in Python (DuckDB FTS has no built-in
  snippet function): find search term in `page_text`, grab ~200 chars of
  surrounding context.
- Filters (source, region, income group, country) apply to search results.
  Filter dropdown values cached with `@st.cache_data`.
- Click a result to open document detail view at the matching page
- 50 results cap with a note ("Showing top 50 results") if more exist
- "No results" state with helpful suggestion text
- Show `st.spinner` during search -- expect ~1-1.5s warm, ~3s cold

### View 3: Document Detail

Opened when clicking a document from browse or search results.

**Header:**
- Document title / issuer name (large heading) -- use same COALESCE chain
- Metadata row: source, date (or "undated"), doc type (or omit if null)
- **"View original filing ↗"** link -- opens source page URL in new tab
  (`target="_blank" rel="noopener noreferrer"`). For LuxSE (no source page
  URL), link to the PDF download URL. The `↗` signals new-tab behavior.
  All external links throughout the app open in new tabs.

**In-document search:**
- Search box at top of document body: "Search within this document"
- On search: highlight matches with `<mark>` tags via regex-safe replacement
  (must skip HTML tags/attributes to avoid breaking links or markdown syntax),
  show match count ("12 matches found")
- **Cap at 100 highlights** to prevent HTML bloat from stop-word searches
  ("the", "and"). Show "100+ matches -- showing first 100 highlights."
- No anchor-based jump navigation. Streamlit does not support in-page
  `#anchor` links -- they trigger full app reruns. Instead: match count +
  highlights only for full-markdown mode; match count + page list for
  page-by-page mode.

**Document body (hybrid rendering):**

- **Full markdown mode** (docs under 200KB markdown -- hard cutoff enforced
  before rendering): render the complete Docling markdown as scrollable
  content. If the markdown has `##` headings, render a ToC in `st.sidebar`
  or an expander with heading list. Covers ~67% of docs (3,256 under 100KB
  + portion of the 1,112 in 100-500KB range).
- **Page-by-page mode** (docs at or over 200KB, or docs with pages but no
  markdown): `st.number_input` page selector (not slider -- corpus max is
  4,108 pages). Show one page at a time. In-document search shows "Found on
  pages 3, 17, 42" as clickable page-load buttons. Current page gets inline
  highlighting.
- **Markdown-only docs** (5 docs with markdown but no pages): render in
  full markdown mode regardless of size. In-document search uses the
  markdown text directly.
- Page count for navigation derived from `SELECT MAX(page_number) FROM
  document_pages WHERE document_id = ?`, not from `documents.page_count`
  (which is NULL for all rows).

The Congo prospectus (~150 pages, well under 200KB) gets full-markdown with
ToC -- that's the demo moment.

**Back navigation:** "Back to results" or "Back to browse" button at top,
depending on how they arrived.

## Country Metadata: Sovereign Issuer Lookup Table

A new `sovereign_issuers` reference table mapping each distinct issuer name
in the corpus to standardized metadata:

| Column | Example |
|--------|---------|
| `issuer_name` | REPUBLIC OF TURKEY |
| `country_name` | Turkey |
| `country_code` | TUR (ISO 3166-1 alpha-3) |
| `region` | Europe & Central Asia (World Bank regions) |
| `income_group` | Upper middle income |
| `lending_category` | IBRD |

261 distinct issuer names in the corpus (not ~150 as initially estimated).
Many are the same country with different formatting ("REPUBLIC OF TURKEY"
vs "TURKIYE (THE REPUBLIC OF)") or are corporate issuers
("UNICREDIT S.P.A.", "BANK OF CYPRUS") that need `is_sovereign = false`.

**Implementation:** Hard-coded Python dict mapping each issuer name to
`(country_code, country_name)`. No fuzzy matching -- too error-prone
("Georgia" = country or US state? "Bank of Cyprus" = sovereign?).
Claude drafts the mapping, Teal verifies. World Bank API or static CSV
provides the country_code-to-region/income_group/lending_category join.

Existing source-native IDs can help: EDGAR stores `cik`, PDIP stores
`country`, NSM stores `lei`. These are secondary validation, not primary.

This table is joined at query time via `LEFT JOIN` (not INNER -- docs
without a mapped issuer must not vanish). `COALESCE` null regions/income
groups to "Unknown" for filter dropdowns (Streamlit multiselect crashes
on None values mixed with strings). Filter dropdown values cached with
`@st.cache_data`.

## External Links

All external links open in new tabs. Implementation via raw HTML in
`st.markdown(..., unsafe_allow_html=True)`:

```html
<a href="https://..." target="_blank" rel="noopener noreferrer">
  View original filing ↗
</a>
```

Applied to: source page URLs, PDF download links, PDIP/Georgetown links,
Teal Insights website, NatureFinance website, V1 Quarto book link.

## Logos

Existing assets:
- `demo/images/teal-insights-logo.png`
- `demo/images/naturefinance-logo.png`

Copy to `explorer/assets/` for the Streamlit app.

## Tech Stack

- Streamlit (already deployed as spike on Streamlit Cloud)
- DuckDB local + MotherDuck for cloud deployment
- DuckDB FTS extension for BM25 search
- Pandas OK in explorer/ (per CLAUDE.md)
- `st.markdown` with `unsafe_allow_html=True` for custom HTML (links,
  highlighting)

## Null Handling

The corpus has significant null values that must be handled throughout:

| Field | Null count | Handling |
|-------|-----------|----------|
| `issuer_name` | 215 | `COALESCE(issuer_name, title, storage_key)` everywhere |
| `publication_date` | 814 | `NULLS LAST` in sort, show "undated" in UI |
| `doc_type` | 664 | Show "Unknown" or omit from display |
| `title` | 71 | Falls through to storage_key via COALESCE chain |
| `source_page_url` | 4,955 (all LuxSE) | Fall through to `download_url` |
| `documents.page_count` | 9,729 (all) | Never use; derive from `MAX(page_number)` |
| `page_text` (no pages) | 4,872 docs | "Not yet available" fallback |
| `markdown_text` (no md) | 4,867 docs | Page-by-page or "not yet available" |

## MotherDuck FTS Risk

DuckDB's FTS extension creates shadow tables (`fts_main_document_pages`
etc.) that are local artifacts. These may not survive upload to MotherDuck.

**Mitigation:** After publishing to MotherDuck, connect to MotherDuck and
run `build_fts_index()` against the remote connection. If this fails,
the explorer falls back to local DuckDB (which always has the index).
Test this before the demo.

The `@st.cache_resource(ttl=3600)` connection pattern handles MotherDuck
cold start (~5-8s for first load after Streamlit Cloud sleep). Open the
app 5 minutes before the demo to warm it up.

## Graceful Fallback for Unparsed Documents

About half the corpus (mostly EDGAR) is still being parsed overnight. These
documents have metadata (issuer, source, date, doc type) but no page text or
markdown yet. The explorer handles this gracefully:

- **Browse table:** Unparsed docs appear normally in the table (they have
  metadata). No visual distinction needed -- they're real documents.
- **Search:** BM25 search only hits `document_pages`, so unparsed docs
  won't appear in search results. That's correct behavior, not a bug.
- **Document detail view:** When someone clicks into an unparsed document,
  show the metadata header and provenance link as normal, but instead of
  document text show:
  "Full text not yet available -- this document is being processed.
  In the meantime, you can [view the original filing ↗](source_url)."
- This naturally resolves once the overnight parse completes and we re-ingest.

## What This Is Not

- Not clause extraction (that's V1 / future work)
- Not a product -- open-source public infrastructure
- Not trying to look finished -- showing momentum and inviting co-design
- Not replacing the original source websites -- provenance links are
  first-class, one click to verify

## Success Criteria (for tomorrow's demo)

1. Landing page loads with logos, stats, search bar, and document table
2. Search "collective action" returns relevant results across multiple
   issuers with text snippets
3. Search "contingent liabilities" finds the Congo prospectus (demo moment)
4. Click into Congo prospectus, see nicely rendered markdown with ToC
5. "View original filing" link opens source website in new tab
6. In-document search highlights terms within a prospectus
7. Filters by region/income group work -- excluding high-income by default
   visibly reduces noise
8. About section communicates SovTech framing and invites co-design
9. Works from a shareable URL (Streamlit Cloud + MotherDuck)
10. Works on phone (basic layout -- doesn't need to be perfect)
