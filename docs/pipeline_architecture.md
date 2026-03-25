# Sovereign Bond Prospectus Corpus — Pipeline Architecture

**Project**: Building an AI-enabled pipeline to download, extract, and analyze sovereign bond prospectuses at scale.

**Timeline**: 6 days (March 24-30, 2026), with primary deliverable for #PublicDebtIsPublic Scoping Roundtable at Georgetown Law.

**Constraints**:
- Limited Teal time (mac mini does the heavy lifting)
- $0 marginal cost (Claude Max plan, ChatGPT Pro, Gemini — all unlimited)
- Compute: Mac Mini running 24/7
- Tools: Claude Code (Opus 4.6), Codex CLI, Python/uv/ruff, VS Code

---

## Overview

The pipeline has three main stages:

1. **Download Pipeline**: Fetch sovereign bond prospectuses from multiple sources (NSM, EDGAR, Luxembourg, Dublin)
2. **Processing Pipeline**: Extract text, identify clauses, store metadata and results
3. **Analysis Pipeline**: Cross-document analysis, synthesis for the roundtable

This document focuses on stages 1 and 2, which are the foundation.

---

## Stage 1: Download Pipeline

### Goal

Download as many sovereign bond prospectuses as possible from multiple sources, starting with NSM and expanding to EDGAR, Luxembourg Stock Exchange, and Euronext Dublin.

**Start small, scale up**: 1 country → 10 countries → all countries

### Rate Limiting & Responsible Access

The Mac Mini runs 24/7, so slow downloads are acceptable and preferable.

- **Exponential backoff**: Start with 2-second delays between requests. On `429` or `503`, double the delay (2s → 4s → 8s → 16s → ...). Cap at 5 minutes between requests.
- **Concurrent requests**: Limit to 1 active download per source at any time. Queue additional requests.
- **User-Agent**: Rotate between realistic user agents; include project contact email in requests where possible (transparency).
- **Request logging**: Every request logged with timestamp, URL, status code, and response headers.

**Rationale**: We want to be responsible citizens of the financial data commons. Rate limiting isn't a problem when you have 24/7 compute.

### Error Handling

The pipeline must gracefully recover from:

- **Network timeouts**: Automatic retry with exponential backoff. Log and skip after 3 failed attempts (logged for manual review).
- **Rate limiting (429, 503)**: Implement backoff. Wait and retry.
- **Server errors (5xx)**: Retry with backoff; skip if persistent.
- **Mac Mini sleep/restart**: Checkpoint system allows resumption from last completed download.
- **Partial downloads**: Verify file hash against source metadata. Re-download if incomplete.
- **Connection drops mid-download**: Resume from byte offset if source supports `Range` headers; otherwise re-download.

### Metadata Database

**SQLite database** (`data/db/prospectus_metadata.db`) tracks every document:

