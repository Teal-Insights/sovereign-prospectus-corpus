# Download Run Reports + Status Command Design

**Date:** 2026-03-26
**Issue:** #14
**Branch:** `feature/run-reports`

## Overview

Shared infrastructure for download run reports and a `corpus status` command. Gives operators visibility into what failed, why, and how to retry — without interrupting long-running downloads. Applies to all source adapters (NSM, EDGAR, PDIP).

## Architecture

### New module: `src/corpus/reporting.py`

Three functions:

**`write_run_report(source, run_id, stats, telemetry_dir, manifest_dir)`**
Called at end of each adapter's download. Writes `data/telemetry/{source}_{run_id}_report.txt` with:
- Aggregate stats (downloaded, skipped, failed)
- Per-document failure details (parsed from telemetry JSONL)
- Retry command

**`get_source_status(source, discovery_path, manifest_dir)`**
Diffs discovery JSONL native_ids against manifest JSONL native_ids. Returns dict:
```python
{
    "source": "edgar",
    "discovery_count": 3306,
    "manifest_count": 3301,
    "outstanding_count": 5,
    "outstanding": [
        {"native_id": "...", "title": "...", "last_error": "..."},
    ],
}
```
Optionally enriches outstanding items with last error from telemetry JSONL.

**`format_status_summary(statuses: list[dict])`**
Renders cross-source table as a string for CLI output.

### CLI: `corpus status [source]`

- `corpus status` — calls `get_source_status` for each source that has a discovery file, renders cross-source summary
- `corpus status edgar` — per-source detail with outstanding documents listed

Discovery file paths follow convention: `data/{source}_discovery.jsonl` (NSM) / `data/edgar_discovery.jsonl` (EDGAR). The status command auto-discovers these.

Manifest files: `data/manifests/{source}_manifest.jsonl`.

### Integration with adapters

After the download loop in `run_nsm_download` and `run_edgar_download`, call `write_run_report()`. This is a 2-line change per adapter — import and call.

### Report format

```
EDGAR Download Report (run_id: edgar-full-001)
  Total: 3306 | Downloaded: 3301 | Skipped: 5 | Failed: 3

  Failed documents (3):
    edgar__0001193125-22-000789  error         Connection reset by peer
    edgar__0001193125-20-000444  error         HTTP 403 Forbidden
    edgar__0001193125-18-000333  rate_limited  SEC 429 — retry also failed

  To retry failed downloads:
    corpus download edgar --discovery-file data/edgar_discovery.jsonl
```

### Status output format

```
$ corpus status
  NSM:    642 / 899  downloaded  (257 html-only)
  EDGAR: 3301 / 3306 downloaded  (5 outstanding)
  PDIP:  not discovered

$ corpus status edgar
  EDGAR: 3301 / 3306 downloaded (5 outstanding)

  Outstanding (in discovery, not in manifest):
    0001193125-22-000789  "Prospectus Supplement"  last error: Connection reset
    0001193125-20-000444  "424B5 - ARGENTINA"      last error: HTTP 403
    ...

  To retry: corpus download edgar --discovery-file data/edgar_discovery.jsonl
```

### Testing

- `test_write_run_report`: generates report from fixture stats + telemetry JSONL, verify format
- `test_get_source_status`: discovery with 5 items, manifest with 3 → 2 outstanding
- `test_get_source_status_no_discovery`: returns "not discovered" status
- `test_get_source_status_empty_manifest`: all items outstanding
- `test_format_status_summary`: multi-source table formatting
- `test_status_cli`: `corpus status` and `corpus status edgar` help text and basic invocation

### Files

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/corpus/reporting.py` | Run reports + status diffing |
| Create | `tests/test_reporting.py` | Unit tests |
| Modify | `src/corpus/cli.py` | Add `corpus status` command |
| Modify | `src/corpus/sources/edgar.py` | Call `write_run_report` after download |
| Modify | `src/corpus/sources/nsm.py` | Call `write_run_report` after download |
