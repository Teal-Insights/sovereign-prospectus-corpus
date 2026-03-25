# COUNCIL-OF-EXPERTS PROMPT — ROUND 2
## Scaling Aggressively: Parallel Bulk Download from FCA + EDGAR Overnight

**Prepared:** March 24, 2026 (evening)
**For:** Council-of-experts consultation across Claude Opus 4.6, ChatGPT Pro, and Gemini Pro Deep Think
**Context Document:** See CONTEXT-PACK-ROUND-2.md (paste relevant sections as indicated)
**Deadline:** March 30, 2026
**Status:** Pipeline validated on 7 documents. Now scaling to hundreds, tonight, in parallel.

---

## WHAT'S DIFFERENT ABOUT ROUND 2

Round 1 was strategic: architecture, framing, prioritization. Those decisions are ratified.

Round 2 is **operational engineering at scale.** The pipeline works. We need to:

1. **Download as many sovereign prospectuses as possible tonight** — from BOTH FCA NSM and SEC EDGAR, running in parallel via git worktrees on a Mac Mini
2. **Prioritize smartly** — distressed/defaulted EM countries first, so if we get rate-limited we've already captured the highest-value documents
3. **Make the pipeline modular** so components can be swapped (SQLite→DuckDB, PyMuPDF→Docling)
4. **Collect rich telemetry** — timing, API behavior, failure modes — so every run teaches us something

**I have the domain expertise.** I know sovereign debt, I know the audience, I know the analytical questions. What I need is **engineering best practices** for downloading, storing, processing, and scaling. Help me do this well so I can go to bed and let the Mac Mini work all night.

**Key context on why scale matters:** For the ODI China lending paper (Greener on the Other Side), it cost $1.50 to LLM-classify 18,000 lending records. An RA at $15/hr doing 5 minutes each would have cost $22,500. Scale is the point. PDIP has a $382K Gates grant to hand-annotate 900 documents. We want to show that the same analysis is possible at a fraction of the cost, and volume is how we prove it.

---

## THE PLAN: PARALLEL DOWNLOADS VIA GIT WORKTREES

**Architecture:** Run two parallel Claude Code CLI sessions on the Mac Mini, each in its own git worktree:

```
worktree-1: FCA NSM downloader (455 prospectus-type docs across 30+ countries)
worktree-2: EDGAR downloader (sovereign 424B/18-K filings — Mexico, Brazil, Argentina, etc.)
```

Both write to the same SQLite database (via separate tables or coordinated writes), or to separate databases that we merge in the morning.

**Why worktrees:** Isolation. If one crashes, the other keeps running. Different rate limits, different API patterns, different failure modes. Git worktrees give us separate working directories on the same repo.

---

## WHAT WE HAVE: NSM DATA ANALYSIS (455 Prospectus-Type Documents)

### Priority Tiers (Based on Credit Risk / Policy Relevance)

**Tier 1 — Defaulted / Restructured / Distressed (HIGHEST PRIORITY, download first)**

| Country | Prospectus Docs | Total Filings | Status |
|---------|----------------|---------------|--------|
| Ghana | 20 | 28 | Defaulted Dec 2022, restructured 2024 |
| Zambia | 2 | 28 | Defaulted Nov 2020, restructured 2024 (G20 Common Framework) |
| Sri Lanka | 0 | 11 | Defaulted May 2022, restructuring ongoing |
| Ukraine | 4 | 21 | Debt moratorium, war-related restructuring |
| Belarus | 2 | 2 | Sanctions, technical default |
| Congo | 0 | 3 | Debt distress |
| Gabon | 1 | 3 | Debt concerns |

**Note:** Sri Lanka, Congo have 0 prospectus-type docs but may have other useful filings. Zambia only has 2 prospectus-type (we already have both). Ghana has 20 (we have 4 — 16 more to get).

**Tier 2 — Frontier/EM, Sub-Investment Grade (HIGH PRIORITY)**

| Country | Prospectus Docs | Total Filings | Notes |
|---------|----------------|---------------|-------|
| Nigeria | 40 | 43 | Africa's largest economy, B- rating |
| Egypt | 35 | 36 | Frequent issuer, IMF program |
| Angola | 14 | 17 | Oil-dependent, debt concerns |
| Kenya | 5 | 19 | Recent Eurobond buyback drama |
| Montenegro | 12 | 16 | Small EM, interesting contract evolution |
| Albania | 3 | 7 | Frontier market |
| Jordan | 2 | 4 | Geopolitical significance |
| Cameroon | 2 | 2 | Francophone Africa |
| Rwanda | 1 | 2 | Frontier, good governance narrative |
| Bosnia and Herzegovina | 1 | 1 | Post-conflict |
| Srpska | 1 | 1 | Sub-sovereign |
| Morocco | 2 | 2 | IG-adjacent |
| North Macedonia | 0 | 1 | — |

