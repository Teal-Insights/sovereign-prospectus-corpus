# Docling Re-Parse Runbook

Lessons learned from the March 28, 2026 bulk re-parse of 1,468 sovereign bond
prospectus PDFs using Docling on a Mac Mini M4 Pro, coordinated across two
machines sharing a Dropbox folder.

**Final result: 1,468 documents, 74,378 pages, 0 failures, 3.9 hours.**

---

## Part 1: Docling in General

### What Docling does

Docling is a document understanding library that converts PDFs into structured
output (Markdown, JSONL) using deep learning models for layout detection, table
structure recognition, and OCR. It replaces simpler text-extraction tools like
PyMuPDF when you need document structure (headings, tables, sections) not just
raw text.

### Key dependencies

Docling pulls in a large dependency tree (~104 packages) including:

- **PyTorch** (76.9 MiB) — the ML runtime
- **torchvision** — vision model support
- **transformers / huggingface-hub** — model downloading
- **docling-parse** — native PDF parsing layer
- **docling-ibm-models** — IBM's layout and table models
- **ocrmac** — macOS-native OCR (auto-selected on Apple Silicon)

Expect the initial `uv add docling` to take 1-2 minutes even on fast internet
due to the PyTorch wheel alone.

### Python version compatibility

As of March 2026, Docling's dependency resolution **stalls indefinitely on
Python 3.14**. The `concurrent.futures.BrokenProcessPool` export also moved
between 3.12 and 3.13 (it's at `concurrent.futures.process.BrokenProcessPool`
in 3.12). **Use Python 3.12 for production Docling runs.** Pin it:

```bash
uv python install 3.12
uv venv --python 3.12
```

### Model warm-up cost

The first document Docling processes in a process triggers model loading:

- Layout detection model download/load (~5s)
- Table structure model download/load (~13s)
- OCR engine selection (~5s)

Our script handles this with a **prewarm step** — process one document
single-threaded before launching the parallel pool. This prevents all workers
from fighting over model loading simultaneously.

### Environment variables

| Variable | Purpose | Recommended |
|---|---|---|
| `DOCLING_DEVICE` | Accelerator: `auto`, `mps`, `cpu` | `auto` (selects MPS on Apple Silicon) |
| `DOCLING_NUM_THREADS` | CPU threads per worker | `3` for 4-worker setup on 14-core M4 Pro |

### Output formats

Docling produces:

- **Markdown** (`.md`) — preserves headings, tables, lists. Best for human
  review and LLM consumption.
- **Plain text JSONL** (`.jsonl`) — one header record + one record per page
  with `page`, `text`, `char_count`. Best for grep-first clause finding.

The JSONL format strips markdown formatting so regex patterns work cleanly.

### Error modes

| Error | Cause | Handling |
|---|---|---|
| MPS/Metal errors | GPU memory pressure with parallel workers | Auto-fallback to CPU after 3 MPS errors |
| Timeout (>300s) | Extremely large or complex PDFs | Logged as `skipped`, not `failed` |
| `BrokenProcessPool` | Worker process crash (segfault in native code) | Auto pool restart, up to 10 times |
| Empty pages | Scanned PDFs with no text layer | `parse_empty` status in JSONL header |

### Verbatim extraction matters

Docling's markdown can reformat text (merge lines, restructure tables). For
our use case (verbatim clause extraction with `assert exact_quote in
raw_pdf_text`), we keep both the markdown and the stripped plain text. The
plain text JSONL is the source of truth for clause matching; the markdown is
for human review.

---

## Part 2: Running on the Mac Mini M4 Pro

### Hardware profile

| Spec | Value |
|---|---|
| Chip | Apple M4 Pro |
| CPU | 14 cores (10P + 4E) |
| GPU | 20-core, Metal 4 |
| RAM | 64 GB unified memory |
| Storage | 1.8 TB SSD (1.2 TB free) |

### Final run results (1,468 PDFs, March 28, 2026)

| Metric | Value |
|---|---|
| Total documents | 1,468 |
| Total pages | 74,378 |
| Success rate | **100%** (1,468/1,468) |
| Failures | 0 |
| Skipped | 0 |
| Pool restarts | 0 |
| Wall clock time | 3.9 hours |
| Overall rate | 1.31 pages/second |

#### Throughput by document size

| Bucket | Docs | Pages | Pages/sec | Sec/page |
|---|---|---|---|---|
| Small (1-10 pages) | 601 | 3,131 | 0.82 | 1.22 |
| Medium (11-50 pages) | 482 | 11,335 | 1.11 | 0.90 |
| Large (50+ pages) | 385 | 59,912 | 1.40 | 0.71 |

#### Timing distribution

| Stat | Elapsed (sec) | Pages |
|---|---|---|
| Min | 0.8 | 0 |
| Median | 12.1 | 15 |
| Mean | 38.7 | 51 |
| Max | 804.5 | 589 |

