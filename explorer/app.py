"""Sovereign Bond Prospectus Explorer -- V2.

Full-text search across sovereign bond prospectuses with page-by-page
document detail view. Built for the IMF/World Bank Spring Meetings.

Open-source SovTech infrastructure by Teal Insights.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `from explorer.queries import ...`
# works on Streamlit Cloud, where the project isn't installed as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Sovereign Bond Prospectus Explorer",
    page_icon="\U0001f4dc",
    layout="wide",
)

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")
ASSETS_DIR = Path(__file__).parent / "assets"
MARKDOWN_SIZE_LIMIT = 200_000  # 200KB hard cutoff for full-markdown mode


# -- Connection ----------------------------------------------------------------


def _missing_db_error():
    st.error(
        "No database available. Set MOTHERDUCK_TOKEN in Streamlit secrets, "
        "or run locally with data/db/corpus.duckdb present."
    )
    st.stop()


@st.cache_resource(ttl=3600)
def get_connection():
    try:
        token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    except Exception:
        token = None
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
    if LOCAL_DB_PATH.exists():
        return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
    _missing_db_error()


@st.cache_data(ttl=3600)
def cached_filter_options(_con):
    from explorer.queries import get_filter_options

    return get_filter_options(_con)


@st.cache_data(ttl=3600)
def cached_corpus_stats(_con):
    from explorer.queries import get_corpus_stats

    return get_corpus_stats(_con)


# -- Shared display helpers (imported from explorer.display) --------------------

from explorer.display import (  # noqa: E402
    GITHUB_URL,
    PROTOTYPE_URL,
    QCRAFT_URL,
    ext_link,
    source_display,
)

# -- About expander ------------------------------------------------------------


def _render_about_expander():
    """Collapsible About section at the top of the browse view."""
    with st.expander("About this project"):
        st.markdown(
            "An open-source corpus of sovereign bond prospectuses collected from "
            "the FCA National Storage Mechanism, SEC EDGAR, "
            "the Sovereign Debt Forum's #PublicDebtIsPublic Dataset, and the "
            "Luxembourg Stock Exchange. Built by "
            + ext_link("https://tealinsights.com", "Teal Insights")
            + " with support from "
            + ext_link("https://naturefinance.net", "NatureFinance")
            + ". "
            + ext_link(GITHUB_URL, "GitHub")
            + " | "
            + ext_link(GITHUB_URL + "/blob/main/LICENSE", "MIT License")
            + ".",
            unsafe_allow_html=True,
        )
        st.markdown(
            "This is an early-stage beta with plenty of rough edges. "
            "It grew out of community feedback on a "
            + ext_link(PROTOTYPE_URL, "prototype proposal")
            + " for scaling clause identification in sovereign bond contracts. "
            "That feedback pointed to an immediate pain point: just finding and "
            "navigating prospectuses across multiple sources is hard. "
            "This explorer is a first down payment on what could become something "
            "much more powerful, with your input.",
            unsafe_allow_html=True,
        )

        st.markdown("**What's next?**")
        st.markdown(
            "- Automated updates as new prospectuses are filed\n"
            "- Filtering by document type (base prospectus, supplement, final terms, etc.)\n"
            "- Automated clause identification with expert validation "
            "(" + ext_link(PROTOTYPE_URL, "learn more") + ")\n"
            "- Part of a growing open-source SovTech ecosystem alongside "
            "tools like the "
            + ext_link(QCRAFT_URL, "Q-CRAFT Explorer")
            + " -- open-source tools that elevate the sovereign debt "
            "conversation by eliminating analytical toil",
            unsafe_allow_html=True,
        )

        st.markdown("**Help shape this tool**")
        st.markdown(
            "We're building this with the people who use sovereign debt data. "
            "If you have 2 minutes, we'd love to hear from you:"
        )
        st.markdown(
            "1. What are your biggest pain points in working with sovereign "
            "bond prospectuses?\n"
            "2. Are you a sovereign debt lawyer who might be interested in "
            '"lawyer-in-the-loop" validation to help automatically identify '
            "key clauses?\n"
            "3. Would you be willing to have a short conversation about how "
            "this tool could be more useful for your work?"
        )
        st.markdown(
            ext_link("mailto:lte@tealinsights.com", "Get in touch")
            + " or open an issue on "
            + ext_link(GITHUB_URL + "/issues", "GitHub")
            + ".",
            unsafe_allow_html=True,
        )


# -- Session state navigation --------------------------------------------------
# Every view transition MUST go through this function. It clears
# stale keys that would otherwise cause infinite redirects,
# wrong back-button labels, or stale page selectors.

_DETAIL_KEYS = {
    "doc_id",
    "start_page",
    "current_page",
    "page_selector",
    "doc_search",
    "nav_origin",
}
_SEARCH_KEYS = {"search_query", "search_query_submitted"}
_BROWSE_KEYS = {"browse_page"}


def _navigate_to(view: str, **extra):
    """Set view and clean up stale session state from other views."""
    keys_to_clear: set[str] = set()
    if view == "browse":
        keys_to_clear = _SEARCH_KEYS | _DETAIL_KEYS
    elif view == "search":
        keys_to_clear = set(_DETAIL_KEYS)
    elif view == "detail":
        # Clear previous detail state but keep search keys (for back nav)
        keys_to_clear = set(_DETAIL_KEYS)

    for k in keys_to_clear:
        st.session_state.pop(k, None)
    # Also clean up dynamic page_selector_{doc_id} keys
    for k in list(st.session_state.keys()):
        if k.startswith("page_selector_"):
            del st.session_state[k]

    st.session_state["view"] = view
    for k, v in extra.items():
        st.session_state[k] = v
    st.rerun()


# -- Filters -------------------------------------------------------------------


def render_filters(con) -> dict:
    """Render filter widgets and return current filter state."""
    opts = cached_filter_options(con)

    include_hi = st.checkbox("Include high-income countries", value=False)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        country_labels = {code: name for code, name in opts["countries"]}
        selected_country_names = st.multiselect("Country", sorted(country_labels.values()))
        selected_codes = [
            code for code, name in country_labels.items() if name in selected_country_names
        ]
    with col2:
        selected_regions = st.multiselect("Region", opts["regions"])
    with col3:
        selected_income = st.multiselect("Income group", opts["income_groups"])
    with col4:
        source_display_to_key = {source_display(s): s for s in opts["sources"]}
        selected_display_sources = st.multiselect("Source", list(source_display_to_key.keys()))
        selected_sources = [source_display_to_key[d] for d in selected_display_sources]

    # Reset browse pagination when filters change
    current_filter_sig = (
        tuple(selected_sources),
        tuple(selected_regions),
        tuple(selected_income),
        tuple(selected_codes),
        include_hi,
    )
    if st.session_state.get("_last_filter_sig") != current_filter_sig:
        st.session_state["browse_page"] = 0
        st.session_state["_last_filter_sig"] = current_filter_sig

    return {
        "sources": selected_sources or None,
        "include_high_income": include_hi,
        "income_groups": selected_income or None,
        "regions": selected_regions or None,
        "country_codes": selected_codes or None,
    }


# -- Browse view ---------------------------------------------------------------


def browse_view(con):
    """Landing page: logos, stats, about expander, filters, document table."""
    # Header with logos
    logo_col1, title_col, logo_col2 = st.columns([1, 4, 1])
    with logo_col1:
        logo = ASSETS_DIR / "teal-insights-logo.png"
        if logo.exists():
            st.image(str(logo), width=120)
    with logo_col2:
        logo = ASSETS_DIR / "naturefinance-logo.png"
        if logo.exists():
            st.image(str(logo), width=120)
    with title_col:
        st.title("Sovereign Bond Prospectus Explorer")
        st.markdown(
            "_Browse 9,700+ sovereign bond prospectuses from "
            "4 public sources. Open-source SovTech infrastructure for "
            "sovereign debt research._"
        )

    # Stats
    stats = cached_corpus_stats(con)
    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", f"{stats['docs']:,}")
    col2.metric("Sources", stats["sources"])
    col3.metric("Issuers", f"{stats['issuers']:,}")

    # About expander -- visible at top, collapsed by default
    _render_about_expander()

    # Filters
    filters = render_filters(con)

    # Document table
    from explorer.queries import browse_documents, count_documents

    page = st.session_state.get("browse_page", 0)
    limit = 50
    offset = page * limit

    total = count_documents(con, **filters)
    df = browse_documents(con, limit=limit, offset=offset, **filters)

    if df.empty:
        st.info("No documents match these filters.")
        return

    st.markdown(
        f"**{total:,} documents**, newest first (showing {offset + 1}--{offset + len(df)})"
    )

    # Column headers
    hdr_name, hdr_source, hdr_date = st.columns([3, 1, 1])
    with hdr_name:
        st.markdown("**Issuer**")
    with hdr_source:
        st.markdown("**Source**")
    with hdr_date:
        st.markdown("**Date**")

    for _idx, row in df.iterrows():
        col_name, col_source, col_date = st.columns([3, 1, 1])
        with col_name:
            if st.button(
                row["display_name"],
                key=f"browse_{row['document_id']}",
                use_container_width=True,
            ):
                _navigate_to(
                    "detail",
                    doc_id=row["document_id"],
                    nav_origin="browse",
                )
        with col_source:
            st.caption(source_display(row["source"]))
        with col_date:
            date = row["publication_date"]
            date_str = str(date)[:10] if pd.notna(date) else "undated"
            st.caption(date_str)

    # Pagination
    pcol1, _pcol2, pcol3 = st.columns([1, 2, 1])
    with pcol1:
        if page > 0 and st.button("\u2190 Previous"):
            st.session_state["browse_page"] = page - 1
            st.rerun()
    with pcol3:
        if offset + limit < total and st.button("Next \u2192"):
            st.session_state["browse_page"] = page + 1
            st.rerun()


# -- Stubs (replaced in Tasks 4 and 5) ----------------------------------------
# These MUST be defined before main() to avoid NameError on first rerun.


def search_view(con):
    """Full-text search results."""
    query = st.session_state.get("search_query_submitted", "")

    if st.button("\u2190 Back to browse"):
        _navigate_to("browse")

    st.subheader(f'Search results for "{query}"')

    # Filters (same as browse)
    filters = render_filters(con)

    if not query:
        st.info("Enter a search term.")
        return

    from explorer.highlight import extract_snippet, highlight_text
    from explorer.queries import search_documents

    with st.spinner("Searching..."):
        try:
            results = search_documents(con, query, limit=50, **filters)
        except Exception:
            st.warning(
                "Full-text search index is not available. "
                "Browse mode still works -- use the back button to browse documents."
            )
            return

    if results.empty:
        st.warning(f'No results for "{query}". Try different terms or adjust filters.')
        return

    # Only say "showing top 50" if we actually hit the limit
    if len(results) >= 50:
        st.markdown(f"**Showing top 50 results** for `{query}`")
    else:
        st.markdown(f"**{len(results)} results** for `{query}`")

    for _, row in results.iterrows():
        display = row["display_name"]
        source = source_display(row["source"])
        date = row["publication_date"]
        date_str = str(date)[:10] if pd.notna(date) else "undated"
        page_num = row["page_number"]

        with st.expander(f"**{display}** -- {source} -- p.{page_num} -- {date_str}"):
            import html as html_mod

            snippet = extract_snippet(row["page_text"] or "", query)
            highlighted = highlight_text(html_mod.escape(snippet), query)
            st.markdown(highlighted, unsafe_allow_html=True)

            if st.button(
                "View full document",
                key=f"search_{row['document_id']}_{page_num}",
            ):
                _navigate_to(
                    "detail",
                    doc_id=row["document_id"],
                    start_page=int(page_num),
                    nav_origin="search",
                )


def detail_view(con):
    """Document detail: metadata, filing link, markdown/page rendering."""
    doc_id = st.session_state.get("doc_id")
    if doc_id is None:
        _navigate_to("browse")
        return

    from explorer.queries import (
        get_document_detail,
        get_markdown_size,
        get_max_page,
    )

    detail = get_document_detail(con, doc_id)
    if detail is None:
        st.error(f"Document {doc_id} not found.")
        if st.button("\u2190 Back"):
            _navigate_to("browse")
        return

    # Back button -- use nav_origin to determine correct target
    nav_origin = st.session_state.get("nav_origin", "browse")
    back_label = (
        "\u2190 Back to search results" if nav_origin == "search" else "\u2190 Back to browse"
    )
    if st.button(back_label):
        _navigate_to(nav_origin)

    # Header
    st.title(detail["display_name"])

    # Metadata row
    meta_parts = [f"**Source:** {source_display(detail['source'])}"]
    if detail["publication_date"]:
        meta_parts.append(f"**Date:** {detail['publication_date']}")
    else:
        meta_parts.append("**Date:** undated")
    if detail["doc_type"]:
        meta_parts.append(f"**Type:** {detail['doc_type']}")
    meta_parts.append(f"**Country:** {detail['country_name']}")
    meta_parts.append(f"**Region:** {detail['region']}")
    st.markdown(" | ".join(meta_parts))

    # Filing link
    if detail["filing_url"]:
        st.markdown(
            ext_link(detail["filing_url"], "View original filing"),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # In-document search
    doc_search = st.text_input(
        "Search within this document",
        key="doc_search",
        placeholder="Find text in this prospectus...",
    )

    # Determine rendering mode
    md_size = get_markdown_size(con, doc_id)
    max_page = get_max_page(con, doc_id)
    start_page = st.session_state.get("start_page", 1)

    has_markdown = md_size > 0
    has_pages = max_page > 0
    use_full_markdown = has_markdown and md_size < MARKDOWN_SIZE_LIMIT

    if not has_markdown and not has_pages:
        # Unparsed document
        st.info("Full text not yet available -- this document is being processed.")
        if detail["filing_url"]:
            st.markdown(
                "In the meantime, you can "
                + ext_link(detail["filing_url"], "view the original filing")
                + ".",
                unsafe_allow_html=True,
            )
        return

    if use_full_markdown:
        _render_full_markdown(con, doc_id, doc_search)
    elif has_pages:
        _render_page_by_page(con, doc_id, max_page, start_page, doc_search)
    else:
        # Markdown-only, over size limit -- force render anyway (5 docs)
        _render_full_markdown(con, doc_id, doc_search)


def _render_full_markdown(con, doc_id: int, search_query: str):
    """Render full markdown with optional highlighting and ToC."""
    import re

    from explorer.queries import get_markdown

    md_text = get_markdown(con, doc_id)
    if not md_text:
        st.info("No markdown available.")
        return

    # Extract headings for ToC
    headings = re.findall(r"^(#{2,3})\s+(.+)$", md_text, re.MULTILINE)
    if headings:
        with st.expander("Table of Contents", expanded=False):
            for marker, title in headings:
                level = len(marker) - 2  # ## = 0 indent, ### = 1 indent
                indent = "\u00a0\u00a0\u00a0\u00a0" * level
                st.markdown(f"{indent}\u2022 {title}")

    # Highlight search terms if present
    if search_query:
        from explorer.highlight import highlight_text

        highlighted, count = highlight_text(md_text, search_query, return_count=True)
        if count > 100:
            st.info(f"{count} matches found -- showing first 100 highlights.")
        elif count > 0:
            st.info(f"{count} matches found.")
        else:
            st.warning(f'"{search_query}" not found in this document.')
        st.markdown(highlighted, unsafe_allow_html=True)
    else:
        st.markdown(md_text)


def _render_page_by_page(con, doc_id: int, max_page: int, start_page: int, search_query: str):
    """Render one page at a time with navigation."""
    from explorer.queries import get_page_text, search_pages_in_document

    # Page-level search results
    if search_query:
        matching_pages = search_pages_in_document(con, doc_id, search_query)
        if matching_pages:
            st.info(
                f'Found "{search_query}" on {len(matching_pages)} pages: '
                + ", ".join(str(p) for p in matching_pages[:20])
                + ("..." if len(matching_pages) > 20 else "")
            )
            # Buttons to jump to matching pages
            cols = st.columns(min(len(matching_pages), 10))
            for i, pg in enumerate(matching_pages[:10]):
                with cols[i]:
                    if st.button(f"p.{pg}", key=f"jump_{pg}"):
                        st.session_state["current_page"] = pg
                        st.rerun()
        else:
            st.warning(f'"{search_query}" not found in this document.')

    # Clamp start_page to valid range (prevents stale state crash)
    initial_page = max(1, min(start_page, max_page))
    page_num = st.session_state.get("current_page", initial_page)
    page_num = max(1, min(page_num, max_page))  # Double-clamp for safety

    # Use a key namespaced by doc_id to prevent stale values across documents
    page_num = st.number_input(
        f"Page (1--{max_page})",
        min_value=1,
        max_value=max_page,
        value=page_num,
        key=f"page_selector_{doc_id}",
    )
    st.session_state["current_page"] = page_num

    text = get_page_text(con, doc_id, page_num)
    if text:
        if search_query:
            import html as html_mod

            from explorer.highlight import highlight_text

            escaped_text = html_mod.escape(text)
            highlighted, count = highlight_text(escaped_text, search_query, return_count=True)
            st.markdown(f"**Page {page_num} of {max_page}** ({count} matches on this page)")
            if count > 0:
                st.markdown(highlighted, unsafe_allow_html=True)
            else:
                st.text(text)
        else:
            st.markdown(f"**Page {page_num} of {max_page}**")
            st.text(text)
    else:
        st.info(f"No text available for page {page_num}.")

    # Prev/Next
    nav1, nav2 = st.columns(2)
    with nav1:
        if page_num > 1 and st.button("\u2190 Previous page"):
            st.session_state["current_page"] = page_num - 1
            st.rerun()
    with nav2:
        if page_num < max_page and st.button("Next page \u2192"):
            st.session_state["current_page"] = page_num + 1
            st.rerun()


# -- Main ----------------------------------------------------------------------


def main():
    con = get_connection()

    view = st.session_state.get("view", "browse")

    if view == "detail":
        detail_view(con)
    elif view == "search":
        search_view(con)
    else:
        browse_view(con)


if __name__ == "__main__":
    main()
