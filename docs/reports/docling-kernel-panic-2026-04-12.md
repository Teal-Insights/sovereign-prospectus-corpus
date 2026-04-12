# Docling Kernel Panic — Incident Report & Lessons Learned

**Date:** 2026-04-12
**Machine:** Mac Mini M4 Pro, 64 GB unified memory (Mac16,11)
**macOS:** 26.3.1 (25D2128)
**Resolution:** Same-day fix, re-parse running successfully by 08:07 EDT

---

## Part 1: The Incident

### What happened

An overnight Docling PDF parsing job caused a macOS kernel panic. The Mac Mini
rebooted itself at ~04:33 EDT. The user woke up to "Your computer was
restarted because of a problem."

### Timeline

| Time (EDT) | Event |
|------------|-------|
| ~21:53 | Docling reparse started — 6,428 total docs, 4 workers |
| ~04:29 | **Jetsam Event #1** — 62.6 GB / 64 GB used, 24 MB free |
| ~04:33 | **Jetsam Event #2** — 5,478 processes killed, memory still critical |
| ~04:33-06:44 | **Kernel panic** — watchdog timer forced hardware reset |
| 06:44 | System rebooted (ResetCounter: `wdog,reset_in_1`) |
| 08:07 | Fix implemented, re-parse started with memory monitoring |
| 08:37 | 37% complete, memory stable at 6 GB, 0 throttle events |

### Blast radius

- **1,032 documents completed before crash** — all safe (atomic writes)
- **0 data corruption** — APFS copy-on-write + `.part` → rename pattern
- **~2 hours lost** — diagnosis, fix, review, restart
- **No hardware damage** — kernel panic is a software-triggered reboot

---

## Part 2: Root Cause

### 10 Python processes consumed 127 GB on a 64 GB machine

The Jetsam crash logs told the whole story:

| Process | Resident Memory |
|---------|---------------:|
| 4 Gen-1 workers (PID 276xx) | 19-23 GB each |
| 4 Gen-2 workers (PID 963xx) | 6-15 GB each |
| Supervisor (PID 27637) | 1.9 GB |
| **Total Python** | **127 GB** |

macOS compressed 29 GB of memory trying to cope. When even compressed memory
filled up, the kernel watchdog expired and forced a hardware reset.

### Why Docling workers leak memory

Each worker calls `DocumentConverter().convert()` per document. Docling loads
ML models (layout analysis, table structure, OCR) on first use. These persist
in the process forever. Over hundreds of documents, each worker accumulates:

1. **ML model caches** that grow with document variants
2. **PyTorch/MPS GPU memory** not fully released between documents
3. **Python heap fragmentation** — large intermediates fragment the allocator;
   RSS never shrinks because Python doesn't return pages to the OS
4. **Per-page text/markdown** from 200-500 page prospectuses

### Why existing safeguards didn't catch it

| Safeguard | Why it failed |
|-----------|--------------|
| Disk space check | Memory was the problem, not disk |
| Pool restart on BrokenProcessPool | Pool never crashed — workers leaked silently |
| MPS fallback to CPU | Leaks happen on CPU too |
| Per-document timeout (600s) | Docs completed fine, they just leaked doing so |
| Watchdog script | Detected stalls, not memory growth |
| **Memory monitoring** | **DID NOT EXIST** |

### The fundamental macOS constraint

**macOS has no kernel-enforced per-process memory limits.** Unlike Linux
(cgroups), there is no way to cap a process's RSS. `resource.setrlimit` is a
silent no-op on macOS. launchd resource limits map to the same no-op. Jetsam
thresholds are hardcoded and SIP-protected.

**The only option is self-policing with psutil.** This is not a workaround — it
is literally the only mechanism available on macOS.

---

## Part 3: The Fix

### What we implemented (same day)

