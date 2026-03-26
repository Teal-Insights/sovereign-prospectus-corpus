"""Download run reports and pipeline status.

Provides:
- write_run_report(): human-readable report after each download run
- get_source_status(): diff discovery vs manifest for outstanding items
- format_status_summary(): cross-source status table
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Discovery file ID extractors per source.
# NSM discovery stores raw _source dicts (key: disclosure_id).
# EDGAR discovery stores manifest-shaped records (key: native_id).
DISCOVERY_ID_KEYS: dict[str, str] = {
    "nsm": "disclosure_id",
    "edgar": "native_id",
    "pdip": "native_id",
}

# Discovery file paths by convention
DISCOVERY_PATHS: dict[str, str] = {
    "nsm": "data/nsm_discovery.jsonl",
    "edgar": "data/edgar_discovery.jsonl",
    "pdip": "data/pdip_discovery.jsonl",
}


def write_run_report(
    *,
    source: str,
    run_id: str,
    stats: dict[str, Any],
    telemetry_dir: Path,
) -> Path:
    """Write a human-readable download report.

    Parses telemetry JSONL for failure details. Returns path to report file.
    """
    report_path = telemetry_dir / f"{source}_{run_id}_report.txt"
    failures = _extract_failures(telemetry_dir, source, run_id)

    lines: list[str] = []
    lines.append(f"{source.upper()} Download Report (run_id: {run_id})")
    lines.append(
        f"  Total: {stats.get('total_in_discovery', '?')} | "
        f"Downloaded: {stats.get('downloaded', 0)} | "
        f"Skipped: {stats.get('skipped', 0)} | "
        f"Failed: {stats.get('failed', 0)}"
    )

    if stats.get("aborted"):
        lines.append("")
        lines.append("  *** ABORTED — circuit breaker triggered ***")

    if failures:
        lines.append("")
        lines.append(f"  Failed documents ({len(failures)}):")
        for f in failures:
            lines.append(
                f"    {f['document_id']:40s}  {f['status']:15s}  {f.get('error_message', '')}"
            )

    lines.append("")
    lines.append("  To retry failed downloads:")
    lines.append(
        f"    corpus download {source}"
        f" --discovery-file {DISCOVERY_PATHS.get(source, f'data/{source}_discovery.jsonl')}"
    )
    lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


_NON_FAILURE_STATUSES = frozenset({"success", "success_after_429", "rate_limited", "not_found"})


def _extract_failures(
    telemetry_dir: Path,
    source: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Parse telemetry JSONL for terminal failure download entries."""
    failures: list[dict[str, Any]] = []

    for log_file in telemetry_dir.glob(f"{source}_*.jsonl"):
        try:
            with log_file.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        entry.get("run_id") == run_id
                        and entry.get("step") == "download"
                        and entry.get("status") not in _NON_FAILURE_STATUSES
                    ):
                        failures.append(entry)
        except OSError:
            continue

    # Deduplicate by document_id (keep last entry per doc)
    seen: dict[str, dict[str, Any]] = {}
    for f in failures:
        seen[f["document_id"]] = f
    return list(seen.values())


def get_source_status(
    source: str,
    *,
    discovery_path: Path | None = None,
    manifest_dir: Path = Path("data/manifests"),
    telemetry_dir: Path = Path("data/telemetry"),
) -> dict[str, Any]:
    """Diff discovery vs manifest for a source. Returns status dict."""
    if discovery_path is None:
        discovery_path = Path(DISCOVERY_PATHS.get(source, f"data/{source}_discovery.jsonl"))

    if not discovery_path.exists():
        return {"source": source, "status": "not_discovered"}

    id_key = DISCOVERY_ID_KEYS.get(source, "native_id")
    manifest_path = manifest_dir / f"{source}_manifest.jsonl"

    # Read discovery IDs and titles
    discovery_items: dict[str, str] = {}
    with discovery_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            native_id = record.get(id_key, "")
            title = record.get("title", record.get("headline", ""))
            if native_id:
                discovery_items[native_id] = title

    # Read manifest IDs
    manifest_ids: set[str] = set()
    if manifest_path.exists():
        with manifest_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                native_id = record.get("native_id", "")
                if native_id:
                    manifest_ids.add(native_id)

    # Find outstanding
    outstanding_ids = set(discovery_items.keys()) - manifest_ids

    # Enrich with last error from telemetry
    last_errors: dict[str, str] = {}
    for log_file in telemetry_dir.glob(f"{source}_*.jsonl"):
        try:
            with log_file.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    doc_id = entry.get("document_id", "")
                    if (
                        doc_id in outstanding_ids
                        and entry.get("status") not in _NON_FAILURE_STATUSES
                    ):
                        last_errors[doc_id] = entry.get("error_message", entry.get("status", ""))
        except OSError:
            continue

    outstanding = [
        {
            "native_id": nid,
            "title": discovery_items[nid],
            "last_error": last_errors.get(nid, ""),
        }
        for nid in sorted(outstanding_ids)
    ]

    return {
        "source": source,
        "status": "ok",
        "discovery_count": len(discovery_items),
        "manifest_count": len(manifest_ids),
        "outstanding_count": len(outstanding),
        "outstanding": outstanding,
    }


def format_status_summary(statuses: list[dict[str, Any]]) -> str:
    """Render cross-source status table as a string."""
    lines: list[str] = []
    for s in statuses:
        if s.get("status") == "not_discovered":
            lines.append(f"  {s['source'].upper():8s} not discovered")
        else:
            detail = ""
            if s["outstanding_count"] > 0:
                detail = f"  ({s['outstanding_count']} outstanding)"
            lines.append(
                f"  {s['source'].upper():8s}"
                f" {s['manifest_count']:>5d} / {s['discovery_count']:<5d} downloaded{detail}"
            )
    return "\n".join(lines)
