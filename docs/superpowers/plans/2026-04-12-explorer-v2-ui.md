# Explorer V2 UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a searchable document explorer with ~9,700 sovereign bond prospectuses for the IMF Spring Meetings demo on Monday 2026-04-13.

**Architecture:** Single Streamlit app (`explorer/app.py`) with three session-state-driven views (browse, search, detail). Country metadata via a hard-coded issuer-to-country mapping loaded into a `sovereign_issuers` DuckDB table. BM25 full-text search via DuckDB FTS extension. Hybrid document rendering: full markdown for docs under 200KB, page-by-page for larger docs.

**Tech Stack:** Streamlit 1.45.1, DuckDB 1.4.4, DuckDB FTS, MotherDuck, Pandas

**Spec:** `docs/superpowers/specs/2026-04-12-explorer-v2-ui-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `explorer/__init__.py` | Create | Empty init — makes `explorer` importable as a Python package |
| `explorer/issuer_country_map.py` | Create | Hard-coded dict mapping 261 issuer names to country codes |
| `explorer/country_metadata.py` | Create | World Bank income group/region/lending category data + `sovereign_issuers` table builder |
| `explorer/queries.py` | Create | All DuckDB queries: browse, search (CTE+window), detail, filters |
| `explorer/highlight.py` | Create | Regex-safe `<mark>` highlighting with 100-match cap |
| `explorer/app.py` | Rewrite | Three-view Streamlit app: browse, search, detail |
| `explorer/assets/` | Create dir | Copy logos from `demo/images/` |
| `sql/002_sovereign_issuers.sql` | Create | DDL for `sovereign_issuers` table |
| `tests/test_explorer_queries.py` | Create | Tests for search CTE, snippet extraction, null handling |
| `tests/test_highlight.py` | Create | Tests for regex-safe highlighting and cap |
| `tests/test_issuer_mapping.py` | Create | Tests for issuer mapping coverage |

---

### Task 1: Sovereign Issuers DDL and Mapping

**Files:**
- Create: `sql/002_sovereign_issuers.sql`
- Create: `explorer/issuer_country_map.py`
- Create: `explorer/country_metadata.py`
- Create: `tests/test_issuer_mapping.py`

- [ ] **Step 0: Make explorer an importable package**

Three things needed for `from explorer.queries import ...` to resolve in all
contexts (Streamlit, pytest, CLI entry points):

1. Create `explorer/__init__.py` (makes it a Python package)
2. Add `"explorer"` to the packages list in `pyproject.toml` (so `uv run`
   installs it and CLI entry points can import it)
3. Delete the stale `explorer/foo.py` (blocks `ruff format --check`)

```bash
touch explorer/__init__.py
rm -f explorer/foo.py
```

Then edit `pyproject.toml` line 57:

```toml
# Before:
packages = ["src/corpus"]
# After:
packages = ["src/corpus", "explorer"]
```

Run `uv sync` to re-install with the new package:

```bash
uv sync --all-extras
```

- [ ] **Step 1: Write the DDL**

Create `sql/002_sovereign_issuers.sql`:

```sql
-- Sovereign issuer lookup table for filtering by country/region/income.
-- Populated at build time from explorer/country_metadata.py.

CREATE TABLE IF NOT EXISTS sovereign_issuers (
    issuer_name      VARCHAR PRIMARY KEY,
    country_name     VARCHAR NOT NULL,
    country_code     VARCHAR NOT NULL,    -- ISO 3166-1 alpha-3
    region           VARCHAR NOT NULL,    -- World Bank region
    income_group     VARCHAR NOT NULL,    -- Low income | Lower middle income | Upper middle income | High income
    lending_category VARCHAR,             -- IDA | IBRD | Blend | null (for non-WB borrowers)
    is_sovereign     BOOLEAN NOT NULL DEFAULT true
);
```

- [ ] **Step 2: Write the issuer-to-country mapping**

Create `explorer/issuer_country_map.py`. This maps every distinct `issuer_name` in the corpus (261 values) to `(country_code, country_name, is_sovereign)`. Corporate issuers get `is_sovereign=False`.

```python
"""Hard-coded mapping of every issuer_name in the corpus to country metadata.

261 distinct issuer names. Many are the same country with different formatting.
Corporate/non-sovereign issuers are flagged with is_sovereign=False.

Format: issuer_name -> (country_code, country_name, is_sovereign)
"""

