"""DuckDB queries for the explorer app.

All queries use parameterized SQL. No string interpolation of user input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb
    import pandas as pd

_DISPLAY_NAME = "COALESCE(d.issuer_name, d.title, d.storage_key)"


def browse_documents(
    con: duckdb.DuckDBPyConnection,
    *,
    limit: int = 50,
    offset: int = 0,
    sources: list[str] | None = None,
    income_groups: list[str] | None = None,
    regions: list[str] | None = None,
    country_codes: list[str] | None = None,
    include_high_income: bool = False,
) -> pd.DataFrame:
    """Fetch documents for the browse table, newest first."""
    where_clauses = []
    params: list[Any] = []

    if sources:
        placeholders = ",".join(["?"] * len(sources))
        where_clauses.append(f"d.source IN ({placeholders})")
        params.extend(sources)

    if not include_high_income:
        where_clauses.append("COALESCE(si.income_group, 'Unknown') != 'High income'")

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        where_clauses.append(f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})")
        params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        where_clauses.append(f"COALESCE(si.region, 'Unknown') IN ({placeholders})")
        params.extend(regions)

    if country_codes:
        placeholders = ",".join(["?"] * len(country_codes))
        where_clauses.append(f"si.country_code IN ({placeholders})")
        params.extend(country_codes)

    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    params.extend([limit, offset])

    return con.execute(
        f"""
        SELECT
            d.document_id,
            {_DISPLAY_NAME} AS display_name,
            d.source,
            d.publication_date,
            d.doc_type,
            COALESCE(si.country_name, 'Unknown') AS country_name
        FROM documents d
        LEFT JOIN sovereign_issuers si ON d.issuer_name = si.issuer_name
        {where}
        ORDER BY d.publication_date DESC NULLS LAST, d.document_id DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchdf()


def count_documents(
    con: duckdb.DuckDBPyConnection,
    *,
    sources: list[str] | None = None,
    include_high_income: bool = False,
    income_groups: list[str] | None = None,
    regions: list[str] | None = None,
    country_codes: list[str] | None = None,
) -> int:
    """Count documents matching filters."""
    where_clauses = []
    params: list[Any] = []

    if sources:
        placeholders = ",".join(["?"] * len(sources))
        where_clauses.append(f"d.source IN ({placeholders})")
        params.extend(sources)

    if not include_high_income:
        where_clauses.append("COALESCE(si.income_group, 'Unknown') != 'High income'")

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        where_clauses.append(f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})")
        params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        where_clauses.append(f"COALESCE(si.region, 'Unknown') IN ({placeholders})")
        params.extend(regions)

    if country_codes:
        placeholders = ",".join(["?"] * len(country_codes))
        where_clauses.append(f"si.country_code IN ({placeholders})")
        params.extend(country_codes)

    where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    row = con.execute(
        f"""
        SELECT COUNT(*)
        FROM documents d
        LEFT JOIN sovereign_issuers si ON d.issuer_name = si.issuer_name
        {where}
        """,
        params,
    ).fetchone()
    return row[0] if row else 0


def search_documents(
    con: duckdb.DuckDBPyConnection,
    query: str,
    *,
    limit: int = 50,
    sources: list[str] | None = None,
    include_high_income: bool = False,
    income_groups: list[str] | None = None,
    regions: list[str] | None = None,
    country_codes: list[str] | None = None,
) -> pd.DataFrame:
    """BM25 full-text search, grouped by document (best page per doc)."""
    filter_clauses = []
    filter_params: list[Any] = []

    if sources:
        placeholders = ",".join(["?"] * len(sources))
        filter_clauses.append(f"d.source IN ({placeholders})")
        filter_params.extend(sources)

    if not include_high_income:
        filter_clauses.append("COALESCE(si.income_group, 'Unknown') != 'High income'")

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        filter_clauses.append(f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})")
        filter_params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        filter_clauses.append(f"COALESCE(si.region, 'Unknown') IN ({placeholders})")
        filter_params.extend(regions)

    if country_codes:
        placeholders = ",".join(["?"] * len(country_codes))
        filter_clauses.append(f"si.country_code IN ({placeholders})")
        filter_params.extend(country_codes)

    extra_where = ""
    if filter_clauses:
        extra_where = "AND " + " AND ".join(filter_clauses)

    # Single query param -- nested CTE avoids evaluating match_bm25 twice
    params = [query, *filter_params, limit]

    return con.execute(
        f"""
        WITH scored AS (
            SELECT
                dp.document_id,
                dp.page_number,
                dp.page_text,
                fts_main_document_pages.match_bm25(dp.page_id, ?) AS score
            FROM document_pages dp
            WHERE score IS NOT NULL
        ),
        ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY document_id ORDER BY score DESC
                ) AS rn
            FROM scored
        )
        SELECT
            r.document_id,
            {_DISPLAY_NAME} AS display_name,
            d.source,
            d.publication_date,
            d.doc_type,
            r.page_number,
            r.page_text,
            r.score,
            COALESCE(si.country_name, 'Unknown') AS country_name
        FROM ranked r
        JOIN documents d ON r.document_id = d.document_id
        LEFT JOIN sovereign_issuers si ON d.issuer_name = si.issuer_name
        WHERE r.rn = 1
        {extra_where}
        ORDER BY r.score DESC
        LIMIT ?
        """,
        params,
    ).fetchdf()