```sql
CREATE TABLE documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,              -- 'nsm', 'edgar', 'luxembourg', 'dublin'
  source_url TEXT NOT NULL UNIQUE,   -- original URL on source platform
  download_url TEXT,                 -- final PDF URL after redirects
  filing_date TEXT,                  -- date filing submitted
  document_date TEXT,                -- date document issued
  issuer_name TEXT,                  -- name of bond issuer
  country TEXT NOT NULL,             -- ISO 2-letter country code
  lei TEXT,                          -- Legal Entity Identifier if available
  isin TEXT,                         -- ISIN if available
  document_type TEXT,                -- base_prospectus, supplement, final_terms, etc.
  currency TEXT,                     -- USD, EUR, GBP, etc.
  amount_issued REAL,                -- amount in millions or as stated
  maturity_date TEXT,                -- expected maturity
  coupon_rate REAL,                  -- if fixed
  file_hash TEXT,                    -- SHA-256 of downloaded PDF
  file_size_bytes INTEGER,           -- size of downloaded file
  download_timestamp DATETIME,       -- when downloaded
  http_status_code INTEGER,          -- final HTTP status code
  http_headers TEXT,                 -- JSON blob of relevant headers (content-type, last-modified, etc.)
  processing_status TEXT,            -- 'downloaded', 'text_extracted', 'clauses_extracted', 'verified'
  text_extraction_error TEXT,        -- error message if text extraction failed
  clause_extraction_error TEXT,      -- error message if clause extraction failed
  notes TEXT,                        -- any manual notes
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE download_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  attempt_number INTEGER,
  timestamp DATETIME,
  status_code INTEGER,
  error_message TEXT,
  backoff_delay_seconds REAL,
  bytes_downloaded INTEGER,
  duration_seconds REAL
);

CREATE TABLE extracted_text (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  full_text TEXT NOT NULL,
  page_count INTEGER,
  extraction_method TEXT,            -- 'docling', 'pdfplumber', etc.
  extraction_timestamp DATETIME,
  confidence REAL,                   -- if applicable
  UNIQUE(document_id)
);

CREATE TABLE extracted_clauses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  clause_type TEXT,                 -- 'cac', 'pari_passu', 'events_of_default', etc.
  clause_text TEXT,
  location_page INTEGER,
  confidence REAL,
  extraction_model TEXT,            -- 'claude-opus-4.6', 'gpt-4', etc.
  extraction_timestamp DATETIME,
  verified_by TEXT,                 -- 'claude', 'gpt4', 'human', null
  verification_timestamp DATETIME
);

CREATE INDEX idx_documents_country ON documents(country);
CREATE INDEX idx_documents_source ON documents(source);
CREATE INDEX idx_documents_status ON documents(processing_status);
CREATE INDEX idx_clauses_type ON extracted_clauses(clause_type);
```

### Resumability & Checkpointing

The download pipeline must be resumable:

- **Checkpoint file**: `data/checkpoint.json` records the last successfully downloaded document ID and timestamp.
- **Restart logic**: On startup, read checkpoint and resume from next document.
- **Commit frequency**: Write checkpoint every 10 documents (configurable).
- **State validation**: Before resuming, verify that the last checkpoint document actually exists on disk with correct hash.

Example checkpoint:

```json
{
  "last_completed_document_id": 427,
  "last_completed_timestamp": "2026-03-25T14:32:18Z",
  "source": "nsm",
  "country": "Senegal",
  "documents_downloaded_total": 427,
  "documents_failed": 3,
  "start_time": "2026-03-24T08:00:00Z"
}
```

### File Organization

Downloaded PDFs organized by source and country:

```
data/pdfs/
├── nsm/
│   ├── senegal/
│   │   ├── SN_2024-01_WAEMU_Bond_Prospectus.pdf
│   │   ├── SN_2024-02_Eurobond_Base_Prospectus.pdf
│   │   └── ...
│   ├── ghana/
│   │   └── ...
│   └── ...
├── edgar/
│   ├── united_states/
│   └── ...
├── luxembourg/
└── dublin/
```

**Filename convention**: `{COUNTRY_CODE}_{YYYY-MM-DD}_{DOCUMENT_TYPE}_{ISSUER_SLUG}.pdf`
- Example: `SN_2024-01-15_Base_Prospectus_WAEMU_Ecowas_Fund.pdf`

This structure makes it easy to browse, audit, and selectively re-process.

### Logging

**Comprehensive logging** to both file and stdout:

- **Main log**: `logs/download.log` — all download activity
- **Error log**: `logs/download_errors.log` — errors only, easier to spot problems
- **Format**:
  ```
  2026-03-25T14:32:18.123Z [INFO] [NSM] [Senegal] Downloaded doc_id=427: SN_2024-01_Base_Prospectus.pdf (2.3 MB, SHA256: a1b2c3...)
  2026-03-25T14:32:45.456Z [WARN] [NSM] [Ghana] HTTP 429 on attempt 2. Backing off 8 seconds.
  2026-03-25T14:35:22.789Z [ERROR] [NSM] [Zambia] Max retries exceeded (3 attempts). Skipping doc_id=445.
  ```

