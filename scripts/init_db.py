#!/usr/bin/env python3
"""
Initialize SQLite database for Sovereign Bond Prospectus Corpus.
Implements all council decisions from CLAUDE.md:
- SQLite as single source of truth
- Status columns for resumability
- Document families
- Quarantine tracking
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

# Database path
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "db" / "corpus.db"

def create_schema(conn):
    """Create all tables with proper constraints."""
    cursor = conn.cursor()
    
    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        country TEXT NOT NULL,
        issuer TEXT,
        lei TEXT,
        doc_type TEXT,
        headline TEXT,
        source TEXT DEFAULT 'manual',
        source_url TEXT,
        pdf_url TEXT,
        local_path TEXT,
        text_path TEXT,
        filing_date TEXT,
        submitted_date TEXT,
        file_size_bytes INTEGER,
        file_hash TEXT,
        page_count INTEGER,
        word_count INTEGER,
        status TEXT DEFAULT 'PENDING' CHECK(
            status IN (
                'PENDING', 'DOWNLOADING', 'DOWNLOADED',
                'PARSE_FAILED', 'PARSING', 'PARSED',
                'EXTRACTING', 'EXTRACTED', 'FAILED'
            )
        ),
        quarantine_reason TEXT,
        family_id TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
    """)
    
    # Clause extractions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clause_extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT NOT NULL REFERENCES documents(id),
        clause_type TEXT NOT NULL,
        verbatim_quote TEXT NOT NULL,
        page_number INTEGER NOT NULL,
        page_range_start INTEGER,
        page_range_end INTEGER,
        context_before TEXT,
        context_after TEXT,
        confidence REAL,
        verified_by TEXT,
        verified_at TEXT,
        extraction_model TEXT,
        extraction_prompt_version TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)
    
    # Grep matches table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS grep_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT NOT NULL REFERENCES documents(id),
        clause_type TEXT NOT NULL,
        page_number INTEGER NOT NULL,
        match_count INTEGER,
        sample_matches TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)
    
    # Pipeline log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pipeline_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT,
        action TEXT NOT NULL,
        status TEXT,
        details TEXT,
        duration_seconds REAL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)
    
    conn.commit()
    print("Schema created successfully")

def insert_ghana_documents(conn):
    """Insert the 4 Ghana documents that were already downloaded."""
    cursor = conn.cursor()
    
    documents = [
        (
            "NI-000022044-0",
            "Ghana",
            "THE REPUBLIC OF GHANA",
            "213800PP4399SNNXZ126",
            "base_prospectus",
            None,
            "NSM",
            None,
            None,
            "data/pdfs/ghana/ghana_2021-03-24_base_prospectus_NI-000022044.pdf",
            "data/text/ghana/ghana_2021-03-24_base_prospectus_NI-000022044.txt",
            "2021-03-24",
            None,
            2073685,
            "ad62b57cd823d0a377e151f55d32c842",
            252,
            153695,
            "PARSED",
            None,
        ),
        (
            "262895144",
            "Ghana",
            None,
            None,
            "base_prospectus",
            None,
            "NSM",
            None,
            None,
            "data/pdfs/ghana/ghana_2020-02-05_base_prospectus_262895144.pdf",
            "data/text/ghana/ghana_2020-02-05_base_prospectus_262895144.txt",
            "2020-02-05",
            None,
            2095098,
            "27ee16d0adc04e5a80ad6455c6df1c4c",
            232,
            142809,
            "PARSED",
            None,
        ),
        (
            "215283187",
            "Ghana",
            None,
            None,
            "base_prospectus",
            None,
            "NSM",
            None,
            None,
            "data/pdfs/ghana/ghana_2019-03-18_base_prospectus_215283187.pdf",
            "data/text/ghana/ghana_2019-03-18_base_prospectus_215283187.txt",
            "2019-03-18",
            None,
            78406,
            None,
            1,
            332,
            "PARSED",
            "Single page cover sheet, not full prospectus",
        ),
        (
            "171818118",
            "Ghana",
            None,
            None,
            "prospectus",
            None,
            "NSM",
            None,
            None,
            "data/pdfs/ghana/ghana_2018-05-14_prospectus_171818118.pdf",
            "data/text/ghana/ghana_2018-05-14_prospectus_171818118.txt",
            "2018-05-14",
            None,
            1453664,
            "e7eaa84e72b2fa988d17e882c77476b2",
            177,
            105450,
            "PARSED",
            None,
        ),
    ]
    
    cursor.executemany("""
        INSERT INTO documents (
            id, country, issuer, lei, doc_type, headline,
            source, source_url, pdf_url, local_path, text_path,
            filing_date, submitted_date, file_size_bytes, file_hash,
            page_count, word_count, status, quarantine_reason
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, documents)
    
    conn.commit()
    print(f"Inserted {len(documents)} Ghana documents")

def main():
    """Initialize the database."""
    # Create db directory if needed
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if present
    if DB_PATH.exists():
        print(f"Removing existing database at {DB_PATH}")
        DB_PATH.unlink()
    
    # Create and initialize database
    conn = sqlite3.connect(str(DB_PATH))
    try:
        create_schema(conn)
        insert_ghana_documents(conn)
        print(f"\nDatabase initialized successfully at {DB_PATH}")
        
        # Verify by querying
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as doc_count FROM documents")
        count = cursor.fetchone()[0]
        print(f"Verification: {count} documents in database")
        
        # Show table info
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = cursor.fetchall()
        print(f"Tables created: {', '.join([t[0] for t in tables])}")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
