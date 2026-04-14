# Docling Parse Post-Mortem: April 12-13, 2026

**Duration:** 41.7 hours (PDF) + 1.5 hours (EDGAR HTML) + 0.9 hours (DB rebuild + publish)
**Machine:** Mac Mini M4 Pro, 14 cores, 64 GB RAM
**Result:** 9,599 documents successfully parsed, 518,227 pages, published to MotherDuck

---

## Final Numbers

| Metric | Value |
|--------|-------|
| **Total docs processed** | 9,643 |
| **Success** | 9,599 (99.5%) |
| **Failed (timeout)** | 44 (0.5%) |
| **Total pages** | 518,227 |
| **DB documents** | 9,729 |
| **DB pages** | 542,451 |
| **Published to MotherDuck** | Yes, auto-published by chain |

### By source

| Source | Docs | Pages | Parse tool |
|--------|------|-------|-----------|
| LuxSE | 4,955 | ~280K | docling (PDF) |
| EDGAR | 3,222 | 96,616 | docling-html / text-passthrough |
| PDIP | 823 | ~65K | docling (PDF) |
| NSM | 650 | ~76K | docling (PDF) |

### By phase

| Phase | Duration | Docs | Rate |
|-------|----------|------|------|
| PDF parse | 41.7 hours | 6,421 | 153 docs/hr |
| EDGAR HTML parse | 1.5 hours | 3,222 | 2,148 docs/hr |
| DB rebuild + MotherDuck publish | 54 min | — | — |
| **Total wall clock** | **~44 hours** | **9,643** | — |

---

## What Went Well

### 1. Memory monitoring prevented another kernel panic

Peak memory hit **33.5 GB** (52% of RAM). Without the monitoring and worker
recycling from the April 12 fix, this would have crashed the machine again.
The three-tier system worked exactly as designed:
- Info threshold (24 GB): logged warnings, continued
- Throttle threshold (36 GB): never triggered (stayed under)
- Ceiling threshold (48 GB): never triggered
- Worker recycling via `max_tasks_per_child=10`: kept memory bounded

### 2. Zero pool restarts, zero throttle events

The `ProcessPoolExecutor` never crashed. No `BrokenProcessPool` exceptions.
No adaptive worker reduction needed. The worker recycling alone was sufficient
to contain the leak.

### 3. EDGAR HTML parsing was blazing fast

3,222 EDGAR filings in 1.5 hours — 14x faster than PDF parsing. Docling's
`SimplePipeline` (BeautifulSoup, no ML models) made this essentially free.
No memory concerns, no worker recycling needed.

### 4. Auto-chain worked (eventually)

The chain wrapper successfully sequenced PDF → EDGAR → validation → DB rebuild
→ MotherDuck publish without human intervention. The auto-publish with
`.env` token sourcing worked perfectly.

### 5. Resume logic saved us repeatedly

The atomic write pattern (`.part` → `os.replace`) and resume filter (skip
existing `.jsonl` + `.md` pairs) meant we could restart without re-processing.
Used during: initial kernel panic recovery, chain timeout recovery, and the
switch from 600s to 900s timeout.

### 6. Council of Experts caught real bugs

Across 6 review rounds (2 specs, 2 plans, 2 implementations), the council
found and fixed:
- Timer thread leak that would have killed the overnight run
- SGML wrapper that would have produced garbage EDGAR output
- Case-sensitive extension routing (.HTM would have been skipped)
- `pipefail` issue that would have masked EDGAR failures
- Page-break-after mishandling
- Multiple threading race conditions

---

## What Went Wrong

### 1. PDF parse took 41.7 hours instead of expected 6-8 hours

The initial estimate was based on the March 28 run (1,468 docs in 3.9 hours).
The April 12 run had 6,428 docs including many much larger LuxSE prospectuses.

**Root cause:** Smallest-first sorting meant the largest documents (100-4000
pages) were all at the end. The rate dropped from 79 docs/min (small docs) to
0.4 docs/min (monsters) — a 200x slowdown.

**Two extreme outliers:** `luxse__1140557` and `luxse__1074238` (81 pages each,
0.9 MB) each took **11.3 hours**. These are clearly pathological documents —
81 pages should take ~60 seconds, not 11 hours. Something in Docling's
pipeline hangs on these files. They eventually completed but consumed a huge
fraction of the total runtime.

### 2. Chain v1 timed out after 14 hours

The chain wrapper had a 14-hour max wait. The PDF parse took 41.7 hours.
Required manual restart (chain v2, then v3).

**Lesson:** Don't set a timeout on the chain — let it wait indefinitely. Or
better: poll for summary file existence rather than time-based limits.

### 3. 44 documents timed out

All failures were timeouts (600s or 900s). No actual crashes or errors.

| Timeout | Count | Examples |
|---------|-------|---------|
| 600s | 8 | Early run with lower timeout |
| 900s | 36 | Later run with increased timeout |

Notable: Two PDIP docs (PER26: 22 pages, KEN28: 23 pages) timed out at 900s
despite being tiny. Something in those PDFs triggers a Docling hang.

### 4. Memory peaked at 33.5 GB

Higher than expected (design target was 24 GB peak with recycling at 10 docs).
The large documents (100-4000 pages) leaked more memory per document than the
small ones. Worker recycling contained it, but on a 36 GB machine this would
have triggered throttling.

### 5. Throughput was highly non-linear