- **Rotate logs**: Keep last 7 days of logs; archive older ones to `logs/archive/`.

---

## Stage 2: Processing Pipeline

### Text Extraction

**Tool**: Docling (or pdfplumber as fallback)

- **Input**: PDF file from `data/pdfs/{source}/{country}/`
- **Output**: Plain text file to `data/text/{source}/{country}/`
- **Metadata**: Store extraction method, page count, any errors in SQLite
- **Robustness**: Log OCR confidence, flag low-confidence extractions for manual review

**Constraints**: Runs locally on Mac Mini. Docling is fast enough for 24/7 processing.

### Clause Extraction

**Primary tool**: Claude Code (Opus 4.6) — unlimited marginal cost on Max plan

**Verification**: Codex CLI (ChatGPT Pro) on a stratified sample (~5-10% of documents)

**Process**:

1. Read extracted text from `data/text/{source}/{country}/`
2. Prompt Claude with contract language and ask for structured extraction of:
   - **Collective Action Clauses (CACs)**: Majority threshold, supermajority requirements, aggregation language
   - **Pari Passu**: Claims of equal treatment, subordination language
   - **Events of Default**: Triggers for accelerated repayment, material adverse change clauses
   - **Governing Law & Jurisdiction**: Which country's law governs, where disputes resolved
   - **Cross-Default**: Links to other instruments
   - **Acceleration & Remedies**: How lenders enforce
   - **Amendment Provisions**: How contract can be modified
   - **Any other material terms**: Unusual features, collateral, guarantees, etc.

3. Store results in `extracted_clauses` table with:
   - Clause type
   - Extracted text
   - Page reference
   - Model used (claude-opus-4.6)
   - Confidence (if model provides)

4. On verification pass with Codex:
   - Select 5-10% of documents stratified by country and document type
   - Feed Codex the same text + original extraction
   - Ask: "Do you agree with these extracted clauses? Any omissions or errors?"
   - Log agreement/disagreement
   - Flag discrepancies for Teal review

**Run with Claude Code**:
```bash
claude code --dangerously-skip-permissions run-clause-extraction.py
```

This allows unattended operation on Mac Mini.

### Data Flow

```
Download Pipeline
    ↓
    PDF files → data/pdfs/{source}/{country}/
    ↓
Text Extraction (Docling)
    ↓
    Plain text → data/text/{source}/{country}/
    ↓
Clause Extraction (Claude Code)
    ↓
    Structured clauses → data/db/prospectus_metadata.db (extracted_clauses table)
    ↓
Verification (Codex CLI, sample)
    ↓
    Confidence scores + manual flags → database
    ↓
Analysis & Export
    ↓
    JSON, CSV, markdown summaries → data/exports/
```

### Git-Based Development

**Trunk-based development**:
- Main branch: `main` (always stable, deployable)
- Feature branches: `feature/nsm-downloader`, `feature/edgar-integration`, etc.
- Each branch solves one problem
- Merge when tested; delete branch

**Commit discipline**:
```
Implement NSM download with exponential backoff

- Add NsmDownloader class with configurable delays
- Implement checkpoint system for resumability
- Add comprehensive logging to file and stdout
- Test with 10 documents from Senegal

Fixes #3
```

### Project Structure

