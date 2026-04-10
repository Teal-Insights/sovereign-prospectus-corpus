"""Sovereign Bond Prospectus Explorer — deployment spike.

Minimal Streamlit app that connects to MotherDuck (cloud) or falls back
to a local DuckDB file, then renders a table of document metadata.
"""

import duckdb
import streamlit as st

st.set_page_config(
    page_title="Sovereign Bond Prospectus Explorer",
    page_icon="📜",
    layout="wide",
)


@st.cache_resource
def get_connection():
    """Connect to MotherDuck if token is available, else fall back to local DB."""
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        return duckdb.connect(f"md:sovereign_corpus?motherduck_token={token}")
    else:
        st.warning("No MotherDuck token found. Using local DuckDB file.")
        return duckdb.connect("data/db/corpus.duckdb", read_only=True)


def main():
    st.title("Sovereign Bond Prospectus Explorer")

    con = get_connection()

    # Corpus stats
    stats = con.execute(
        "SELECT COUNT(*) AS docs, COUNT(DISTINCT source) AS sources FROM documents"
    ).fetchone()
    if stats:
        st.metric("Documents", f"{stats[0]:,}")
        st.metric("Sources", stats[1])

    # Recent documents
    st.subheader("Recent Prospectuses")
    df = con.execute("""
        SELECT
            document_id,
            source,
            title,
            issuer_name,
            publication_date,
            doc_type
        FROM documents
        ORDER BY publication_date DESC NULLS LAST
        LIMIT 50
    """).fetchdf()

    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
