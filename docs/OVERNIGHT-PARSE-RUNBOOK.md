# Overnight Docling Parse Runbook

A single document covering everything needed to run a Docling PDF parsing job
on any Mac. Designed for unattended overnight execution with full resilience.

**Last validated:** 2026-04-12 (5,400+ docs on Mac Mini M4 Pro, 64 GB)

---

## Quick Start (experienced operators)

```bash
# 1. Pre-flight
uv run python scripts/verify_parse_environment.py

# 2. Launch (uses auto-detected config)
caffeinate -d -i -s uv run python scripts/docling_reparse.py \
  --workers 4 --timeout 900 \
  >> /tmp/docling_overnight.log 2>&1 &

# 3. Monitor
watch -n 60 bash scripts/parse_status.sh

# 4. Morning validation
uv run python scripts/validate_parse_output.py
```

---

## Before You Start

### 1. Run the pre-flight check

```bash
uv run python scripts/verify_parse_environment.py
```

This verifies:
- Python 3.12.x (required for Docling)
- Venv is outside Dropbox (avoids file lock issues)
- All dependencies installed (docling, psutil, etc.)
- Memory-fix code present (max_tasks_per_child, monitoring, throttle)
- Disk space >10 GB
- PDF source directories have files
- No conflicting Docling processes already running
- Auto-detects hardware and recommends worker/memory configuration

**Fix all FAILUREs before proceeding. WARNINGs are advisory.**

### 2. Environment setup (first time on a new machine)

```bash
# Set canonical venv location outside Dropbox
echo 'export UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus' >> ~/.zshrc
source ~/.zshrc

# Install dependencies
uv sync --all-extras

# Verify Docling works
uv run python -c "from docling.document_converter import DocumentConverter; print('OK')"
```

### 3. Pre-launch checklist

- [ ] Pre-flight script passes (all green or warnings-only)
- [ ] No other heavy ML jobs running (`pgrep -f torch; pgrep -f docling`)
- [ ] Dropbox is synced (no pending uploads in output directory)
- [ ] Terminal will stay open (use `tmux` or `screen` for SSH sessions)
- [ ] You know where to check status from your phone (see Monitoring section)

---

## Launch

### Standard launch (auto-configured)

The pre-flight script shows the recommended command for your hardware. For a
Mac Mini M4 Pro (64 GB):

```bash
caffeinate -d -i -s uv run python scripts/docling_reparse.py \
  --workers 4 --memory-throttle 36 --memory-ceiling 48 --timeout 900 \
  >> /tmp/docling_overnight.log 2>&1 &
echo "Started PID $!"
```

### Machine-specific configurations

**Our machines:**

| Machine | Chip | Cores | RAM | Workers | Throttle | Ceiling | Est. 5K docs |
|---------|------|-------|-----|---------|----------|---------|-------------|
| Mac Mini (primary) | M4 Pro | 14 (10P+4E) | 64 GB | 4 | 36 GB | 48 GB | 6-8 hrs |
| MacBook Air | M5 | 10 | 24 GB | 2 | 14 GB | 18 GB | 15-20 hrs |
| MacBook Air | M5 | 10 | 32 GB | 2 | 18 GB | 24 GB | 15-20 hrs |

**For colleagues (common configs):**

| Machine | RAM | Workers | Throttle | Ceiling | Est. 5K docs |
|---------|-----|---------|----------|---------|-------------|
| M3/M4 MacBook Air (16 GB) | 16 GB | 1 | 8 GB | 12 GB | 30+ hrs |
| M3/M4 MacBook Pro (36 GB) | 36 GB | 3 | 20 GB | 27 GB | 10-15 hrs |
| M3/M4 Pro Mac Mini (64 GB) | 64 GB | 4 | 36 GB | 48 GB | 6-8 hrs |

The pre-flight script auto-detects your hardware and calculates these:
```bash
uv run python scripts/verify_parse_environment.py
```

**Formula:** `workers = min((cores - 2) // 3, 6)`, `ceiling = RAM * 0.75`,
`throttle = ceiling * 0.75`.

### Resume a stopped run

Just run the same command again. The script automatically:
- Skips documents that already have both `.jsonl` AND `.md` output files
- Cleans up orphaned `.part` files from interrupted writes
- Picks up exactly where it left off

```bash
# Same command — resume is automatic
caffeinate -d -i -s uv run python scripts/docling_reparse.py \
  --workers 4 --timeout 900 \
  >> /tmp/docling_overnight.log 2>&1 &
```

---

## Monitoring

### From the terminal (best)

```bash
# Full status report
bash scripts/parse_status.sh

# Auto-refresh every 60 seconds
watch -n 60 bash scripts/parse_status.sh

# Tail the live log
tail -f /tmp/docling_overnight.log
```

### From your phone (via SSH)

```bash
ssh your-mac "bash /path/to/scripts/parse_status.sh"
```

### What to look for

| Metric | Healthy | Warning | Danger |
|--------|---------|---------|--------|
| **Memory** | <24 GB (green) | 24-36 GB (yellow) | >36 GB (red) |
| **Workers** | 4 (or configured count) | 3 (throttle fired once) | 1-2 (repeated throttles) |
| **Rate** | >5 docs/min | 1-5 docs/min (large docs) | 0 docs/min (stalled) |
| **Errors** | <1% | 1-5% | >5% |
| **Heartbeat** | Updated <60s ago | Updated 60-300s ago | Updated >300s ago |

### Memory trend interpretation

- **Flat with periodic drops** — healthy. Drops are worker recycling events.
- **Slowly rising** — leak present but recycling is containing it. Normal.
- **Rapidly rising (>1 GB/min)** — something wrong. Check worker count.
- **Dropping** — workers just recycled. Healthy.