```
sovereign-prospectus-corpus/
├── pyproject.toml                  # Project config, dependencies
├── .python-version                 # Python 3.11+
├── CLAUDE.md                       # Project context for Claude Code
├── README.md                       # User-facing documentation
├── .gitignore                      # Exclude data/, logs/, .venv/
│
├── src/
│   └── sovereign_corpus/
│       ├── __init__.py
│       ├── config.py               # Configuration, constants, env vars
│       ├── logging.py              # Logging setup
│       │
│       ├── download/
│       │   ├── __init__.py
│       │   ├── base.py             # BaseDownloader abstract class
│       │   ├── nsm.py              # NsmDownloader (NSM-specific logic)
│       │   ├── edgar.py            # EdgarDownloader (future)
│       │   ├── luxembourg.py       # LuxembourgDownloader (future)
│       │   └── dublin.py           # DublinDownloader (future)
│       │
│       ├── extract/
│       │   ├── __init__.py
│       │   ├── text.py             # PDF → text extraction (Docling)
│       │   └── clauses.py          # Clause identification (Claude API)
│       │
│       ├── analyze/
│       │   ├── __init__.py
│       │   └── compare.py          # Cross-document analysis
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py           # SQLAlchemy models / raw SQL schema
│       │   ├── queries.py          # Common queries (reusable)
│       │   └── init.py             # Schema initialization
│       │
│       └── utils/
│           ├── __init__.py
│           ├── file.py             # File operations (hash, move, etc.)
│           └── http.py             # HTTP utilities (retry logic, headers)
│
├── scripts/
│   ├── download_nsm.py             # CLI: python scripts/download_nsm.py
│   ├── extract_text.py             # CLI: python scripts/extract_text.py
│   ├── extract_clauses.py          # CLI: python scripts/extract_clauses.py
│   └── verify_sample.py            # CLI: python scripts/verify_sample.py
│
├── data/
│   ├── pdfs/                       # Downloaded PDFs (not in git)
│   │   ├── nsm/{country}/
│   │   ├── edgar/{country}/
│   │   ├── luxembourg/{country}/
│   │   └── dublin/{country}/
│   ├── text/                       # Extracted text (not in git)
│   │   └── {source}/{country}/
│   ├── db/                         # SQLite database (not in git)
│   │   └── prospectus_metadata.db
│   ├── exports/                    # Analysis outputs (git tracked)
│   │   ├── summary.json
│   │   ├── clauses_by_country.csv
│   │   └── case_study_senegal.md
│   └── checkpoint.json             # Last download state (not in git)
│
├── logs/
│   ├── download.log                # Main download log (not in git)
│   ├── download_errors.log         # Error log only (not in git)
│   └── archive/                    # Older logs (not in git)
│
└── tests/
    ├── test_nsm_downloader.py
    ├── test_text_extraction.py
    ├── test_clause_extraction.py
    └── fixtures/                   # Sample PDFs for testing
```

---

## Mac Mini Setup Guide

### Prevent Sleep

```bash
# Disable sleep entirely
sudo pmset -a sleep 0 disablesleep 1

# Disable display sleep
sudo pmset -a displaysleep 0

# Enable auto-restart after power failure (good insurance)
sudo pmset -a autorestart 1
```

Verify with:
```bash
pmset -g
```

### Persistent Terminal Sessions

Use **tmux** or **screen** to keep processes running even if terminal closes:

```bash
# Install tmux if needed
brew install tmux

# Start a new session
tmux new-session -d -s download -c ~/sovereign-prospectus-corpus

# Attach to session
tmux attach -t download

# Detach: Ctrl+B, then D

# List sessions
tmux list-sessions
```

### Background Processing

For long-running tasks, use `nohup`:

```bash
nohup python scripts/download_nsm.py > logs/download_nohup.log 2>&1 &
```

Or use `caffeinate` to prevent sleep during a specific command:

```bash
caffeinate -i python scripts/download_nsm.py
```

(`-i` = prevent idle sleep while command runs)

### Automated Runs with launchd

Create a plist file for launchd to run downloads on schedule:

`~/Library/LaunchAgents/com.teal.sovereign-corpus.download.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.teal.sovereign-corpus.download</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/teal/sovereign-prospectus-corpus/scripts/download_nsm.py</string>
    </array>
    <key>StandardOutPath</key>
    <string>/Users/teal/sovereign-prospectus-corpus/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/teal/sovereign-prospectus-corpus/logs/launchd_errors.log</string>
    <key>StartInterval</key>
    <integer>3600</integer>
    <!-- Run every 3600 seconds (1 hour) -->
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.teal.sovereign-corpus.download.plist
```

### Monitoring

Check resource usage with **htop** or **Activity Monitor**:

```bash
brew install htop
htop
```

Or use Activity Monitor GUI (Applications → Utilities).