# (country_code, country_name, is_sovereign)
ISSUER_TO_COUNTRY: dict[str, tuple[str, str, bool]] = {
    # --- High volume (>100 docs) ---
    "ISRAEL, STATE OF": ("ISR", "Israel", True),
    "BANK OF CYPRUS HOLDINGS PUBLIC LIMITED COMPANY, BANK OF CYPRUS PUBLIC COMPANY LIMITED (2 issuers)": ("CYP", "Cyprus", False),
    "FEDERATIVE REPUBLIC OF BRAZIL": ("BRA", "Brazil", True),
    "UNICREDIT S.P.A., UNICREDIT BANK IRELAND PUBLIC LIMITED COMPANY, UNICREDIT INTERNATIONAL BANK (LUXEMBOURG) S.A. (3 issuers)": ("ITA", "Italy", False),
    "REPUBLIC OF TURKEY": ("TUR", "Turkey", True),
    "UNITED MEXICAN STATES": ("MEX", "Mexico", True),
    "REPUBLIC OF COLOMBIA": ("COL", "Colombia", True),
    "PHILIPPINES (REPUBLIC OF THE)": ("PHL", "Philippines", True),
    "LEBANESE REPUBLIC (THE)": ("LBN", "Lebanon", True),
    "COLOMBIA (REPUBLIC OF)": ("COL", "Colombia", True),
    "TÜRKIYE (THE REPUBLIC OF)": ("TUR", "Turkey", True),
    "REPUBLIC OF CHILE": ("CHL", "Chile", True),
    "UNICREDIT S.P.A., UNICREDIT BANK IRELAND PUBLIC LIMITED COMPANY (2 issuers)": ("ITA", "Italy", False),
    "BANK OF CYPRUS PUBLIC COMPANY LIMITED": ("CYP", "Cyprus", False),
    "REPUBLIC OF THE PHILIPPINES": ("PHL", "Philippines", True),
    "LATVIA (REPUBLIC OF)": ("LVA", "Latvia", True),
    "UNICREDIT BANK IRELAND PUBLIC LIMITED COMPANY": ("IRL", "Ireland", False),
    "URUGUAY REPUBLIC OF": ("URY", "Uruguay", True),
    "ITALY (REPUBLIC OF)": ("ITA", "Italy", True),
    "URUGUAY (REPUBLICA ORIENTAL DEL)": ("URY", "Uruguay", True),
    "Peru": ("PER", "Peru", True),
    "PANAMA REPUBLIC OF": ("PAN", "Panama", True),
    "OPUS (PUBLIC) CHARTERED ISSUANCE SA": ("LUX", "Luxembourg", False),
    "ARKÉA PUBLIC SECTOR SCF": ("FRA", "France", False),
    "LITHUANIA (THE REPUBLIC OF)": ("LTU", "Lithuania", True),
    "UNICREDIT BANK CZECH REPUBLIC AND SLOVAKIA, A.S.": ("CZE", "Czech Republic", False),
    "PANAMA (THE REPUBLIC OF)": ("PAN", "Panama", True),
    "ARGENTINA (THE REPUBLIC OF)": ("ARG", "Argentina", True),
    "PERU (THE REPUBLIC OF)": ("PER", "Peru", True),
    "Republic of Indonesia": ("IDN", "Indonesia", True),
    "POLAND (THE REPUBLIC OF)": ("POL", "Poland", True),
    "State of Israel": ("ISR", "Israel", True),
    "PERU REPUBLIC OF": ("PER", "Peru", True),
    "CHILE (REPUBLIC OF)": ("CHL", "Chile", True),
    "SOUTH AFRICA (REPUBLIC OF)": ("ZAF", "South Africa", True),
    "AUSTRIA (REPUBLIC OF)": ("AUT", "Austria", True),
    "REPUBLIC OF SOUTH AFRICA": ("ZAF", "South Africa", True),
    "Kingdom of Sweden": ("SWE", "Sweden", True),
    "CANADA": ("CAN", "Canada", True),
    "DOMINICAN REPUBLIC (THE)": ("DOM", "Dominican Republic", True),
    "VENEZUELA (BOLIVARIAN REPUBLIC OF)": ("VEN", "Venezuela", True),
    "ARKEA PUBLIC SECTOR SCF": ("FRA", "France", False),
    "ALDBURG PUBLIC S.A.": ("LUX", "Luxembourg", False),
    "ECUADOR (REPUBLIC OF)": ("ECU", "Ecuador", True),
    "REPUBLIC OF KOREA": ("KOR", "Korea", True),
    "Rwanda": ("RWA", "Rwanda", True),
    "Philippines": ("PHL", "Philippines", True),
    "PROXIMUS S.A. DE DROIT PUBLIC": ("BEL", "Belgium", False),
    "FRESENIUS FINANCE IRELAND PUBLIC LIMITED COMPANY, FRESENIUS SE & CO. KGAA, FRESENIUS FINANCE IRELAND II PUBLIC LIMITED COMPANY (3 issuers)": ("DEU", "Germany", False),
    "CYPRUS POPULAR BANK PUBLIC CO LTD": ("CYP", "Cyprus", False),
    "ITALY REPUBLIC OF": ("ITA", "Italy", True),
    "FRESENIUS FINANCE IRELAND II PUBLIC LIMITED COMPANY, FRESENIUS FINANCE IRELAND PUBLIC LIMITED COMPANY, FRESENIUS SE & CO KGAA (3 issuers)": ("DEU", "Germany", False),
    "JAMAICA GOVERNMENT OF": ("JAM", "Jamaica", True),
    "Venezuela": ("VEN", "Venezuela", True),
    "REPUBLIC OF ARGENTINA": ("ARG", "Argentina", True),
    "FRESENIUS FINANCE IRELAND PUBLIC LIMITED COMPANY": ("DEU", "Germany", False),
    "The Federal Republic of Nigeria": ("NGA", "Nigeria", True),
    "State Of Israel": ("ISR", "Israel", True),
    "Emirate of Abu Dhabi": ("ARE", "United Arab Emirates", True),
    "SLOVENIA (REPUBLIC OF)": ("SVN", "Slovenia", True),
    "Ecuador": ("ECU", "Ecuador", True),
    "EGYPT (THE ARAB REPUBLIC OF)": ("EGY", "Egypt", True),
    "BULGARIA (REPUBLIC OF)": ("BGR", "Bulgaria", True),
    "BANK OF CYPRUS HOLDINGS PUBLIC LIMITED COMPANY": ("CYP", "Cyprus", False),
    "HUNGARY": ("HUN", "Hungary", True),
    "Republic of Finland": ("FIN", "Finland", True),
    "Ghana": ("GHA", "Ghana", True),
    "SURINAME (REPUBLIC OF)": ("SUR", "Suriname", True),
    "EL SALVADOR (THE REPUBLIC OF)": ("SLV", "El Salvador", True),
    "HYPO PUBLIC FINANCE BANK": ("AUT", "Austria", False),
    "Kenya": ("KEN", "Kenya", True),
    "PARAGUAY (THE REPUBLIC OF)": ("PRY", "Paraguay", True),
    "CROATIA (REPUBLIC OF)": ("HRV", "Croatia", True),
    "Arab Republic of Egypt": ("EGY", "Egypt", True),
    "Netherlands": ("NLD", "Netherlands", True),
    "Republic Of Cyprus": ("CYP", "Cyprus", True),
    "Hungary": ("HUN", "Hungary", True),
    "STATE OF ISRAEL": ("ISR", "Israel", True),
    "OPUS (PUBLIC) CHARTERED ISSUANCE S.A.": ("LUX", "Luxembourg", False),
    "Jamaica": ("JAM", "Jamaica", True),
    "GREECE (THE HELLENIC REPUBLIC)": ("GRC", "Greece", True),
    "HELLENIC BANK PUBLIC COMPANY LIMITED": ("CYP", "Cyprus", False),
    "Indonesia": ("IDN", "Indonesia", True),
    "PORTUGAL (REPUBLIC OF)": ("PRT", "Portugal", True),
    "Saudi Arabia": ("SAU", "Saudi Arabia", True),
    "FRESENIUS FINANCE IRELAND PUBLIC LIMITED COMPANY, FRESENIUS SE & CO KGAA, FRESENIUS FINANCE IRELAND II PUBLIC LIMITED COMPANY (3 issuers)": ("DEU", "Germany", False),
    "Republic of Kazakhstan": ("KAZ", "Kazakhstan", True),
    "BNP PARIBAS PUBLIC SECTOR SCF": ("FRA", "France", False),
    "Sierra Leone": ("SLE", "Sierra Leone", True),
    "Argentina": ("ARG", "Argentina", True),
    "China": ("CHN", "China", True),
    "TURKEY (REPUBLIC OF)": ("TUR", "Turkey", True),
    "The Republic of Ghana": ("GHA", "Ghana", True),
    "Angola": ("AGO", "Angola", True),
    "GUATEMALA (THE REPUBLIC OF)": ("GTM", "Guatemala", True),
    "HELLENIC RAILWAYS, GREECE (THE HELLENIC REPUBLIC)": ("GRC", "Greece", False),
    "Republic of Iceland": ("ISL", "Iceland", True),
    "Kingdom of Saudi Arabia (The)": ("SAU", "Saudi Arabia", True),
    "LUNAR FUNDING V PUBLIC LIMITED COMPANY": ("IRL", "Ireland", False),
    "Serbia (Republic of)": ("SRB", "Serbia", True),
    "EUROBANK LIMITED": ("CYP", "Cyprus", False),
    "CZECH REPUBLIC": ("CZE", "Czech Republic", True),
    "Nigeria": ("NGA", "Nigeria", True),
    "Uzbekistan (Republic of)": ("UZB", "Uzbekistan", True),
    "Angola (The Republic of)": ("AGO", "Angola", True),
    "State of Qatar-Ministry of Finance": ("QAT", "Qatar", True),
    "Kingdom of Saudi Arabia": ("SAU", "Saudi Arabia", True),
    "Sweden": ("SWE", "Sweden", True),
    "Cyprus": ("CYP", "Cyprus", True),
    "ICELAND (REPUBLIC OF)": ("ISL", "Iceland", True),
    "Cameroon": ("CMR", "Cameroon", True),
    "Government of The Republic of Iceland": ("ISL", "Iceland", True),
    "TRINIDAD AND TOBAGO (REPUBLIC OF)": ("TTO", "Trinidad and Tobago", True),
    "Bahrain": ("BHR", "Bahrain", True),
    "Oman Sovereign Sukuk S.A.O.C.": ("OMN", "Oman", True),
    "CHINA (PEOPLE'S REPUBLIC OF)": ("CHN", "China", True),
    "Kazakhstan": ("KAZ", "Kazakhstan", True),
    "Republic of Serbia (represented by the Government of the Republic of Serbia, acting by and through the Ministry of Finance)": ("SRB", "Serbia", True),
    "Senegal": ("SEN", "Senegal", True),
    "UNICREDIT BANK GMBH": ("DEU", "Germany", False),
    "BELGACOM FINANCE S.A., PROXIMUS S.A. DE DROIT PUBLIC (2 issuers)": ("BEL", "Belgium", False),
    "AZOR MORTGAGES PUBLIC LIMITED COMPANY": ("IRL", "Ireland", False),
    "Kingdom of Bahrain-Ministry of Fin.": ("BHR", "Bahrain", True),
    "The Republic of Uzbekistan": ("UZB", "Uzbekistan", True),
    "MOL HUNGARIAN OIL AND GAS PUBLIC LIMITED COMPANY": ("HUN", "Hungary", False),
    "Nigeria (Federal Republic of) (The)": ("NGA", "Nigeria", True),
    "SAN MARINO (REPUBLIC OF)": ("SMR", "San Marino", True),
    "COSTA RICA (REPUBLIC OF)": ("CRI", "Costa Rica", True),
    "Republic of Angola": ("AGO", "Angola", True),
    "Barbados": ("BRB", "Barbados", True),
    "PAKISTAN (THE ISLAMIC REPUBLIC OF)": ("PAK", "Pakistan", True),
    "Moldova": ("MDA", "Moldova", True),
    "Egypt (Arab Republic of) (The)": ("EGY", "Egypt", True),
    "UNICREDIT LUXEMBOURG FINANCE S.A., UNICREDIT BANK IRELAND PUBLIC LIMITED COMPANY": ("ITA", "Italy", False),
    "THE REPUBLIC OF GHANA": ("GHA", "Ghana", True),
    "HONDURAS (THE REPUBLIC OF)": ("HND", "Honduras", True),
    "The Government of the Sultanate of Oman": ("OMN", "Oman", True),
    "Kazakhstan (Republic of)": ("KAZ", "Kazakhstan", True),
    "Kuwait": ("KWT", "Kuwait", True),
    "Republic of Serbia": ("SRB", "Serbia", True),
    "Ethiopia": ("ETH", "Ethiopia", True),
    "SENEGAL (THE REPUBLIC OF)": ("SEN", "Senegal", True),
    "REPUBLIC OF BELARUS": ("BLR", "Belarus", True),
    "BANK OF CYPRUS HOLDINGS PUBLIC LIMITED COMPANY, BANK OF CYPRUS PUBLIC COMPANY LIMITED": ("CYP", "Cyprus", False),
    "Jordan": ("JOR", "Jordan", True),
    "The Kingdom of Saudi Arabia acting through the Ministry of Finance": ("SAU", "Saudi Arabia", True),
    "Montenegro": ("MNE", "Montenegro", True),
    "State of Montenegro": ("MNE", "Montenegro", True),
    "Egypt": ("EGY", "Egypt", True),
    "SLOVAK REPUBLIC": ("SVK", "Slovakia", True),
    "SERBIA (THE REPUBLIC OF)": ("SRB", "Serbia", True),
    "Central Bank of Iceland": ("ISL", "Iceland", True),
    "State of Israel Ministry of Finance": ("ISR", "Israel", True),
    "Oman (Government of Sultanate of)": ("OMN", "Oman", True),
    "BELGACOM FINANCE S.A., PROXIMUS S.A. DE DROIT PUBLIC": ("BEL", "Belgium", False),
    "THE ARAB REPUBLIC OF EGYPT": ("EGY", "Egypt", True),
    "Israel": ("ISR", "Israel", True),
    "NATIONAL TREASURY OF THE REPUBLIC OF SOUTH AFRICA": ("ZAF", "South Africa", True),
    "The Hashemite Kingdom of Jordan": ("JOR", "Jordan", True),
    "The Republic Of Uzbekistan": ("UZB", "Uzbekistan", True),
    "FINLAND REPUBLIC OF": ("FIN", "Finland", True),
    "TT&T PUBLIC COMPANY LIMITED": ("THA", "Thailand", False),
    "Sri Lanka (G.D.S. Republic of)": ("LKA", "Sri Lanka", True),
    "Kenya (The Republic of)": ("KEN", "Kenya", True),
    "ALBANIA (THE REPUBLIC OF)": ("ALB", "Albania", True),
    "REPUBLIC OF CONGO (THE)": ("COG", "Republic of Congo", True),
    "SECTEUR PUBLIC FRANCE 2012-1": ("FRA", "France", False),
    "The Govt of the Hong Kong Spl Adm Region of the People's Republic of China": ("HKG", "Hong Kong", True),
    "Republic of Austria": ("AUT", "Austria", True),
    "Iceland": ("ISL", "Iceland", True),
    "Kyrgyzstan": ("KGZ", "Kyrgyzstan", True),
    "Uzbekistan": ("UZB", "Uzbekistan", True),
    "Ghana (Republic of) (The)": ("GHA", "Ghana", True),
    "Austria": ("AUT", "Austria", True),
    "Republic of Zambia": ("ZMB", "Zambia", True),
    "Kazakhstan Temir Zholy Finance BV": ("KAZ", "Kazakhstan", False),
    "Albania (The Republic of) ": ("ALB", "Albania", True),
    "Government of Canada": ("CAN", "Canada", True),
    "Ukraine, represented by the Minister of Finance": ("UKR", "Ukraine", True),
    "Morocco": ("MAR", "Morocco", True),
    "State of Kuwait (Ministry of Fin.)": ("KWT", "Kuwait", True),
    "State of Montenegro (represented by the Government of Montenegro, acting by and through its Ministry of Finance and Social Welfare)": ("MNE", "Montenegro", True),
    "Canada": ("CAN", "Canada", True),
    "VIETNAM (THE SOCIALISTIC REPUBLIC OF)": ("VNM", "Vietnam", True),
    "Eastern Republic of Uruguay": ("URY", "Uruguay", True),
    "Joint Stock Company National Bank for Foreign Economic Activity of the Republic of Uzbekistan": ("UZB", "Uzbekistan", False),
    "Italy": ("ITA", "Italy", True),
    "Brazil": ("BRA", "Brazil", True),
    "Morocco (Kingdom of)": ("MAR", "Morocco", True),
    "THE STANDARD BANK OF SOUTH AFRICA LTD": ("ZAF", "South Africa", False),
    "THE FEDERAL REPUBLIC OF NIGERIA": ("NGA", "Nigeria", True),
    "Emirate Of Abu Dhabi": ("ARE", "United Arab Emirates", True),
    "Jordan (Hashemite Kingdom of) (The)": ("JOR", "Jordan", True),
    "KOREA (THE REPUBLIC OF)": ("KOR", "Korea", True),
    "State Of Kuwait": ("KWT", "Kuwait", True),
    "China (MoF of People's Republic of)": ("CHN", "China", True),
    "Federal Government of UAE": ("ARE", "United Arab Emirates", True),
    "State Of Qatar": ("QAT", "Qatar", True),
    "The State of Qatar": ("QAT", "Qatar", True),
    "South Africa (Government of)": ("ZAF", "South Africa", True),
    "MACEDONIA (FORMER YUGOSLAV REPUBLIC OF)": ("MKD", "North Macedonia", True),
    "Republic of Angola (The)": ("AGO", "Angola", True),
    "Belarus (Republic of)": ("BLR", "Belarus", True),
    "REPUBLIC OF KENYA": ("KEN", "Kenya", True),
    "Zambia (Republic of) (MoF)": ("ZMB", "Zambia", True),
    "Arab Republic of Egypt (The)": ("EGY", "Egypt", True),
    "REPUBLIC OF IRELAND": ("IRL", "Ireland", True),
    "HELLENIC RAILWAYS, GREECE (THE HELLENIC REPUBLIC), NATIONAL BANK OF GREECE S.A.... (7 issuers)": ("GRC", "Greece", False),
    "JSC National Bank for Foreign Economic Activity of the Republic of Uzbekistan": ("UZB", "Uzbekistan", False),
    "Republic of  Belarus": ("BLR", "Belarus", True),
    "Government Of The Republic Of Fiji": ("FJI", "Fiji", True),
    "MINISTRY OF FINANCE, THE DEMOCRATIC REPUBLIC OF THE CONGO": ("COD", "Democratic Republic of the Congo", True),
    "SG ISSUER, SOCIETE GENERALE, PORTUGAL (REPUBLIC OF)": ("FRA", "France", False),
    "The Republic Of Kazakhstan": ("KAZ", "Kazakhstan", True),
    "Arab Republic Of Egypt (The)": ("EGY", "Egypt", True),
    "THE REPUBLIC OF KENYA": ("KEN", "Kenya", True),
    "Global Sukuk Ventures (Q.P.J.S.C.)": ("QAT", "Qatar", False),
    "Bosnia and Herzegovina (Fedtn of.) ": ("BIH", "Bosnia and Herzegovina", True),
    "Republic of Cameroon (The)": ("CMR", "Cameroon", True),
    "National Treasury of the Republic of South Africa": ("ZAF", "South Africa", True),
    "Republic Of Serbia": ("SRB", "Serbia", True),
    "The Republic of Rwanda": ("RWA", "Rwanda", True),
    "GOVERNMENT OF JAMICA": ("JAM", "Jamaica", True),
    "SULTANATE OF OMAN": ("OMN", "Oman", True),
    "Guyana": ("GUY", "Guyana", True),
    "Sri Lanka": ("LKA", "Sri Lanka", True),
    "GOVERNMENT OF BELIZE": ("BLZ", "Belize", True),
    "FINLAND (REPUBLIC OF)": ("FIN", "Finland", True),
    "CASTANEA ONE PUBLIC LIMITED COMPANY": ("IRL", "Ireland", False),
    "UNICREDIT S.P.A., UNICREDIT BANK IRELAND PUBLIC LIMITED COMPANY, ING BANK N.V., UNICREDIT INTERNATIONAL BANK (LUXEMBOURG) S.A.": ("ITA", "Italy", False),
    "Armenia (Republic of)": ("ARM", "Armenia", True),
    "Gabonese Republic (The)": ("GAB", "Gabon", True),
    "Cyprus (Republic of)": ("CYP", "Cyprus", True),
    "SWEDEN (KINGDOM OF)": ("SWE", "Sweden", True),
    "BANCO DE RESERVAS DE LA REPUBLICA DOMINICANA": ("DOM", "Dominican Republic", False),
    "Uganda": ("UGA", "Uganda", True),
    "ZELEZNICE SLOVENSKEJ REPUBLIKY": ("SVK", "Slovakia", False),
    "XXI CENTURY INVESTMENTS PUBLIC LIMITED": ("CYP", "Cyprus", False),
    "GREECE (THE HELLENIC REPUBLIC), NATIONAL BANK OF GREECE S.A., NBG FINANCE PLC... (25 issuers)": ("GRC", "Greece", False),
    "REPUBLIC OF TAJIKISTAN": ("TJK", "Tajikistan", True),
    "Albania (The Republic of)": ("ALB", "Albania", True),
    "Srpska (Republic of)": ("BIH", "Bosnia and Herzegovina", True),
    "ESTONIA (REPUBLIC OF)": ("EST", "Estonia", True),
    "State of Montenegro": ("MNE", "Montenegro", True),
    "MINISTRY OF FINANCE OF REPUBLIC OF SRPSKA": ("BIH", "Bosnia and Herzegovina", True),
    "Latvia": ("LVA", "Latvia", True),
    "MORGAN GUARANTY TRUST COMPANY OF NEW YORK": ("USA", "United States", False),
    "ADVANCE AGRO PUBLIC COMPANY LIMITED": ("THA", "Thailand", False),
    "Serbia": ("SRB", "Serbia", True),
    "Guinea": ("GIN", "Guinea", True),
    "SG ISSUER, PORTUGAL (REPUBLIC OF)": ("FRA", "France", False),
    "Japan": ("JPN", "Japan", True),
    "Bosnia and Herzegovina": ("BIH", "Bosnia and Herzegovina", True),
    "Albania; Andorra; Austria; Indonesia": ("ALB", "Albania", True),
    "THE HASHEMITE KINGDOM OF JORDAN": ("JOR", "Jordan", True),
    "Rwanda (Republic of) (The)": ("RWA", "Rwanda", True),
    "INDONESIA (REPUBLIC OF)": ("IDN", "Indonesia", True),
    "CENTRAL BANK OF THE DOMINICAN REPUBLIC": ("DOM", "Dominican Republic", True),
    "Republic of Uzbekistan": ("UZB", "Uzbekistan", True),
    "Republic of Srpska": ("BIH", "Bosnia and Herzegovina", True),
    "Republic of Cameroon": ("CMR", "Cameroon", True),
    # --- Keys missed in initial draft (caught by review) ---
    "State Of Montenegro": ("MNE", "Montenegro", True),  # Case variant: "Of" not "of"
    "The Govt of the Hong Kong Spl Adm Region of the People\u2019s Republic of China": ("HKG", "Hong Kong", True),  # Curly apostrophe variant
}
```

Note: "State of Montenegro" appears with two capitalizations ("of" and "Of").
Both must be present as separate keys. Python dicts deduplicate on exact
string match, so the two variants are distinct keys mapping to MNE.

- [ ] **Step 3: Write the World Bank metadata + table builder**

Create `explorer/country_metadata.py`:

```python
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
    "LBN": ("Middle East & North Africa", "Lower middle income", "IBRD"),  # Downgraded by WB in 2022
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
```

- [ ] **Step 4: Write test for mapping coverage**

Create `tests/test_issuer_mapping.py`:

```python
"""Tests for issuer-to-country mapping coverage."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_all_issuers_mapped():
    """Every issuer_name in the mapping resolves to a known WB country."""
    from explorer.country_metadata import WORLD_BANK_CLASSIFICATIONS
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    unmapped = []
    for issuer, (code, _name, _is_sov) in ISSUER_TO_COUNTRY.items():
        if code not in WORLD_BANK_CLASSIFICATIONS:
            unmapped.append(f"{issuer} -> {code}")

    assert not unmapped, "Issuers with unmapped country codes:\n" + "\n".join(unmapped)


def test_no_empty_country_names():
    """Every mapping has a non-empty country name."""
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    empty = [k for k, (_, name, _) in ISSUER_TO_COUNTRY.items() if not name]
    assert not empty, "Issuers with empty country names: " + str(empty)


def test_country_codes_are_alpha3():
    """All country codes are 3-letter uppercase."""
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    bad = [
        f"{k} -> {code}"
        for k, (code, _, _) in ISSUER_TO_COUNTRY.items()
        if len(code) != 3 or code != code.upper()
    ]
    assert not bad, "Invalid country codes:\n" + "\n".join(bad)


@pytest.mark.skipif(
    not Path("data/db/corpus.duckdb").exists(),
    reason="Local corpus.duckdb not available",
)
def test_mapping_covers_all_corpus_issuers():
    """Every non-null issuer_name in the DB has a mapping entry."""
    import duckdb

    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    con = duckdb.connect("data/db/corpus.duckdb", read_only=True)
    db_issuers = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT issuer_name FROM documents WHERE issuer_name IS NOT NULL"
        ).fetchall()
    ]
    con.close()

    unmapped = [name for name in db_issuers if name not in ISSUER_TO_COUNTRY]
    assert not unmapped, (
        str(len(unmapped)) + " issuers in DB not in mapping:\n"
        + "\n".join(unmapped[:20])
    )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_issuer_mapping.py -v
```

Expected: 4 PASSED (3 unit + 1 DB coverage check).

- [ ] **Step 6: Commit**

```bash
git rm explorer/foo.py
git add explorer/__init__.py pyproject.toml sql/002_sovereign_issuers.sql \
  explorer/issuer_country_map.py explorer/country_metadata.py \
  tests/test_issuer_mapping.py
git commit -m "feat: sovereign issuer lookup table with 263 issuer-to-country mappings"
```

---

### Task 2: Search and Highlight Utilities

**Files:**
- Create: `explorer/queries.py`
- Create: `explorer/highlight.py`
- Create: `tests/test_explorer_queries.py`
- Create: `tests/test_highlight.py`

- [ ] **Step 1: Write highlight tests**

Create `tests/test_highlight.py`:

```python
"""Tests for regex-safe text highlighting."""

from __future__ import annotations


def test_basic_highlight():
    from explorer.highlight import highlight_text

    result = highlight_text("The cat sat on the mat", "cat")
    assert "<mark>cat</mark>" in result
    assert result.count("<mark>") == 1


def test_case_insensitive():
    from explorer.highlight import highlight_text

    result = highlight_text("The CAT sat on the Cat mat", "cat")
    assert result.count("<mark>") == 2


def test_html_safe():
    """Must not replace inside HTML tags."""
    from explorer.highlight import highlight_text

    text = 'Click <a href="http://cat.com">here</a> to see the cat'
    result = highlight_text(text, "cat")
    # Should highlight "cat" in text, not in the URL
    assert 'href="http://cat.com"' in result
    assert result.count("<mark>") == 1


def test_cap_at_100():
    from explorer.highlight import highlight_text

    text = " ".join(["the"] * 500)
    result, count = highlight_text(text, "the", return_count=True)
    assert count == 500
    assert result.count("<mark>") == 100


def test_empty_query():
    from explorer.highlight import highlight_text

    result = highlight_text("some text", "")
    assert "<mark>" not in result


def test_snippet_extraction():
    from explorer.highlight import extract_snippet

    text = "A" * 200 + "collective action clause" + "B" * 200
    snippet = extract_snippet(text, "collective action")
    assert "collective action" in snippet
    assert len(snippet) < len(text)
```

- [ ] **Step 2: Implement highlight module**

Create `explorer/highlight.py`:

```python
"""Regex-safe text highlighting and snippet extraction."""

from __future__ import annotations

import re


def highlight_text(
    text: str,
    query: str,
    *,
    max_highlights: int = 100,
    return_count: bool = False,
) -> str | tuple[str, int]:
    """Wrap matches in <mark> tags, skipping inside HTML tags.

    Returns highlighted text, or (text, total_count) if return_count=True.
    """
    if not query or not text:
        return (text, 0) if return_count else text

    # Match the query only when NOT inside an HTML tag.
    # Strategy: split text into (HTML tag, non-tag) segments, only replace
    # in non-tag segments.
    escaped = re.escape(query)
    pattern = re.compile(escaped, re.IGNORECASE)

    # Split on HTML tags, keeping the tags
    parts = re.split(r"(<[^>]+>)", text)

    total_count = 0
    highlighted_count = 0
    result_parts = []

    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            # HTML tag -- pass through unchanged
            result_parts.append(part)
        else:
            # Count all matches in this segment
            matches = list(pattern.finditer(part))
            total_count += len(matches)

            if not matches or highlighted_count >= max_highlights:
                result_parts.append(part)
                continue

            # Replace up to the cap
            new_part = []
            last_end = 0
            for m in matches:
                if highlighted_count >= max_highlights:
                    new_part.append(part[last_end:])
                    break
                new_part.append(part[last_end : m.start()])
                new_part.append(f"<mark>{m.group()}</mark>")
                last_end = m.end()
                highlighted_count += 1
            else:
                new_part.append(part[last_end:])
            result_parts.append("".join(new_part))

    result = "".join(result_parts)
    return (result, total_count) if return_count else result


def extract_snippet(text: str, query: str, context_chars: int = 200) -> str:
    """Extract a snippet centered on the first occurrence of query."""
    if not query or not text:
        return text[:400] if text else ""

    idx = text.lower().find(query.lower())
    if idx < 0:
        return text[:400] + ("..." if len(text) > 400 else "")

    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix
```

- [ ] **Step 3: Run highlight tests**

```bash
uv run pytest tests/test_highlight.py -v
```

Expected: 6 PASSED.

- [ ] **Step 4: Write query tests**

Create `tests/test_explorer_queries.py`:

```python
"""Tests for explorer database queries.