Large documents are more efficient per-page because model loading and pipeline
initialization are amortized. The corpus is dominated by large docs (385 docs
account for 59,912 of 74,378 total pages — 81%). The sweet spot for throughput
is large batch runs, not one-off conversions.

### Worker configuration

With 14 CPU cores and MPS GPU acceleration:

- **4 workers** is the sweet spot. Each worker gets ~3 CPU threads
  (`DOCLING_NUM_THREADS=3`), leaving 2 cores for the OS and the supervisor
  process.
- Going above 4 workers risks MPS contention — all workers share the same GPU.
- The GPU (MPS) handles layout detection and table structure; CPU handles OCR
  and text extraction.

### Recommended launch command

```bash
export UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus
export DOCLING_DEVICE=auto
export DOCLING_NUM_THREADS=3

# Test with 1 doc first
uv run python3 scripts/docling_reparse.py --workers 1 --limit 1

# Full run, backgrounded
nohup uv run python3 scripts/docling_reparse.py --workers 4 \
  > data/parsed_docling/_stdout.log 2>&1 &
echo "Started PID $!. Monitor: tail -f data/parsed_docling/_stdout.log"
```

### Monitoring a running job

```bash
# Live log
tail -f data/parsed_docling/_stdout.log

# Document count
wc -l data/parsed_docling/_progress.jsonl

# Errors only
cat data/parsed_docling/_errors.log

# Final summary (written on completion)
cat data/parsed_docling/_summary.json
```

### Resilience features

The script is designed for unattended multi-hour runs:

1. **Resume support** — checks for existing `.jsonl` output files on startup
   and skips them. Safe to kill and restart.
2. **Graceful shutdown** — catches SIGTERM/SIGINT, finishes current documents
   before exiting.
3. **Supervised pool** — `BrokenProcessPool` exceptions trigger automatic pool
   restart (up to 10 times).
4. **Per-document timeout** — 300s default, prevents one bad PDF from blocking
   the pipeline.
5. **Disk space check** — every 50 documents, stops if <1 GB free.
6. **MPS fallback** — after 3 GPU errors, switches to CPU for remaining docs.
7. **Atomic writes** — `.part` file renamed on completion, so partial files
   never appear as "done" on resume.

---

## Part 3: Multi-Machine Workflow with Dropbox

### The setup

Two machines share the same git repo and data directory via Dropbox:

| Machine | Role | Specs |
|---|---|---|
| Mac Mini M4 Pro | Heavy compute (parsing, ML) | 14-core, 64 GB, always-on |
| MacBook Air | Development, code review | Portable, intermittent |

### The fundamental tension

Dropbox syncs everything in real time. This is great for sharing PDFs and code,
but terrible for:

- **Virtual environments** — thousands of small files, platform-specific
  binaries, symlinks that point to machine-local paths
- **Git lock files** — `index.lock` gets synced mid-operation, causing
  "another git process" errors
- **Large intermediate outputs** — model weights, `.part` files during writes

### Rule 1: Virtual environments live outside Dropbox

Never create `.venv` inside a Dropbox-synced directory. Dropbox will:

- Lock files during sync, causing `Operation timed out (os error 60)`
- Resurrect deleted directories from the other machine's sync
- Corrupt platform-specific `.so`/`.dylib` files between ARM Macs

**Solution:** Create the venv in a machine-local directory:

```bash
mkdir -p ~/.local/venvs
uv venv --python 3.12 ~/.local/venvs/sovereign-corpus
export UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus
```

Each machine maintains its own venv. The `pyproject.toml` and `uv.lock` in
Dropbox are the shared contract; each machine runs `uv sync` independently.

### Rule 2: Don't overlap git operations

Dropbox syncs the `.git` directory. If both machines run git commands
simultaneously, you get corrupted index files and stale lock files.

**Protocol:**
- Only one machine does git operations at a time
- If you see `index.lock` errors, check if the other machine is running git
- Stale lock files (from crashed git): safe to `rm .git/index.lock`
- Dropbox-resurrected lock files: wait for sync to settle, or pause Dropbox

### Rule 3: Coordinate via SESSION-HANDOFF.md

The project already uses `SESSION-HANDOFF.md` for task handoff. When switching
machines:

1. On the departing machine: update `SESSION-HANDOFF.md` with current state
2. On the arriving machine: `git pull`, read `SESSION-HANDOFF.md`
3. Set up the local venv if needed: `uv sync` with `UV_PROJECT_ENVIRONMENT`

### Rule 4: Data files are Dropbox's strength

PDFs in `data/original/`, `data/pdfs/`, and parsed output in
`data/parsed_docling/` sync naturally via Dropbox. The atomic write pattern
(`.part` -> rename) means the other machine never sees half-written files.

