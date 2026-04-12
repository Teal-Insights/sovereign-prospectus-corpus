"""World Bank country classification data and sovereign_issuers table builder.

Sources: World Bank Country and Lending Groups (July 2025 edition).
https://datahelpdesk.worldbank.org/knowledgebase/articles/906519
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# country_code -> (region, income_group, lending_category)
# lending_category is None for countries not borrowing from WB
WORLD_BANK_CLASSIFICATIONS: dict[str, tuple[str, str, str | None]] = {
    "AGO": ("Sub-Saharan Africa", "Lower middle income", "IBRD"),
    "ALB": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "ARE": ("Middle East & North Africa", "High income", None),
    "ARG": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "ARM": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "AUT": ("Europe & Central Asia", "High income", None),
    "BEL": ("Europe & Central Asia", "High income", None),
    "BGR": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "BHR": ("Middle East & North Africa", "High income", None),
    "BIH": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "BLR": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "BLZ": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "BRA": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "BRB": ("Latin America & Caribbean", "High income", None),
    "CAN": ("North America", "High income", None),
    "CHL": ("Latin America & Caribbean", "High income", "IBRD"),
    "CHN": ("East Asia & Pacific", "Upper middle income", "IBRD"),
    "CMR": ("Sub-Saharan Africa", "Lower middle income", "Blend"),
    "COD": ("Sub-Saharan Africa", "Low income", "IDA"),
    "COG": ("Sub-Saharan Africa", "Lower middle income", "IDA"),
    "COL": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "CRI": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "CYP": ("Europe & Central Asia", "High income", None),
    "CZE": ("Europe & Central Asia", "High income", None),
    "DEU": ("Europe & Central Asia", "High income", None),
    "DOM": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "ECU": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "EGY": ("Middle East & North Africa", "Lower middle income", "IBRD"),
    "EST": ("Europe & Central Asia", "High income", None),
    "ETH": ("Sub-Saharan Africa", "Low income", "IDA"),
    "FIN": ("Europe & Central Asia", "High income", None),
    "FJI": ("East Asia & Pacific", "Upper middle income", "IBRD"),
    "FRA": ("Europe & Central Asia", "High income", None),
    "GAB": ("Sub-Saharan Africa", "Upper middle income", "IBRD"),
    "GHA": ("Sub-Saharan Africa", "Lower middle income", "IDA"),
    "GIN": ("Sub-Saharan Africa", "Low income", "IDA"),
    "GRC": ("Europe & Central Asia", "High income", None),
    "GTM": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "GUY": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "HKG": ("East Asia & Pacific", "High income", None),
    "HND": ("Latin America & Caribbean", "Lower middle income", "IDA"),
    "HRV": ("Europe & Central Asia", "High income", None),
    "HUN": ("Europe & Central Asia", "High income", None),
    "IDN": ("East Asia & Pacific", "Upper middle income", "IBRD"),
    "IRL": ("Europe & Central Asia", "High income", None),
    "ISL": ("Europe & Central Asia", "High income", None),
    "ISR": ("Middle East & North Africa", "High income", None),
    "ITA": ("Europe & Central Asia", "High income", None),
    "JAM": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "JOR": ("Middle East & North Africa", "Upper middle income", "IBRD"),
    "JPN": ("East Asia & Pacific", "High income", None),
    "KAZ": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "KEN": ("Sub-Saharan Africa", "Lower middle income", "IDA"),
    "KGZ": ("Europe & Central Asia", "Lower middle income", "IDA"),
    "KOR": ("East Asia & Pacific", "High income", None),
    "KWT": ("Middle East & North Africa", "High income", None),
    "LBN": (
        "Middle East & North Africa",
        "Lower middle income",
        "IBRD",
    ),  # Downgraded by WB in 2022
    "LKA": ("South Asia", "Lower middle income", "IBRD"),
    "LTU": ("Europe & Central Asia", "High income", None),
    "LUX": ("Europe & Central Asia", "High income", None),
    "LVA": ("Europe & Central Asia", "High income", None),
    "MAR": ("Middle East & North Africa", "Lower middle income", "IBRD"),
    "MDA": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "MEX": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "MKD": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "MNE": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "NGA": ("Sub-Saharan Africa", "Lower middle income", "Blend"),
    "NLD": ("Europe & Central Asia", "High income", None),
    "OMN": ("Middle East & North Africa", "High income", None),
    "PAK": ("South Asia", "Lower middle income", "Blend"),
    "PAN": ("Latin America & Caribbean", "High income", "IBRD"),
    "PER": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "PHL": ("East Asia & Pacific", "Lower middle income", "IBRD"),
    "POL": ("Europe & Central Asia", "High income", None),
    "PRT": ("Europe & Central Asia", "High income", None),
    "PRY": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "QAT": ("Middle East & North Africa", "High income", None),
    "RWA": ("Sub-Saharan Africa", "Low income", "IDA"),
    "SAU": ("Middle East & North Africa", "High income", None),
    "SEN": ("Sub-Saharan Africa", "Lower middle income", "IDA"),
    "SLE": ("Sub-Saharan Africa", "Low income", "IDA"),
    "SLV": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "SMR": ("Europe & Central Asia", "High income", None),
    "SRB": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "SUR": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "SVK": ("Europe & Central Asia", "High income", None),
    "SVN": ("Europe & Central Asia", "High income", None),
    "SWE": ("Europe & Central Asia", "High income", None),
    "THA": ("East Asia & Pacific", "Upper middle income", "IBRD"),
    "TJK": ("Europe & Central Asia", "Lower middle income", "IDA"),
    "TTO": ("Latin America & Caribbean", "High income", None),
    "TUR": ("Europe & Central Asia", "Upper middle income", "IBRD"),
    "UGA": ("Sub-Saharan Africa", "Low income", "IDA"),
    "UKR": ("Europe & Central Asia", "Lower middle income", "IBRD"),
    "URY": ("Latin America & Caribbean", "High income", "IBRD"),
    "USA": ("North America", "High income", None),
    "UZB": ("Europe & Central Asia", "Lower middle income", "Blend"),
    "VEN": ("Latin America & Caribbean", "Upper middle income", "IBRD"),
    "VNM": ("East Asia & Pacific", "Lower middle income", "Blend"),
    "ZAF": ("Sub-Saharan Africa", "Upper middle income", "IBRD"),
    "ZMB": ("Sub-Saharan Africa", "Low income", "IDA"),
}


def populate_sovereign_issuers(conn: duckdb.DuckDBPyConnection) -> int:
    """Populate sovereign_issuers table from the hard-coded mapping.

    Returns number of rows inserted.
    """
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    conn.execute("DELETE FROM sovereign_issuers")

    inserted = 0
    for issuer_name, (code, country_name, is_sov) in ISSUER_TO_COUNTRY.items():
        wb = WORLD_BANK_CLASSIFICATIONS.get(code)
        if wb is None:
            region, income, lending = "Unknown", "Unknown", None
        else:
            region, income, lending = wb

        conn.execute(
            "INSERT INTO sovereign_issuers "
            "(issuer_name, country_name, country_code, region, income_group, "
            "lending_category, is_sovereign) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [issuer_name, country_name, code, region, income, lending, is_sov],
        )
        inserted += 1

    return inserted
