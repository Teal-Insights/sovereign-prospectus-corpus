"""Sovereign Bond Prospectus Explorer — deployment spike."""

import streamlit as st

st.set_page_config(
    page_title="Sovereign Bond Prospectus Explorer",
    page_icon="📜",
    layout="wide",
)

st.title("Sovereign Bond Prospectus Explorer")
st.write("Deployment spike -- if you see this, Streamlit Cloud works.")

try:
    import duckdb

    st.write(f"duckdb version: {duckdb.__version__}")

    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        st.write("MotherDuck token found, connecting...")
        con = duckdb.connect(f"md:sovereign_corpus?motherduck_token={token}")
        stats = con.execute(
            "SELECT COUNT(*) AS docs, COUNT(DISTINCT source) AS sources FROM documents"
        ).fetchone()
        if stats:
            st.metric("Documents", f"{stats[0]:,}")
            st.metric("Sources", stats[1])

        df = con.execute("""
            SELECT document_id, source, title, issuer_name, publication_date
            FROM documents
            ORDER BY publication_date DESC NULLS LAST
            LIMIT 20
        """).fetchdf()
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("No MOTHERDUCK_TOKEN in secrets.")
except Exception as e:
    st.error(f"Error: {e}")
