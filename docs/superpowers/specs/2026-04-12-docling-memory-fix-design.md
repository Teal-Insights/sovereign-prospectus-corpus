# Docling Memory Leak Fix — Design Spec

**Date:** 2026-04-12
**Context:** Overnight Docling parsing job caused kernel panic by leaking 127 GB
across 10 Python worker processes on a 64 GB Mac Mini M4 Pro. Root cause
analysis in `docs/reports/docling-kernel-panic-2026-04-12.md`.

**Goal:** Fix the memory leak, add monitoring and adaptive throttling, so the
job can safely run overnight and complete ~5,400 remaining documents before the
Spring Meetings presentation on April 13.

---

## 1. Worker recycling

Add `max_tasks_per_child=25` to `ProcessPoolExecutor`. After 25 documents, the
worker process is killed and a fresh one spawns.

**Why 25:**
- Docling model load is ~3-5 seconds. At 25 docs, reload overhead is ~1-2%.
- At observed leak rate (~0.5-1 GB per large doc), workers peak ~6 GB before
  recycling. 4 workers x 6 GB = 24 GB, well within 64 GB.
- 10 adds unnecessary reload overhead. 50 risks 12+ GB per worker.

**Sort documents smallest-first** by file size so large documents (worst
leakers) land on freshly recycled workers.

## 2. Memory monitoring and adaptive throttling

Each time `concurrent.futures.wait()` returns with completed futures (i.e.,
every time any worker finishes a document), the supervisor queries RSS of all
worker PIDs via `psutil.Process(pid).memory_info().rss`.

Three thresholds with escalating responses:

| Threshold | Total Python RSS | Action |
|-----------|-----------------|--------|
| **Info** | >24 GB | Log warning, continue |
| **Throttle** | >36 GB | Kill pool, restart with `max_workers - 1` (min 1). Log prominently. |
| **Ceiling** | >48 GB | Graceful shutdown. Save progress, write summary, exit cleanly. |

**Why these numbers on 64 GB:**
- 24 GB: expected healthy ceiling with recycling. Exceeding it = something
  unexpected, worth logging.
- 36 GB: enough headroom for macOS (~8-10 GB for itself + Dropbox + services).
  Throttling reduces parallelism to buy time.
- 48 GB: last resort. Better to stop cleanly and resume than crash the machine.

**Adaptive worker reduction:** When throttle triggers, supervisor tears down the
pool and rebuilds with one fewer worker. In-flight items re-queued (same as
existing BrokenProcessPool handling). Can happen multiple times: 4 -> 3 -> 2 -> 1.
At 1 worker hitting ceiling, shut down.

**Memory logged to progress file:** Each progress entry gets `memory_gb` and
`workers` fields.

## 3. Enhanced status and watchdog scripts

### parse_status.sh additions
- Per-worker PID and RSS (e.g., `Worker PID 12345: 3.2 GB`)
- Total Python memory and percentage of system RAM
- Memory trend: compare current total to value 50 docs ago from progress log
- Color-coded: green <24 GB, yellow 24-36 GB, red >36 GB

### parse_watchdog.sh additions
- Check total Python RSS alongside stall detection
- If total RSS >40 GB and growing, log a warning line
- No auto-kill: adaptive throttling in supervisor handles that. Watchdog is
  observability only.

### Progress log schema change
```json
{"status": "success", "storage_key": "...", "page_count": 42, "elapsed_s": 55.1,
 "memory_gb": 18.3, "workers": 4, "timestamp": "..."}
```

Two new fields: `memory_gb` (total Python RSS at time of logging) and `workers`
(current worker count, visible throttle events in log).

## 4. Dependency and configuration

**New dependency:** `psutil` added to `pyproject.toml`.

**New CLI flags (docling_reparse.py):**
- `--memory-ceiling` (default 48) — GB threshold for graceful shutdown
- `--memory-throttle` (default 36) — GB threshold for reducing workers

Existing `--workers 4` and `--timeout 600` unchanged.

**No changes to:**
- `config.toml` — script-level concern, not pipeline config
- `src/corpus/parsers/docling_parser.py` — parser is fine, leak is in Docling
  internals accumulating across calls
- `src/corpus/cli.py` — sequential `corpus parse run` doesn't have this problem
- Resume logic — unchanged, checks `.jsonl` + `.md` pairs
- Atomic write pattern — unchanged

## 5. What we're NOT doing

- **subprocess-per-document** — too slow, worker recycling solves same problem
- **ulimit/cgroup memory limits** — macOS doesn't support cgroups, ulimit RSS
  unreliable on Darwin
- **max_tasks_per_child < 25** — diminishing returns, model reload cost matters
- **Docling internal config changes** — leak is in their ML model caching /
  PyTorch internals, not configurable
- **Adding swap** — unified memory doesn't benefit, just delays the crash
- **Makefile parse target** — invokes sequential CLI, not this script

## 6. Files changed

| File | Change |
|------|--------|
| `scripts/docling_reparse.py` | Worker recycling, memory monitoring, adaptive throttling, sort smallest-first, progress log fields |
| `scripts/parse_status.sh` | Per-worker RSS, total memory, trend, color-coding |
| `scripts/parse_watchdog.sh` | RSS check alongside stall detection |
| `pyproject.toml` | Add `psutil` dependency |

## 7. Completion criteria

1. `docling_reparse.py` uses `max_tasks_per_child=25` for worker recycling
2. Memory monitoring queries worker RSS every batch cycle
3. Three-tier response: log at 24 GB, throttle workers at 36 GB, shutdown at 48 GB
4. Adaptive worker reduction: 4 -> 3 -> 2 -> 1 on repeated throttle triggers
5. Progress log entries include `memory_gb` and `workers` fields
6. `parse_status.sh` shows per-worker memory, total, trend, color-coded
7. `parse_watchdog.sh` includes RSS check
8. `psutil` added to `pyproject.toml`
9. `--memory-ceiling` and `--memory-throttle` CLI flags work
10. Documents sorted smallest-first by file size
11. Existing resume logic, atomic writes, and all tests still pass
12. Job can be started tonight and run unattended to completion