This is actually an advantage: start a parse job on the Mac Mini, and the
MacBook Air can read results as they appear via Dropbox sync.

### Recommended .gitignore additions

The project already ignores `data/` and `.venv`. Consider also adding to
Dropbox's selective sync exclusions (via Dropbox preferences):

- `.venv/` — if it accidentally gets created in-repo
- `__pycache__/` — regenerated per-machine
- `*.egg-info/` — build artifacts

---

## Part 4: Autonomous Operation with `--dangerously-skip-permissions`

### Why the Mac Mini runs autonomously

The Mac Mini is the "workhorse" — it runs long compute jobs (4-5 hour PDF
parses, model inference) unattended. Claude Code with
`--dangerously-skip-permissions` lets it execute the full task workflow without
waiting for human approval at each step.

### Safety guardrails already in place

1. **Atomic file writes** — the parsing script uses `.part` -> `os.replace()`
   for all output. A killed process never leaves corrupt files.

2. **Resume support** — every script checks for existing output before
   processing. Safe to restart after crashes, power loss, or manual kills.

3. **Graceful shutdown** — SIGTERM/SIGINT handlers finish current work before
   exiting. `kill <pid>` does the right thing.

4. **Bounded resource usage** — worker count and thread count are configured,
   not unbounded. Disk space checks prevent filling the drive.

5. **Append-only telemetry** — `_progress.jsonl` and `_errors.log` are
   append-only. Even if the main process dies, you have a record of everything
   it did.

6. **No destructive git operations** — the CLAUDE.md explicitly forbids
   `--force`, `--hard`, etc. without user confirmation. Autonomous mode runs
   code and pipelines, not destructive git commands.

7. **Data directory is gitignored** — `data/` is in `.gitignore`. Even if
   something goes wrong with parsing output, it can't accidentally get
   committed and pushed.

8. **Circuit breakers** — pool restart limit (10), MPS error threshold (3),
   disk space floor (1 GB), per-document timeout (300s). The script stops
   itself rather than thrashing.

### What to verify before leaving it unattended

```bash
# 1. Correct branch
git branch --show-current

# 2. Venv is outside Dropbox
echo $UV_PROJECT_ENVIRONMENT  # should be ~/.local/venvs/...

# 3. Enough disk space
df -h .  # >10 GB free recommended

# 4. Test one document first
uv run python3 scripts/docling_reparse.py --workers 1 --limit 1

# 5. Check the test worked
ls -la data/parsed_docling/*.md | head -3

# 6. Launch and verify it's running
nohup uv run python3 scripts/docling_reparse.py --workers 4 \
  > data/parsed_docling/_stdout.log 2>&1 &
sleep 10 && tail -5 data/parsed_docling/_stdout.log
```

### Monitoring from the MacBook Air

Since output lands in Dropbox, you can monitor from the other machine:

```bash
# Watch progress (synced via Dropbox with ~30s delay)
tail -f data/parsed_docling/_stdout.log

# Quick status check
wc -l data/parsed_docling/_progress.jsonl
cat data/parsed_docling/_errors.log
```

Or SSH into the Mac Mini for real-time monitoring if Dropbox lag is too slow.

### Recovery playbook

| Scenario | Action |
|---|---|
| Process died | Just restart — resume support skips completed docs |
| Mac Mini rebooted | Re-export env vars, restart the script |
| Dropbox conflict files | Delete `*.conflicted*` copies, keep originals |
| Git index.lock stuck | `rm .git/index.lock` (check other machine first) |
| MPS errors in log | Script auto-falls back to CPU; no action needed |
| Disk full | Script auto-stops at <1 GB; free space and restart |

---

## Part 5: Troubleshooting Log — March 28, 2026 Setup

This section documents every issue encountered when setting up and launching
the Docling re-parse on the Mac Mini, with root causes and solutions. These
are the kinds of problems to expect when two machines share a Dropbox-synced
git repo with virtualenvs.

### Issue 1: Python 3.14 stalls Docling dependency resolution

**Symptom:** `uv add docling` hung for 2+ minutes showing only
`Using CPython 3.14.3` — no progress, no error.

**Root cause:** The Mac Mini only had Python 3.14.3 and 3.9.6 installed.
Docling's dependency tree (especially PyTorch) didn't have resolved wheels for
3.14 yet, so uv's resolver looped indefinitely.

**Fix:**
```bash
uv python install 3.12
uv venv --python 3.12 ~/.local/venvs/sovereign-corpus
export UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus
uv add docling  # completes in ~8 seconds
```

**Prevention:** Pin Python 3.12 for this project. Consider adding a
`.python-version` file to the repo root so uv selects it automatically.

### Issue 2: Dropbox locks prevent venv deletion

**Symptom:** After the stalled `uv add` left a broken `.venv` in the
Dropbox-synced directory, every attempt to remove it failed:

