"""PDIP annotations harvester — fetch clause annotations from /api/details.

Inventory-driven, resumable harvester that fetches PDIP annotation payloads
for annotated documents and classifies CAC candidates.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — needed at runtime
from typing import Any

import requests

from corpus.sources.pdip import PDIP_BASE_URL, PDIP_HEADERS, _build_ca_bundle

log = logging.getLogger(__name__)

PDIP_DETAILS_URL = f"{PDIP_BASE_URL}/api/details/{{doc_id}}"

EXPECTED_INVENTORY_HEADERS = [
    "id",
    "document_title",
    "tag_status",
    "country",
    "instrument_type",
    "creditor_country",
    "creditor_type",
    "entity_type",
    "document_date",
    "maturity_date",
]

EXPECTED_ANNOTATED_COUNT = 162
EXPECTED_ANNOTATED_BOND_COUNT = 58

SMOKE_TEST_IDS = {"VEN85", "NLD21", "KEN68", "JAM22", "VEN59"}

# Statuses that are transport/API failures (trip circuit breaker)
_TRANSPORT_FAILURE_STATUSES = frozenset(
    {"failed_http", "failed_request", "invalid_json", "api_error"}
)

# CAC label prefixes
_CAC_MODIFICATION_PREFIX = "VotingCollectiveActionModification_"
_CAC_ACCELERATION_PREFIX = "VotingRequirementforAcceleration_"


def load_inventory(
    inventory_path: Path,
    *,
    annotated_only: bool = True,
) -> list[dict[str, str]]:
    """Load inventory CSV rows, optionally filtering to annotated only."""
    with inventory_path.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty or malformed CSV: {inventory_path}")
        actual = list(reader.fieldnames)
        if actual != EXPECTED_INVENTORY_HEADERS:
            raise ValueError(
                f"Inventory headers mismatch.\n"
                f"  Expected: {EXPECTED_INVENTORY_HEADERS}\n"
                f"  Actual:   {actual}"
            )
        rows = list(reader)

    if annotated_only:
        rows = [r for r in rows if r["tag_status"] == "Annotated"]

    return rows


def run_preflight(
    rows: list[dict[str, str]],
    *,
    doc_ids: list[str] | None = None,
) -> None:
    """Validate inventory counts and smoke-test IDs exist."""
    annotated_count = len(rows)
    if annotated_count != EXPECTED_ANNOTATED_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_ANNOTATED_COUNT} annotated docs, got {annotated_count}"
        )

    bond_count = sum(1 for r in rows if r["instrument_type"] == "Bond")
    if bond_count != EXPECTED_ANNOTATED_BOND_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_ANNOTATED_BOND_COUNT} annotated bonds, got {bond_count}"
        )

    row_ids = {r["id"] for r in rows}
    for sid in SMOKE_TEST_IDS:
        if sid not in row_ids:
            raise ValueError(f"Smoke-test ID {sid} not in annotated set")

    if doc_ids:
        for did in doc_ids:
            if did not in row_ids:
                raise ValueError(f"Requested doc_id {did} not in annotated set")


def load_completed_ids(annotations_path: Path) -> set[str]:
    """Load completed doc_ids from annotations.jsonl, tolerating truncated trailing line."""
    completed: set[str] = set()
    if not annotations_path.exists():
        return completed

    with annotations_path.open() as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                doc_id = record.get("doc_id")
                if doc_id:
                    completed.add(doc_id)
            except json.JSONDecodeError:
                log.warning(
                    "Ignoring invalid JSON at line %d in %s (likely truncated)",
                    line_num,
                    annotations_path,
                )
    return completed


def extract_labels(clauses: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract and classify clause labels from API response.

    PDIP annotations use Label Studio format where clause labels are stored
    in ``clause["value"]["rectanglelabels"]`` (a list of strings).
    """
    raw_labels: list[str] = []
    for clause in clauses:
        # Label Studio format: labels in value.rectanglelabels
        value = clause.get("value")
        if not isinstance(value, dict):
            continue
        rect_labels = value.get("rectanglelabels")
        if not isinstance(rect_labels, list):
            continue
        for label in rect_labels:
            if isinstance(label, str) and label:
                raw_labels.append(label)

    modification_labels = [lbl for lbl in raw_labels if lbl.startswith(_CAC_MODIFICATION_PREFIX)]
    acceleration_labels = [lbl for lbl in raw_labels if lbl.startswith(_CAC_ACCELERATION_PREFIX)]
    cac_candidate = len(modification_labels) > 0

    return {
        "clause_count": len(clauses),
        "raw_clause_labels": raw_labels,
        "cac_modification_labels": modification_labels,
        "cac_acceleration_labels": acceleration_labels,
        "cac_candidate": cac_candidate,
    }


