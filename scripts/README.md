# Sovereign Bond Prospectus Bulk Downloader

## Overview

`nsm_bulk_download.py` is a production-grade pipeline for downloading sovereign bond prospectuses from the FCA National Storage Mechanism (NSM) overnight, unattended.

**Key features:**
- Grep-first clause finding (locate clauses before processing)
- Atomic PDF downloads (download to `.part`, validate, then rename)
- Inline Group A processing (text extraction, hashing, clause scanning)
- Comprehensive error handling and circuit breaker logic
- JSONL telemetry (one JSON per download event)
- SQLite resumability (status columns allow pause/resume)
- Signal handling (SIGINT/SIGTERM for clean shutdown)
- Adaptive throttling (429/timeout trigger exponential backoff)

## Architecture

The script implements these decisions from `CLAUDE.md`:

1. **CorpusDB class**: Thin SQLite wrapper with WAL mode
2. **Country priority tiers**: 4 tiers (defaulted, frontier, EM-IG, developed)
3. **Prospectus types**: Filters for publication, base prospectus, supplementary, final terms
4. **Two-hop resolution**: Handles HTML metadata pages that link to PDFs
5. **Atomic writes**: Prevents corrupted PDFs (always validate before rename)
6. **Group A processing**: Inline extraction of text, metadata, and clause matches
7. **JSONL telemetry**: One JSON object per download for analysis

## Usage

### Basic download (all countries, all tiers)
```bash
python scripts/nsm_bulk_download.py
```

### Download only Tier 1 (defaulted countries)
```bash
python scripts/nsm_bulk_download.py --tiers 1
```

### Test run (Tier 1, max 10 documents)
```bash
python scripts/nsm_bulk_download.py --tiers 1 --limit 10
```

### Dry run (list what would be downloaded, no actual downloads)
```bash
python scripts/nsm_bulk_download.py --dry-run
```

### Custom config file
```bash
python scripts/nsm_bulk_download.py --config /path/to/config.toml
```

### Tier syntax
- `--tiers 1` = Tier 1 only
- `--tiers 1,2` = Tiers 1 and 2
- `--tiers 1,2,3,4` = All tiers (default)

## Configuration

Edit `config.toml` to adjust:

```toml
[nsm]
delay_api = 1.0          # seconds between API queries
delay_download = 1.0     # seconds between PDFs
max_retries = 5
backoff_factor = 0.5
timeout = 60             # HTTP timeout

[nsm.circuit_breaker]
consecutive_failures_skip_country = 5
rate_limit_sleep_seconds = 660   # 11 minutes on 429s
total_failures_abort = 10
```

## Database

SQLite database at `data/db/corpus.db`:

**documents table:**
- `id` (TEXT): Unique document ID
- `country`, `issuer`, `lei`, `doc_type`, `headline`
- `status`: PENDING → DOWNLOADING → DOWNLOADED → PARSED → EXTRACTED
- `file_hash`, `page_count`, `word_count`, `estimated_tokens`
- `quarantine_reason`: If failed parsing
- `created_at`, `updated_at`

**grep_matches table:**
- Stores clause type scan results per document
- `clause_type`: CAC, PARI_PASSU, EVENTS_OF_DEFAULT, etc.
- `match_count`: Number of matches in document

**pipeline_log table:**
- Audit trail of all actions

## Output Structure

```
data/
├── pdfs/nsm/
│   ├── ghana/
│   │   └── ghana_2024-01-15_doc-id.pdf
│   ├── senegal/
│   └── ...
├── text/nsm/
│   ├── ghana/
│   │   └── doc-id.txt
│   └── ...
├── telemetry/
│   └── nsm_run_2026-03-25.jsonl
└── db/
    └── corpus.db
```

## Telemetry (JSONL)

Each download event is logged to `data/telemetry/nsm_run_YYYY-MM-DD.jsonl`:

```json
{
  "timestamp": "2026-03-25T14:30:12.345Z",
  "country": "Ghana",
  "doc_id": "doc-12345",
  "headline": "Publication of a Prospectus",
  "status": "downloaded",
  "download_duration_seconds": 2.5,
  "content_length_bytes": 2100000,
  "two_hop_required": true,
  "two_hop_duration_seconds": 0.8,
  "group_a_status": "success",
  "page_count": 232,
  "word_count": 142809,
  "estimated_tokens": 35700,
  "clause_matches": {
    "CAC": 5,
    "PARI_PASSU": 3
  }
}
```

## Logging

Logs are written to:
- `logs/nsm_bulk_download_YYYY-MM-DD_HH-MM-SS.log` (file)
- `stderr` (console, INFO level)

Example:
```
2026-03-25 14:30:12 [INFO    ] __main__: Loaded config from config.toml
2026-03-25 14:30:13 [INFO    ] __main__: Starting downloads for Ghana...
2026-03-25 14:30:15 [INFO    ] __main__: Downloaded: doc-12345 (2050.5KB)
```

