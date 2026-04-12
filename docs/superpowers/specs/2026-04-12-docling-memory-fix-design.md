# Docling Memory Leak Fix — Design Spec

**Date:** 2026-04-12
**Context:** Overnight Docling parsing job caused kernel panic by leaking 127 GB
across 10 Python worker processes on a 64 GB Mac Mini M4 Pro. Root cause
analysis in `docs/reports/docling-kernel-panic-2026-04-12.md`.

**Goal:** Fix the memory leak, add monitoring and adaptive throttling, so the
job can safely run overnight and complete ~5,400 remaining documents before the
Spring Meetings presentation on April 13.

**Council of Experts review:** Spec reviewed by Claude Opus 4.6, Gemini 2.5 Pro,
and Codex (GPT-5.4). Findings triaged and incorporated below.

---

## 1. Worker recycling

Add `max_tasks_per_child=10` to `ProcessPoolExecutor`. After 10 documents, the
worker process is killed and a fresh one spawns.

**Why 10:** (revised from 25 after council review — Codex caught that 25 x 1 GB
= 25 GB worst case per worker, not 6 GB as originally claimed)
- Docling model load is ~3-5 seconds. At 10 docs, reload overhead is ~3-5%.
  Acceptable for overnight runs.
- At observed leak rate (~0.5-1 GB per large doc), worst case is 10 GB per
  worker before recycling. 4 workers x 10 GB = 40 GB — within 64 GB, and the
  memory monitoring provides a safety net if this estimate is wrong.
- Exposed as `--max-tasks-per-child` CLI flag for tuning.

**Sort documents smallest-first** by file size. This is a throughput
optimization, not a safety guarantee — the memory monitoring is the safety net.

Note: `--limit N` with smallest-first sorting will process the N smallest docs.
This may not be representative for memory testing. Use `--limit` with caution.

## 2. Memory monitoring and adaptive throttling

### 2a. Primary monitoring (on document completion)

Each time `concurrent.futures.wait()` returns with completed futures, the
supervisor queries RSS of **all Python processes** — workers via
`pool._processes` PIDs AND the supervisor itself via `os.getpid()` — using
`psutil.Process(pid).memory_info().rss`.

Note: `pool._processes` is a private CPython API (dict[int, Process]). The
existing code already uses it (line 458). Acknowledged as pragmatic — add a
code comment noting the dependency.

### 2b. Background safety net (independent of document completion)

A background `threading.Timer` thread checks total RSS every 30 seconds,
independent of document completions. This catches memory growth during
long-running documents (some LuxSE PDFs take 10+ minutes) where no `wait()`
return occurs.

The background thread only triggers the **ceiling** action (graceful shutdown).
Throttle decisions are made in the main loop where pool teardown can be
coordinated safely.

### 2c. Thresholds

Three thresholds with escalating responses. Info threshold is derived:
`info = throttle * 0.67`.

| Threshold | Default | CLI flag | Action |
|-----------|---------|----------|--------|
| **Info** | 24 GB | (derived from throttle) | Log warning, continue |
| **Throttle** | 36 GB | `--memory-throttle` | Kill pool, restart with `max_workers - 1` (min 1). Log prominently. |
| **Ceiling** | 48 GB | `--memory-ceiling` | Graceful shutdown. Save progress, write summary, exit cleanly. |

**At 1 worker:** throttle threshold triggers graceful shutdown (same as
ceiling), since there is nowhere to reduce to.

### 2d. psutil failure handling

If `psutil.Process(pid).memory_info()` raises any exception (NoSuchProcess,
AccessDenied, OSError), the unreadable PID is counted as consuming **8 GB**
(conservative estimate based on observed per-worker peaks). This ensures
monitoring fails safe — missing data triggers thresholds sooner, not later.

### 2e. Throttle teardown sequence

When the throttle threshold is exceeded, the supervisor executes this exact
sequence:

1. **Capture PIDs** — copy `list(pool._processes.keys())` before any shutdown
2. **Cancel unstarted futures** — `fut.cancel()` for queued items, re-queue to
   `remaining`
3. **Shutdown pool** — `pool.shutdown(wait=False, cancel_futures=True)`
4. **SIGTERM captured PIDs** — terminate workers using the captured PID list
   (not `pool._processes`, which may be cleared by shutdown)
5. **Bounded wait** — wait up to 10 seconds for workers to exit. Escalate to
   SIGKILL for any survivors.
6. **Verify old workers gone** — confirm all captured PIDs are dead before
   proceeding
7. **Check output files** — for each in-flight item, check if both `.jsonl`
   and `.md` exist. If yes: count as completed. If no: re-queue (up to 2
   crash retries per doc, then quarantine).
8. **Clean up `.part` files** — remove any orphaned `.part` files from
   interrupted atomic writes
9. **Create new pool** — `ProcessPoolExecutor(max_workers=current_workers - 1,
   max_tasks_per_child=max_tasks_per_child)`
10. **Resume** — continue processing from remaining queue

This is the same logic as the existing `BrokenProcessPool` handler, plus
steps 1, 5, 6, and 8 which address the council's concerns about overlapping
pool generations and orphaned files.

### 2f. Memory logged to progress file

Each progress entry gets `memory_gb`, `workers`, and `file_size_mb` fields.

## 3. Enhanced status and watchdog scripts

All memory reporting in shell scripts uses pure shell commands (`ps aux`,
`pgrep`, `awk`) — no Python imports, no `psutil` dependency in shell.