### Automated watchdog (optional)

Install the watchdog as a cron job for 15-minute checks:

```bash
crontab -e
# Add:
*/15 * * * * /path/to/scripts/parse_watchdog.sh >> /tmp/watchdog.log 2>&1
```

The watchdog is **observability-only** — it logs warnings but does NOT
auto-kill or restart the process. The adaptive throttling in the supervisor
handles memory issues.

---

## Recovery Decision Tree

| Symptom | Cause | Recovery |
|---------|-------|----------|
| Process exited, summary says `shutdown_requested: true` | Memory ceiling reached | Working as designed. Resume with same command. |
| Process exited, log shows `THROTTLE` then shutdown | Reduced to 1 worker, still over threshold | Resume with `--workers 2 --memory-ceiling 60` |
| Process exited, no summary file | Crash (SIGKILL, kernel panic, power loss) | Check `dmesg` / diagnostic reports. Resume with same command. |
| Process running but no progress >30 min | Stuck on huge PDF | Check heartbeat file age. If >5 min stale, kill and resume. |
| Process running, memory >40 GB | Approaching danger | Watch closely. Throttling should kick in at 36 GB. |
| Many `timeout` errors | Pathological PDFs | Normal for some documents. Check which PDFs are timing out. |
| `BrokenProcessPool` in log | Worker segfault | Automatic recovery. Check if it repeats on same doc. |
| Dropbox conflict files in output | Two machines wrote simultaneously | Delete `.conflicted` copies, keep originals. |

### Emergency stop

```bash
# Graceful (preserves progress)
kill -TERM $(pgrep -f docling_reparse.py | head -1)

# Force (if graceful doesn't work after 30s)
pkill -9 -f docling_reparse.py
```

After any stop, resume is safe — atomic writes protect completed documents.

---

## Morning Validation

After the parse completes (check for `_summary.json`):

### 1. Check the summary

```bash
cat data/parsed_docling/_summary.json | python3 -m json.tool
```

**Must-pass:**
- `completed` matches expected count (within ~1% of total PDFs)
- `failed` < 2% of total
- `shutdown_requested: false`
- `throttle_events` < 5

### 2. Run the validation script

```bash
uv run python scripts/validate_parse_output.py
```

**Must-pass:**
- All output file pairs present (`.jsonl` + `.md`)
- No empty output files (<50 bytes)
- No orphaned `.part` files
- Error rate <5%

### 3. Spot-check quality

```bash
# Random sample of 5 markdown files
ls data/parsed_docling/*.md | shuf | head -5 | xargs -I {} sh -c 'echo "=== {} ===" && head -20 {}'
```

Verify the markdown has actual document structure (headings, paragraphs, tables),
not empty or garbled content.

### 4. Proceed to pipeline

If all checks pass:

```bash
uv run python scripts/promote_parsed_dir.py
rm -f data/db/corpus.duckdb && uv run corpus ingest --run-id rebuild-$(date +%Y%m%d)
uv run corpus build-pages
uv run corpus build-markdown
uv run corpus grep run --run-id grep-docling-$(date +%Y%m%d)
```

---

## Reference: How the Safety Mechanisms Work

### Worker recycling (`max_tasks_per_child=10`)

Each worker process is killed and respawned after 10 documents. This prevents
Docling's memory leaks (8+ open upstream issues, no official fix) from
accumulating beyond ~10 GB per worker. Cost: ~3-5% throughput overhead from
model reloading.

### Three-tier memory response

| Threshold | Default | Action |
|-----------|---------|--------|
| Info | 24 GB | Log warning |
| Throttle | 36 GB | Kill pool, restart with 1 fewer worker |
| Ceiling | 48 GB | Graceful shutdown, write summary, exit |

Thresholds are configurable via CLI flags. Formula: `info = throttle * 0.67`.

### Background monitoring thread

A timer thread checks total Python RSS every 30 seconds, independent of
document completions. This catches memory spikes during long-running documents
(some LuxSE PDFs take 10+ minutes). Writes a heartbeat file for external
monitoring.

### Atomic writes + resume

Each document's output is written to `.part` files first, then atomically
renamed. If the process dies mid-write, the `.part` file is cleaned up on
restart. Resume checks for both `.jsonl` AND `.md` files with size > 0.

---

## Reference: Why macOS Needs Self-Monitoring

macOS has **no kernel-enforced per-process memory limits**:
- `resource.setrlimit(RLIMIT_AS, ...)` is a silent no-op on macOS
- launchd resource limits map to the same no-op
- No cgroups (Linux only)
- Jetsam thresholds are SIP-protected and not configurable

The only way to prevent a runaway process from causing a kernel panic on macOS
is **self-monitoring with psutil**. This is not a workaround — it is the only
mechanism available.

---

## Appendix: Golden Run Metrics (Mac Mini M4 Pro, 64 GB)

From the April 12, 2026 run (5,400+ documents):

| Phase | Docs | Rate | Memory |
|-------|------|------|--------|
| Small docs (0-0.2 MB) | ~2,400 | 79 docs/min | 4-7 GB |
| Medium docs (0.2-2 MB) | ~2,000 | 15 docs/min | 5-9 GB |
| Large docs (2+ MB) | ~1,000 | 3-6 docs/min | 6-12 GB |

| Metric | Baseline |
|--------|----------|
| Overall success rate | 99.7% |
| Worker recycling events | ~80 per 2,400 docs (1 per 30 docs) |
| Throttle events | 0 |
| Peak memory | 8.9 GB |
| Memory trend | Flat with periodic drops |
| Total wall clock | ~6-8 hours for 5,400 docs |