**Tier 3 — EM Investment Grade / Gulf States (MEDIUM PRIORITY)**

| Country | Prospectus Docs | Total Filings | Notes |
|---------|----------------|---------------|-------|
| Uzbekistan | 21 | 63 | Reform story, interesting quasi-sovereign mix |
| Serbia | 24 | 41 | EU accession candidate |
| UAE - Abu Dhabi | 35 | 37 | Wealthy but interesting contract terms |
| Kazakhstan | 22 | 29 | Oil economy, quasi-sovereign |
| Saudi Arabia | 23 | 27 | Recent IG issuer, large program |
| Oman | 16 | 25 | Debt concerns resolved |
| Qatar | 10 | 10 | Wealthy, blockade history |
| Bahrain | 5 | 9 | Gulf, small |
| Kuwait | 4 | 5 | Wealthy |

**Tier 4 — Developed Markets / EU (LOWER PRIORITY but useful as control group)**

| Country | Prospectus Docs | Total Filings | Notes |
|---------|----------------|---------------|-------|
| Israel | 126 | 148 | BY FAR largest issuer, interesting DM control |
| Sweden | 7 | 64 | EU, AAA |
| Finland | 2 | 36 | EU, AA |
| Hungary | 5 | 30 | EU but EM-adjacent, interesting |
| Iceland | 1 | 36 | Post-2008 crisis veteran |
| Cyprus | 5 | 24 | Bailout history (2013), now recovered |
| Canada | 2 | 2 | DM control |

**UK excluded entirely:** 560 filings, 0 prospectus-type. All "Issue of Debt" (gilts). Not useful.

### FCA NSM Download Target: 455 prospectus-type documents

Sequenced as: Tier 1 → Tier 2 → Tier 3 → Tier 4. If rate-limited, we stop with the highest-value docs already captured.

### EDGAR Download Target: Major EM Sovereign Issuers (New York Law)

Known EDGAR sovereign filers include: Mexico (CIK 101368), Brazil (CIK 205317), Argentina, Colombia, Indonesia, Philippines, Peru, Chile, Turkey, South Africa. SIC code 8888 = "Foreign Governments."

**Form types:** 424B2, 424B5 (prospectus supplements), 18-K (annual reports), F-1/F-3 (registration statements).

**Key value of EDGAR:** New York law bonds. FCA NSM gives us English law. EDGAR gives us the other major governing law jurisdiction. Comparing English law vs. New York law clause variation across the same issuer (e.g., Mexico issues under both) is analytically valuable.

---

## CORE QUESTIONS

### 1. Parallel Download Architecture: Git Worktrees + Separate Databases

**Context:** Two parallel Claude Code CLI sessions on Mac Mini, each in its own git worktree. One does FCA NSM, the other does EDGAR.

**What we need to know:**

- **Separate SQLite databases vs. shared database?** SQLite supports WAL mode concurrent readers but only one writer at a time. Options: (a) Separate databases (`corpus_nsm.db`, `corpus_edgar.db`), merge in the morning. (b) Shared database with WAL + retry on `SQLITE_BUSY`. (c) Shared database with write queue. Which is safest for unattended overnight?

- **Git worktree coordination:** Each worktree will have its own copy of the scripts. They'll write PDFs to `data/pdfs/{source}/{country}/`. Any risk of path collisions? Should we namespace by source (`data/pdfs/nsm/ghana/` vs `data/pdfs/edgar/ghana/`)?

- **Resource contention:** Mac Mini M-series has ~32GB RAM, NVMe SSD, gigabit ethernet. Is there any risk of resource contention between two parallel download processes? CPU? Disk I/O? Network? Connection limits?

- **Failure isolation:** If the NSM downloader crashes, should it affect the EDGAR downloader? How do we ensure full isolation between the two processes?

- **Merge strategy:** In the morning, how do we cleanly merge two separate databases (or two worktrees of data) into a single canonical corpus? What schema considerations make this merge easier?

### 2. FCA NSM: Aggressive but Polite Overnight Download

**Context:** 455 prospectus-type documents across 30+ countries, prioritized by credit risk tier.

**What we need to know:**