### parse_status.sh additions
- Per-worker PID and RSS via `ps -o pid,rss -p <pids>`
- Total Python memory and percentage of system RAM
- Memory trend: compare current total to value 50 docs ago from progress log
- Color-coded: green <24 GB, yellow 24-36 GB, red >36 GB

### parse_watchdog.sh additions
- Check total Python RSS alongside stall detection
- If total RSS >40 GB and growing, log a warning line
- Read heartbeat file written by supervisor (contains current worker count,
  last-activity timestamp, current memory). Use this to avoid killing a
  throttled-down supervisor that is still making progress.
- No auto-kill: adaptive throttling in supervisor handles that. Watchdog is
  observability only.

### Supervisor heartbeat file
The supervisor writes `_heartbeat.json` every 30 seconds (same timer as
background memory monitoring):
```json
{"timestamp": "...", "workers": 3, "memory_gb": 22.1, "completed": 450, "remaining": 4950}
```
The watchdog reads this instead of relying solely on progress log recency.

### Progress log schema change
```json
{"status": "success", "storage_key": "...", "page_count": 42, "elapsed_s": 55.1,
 "memory_gb": 18.3, "workers": 4, "file_size_mb": 12.3, "timestamp": "..."}
```

### Summary JSON additions
```json
{"throttle_events": 1, "peak_memory_gb": 28.4, ...}
```

## 4. Prewarm in pool, not supervisor

Move the prewarm step from the supervisor process into the pool. Submit the
first document as a regular pool task instead of calling `process_one_pdf()`
directly in the parent. This avoids the supervisor accumulating ~2 GB of
Docling model state that persists for the entire run.

## 5. Worker-level optimization

Add `gc.collect()` at the end of `process_one_pdf()`, after writing output
files. This won't return memory to the OS (Python's allocator doesn't do
that), but it breaks reference cycles sooner and may modestly reduce the rate
of heap fragmentation. Cost: ~10ms per document.

## 6. Dependency and configuration

**New dependency:** `psutil` added to `pyproject.toml`. Run `uv sync` after.

**New CLI flags (docling_reparse.py):**
- `--memory-ceiling` (default 48) — GB threshold for graceful shutdown
- `--memory-throttle` (default 36) — GB threshold for reducing workers
- `--max-tasks-per-child` (default 10) — documents per worker before recycle

Existing `--workers 4` and `--timeout 600` unchanged.

**No changes to:**
- `config.toml` — script-level concern, not pipeline config
- `src/corpus/parsers/docling_parser.py` — parser is fine, leak is in Docling
  internals accumulating across calls
- `src/corpus/cli.py` — sequential `corpus parse run` doesn't have this problem
- Resume logic — unchanged, checks `.jsonl` + `.md` pairs
- Atomic write pattern — unchanged

## 7. What we're NOT doing

- **subprocess-per-document** — too slow, worker recycling solves same problem
- **ulimit/cgroup memory limits** — macOS doesn't support cgroups, ulimit RSS
  unreliable on Darwin
- **Docling internal config changes** — leak is in their ML model caching /
  PyTorch internals, not configurable
- **Adding swap** — unified memory doesn't benefit, just delays the crash
- **Makefile parse target** — invokes sequential CLI, not this script
- **Changing default to 2 workers** — adaptive throttling handles this
  dynamically. Document `--workers 2` as conservative option for large corpus.

## 8. Files changed

| File | Change |
|------|--------|
| `scripts/docling_reparse.py` | Worker recycling, memory monitoring (primary + background thread), adaptive throttling with explicit teardown, prewarm in pool, gc.collect, heartbeat file, progress log fields, summary fields |
| `scripts/parse_status.sh` | Per-worker RSS (via `ps`), total memory, trend, color-coding |
| `scripts/parse_watchdog.sh` | RSS check via `ps`, read heartbeat file for stall detection |
| `pyproject.toml` | Add `psutil` dependency |

## 9. Completion criteria

1. `docling_reparse.py` uses `max_tasks_per_child=10` (configurable via CLI)
2. Primary memory monitoring queries all Python RSS on every `wait()` return
3. Background thread checks RSS every 30 seconds independently
4. Three-tier response: info (derived), throttle at 36 GB, ceiling at 48 GB
5. Adaptive worker reduction: 4 -> 3 -> 2 -> 1 on throttle, shutdown at 1
6. Throttle teardown follows explicit 10-step sequence (capture PIDs first, SIGKILL escalation, verify dead, clean .part files)
7. psutil failures counted as 8 GB (fail-safe)
8. Supervisor RSS included in total (prewarm moved into pool)
9. Progress log entries include `memory_gb`, `workers`, `file_size_mb`
10. Summary includes `throttle_events` and `peak_memory_gb`
11. Heartbeat file written every 30s, read by watchdog
12. `parse_status.sh` shows per-worker memory via pure shell
13. `parse_watchdog.sh` reads heartbeat, uses `ps` for memory
14. `psutil` added to `pyproject.toml`, `uv sync` run
15. `--memory-ceiling`, `--memory-throttle`, `--max-tasks-per-child` CLI flags
16. Documents sorted smallest-first by file size
17. `gc.collect()` after each document in worker
18. Existing resume logic, atomic writes, and all tests still pass
19. Soak test: run 50 large LuxSE docs with `--workers 4`, verify memory stays bounded
20. Forced-throttle test: set `--memory-throttle 2` and verify worker reduction
21. Forced-ceiling test: set `--memory-ceiling 2` and verify graceful shutdown + resume