These tests require the local corpus.duckdb to exist with data.
Skip if the DB is not available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DB_PATH = Path("data/db/corpus.duckdb")

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(), reason="Local corpus.duckdb not available"
)


@pytest.fixture
def con():
    """Connect to the local DB. Requires sovereign_issuers table to exist.

    Run Task 6 (populate DB) before these tests. All query functions JOIN
    on sovereign_issuers, so they fail with CatalogError if the table is
    missing.
    """
    import duckdb

    conn = duckdb.connect(str(DB_PATH), read_only=True)
    conn.execute("INSTALL fts; LOAD fts")
    # Verify sovereign_issuers table exists
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if "sovereign_issuers" not in tables:
        pytest.skip("sovereign_issuers table not yet populated — run Task 6 first")
    yield conn
    conn.close()


def test_browse_query_returns_rows(con):
    from explorer.queries import browse_documents

    df = browse_documents(con, limit=10)
    assert len(df) > 0
    assert "display_name" in df.columns


def test_browse_query_null_safe(con):
    """No None values in display columns."""
    from explorer.queries import browse_documents

    df = browse_documents(con, limit=50)
    assert df["display_name"].isna().sum() == 0


def test_search_returns_results(con):
    from explorer.queries import search_documents

    results = search_documents(con, "collective action", limit=10)
    assert len(results) > 0
    assert "document_id" in results.columns
    assert "page_number" in results.columns
    assert "page_text" in results.columns