- **Throttling for 455 docs over ~8 hours:** What's the optimal request delay? At 1 req/sec we finish in ~15 minutes (API queries) + download time. At 0.5 req/sec, ~30 minutes. The FCA API has no published limits and we ran 156 queries without issues. For the PDF downloads (separate HTTP requests to data.fca.org.uk/artefacts/), what's appropriate? These are file downloads, not API queries — different server, different capacity.

- **Separate throttling for API queries vs. PDF downloads?** The Elasticsearch API and the artefacts file server are likely different backends. Should we treat them differently?

- **Connection pooling at scale:** For 455 documents, should we use a single `requests.Session` (persistent TCP connections) or rotate sessions periodically to avoid connection staleness?

- **Two-hop resolution optimization:** ~250 documents require HTML→PDF resolution. Should we batch all HTML resolution first (build a URL map), then download all PDFs? Or continue the current interleaved approach (resolve + download per document)?

- **What if we get rate limited at document 200?** The tiered priority ensures we have Tier 1 and Tier 2 already. But how should we detect rate limiting? HTTP 429 is obvious, but what about: slower responses? HTTP 503? Connection resets? What signals should we watch for and how should we respond?

- **Adaptive throttling:** Should we start fast (0.5 req/sec) and slow down if we detect stress signals (increasing latency, timeouts)? Or start conservative (2s delay) and never risk it?

- **Parallel within NSM:** Should we run 2-3 concurrent downloads from FCA (asyncio/threading) or keep it strictly sequential? What's the risk/reward?

### 3. EDGAR: Getting Started Right

**Context:** We've never downloaded from EDGAR before. The rules are stricter (10 req/sec enforced, mandatory User-Agent, 10-min IP blocks).

**What we need to know:**

- **Discovery first:** Before downloading anything, we need to identify which sovereign issuers are on EDGAR and find their CIK numbers. Best approach: (a) Download `company_tickers.json` or `submission.zip` and filter by SIC code 8888, (b) Search EFTS API for "Republic of" + country names, (c) Manual CIK lookup for known issuers (Mexico, Brazil, Argentina, etc.). Which is fastest and most complete?

- **Filing navigation:** Each EDGAR filing is a package (cover letter, prospectus, exhibits). The primary prospectus document is usually the largest PDF. Is there a reliable heuristic? Should we download all documents in a filing, or try to identify the primary one?

- **Rate limiting implementation:** 10 req/sec is generous but the penalty (10-min IP block) is severe. What's the safest implementation? Token bucket at 8 req/sec (leaving headroom)? Simple `time.sleep(0.15)` between requests? How do we account for parallel EDGAR + NSM downloads sharing the same IP (but different domains)?

- **User-Agent:** Must be `"Teal Insights lte@tealinsights.com"` or similar format. SEC requires company name + contact email. Is there anything else we should know about EDGAR's user-agent requirements?

- **Overnight target:** Realistically, how many EDGAR sovereign prospectuses can we expect to find and download overnight? Mexico alone might have dozens. Are we looking at 50? 200? 500?

- **EDGAR-specific metadata:** What metadata should we capture that's EDGAR-specific? CIK, accession number, form type, filing date — anything else? XBRL data?

### 4. Modular Architecture (Right-Sized for This Week)

**Context:** Current stack: SQLite, PyMuPDF, regex extraction. Future: maybe DuckDB, Docling, LLM extraction. Solo developer, 6-day sprint.

**What we need to know:**

- **Database abstraction level:** We might want DuckDB later for analytical queries. What's the lightest-weight abstraction that makes this swap easy? A simple Python class with `save_document()`, `get_document()`, `update_status()`, `query()` methods? Or just write clean SQL and swap the driver? SQLAlchemy seems like overkill for a solo project.

- **Parser interface:** PyMuPDF returns `page.get_text()`. Docling returns structured objects with tables. The minimum shared interface: `parse(pdf_path) -> list[PageText]` where `PageText` has `.text`, `.page_number`, optionally `.tables`. Is this right? What else should the interface expose?

- **Configuration file:** Currently everything is hardcoded. For overnight runs with different parameters (throttle rates, priority tiers, output dirs), a config file helps. TOML (Python 3.11+ native), YAML (needs PyYAML), or JSON? Where should it live?

- **"Not yet" decisions:** What should we explicitly defer? ORM? Cloud storage? Containerization? What's the list of things that are clearly post-roundtable?

### 5. Telemetry: Learning from Every Download

**Context:** Every download teaches us something about the APIs, the documents, and the pipeline. We want to capture this systematically.

**Per-document metrics to log:**

