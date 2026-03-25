# Council Round 2: Synthesis
## Scaling the Pipeline Overnight — Operational Engineering

**Date:** March 24, 2026 (evening)
**Models:** Claude Opus 4.6, ChatGPT 5.4 Pro, Gemini 3.1 Pro Deep Think
**Synthesized by:** Claude (Cowork session)
**Status:** Ready for Teal's review and launch decision

---

## 1. Points of Strong Agreement (All Three Models)

### 1a. Separate databases, merge in the morning

**Unanimous.** All three say: do NOT share a SQLite database between the NSM and EDGAR workers. Even with WAL mode, concurrent writers risk `SQLITE_BUSY` at 3 AM when nobody's watching.

- `corpus_nsm.db` and `corpus_edgar.db`
- Merge via `ATTACH DATABASE` in the morning
- Make document IDs deterministic and source-prefixed (`nsm:ghana:171818118`, `edgar:101368:0001013680-24-001234`)

### 1b. Sequential downloads within each source

**Unanimous.** No async, no threading, no concurrent downloads within a single source. The risk-reward is terrible: best case saves an hour, worst case gets IP-blocked. Sequential with polite delays will finish overnight easily.

### 1c. Use tmux (or simple terminal tabs), not git worktrees

**Opus and Gemini agree:** tmux panes or terminal tabs are simpler than git worktrees for this. Two scripts, two databases, two log files, same repo. ChatGPT slightly favors worktrees for the "build-and-launch" phase since Claude Code sessions might edit code independently, but agrees the simpler path is fine.

**Resolution:** Use tmux if launching from CLI. If launching from two separate Claude Code sessions, worktrees are fine for isolation. Either way, the key is separate databases and separate output directories.

### 1d. Honest, transparent User-Agent

**Unanimous.** Drop the fake browser UA. Use something like:

```
Teal Insights Research Pipeline/1.0 (lte@tealinsights.com; sovereign debt policy research)
```

For EDGAR specifically (SEC requirement): `Teal Insights lte@tealinsights.com`

### 1e. JSONL for telemetry, SQLite for canonical state

**Unanimous.** Telemetry events (per-request, per-download) go in append-only JSONL files. Document metadata and status go in SQLite. JSONL survives crashes, doesn't require locks, and is trivially analyzable with pandas in the morning.

### 1f. Circuit breaker pattern

**All agree on the principle:** consecutive failures should trigger a pause or skip, not infinite retries.

- **Opus:** 5 consecutive → skip country, 10 across countries → stop
- **Gemini:** 5 consecutive → slow down + cool down, 3 rate-limit signals → sleep 11 min, 10 per country → skip
- **ChatGPT:** 5 host failures → slow + cool, 3 rate-limit → sleep 11-15 min, 10 per bucket → skip

**Resolution:** Adopt Gemini/ChatGPT's more granular version:
- 5 consecutive failures for one country → skip to next country
- 3 explicit rate-limit (429/403) signals → sleep 11 minutes
- 10 consecutive failures across all countries → stop run, save state

### 1g. Checkpoint after every document

**Unanimous.** The I/O cost is negligible (<1ms per commit). Don't batch checkpoints.

### 1h. Group A time estimate: ~8 minutes for 455 docs

**All agree** that Group A (PyMuPDF + regex) is trivially fast and can easily run either inline or batch.

---

## 2. Points of Meaningful Disagreement

### 2a. Group A: Inline during download vs. batch after

| Model | Recommendation | Reasoning |
|-------|---------------|-----------|
| Opus | Inline | Partial results if crash. Only adds ~1s per doc. |
| Gemini | **Batch** | PyMuPDF C-binding segfault can kill the download process |
| ChatGPT | Inline | Wake up with a usable rectangular dataset even if run dies halfway |

**The tension:** Gemini raises a real risk — PyMuPDF is a C extension wrapping MuPDF. A severely corrupted PDF could trigger a segfault that kills the entire Python process, taking the downloader with it. Opus and ChatGPT dismiss this as unlikely.