def test_search_grouped_by_document(con):
    """Each document appears at most once in results."""
    from explorer.queries import search_documents

    results = search_documents(con, "collective action", limit=50)
    assert results["document_id"].is_unique


def test_document_detail(con):
    from explorer.queries import get_document_detail

    # Get a known document_id
    row = con.execute("SELECT document_id FROM documents LIMIT 1").fetchone()
    assert row is not None
    detail = get_document_detail(con, row[0])
    assert detail is not None
    assert "document_id" in detail
```

- [ ] **Step 5: Implement queries module**

Create `explorer/queries.py`:

```python
"""DuckDB queries for the explorer app.

All queries use parameterized SQL. No string interpolation of user input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    import duckdb

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
        where_clauses.append(
            "COALESCE(si.income_group, 'Unknown') != 'High income'"
        )

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        where_clauses.append(
            f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})"
        )
        params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        where_clauses.append(
            f"COALESCE(si.region, 'Unknown') IN ({placeholders})"
        )
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
        where_clauses.append(
            "COALESCE(si.income_group, 'Unknown') != 'High income'"
        )

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        where_clauses.append(
            f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})"
        )
        params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        where_clauses.append(
            f"COALESCE(si.region, 'Unknown') IN ({placeholders})"
        )
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
        filter_clauses.append(
            "COALESCE(si.income_group, 'Unknown') != 'High income'"
        )

    if income_groups:
        placeholders = ",".join(["?"] * len(income_groups))
        filter_clauses.append(
            f"COALESCE(si.income_group, 'Unknown') IN ({placeholders})"
        )
        filter_params.extend(income_groups)

    if regions:
        placeholders = ",".join(["?"] * len(regions))
        filter_clauses.append(
            f"COALESCE(si.region, 'Unknown') IN ({placeholders})"
        )
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


def get_document_detail(
    con: duckdb.DuckDBPyConnection, document_id: int
) -> dict | None:
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
        "document_id", "display_name", "title", "issuer_name", "source",
        "publication_date", "doc_type", "filing_url", "country_name",
        "region", "income_group",
    ]
    return dict(zip(cols, row))


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
        for r in con.execute(
            "SELECT DISTINCT source FROM documents ORDER BY source"
        ).fetchall()
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
```

- [ ] **Step 6: Run query tests**

```bash
uv run pytest tests/test_explorer_queries.py -v
```

Expected: 5 PASSED (or skipped if DB not available).

- [ ] **Step 7: Commit**

```bash
git add explorer/queries.py explorer/highlight.py \
  tests/test_explorer_queries.py tests/test_highlight.py
git commit -m "feat: search queries (CTE+window), highlight, snippet extraction"
```

---

### Task 3: Streamlit App — Browse View

**Files:**
- Rewrite: `explorer/app.py`
- Create: `explorer/assets/` (copy logos)

- [ ] **Step 1: Copy logos**

```bash
mkdir -p explorer/assets
cp demo/images/teal-insights-logo.png explorer/assets/
cp demo/images/naturefinance-logo.png explorer/assets/
```

- [ ] **Step 2: Write the app skeleton + browse view**

Rewrite `explorer/app.py`:

```python
"""Sovereign Bond Prospectus Explorer — V2.

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


