# Docling Memory Leak Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Docling worker memory leak that caused a kernel panic, add memory monitoring with adaptive throttling, so the parse can run unattended overnight.

**Architecture:** Worker recycling via `max_tasks_per_child` prevents unbounded leak growth. A three-tier memory monitoring system (info/throttle/ceiling) with both synchronous (on document completion) and asynchronous (background thread every 30s) checks provides layered defense. Adaptive throttling reduces workers before ceiling triggers graceful shutdown.

**Tech Stack:** Python 3.12, `concurrent.futures.ProcessPoolExecutor`, `psutil`, `threading.Timer`, shell (`ps`, `pgrep`, `awk`)

**Spec:** `docs/superpowers/specs/2026-04-12-docling-memory-fix-design.md`
**Script under modification:** `scripts/docling_reparse.py` (567 lines)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/docling_reparse.py` | Modify | Worker recycling, memory monitoring, adaptive throttling, heartbeat |
| `scripts/parse_status.sh` | Modify | Show per-worker RSS, total memory, color-coded |
| `scripts/parse_watchdog.sh` | Modify | Read heartbeat file, RSS check via `ps` |
| `pyproject.toml` | Modify | Add `psutil` dependency |
| `tests/test_memory_monitor.py` | Create | Unit tests for memory monitoring functions |

---

### Task 1: Add `psutil` dependency

**Files:**
- Modify: `pyproject.toml:6-14`

- [ ] **Step 1: Add psutil to dependencies**

In `pyproject.toml`, add `psutil` to the dependencies list:

```toml
dependencies = [
    "duckdb>=1.4,<1.5",
    "polars>=1.0",
    "pymupdf>=1.24",
    "requests>=2.31",
    "click>=8.1",
    "beautifulsoup4>=4.14.3",
    "docling>=2.86.0",
    "psutil>=5.9",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: psutil installed, no errors

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import psutil; print(psutil.__version__)"`
Expected: prints version number

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add psutil for memory monitoring"
```

---

### Task 2: Extract memory monitoring functions

**Files:**
- Modify: `scripts/docling_reparse.py` (add functions after line 56)
- Create: `tests/test_memory_monitor.py`

- [ ] **Step 1: Write test for `get_total_python_rss_gb`**

Create `tests/test_memory_monitor.py`:

```python
"""Tests for memory monitoring functions in docling_reparse."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


def test_get_total_python_rss_gb_includes_supervisor():
    """RSS sum must include the supervisor process, not just workers."""
    # Import using absolute path to avoid cwd-dependent failures
    import importlib.util
    from pathlib import Path

    script_path = str(Path(__file__).resolve().parent.parent / "scripts" / "docling_reparse.py")
    spec = importlib.util.spec_from_file_location("docling_reparse", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_pool = MagicMock()
    # Simulate 2 workers with known PIDs
    mock_pool._processes = {100: None, 200: None}

    def fake_process(pid):
        p = MagicMock()
        mem = MagicMock()
        # Worker 100: 2 GB, Worker 200: 3 GB, Supervisor (os.getpid()): 1 GB
        rss_map = {100: 2 * 1024**3, 200: 3 * 1024**3, os.getpid(): 1 * 1024**3}
        mem.rss = rss_map.get(pid, 0)
        p.memory_info.return_value = mem
        return p

    with patch("psutil.Process", side_effect=fake_process):
        total = mod.get_total_python_rss_gb(mock_pool)
        # 2 + 3 + 1 = 6 GB
        assert abs(total - 6.0) < 0.01


def test_get_total_python_rss_gb_psutil_failure_counts_as_8gb():
    """If psutil can't read a PID, count it as 8 GB (fail-safe)."""
    import importlib.util
    from pathlib import Path

    script_path = str(Path(__file__).resolve().parent.parent / "scripts" / "docling_reparse.py")
    spec = importlib.util.spec_from_file_location("docling_reparse", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_pool = MagicMock()
    mock_pool._processes = {100: None, 200: None}

    call_count = 0

    def fake_process(pid):
        nonlocal call_count
        call_count += 1
        if pid == 200:
            raise OSError("Permission denied")
        p = MagicMock()
        mem = MagicMock()
        mem.rss = 2 * 1024**3  # 2 GB for readable PIDs
        p.memory_info.return_value = mem
        return p

    with patch("psutil.Process", side_effect=fake_process):
        total = mod.get_total_python_rss_gb(mock_pool)
        # PID 100: 2 GB, PID 200: 8 GB (fail-safe), supervisor: 2 GB
        assert total >= 10.0  # At least 8 + 2 from the fail-safe + supervisor
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_memory_monitor.py -v`
Expected: FAIL — `get_total_python_rss_gb` does not exist yet

- [ ] **Step 3: Implement `get_total_python_rss_gb`**

Add after line 56 in `scripts/docling_reparse.py`:

```python
FAIL_SAFE_RSS_GB = 8.0  # Conservative estimate for unreadable worker PIDs


def get_total_python_rss_gb(pool: ProcessPoolExecutor) -> float:
    """Sum RSS of all worker processes + supervisor. Fail-safe: unreadable PIDs count as 8 GB."""
    import psutil

    total_bytes = 0
    unreadable = 0

    # Worker processes
    for pid in list(pool._processes or {}):  # noqa: SLF001 — private API, acknowledged
        try:
            total_bytes += psutil.Process(pid).memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            unreadable += 1

    # Supervisor process
    try:
        total_bytes += psutil.Process(os.getpid()).memory_info().rss
    except (Exception,):
        unreadable += 1

    total_gb = total_bytes / (1024**3)
    total_gb += unreadable * FAIL_SAFE_RSS_GB

    if unreadable:
        logging.warning(
            "Could not read RSS for %d process(es), counting as %.0f GB each",
            unreadable,
            FAIL_SAFE_RSS_GB,
        )

    return total_gb
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_memory_monitor.py -v`
Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/docling_reparse.py tests/test_memory_monitor.py
git commit -m "feat: add get_total_python_rss_gb with fail-safe for unreadable PIDs"
```

---

### Task 3: Add worker recycling and new CLI flags

**Files:**
- Modify: `scripts/docling_reparse.py:285,494-499`

- [ ] **Step 1: Add CLI flags for memory thresholds and max-tasks-per-child**

Replace the `main()` argument parsing section (lines 495-498) with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="Docling PDF re-parse")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    parser.add_argument("--timeout", type=int, default=600, help="Per-document timeout in seconds")
    parser.add_argument("--limit", type=int, default=None, help="Max documents to process")
    parser.add_argument(
        "--max-tasks-per-child",
        type=int,
        default=10,
        help="Documents per worker before recycle (default: 10)",
    )
    parser.add_argument(
        "--memory-throttle",
        type=float,
        default=36.0,
        help="GB threshold to reduce workers (default: 36)",
    )
    parser.add_argument(
        "--memory-ceiling",
        type=float,
        default=48.0,
        help="GB threshold for graceful shutdown (default: 48)",
    )
    args = parser.parse_args()
```

- [ ] **Step 2: Pass new args to `run_supervised`**

Update the `run_supervised` call (line 562) and signature to accept the new parameters:

```python
def run_supervised(
    pdf_list: list[tuple[str, Path]],
    max_workers: int,
    timeout: int,
    max_tasks_per_child: int = 10,
    memory_throttle_gb: float = 36.0,
    memory_ceiling_gb: float = 48.0,
) -> dict:
```

And the call in `main()`:

```python
    run_supervised(
        remaining,
        args.workers,
        args.timeout,
        max_tasks_per_child=args.max_tasks_per_child,
        memory_throttle_gb=args.memory_throttle,
        memory_ceiling_gb=args.memory_ceiling,
    )
```

- [ ] **Step 3: Add `max_tasks_per_child` to ProcessPoolExecutor**

In `run_supervised`, change the pool creation (line 285):

```python
            pool = ProcessPoolExecutor(
                max_workers=max_workers,
                max_tasks_per_child=max_tasks_per_child,
            )
```

- [ ] **Step 4: Log the new configuration at startup**

Add to the logging section in `main()` (after line 509):

```python
    logging.info("  Max tasks per child: %d", args.max_tasks_per_child)
    logging.info("  Memory throttle: %.0f GB", args.memory_throttle)
    logging.info("  Memory ceiling: %.0f GB", args.memory_ceiling)
```

- [ ] **Step 5: Verify script still parses arguments**

Run: `uv run python scripts/docling_reparse.py --help`
Expected: shows all flags including `--max-tasks-per-child`, `--memory-throttle`, `--memory-ceiling`

- [ ] **Step 6: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "feat: add worker recycling (max_tasks_per_child=10) and memory threshold CLI flags"
```

---

### Task 4: Add smallest-first sorting and move prewarm into pool

**Files:**
- Modify: `scripts/docling_reparse.py:526-559`

- [ ] **Step 1: Sort documents smallest-first**

After the `filter_already_done` call and before the `--limit` check, add:

```python
    remaining = filter_already_done(all_pdfs)
    # Sort smallest-first: large docs (worst leakers) hit freshly recycled workers
    remaining.sort(key=lambda item: item[1].stat().st_size)
    logging.info(
        "After resume filter: %d remaining (%d already done), sorted smallest-first",
        len(remaining),
        len(all_pdfs) - len(remaining),
    )
```

- [ ] **Step 2: Move prewarm into pool**

Replace the prewarm section (lines 544-559) with:

```python
    # Prewarm: the first document runs in a disposable pool (not the supervisor)
    # to avoid loading Docling models into the parent process (~2 GB persistent leak).
    # Use explicit shutdown(wait=False) + SIGTERM on failure, since the context
    # manager's __exit__ calls shutdown(wait=True) which hangs on stuck workers.
    logging.info("Prewarming on first document (in pool)...")
    prewarm_pool = ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1)
    try:
        prewarm_future = prewarm_pool.submit(
            process_one_pdf, (remaining[0][0], str(remaining[0][1]))
        )
        prewarm_result = prewarm_future.result(timeout=args.timeout)
    except (TimeoutError, Exception) as exc:
        logging.error("Prewarm failed: %s", exc)
        prewarm_pool.shutdown(wait=False, cancel_futures=True)
        for pid in list(prewarm_pool._processes or {}):  # noqa: SLF001
            import contextlib
            with contextlib.suppress(ProcessLookupError, OSError):
                os.kill(pid, signal.SIGTERM)
        sys.exit(1)
    else:
        prewarm_pool.shutdown(wait=False)
    if prewarm_result["status"] != "success":
        logging.error("Prewarm failed: %s. Check Docling installation.", prewarm_result["error"])
        sys.exit(1)
    logging.info(
        "Prewarm OK: %s — %d pages in %.1fs",
        prewarm_result["storage_key"],
        prewarm_result["page_count"],
        prewarm_result["elapsed_s"],
    )
    write_progress(prewarm_result)
    remaining = remaining[1:]
```

- [ ] **Step 3: Run lint**

Run: `uv run ruff check scripts/docling_reparse.py`
Expected: no errors (or only pre-existing ones)

- [ ] **Step 4: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "feat: sort docs smallest-first, move prewarm into disposable pool"
```

---

### Task 5: Add `gc.collect()` and enhanced progress logging in worker

**Files:**
- Modify: `scripts/docling_reparse.py:135-243`

- [ ] **Step 1: Add `gc.collect()` at end of worker function**

At the top of `process_one_pdf`, add `import gc`. At the end of the try block, before the return (after line 223, after `os.replace`):

```python
        # Break reference cycles to slow heap fragmentation (~10ms)
        gc.collect()

        return {
            "status": "success",
            ...
```

- [ ] **Step 2: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "feat: add gc.collect() after each document to slow heap fragmentation"
```

---

### Task 6: Integrate memory monitoring into the supervisor loop

This is the largest task — wiring the monitoring, throttle teardown, and
background thread into `run_supervised`.

**Files:**
- Modify: `scripts/docling_reparse.py:249-479`

- [ ] **Step 1: Add memory tracking state variables**

At the start of `run_supervised`, after `batch_size = max_workers * 2` (line 278), add:

```python
    memory_info_gb = memory_throttle_gb * 0.67  # Info threshold derived from throttle
    current_max_workers = max_workers
    throttle_events = 0
    peak_memory_gb = 0.0
    bg_shutdown_flag = False  # Set by background thread if ceiling exceeded
```

- [ ] **Step 2: Add the background memory monitoring thread**

Add a new function before `run_supervised`. **Key design choice (from council
review):** return a `threading.Event` stop flag so the caller can cancel the
timer chain before pool teardown. This prevents stale timers from reading dead
pools, writing stale heartbeats, or falsely tripping the ceiling after a
throttle event.

```python
import threading


def _start_memory_watchdog(
    pool: ProcessPoolExecutor,
    ceiling_gb: float,
    heartbeat_path: Path,
    shutdown_flag: list,  # [bool] — mutable container for cross-thread signaling
    completed_ref: list,  # [completed_count]
    remaining_ref: list,  # [remaining_count]
    workers_ref: list,  # [current_worker_count]
    interval: float = 30.0,
) -> threading.Event:
    """Background thread: check RSS every 30s, write heartbeat, trigger ceiling shutdown.

    Returns a threading.Event — call .set() to stop the timer chain before
    pool teardown. This prevents stale timers from reading dead pools.
    """
    stop_event = threading.Event()

    def _check():
        if stop_event.is_set() or shutdown_flag[0]:
            return  # Cancelled or already shutting down — do not reschedule
        try:
            mem_gb = get_total_python_rss_gb(pool)
            # Write heartbeat atomically (.part -> rename)
            heartbeat = {
                "timestamp": datetime.now(UTC).isoformat(),
                "workers": workers_ref[0],
                "memory_gb": round(mem_gb, 1),
                "completed": completed_ref[0],
                "remaining": remaining_ref[0],
            }
            part = heartbeat_path.with_suffix(".json.part")
            part.write_text(json.dumps(heartbeat))
            os.replace(str(part), str(heartbeat_path))

            if mem_gb > ceiling_gb:
                logging.error(
                    "BACKGROUND MONITOR: Memory %.1f GB exceeds ceiling %.1f GB. "
                    "Requesting shutdown.",
                    mem_gb,
                    ceiling_gb,
                )
                shutdown_flag[0] = True
                return  # Don't reschedule
        except Exception:
            logging.exception("Background memory monitor error")

        # Schedule next check (only if not stopped)
        if not stop_event.is_set():
            t = threading.Timer(interval, _check)
            t.daemon = True
            t.start()

    # Start first check
    t = threading.Timer(interval, _check)
    t.daemon = True
    t.start()
    return stop_event
```

- [ ] **Step 3: Add throttle teardown function**

Add before `run_supervised`:

```python
def _throttle_teardown(
    pool: ProcessPoolExecutor,
    futures: dict,
    remaining: deque,
    crash_counts: dict,
    watchdog_stop: threading.Event | None = None,
) -> tuple[int, int]:
    """Execute the 10-step throttle teardown. Returns (completed, failed) counts.

    IMPORTANT: Cancel the background watchdog FIRST (via watchdog_stop) to prevent
    stale timer threads from reading the dead pool or writing stale heartbeats.
    """
    completed = 0
    failed = 0

    # Step 0: Cancel background watchdog before touching the pool
    if watchdog_stop is not None:
        watchdog_stop.set()

    # Step 1: Capture PIDs before shutdown clears them
    captured_pids = list(pool._processes or {})  # noqa: SLF001

    # Step 2: Cancel unstarted futures, re-queue
    for fut, args in list(futures.items()):
        if fut.cancel():
            remaining.appendleft(args)
            del futures[fut]

    # Step 3: Shutdown pool
    pool.shutdown(wait=False, cancel_futures=True)

    # Step 4: SIGTERM captured PIDs
    import contextlib

    for pid in captured_pids:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, signal.SIGTERM)

    # Step 5: Bounded wait (10s), escalate to SIGKILL
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        alive = []
        for pid in captured_pids:
            try:
                os.kill(pid, 0)  # Check if alive
                alive.append(pid)
            except (ProcessLookupError, OSError):
                pass
        if not alive:
            break
        time.sleep(0.5)
    else:
        # Step 6: SIGKILL survivors
        for pid in alive:
            with contextlib.suppress(ProcessLookupError, OSError):
                os.kill(pid, signal.SIGKILL)
                logging.warning("SIGKILL sent to hung worker PID %d", pid)

    # Step 7: Check output files for in-flight items
    for fut, args in list(futures.items()):
        sk = args[0]
        jsonl_out = OUTPUT_DIR / f"{sk}.jsonl"
        md_out = OUTPUT_DIR / f"{sk}.md"
        if jsonl_out.exists() and md_out.exists():
            completed += 1
        else:
            crash_counts[sk] = crash_counts.get(sk, 0) + 1
            if crash_counts[sk] <= 2:
                remaining.appendleft(args)
            else:
                failed += 1
                logging.error("QUARANTINED after %d crashes: %s", crash_counts[sk], sk)
    futures.clear()

    # Step 8: Clean up orphaned .part files
    for part_file in OUTPUT_DIR.glob("*.part"):
        logging.warning("Removing orphaned .part file: %s", part_file.name)
        part_file.unlink()

    return completed, failed
```

- [ ] **Step 4: Wire monitoring into the main loop**

**CRITICAL (from council review):** The memory check MUST be placed AFTER the
`for future in done_set:` loop completes, NOT inside it. Placing it inside
means a throttle `break` would skip processing remaining completed futures,
losing their progress. Also, the `break` must exit the inner `while` loop (not
just the `for` loop), and after throttle teardown set `pool = None` to prevent
the `finally` block from double-shutting-down the pool.

Also: replace the single blocking `wait()` with a polling loop that checks the
background shutdown flag every 5 seconds, so ceiling shutdown isn't delayed up
to 10 minutes.

In `run_supervised`, replace the `wait()` call and the `for future in done_set`
processing section with:

```python
                # Poll with 5s timeout to check background shutdown flag frequently
                deadline = time.monotonic() + timeout
                done_set = set()
                while time.monotonic() < deadline:
                    done_set, _pending = wait(
                        futures.keys(), timeout=5.0, return_when=FIRST_COMPLETED
                    )
                    if done_set or bg_shutdown_flag[0] or shutdown_requested:
                        break

                if bg_shutdown_flag[0]:
                    logging.error("Background monitor requested shutdown.")
                    shutdown_requested = True
                    # Still process any completed futures below before exiting

                if not done_set and not bg_shutdown_flag[0]:
                    # True timeout — no future completed in `timeout` seconds
                    # ... existing timeout handling (unchanged) ...

                # Measure memory ONCE for this batch
                mem_gb = get_total_python_rss_gb(pool)
                peak_memory_gb = max(peak_memory_gb, mem_gb)

                # Process ALL completed futures first (no break inside this loop)
                for future in done_set:
                    args = futures.pop(future)
                    storage_key = args[0]

                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {
                            "status": "failed",
                            "storage_key": storage_key,
                            "page_count": 0,
                            "elapsed_s": 0,
                            "file_size_mb": 0,
                            "error": f"{type(exc).__name__}: {exc}",
                        }

                    # ... existing result tracking + logging (unchanged) ...

                    write_progress(result, memory_gb=mem_gb, workers=current_max_workers)

                # Update refs for background watchdog
                completed_ref[0] = completed
                remaining_ref[0] = len(remaining)
                workers_ref[0] = current_max_workers

                # NOW evaluate thresholds (after all futures processed)
                need_throttle = False
                if mem_gb > memory_ceiling_gb:
                    logging.error(
                        "CEILING: Memory %.1f GB > %.1f GB. Graceful shutdown.",
                        mem_gb, memory_ceiling_gb,
                    )
                    shutdown_requested = True
                elif mem_gb > memory_throttle_gb:
                    logging.warning(
                        "THROTTLE: Memory %.1f GB > %.1f GB. Reducing workers %d -> %d.",
                        mem_gb, memory_throttle_gb,
                        current_max_workers, max(current_max_workers - 1, 1),
                    )
                    if current_max_workers <= 1:
                        logging.error("Already at 1 worker. Shutting down.")
                        shutdown_requested = True
                    else:
                        need_throttle = True
                elif mem_gb > memory_info_gb:
                    logging.info(
                        "MEMORY INFO: %.1f GB (threshold %.1f GB)", mem_gb, memory_info_gb
                    )

                if need_throttle:
                    throttle_events += 1
                    tc, tf = _throttle_teardown(
                        pool, futures, remaining, crash_counts, watchdog_stop
                    )
                    completed += tc
                    failed += tf
                    current_max_workers -= 1
                    pool = None  # Prevent finally block from double-shutdown
                    break  # Break inner while loop → outer loop creates new smaller pool
```

- [ ] **Step 5: Background shutdown flag is already handled in Step 4**

The polling loop in Step 4 already checks `bg_shutdown_flag[0]` every 5 seconds
and sets `shutdown_requested = True` when triggered. No separate step needed.

Note: `bg_shutdown_flag` is defined as `[False]` (mutable list) in Step 1. This
is the ONLY definition — do not use a plain boolean.

- [ ] **Step 6: Start background monitor when pool is created**

After `pool = ProcessPoolExecutor(...)` (line 285), add:

```python
            completed_ref = [completed]
            remaining_ref = [len(remaining)]
            workers_ref = [current_max_workers]
            heartbeat_path = OUTPUT_DIR / "_heartbeat.json"
            watchdog_stop = _start_memory_watchdog(
                pool,
                memory_ceiling_gb,
                heartbeat_path,
                bg_shutdown_flag,
                completed_ref,
                remaining_ref,
                workers_ref,
            )
```

The `watchdog_stop` event is passed to `_throttle_teardown` in Step 4 and
must be `.set()` in the `finally` block before pool cleanup:

```python
        finally:
            # Cancel background watchdog BEFORE touching the pool
            if watchdog_stop is not None:
                watchdog_stop.set()
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)
                import contextlib
                for pid in list(pool._processes or []):
                    with contextlib.suppress(ProcessLookupError, OSError):
                        os.kill(pid, signal.SIGTERM)
```

Ref updates are already handled in Step 4 after the `for` loop.

- [ ] **Step 7: Update pool creation in outer loop to use `current_max_workers`**

Change line 285:

```python
            pool = ProcessPoolExecutor(
                max_workers=current_max_workers,
                max_tasks_per_child=max_tasks_per_child,
            )
```

Also update `batch_size` to be dynamic:

```python
                batch_size = current_max_workers * 2
```

- [ ] **Step 8: Update progress logging to include new fields**

In `write_progress`, update to accept and log memory:

```python
def write_progress(result: dict, memory_gb: float = 0.0, workers: int = 0) -> None:
    """Append a progress entry (advisory, not for correctness)."""
    entry = {
        **result,
        "memory_gb": round(memory_gb, 1),
        "workers": workers,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    line = json.dumps(entry) + "\n"
    with PROGRESS_LOG.open("a") as f:
        f.write(line)
        f.flush()
```

Update all call sites to pass memory and workers:

```python
                    write_progress(result, memory_gb=mem_gb, workers=current_max_workers)
```

For calls where memory isn't available (prewarm, error paths), pass 0.

- [ ] **Step 9: Add `file_size_mb` to progress entries**

In the `process_one_pdf` function, calculate file size BEFORE the try block
(so it's available in both success and error paths):

```python
    storage_key, pdf_path_str = args
    pdf_path = Path(pdf_path_str)
    start = time.monotonic()
    file_size_mb = round(pdf_path.stat().st_size / (1024 * 1024), 1)

    try:
        # ... existing code ...

        return {
            "status": "success",
            "storage_key": storage_key,
            "page_count": page_count,
            "elapsed_s": round(elapsed, 1),
            "file_size_mb": file_size_mb,
            "error": None,
        }

    except Exception as exc:
        elapsed = time.monotonic() - start
        is_mps_error = "MPS" in str(exc) or "Metal" in str(exc)

        return {
            "status": "mps_error" if is_mps_error else "failed",
            "storage_key": storage_key,
            "page_count": 0,
            "elapsed_s": round(elapsed, 1),
            "file_size_mb": file_size_mb,
            "error": f"{type(exc).__name__}: {exc}",
        }
```

- [ ] **Step 10: Update summary JSON with new fields**

In the summary dict at the end of `run_supervised`:

```python
    summary = {
        "total": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "pool_restarts": pool_restarts,
        "throttle_events": throttle_events,
        "peak_memory_gb": round(peak_memory_gb, 1),
        "elapsed_s": round(elapsed_total, 1),
        "elapsed_human": f"{elapsed_total / 3600:.1f}h",
        "shutdown_requested": shutdown_requested,
        "finished_at": datetime.now(UTC).isoformat(),
    }
```

- [ ] **Step 11: Run lint and format**

Run: `uv run ruff check scripts/docling_reparse.py && uv run ruff format scripts/docling_reparse.py`
Expected: clean (fix any issues)

- [ ] **Step 12: Commit**

```bash
git add scripts/docling_reparse.py
git commit -m "feat: memory monitoring with adaptive throttling and background watchdog thread"
```

---

### Task 7: Update `parse_status.sh` with memory reporting

**Files:**
- Modify: `scripts/parse_status.sh`

- [ ] **Step 1: Add memory section after the "Status" block**

After the process-running check (line 25), insert:

```bash
# Memory usage (pure shell — no Python/psutil)
PIDS=$(pgrep -f "docling_reparse.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "=== Memory ==="
    TOTAL_KB=0
    while IFS= read -r pid; do
        RSS_KB=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
        if [ -n "$RSS_KB" ] && [ "$RSS_KB" -gt 0 ]; then
            RSS_GB=$(echo "scale=1; $RSS_KB / 1048576" | bc)
            CMDLINE=$(ps -o command= -p "$pid" 2>/dev/null | head -c 60)
            echo "  PID $pid: ${RSS_GB} GB  ($CMDLINE)"
            TOTAL_KB=$((TOTAL_KB + RSS_KB))
        fi
    done <<< "$PIDS"

    # Also check python3.12 children (worker processes)
    WORKER_PIDS=$(pgrep -P "$(echo "$PIDS" | head -1)" 2>/dev/null)
    if [ -n "$WORKER_PIDS" ]; then
        while IFS= read -r pid; do
            RSS_KB=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
            if [ -n "$RSS_KB" ] && [ "$RSS_KB" -gt 0 ]; then
                RSS_GB=$(echo "scale=1; $RSS_KB / 1048576" | bc)
                echo "  PID $pid: ${RSS_GB} GB  (worker)"
                TOTAL_KB=$((TOTAL_KB + RSS_KB))
            fi
        done <<< "$WORKER_PIDS"
    fi

    TOTAL_GB=$(echo "scale=1; $TOTAL_KB / 1048576" | bc)
    SYS_MEM_GB=64

    # Color-code: green <24, yellow 24-36, red >36
    if [ "$(echo "$TOTAL_GB > 36" | bc)" -eq 1 ]; then
        COLOR="\033[31m"  # Red
    elif [ "$(echo "$TOTAL_GB > 24" | bc)" -eq 1 ]; then
        COLOR="\033[33m"  # Yellow
    else
        COLOR="\033[32m"  # Green
    fi
    RESET="\033[0m"
    echo -e "  Total: ${COLOR}${TOTAL_GB} GB${RESET} / ${SYS_MEM_GB} GB"

    # Memory trend from progress log
    if [ -f "$PROGRESS" ]; then
        RECENT_MEM=$(tail -1 "$PROGRESS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('memory_gb','?'))" 2>/dev/null || echo "?")
        OLDER_MEM=$(tail -50 "$PROGRESS" | head -1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('memory_gb','?'))" 2>/dev/null || echo "?")
        echo "  Trend: ${OLDER_MEM} GB (50 docs ago) -> ${RECENT_MEM} GB (latest)"
    fi
    echo ""
fi
```

- [ ] **Step 2: Add heartbeat info if available**

After the memory section:

```bash
# Heartbeat
HEARTBEAT="$DIR/data/parsed_docling/_heartbeat.json"
if [ -f "$HEARTBEAT" ]; then
    echo "=== Heartbeat ==="
    python3 -c "
import json
with open('$HEARTBEAT') as f:
    h = json.load(f)
print(f\"  Workers: {h.get('workers', '?')}\")
print(f\"  Memory: {h.get('memory_gb', '?')} GB\")
print(f\"  Completed: {h.get('completed', '?')}\")
print(f\"  Remaining: {h.get('remaining', '?')}\")
print(f\"  Updated: {h.get('timestamp', '?')}\")
" 2>/dev/null
    echo ""
fi
```

- [ ] **Step 3: Test the script**

Run: `bash scripts/parse_status.sh`
Expected: runs without errors, shows memory section if parse is running

- [ ] **Step 4: Commit**

```bash
git add scripts/parse_status.sh
git commit -m "feat: add per-worker memory reporting and trend to parse_status.sh"
```

---

### Task 8: Update `parse_watchdog.sh` with heartbeat reading

**Files:**
- Modify: `scripts/parse_watchdog.sh`

- [ ] **Step 1: Add heartbeat-based stall detection**

Replace the ENTIRE process-running block (lines 21-50) with heartbeat-based
observability. **Per the spec, the watchdog is observability-only — remove the
auto-kill/restart logic** to prevent the watchdog from killing a healthy
throttled-down supervisor:

```bash
    # Process running — check if it's making progress
    HEARTBEAT="$DIR/data/parsed_docling/_heartbeat.json"
    if [ -f "$HEARTBEAT" ]; then
        # Prefer heartbeat file (written every 30s by background monitor)
        HEARTBEAT_AGE=$(python3 -c "
import json
from datetime import datetime, UTC
try:
    with open('$HEARTBEAT') as f:
        h = json.load(f)
    ts = h.get('timestamp', '')
    dt = datetime.fromisoformat(ts)
    age = (datetime.now(UTC) - dt).total_seconds()
    print(int(age))
except:
    print(9999)
" 2>/dev/null)

        WORKERS=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('workers', '?'))" 2>/dev/null || echo "?")
        MEM_GB=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('memory_gb', '?'))" 2>/dev/null || echo "?")

        if [ "$HEARTBEAT_AGE" -gt 120 ]; then
            # Heartbeat stale for >2 minutes — background thread may be dead
            echo "[$(date)] WARNING: Heartbeat stale (${HEARTBEAT_AGE}s). Checking progress log..." >> "$WATCHDOG_LOG"
            # Fall through to progress log check below
        else
            DONE=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('completed', '?'))" 2>/dev/null || echo "?")
            REMAIN=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('remaining', '?'))" 2>/dev/null || echo "?")
            echo "[$(date)] Running OK. Workers=$WORKERS, Mem=${MEM_GB}GB, Done=$DONE, Remaining=$REMAIN. Heartbeat ${HEARTBEAT_AGE}s ago." >> "$WATCHDOG_LOG"
            exit 0
        fi
    fi

    # Fallback: check progress log (original logic)
    if [ -f "$PROGRESS" ]; then
```

- [ ] **Step 2: Add RSS check to watchdog**

Before the stall-detection restart logic (line 38), add:

```bash
        # Check total memory via ps
        TOTAL_RSS_KB=0
        for pid in $(pgrep -f "docling_reparse.py" 2>/dev/null) $(pgrep -f "python.*process" 2>/dev/null); do
            RSS=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
            [ -n "$RSS" ] && TOTAL_RSS_KB=$((TOTAL_RSS_KB + RSS))
        done
        TOTAL_RSS_GB=$(echo "scale=1; $TOTAL_RSS_KB / 1048576" | bc)
        if [ "$(echo "$TOTAL_RSS_GB > 40" | bc)" -eq 1 ]; then
            echo "[$(date)] WARNING: High memory usage: ${TOTAL_RSS_GB} GB" >> "$WATCHDOG_LOG"
        fi
```

- [ ] **Step 3: Test the script**

Run: `bash scripts/parse_watchdog.sh`
Expected: runs without errors, logs to `/tmp/watchdog.log`

- [ ] **Step 4: Commit**

```bash
git add scripts/parse_watchdog.sh
git commit -m "feat: watchdog reads heartbeat file, checks RSS via ps"
```

---

### Task 9: Lint, type-check, and run existing tests

**Files:** All modified files

- [ ] **Step 1: Ruff lint**

Run: `uv run ruff check scripts/ tests/`
Expected: no new errors. Fix any issues.

- [ ] **Step 2: Ruff format**

Run: `uv run ruff format --check scripts/ tests/`
Expected: clean. If not, run `uv run ruff format scripts/ tests/`.

- [ ] **Step 3: Pyright**

Run: `uv run pyright scripts/docling_reparse.py tests/test_memory_monitor.py`
Expected: no new errors (pre-existing errors in other files are OK)

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: all tests pass including new `test_memory_monitor.py`

- [ ] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: lint and type-check fixes for memory monitoring"
```

---

### Task 10: Soak test and forced-threshold tests

**Files:** None (testing only)

- [ ] **Step 1: Forced-ceiling test**

Run with a very low ceiling to verify graceful shutdown:

```bash
uv run python scripts/docling_reparse.py --workers 2 --limit 5 --memory-ceiling 0.001 --memory-throttle 0.0005
```

Expected: starts, detects memory > 0.001 GB immediately, logs "CEILING" or
"BACKGROUND MONITOR" message, writes summary, exits cleanly.

- [ ] **Step 2: Verify resume after forced shutdown**

Run the same command again:

```bash
uv run python scripts/docling_reparse.py --workers 2 --limit 5 --memory-ceiling 0.001 --memory-throttle 0.0005
```

Expected: detects completed docs from Step 1, skips them, shuts down again.
The key check: no duplicate output files, no corruption.

- [ ] **Step 3: Forced-throttle test**

```bash
uv run python scripts/docling_reparse.py --workers 4 --limit 10 --memory-throttle 0.001 --memory-ceiling 100
```

Expected: starts with 4 workers, immediately hits throttle, reduces to 3, then
2, then 1, then shuts down (since 1 worker at throttle = shutdown). Check logs
for "THROTTLE" messages with decreasing worker counts.

- [ ] **Step 4: Soak test with real large documents**

**NOTE:** `--limit 50` with smallest-first sorting will process the 50 smallest
docs, which is NOT representative for memory testing. Instead, run without
`--limit` but set a low timeout to cap wall-clock time, and monitor memory
manually. Alternatively, temporarily disable sorting for this test.

```bash
# Run 20 minutes of real parsing (no limit), watch memory
timeout 1200 uv run python scripts/docling_reparse.py --workers 4 --timeout 900
```

In a separate terminal, monitor memory:
```bash
watch -n 30 bash scripts/parse_status.sh
```

Expected: memory stays bounded (under 24 GB with default thresholds), workers
get recycled after 10 docs each, heartbeat file updates every 30s. Check
`data/parsed_docling/_progress.jsonl` — `memory_gb` values should trend flat
(not monotonically increasing).

- [ ] **Step 5: Verify status script reads new data**

Run: `bash scripts/parse_status.sh`
Expected: shows memory section with per-worker RSS, heartbeat data, trend.

- [ ] **Step 6: Commit any remaining fixes**

```bash
git add -u
git commit -m "test: verify memory monitoring with forced threshold and soak tests"
```

---

### Task 11: Final review and prep for overnight run

- [ ] **Step 1: Run full verification suite**

```bash
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/ scripts/
uv run pyright src/ tests/
uv run pytest -v
```

- [ ] **Step 2: Check remaining document count**

```bash
uv run python -c "
from scripts.docling_reparse import discover_pdfs, filter_already_done
all_pdfs = discover_pdfs()
remaining = filter_already_done(all_pdfs)
print(f'Total: {len(all_pdfs)}, Remaining: {len(remaining)}, Done: {len(all_pdfs) - len(remaining)}')
"
```

- [ ] **Step 3: Verify caffeinate is running**

```bash
pgrep caffeinate && echo "caffeinate running" || echo "START CAFFEINATE"
```

- [ ] **Step 4: Start the overnight run**

```bash
caffeinate -d -i -s uv run python scripts/docling_reparse.py \
  --workers 4 --timeout 900 \
  >> /tmp/docling_overnight.log 2>&1 &
echo "Started PID $!"
```

- [ ] **Step 5: Verify it's running and making progress**

Wait 2-3 minutes, then:

```bash
bash scripts/parse_status.sh
```

Expected: shows RUNNING, memory reasonable, first few docs completing.