def _make_session(
    *,
    insecure: bool = False,
    timeout: int = 60,
) -> tuple[requests.Session, dict[str, Any]]:
    """Create a requests session for PDIP API calls.

    Returns (session, tls_info) where tls_info has mode/verify/reason.
    """
    session = requests.Session()
    session.headers.update(PDIP_HEADERS)

    if insecure:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session.verify = False
        tls_info = {
            "tls_mode": "insecure",
            "tls_verify": False,
            "tls_reason": "explicit --insecure flag",
        }
    else:
        ca_bundle = _build_ca_bundle()
        session.verify = ca_bundle
        tls_info = {
            "tls_mode": "ca_bundle",
            "tls_verify": ca_bundle,
            "tls_reason": "PDIP CA bundle with InCommon intermediate",
        }

    return session, tls_info


def _fetch_details(
    session: requests.Session,
    doc_id: str,
    *,
    timeout: int = 60,
) -> tuple[dict[str, Any] | None, int, str | None]:
    """Fetch /api/details/{doc_id}.

    Returns (payload, http_status, error_message).
    """
    url = PDIP_DETAILS_URL.format(doc_id=doc_id)
    resp = session.get(url, timeout=timeout)

    if resp.status_code == 404:
        return None, 404, "not_found"

    if resp.status_code >= 400:
        return None, resp.status_code, f"HTTP {resp.status_code}"

    try:
        payload = resp.json()
    except json.JSONDecodeError as e:
        return None, resp.status_code, f"invalid JSON: {e}"

    return payload, resp.status_code, None


def _classify_status(
    payload: dict[str, Any] | None,
    http_status: int,
    error_msg: str | None,
    *,
    inventory_tag_status: str,
    attempt: int,
    max_zero_clause_retries: int = 1,
) -> str:
    """Classify a fetch result into a terminal status."""
    if error_msg == "not_found":
        return "not_found"
    if error_msg is not None and "invalid JSON" in error_msg:
        return "invalid_json"
    if error_msg is not None:
        if http_status >= 500 or http_status == 429:
            return "failed_http"
        return "failed_request"
    if payload is None:
        return "failed_request"

    if "error" in payload:
        return "api_error"

    clauses = payload.get("clauses", [])
    if len(clauses) == 0 and inventory_tag_status == "Annotated":
        return "annotated_zero_clauses"

    return "success"


def _write_telemetry(
    telemetry_path: Path,
    *,
    run_id: str,
    doc_id: str,
    attempt: int,
    phase: str,
    status: str,
    started_at: str,
    ended_at: str,
    duration_ms: int,
    http_status: int | None = None,
    exception_class: str | None = None,
    tls_mode: str = "",
    response_path: str | None = None,
    note: str | None = None,
) -> None:
    """Append a telemetry event."""
    event = {
        "run_id": run_id,
        "doc_id": doc_id,
        "attempt": attempt,
        "phase": phase,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "http_status": http_status,
        "exception_class": exception_class,
        "tls_mode": tls_mode,
        "response_path": response_path,
        "note": note,
    }
    with telemetry_path.open("a") as f:
        f.write(json.dumps(event) + "\n")