# ── Connection ────────────────────────────────────────────────────


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


# ── External link helper ──────────────────────────────────────────


def ext_link(url: str, text: str) -> str:
    """HTML for an external link that opens in a new tab."""
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
        f"{text} ↗</a>"
    )


# ── Session state navigation ─────────────────────────────────────
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


# ── Filters ───────────────────────────────────────────────────────


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
        selected_country_names = st.multiselect(
            "Country", sorted(country_labels.values())
        )
        selected_codes = [
            code
            for code, name in country_labels.items()
            if name in selected_country_names
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


# ── Browse view ───────────────────────────────────────────────────


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

    # Search bar — use a form to prevent the text_input's persisted value
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
        pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
        with pcol1:
            if page > 0 and st.button("← Previous"):
                st.session_state["browse_page"] = page - 1
                st.rerun()
        with pcol3:
            if offset + limit < total and st.button("Next →"):
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
        + ", as part of an emerging \"SovTech\" approach -- open-source "
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


# ── Stubs (replaced in Tasks 4 and 5) ────────────────────────────
# These MUST be defined before main() to avoid NameError on first rerun.


def search_view(con):
    """Stub — replaced in Task 4."""
    st.warning("Search view not yet implemented")
    if st.button("← Back"):
        _navigate_to("browse")


def detail_view(con):
    """Stub — replaced in Task 5."""
    st.warning("Detail view not yet implemented")
    if st.button("← Back"):
        _navigate_to("browse")


# ── Main ──────────────────────────────────────────────────────────


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
```

- [ ] **Step 3: Build the sovereign_issuers table into the local DB**

```bash
uv run python -c "
import duckdb
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')
# Create table
ddl = Path('sql/002_sovereign_issuers.sql').read_text()
for stmt in ddl.split(';'):
    s = stmt.strip()
    if s:
        con.execute(s)

# Populate
from explorer.country_metadata import populate_sovereign_issuers
n = populate_sovereign_issuers(con)
print(f'Inserted {n} sovereign issuer mappings')
con.close()
"
```

Expected: `Inserted 261 sovereign issuer mappings` (or close -- deduplication
of "State of Montenegro" reduces it by 1).

- [ ] **Step 4: Test locally**

```bash
uv run streamlit run explorer/app.py
```

Open in browser. Verify:
- Logos appear (Teal Insights left, NatureFinance right)
- Stats show (~9,729 docs, 4 sources)
- Filter row appears with source, region, country
- "Include high-income countries" checkbox is unchecked
- Document table shows rows, newest first
- Unchecking high-income filters out Israel, UniCredit, Bank of Cyprus
- About section renders with external links opening in new tabs
- Clicking a document name shows the stub "Detail view not yet implemented"

- [ ] **Step 5: Commit**

```bash
git add explorer/app.py explorer/assets/
git commit -m "feat: explorer browse view with logos, filters, document table"
```

---

### Task 4: Search View

**Files:**
- Modify: `explorer/app.py` (replace `search_view` stub)

- [ ] **Step 1: Replace the search_view stub in app.py**

Replace the `search_view` stub with:

```python
def search_view(con):
    """Full-text search results."""
    query = st.session_state.get("search_query_submitted", "")

    if st.button("← Back to browse"):
        _navigate_to("browse")

    st.subheader(f'Search results for "{query}"')

    # Filters (same as browse)
    filters = render_filters(con)

    if not query:
        st.info("Enter a search term.")
        return

    from explorer.highlight import extract_snippet
    from explorer.queries import search_documents

    with st.spinner("Searching..."):
        results = search_documents(con, query, limit=50, **filters)

    if results.empty:
        st.warning(f'No results for "{query}". Try different terms or adjust filters.')
        return

    # Only say "showing top 50" if we actually hit the limit
    if len(results) >= 50:
        st.markdown(f"**Showing top 50 results** for _{query}_")
    else:
        st.markdown(f"**{len(results)} results** for _{query}_")

    for _, row in results.iterrows():
        display = row["display_name"]
        source = row["source"]
        date = row["publication_date"]
        date_str = str(date) if pd.notna(date) else "undated"
        page_num = row["page_number"]

        with st.expander(
            f"**{display}** -- {source} -- p.{page_num} -- {date_str}"
        ):
            snippet = extract_snippet(row["page_text"] or "", query)
            # Highlight the query in the snippet
            from explorer.highlight import highlight_text

            highlighted = highlight_text(snippet, query)
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
```

- [ ] **Step 2: Test search locally**

Restart Streamlit. Search for "collective action". Verify:
- Results appear with snippets
- Snippets have highlighted matches
- Source, date, page number shown
- "View full document" button navigates to detail stub

Search for "contingent liabilities". Verify results appear.

- [ ] **Step 3: Commit**

```bash
git add explorer/app.py
git commit -m "feat: search view with BM25, snippets, and highlighted matches"
```

---

### Task 5: Document Detail View

**Files:**
- Modify: `explorer/app.py` (replace `detail_view` stub)

- [ ] **Step 1: Replace the detail_view stub in app.py**

Replace the `detail_view` stub with:

```python
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
        if st.button("← Back"):
            _navigate_to("browse")
        return

    # Back button — use nav_origin to determine correct target
    nav_origin = st.session_state.get("nav_origin", "browse")
    back_label = "← Back to search results" if nav_origin == "search" else "← Back to browse"
    if st.button(back_label):
        _navigate_to(nav_origin)

    # Header
    st.title(detail["display_name"])

    # Metadata row
    meta_parts = [f"**Source:** {detail['source']}"]
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
        st.info(
            "Full text not yet available -- this document is being processed."
        )
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
    from explorer.queries import get_markdown

    md_text = get_markdown(con, doc_id)
    if not md_text:
        st.info("No markdown available.")
        return

    # Extract headings for ToC
    import re

    headings = re.findall(r"^(#{2,3})\s+(.+)$", md_text, re.MULTILINE)
    if headings:
        with st.expander("Table of Contents", expanded=False):
            for marker, title in headings:
                level = len(marker) - 2  # ## = 0 indent, ### = 1 indent
                indent = "\u00a0\u00a0\u00a0\u00a0" * level
                st.markdown(f"{indent}• {title}")

    # Highlight search terms if present
    if search_query:
        from explorer.highlight import highlight_text

        highlighted, count = highlight_text(
            md_text, search_query, return_count=True
        )
        if count > 100:
            st.info(f"{count} matches found -- showing first 100 highlights.")
        elif count > 0:
            st.info(f"{count} matches found.")
        else:
            st.warning(f'"{search_query}" not found in this document.')
        st.markdown(highlighted, unsafe_allow_html=True)
    else:
        st.markdown(md_text)


def _render_page_by_page(
    con, doc_id: int, max_page: int, start_page: int, search_query: str
):
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
            from explorer.highlight import highlight_text

            highlighted, count = highlight_text(
                text, search_query, return_count=True
            )
            st.markdown(f"**Page {page_num} of {max_page}** ({count} matches on this page)")
            # Show highlighted version inline (not hidden in expander)
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
        if page_num > 1 and st.button("← Previous page"):
            st.session_state["current_page"] = page_num - 1
            st.rerun()
    with nav2:
        if page_num < max_page and st.button("Next page →"):
            st.session_state["current_page"] = page_num + 1
            st.rerun()
```

- [ ] **Step 2: Test detail view locally**

Restart Streamlit. Click into a document from the browse table. Verify:
- Metadata row shows source, date, type, country, region
- "View original filing" link opens in new tab (test with an EDGAR doc)
- For a doc with markdown under 200KB: full markdown renders with ToC
- In-document search highlights matches and shows count
- For a large doc: page-by-page view with number input
- "Not yet available" message for unparsed docs
- Back button returns to browse or search

- [ ] **Step 3: Commit**

```bash
git add explorer/app.py
git commit -m "feat: document detail with hybrid markdown/page-by-page rendering"
```

---

### Task 6: Populate DB + End-to-End Test

**Files:**
- No new files. This task wires everything together.

- [ ] **Step 1: Add sovereign_issuers schema to the main schema loader**

Modify `src/corpus/db/schema.py` to also load `sql/002_sovereign_issuers.sql`:

Add after the existing `_DDL_FILE` line:

```python
_DDL_FILE_2 = Path(__file__).resolve().parents[3] / "sql" / "002_sovereign_issuers.sql"
```

And at the end of `create_schema`:

```python
    ddl2 = _DDL_FILE_2.read_text()
    lines2 = [line for line in ddl2.splitlines() if not line.strip().startswith("--")]
    cleaned2 = "\n".join(lines2)
    for statement in cleaned2.split(";"):
        stripped = statement.strip()
        if stripped:
            conn.execute(stripped)
```

- [ ] **Step 2: Add sovereign_issuers table to existing DB (do NOT rebuild)**

The existing DB already has 9,729 docs + 4,857 with pages + FTS index.
Rebuilding from scratch risks hours of re-ingestion. Instead, add the new
table to the existing DB:

```bash
uv run python -c "
import duckdb
from pathlib import Path

con = duckdb.connect('data/db/corpus.duckdb')

# Create the sovereign_issuers table
ddl = Path('sql/002_sovereign_issuers.sql').read_text()
for stmt in ddl.split(';'):
    s = stmt.strip()
    if s:
        con.execute(s)

# Populate it
from explorer.country_metadata import populate_sovereign_issuers
n = populate_sovereign_issuers(con)
print(f'Inserted {n} sovereign issuer mappings')
con.close()
"
```

Expected: `Inserted 263 sovereign issuer mappings` (261 original + 2 missed
variants caught in review).

- [ ] **Step 3: Run all tests**

```bash
uv run pytest tests/test_issuer_mapping.py tests/test_highlight.py tests/test_explorer_queries.py -v
```

Expected: All pass.

- [ ] **Step 4: Run Streamlit and test the full flow**

```bash
uv run streamlit run explorer/app.py
```

Test the full flow:
1. Landing page: logos, stats, search bar, filters, document table
2. Uncheck "Include high-income" -- Israel/UniCredit disappear
3. Search "collective action" -- results with highlighted snippets
4. Search "contingent liabilities" -- results appear
5. Click into a document -- markdown renders with ToC
6. In-document search -- highlights and match count
7. "View original filing" -- opens in new tab
8. Back to search -- previous results preserved
9. Try a LuxSE doc -- filing link goes to PDF download
10. Click an unparsed doc -- "not yet available" message

- [ ] **Step 5: Run lint and type checks**

```bash
uv run ruff check explorer/ tests/test_explorer_queries.py tests/test_highlight.py tests/test_issuer_mapping.py
uv run ruff format --check explorer/ tests/test_explorer_queries.py tests/test_highlight.py tests/test_issuer_mapping.py
```

Fix any issues.

- [ ] **Step 6: Commit**

```bash
git add src/corpus/db/schema.py
git commit -m "chore: load sovereign_issuers DDL in schema loader"
```

---

### Task 7: Add `populate-issuers` CLI Command

**Files:**
- Modify: `src/corpus/cli.py`

- [ ] **Step 1: Add CLI command**

Add after the `build_markdown` command in `src/corpus/cli.py`:

```python
@cli.command("populate-issuers")
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default="data/db/corpus.duckdb",
    help="Path to the DuckDB database file.",
)
def populate_issuers(db_path: Path) -> None:
    """Populate sovereign_issuers lookup table from hard-coded mapping."""
    import duckdb

    from corpus.db.schema import create_schema
    from explorer.country_metadata import populate_sovereign_issuers

    with duckdb.connect(str(db_path)) as conn:
        create_schema(conn)
        n = populate_sovereign_issuers(conn)
        click.echo(f"Sovereign issuers: {n} inserted.")
