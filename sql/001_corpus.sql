-- Sovereign Prospectus Corpus — core schema
-- Matches docs/RATIFIED-DECISIONS.md decisions 1, 9, 14, 18.

-- Sequences first (referenced in DEFAULT expressions)
CREATE SEQUENCE IF NOT EXISTS documents_seq START 1;
CREATE SEQUENCE IF NOT EXISTS grep_matches_seq START 1;
CREATE SEQUENCE IF NOT EXISTS source_events_seq START 1;

CREATE TABLE IF NOT EXISTS documents (
    document_id     INTEGER PRIMARY KEY DEFAULT nextval('documents_seq'),
    source          VARCHAR NOT NULL,           -- nsm | edgar | pdip
    native_id       VARCHAR NOT NULL,           -- source-specific identifier
    storage_key     VARCHAR NOT NULL UNIQUE,     -- {source}__{native_id}
    family_id       VARCHAR,                     -- links base + supplements + final terms
    doc_type        VARCHAR,                     -- prospectus, supplement, final_terms, etc.
    title           VARCHAR,
    issuer_name     VARCHAR,
    lei             VARCHAR,                     -- Legal Entity Identifier
    publication_date DATE,
    submitted_date  TIMESTAMP,
    download_url    VARCHAR,
    file_path       VARCHAR,                     -- relative path under data/original/
    file_hash       VARCHAR,                     -- SHA-256 of downloaded file
    page_count      INTEGER,
    parse_tool      VARCHAR,                     -- pymupdf | docling (decision 18)
    parse_version   VARCHAR,                     -- version string of parse tool
    is_sovereign    BOOLEAN DEFAULT true,        -- noise filter (decision 14)
    issuer_type     VARCHAR DEFAULT 'sovereign', -- sovereign | quasi-sovereign | corporate
    scope_status    VARCHAR DEFAULT 'in_scope',  -- in_scope | excluded | quarantine
    source_metadata VARCHAR,                     -- JSON blob for source-specific fields
    created_at      TIMESTAMP DEFAULT current_timestamp,
    updated_at      TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS document_countries (
    document_id  INTEGER NOT NULL REFERENCES documents(document_id),
    country_code VARCHAR NOT NULL,  -- ISO 3166-1 alpha-3
    country_name VARCHAR,
    role         VARCHAR DEFAULT 'issuer',  -- issuer | guarantor | related
    PRIMARY KEY (document_id, country_code, role)
);

CREATE TABLE IF NOT EXISTS grep_matches (
    match_id        INTEGER PRIMARY KEY DEFAULT nextval('grep_matches_seq'),
    document_id     INTEGER NOT NULL REFERENCES documents(document_id),
    pattern_name    VARCHAR NOT NULL,    -- e.g. cac_single_limb, pari_passu
    pattern_version VARCHAR NOT NULL,    -- versioned pattern from config
    page_number     INTEGER,
    matched_text    VARCHAR NOT NULL,
    context_before  VARCHAR,
    context_after   VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
);

-- Page convention: page_index columns are 0-indexed (pdip_clauses.page_index).
-- page_number columns are 1-indexed (grep_matches.page_number).
-- Display layers (CLI, views, reports) always show 1-indexed page numbers.

ALTER TABLE grep_matches ADD COLUMN IF NOT EXISTS run_id VARCHAR;

CREATE SEQUENCE IF NOT EXISTS pdip_clauses_seq START 1;

CREATE TABLE IF NOT EXISTS pdip_clauses (
    pdip_clause_id  INTEGER PRIMARY KEY DEFAULT nextval('pdip_clauses_seq'),
    doc_id          VARCHAR NOT NULL,
    storage_key     VARCHAR,               -- e.g. pdip__VEN85 (joins to documents)
    clause_id       VARCHAR NOT NULL,      -- Label Studio annotation ID
    label           VARCHAR NOT NULL,
    label_family    VARCHAR,               -- mapped clause family (nullable)
    page_index      INTEGER,               -- 0-indexed page number
    text            VARCHAR,               -- clause text (nullable if empty/missing)
    text_status     VARCHAR NOT NULL,       -- present | empty | missing
    bbox            JSON,                  -- {x, y, width, height}
    original_dims   JSON,                  -- {width, height}
    country         VARCHAR,
    instrument_type VARCHAR,
    governing_law   VARCHAR,
    currency        VARCHAR,
    document_title  VARCHAR,
    created_at      TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS source_events (
    event_id    INTEGER PRIMARY KEY DEFAULT nextval('source_events_seq'),
    source      VARCHAR NOT NULL,
    native_id   VARCHAR NOT NULL,
    event_type  VARCHAR NOT NULL,  -- new_filing | updated_filing | removed
    detected_at TIMESTAMP DEFAULT current_timestamp,
    metadata    VARCHAR             -- JSON blob
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id     VARCHAR NOT NULL,
    step       VARCHAR NOT NULL,    -- download | parse | grep | extract | ingest
    started_at TIMESTAMP DEFAULT current_timestamp,
    ended_at   TIMESTAMP,
    status     VARCHAR DEFAULT 'running',  -- running | completed | failed
    doc_count  INTEGER DEFAULT 0,
    error_msg  VARCHAR,
    PRIMARY KEY (run_id, step)
);
