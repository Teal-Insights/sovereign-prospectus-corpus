# Download Run Reports + Status Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared run report generation and a `corpus status` command so operators can see what failed, why, and how to retry.

**Architecture:** A `reporting.py` module provides `write_run_report()` (called by each adapter after download) and `get_source_status()` (called by CLI status command). Status works by diffing discovery JSONL against manifest JSONL — no DB needed.

**Tech Stack:** Python 3.12, Click CLI, JSONL file parsing.

**Spec:** `docs/superpowers/specs/2026-03-26-run-reports-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/corpus/reporting.py` | Run reports + status diffing |
| Create | `tests/test_reporting.py` | Unit tests |
| Modify | `src/corpus/cli.py` | Add `corpus status [source]` command |
| Modify | `src/corpus/sources/edgar.py` | Call `write_run_report` after download |
| Modify | `src/corpus/sources/nsm.py` | Call `write_run_report` after download |

---

### Task 1: Run Report Generation

**Files:**
- Create: `src/corpus/reporting.py`
- Create: `tests/test_reporting.py`

Build `write_run_report()` — reads telemetry JSONL to find failures, writes a human-readable report file.

- [ ] **Step 1: Write failing tests**

Create `tests/test_reporting.py`:

```python
"""Tests for download run reports and status."""

from __future__ import annotations

import json
from pathlib import Path


class TestWriteRunReport:
    """Tests for run report generation."""

    def test_writes_report_file(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()
        log_file = telemetry_dir / "edgar_edgar-test.jsonl"
        log_file.write_text(
            json.dumps({"run_id": "edgar-test", "document_id": "doc-1", "step": "download", "duration_ms": 100, "status": "success", "timestamp": "2026-03-26T00:00:00Z"}) + "\n"
            + json.dumps({"run_id": "edgar-test", "document_id": "doc-2", "step": "download", "duration_ms": 200, "status": "error", "error_message": "Connection reset", "timestamp": "2026-03-26T00:00:01Z"}) + "\n"
        )

        stats = {"downloaded": 1, "skipped": 0, "failed": 1, "total_in_discovery": 2, "aborted": False}

        report_path = write_run_report(
            source="edgar",
            run_id="edgar-test",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        assert report_path.exists()
        content = report_path.read_text()
        assert "Downloaded: 1" in content
        assert "Failed: 1" in content
        assert "doc-2" in content
        assert "Connection reset" in content

    def test_report_includes_retry_command(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        stats = {"downloaded": 5, "skipped": 0, "failed": 0, "total_in_discovery": 5, "aborted": False}

        report_path = write_run_report(
            source="edgar",
            run_id="test-run",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        content = report_path.read_text()
        assert "corpus download edgar" in content

    def test_report_shows_aborted_warning(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        stats = {"downloaded": 3, "skipped": 0, "failed": 10, "total_in_discovery": 100, "aborted": True}

        report_path = write_run_report(
            source="nsm",
            run_id="test-run",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        content = report_path.read_text()
        assert "ABORTED" in content

    def test_report_handles_missing_telemetry(self, tmp_path: Path) -> None:
        from corpus.reporting import write_run_report

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()
        # No telemetry file exists

        stats = {"downloaded": 5, "skipped": 0, "failed": 2, "total_in_discovery": 7, "aborted": False}

        report_path = write_run_report(
            source="edgar",
            run_id="no-telemetry",
            stats=stats,
            telemetry_dir=telemetry_dir,
        )

        assert report_path.exists()
        content = report_path.read_text()
        assert "Failed: 2" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.reporting'`

- [ ] **Step 3: Implement write_run_report**

Create `src/corpus/reporting.py`:

