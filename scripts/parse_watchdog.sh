#!/bin/bash
# Watchdog for overnight Docling parse — OBSERVABILITY ONLY.
# Reports status but does NOT auto-kill or auto-restart.
# The adaptive throttling in the supervisor handles memory issues.
# Install as cron: */15 * * * * /path/to/parse_watchdog.sh >> /tmp/watchdog.log 2>&1

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRESS="$DIR/data/parsed_docling/_progress.jsonl"
SUMMARY="$DIR/data/parsed_docling/_summary.json"
HEARTBEAT="$DIR/data/parsed_docling/_heartbeat.json"
WATCHDOG_LOG="/tmp/watchdog.log"

echo "[$(date)] Watchdog check" >> "$WATCHDOG_LOG"

# If summary exists, the run completed — nothing to do
if [ -f "$SUMMARY" ]; then
    echo "[$(date)] Parse complete. Nothing to do." >> "$WATCHDOG_LOG"
    exit 0
fi

# Check if process is running
if pgrep -f "docling_reparse.py" > /dev/null 2>&1; then
    # Process running — check heartbeat first (preferred)
    if [ -f "$HEARTBEAT" ]; then
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
        DONE=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('completed', '?'))" 2>/dev/null || echo "?")
        REMAIN=$(python3 -c "import json; print(json.load(open('$HEARTBEAT')).get('remaining', '?'))" 2>/dev/null || echo "?")

        if [ "$HEARTBEAT_AGE" -gt 120 ]; then
            echo "[$(date)] WARNING: Heartbeat stale (${HEARTBEAT_AGE}s). Workers=$WORKERS, Mem=${MEM_GB}GB. Process may be hung." >> "$WATCHDOG_LOG"
        else
            echo "[$(date)] Running OK. Workers=$WORKERS, Mem=${MEM_GB}GB, Done=$DONE, Remaining=$REMAIN. Heartbeat ${HEARTBEAT_AGE}s ago." >> "$WATCHDOG_LOG"
        fi
    elif [ -f "$PROGRESS" ]; then
        # Fallback: check progress log
        LAST_TIME=$(tail -1 "$PROGRESS" | python3 -c "
import sys, json
from datetime import datetime, UTC
try:
    ts = json.load(sys.stdin).get('timestamp', '')
    dt = datetime.fromisoformat(ts)
    age = (datetime.now(UTC) - dt).total_seconds()
    print(int(age))
except:
    print(9999)
" 2>/dev/null)
        DONE=$(wc -l < "$PROGRESS" | tr -d ' ')
        echo "[$(date)] Running. $DONE docs processed. Last activity ${LAST_TIME}s ago." >> "$WATCHDOG_LOG"

        if [ "$LAST_TIME" -gt 1800 ]; then
            echo "[$(date)] WARNING: No progress in ${LAST_TIME}s. Process may be hung." >> "$WATCHDOG_LOG"
        fi
    else
        echo "[$(date)] Running but no progress file yet (still prewarming)." >> "$WATCHDOG_LOG"
    fi

    # Check total memory via ps (observability only)
    TOTAL_RSS_KB=0
    for pid in $(pgrep -f "docling_reparse.py" 2>/dev/null); do
        RSS=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
        [ -n "$RSS" ] && TOTAL_RSS_KB=$((TOTAL_RSS_KB + RSS))
    done
    # Include worker children
    SUPERVISOR_PID=$(pgrep -f "docling_reparse.py" | head -1)
    if [ -n "$SUPERVISOR_PID" ]; then
        for pid in $(pgrep -P "$SUPERVISOR_PID" 2>/dev/null); do
            RSS=$(ps -o rss= -p "$pid" 2>/dev/null | tr -d ' ')
            [ -n "$RSS" ] && TOTAL_RSS_KB=$((TOTAL_RSS_KB + RSS))
        done
    fi
    TOTAL_RSS_GB=$(echo "scale=1; $TOTAL_RSS_KB / 1048576" | bc)
    if [ "$(echo "$TOTAL_RSS_GB > 40" | bc)" -eq 1 ]; then
        echo "[$(date)] WARNING: High memory usage: ${TOTAL_RSS_GB} GB" >> "$WATCHDOG_LOG"
    fi
else
    # Process not running and no summary — it stopped unexpectedly
    echo "[$(date)] Process not running! Check logs at /tmp/docling_overnight.log" >> "$WATCHDOG_LOG"
fi
