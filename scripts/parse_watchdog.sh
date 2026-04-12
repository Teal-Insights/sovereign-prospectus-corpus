#!/bin/bash
# Watchdog for overnight Docling parse.
# Checks if the process is running and healthy. Restarts if crashed.
# Install as cron: */15 * * * * /path/to/parse_watchdog.sh >> /tmp/watchdog.log 2>&1

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRESS="$DIR/data/parsed_docling/_progress.jsonl"
SUMMARY="$DIR/data/parsed_docling/_summary.json"
LOG="/tmp/docling_overnight.log"
WATCHDOG_LOG="/tmp/watchdog.log"

echo "[$(date)] Watchdog check" >> "$WATCHDOG_LOG"

# If summary exists, the run completed — nothing to do
if [ -f "$SUMMARY" ]; then
    echo "[$(date)] Parse complete. Nothing to do." >> "$WATCHDOG_LOG"
    exit 0
fi

# Check if process is running
if pgrep -f "docling_reparse.py" > /dev/null 2>&1; then
    # Process running — check if it's making progress
    if [ -f "$PROGRESS" ]; then
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

        if [ "$LAST_TIME" -gt 1800 ]; then
            echo "[$(date)] WARNING: No progress in ${LAST_TIME}s. Process may be hung." >> "$WATCHDOG_LOG"
            echo "[$(date)] Killing hung process and restarting..." >> "$WATCHDOG_LOG"
            pkill -f "docling_reparse.py"
            sleep 5
            # Restart (resume semantics will skip completed docs)
            cd "$DIR" && caffeinate -d -i uv run python scripts/docling_reparse.py >> "$LOG" 2>&1 &
            echo "[$(date)] Restarted parse (PID $!)" >> "$WATCHDOG_LOG"
        else
            DONE=$(wc -l < "$PROGRESS" | tr -d ' ')
            echo "[$(date)] Running OK. $DONE docs processed. Last activity ${LAST_TIME}s ago." >> "$WATCHDOG_LOG"
        fi
    else
        echo "[$(date)] Running but no progress file yet (still prewarming)." >> "$WATCHDOG_LOG"
    fi
else
    # Process not running and no summary — it crashed
    echo "[$(date)] Process not running! Restarting..." >> "$WATCHDOG_LOG"
    cd "$DIR" && caffeinate -d -i uv run python scripts/docling_reparse.py >> "$LOG" 2>&1 &
    echo "[$(date)] Restarted parse (PID $!)" >> "$WATCHDOG_LOG"
fi
