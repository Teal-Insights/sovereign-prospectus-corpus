# Overnight Launch Instructions — Mac Mini

**Last updated:** 2026-03-24 evening
**Estimated runtime:** 2-4 hours for all 4 tiers (~434 prospectus docs)

## Pre-Flight: Copy to Local Disk

SQLite and Git **do not work** on Google Drive File Stream (journal I/O errors,
lock file failures). You must run from a local directory.

```bash
# 1. Copy project to local disk
cp -r ~/Library/CloudStorage/GoogleDrive-*/My\ Drive/01-PROJECTS/2026-03_Sovereign-Prospectus-Corpus ~/Desktop/sovereign-corpus
cd ~/Desktop/sovereign-corpus

# 2. Initialize git
git init -b main
git add .gitignore Claude.md config.toml pyproject.toml \
    scripts/nsm_bulk_download.py scripts/nsm_downloader.py \
    scripts/clause_extraction_templates.py \
    docs/ planning/ data/raw/ data/knowledge/ \
    LOG.md OVERNIGHT-LAUNCH.md
git commit -m "v0.1.0-poc: NSM bulk downloader, tested on 10 documents

Pipeline downloads sovereign bond prospectuses from FCA NSM, extracts
text via PyMuPDF, scans for 10 clause types, stores in SQLite.

Tested: 10/10 downloads successful across 5 countries (Tier 1).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git tag v0.1.0-poc
```

## Install Dependencies

```bash
# Using uv (preferred)
uv venv && source .venv/bin/activate
uv pip install requests beautifulsoup4 pymupdf ruff pyright

# Or plain pip
python3 -m venv .venv && source .venv/bin/activate
pip install requests beautifulsoup4 pymupdf ruff pyright
```

## Smoke Test (2 minutes)

```bash
# Quick test: Tier 1, limit 3 docs
python3 scripts/nsm_bulk_download.py --tiers 1 --limit 3

# Expected output: ~3-10 successful downloads from Ghana/Ukraine/Zambia/Belarus/Gabon
# Check: data/pdfs/nsm/ should have PDF files
# Check: data/text/nsm/ should have .txt files
```

## Launch Overnight Run

```bash
# Option A: tmux (recommended)
tmux new-session -d -s nsm-download 'python3 scripts/nsm_bulk_download.py --tiers 1,2,3,4 2>&1 | tee logs/overnight_$(date +%Y-%m-%d).log'
tmux attach -t nsm-download  # to monitor
# Ctrl-B, D to detach (keeps running)

# Option B: nohup
nohup python3 scripts/nsm_bulk_download.py --tiers 1,2,3,4 > logs/overnight_$(date +%Y-%m-%d).log 2>&1 &
echo $! > logs/nsm_pid.txt
```

## Monitor Progress

```bash
# Check if still running
ps aux | grep nsm_bulk_download

# Tail the log
tail -f logs/nsm_bulk_download_*.log

# Quick DB summary
python3 -c "
import sqlite3
conn = sqlite3.connect('data/db/nsm_corpus.db')
for row in conn.execute('SELECT status, COUNT(*) FROM documents GROUP BY status'):
    print(f'{row[0]:12s} {row[1]}')
print()
for row in conn.execute('SELECT country, COUNT(*) FROM documents WHERE status=\"PARSED\" GROUP BY country ORDER BY COUNT(*) DESC'):
    print(f'{row[0]:20s} {row[1]} docs')
"
```

## Graceful Shutdown

The script handles SIGINT (Ctrl-C) and SIGTERM gracefully — it finishes the
current document, saves state, and prints a summary. Safe to interrupt at any
time; the download will resume from where it left off on the next run.

```bash
# Gentle stop (finishes current doc)
kill -SIGTERM $(cat logs/nsm_pid.txt)

# Or just Ctrl-C if in tmux
```

## After the Run

```bash
# 1. Check results
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/db/nsm_corpus.db')
print('=== Status Summary ===')
for r in conn.execute('SELECT status, COUNT(*) FROM documents GROUP BY status'):
    print(f'  {r[0]:12s} {r[1]}')
print()
print('=== By Country ===')
for r in conn.execute('SELECT country, COUNT(*) FROM documents WHERE status=\"PARSED\" GROUP BY country ORDER BY COUNT(*) DESC'):
    print(f'  {r[0]:20s} {r[1]} docs')
print()
print('=== Clause Coverage ===')
for r in conn.execute('SELECT clause_type, COUNT(DISTINCT document_id), SUM(match_count) FROM grep_matches GROUP BY clause_type ORDER BY COUNT(DISTINCT document_id) DESC'):
    print(f'  {r[0]:25s} {r[1]} docs, {r[2]} total matches')
"

# 2. Git commit results
git add data/knowledge/ logs/
git commit -m "Overnight NSM run: $(date +%Y-%m-%d)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# 3. Copy DB + results back to Google Drive (optional)
cp data/db/nsm_corpus.db ~/Library/CloudStorage/GoogleDrive-*/My\ Drive/01-PROJECTS/2026-03_Sovereign-Prospectus-Corpus/data/db/

# 4. Update knowledge base with empirical learnings
# (will be done in tomorrow's session)
```

## Expected Outcomes

| Tier | Countries | Expected Docs | Notes |
|------|-----------|---------------|-------|
| 1 | Ghana, Ukraine, Zambia, Belarus, Gabon, Sri Lanka, Congo | ~30 | Highest value (defaulted/distressed) |
| 2 | Nigeria, Egypt, Angola, etc. | ~100 | Frontier/EM, high filing counts |
| 3 | Abu Dhabi, Serbia, Saudi Arabia, etc. | ~80 | EM investment grade |
| 4 | Israel, Hungary, Cyprus, etc. | ~150 | DM control group |

**Total estimated:** ~360-434 prospectus-type documents (some may be HTML or
password-protected → quarantined).

## Troubleshooting

- **"disk I/O error"**: You're running on Google Drive. Copy to local disk first.
- **429 Too Many Requests**: Circuit breaker will handle this — sleeps 11 min then retries.
- **All docs "skipped"**: DB has records from a previous run. Either delete the DB or
  use `--db data/db/nsm_corpus_fresh.db` for a clean run.
- **PDF validation failures**: Expected for ~5-15% of docs. Check `data/pdfs/nsm/quarantine/`.
