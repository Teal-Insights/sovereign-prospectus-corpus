"""Sovereign Bond Prospectus Explorer — deployment spike."""

from pathlib import Path
from typing import NoReturn

import duckdb
import streamlit as st

st.set_page_config(
    page_title="Sovereign Bond Prospectus Explorer",
    page_icon="📜",
    layout="wide",
)

LOCAL_DB_PATH = Path("data/db/corpus.duckdb")


def _missing_db_error() -> NoReturn:
    """Fail fast when neither MotherDuck nor a local DB is available.

    On Streamlit Cloud, the data/ directory is gitignored and absent, so
    silently falling back to the local path would raise a cryptic IOError.
    Surface a clear error instead.
    """
    st.error(
        "No database available. Set MOTHERDUCK_TOKEN in Streamlit secrets, "
        "or run locally with data/db/corpus.duckdb present."
    )
    st.stop()
    raise RuntimeError("unreachable")


@st.cache_resource(ttl=3600)  # Refresh every hour to avoid stale MotherDuck connections.
def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to MotherDuck when a token is set, else use local DuckDB."""
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        return duckdb.connect(
            "md:sovereign_corpus",
            read_only=True,
            config={"motherduck_token": token},
        )

    if LOCAL_DB_PATH.exists():
        return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)

    _missing_db_error()


def main() -> None:
    st.title("Sovereign Bond Prospectus Explorer")

    con = get_connection()

    stats = con.execute(
        "SELECT COUNT(*) AS docs, COUNT(DISTINCT source) AS sources FROM documents"
    ).fetchone()
    assert stats is not None  # COUNT(*) always returns one row

    col1, col2 = st.columns(2)
    col1.metric("Documents", f"{stats[0]:,}")
    col2.metric("Sources", stats[1])

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