Monitor disk usage:

```bash
df -h
du -sh data/
```

Alert on low disk space (add to monitoring script):

```python
import shutil
_, _, free = shutil.disk_usage("/")
if free < 10e9:  # Less than 10 GB free
    logger.warning(f"Low disk space: {free / 1e9:.1f} GB remaining")
```

### Git Auto-Commit Progress

Add a periodic commit hook to track progress:

`scripts/auto_commit.py`:

```python
#!/usr/bin/env python3
import subprocess
import datetime

def commit_progress():
    timestamp = datetime.datetime.now().isoformat()
    result = subprocess.run(
        ["git", "add", "data/exports/", "logs/"],
        cwd="/path/to/repo",
        capture_output=True
    )
    if result.returncode == 0:
        subprocess.run(
            ["git", "commit", "-m", f"Auto-commit progress: {timestamp}"],
            cwd="/path/to/repo"
        )

if __name__ == "__main__":
    commit_progress()
```

Add to launchd or cron to run every 6 hours.

---

## Risk Register

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|-----------|
| 1 | **Rate limiting (429, 503)** | Downloads blocked for hours | Medium | Exponential backoff, configurable delays, queue system. Start conservative (2s delays). |
| 2 | **Server downtime** | Missing documents, timeline pressure | Medium | Retry with backoff. Log and skip gracefully after 3 attempts. Resume with checkpoint. |
| 3 | **PDF format variations** | Text extraction fails on some documents | Medium-High | Robust parser (Docling). Log extraction errors. Flag for manual review. Have fallback (OCR). |
| 4 | **Mac Mini power loss** | Lost progress, data corruption | Low-Medium | Checkpoint system. Auto-restart enabled. SQLite ACID guarantees. Verify file hashes on resume. |
| 5 | **Disk space exhaustion** | Pipeline crashes, data loss risk | Low | Monitor `du -sh data/`. Alert at 80% capacity. Estimate: ~2-3 MB per document. 500 docs = 1-1.5 GB. |
| 6 | **Claude Code rate limits** | Clause extraction blocked | Low | Queue system. Rotate between models (Claude, GPT, Gemini). Batch requests. |
| 7 | **Network interruption** | Download interrupted mid-file | Medium | Support HTTP `Range` headers for resume. Fall back to re-download. Log attempt count. |
| 8 | **Corrupt PDFs** | Downloaded file is invalid | Low-Medium | SHA-256 hash verification. Re-download if mismatch. Log corrupted documents. |
| 9 | **Two-hop URL resolution** | Final PDF URL not found | Low | Multiple parsing strategies (link extraction, metadata inspection). Fallback to browser automation (Selenium). |
| 10 | **API schema changes** | NSM API changes break downloader | Low | Version-pin dependencies. Add integration tests. Monitor API responses. |

---

## Success Criteria for March 30

**For the roundtable**:
- [ ] 500+ prospectuses downloaded (demonstrating scale)
- [ ] 2-5 deeply processed documents with extracted clauses (quality demonstration)
- [ ] Case study: Senegal bond prospectus with clause analysis (real example)
- [ ] Compelling narrative: "900 PDIP documents are a validation set, not just a resource"
- [ ] Technical credibility: Architecture doc, reproducible pipeline, code on GitHub

**Stretch goals**:
- [ ] Ghana or Zambia case study (recent restructuring cases)
- [ ] Comparison: PDIP's hand-annotated clauses vs. AI-extracted clauses (if PDIP data accessible)
- [ ] Prototype of searchable database (simple web interface or Jupyter notebook)

---

## Future Expansion (Post-Roundtable)

- Integrate EDGAR (US Treasuries), Luxembourg Stock Exchange, Euronext Dublin
- Add more clause types (credit enhancements, subordination, commodity-backed provisions)
- Train custom clause extraction model on PDIP's 900 documents
- Build web interface for searching and filtering
- Connect to debt restructuring timelines (track how clauses change over time)
- Cross-reference with IMF-World Bank debt surveys