```
{
  "doc_id": "...",
  "source": "nsm|edgar",
  "country": "...",
  "tier": 1-4,
  "download_started": "ISO timestamp",
  "download_completed": "ISO timestamp",
  "download_duration_seconds": 12.3,
  "download_status": "success|failed|timeout|rate_limited",
  "http_status_code": 200,
  "content_type": "application/pdf",
  "content_length_header": 2100000,
  "actual_file_size_bytes": 2100000,
  "file_hash_md5": "...",
  "two_hop_required": true,
  "two_hop_duration_seconds": 2.1,
  "pdf_valid": true,
  "page_count": 232,
  "word_count": 142809,
  "text_extraction_seconds": 0.65,
  "grep_scan_seconds": 0.02,
  "grep_matches": {"CAC": [12,45,46], "PARI_PASSU": [88], ...},
  "estimated_tokens": 190000,
  "errors": [],
  "retry_count": 0,
  "response_headers": {"server": "...", "x-rate-limit-remaining": "..."}
}
```

**What we need to know:**

- **Is this the right set of fields?** What are we missing? What's unnecessary overhead?

- **Token estimation:** For future API cost modeling, we want to estimate how many tokens each document would cost to process. Rough formula: `word_count * 1.33` for English text? Is there a better estimator? Should we sample a few documents through a tokenizer?

- **API behavior logging:** We want to learn about rate limits empirically. Should we log: response time per request? Any rate-limit headers (X-RateLimit-Remaining, Retry-After)? Server header? Connection reuse stats?

- **Aggregate summary report:** After the overnight run, the script should print/save a summary. Proposed fields: total attempted, success count, failure count by type, total bytes, total time, average/median/p95 download time, countries completed, documents per tier. What else?

- **Structured log format:** One JSON object per event, appended to a JSONL file? Or a structured SQLite `telemetry` table? What's better for post-hoc analysis?

### 6. Graceful Failure Modes for Overnight Runs

**What can go wrong and how to recover:**

| Failure Mode | Detection | Recovery |
|-------------|-----------|----------|
| HTTP 429 (rate limited) | Status code | Exponential backoff, log timing |
| HTTP 503 (service unavailable) | Status code | Retry with backoff |
| Connection timeout | requests.Timeout | Retry, increase timeout |
| Connection reset | ConnectionError | Retry after 30s |
| Corrupted PDF | Missing %PDF header | Quarantine, log, continue |
| HTML instead of PDF | Content-type check | Two-hop resolve, or quarantine |
| Disk full | OSError | Stop cleanly, log final state |
| Process crash | Uncaught exception | Checkpoint enables restart |
| Network loss | Repeated ConnectionError | Sleep 5min, retry, stop after 5 failures |
| IP block (EDGAR) | 403 for 10+ minutes | Stop EDGAR, continue NSM |

**What we need to know:**

- **Is this failure table complete?** What are we missing?
- **Should we implement a watchdog process?** Something that checks if the download scripts are still running and restarts them if they hang?
- **Checkpoint granularity:** Save state after every document? Every N documents? Every N minutes? What's the right balance between safety and I/O overhead?
- **Signal handling:** Should we catch SIGTERM, SIGINT, SIGHUP for clean shutdown? What about SIGPIPE?
- **"Circuit breaker" pattern:** After N consecutive failures, should we skip to the next tier/country instead of retrying forever? What N?

### 7. The Processing Pipeline: Group A at Scale

**After download completes, run Group A processing on everything:**

Group A (automated, no LLM, all documents):
- Text extraction (PyMuPDF)
- Page count, word count
- Grep scan (10 clause types)
- Metadata regex (governing law, law firms, arrangers, ISINs, fiscal agent, listing exchange)
- File hash
- Store in SQLite

**What we need to know:**

- **Run Group A inline during download or as a separate batch?** Inline means each document is parsed immediately after download. Batch means parse all after downloads complete. Inline gives us partial results if download crashes. Batch is simpler.

- **Group A time estimate for 455+ docs:** PyMuPDF: 0.5s/doc. Grep: 0.1s. Metadata regex: 0.5s. So ~1.1s per doc × 455 = ~8 minutes total. Worth running inline during download (adds trivially to per-doc time)?

- **Metadata regex patterns to add:** Current patterns cover law firms, arrangers, ISINs, governing law, fiscal agent, listing exchange. What else should we grep for at the bulk level? Coupon rates? Currency? Maturity dates? Programme size? Rating agency mentions?

