# Docling Kernel Panic — Root Cause Analysis

**Date:** 2026-04-12 (crash at ~04:29 EDT)
**Machine:** Mac Mini M4 Pro, 64 GB RAM (Mac16,11)
**macOS:** 26.3.1 (25D2128)

## What happened

The Mac Mini kernel-panicked and rebooted during an overnight Docling PDF
parsing job. The user woke up to "Your computer was restarted because of a
problem."

## Timeline

| Time (EDT) | Event |
|------------|-------|
| ~21:53 | Docling reparse started (1,032 docs attempted) |
| 04:29 | **Jetsam Event #1** — system at 62.6 GB / 64 GB, 24 MB free. macOS starts killing processes. 5,478 processes jettisoned. |
| 04:33 | **Jetsam Event #2** — system still critical. Wired memory 17.4 GB, compressor 27.3 GB, 133 MB free. Python workers still running. |
| ~04:33–06:44 | **Kernel panic** — macOS could not recover memory fast enough. Watchdog timer triggered hardware reset (`wdog,reset_in_1`). |
| 06:44 | System rebooted (ResetCounter logged). |

## Root cause: Docling memory leak in long-lived worker processes

**10 Python 3.12 processes consumed 127 GB of resident memory on a 64 GB machine.**

The jetsam logs show two generations of worker processes:

| Process | Resident Memory | Notes |
|---------|---------------:|-------|
| PID 27681 (Gen 1 worker) | 23,581 MB | ~23 GB each |
| PID 27680 (Gen 1 worker) | 22,537 MB | |
| PID 27678 (Gen 1 worker) | 21,303 MB | |
| PID 27679 (Gen 1 worker) | 19,341 MB | |
| PID 96312 (Gen 2 worker) | 15,278 MB | Pool restarted, new workers already leaking |
| PID 96311 (Gen 2 worker) | 9,799 MB | |
| PID 96310 (Gen 2 worker) | 9,782 MB | |
| PID 96313 (Gen 2 worker) | 6,356 MB | |
| PID 27637 (supervisor) | 1,927 MB | |
| PID 27669 (unknown) | 9 MB | |
| **Total Python** | **129,913 MB** | **~127 GB — 2x physical RAM** |

The macOS memory compressor was holding 29.1 GB of compressed data, meaning
the system was desperately trying to keep everything alive by compressing
memory pages. When even compressed memory filled up, the kernel watchdog
timer expired and forced a hardware reset.

### Why the workers leaked

Each worker calls `DocumentConverter()` and `converter.convert()` per
document in `process_one_pdf()`. Docling loads ML models (layout analysis,
table structure recognition, OCR) into memory on first use. These models
persist in the process for its entire lifetime.

**The critical issue:** `ProcessPoolExecutor` reuses worker processes across
all documents. A worker that processes 200+ documents accumulates:

1. **ML model caches** — Docling's internal model caches grow with each
   document variant encountered
2. **PyTorch/MPS GPU memory** — Metal Performance Shaders allocate device
   memory that isn't fully released between documents
3. **Python object graph fragmentation** — large intermediate objects
   (page images, layout tensors) fragment the heap; even after GC, the
   process RSS doesn't shrink because Python's memory allocator doesn't
   return pages to the OS
4. **Per-page markdown/text accumulation** — 200-300 page prospectuses
   generate large intermediate strings

### Why the existing safeguards didn't help

| Safeguard | Why it failed |
|-----------|--------------|
| Disk space check | Memory was the problem, not disk |
| Pool restart on BrokenProcessPool | Pool never crashed — workers just leaked silently |
| MPS fallback to CPU | MPS errors trigger fallback, but memory leaks happen on CPU too |
| Per-document timeout (600s) | Documents completed successfully — they just leaked memory doing so |
| Watchdog script | Detects stalled progress, not memory growth |

**There are zero memory guards in the current code.** No per-process RSS
monitoring, no worker recycling, no memory ceiling.

## Fix plan

### Fix 1: Worker recycling (critical — prevents the crash)

Add `max_tasks_per_child` to `ProcessPoolExecutor` to kill and restart
worker processes after N documents. This is the single most important fix.

```python
# Before (workers live forever, leak memory):
pool = ProcessPoolExecutor(max_workers=max_workers)

# After (workers recycled every N documents):
pool = ProcessPoolExecutor(
    max_workers=max_workers,
    max_tasks_per_child=25,  # Kill worker after 25 docs, spawn fresh one
)
```

**Why 25?** At ~1 GB leak per large document, 25 docs keeps each worker
under ~6 GB peak. 4 workers x 6 GB = 24 GB, well within 64 GB.

> Note: `max_tasks_per_child` requires Python 3.11+. We're on 3.12.

### Fix 2: Memory pressure monitoring (safety net)

Add RSS monitoring in the supervisor loop. If total Python memory exceeds a
threshold, trigger graceful shutdown instead of letting macOS kill everything.

```python
import psutil

def get_pool_memory_gb(pool):
    """Sum RSS of all worker processes."""
    total = 0
    for pid in list(pool._processes or []):
        try:
            total += psutil.Process(pid).memory_info().rss
        except (psutil.NoSuchProcess, ProcessLookupError):
            pass
    return total / (1024 ** 3)

# In the periodic check (every 50 docs):
pool_mem = get_pool_memory_gb(pool)
if pool_mem > 48.0:  # 48 GB ceiling on 64 GB machine
    logging.error("Memory ceiling reached: %.1f GB. Stopping to prevent crash.", pool_mem)
    shutdown_requested = True
```

### Fix 3: Reduce worker count for LuxSE corpus

The original 4-worker config was tuned for 1,468 smaller PDIP/NSM documents.
The LuxSE corpus has 5,605 documents including many 200-500 page
prospectuses. Reduce to 2 workers for large-corpus runs.

```bash
# For LuxSE (large docs, long runs):
python scripts/docling_reparse.py --workers 2 --timeout 900
```

### Fix 4: Sort documents smallest-first

Process small documents first so workers get recycled on cheap docs. Large
documents (which leak the most memory) run on fresh workers.

```python
# Sort by file size ascending — small docs first
remaining.sort(key=lambda x: Path(x[1]).stat().st_size)
```

### Fix 5: Add memory to status/watchdog scripts

Update `parse_status.sh` and `parse_watchdog.sh` to report Python process
memory, so overnight monitoring catches runaway growth before it becomes
critical.

## Implementation priority

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | `max_tasks_per_child=25` | 1 line | **Prevents the crash entirely** |
| 2 | Memory pressure monitoring | ~20 lines | Safety net for edge cases |
| 3 | Reduce workers for large corpus | CLI flag | Reduces peak memory |
| 4 | Sort smallest-first | 1 line | Optimizes worker recycling |
| 5 | Watchdog memory reporting | ~10 lines | Early warning |

## Recovery

The parsing job has resume support — 1,032 of ~6,428 documents completed
successfully before the crash. After applying fixes, re-run with the same
command and it will pick up where it left off.
