# src/corpus/extraction/run_manifest.py
"""Run manifest and per-family completion protocol.

Each extraction run uses a run_id directory. Each family within the run
gets its own subdirectory with a COMPLETE.json sentinel written last.

IMPORTANT: The manifest uses load-modify-save without locking. Only one
process should modify the manifest at a time. This is safe because
families are processed sequentially within a session. If parallel
processing is needed in the future, add file locking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — used at runtime in function bodies


@dataclass
class RunManifest:
    run_id: str
    families_completed: list[str] = field(default_factory=list)
    families_in_progress: list[str] = field(default_factory=list)
    families_pending: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


def create_manifest(
    run_dir: Path,
    run_id: str,
    families: list[str],
) -> RunManifest:
    """Create a new run manifest."""
    now = datetime.now(UTC).isoformat()
    manifest = RunManifest(
        run_id=run_id,
        families_pending=list(families),
        created_at=now,
        updated_at=now,
    )
    _save(run_dir, manifest)
    return manifest


def load_manifest(run_dir: Path) -> RunManifest:
    """Load manifest from run directory."""
    path = run_dir / "RUN_MANIFEST.json"
    data = json.loads(path.read_text())
    known_fields = {f for f in RunManifest.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return RunManifest(**filtered)


def mark_family_in_progress(run_dir: Path, family: str) -> None:
    """Mark a family as in-progress."""
    m = load_manifest(run_dir)
    if family in m.families_pending:
        m.families_pending.remove(family)
    if family not in m.families_in_progress:
        m.families_in_progress.append(family)
    _save(run_dir, m)


def mark_family_complete(run_dir: Path, family: str) -> None:
    """Mark a family as complete. Writes COMPLETE.json sentinel."""
    m = load_manifest(run_dir)
    if family in m.families_in_progress:
        m.families_in_progress.remove(family)
    if family not in m.families_completed:
        m.families_completed.append(family)
    _save(run_dir, m)

    # Write per-family COMPLETE.json sentinel
    family_dir = run_dir / family
    family_dir.mkdir(parents=True, exist_ok=True)
    completion = {
        "family": family,
        "completed_at": datetime.now(UTC).isoformat(),
        "run_id": m.run_id,
    }
    sentinel_path = family_dir / "COMPLETE.json"
    part_path = sentinel_path.with_suffix(".json.part")
    part_path.write_text(json.dumps(completion, indent=2) + "\n")
    part_path.rename(sentinel_path)


def is_family_complete(run_dir: Path, family: str) -> bool:
    """Check if a family has been completed."""
    return (run_dir / family / "COMPLETE.json").exists()


def _save(run_dir: Path, manifest: RunManifest) -> None:
    """Save manifest to disk using .part -> rename pattern."""
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest.updated_at = datetime.now(UTC).isoformat()
    data = {
        "run_id": manifest.run_id,
        "families_completed": manifest.families_completed,
        "families_in_progress": manifest.families_in_progress,
        "families_pending": manifest.families_pending,
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
    }
    target = run_dir / "RUN_MANIFEST.json"
    part = target.with_suffix(".json.part")
    part.write_text(json.dumps(data, indent=2) + "\n")
    part.rename(target)