```

- [ ] **Step 2: Test it**

```bash
uv run corpus populate-issuers
```

Expected: `Sovereign issuers: 260 inserted.` (or 261 minus dedup).

- [ ] **Step 3: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: populate-issuers CLI command"
```

---

### Task 8: MotherDuck Publish + Streamlit Cloud Deploy

**Files:** No new files. This wires the local DB to the cloud.

**NOTE:** Task 8 requires the `MOTHERDUCK_TOKEN` environment variable to be
set. This is a secret that the human operator must provide. If running
autonomously, skip Task 8 and flag it for manual execution. The explorer
works locally without MotherDuck.

- [ ] **Step 1: Publish local DB to MotherDuck**

Requires `MOTHERDUCK_TOKEN` to be set in the shell environment.

```bash
uv run python -c "
import duckdb

# Connect to MotherDuck
con = duckdb.connect('md:', config={'motherduck_token': '$MOTHERDUCK_TOKEN'})

# Drop and recreate the database from local
con.execute('DROP DATABASE IF EXISTS sovereign_corpus')
con.execute('CREATE DATABASE sovereign_corpus')
con.execute('USE sovereign_corpus')

# Attach local DB and copy all tables
local = duckdb.connect('data/db/corpus.duckdb', read_only=True)
tables = [r[0] for r in local.execute('SHOW TABLES').fetchall()]
for table in tables:
    print(f'Copying {table}...')
    df = local.execute(f'SELECT * FROM {table}').fetchdf()
    con.execute(f'CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df')
    count = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'  {count} rows')

local.close()
print('All tables copied.')
"
```