**Resolution:** **Inline, but with subprocess isolation for PyMuPDF.** Wrap the Group A processing in a try/except that catches everything, and consider running PyMuPDF in a subprocess with a timeout for safety. If a doc fails to parse, mark it QUARANTINED and continue downloading. This gets the best of both: partial results + crash protection.

Alternative (simpler): Inline with a bare `try: ... except Exception: ...` around the parse step. If PyMuPDF segfaults (rare), the download process dies, but the checkpoint restarts from the last successful doc. Acceptable risk for a one-night run.

### 2b. FCA NSM throttle rate

| Model | API Delay | PDF Download Delay |
|-------|-----------|-------------------|
| Opus | 0.5s API, 1.0s PDF | Conservative but fast enough |
| Gemini | 1.0s API, 1.5s PDF | Most conservative |
| ChatGPT | 1.0s API, 0.75s PDF (max 2 concurrent) | Moderate |

**Resolution:** Start at **1.0s API, 1.0s PDF** (splitting the difference). This is polite enough for a government API with no published limits, and finishes 455 docs in ~2-3 hours. Adaptive throttling: if latency spikes >4s or any 429 detected, permanently add 1.0s to base delay.

### 2c. EDGAR discovery approach

| Model | Primary Approach | Secondary |
|-------|-----------------|-----------|
| Opus | Manual CIK list (~20 countries) | Validate with company_tickers.json |
| Gemini | Hardcoded CIK list | submissions.json per filer |
| ChatGPT | Manual seed + download submissions.zip | Use EFTS as gap-filler |

**Resolution:** **Manual seed list tonight, submissions.zip tomorrow.** Create a Python dict of ~20 known sovereign CIKs (Mexico, Brazil, Argentina, Colombia, Indonesia, Philippines, Peru, Chile, Turkey, South Africa, etc.). Query their submissions JSON directly. submissions.zip is 2GB+ and overkill for tonight. Use it tomorrow for completeness.

### 2d. EDGAR format: PDF vs HTML problem

**ChatGPT raises a critical insight the others underemphasize:** EDGAR sovereign prospectuses are frequently HTML, not PDF. The 424B2/424B5 primary documents for Mexico, Colombia, etc. are often HTM files. PyMuPDF can't parse HTML.

| Model | Assessment |
|-------|-----------|
| Opus | Mentions HTM as a consideration but doesn't flag it as critical |
| Gemini | Lists it as "Biggest Risk" |
| ChatGPT | Dedicates significant space to it, calls it "the format mismatch" |

**Resolution:** This is the #1 EDGAR risk. For tonight, download everything (HTML and PDF both). Store the raw files. For Group A processing, add a BeautifulSoup HTML→text fallback alongside PyMuPDF. HTML documents won't have page numbers — set `page_number = NULL` and note the format. This doesn't block the download; it blocks the extraction. We can solve extraction tomorrow.

### 2e. Parser interface design

| Model | Recommendation |
|-------|---------------|
| Opus | `parse(pdf_path) -> list[PageText]` with PageText(page_number, text, tables) |
| ChatGPT | `parse(path, mime_type, source) -> ParsedDocument` with pages, raw_text, tables, warnings, source_format |
| Gemini | `BaseParser(ABC)` with `parse(filepath) -> list[PageText]` |

**Resolution:** ChatGPT's version is right because of EDGAR. The parser needs to handle both PDF and HTML. Minimum interface:

```python
@dataclass
class ParsedDocument:
    pages: list[PageText]  # may be empty for HTML
    raw_text: str           # always present
    page_count: int | None  # None for HTML
    word_count: int
    source_format: str      # 'pdf', 'html', 'txt'
    warnings: list[str]
```

### 2f. Watchdog process

| Model | Recommendation |
|-------|---------------|
| Opus | No. Overkill for one night. |
| Gemini | No. Use bash restart loop instead. |
| ChatGPT | Yes, but tiny. Heartbeat file + parent shell script. |

**Resolution:** **No formal watchdog.** Use Gemini's bash loop: `while true; do python pipeline.py --source nsm && break; sleep 10; done`. Simple, effective, doesn't add code complexity.

