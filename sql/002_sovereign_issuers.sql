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