| Fix | What it does |
|-----|-------------|
| **Worker recycling** (`max_tasks_per_child=10`) | Kills and respawns workers after 10 documents. Prevents unbounded leak growth. |
| **Three-tier memory monitoring** | Info (24 GB): log. Throttle (36 GB): reduce workers. Ceiling (48 GB): graceful shutdown. |
| **Background watchdog thread** (30s) | Checks RSS independently of document completions. Catches leaks during long-running docs. |
| **Adaptive worker reduction** | 4→3→2→1 workers on throttle events. Shutdown at 1 worker. |
| **Explicit throttle teardown** | 10-step sequence: capture PIDs, cancel futures, shutdown, SIGTERM, bounded wait, SIGKILL, check outputs, clean .part, rebuild pool. |
| **Prewarm in disposable pool** | Avoids loading ~2 GB of Docling models into the supervisor process. |
| **`gc.collect()` per document** | Breaks reference cycles sooner (~10ms cost). |
| **Smallest-first sorting** | Large docs hit fresh workers. |
| **Enhanced monitoring scripts** | `parse_status.sh`: per-worker RSS, color-coded, trends. `parse_watchdog.sh`: observability-only, heartbeat-based. |

### Validated by

- **Council of Experts** — 3 rounds of review by Claude Opus, Gemini 3.1 Pro,
  and Codex (GPT-5.4) at spec, plan, and implementation stages. 6 CRITICALs
  found and fixed before deployment.
- **Forced-threshold tests** — ceiling shutdown at 0.001 GB, throttle 4→3→2
  workers, resume after shutdown.
- **Live run** — 2,400+ docs processed in first 30 minutes, memory stable at
  4-7 GB, 0 throttle events, 99.7% success rate.

### Key metrics from the fix run

| Metric | Before fix (crashed) | After fix |
|--------|---------------------|-----------|
| Peak memory | 127 GB (2x RAM) | 8.9 GB (14% RAM) |
| Memory trend | Monotonically increasing | Flat with periodic drops (recycling) |
| Worker recycling | None | Every ~30 docs (78 events in first 2,400 docs) |
| Throttle events | N/A | 0 |
| Success rate | N/A (crashed) | 99.7% (8 timeouts on pathological PDFs) |
| Throughput | ~6 docs/min before crash | 79 docs/min (small), ~6 docs/min (large) |

---

## Part 4: Lessons Learned

### 1. Memory is the silent killer on macOS batch jobs

Unlike Linux, macOS provides **zero tools for enforcing memory limits**. No
cgroups, no enforceable ulimits, no Jetsam configuration. If your process
leaks memory, macOS will compress pages, swap to SSD, kill background
processes, and eventually kernel-panic. The only defense is self-monitoring
with psutil.

**Rule:** Any batch job running >1 hour on macOS MUST have psutil-based memory
monitoring with a ceiling that triggers graceful shutdown.

### 2. `max_tasks_per_child` is the standard fix for leaking worker pools

Python 3.11+ supports `max_tasks_per_child` in `ProcessPoolExecutor`. This
kills and respawns workers after N tasks, preventing unbounded leak
accumulation. It's the same pattern `multiprocessing.Pool` has had since
Python 2 via `maxtasksperchild`.

**Rule:** Any `ProcessPoolExecutor` running ML models (Docling, PyTorch,
transformers) should use `max_tasks_per_child`. Start with 10-25 and tune
based on observed leak rate.

### 3. Docling has known memory management challenges

Docling loads multiple ML models (layout, table structure, OCR) that persist in
the process. The `DocumentConverter` creates a new converter per call, but the
underlying PyTorch models remain cached. There is no official API to clear
model caches between documents.

The Docling project provides `docling-jobkit` for production batch processing
with `LocalOrchestrator` (shared models, worker management) and
`docling-jobkit-multiproc` CLI. These may handle memory better than our custom
pool. Worth evaluating for future runs.

**Relevant Docling settings that affect memory:**
- `generate_parsed_pages=False` — don't retain intermediate page data (default)
- `ocr_batch_size`, `layout_batch_size`, `table_batch_size` — lower = less memory
- `document_timeout` — per-document timeout at the Docling level
- `queue_max_size` — limits inter-stage buffering in threaded pipeline