---

## 3. Unique Insights by Model

### Opus (Unique Contributions)
- **Adaptive throttling code pattern:** Concrete Python implementation with latency-aware backoff. Start at base_delay, multiply on stress signals, decay back to base when healthy.
- **Session rotation every 100 requests:** Government load balancers can silently drop persistent connections after long idle periods. Recreate session periodically.
- **Two-hop HTML parsing brittleness:** At 250 two-hop docs, expect 3-5 different HTML templates. Add assertion: if resolution returns no PDF link, quarantine and log the HTML for manual review.

### Gemini (Unique Contributions)
- **PyMuPDF C-level segfault risk:** A severely corrupted PDF can segfault the Python process, bypassing try/except. This is real — MuPDF is a C library. Mitigation: subprocess isolation or at minimum, robust checkpointing.
- **Zero-byte file detection:** Connection drops can create empty files. Check `os.path.getsize() > 1024` after download.
- **"Crash-Only, Append-Only, Decoupled"** as guiding philosophy. Strong framing.

### ChatGPT (Unique Contributions)
- **EDGAR is HTML-first, not PDF-first.** This is the critical insight for EDGAR integration. Recent sovereign 424B5 filings (Colombia, Indonesia) have HTML as the primary document. PyMuPDF won't work. Need BeautifulSoup fallback.
- **External corpus root:** Write data outside the git repo to separate code from data. `CORPUS_ROOT` as an environment variable or config parameter.
- **`artifacts` table:** EDGAR filings are packages with multiple documents. The current schema (one row per filing, one `local_path`) doesn't fit. Need a `documents` → `artifacts` relationship where each filing can have multiple files.
- **Per-request telemetry table:** Log every HTTP request (not just per-document), capturing latency, status, bytes, retries. This is more granular than per-document telemetry and better for debugging API behavior.
- **Additional EDGAR form types:** Add `18-K/A` (amendments), `FWP` (free writing prospectus), and old `Schedule B` to secondary queue.

---

## 4. Consolidated Action Plan for Tonight

### Before Launch (do now, ~45 minutes)

1. **Update User-Agent** to honest research identifier
2. **Create config.toml** with NSM delays (1.0s), paths, tier ordering
3. **Write thin `CorpusDB` class** — `save_document()`, `get_document()`, `update_status()`, `save_telemetry()`, `get_pending()`
4. **Add signal handlers** for SIGINT/SIGTERM → clean checkpoint + exit
5. **Add circuit breaker** — 5 consecutive failures → skip country, 3 rate-limits → sleep 11 min
6. **Add Content-Length vs actual size check** for truncation detection
7. **Add zero-byte file check** (`os.path.getsize() > 1024`)
8. **Enable JSONL telemetry** — one line per download event
9. **Update priority country list** — Tier 1 → 2 → 3 → 4 ordering
10. **Add `b"%PDF"` check + HTML content-type check** — quarantine non-PDFs

### Launch NSM Download (~5 min)

11. **Start in tmux:** `tmux new-session -d -s nsm 'python nsm_bulk_download.py'`
12. **Verify first 5 downloads** complete successfully before walking away
13. **Go to sleep**

### Tomorrow Morning

14. **Check telemetry** — count docs, diagnose failures, review timing
15. **Run Group A** on all downloaded docs (if not run inline): ~8 min
16. **Merge databases** if EDGAR also ran
17. **Export rectangular dataset** for R analysis
18. **Start EDGAR downloader** (may need morning to debug)

### Tomorrow: EDGAR Build (~2-3 hours)

