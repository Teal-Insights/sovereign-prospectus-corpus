#!/bin/bash
# chain_overnight.sh — Wait for PDF parse, run EDGAR parse, validate.
#
# Usage:
#   nohup bash scripts/chain_overnight.sh >> /tmp/chain_overnight.log 2>&1 &
#
# Monitor from phone:
#   tail -1 data/parsed_docling/_chain_log.jsonl
#   cat data/parsed_docling/_chain_complete.json

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PARSED="$DIR/data/parsed_docling"
CHAIN_LOG="$PARSED/_chain_log.jsonl"
CHAIN_COMPLETE="$PARSED/_chain_complete.json"
CHAIN_START=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
MAX_WAIT_HOURS=14  # Give up after 14 hours of waiting

log_stage() {
    local stage="$1" status="$2"
    shift 2
    echo "{\"stage\":\"$stage\",\"status\":\"$status\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"$*}" >> "$CHAIN_LOG"
}

echo "Chain started at $(date). Waiting for PDF parse to finish..."
log_stage "waiting_for_pdf" "started"

# Wait for PDF parse to finish by watching for fresh _summary.json
WAIT_START=$(date +%s)
while true; do
    # Timeout check
    NOW=$(date +%s)
    ELAPSED_HOURS=$(( (NOW - WAIT_START) / 3600 ))
    if [ "$ELAPSED_HOURS" -ge "$MAX_WAIT_HOURS" ]; then
        echo "ERROR: Waited $MAX_WAIT_HOURS hours for PDF parse. Giving up."
        log_stage "chain_aborted" "timeout"
        echo "{\"status\":\"aborted\",\"reason\":\"wait_timeout\",\"hours_waited\":$ELAPSED_HOURS,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"}" > "$CHAIN_COMPLETE"
        exit 1
    fi

    # Check for fresh summary
    if [ -f "$PARSED/_summary.json" ]; then
        FINISHED_AT=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('finished_at',''))" 2>/dev/null || echo "")
        if [ -n "$FINISHED_AT" ] && [ "$FINISHED_AT" \> "$CHAIN_START" ]; then
            echo "PDF parse completed at $FINISHED_AT"
            break
        fi
    fi

    # Also check if parse process is dead (hard crash, no summary written)
    if ! pgrep -f "docling_reparse.py" > /dev/null 2>&1; then
        # Process not running — check if summary was written
        if [ -f "$PARSED/_summary.json" ]; then
            FINISHED_AT=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('finished_at',''))" 2>/dev/null || echo "")
            if [ -n "$FINISHED_AT" ] && [ "$FINISHED_AT" \> "$CHAIN_START" ]; then
                echo "PDF parse completed (detected after process exit)"
                break
            fi
        fi
        echo "WARNING: PDF parse process not running, no fresh summary. Waiting for possible restart..."
    fi

    sleep 300
done

# Verify PDF parse succeeded
SHUTDOWN=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('shutdown_requested', True))" 2>/dev/null)
FAILED=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('failed',0))" 2>/dev/null)
TOTAL=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('total',0))" 2>/dev/null)
COMPLETED=$(python3 -c "import json; print(json.load(open('$PARSED/_summary.json')).get('completed',0))" 2>/dev/null)
# Default to 0 if python3 returned empty (corrupt JSON, etc.)
FAILED=${FAILED:-0}
TOTAL=${TOTAL:-0}
COMPLETED=${COMPLETED:-0}

log_stage "pdf_complete" "checked" ",\"completed\":$COMPLETED,\"failed\":$FAILED"

if [ "$SHUTDOWN" = "True" ]; then
    echo "WARNING: PDF parse was shut down (memory ceiling or signal)."
    echo "Proceeding with EDGAR parse anyway — PDF docs are safe (atomic writes)."
    log_stage "pdf_warning" "shutdown_detected"
fi

# Start EDGAR parse
echo "Starting EDGAR HTML parse at $(date)..."
log_stage "edgar_parse" "started"

cd "$DIR"
# Don't use set -e — we want to continue to validation even if EDGAR has some failures
set -o pipefail
uv run python scripts/docling_reparse_edgar.py 2>&1 | tee -a /tmp/docling_edgar.log
EDGAR_EXIT=${PIPESTATUS[0]:-$?}
set +o pipefail

if [ "$EDGAR_EXIT" -ne 0 ]; then
    echo "WARNING: EDGAR parse exited with code $EDGAR_EXIT"
    log_stage "edgar_complete" "exit_code_$EDGAR_EXIT"
else
    log_stage "edgar_complete" "success"
fi

# Check EDGAR results
if [ -f "$PARSED/_edgar_summary.json" ]; then
    EDGAR_COMPLETED=$(python3 -c "import json; print(json.load(open('$PARSED/_edgar_summary.json')).get('completed',0))" 2>/dev/null)
    EDGAR_FAILED=$(python3 -c "import json; print(json.load(open('$PARSED/_edgar_summary.json')).get('failed',0))" 2>/dev/null)
    echo "EDGAR parse: $EDGAR_COMPLETED completed, $EDGAR_FAILED failed"
    log_stage "edgar_summary" "checked" ",\"completed\":$EDGAR_COMPLETED,\"failed\":$EDGAR_FAILED"
fi

# Validate
echo "Running validation at $(date)..."
log_stage "validation" "started"
cd "$DIR" && uv run python scripts/validate_parse_output.py 2>&1 || true
log_stage "validation" "finished"

# Write completion marker
CHAIN_END=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
TOTAL_JSONL=$(find "$PARSED" -maxdepth 1 -name "*.jsonl" ! -name "_*" | wc -l | tr -d ' ')
TOTAL_MD=$(find "$PARSED" -maxdepth 1 -name "*.md" ! -name "_*" | wc -l | tr -d ' ')
echo "{\"status\":\"complete\",\"started\":\"$CHAIN_START\",\"finished\":\"$CHAIN_END\",\"total_jsonl\":$TOTAL_JSONL,\"total_md\":$TOTAL_MD,\"timestamp\":\"$CHAIN_END\"}" > "$CHAIN_COMPLETE"

echo "Chain complete at $(date). $TOTAL_JSONL JSONL, $TOTAL_MD MD files."
log_stage "chain_complete" "done" ",\"total_jsonl\":$TOTAL_JSONL,\"total_md\":$TOTAL_MD"