- **The rectangular dataset:** After Group A on all documents, we have a data frame. Proposed columns:
  ```
  doc_id | source | country | issuer | filing_date | doc_type | pages | words |
  governing_law | law_firm_issuer | law_firm_managers | fiscal_agent |
  listing_exchange | isins | arrangers | currency | tier |
  has_cac | cac_pages | has_pari_passu | has_eod | has_neg_pledge |
  has_sov_immunity | has_cross_default | has_ext_indebtedness |
  has_acceleration | has_trustee_fa | estimated_tokens
  ```
  What's missing? What would make this more analytically useful?

### 8. Honest Assessment — Round 2

- **Confidence level (1-10) for successfully downloading 400+ documents overnight from FCA NSM?** Main failure mode?

- **Confidence level (1-10) for having EDGAR downloading working by tomorrow evening?** Hardest part?

- **Realistic overnight target:** If we run FCA NSM + EDGAR in parallel for 8 hours on a Mac Mini, how many total documents should we expect by morning? Give a range.

- **Biggest technical risk** we haven't mentioned?

- **The "two-hop problem" at scale:** ~250 NSM documents need HTML→PDF resolution. Failure rate estimate?

- **Over-engineering vs. under-engineering:** Are we investing the right amount in architecture for a 6-day sprint? Where should we invest more? Where should we cut corners?

- **Parallel worktrees:** Is this the right approach for running FCA + EDGAR simultaneously? Or is there a simpler way (e.g., two terminal windows, separate scripts)?

---

## DESIRED OUTPUT FORMAT

### 1. Parallel Architecture
- **Database strategy:** [Separate / shared / recommendation]
- **Path namespacing:** [How to avoid collisions]
- **Resource contention risk:** [Low/Med/High + why]
- **Merge strategy:** [How to combine in the morning]

### 2. FCA NSM Configuration
- **Optimal delay between requests:** [X seconds for API queries, Y seconds for PDF downloads]
- **Connection strategy:** [Session reuse / rotation / recommendation]
- **Two-hop optimization:** [Batch / interleaved / recommendation]
- **Rate limit detection signals:** [What to watch for]
- **Adaptive throttling:** [Yes/No + implementation]
- **Parallelism within NSM:** [Yes N=? / No]
- **User-Agent:** [Exact string recommendation]

### 3. EDGAR Configuration
- **Discovery approach:** [Best method + implementation sketch]
- **Filing identification:** [Heuristic for finding the primary prospectus document]
- **Rate limiting implementation:** [Specific technique with headroom]
- **Overnight target estimate:** [Number range]

### 4. Modular Architecture
- **Database abstraction:** [Specific recommendation]
- **Parser interface:** [Specific recommendation]
- **Configuration:** [Format + location]
- **"Not yet" list:** [What to explicitly defer]

### 5. Telemetry
- **Per-document fields:** [Complete list with any additions/removals]
- **Token estimation:** [Method]
- **API behavior metrics:** [What to capture]
- **Aggregate report:** [Template]
- **Storage format:** [JSONL / SQLite / recommendation]

### 6. Failure Modes
- **Missing failure modes:** [Any additions to our table]
- **Watchdog:** [Yes/No + implementation]
- **Checkpoint strategy:** [Recommendation]
- **Circuit breaker N:** [Number]
- **Signal handling:** [What to catch]

### 7. Group A Processing
- **Inline vs. batch:** [Recommendation]
- **Additional metadata patterns:** [What to add]
- **Dataset columns:** [Additions/changes]

### 8. Honest Assessment
- **FCA overnight confidence (1-10):** [Number + reasoning]
- **EDGAR Day 2 confidence (1-10):** [Number + reasoning]
- **Realistic overnight total:** [Range]
- **Biggest risk:** [Specific]
- **Two-hop failure rate:** [Estimate]
- **Architecture verdict:** [Right-sized / over / under]
- **Worktree vs. simpler alternative:** [Recommendation]

---

## WHAT WE DON'T NEED ADVICE ON

- Which countries matter (we ranked them by credit risk — that's domain expertise)
- How to frame the roundtable (we know the audience personally)
- Strategic positioning / funding / product vision (we have that covered)
- Which clause types to extract (domain expertise)

## WHAT WE DO NEED

- How to download 455+ documents from FCA and hundreds more from EDGAR overnight without corruptions or blocks
- Whether parallel worktrees or separate scripts is the right architecture
- What logging to add so every failure teaches us something
- The right amount of modularity for a 6-day sprint
- EDGAR-specific technical gotchas
- Whether we're being too cautious or not cautious enough with rate limiting

**In short: We have the "what" and the "why." Help us with the "how." And aim high — we want to wake up to hundreds of documents, not dozens.**

---

**Prepared by Teal Insights**
**March 24, 2026 (evening)**

*"Scale is the point. Help us get there overnight."*
