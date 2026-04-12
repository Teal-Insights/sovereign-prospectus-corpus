"""Sovereign Bond Prospectus Explorer -- V2.

Full-text search across sovereign bond prospectuses with page-by-page
document detail view. Built for the IMF/World Bank Spring Meetings.

Open-source SovTech infrastructure by Teal Insights.
"""

from __future__ import annotations

from pathlib import Path

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
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        con = duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )
        con.execute("INSTALL fts; LOAD fts")
        return con
    if LOCAL_DB_PATH.exists():
        con = duckdb.connect(str(LOCAL_DB_PATH), read_only=True)
        con.execute("INSTALL fts; LOAD fts")
        return con
    _missing_db_error()


@st.cache_data(ttl=3600)
def cached_filter_options(_con):
    from explorer.queries import get_filter_options

    return get_filter_options(_con)


@st.cache_data(ttl=3600)
def cached_corpus_stats(_con):
    from explorer.queries import get_corpus_stats

    return get_corpus_stats(_con)


# -- External link helper ------------------------------------------------------


def ext_link(url: str, text: str) -> str:
    """HTML for an external link that opens in a new tab."""
    return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{text} \u2197</a>'


# -- Session state navigation --------------------------------------------------
# Every view transition MUST go through this function. It clears
# stale keys that would otherwise cause infinite redirects,
# wrong back-button labels, or stale page selectors.

_DETAIL_KEYS = {"doc_id", "start_page", "current_page", "page_selector", "doc_search"}
_SEARCH_KEYS = {"search_query", "search_query_submitted"}
_BROWSE_KEYS = {"browse_page"}


def _navigate_to(view: str, **extra):
    """Set view and clean up stale session state from other views."""
    if view == "browse":
        for k in _SEARCH_KEYS | _DETAIL_KEYS:
            st.session_state.pop(k, None)
    elif view == "search":
        for k in _DETAIL_KEYS:
            st.session_state.pop(k, None)
    elif view == "detail":
        # Clear previous detail state but keep search keys (for back nav)
        for k in _DETAIL_KEYS:
            st.session_state.pop(k, None)

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
        selected_sources = st.multiselect("Source", opts["sources"])
    with col2:
        selected_regions = st.multiselect("Region", opts["regions"])
    with col3:
        selected_income = st.multiselect("Income group", opts["income_groups"])
    with col4:
        country_labels = {code: name for code, name in opts["countries"]}
        selected_country_names = st.multiselect("Country", sorted(country_labels.values()))
        selected_codes = [
            code for code, name in country_labels.items() if name in selected_country_names
        ]

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
    """Landing page: logos, stats, search, filters, document table."""
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
            "_Search and browse 9,700+ sovereign bond prospectuses from "
            "4 public sources. Open-source SovTech infrastructure for "
            "sovereign debt research._"
        )

    # Stats
    stats = cached_corpus_stats(con)
    col1, col2, col3 = st.columns(3)
    col1.metric("Documents", f"{stats['docs']:,}")
    col2.metric("Sources", stats["sources"])
    col3.metric("Issuers", f"{stats['issuers']:,}")

    # Search bar -- use a form to prevent the text_input's persisted value
    # from triggering an infinite redirect back to search when the user
    # navigates back to browse. The form only submits on Enter/button click.
    with st.form("search_form", clear_on_submit=True):
        query = st.text_input(
            "Search prospectus text",
            placeholder="e.g., collective action clause, governing law, contingent liabilities",
        )
        submitted = st.form_submit_button("Search")
    if submitted and query:
        _navigate_to("search", search_query_submitted=query)

    # Filters
    filters = render_filters(con)

    # Document table
    from explorer.queries import browse_documents, count_documents

    page = st.session_state.get("browse_page", 0)
    limit = 50
    offset = page * limit

    total = count_documents(con, **filters)
    df = browse_documents(con, limit=limit, offset=offset, **filters)

    st.markdown(f"**{total:,} documents** (showing {offset + 1}--{offset + len(df)})")

    if not df.empty:
        # Make display_name clickable
        for _idx, row in df.iterrows():
            col_name, col_source, col_date, col_type = st.columns([3, 1, 1, 1])
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
                st.caption(row["source"])
            with col_date:
                date = row["publication_date"]
                st.caption(str(date) if pd.notna(date) else "undated")
            with col_type:
                st.caption(row["doc_type"] if pd.notna(row["doc_type"]) else "")

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

    # About section
    st.markdown("---")
    st.markdown(
        "**What is this?** An open-source, searchable corpus of sovereign bond "
        "prospectuses collected from the FCA National Storage Mechanism, SEC EDGAR, "
        "the Sovereign Debt Forum's #PublicDebtIsPublic Dataset, and the Luxembourg "
        "Stock Exchange. Built by "
        + ext_link("https://tealinsights.com", "Teal Insights")
        + " with support from "
        + ext_link("https://naturefinance.net", "NatureFinance")
        + ', as part of an emerging "SovTech" approach -- open-source '
        "infrastructure for sovereign debt markets.",
        unsafe_allow_html=True,
    )
    st.markdown(
        "This explorer grew out of community feedback on a "
        + ext_link(
            "https://teal-insights.github.io/sovereign-prospectus-corpus/",
            "prototype proposal",
        )
        + " for scaling up clause identification in sovereign bond contracts. "
        "That feedback pointed to lower-hanging fruit that solves real pain points "
        "immediately: make it easy to find and navigate the prospectuses themselves.",
        unsafe_allow_html=True,
    )
    st.markdown(
        "**Why?** The contract terms that govern how nations borrow, restructure, "
        "and default are buried in dense prospectuses scattered across multiple "
        "websites. This explorer brings them together in one searchable place."
    )
    st.markdown(
        "**This is public infrastructure being built in the open.** "
        "We're building this with the people who use this data. "
        "What would make this useful for your work? "
        + ext_link("mailto:teal@tealinsights.com", "Get in touch"),
        unsafe_allow_html=True,
    )


# -- Stubs (replaced in Tasks 4 and 5) ----------------------------------------
# These MUST be defined before main() to avoid NameError on first rerun.


def search_view(con):
    """Stub -- replaced in Task 4."""
    st.warning("Search view not yet implemented")
    if st.button("\u2190 Back"):
        _navigate_to("browse")


def detail_view(con):
    """Stub -- replaced in Task 5."""
    st.warning("Detail view not yet implemented")
    if st.button("\u2190 Back"):
        _navigate_to("browse")


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