| Time Window | Docs | Avg Pages/Doc | Docs/Hour |
|-------------|------|--------------|-----------|
| Hours 0-6 | 917 | 75 | 153 |
| Hours 6-12 | 2,785 | 16 | 464 |
| Hours 12-18 | 1,151 | 74 | 192 |
| Hours 18-24 | 534 | 113 | 89 |
| Hours 24-30 | 494 | 142 | 82 |
| Hours 30-36 | 340 | 192 | 57 |
| Hours 36-42 | 156 | 180 | 26 |

The smallest-first sort created a dramatic throughput cliff. Hours 6-12 were
fast (small docs), but the last 6 hours processed only 156 documents.

---

## Lessons Learned

### 1. Estimate based on pages, not documents

The correct unit for time estimation is **pages**, not documents. Our actual
throughput was ~10,000 pages/hour consistently. A 500-page document takes
~50x longer than a 10-page one. Future estimates should use:

```
estimated_hours = total_pages / 10000
```

For this corpus: 420,000 pages / 10,000 = 42 hours. Almost exactly right.

### 2. Smallest-first sorting trades predictability for safety

Sorting smallest-first is correct for memory safety (large docs hit fresh
workers). But it makes the job feel like it's almost done at 80% when there
are still 12+ hours left. Consider adding an estimated-hours-remaining based
on pages, not document count.

### 3. Per-document timeout needs to scale with page count

A flat 900s timeout fails on both ends:
- 22-page docs that hang should timeout faster (300s)
- 4000-page docs legitimately need 4+ hours

Future: `timeout = max(300, pages * 5)` — 5 seconds per page with a 300s floor.

### 4. Identify and quarantine pathological documents early

The two 11-hour documents and 44 timeouts should have been detected and
skipped earlier. Future: if a document exceeds 2x the expected time for its
page count, kill and quarantine it rather than blocking the worker.

### 5. Chain timeout should be "no timeout" for overnight runs

The 14-hour timeout was too aggressive. For unattended overnight runs, the
chain should wait indefinitely (or at least 48 hours). The parse finishing
is the signal, not a clock.

### 6. EDGAR HTML is a different problem than PDF

| Dimension | PDF Parse | EDGAR HTML |
|-----------|----------|------------|
| Engine | StandardPdfPipeline (ML models) | SimplePipeline (BeautifulSoup) |
| Memory | Leaks ~0.5-1 GB/doc | ~1.3 MB/doc, no leak |
| Speed | ~10K pages/hr | ~64K pages/hr |
| Worker recycling | Required | Not needed |
| Memory monitoring | Required | Not needed |
| Risk | High (kernel panic) | Low |

Keep these as separate scripts. Don't try to unify them.

### 7. The `parse_status.sh` ETA was misleading

Because throughput varied 200x between small and large documents, the ETA
swung wildly (from 2:30 PM to 1:00 AM to 10:30 AM to 5:00 PM). A
page-weighted ETA would have been much more stable.

### 8. Auto-publish in the chain was the right call

Adding the DB rebuild + MotherDuck publish as the final chain step meant the
explorer was updated automatically. No manual intervention needed. This should
be the default pattern for all future runs.

---

## Recommendations for Future Runs

### Immediate improvements

1. **Page-weighted timeout:** `timeout = max(300, page_count * 5)`
2. **Page-weighted ETA** in `parse_status.sh`
3. **No chain timeout** for overnight runs
4. **Quarantine threshold:** kill docs exceeding 2x expected time
5. **Auto-publish** as default chain step (already implemented)

### For the reusable package

1. **Auto-detect corpus characteristics** before starting: count docs, sample
   page counts, estimate total pages, predict runtime
2. **Hardware scaling formula** validated: `workers = min((cores-2)//3, 6)`,
   `ceiling = RAM * 0.75`, `time_hours = total_pages / 10000`
3. **Separate PDF and HTML pipelines** — different scripts, different configs
4. **Pre-run pathological doc detection** — scan for known-bad patterns
   (encrypted PDFs, scanned-only with no OCR, extremely long tables)

### For cloud processing

(See separate cloud options research — appended when available)

---

## Timeline of the Full Session

| Time | Event |
|------|-------|
| Apr 12, 06:44 AM | Woke up to kernel panic — machine rebooted |
| Apr 12, 07:00 AM | Root cause analysis — Jetsam logs, 127 GB memory |
| Apr 12, 08:07 AM | Memory fix implemented, parse restarted |
| Apr 12, 08:30 AM | 37% done, memory stable at 6 GB |
| Apr 12, 01:50 PM | Chain v1 started |
| Apr 12, 05:30 PM | EDGAR script + chain reviewed by council |
| Apr 12, 05:50 PM | Chain v1 started waiting for PDF parse |
| Apr 13, 07:50 AM | Chain v1 timed out (14hr limit) |
| Apr 13, 10:11 AM | Chain v2 started (no timeout) |
| Apr 13, 12:44 PM | Chain v3 started (with auto-publish) |
| Apr 13, 03:34 PM | PDF parse complete (6,377 success, 44 timeout) |
| Apr 13, 03:34 PM | EDGAR parse auto-started |
| Apr 13, 05:03 PM | EDGAR parse complete (3,222 success, 0 failed) |
| Apr 13, 05:03 PM | DB rebuild started |
| Apr 13, 05:57 PM | MotherDuck published — 9,729 docs, 542,451 pages |

**Total: ~35 hours from restart to published explorer.**