```python
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
_DISCOVERY_ID_KEYS: dict[str, str] = {
    "nsm": "disclosure_id",
    "edgar": "native_id",
    "pdip": "native_id",
}

# Discovery file paths by convention
_DISCOVERY_PATHS: dict[str, str] = {
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
            lines.append(f"    {f['document_id']:40s}  {f['status']:15s}  {f.get('error_message', '')}")

    lines.append("")
    lines.append("  To retry failed downloads:")
    lines.append(f"    corpus download {source} --discovery-file {_DISCOVERY_PATHS.get(source, f'data/{source}_discovery.jsonl')}")
    lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


def _extract_failures(
    telemetry_dir: Path, source: str, run_id: str,
) -> list[dict[str, Any]]:
    """Parse telemetry JSONL for non-success download entries."""
    failures: list[dict[str, Any]] = []

    # Try both naming conventions: {source}_{run_id}.jsonl
    for pattern in [f"{source}_{run_id}.jsonl", f"{source}_*.jsonl"]:
        for log_file in telemetry_dir.glob(pattern):
            try:
                with log_file.open() as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        if (
                            entry.get("run_id") == run_id
                            and entry.get("step") == "download"
                            and entry.get("status") not in ("success", "success_after_429")
                        ):
                            failures.append(entry)
            except (json.JSONDecodeError, OSError):
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
        discovery_path = Path(_DISCOVERY_PATHS.get(source, f"data/{source}_discovery.jsonl"))

    if not discovery_path.exists():
        return {"source": source, "status": "not_discovered"}

    id_key = _DISCOVERY_ID_KEYS.get(source, "native_id")
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
                    entry = json.loads(line)
                    doc_id = entry.get("document_id", "")
                    if doc_id in outstanding_ids and entry.get("status") not in ("success", "success_after_429"):
                        last_errors[doc_id] = entry.get("error_message", entry.get("status", ""))
        except (json.JSONDecodeError, OSError):
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
                f"  {s['source'].upper():8s} {s['manifest_count']:>5d} / {s['discovery_count']:<5d} downloaded{detail}"
            )
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/corpus/reporting.py tests/test_reporting.py && uv run ruff format --check src/corpus/reporting.py tests/test_reporting.py`

- [ ] **Step 6: Commit**

