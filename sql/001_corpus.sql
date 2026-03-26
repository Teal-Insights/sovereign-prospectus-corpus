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
    document_id  INTEGER NOT NULL,
    country_code VARCHAR NOT NULL,  -- ISO 3166-1 alpha-3
    country_name VARCHAR,
    role         VARCHAR DEFAULT 'issuer',  -- issuer | guarantor | related
    PRIMARY KEY (document_id, country_code, role)
);

CREATE TABLE IF NOT EXISTS grep_matches (
    match_id        INTEGER PRIMARY KEY DEFAULT nextval('grep_matches_seq'),
    document_id     INTEGER NOT NULL,
    pattern_name    VARCHAR NOT NULL,    -- e.g. cac_single_limb, pari_passu
    pattern_version VARCHAR NOT NULL,    -- versioned pattern from config
    page_number     INTEGER,
    matched_text    VARCHAR NOT NULL,
    context_before  VARCHAR,
    context_after   VARCHAR,
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
