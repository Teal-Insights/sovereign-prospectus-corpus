#!/bin/bash
# Quick status report for the overnight Docling parse.
# Run from anywhere: bash scripts/parse_status.sh
# Or from Claude Code: just ask "how's the parse going?"

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRESS="$DIR/data/parsed_docling/_progress.jsonl"
SUMMARY="$DIR/data/parsed_docling/_summary.json"
ERRORS="$DIR/data/parsed_docling/_errors.log"
OUTPUT="$DIR/data/parsed_docling"
HEARTBEAT="$DIR/data/parsed_docling/_heartbeat.json"

echo "=== Overnight Docling Parse Status ==="
echo "Time: $(date)"
echo ""

# Check if process is running
SUPERVISOR_PID=""
if pgrep -f "docling_reparse.py" > /dev/null 2>&1; then
    SUPERVISOR_PID=$(pgrep -f "docling_reparse.py" | head -1)
    echo "Status: RUNNING (PID $SUPERVISOR_PID)"
else
    if [ -f "$SUMMARY" ]; then
        echo "Status: COMPLETED"
    else
        echo "Status: NOT RUNNING (no summary file — may have crashed)"
    fi
fi
echo ""

# Memory usage (pure shell — no Python/psutil)
if [ -n "$SUPERVISOR_PID" ]; then
    echo "=== Memory ==="
    TOTAL_KB=0

    # Supervisor process
    RSS_KB=$(ps -o rss= -p "$SUPERVISOR_PID" 2>/dev/null | tr -d ' ')
    if [ -n "$RSS_KB" ] && [ "$RSS_KB" -gt 0 ]; then
        RSS_GB=$(echo "scale=1; $RSS_KB / 1048576" | bc)
        echo "  PID $SUPERVISOR_PID: ${RSS_GB} GB  (supervisor)"
        TOTAL_KB=$((TOTAL_KB + RSS_KB))
    fi

    # Worker processes (children of supervisor)
    WORKER_PIDS=$(pgrep -P "$SUPERVISOR_PID" 2>/dev/null)
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
    SYS_MEM_GB=$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1024/1024/1024}')
    SYS_MEM_GB=${SYS_MEM_GB:-64}

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

# Heartbeat
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

# Count outputs
JSONL_COUNT=$(find "$OUTPUT" -maxdepth 1 -name "*.jsonl" ! -name "_*" 2>/dev/null | wc -l | tr -d ' ')
MD_COUNT=$(find "$OUTPUT" -maxdepth 1 -name "*.md" ! -name "_*" 2>/dev/null | wc -l | tr -d ' ')
echo "Output files: $JSONL_COUNT JSONL, $MD_COUNT MD"

# Progress from log
if [ -f "$PROGRESS" ]; then
    TOTAL_LOGGED=$(wc -l < "$PROGRESS" | tr -d ' ')
    SUCCESS=$(grep -c '"success"' "$PROGRESS" 2>/dev/null || echo 0)
    FAILED=$(grep -c '"failed"\|"pool_crash"\|"timeout"' "$PROGRESS" 2>/dev/null || echo 0)

    # Get the last entry timestamp and calculate rate
    LAST_ENTRY=$(tail -1 "$PROGRESS")
    LAST_TIME=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('timestamp','?'))" 2>/dev/null || echo "?")
    LAST_KEY=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('storage_key','?'))" 2>/dev/null || echo "?")
    LAST_ELAPSED=$(echo "$LAST_ENTRY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('elapsed_s','?'))" 2>/dev/null || echo "?")

    echo "Progress: $TOTAL_LOGGED processed ($SUCCESS ok, $FAILED failed)"
    echo "Last doc: $LAST_KEY (${LAST_ELAPSED}s) at $LAST_TIME"

    # Estimate total and ETA
    INPUT_PDFS=$(find "$DIR/data/original" "$DIR/data/pdfs/pdip" -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$INPUT_PDFS" -gt 0 ] && [ "$TOTAL_LOGGED" -gt 0 ]; then
        PCT=$((TOTAL_LOGGED * 100 / INPUT_PDFS))
        echo "Coverage: $TOTAL_LOGGED / $INPUT_PDFS ($PCT%)"
    fi
else
    echo "No progress log yet"
fi

# Errors
if [ -f "$ERRORS" ]; then
    ERROR_COUNT=$(wc -l < "$ERRORS" | tr -d ' ')
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo ""
        echo "ERRORS: $ERROR_COUNT (last 3):"
        tail -3 "$ERRORS" | sed 's/^/  /'
    fi
else
    echo "No errors logged"
fi

# Summary if complete
if [ -f "$SUMMARY" ]; then
    echo ""
    echo "=== Final Summary ==="
    python3 -c "
import json
with open('$SUMMARY') as f:
    s = json.load(f)
print(f\"  Total: {s['total']}\")
print(f\"  Completed: {s['completed']}\")
print(f\"  Failed: {s['failed']}\")
print(f\"  Skipped: {s['skipped']}\")
print(f\"  Pool restarts: {s['pool_restarts']}\")
print(f\"  Throttle events: {s.get('throttle_events', 'n/a')}\")
print(f\"  Peak memory: {s.get('peak_memory_gb', 'n/a')} GB\")
print(f\"  Elapsed: {s['elapsed_human']}\")
print(f\"  Finished: {s['finished_at']}\")
" 2>/dev/null
fi

echo ""
echo "=== Disk ==="
df -h "$OUTPUT" 2>/dev/null | tail -1 | awk '{print "  Free: " $4 " (" $5 " used)"}'
