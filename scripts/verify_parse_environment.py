#!/usr/bin/env python3
"""Pre-flight verification for overnight Docling parse runs.

Checks Python, venv, dependencies, disk, Docling installation, memory-fix
code, and auto-configures workers/thresholds for detected hardware.

Usage:
    uv run python scripts/verify_parse_environment.py
    uv run python scripts/verify_parse_environment.py --json   # machine-readable
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
INFO = "\033[36mINFO\033[0m"


def check_python_version() -> dict:
    """Python 3.12+ required (Docling dependency resolution fails on 3.14+)."""
    v = sys.version_info
    ok = v.major == 3 and 12 <= v.minor <= 13
    return {
        "name": "Python version",
        "status": "pass" if ok else "fail",
        "value": f"{v.major}.{v.minor}.{v.micro}",
        "expected": "3.12.x or 3.13.x",
    }


def check_venv_location() -> dict:
    """Venv must live outside Dropbox to avoid file lock issues."""
    venv_path = Path(sys.prefix)
    in_dropbox = "Dropbox" in str(venv_path) or "dropbox" in str(venv_path)
    uv_project_env = os.environ.get("UV_PROJECT_ENVIRONMENT", "")
    return {
        "name": "Venv location",
        "status": "fail" if in_dropbox else "pass",
        "value": str(venv_path),
        "expected": "Outside Dropbox (e.g., ~/.local/venvs/)",
        "uv_project_environment": uv_project_env,
    }


def check_dependencies() -> dict:
    """Check that critical packages are installed."""
    missing = []
    versions = {}
    for pkg in ["docling", "psutil", "duckdb", "polars", "click"]:
        try:
            from importlib.metadata import version as pkg_version

            versions[pkg] = pkg_version(pkg)
        except Exception:
            missing.append(pkg)

    return {
        "name": "Dependencies",
        "status": "fail" if missing else "pass",
        "value": versions,
        "missing": missing,
    }


def check_memory_fix_code() -> dict:
    """Verify the memory-fix code is present in docling_reparse.py."""
    script = PROJECT_ROOT / "scripts" / "docling_reparse.py"
    if not script.exists():
        return {
            "name": "Memory fix code",
            "status": "fail",
            "value": "scripts/docling_reparse.py not found",
        }

    content = script.read_text()
    checks = {
        "max_tasks_per_child": "max_tasks_per_child" in content,
        "get_total_python_rss_gb": "get_total_python_rss_gb" in content,
        "memory_ceiling": "memory_ceiling" in content,
        "_throttle_teardown": "_throttle_teardown" in content,
        "_start_memory_watchdog": "_start_memory_watchdog" in content,
    }
    all_present = all(checks.values())
    return {
        "name": "Memory fix code",
        "status": "pass" if all_present else "fail",
        "value": checks,
        "detail": "All safety mechanisms present"
        if all_present
        else "MISSING: " + ", ".join(k for k, v in checks.items() if not v),
    }


def check_disk_space() -> dict:
    """Need at least 10 GB free."""
    usage = shutil.disk_usage(str(PROJECT_ROOT))
    free_gb = usage.free / (1024**3)
    return {
        "name": "Disk space",
        "status": "pass" if free_gb >= 10 else "fail" if free_gb < 5 else "warn",
        "value": f"{free_gb:.1f} GB free",
        "expected": ">= 10 GB",
    }


def check_data_directories() -> dict:
    """Verify PDF source directories exist and have files."""
    dirs = {
        "data/pdfs/pdip": 0,
        "data/original": 0,
    }
    for d in dirs:
        p = PROJECT_ROOT / d
        if p.exists():
            dirs[d] = len(list(p.rglob("*.pdf")))

    total = sum(dirs.values())
    return {
        "name": "PDF source directories",
        "status": "pass" if total > 0 else "fail",
        "value": dirs,
        "total_pdfs": total,
    }


def check_existing_output() -> dict:
    """Check for existing parsed output (resume state)."""
    output_dir = PROJECT_ROOT / "data" / "parsed_docling"
    if not output_dir.exists():
        return {
            "name": "Existing output",
            "status": "info",
            "value": "No output directory — fresh run",
            "completed": 0,
        }

    jsonl_count = len(list(output_dir.glob("*.jsonl")))
    md_count = len(list(output_dir.glob("*.md")))
    summary = output_dir / "_summary.json"
    has_summary = summary.exists()

    return {
        "name": "Existing output",
        "status": "info",
        "value": f"{jsonl_count} JSONL, {md_count} MD"
        + (" (completed)" if has_summary else " (partial — will resume)"),
        "completed": min(jsonl_count, md_count),
        "has_summary": has_summary,
    }


def check_running_processes() -> dict:
    """Check for already-running Docling processes."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "docling_reparse.py"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().split("\n") if result.stdout.strip() else []
        running = len(pids) > 0
    except Exception:
        running = False
        pids = []

    return {
        "name": "Running processes",
        "status": "warn" if running else "pass",
        "value": f"docling_reparse.py already running (PIDs: {', '.join(pids)})"
        if running
        else "No Docling processes running",
    }