- [ ] **Step 2: Build FTS index on MotherDuck**

```bash
uv run python -c "
import duckdb

con = duckdb.connect('md:sovereign_corpus', config={'motherduck_token': '$MOTHERDUCK_TOKEN'})
con.execute('INSTALL fts; LOAD fts')
con.execute(\"\"\"
    PRAGMA create_fts_index(
        'document_pages', 'page_id', 'page_text',
        stemmer='english', stopwords='english',
        ignore='(\\\\.|[^a-z])+',
        lower=1
    )
\"\"\")
print('FTS index created on MotherDuck')

# Quick test
result = con.execute(\"\"\"
    SELECT COUNT(*)
    FROM document_pages dp
    WHERE fts_main_document_pages.match_bm25(dp.page_id, 'collective action') IS NOT NULL
\"\"\").fetchone()
print(f'FTS test: {result[0]} pages match \"collective action\"')
con.close()
"
```

**Important:** If FTS creation fails on MotherDuck, the search feature will
not work on Streamlit Cloud. The `get_connection()` function does NOT fall
back to local DuckDB when a MotherDuck token is present -- it returns the
remote connection unconditionally. On Streamlit Cloud, no local DB exists.
Therefore, FTS must work on MotherDuck for the cloud demo. Test this step
carefully.