## Country Priority Tiers

**Tier 1: Defaulted/Distressed (7 countries)**
- Ghana, Ukraine, Zambia, Belarus, Gabon, Sri Lanka, Congo

**Tier 2: Frontier/EM Sub-Investment Grade (13 countries)**
- Nigeria, Egypt, Angola, Montenegro, Kenya, Bahrain, Albania, Jordan, Cameroon, Morocco, Rwanda, Bosnia and Herzegovina, Srpska

**Tier 3: EM Investment Grade / Gulf (8 countries)**
- UAE - Abu Dhabi, Serbia, Saudi Arabia, Kazakhstan, Uzbekistan, Oman, Qatar, Kuwait

**Tier 4: Developed Markets / Control Group (7 countries)**
- Israel, Hungary, Cyprus, Sweden, Canada, Finland, Iceland

## Clause Types Scanned (Group A)

The script scans documents for these 10 clause types:

1. **CAC**: Collective Action Clause
2. **PARI_PASSU**: Pari Passu / Equal Ranking
3. **EVENTS_OF_DEFAULT**: Events of Default
4. **GOVERNING_LAW**: Governing Law
5. **NEGATIVE_PLEDGE**: Negative Pledge
6. **SOVEREIGN_IMMUNITY**: Sovereign Immunity / Waiver
7. **CROSS_DEFAULT**: Cross-Default
8. **EXTERNAL_INDEBTEDNESS**: External Indebtedness
9. **ACCELERATION**: Acceleration
10. **TRUSTEE_FISCAL_AGENT**: Trustee / Fiscal Agent

Matches are logged in `grep_matches` table (used for later extraction).

## Error Handling

**Circuit Breaker:** 5 consecutive failures for a country → skip to next country

**Rate Limiting:** 3x HTTP 429 → sleep 11 minutes

**PDF Validation:** Check `%PDF` header; reject invalid files

**Text Extraction:** Files that fail PyMuPDF extraction go to status PARSE_FAILED

**Shutdown:** SIGINT/SIGTERM triggers graceful shutdown (saves checkpoint, closes DB, flushes telemetry)

## Resumability

The SQLite status columns enable resuming interrupted runs:

- Status PENDING or FAILED documents are re-downloaded on next run
- Status DOWNLOADED, PARSED, or EXTRACTED documents are skipped
- No separate checkpoint file needed (SQLite is the checkpoint)

To resume:
```bash
python scripts/nsm_bulk_download.py --tiers 1
```

The script will pick up where it left off.

## Performance Expectations

**Typical numbers (from council testing):**
- 1-2 MB avg file size per prospectus
- 30-40 seconds per download (including two-hop resolution)
- 200-300 documents per hour per tier
- Full run (all 4 tiers): ~6-8 hours for ~400 documents

**To speed up testing:**
```bash
python scripts/nsm_bulk_download.py --tiers 1 --limit 5
```

## Dependencies

- `requests`: HTTP client
- `beautifulsoup4`: HTML parsing (for two-hop resolution)
- `fitz` (PyMuPDF): PDF text extraction
- `csv`, `json`, `sqlite3`: Standard library

Install with:
```bash
pip install requests beautifulsoup4 pymupdf
```

## Integration with CLAUDE.md

This script implements all architecture decisions from CLAUDE.md:

1. ✓ SQLite as single source of truth (no checkpoints needed)
2. ✓ Depth over breadth for demo (hand-verified later)
3. ✓ No Selenium (uses requests + BeautifulSoup for two-hop)
4. ✓ Atomic file writes (→ .part, then rename)
5. ✓ Quarantine directory for unparseable PDFs
6. ✓ Verbatim quote extraction (via Group A grep scanning)
7. ✓ Document families ready (SQLite schema has family_id)

## Troubleshooting

**No config file found**
```
FileNotFoundError: Config file not found: config.toml
```
Solution: Run from project root or use `--config /path/to/config.toml`

**"Too many files open" error**
Solution: Increase ulimit with `ulimit -n 4096`

**Rate limited (many 429 errors)**
Solution: Increase `delay_download` in config.toml or run during off-peak hours

**PDF validation failures**
Solution: Check for HTML instead of PDF at source URL. These go to `quarantine_reason` in database.

## Next Steps

1. **Manual hand-verification** of extracted clauses (non-negotiable per CLAUDE.md)
2. **PDIP comparison** (1+ documents matched against expert baseline)
3. **Clause extraction** via Claude Code (using grep matches as targeting)
4. **Change detection** (compare documents over time within same country)

---

**Author:** Teal Insights Research Pipeline  
**Last updated:** 2026-03-24  
**Architecture:** Council of Experts Round 1 decisions