- `rm -rf .venv` — hung, then partially deleted (left `lib/` and `share/`)
- `uv venv --clear` — failed with `Operation timed out (os error 60)`
- `mv .venv /tmp/` — appeared to succeed but Dropbox **resurrected** the
  directory from the MacBook Air's synced copy

**Root cause:** Dropbox holds file locks on synced directories. When the
MacBook Air still has a `.venv`, Dropbox re-syncs it to the Mac Mini even
after deletion. The `.venv` contained platform-specific symlinks pointing to
the MacBook Air's Python installation, so even if it synced successfully, it
wouldn't work.

**Fix:** Abandon the in-repo `.venv` entirely. Create the venv outside
Dropbox:

```bash
mkdir -p ~/.local/venvs
uv venv --python 3.12 ~/.local/venvs/sovereign-corpus
export UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus
```

**The ghost `.venv`:** The Dropbox-synced `.venv` directory may linger
indefinitely in the repo. It's harmless — `UV_PROJECT_ENVIRONMENT` overrides
it completely. Don't waste time fighting Dropbox to remove it.

**Prevention:** Both machines should use `UV_PROJECT_ENVIRONMENT` pointing
to a machine-local path. Never run `uv venv` inside the Dropbox directory.

### Issue 3: Git index.lock from Dropbox sync

**Symptom:** `git checkout feature/30-docling-reparse` failed with:
```
fatal: Unable to create '.git/index.lock': File exists.
Another git process seems to be running in this repository
```

**Root cause:** The MacBook Air had recently run git commands. Dropbox synced
the `.git/index.lock` file (or a transient lock from the stash operation
collided with Dropbox's sync).

**Fix:** Remove the stale lock and retry:
```bash
rm .git/index.lock
git checkout feature/30-docling-reparse
```

The second `git checkout` then failed with `fatal: unable to write new index
file` — likely Dropbox was still syncing the `.git` directory. Waiting a few
seconds and retrying succeeded.

**Prevention:** Don't run git on both machines simultaneously. If switching
machines, wait for Dropbox sync to settle (~30 seconds) before running git
commands. Consider pausing Dropbox sync during intensive git operations.

### Issue 4: BrokenProcessPool import path differs by Python version

**Symptom:** First test run failed with:
```
ImportError: cannot import name 'BrokenProcessPool' from 'concurrent.futures'
```

**Root cause:** The script was written on the MacBook Air using Python 3.13+,
where `BrokenProcessPool` is exported at the top level of
`concurrent.futures`. In Python 3.12, it's only available at
`concurrent.futures.process.BrokenProcessPool`.

**Fix:**
```python
# Before (3.13+ only):
from concurrent.futures import BrokenProcessPool, ProcessPoolExecutor, as_completed

# After (3.12 compatible):
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
```

**Prevention:** Test on the target Python version before committing. The
MacBook Air may have a different Python version than the Mac Mini.

### Summary: The Dropbox + dual-machine workflow

The core problem is that Dropbox tries to make two machines look identical, but
Python development requires machine-local state (venvs, compiled extensions,
`.pyc` files, Python version). The solution is to clearly separate what Dropbox
should sync from what must be machine-local:

| Dropbox syncs (shared) | Machine-local (not synced) |
|---|---|
| Source code (`src/`, `scripts/`, `tests/`) | Virtual environments (`~/.local/venvs/`) |
| Config files (`pyproject.toml`, `uv.lock`) | `__pycache__/`, `.pyc` files |
| Data files (`data/original/`, `data/parsed*/`) | Model weights (`~/.cache/huggingface/`) |
| Documentation (`docs/`) | `.git/index.lock` (transient) |
| Git history (`.git/` minus locks) | Build artifacts (`*.egg-info/`) |

**Ideal workflow for dual-machine long-running compute:**

1. **MacBook Air:** Write code, commit, push to branch
2. **Mac Mini:** Pull branch, set up local venv (`UV_PROJECT_ENVIRONMENT`),
   test one doc, launch background job
3. **While running:** MacBook Air can read output via Dropbox, but should
   NOT run git commands or modify files that the Mac Mini is using
4. **After completion:** Mac Mini commits results/code changes, pushes.
   MacBook Air pulls.

**Potential improvements to investigate:**

- Add `.python-version` file to repo (ensures uv picks 3.12 everywhere)
- Add `UV_PROJECT_ENVIRONMENT` to a machine-local `.env` file (not synced)
- Exclude `.venv/` and `__pycache__/` from Dropbox sync via Dropbox
  selective sync settings
- Consider excluding `.git/` from Dropbox entirely and using a bare git
  remote (e.g., GitHub) as the sync mechanism instead — this would eliminate
  all git lock file issues, at the cost of requiring explicit push/pull