- [ ] **Step 3: Push branch and update Streamlit Cloud**

```bash
git push -u origin feature/explorer-v2
```

Then in Streamlit Cloud dashboard:
1. Update the app to point to the `feature/explorer-v2` branch
2. Verify `MOTHERDUCK_TOKEN` is set in Streamlit secrets
3. Verify Python version is 3.12 in Advanced Settings

- [ ] **Step 4: Test shareable URL**

Open the Streamlit Cloud URL in an incognito browser window. Verify:
- Page loads (may take 5-8s on cold start)
- Stats show correct counts
- Search "collective action" returns results
- Click into a document, verify markdown renders
- "View original filing" link works

Also test from phone to verify basic mobile layout.

- [ ] **Step 5: Warm up for demo**

Open the app URL 5 minutes before the demo to ensure it's not cold-starting
during the presentation.

---

## Verification Checklist

After all tasks complete, verify against the spec's success criteria:

1. [ ] Landing page loads with logos, stats, search bar, and document table
2. [ ] Search "collective action" returns results across multiple issuers
3. [ ] Search "contingent liabilities" finds results (Congo when available)
4. [ ] Click into a document, see rendered markdown with ToC
5. [ ] "View original filing" opens source website in new tab
6. [ ] In-document search highlights terms (inline, not hidden in expander)
7. [ ] Filters by source, region, income group, country all work
8. [ ] High-income excluded by default, one click to include
9. [ ] About section with SovTech framing and co-design invitation
10. [ ] Session state: browse -> search -> detail -> back -> back works cleanly
11. [ ] No infinite redirect when returning from search to browse
12. [ ] Unparsed docs show "not yet available" + provenance link
13. [ ] Works from shareable Streamlit Cloud URL (MotherDuck backend)
14. [ ] `uv run ruff check explorer/ tests/`
15. [ ] `uv run ruff format --check explorer/ tests/`
16. [ ] `uv run pytest tests/test_issuer_mapping.py tests/test_highlight.py tests/test_explorer_queries.py -v`