def detect_hardware() -> dict:
    """Auto-detect hardware and recommend configuration."""
    import psutil

    cpu_count = os.cpu_count() or 4
    ram_gb = psutil.virtual_memory().total / (1024**3)
    chip = platform.processor() or "unknown"
    machine = platform.machine()

    # Auto-configure based on hardware
    # Formula: workers = min((cores - 2) // 3, 6), ceiling = RAM * 0.75
    workers = max(1, min((cpu_count - 2) // 3, 6))
    ceiling_gb = round(ram_gb * 0.75)
    throttle_gb = round(ceiling_gb * 0.75)

    return {
        "name": "Hardware detection",
        "status": "info",
        "value": {
            "cpu_cores": cpu_count,
            "ram_gb": round(ram_gb, 1),
            "chip": chip,
            "architecture": machine,
        },
        "recommended": {
            "workers": workers,
            "memory_throttle_gb": throttle_gb,
            "memory_ceiling_gb": ceiling_gb,
            "max_tasks_per_child": 10,
        },
        "command": (
            f"caffeinate -d -i -s uv run python scripts/docling_reparse.py "
            f"--workers {workers} --memory-throttle {throttle_gb} "
            f"--memory-ceiling {ceiling_gb} --timeout 900"
        ),
    }


def check_caffeinate() -> dict:
    """Check if caffeinate is running."""
    try:
        result = subprocess.run(["pgrep", "caffeinate"], capture_output=True, text=True)
        running = bool(result.stdout.strip())
    except Exception:
        running = False

    return {
        "name": "Caffeinate",
        "status": "pass" if running else "warn",
        "value": "Running (sleep prevention active)"
        if running
        else "NOT running — machine may sleep during overnight job",
    }


def main() -> None:
    json_mode = "--json" in sys.argv

    checks = [
        check_python_version(),
        check_venv_location(),
        check_dependencies(),
        check_memory_fix_code(),
        check_disk_space(),
        check_data_directories(),
        check_existing_output(),
        check_running_processes(),
        detect_hardware(),
        check_caffeinate(),
    ]

    if json_mode:
        print(json.dumps(checks, indent=2))
        sys.exit(0 if all(c["status"] != "fail" for c in checks) else 1)

    print("=" * 60)
    print("  Docling Overnight Parse — Pre-flight Verification")
    print("=" * 60)
    print()

    failures = 0
    warnings = 0

    for check in checks:
        status = check["status"]
        icon = {"pass": PASS, "fail": FAIL, "warn": WARN, "info": INFO}[status]
        print(f"  [{icon}] {check['name']}")

        if status == "fail":
            failures += 1
        elif status == "warn":
            warnings += 1

        # Print details
        if isinstance(check.get("value"), dict):
            for k, v in check["value"].items():
                print(f"         {k}: {v}")
        else:
            print(f"         {check.get('value', '')}")

        if check.get("detail"):
            print(f"         {check['detail']}")
        if check.get("missing"):
            print(f"         Missing: {', '.join(check['missing'])}")
        if check.get("expected") and status == "fail":
            print(f"         Expected: {check['expected']}")
        print()

    # Hardware recommendation
    hw = next(c for c in checks if c["name"] == "Hardware detection")
    rec = hw["recommended"]
    print("-" * 60)
    print("  Recommended configuration for this machine:")
    print(f"    Workers:          {rec['workers']}")
    print(f"    Memory throttle:  {rec['memory_throttle_gb']} GB")
    print(f"    Memory ceiling:   {rec['memory_ceiling_gb']} GB")
    print(f"    Tasks per child:  {rec['max_tasks_per_child']}")
    print()
    print("  Launch command:")
    print(f"    {hw['command']}")
    print()

    # Existing output / resume info
    output = next(c for c in checks if c["name"] == "Existing output")
    if output.get("completed", 0) > 0 and not output.get("has_summary"):
        pdfs = next(c for c in checks if c["name"] == "PDF source directories")
        total = pdfs.get("total_pdfs", 0)
        done = output["completed"]
        remaining = total - done
        print(f"  Resume: {done} docs already done, ~{remaining} remaining")
        print()

    # Summary
    print("=" * 60)
    if failures:
        print(f"  \033[31m{failures} FAILURE(S) — fix before running\033[0m")
        sys.exit(1)
    elif warnings:
        print(f"  \033[33m{warnings} WARNING(S) — review before running\033[0m")
        sys.exit(0)
    else:
        print("  \033[32mALL CHECKS PASSED — ready to run\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
