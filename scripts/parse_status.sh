#!/bin/bash
# Quick status report for the overnight Docling parse.
# Run from anywhere: bash scripts/parse_status.sh
# Or from Claude Code: just ask "how's the parse going?"

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROGRESS="$DIR/data/parsed_docling/_progress.jsonl"
SUMMARY="$DIR/data/parsed_docling/_summary.json"
ERRORS="$DIR/data/parsed_docling/_errors.log"
OUTPUT="$DIR/data/parsed_docling"

echo "=== Overnight Docling Parse Status ==="
echo "Time: $(date)"
echo ""

# Check if process is running
if pgrep -f "docling_reparse.py" > /dev/null 2>&1; then
    echo "Status: RUNNING (PID $(pgrep -f docling_reparse.py | head -1))"
else
    if [ -f "$SUMMARY" ]; then
        echo "Status: COMPLETED"
    else
        echo "Status: NOT RUNNING (no summary file — may have crashed)"
    fi
fi
echo ""

# Count outputs
JSONL_COUNT=$(ls "$OUTPUT"/*.jsonl 2>/dev/null | grep -v "^_" | wc -l | tr -d ' ')
MD_COUNT=$(ls "$OUTPUT"/*.md 2>/dev/null | grep -v "^_" | wc -l | tr -d ' ')
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
print(f\"  Elapsed: {s['elapsed_human']}\")
print(f\"  Finished: {s['finished_at']}\")
" 2>/dev/null
fi

echo ""
echo "=== Disk ==="
df -h "$OUTPUT" 2>/dev/null | tail -1 | awk '{print "  Free: " $4 " (" $5 " used)"}'