def _write_raw_payload(
    raw_dir: Path,
    doc_id: str,
    payload: dict[str, Any],
    *,
    overwrite: bool = True,
) -> tuple[Path, str]:
    """Write raw API payload to raw/{doc_id}.json. Returns (path, sha256)."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"{doc_id}.json"
    data = json.dumps(payload, indent=2).encode()
    sha = hashlib.sha256(data).hexdigest()
    target.write_bytes(data)
    return target, sha


def _write_artifact(
    artifacts_dir: Path,
    doc_id: str,
    attempt: int,
    payload: dict[str, Any] | None,
    error_msg: str | None = None,
) -> None:
    """Write per-attempt artifact for debugging."""
    doc_dir = artifacts_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    if payload is not None:
        artifact_path = doc_dir / f"attempt-{attempt}-response.json"
        artifact_path.write_text(json.dumps(payload, indent=2))
    elif error_msg:
        failure_path = doc_dir / "failure.txt"
        with failure_path.open("a") as f:
            f.write(f"attempt-{attempt}: {error_msg}\n")


def generate_summary(
    records: list[dict[str, Any]],
    *,
    selected_total: int,
    skipped_via_resume: int,
) -> dict[str, Any]:
    """Generate run summary from terminal records."""
    status_counts: dict[str, int] = {}
    retry_dist: dict[int, int] = {}
    all_raw_labels: set[str] = set()
    cac_candidate_count = 0
    country_counts: dict[str, int] = {}
    country_instrument_counts: dict[str, dict[str, int]] = {}

    for r in records:
        s = r.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

        attempts = r.get("attempts_used", 1)
        retry_dist[attempts] = retry_dist.get(attempts, 0) + 1

        for label in r.get("raw_clause_labels", []):
            all_raw_labels.add(label)

        if r.get("cac_candidate"):
            cac_candidate_count += 1

        country = r.get("country", "Unknown")
        country_counts[country] = country_counts.get(country, 0) + 1

        instrument = r.get("instrument_type", "Unknown")
        if country not in country_instrument_counts:
            country_instrument_counts[country] = {}
        ci = country_instrument_counts[country]
        ci[instrument] = ci.get(instrument, 0) + 1

    known_prefixes = [_CAC_MODIFICATION_PREFIX, _CAC_ACCELERATION_PREFIX]
    unmapped = sorted(
        lbl for lbl in all_raw_labels if not any(lbl.startswith(p) for p in known_prefixes)
    )

    return {
        "selected_total": selected_total,
        "new_attempted": len(records) - skipped_via_resume,
        "skipped_via_resume": skipped_via_resume,
        "terminal_total": len(records),
        "status_counts": status_counts,
        "retry_distribution": {str(k): v for k, v in sorted(retry_dist.items())},
        "zero_clause_on_annotated_count": status_counts.get("annotated_zero_clauses", 0),
        "distinct_raw_labels": sorted(all_raw_labels),
        "unmapped_labels": unmapped,
        "cac_candidate_count": cac_candidate_count,
        "counts_by_country": dict(sorted(country_counts.items())),
        "counts_by_country_instrument": {
            k: dict(sorted(v.items())) for k, v in sorted(country_instrument_counts.items())
        },
    }


def write_cac_candidates_csv(
    records: list[dict[str, Any]],
    output_path: Path,
) -> int:
    """Write CAC candidate records to CSV. Returns count written."""
    candidates = [r for r in records if r.get("cac_candidate")]

    fieldnames = [
        "doc_id",
        "document_title",
        "country",
        "instrument_type",
        "clause_count",
        "cac_modification_labels",
        "cac_acceleration_labels",
        "source_url",
        "api_url",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in candidates:
            row = {
                "doc_id": r["doc_id"],
                "document_title": r.get("document_title", ""),
                "country": r.get("country", ""),
                "instrument_type": r.get("instrument_type", ""),
                "clause_count": r.get("clause_count", 0),
                "cac_modification_labels": "; ".join(r.get("cac_modification_labels", [])),
                "cac_acceleration_labels": "; ".join(r.get("cac_acceleration_labels", [])),
                "source_url": r.get("source_url", ""),
                "api_url": r.get("api_url", ""),
            }
            writer.writerow(row)

    return len(candidates)


def run_annotations_harvest(
    *,
    inventory_path: Path,
    output_dir: Path,
    run_id: str,
    annotated_only: bool = True,
    doc_ids: list[str] | None = None,
    limit: int | None = None,
    insecure: bool = False,
    timeout: int = 60,
    max_retries: int = 3,
    delay: float = 1.0,
    consecutive_failures_pause: int = 3,
    consecutive_failures_abort: int = 8,
    zero_clause_early_abort_count: int = 10,
    zero_clause_early_abort_window: int = 20,
    zero_clause_rate_threshold: float = 0.40,
    zero_clause_rate_min_docs: int = 50,
) -> dict[str, Any]:
    """Run the PDIP annotations harvest.

    Returns a summary dict suitable for JSON serialization.
    """
    # Load and validate inventory
    all_rows = load_inventory(inventory_path, annotated_only=annotated_only)
    run_preflight(all_rows, doc_ids=doc_ids)

    # Filter to specific doc_ids if requested
    if doc_ids:
        id_set = set(doc_ids)
        target_rows = [r for r in all_rows if r["id"] in id_set]
        # Preserve doc_ids order
        id_order = {did: i for i, did in enumerate(doc_ids)}
        target_rows.sort(key=lambda r: id_order.get(r["id"], 0))
    else:
        target_rows = all_rows

    # Apply limit in stable inventory order
    if limit is not None:
        target_rows = target_rows[:limit]

    selected_total = len(target_rows)

    # Setup output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    artifacts_dir = output_dir / "artifacts"
    annotations_path = output_dir / "annotations.jsonl"
    telemetry_path = output_dir / "telemetry.jsonl"
    summary_path = output_dir / "summary.json"
    cac_csv_path = output_dir / "cac_candidates.csv"

    # Resume: load already-completed doc_ids
    completed_ids = load_completed_ids(annotations_path)
    skipped_via_resume = 0

    # Create session
    session, tls_info = _make_session(insecure=insecure, timeout=timeout)

    # Track all terminal records (including resumed ones)
    all_records: list[dict[str, Any]] = []

    # Re-read existing records for summary generation, filtered to current target set
    target_ids = {r["id"] for r in target_rows}
    if annotations_path.exists():
        with annotations_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                with contextlib.suppress(json.JSONDecodeError):
                    record = json.loads(line)
                    if record.get("doc_id") in target_ids:
                        all_records.append(record)

    # Circuit breaker state
    consecutive_transport_failures = 0
    aborted = False
    abort_reason = ""

    # Zero-clause tracking — seed from resumed records so gate isn't bypassed
    zero_clause_count = sum(1 for r in all_records if r.get("status") == "annotated_zero_clauses")
    docs_processed = len(all_records)

    for row in target_rows:
        doc_id = row["id"]

        if doc_id in completed_ids:
            skipped_via_resume += 1
            continue

        docs_processed += 1
        doc_start = datetime.now(UTC).isoformat()
        t_start = time.monotonic()

        document_url = f"{PDIP_BASE_URL}/pdf/{doc_id}/"
        api_url = PDIP_DETAILS_URL.format(doc_id=doc_id)

        best_payload: dict[str, Any] | None = None
        best_status = "failed_request"
        best_error: str | None = None
        attempts_used = 0

        for attempt in range(1, max_retries + 1):
            attempts_used = attempt
            attempt_start = datetime.now(UTC).isoformat()
            at_start = time.monotonic()

            try:
                payload, http_status, error_msg = _fetch_details(session, doc_id, timeout=timeout)
            except Exception as exc:
                elapsed = int((time.monotonic() - at_start) * 1000)
                attempt_end = datetime.now(UTC).isoformat()
                _write_telemetry(
                    telemetry_path,
                    run_id=run_id,
                    doc_id=doc_id,
                    attempt=attempt,
                    phase="fetch",
                    status="exception",
                    started_at=attempt_start,
                    ended_at=attempt_end,
                    duration_ms=elapsed,
                    exception_class=type(exc).__name__,
                    tls_mode=tls_info["tls_mode"],
                    note=str(exc),
                )
                _write_artifact(artifacts_dir, doc_id, attempt, None, str(exc))
                best_error = str(exc)
                best_status = "failed_request"
                if attempt < max_retries:
                    time.sleep(delay * attempt)
                continue

            elapsed = int((time.monotonic() - at_start) * 1000)
            attempt_end = datetime.now(UTC).isoformat()

            status = _classify_status(
                payload,
                http_status,
                error_msg,
                inventory_tag_status=row["tag_status"],
                attempt=attempt,
            )

            _write_artifact(artifacts_dir, doc_id, attempt, payload, error_msg)
            _write_telemetry(
                telemetry_path,
                run_id=run_id,
                doc_id=doc_id,
                attempt=attempt,
                phase="fetch",
                status=status,
                started_at=attempt_start,
                ended_at=attempt_end,
                duration_ms=elapsed,
                http_status=http_status,
                tls_mode=tls_info["tls_mode"],
                response_path=str(raw_dir / f"{doc_id}.json") if payload else None,
            )

            best_payload = payload
            best_status = status
            best_error = error_msg

            # Don't retry on terminal-good or stable-content states
            if status == "success":
                break
            if status == "not_found":
                break
            if status == "annotated_zero_clauses":
                # Retry once for zero-clause
                if attempt >= 2:
                    break
                time.sleep(delay)
                continue
            if status in _TRANSPORT_FAILURE_STATUSES and attempt < max_retries:
                time.sleep(delay * attempt)
                continue
            break

        # Build terminal record
        doc_end = datetime.now(UTC).isoformat()
        doc_duration_ms = int((time.monotonic() - t_start) * 1000)

        # Write raw payload if we got one
        payload_sha = None
        raw_path_str = None
        if best_payload is not None:
            raw_path, payload_sha = _write_raw_payload(
                raw_dir, doc_id, best_payload, overwrite=True
            )
            raw_path_str = str(raw_path)

        # Extract labels
        label_info: dict[str, Any]
        if best_payload is not None:
            label_info = extract_labels(best_payload.get("clauses", []))
        else:
            label_info = {
                "clause_count": 0,
                "raw_clause_labels": [],
                "cac_modification_labels": [],
                "cac_acceleration_labels": [],
                "cac_candidate": False,
            }

        terminal_record: dict[str, Any] = {
            "run_id": run_id,
            "doc_id": doc_id,
            "document_url": document_url,
            "api_url": api_url,
            "attempts_used": attempts_used,
            "status": best_status,
            "started_at": doc_start,
            "ended_at": doc_end,
            "duration_ms": doc_duration_ms,
            "inventory_tag_status": row["tag_status"],
            "country": row.get("country", ""),
            "instrument_type": row.get("instrument_type", ""),
            "document_title": row.get("document_title", ""),
            "source_url": best_payload.get("source_url", "") if best_payload else "",
            "clause_count": label_info["clause_count"],
            "raw_clause_labels": label_info["raw_clause_labels"],
            "cac_modification_labels": label_info["cac_modification_labels"],
            "cac_acceleration_labels": label_info["cac_acceleration_labels"],
            "cac_candidate": label_info["cac_candidate"],
            "payload_sha256": payload_sha,
            "raw_payload_path": raw_path_str,
            "tls_mode": tls_info["tls_mode"],
            "tls_verify": tls_info["tls_verify"],
            "tls_reason": tls_info["tls_reason"],
            "error_message": best_error,
        }

        # Append terminal record
        with annotations_path.open("a") as f:
            f.write(json.dumps(terminal_record) + "\n")

        all_records.append(terminal_record)
        completed_ids.add(doc_id)

        # Circuit breaker: transport failures only
        if best_status in _TRANSPORT_FAILURE_STATUSES:
            consecutive_transport_failures += 1

            if consecutive_transport_failures == consecutive_failures_pause:
                log.warning(
                    "Circuit breaker: %d consecutive transport failures, "
                    "pausing 60s and rebuilding session",
                    consecutive_transport_failures,
                )
                time.sleep(60)
                session, tls_info = _make_session(insecure=insecure, timeout=timeout)

            if consecutive_transport_failures >= consecutive_failures_abort:
                abort_reason = (
                    f"Circuit breaker: {consecutive_transport_failures} "
                    f"consecutive transport failures"
                )
                log.error(abort_reason)
                aborted = True
                break
        else:
            consecutive_transport_failures = 0

        # Zero-clause anomaly gate
        if best_status == "annotated_zero_clauses":
            zero_clause_count += 1

            # Early window check
            if (
                docs_processed <= zero_clause_early_abort_window
                and zero_clause_count > zero_clause_early_abort_count
            ):
                abort_reason = (
                    f"Zero-clause anomaly gate: {zero_clause_count}/{docs_processed} "
                    f"in first {zero_clause_early_abort_window} docs"
                )
                log.error(abort_reason)
                aborted = True
                break

            # Rate check after minimum docs
            if docs_processed >= zero_clause_rate_min_docs:
                rate = zero_clause_count / docs_processed
                if rate > zero_clause_rate_threshold:
                    abort_reason = (
                        f"Zero-clause anomaly gate: rate {rate:.1%} > "
                        f"{zero_clause_rate_threshold:.0%} after {docs_processed} docs"
                    )
                    log.error(abort_reason)
                    aborted = True
                    break

        if delay > 0 and not aborted:
            time.sleep(delay)

    # Generate summary
    summary = generate_summary(
        all_records,
        selected_total=selected_total,
        skipped_via_resume=skipped_via_resume,
    )
    summary["run_id"] = run_id
    summary["aborted"] = aborted
    summary["abort_reason"] = abort_reason
    summary["tls_mode"] = tls_info["tls_mode"]

    # Write summary
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2))

    # Write CAC candidates CSV
    cac_count = write_cac_candidates_csv(all_records, cac_csv_path)
    summary["cac_candidates_exported"] = cac_count

    return summary