```bash
git add src/corpus/reporting.py tests/test_reporting.py
git commit -m "feat: add run report generation

write_run_report() parses telemetry JSONL for failure details,
writes human-readable report to data/telemetry/.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Source Status Diffing

**Files:**
- Modify: `src/corpus/reporting.py` (already created in Task 1)
- Test: `tests/test_reporting.py`

Add tests for `get_source_status()` and `format_status_summary()` — the functions are already implemented in Task 1, we just need to test them.

- [ ] **Step 1: Write tests for get_source_status**

Append to `tests/test_reporting.py`:

```python
class TestGetSourceStatus:
    """Tests for source status diffing."""

    def test_diffs_discovery_vs_manifest(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(
            "\n".join(
                json.dumps({"native_id": f"doc-{i}", "title": f"Doc {i}"})
                for i in range(5)
            ) + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        manifest = manifest_dir / "edgar_manifest.jsonl"
        manifest.write_text(
            "\n".join(
                json.dumps({"native_id": f"doc-{i}", "file_path": f"data/original/edgar__doc-{i}.htm"})
                for i in range(3)
            ) + "\n"
        )

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["source"] == "edgar"
        assert status["discovery_count"] == 5
        assert status["manifest_count"] == 3
        assert status["outstanding_count"] == 2
        outstanding_ids = {o["native_id"] for o in status["outstanding"]}
        assert outstanding_ids == {"doc-3", "doc-4"}

    def test_not_discovered(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        status = get_source_status(
            "pdip",
            discovery_path=tmp_path / "nonexistent.jsonl",
            manifest_dir=tmp_path,
            telemetry_dir=tmp_path,
        )

        assert status["status"] == "not_discovered"

    def test_empty_manifest(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(
            json.dumps({"native_id": "doc-1", "title": "Doc 1"}) + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        # No manifest file

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["discovery_count"] == 1
        assert status["manifest_count"] == 0
        assert status["outstanding_count"] == 1

    def test_enriches_with_telemetry_errors(self, tmp_path: Path) -> None:
        from corpus.reporting import get_source_status

        discovery = tmp_path / "edgar_discovery.jsonl"
        discovery.write_text(
            json.dumps({"native_id": "fail-doc", "title": "Failed"}) + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()
        log = telemetry_dir / "edgar_test-run.jsonl"
        log.write_text(
            json.dumps({"run_id": "test-run", "document_id": "fail-doc", "step": "download", "duration_ms": 100, "status": "error", "error_message": "HTTP 403", "timestamp": "2026-03-26T00:00:00Z"}) + "\n"
        )

        status = get_source_status(
            "edgar",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=telemetry_dir,
        )

        assert status["outstanding"][0]["last_error"] == "HTTP 403"

    def test_nsm_uses_disclosure_id(self, tmp_path: Path) -> None:
        """NSM discovery uses disclosure_id, not native_id."""
        from corpus.reporting import get_source_status

        discovery = tmp_path / "nsm_discovery.jsonl"
        discovery.write_text(
            json.dumps({"disclosure_id": "abc-123", "headline": "Kenya Note"}) + "\n"
            + json.dumps({"disclosure_id": "def-456", "headline": "Ghana Bond"}) + "\n"
        )

        manifest_dir = tmp_path / "manifests"
        manifest_dir.mkdir()
        manifest = manifest_dir / "nsm_manifest.jsonl"
        manifest.write_text(
            json.dumps({"native_id": "abc-123"}) + "\n"
        )

        status = get_source_status(
            "nsm",
            discovery_path=discovery,
            manifest_dir=manifest_dir,
            telemetry_dir=tmp_path,
        )

        assert status["discovery_count"] == 2
        assert status["manifest_count"] == 1
        assert status["outstanding_count"] == 1
        assert status["outstanding"][0]["native_id"] == "def-456"


class TestFormatStatusSummary:
    """Tests for cross-source status formatting."""

    def test_formats_multiple_sources(self) -> None:
        from corpus.reporting import format_status_summary

        statuses = [
            {"source": "nsm", "status": "ok", "discovery_count": 899, "manifest_count": 642, "outstanding_count": 257, "outstanding": []},
            {"source": "edgar", "status": "ok", "discovery_count": 3306, "manifest_count": 3301, "outstanding_count": 5, "outstanding": []},
            {"source": "pdip", "status": "not_discovered"},
        ]

        output = format_status_summary(statuses)

        assert "NSM" in output
        assert "642" in output
        assert "899" in output
        assert "EDGAR" in output
        assert "3301" in output
        assert "PDIP" in output
        assert "not discovered" in output
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: All 10 tests PASS (4 from Task 1 + 6 new)

- [ ] **Step 3: Lint**

Run: `uv run ruff check src/corpus/reporting.py tests/test_reporting.py && uv run ruff format --check src/corpus/reporting.py tests/test_reporting.py`

- [ ] **Step 4: Commit**

```bash
git add tests/test_reporting.py
git commit -m "test: add source status diffing and summary tests

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: CLI Status Command

**Files:**
- Modify: `src/corpus/cli.py`
- Test: `tests/test_reporting.py`

Add `corpus status [source]` CLI command.

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_reporting.py`:

```python
class TestStatusCli:
    """Tests for corpus status CLI command."""

    def test_status_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0
        assert "source" in result.output.lower()

    def test_status_no_args_shows_summary(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        mock_statuses = [
            {"source": "nsm", "status": "ok", "discovery_count": 10, "manifest_count": 8, "outstanding_count": 2, "outstanding": []},
            {"source": "edgar", "status": "not_discovered"},
        ]

        with patch("corpus.reporting.get_source_status", side_effect=mock_statuses):
            runner = CliRunner()
            result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "NSM" in result.output

    def test_status_with_source(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        mock_status = {
            "source": "edgar",
            "status": "ok",
            "discovery_count": 100,
            "manifest_count": 95,
            "outstanding_count": 5,
            "outstanding": [
                {"native_id": "doc-1", "title": "Test Doc", "last_error": "HTTP 403"},
            ],
        }

        with patch("corpus.reporting.get_source_status", return_value=mock_status):
            runner = CliRunner()
            result = runner.invoke(cli, ["status", "edgar"])

        assert result.exit_code == 0
        assert "EDGAR" in result.output
        assert "doc-1" in result.output
        assert "HTTP 403" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reporting.py::TestStatusCli -v`
Expected: FAIL — no `status` command in CLI

- [ ] **Step 3: Add status command to CLI**

Add to `src/corpus/cli.py`, before the `# ── Entry point` section:

```python
# ── Status command ─────────────────────────────────────────────────


@cli.command()
@click.argument("source", required=False, default=None)
def status(source: str | None) -> None:
    """Show download status. Optionally filter by SOURCE (nsm, edgar, pdip)."""
    from corpus.reporting import (
        _DISCOVERY_PATHS,
        format_status_summary,
        get_source_status,
    )

    sources = [source] if source else list(_DISCOVERY_PATHS.keys())

    if source:
        # Detailed per-source view
        s = get_source_status(source)
        if s.get("status") == "not_discovered":
            click.echo(f"  {source.upper()}: not discovered")
            return

        click.echo(
            f"  {s['source'].upper()}: {s['manifest_count']} / {s['discovery_count']} "
            f"downloaded ({s['outstanding_count']} outstanding)"
        )

        if s["outstanding"]:
            click.echo("")
            click.echo(f"  Outstanding ({s['outstanding_count']}):")
            for item in s["outstanding"]:
                error = f"  last error: {item['last_error']}" if item.get("last_error") else ""
                click.echo(f"    {item['native_id']:40s}  {item['title'][:40]:40s}{error}")

            click.echo("")
            discovery_path = _DISCOVERY_PATHS.get(source, f"data/{source}_discovery.jsonl")
            click.echo(f"  To retry: corpus download {source} --discovery-file {discovery_path}")
    else:
        # Cross-source summary
        statuses = [get_source_status(s) for s in sources]
        click.echo(format_status_summary(statuses))
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_reporting.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/corpus/cli.py tests/test_reporting.py && uv run ruff format --check src/corpus/cli.py tests/test_reporting.py`

- [ ] **Step 6: Commit**

```bash
git add src/corpus/cli.py tests/test_reporting.py
git commit -m "feat: add corpus status command

corpus status — cross-source summary
corpus status edgar — per-source detail with outstanding items

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Integrate with Adapters

**Files:**
- Modify: `src/corpus/sources/edgar.py`
- Modify: `src/corpus/sources/nsm.py`
- Modify: `src/corpus/cli.py`

Call `write_run_report()` from the CLI download commands after each adapter finishes.

- [ ] **Step 1: Add report call to EDGAR CLI download**

In `src/corpus/cli.py`, in the `edgar` download command, after the `stats = run_edgar_download(...)` call and before the `click.echo` summary, add:

```python
    from corpus.reporting import write_run_report

    report_path = write_run_report(
        source="edgar", run_id=run_id, stats=stats, telemetry_dir=log_dir,
    )
```

And add to the echo output:

```python
    click.echo(f"Report: {report_path}")
```

- [ ] **Step 2: Add report call to NSM CLI download**

In `src/corpus/cli.py`, in the `nsm` download command, after the `stats = run_nsm_download(...)` call and before the `click.echo` summary, add:

```python
    from corpus.reporting import write_run_report

    report_path = write_run_report(
        source="nsm", run_id=run_id, stats=stats, telemetry_dir=log_dir,
    )
```

And add to the echo output:

```python
    click.echo(f"Report: {report_path}")
```

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v --tb=short`
Expected: All tests PASS (no regressions)

- [ ] **Step 4: Lint and typecheck**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run pyright src/corpus/`

- [ ] **Step 5: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: integrate run reports into NSM and EDGAR download commands

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: End-to-End Verification

**Files:** All from Tasks 1-4

- [ ] **Step 1: Run full lint + typecheck + test suite**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run pyright src/corpus/ && uv run pytest -v`
Expected: All pass

- [ ] **Step 2: Test corpus status against real data**

Run: `uv run corpus status`
Expected: Shows NSM and EDGAR counts matching what we downloaded earlier.

Run: `uv run corpus status edgar`
Expected: Shows per-source detail. If all 3306 downloaded, should show 0 outstanding (or 5 outstanding if the test-run manifest is still there).

- [ ] **Step 3: Verify report generation with a small test download**

Run: `head -3 data/edgar_discovery.jsonl > /tmp/report_test_discovery.jsonl && CONTACT_EMAIL=lte@tealinsights.com uv run corpus download edgar --discovery-file /tmp/report_test_discovery.jsonl --run-id report-test`
Expected: Download completes, report file created at `data/telemetry/edgar_report-test_report.txt`. Verify report content.