19. **Create manual CIK seed list** (~20 sovereign issuers)
20. **Write `edgar_downloader.py`** — CIK → submissions JSON → filter 424B/18-K → download
21. **Add HTML→text parser** (BeautifulSoup fallback for EDGAR's HTML-first format)
22. **Add `artifacts` table** for EDGAR's multi-document filing packages
23. **Test on Mexico** (largest, most predictable filer)
24. **Launch EDGAR overnight** tomorrow night

---

## 5. Schema Decisions

### Tonight's Downloads: Minimum Schema Additions

```sql
-- Add to documents table
ALTER TABLE documents ADD COLUMN tier INTEGER;           -- 1-4 priority tier
ALTER TABLE documents ADD COLUMN raw_format TEXT;         -- 'pdf', 'html', 'txt'
ALTER TABLE documents ADD COLUMN download_duration_sec REAL;
ALTER TABLE documents ADD COLUMN two_hop_required BOOLEAN;

-- New telemetry table (or use JSONL)
CREATE TABLE IF NOT EXISTS download_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT,
    source TEXT,
    country TEXT,
    tier INTEGER,
    started_at TEXT,
    completed_at TEXT,
    duration_seconds REAL,
    http_status INTEGER,
    content_type TEXT,
    content_length_expected INTEGER,
    file_size_actual INTEGER,
    two_hop_required BOOLEAN,
    two_hop_duration_seconds REAL,
    retry_count INTEGER,
    error_type TEXT,
    error_message TEXT,
    response_time_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Tomorrow: EDGAR Schema Extension

```sql
-- For EDGAR's multi-document filing packages
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,           -- 'edgar:{cik}:{accession}:{filename}'
    document_id TEXT REFERENCES documents(id),
    artifact_type TEXT,            -- 'primary', 'exhibit', 'cover', 'graphic'
    filename TEXT,
    local_path TEXT,
    file_size_bytes INTEGER,
    mime_type TEXT,
    created_at TIMESTAMP
);
```

---

## 6. Key Numbers

| Metric | Estimate | Source |
|--------|----------|--------|
| NSM prospectus docs to download | 455 | Actual count from data |
| NSM download time (sequential, 1s delay) | 2-3 hours | Empirical + math |
| NSM expected success rate | 90-95% | Council consensus |
| NSM two-hop failure rate | 5-10% | Council consensus |
| EDGAR sovereign issuers | ~20-30 | Research + council |
| EDGAR docs per major issuer | 20-50 | Council estimate |
| EDGAR overnight target | 75-250 | Council range |
| Total by Wednesday morning | 450-700 | NSM + EDGAR |
| Group A processing time (all docs) | ~8 min | Empirical timing |
| Disk space needed | 500MB-1GB | File size estimates |

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| FCA rate limiting | Low (20%) | Medium | Adaptive throttle, tier priority ordering |
| Two-hop HTML parsing failures | Medium (30%) | Low | Quarantine + manual review, 5-10% expected |
| EDGAR HTML-not-PDF format | High (70%) | Medium | BeautifulSoup fallback, page_number=NULL |
| PyMuPDF segfault on corrupt PDF | Low (5%) | High | try/except + checkpoint restart |
| Network loss overnight | Low (10%) | Low | Checkpoint resume, bash restart loop |
| Disk full | Very Low (2%) | High | Size check before download, ~1GB needed |
| SQLite corruption | Very Low (1%) | Critical | WAL mode, separate DBs, local disk |

---

## 8. Teal's Decisions Required

### Must Decide Now (Before Launch)

1. **Inline Group A or batch?** Council split 2-1 for inline. Synthesis recommends inline with try/except. Confirm?

2. **NSM throttle rate:** 1.0s API + 1.0s PDF downloads. OK, or more conservative?

3. **EDGAR tonight or tomorrow?** Council consensus: NSM tonight, EDGAR tomorrow (need to write the downloader). But if Teal wants to spend 2 hours building EDGAR tonight, it could run overnight too.

4. **Data location:** Inside repo (`data/pdfs/`) or external corpus root? ChatGPT recommends external. Current setup is in-repo. Changing now adds complexity; keeping in-repo is fine for this week.

### Can Decide Tomorrow

5. **Parser interface detail** (ChatGPT's `ParsedDocument` vs simpler `list[PageText]`)
6. **Artifacts table** (needed for EDGAR, not for NSM tonight)
7. **DuckDB migration timing** (post-roundtable)
8. **Docling integration timing** (post-roundtable)

---

*Synthesized March 24, 2026 (evening)*
*Ready for Teal's launch decision*