def get_document_detail(con: duckdb.DuckDBPyConnection, document_id: int) -> dict | None:
    """Fetch document metadata for the detail view."""
    row = con.execute(
        f"""
        SELECT
            d.document_id,
            {_DISPLAY_NAME} AS display_name,
            d.title,
            d.issuer_name,
            d.source,
            d.publication_date,
            d.doc_type,
            COALESCE(d.source_page_url, d.download_url) AS filing_url,
            COALESCE(si.country_name, 'Unknown') AS country_name,
            COALESCE(si.region, 'Unknown') AS region,
            COALESCE(si.income_group, 'Unknown') AS income_group
        FROM documents d
        LEFT JOIN sovereign_issuers si ON d.issuer_name = si.issuer_name
        WHERE d.document_id = ?
        """,
        [document_id],
    ).fetchone()
    if row is None:
        return None
    cols = [
        "document_id",
        "display_name",
        "title",
        "issuer_name",
        "source",
        "publication_date",
        "doc_type",
        "filing_url",
        "country_name",
        "region",
        "income_group",
    ]
    return dict(zip(cols, row, strict=True))


def get_markdown(con: duckdb.DuckDBPyConnection, document_id: int) -> str | None:
    """Fetch full markdown text for a document. Returns None if not available."""
    row = con.execute(
        "SELECT markdown_text, char_count FROM document_markdown WHERE document_id = ?",
        [document_id],
    ).fetchone()
    if row is None:
        return None
    return row[0]


def get_markdown_size(con: duckdb.DuckDBPyConnection, document_id: int) -> int:
    """Get markdown char_count without loading the full text."""
    row = con.execute(
        "SELECT char_count FROM document_markdown WHERE document_id = ?",
        [document_id],
    ).fetchone()
    return row[0] if row else 0


def get_page_text(
    con: duckdb.DuckDBPyConnection, document_id: int, page_number: int
) -> str | None:
    """Fetch text for a single page."""
    row = con.execute(
        "SELECT page_text FROM document_pages WHERE document_id = ? AND page_number = ?",
        [document_id, page_number],
    ).fetchone()
    return row[0] if row else None


def get_max_page(con: duckdb.DuckDBPyConnection, document_id: int) -> int:
    """Get highest page number for a document."""
    row = con.execute(
        "SELECT MAX(page_number) FROM document_pages WHERE document_id = ?",
        [document_id],
    ).fetchone()
    return row[0] if row and row[0] else 0


def search_pages_in_document(
    con: duckdb.DuckDBPyConnection, document_id: int, query: str
) -> list[int]:
    """Find page numbers in a document that contain the query text."""
    # Escape ILIKE wildcards in the user's query to prevent % and _ from
    # being interpreted as wildcards (e.g., "10%" would match "10" + anything)
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = con.execute(
        """
        SELECT page_number FROM document_pages
        WHERE document_id = ? AND page_text ILIKE '%' || ? || '%' ESCAPE '\\'
        ORDER BY page_number
        """,
        [document_id, escaped],
    ).fetchall()
    return [r[0] for r in rows]


def get_filter_options(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """Get distinct values for filter dropdowns. Cache this with @st.cache_data."""
    sources = [
        r[0]
        for r in con.execute("SELECT DISTINCT source FROM documents ORDER BY source").fetchall()
    ]
    regions = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT region FROM sovereign_issuers ORDER BY region"
        ).fetchall()
    ]
    income_groups = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT income_group FROM sovereign_issuers ORDER BY income_group"
        ).fetchall()
    ]
    countries = [
        (r[0], r[1])
        for r in con.execute(
            """
            SELECT DISTINCT si.country_code, si.country_name
            FROM sovereign_issuers si
            JOIN documents d ON d.issuer_name = si.issuer_name
            ORDER BY si.country_name
            """
        ).fetchall()
    ]
    return {
        "sources": sources,
        "regions": regions,
        "income_groups": income_groups,
        "countries": countries,
    }


def get_corpus_stats(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Get corpus overview stats."""
    row = con.execute("""
        SELECT
            COUNT(*) AS docs,
            COUNT(DISTINCT source) AS sources,
            COUNT(DISTINCT issuer_name) AS issuers
        FROM documents
        WHERE issuer_name IS NOT NULL
    """).fetchone()
    # docs count should include all docs, issuers should exclude nulls
    total = con.execute("SELECT COUNT(*) FROM documents").fetchone()
    return {"docs": total[0], "sources": row[1], "issuers": row[2]}