### 4. Worker recycling has a 3-5% throughput cost — worth it

At `max_tasks_per_child=10`, each worker reloads Docling models every 10 docs
(~3-5 seconds). Over a 6-hour run this adds ~15-20 minutes. The alternative
is a kernel panic and lost hours.

### 5. Atomic writes + resume logic saved the day

The `.part` → `os.replace()` pattern meant the 1,032 documents completed
before the crash were perfectly intact. The `filter_already_done()` check
(both `.jsonl` AND `.md` must exist with size > 0) meant the re-run picked up
exactly where it left off with zero re-processing.

**Rule:** Any batch job writing output files MUST use atomic writes. Any batch
job running >1 hour MUST support resume.

### 6. Monitoring is not optional for overnight jobs

The original job had monitoring for stalls (watchdog) and disk space, but none
for memory. Memory was the thing that killed it. The fix added:
- Real-time RSS monitoring in the supervisor loop
- Background thread for long-running documents
- Heartbeat file for external monitoring
- Color-coded status script

**Rule:** Monitor the resource that will kill your job. For ML batch jobs on
macOS, that's always memory.

### 7. The Council of Experts review pattern caught 6 critical bugs

Three AI models (Claude, Gemini, Codex) independently reviewing the same code
found bugs that any single model missed:
- **Gemini** found the timer thread leak and lost-futures bug
- **Codex** found the PID-after-shutdown bug and the stale shutdown flag
- **Claude** found the double-shutdown and prewarm hang

Running 3 rounds of review (spec, plan, implementation) with all 3 models
added ~1.5 hours but prevented at least 3 bugs that would have crashed the
overnight run.

### 8. Small docs first, large docs on fresh workers

Sorting documents smallest-first means workers burn through small docs quickly
(building up the completed count and providing early progress feedback), then
hit large docs on freshly recycled workers with maximum memory headroom. This
is both a throughput optimization and a safety strategy.

### 9. Background monitoring catches what synchronous checks miss

The supervisor only checks memory when `wait()` returns (i.e., when a document
completes). If 4 workers are all processing 300-page prospectuses, no
completion occurs for 5-10 minutes. During that window, memory can spike
dramatically with no check. The background thread (30s interval) catches this.

### 10. `caffeinate` prevents sleep but doesn't help with memory

`caffeinate` keeps the machine running, which means a leaking job runs longer
and causes MORE damage. Always pair `caffeinate` with memory monitoring.

---

## Part 5: Future Work

### Reusable solution needed

This incident and fix should be generalized into a reusable package or pattern
for running Docling (and similar ML batch jobs) on any Mac. Key components:

1. **Pre-flight verification script** — checks Python version, venv location,
   dependencies, disk space, Docling installation, memory-fix code present
2. **Portable worker configuration** — auto-detect cores/RAM and set workers,
   `max_tasks_per_child`, and memory thresholds accordingly
3. **Consolidated overnight runbook** — single document with pre-flight,
   launch command, monitoring, recovery decision tree, morning validation
4. **Golden run metrics** — expected throughput, memory curve, recycle
   frequency for different Mac models
5. **Evaluate `docling-jobkit`** — the official batch processing tool may
   handle worker lifecycle better than our custom pool

### Machine scaling table

| Mac Model | RAM | Workers | Throttle | Ceiling | Est. 5K docs |
|-----------|-----|---------|----------|---------|-------------|
| M4 Pro (14-core, 64 GB) | 64 GB | 4 | 36 GB | 48 GB | 6-8 hrs |
| M3 Pro (12-core, 36 GB) | 36 GB | 2-3 | 20 GB | 28 GB | 10-15 hrs |
| M3 Max (14-core, 128 GB) | 128 GB | 4-6 | 72 GB | 96 GB | 4-6 hrs |
| M2 MacBook Air (16 GB) | 16 GB | 1 | 8 GB | 12 GB | 30+ hrs |

Formula: `workers = min((cores - 2) // 3, 6)`, `ceiling = RAM * 0.75`,
`throttle = ceiling * 0.75`.
