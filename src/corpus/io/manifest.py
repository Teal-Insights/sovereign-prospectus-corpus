"""Atomic, resume-safe helpers for source manifest JSONL files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from corpus.io.safe_write import safe_write


class ManifestConflictError(RuntimeError):
    """Raised when one storage key resolves to different downloaded bytes."""


def portable_data_path(path: Path, *, data_root: Path | None = None) -> str:
    """Return a portable path only when the caller identifies its data root."""
    if data_root is not None:
        try:
            relative = path.resolve().relative_to(data_root.resolve())
        except ValueError:
            pass
        else:
            return (Path("data") / relative).as_posix()
    return str(path)


def upsert_manifest_record(manifest_path: Path, record: dict[str, Any]) -> None:
    """Atomically upsert one manifest record by storage key."""
    upsert_manifest_records(manifest_path, [record])


def upsert_manifest_records(manifest_path: Path, new_records: list[dict[str, Any]]) -> None:
    """Atomically upsert a batch of manifest records with one file rewrite."""
    if not new_records:
        return

    records: list[dict[str, Any]] = []
    by_key: dict[str, int] = {}
    if manifest_path.exists():
        with manifest_path.open() as manifest:
            for line in manifest:
                if not line.strip():
                    continue
                current = json.loads(line)
                current_key = current.get("storage_key", "")
                if current_key in by_key:
                    prior = records[by_key[current_key]]
                    prior_hash = prior.get("file_hash")
                    current_hash = current.get("file_hash")
                    if prior_hash and current_hash and prior_hash != current_hash:
                        raise ManifestConflictError(
                            f"Conflicting hashes in manifest for {current_key}"
                        )
                    records[by_key[current_key]] = {**prior, **current}
                    continue
                by_key[current_key] = len(records)
                records.append(current)

    for record in new_records:
        storage_key = record.get("storage_key", "")
        if not storage_key:
            raise ValueError("Manifest record is missing storage_key")
        if storage_key in by_key:
            existing = records[by_key[storage_key]]
            existing_hash = existing.get("file_hash")
            new_hash = record.get("file_hash")
            if existing_hash and new_hash and existing_hash != new_hash:
                raise ManifestConflictError(f"Conflicting hashes for {storage_key}")
            records[by_key[storage_key]] = {**existing, **record}
        else:
            by_key[storage_key] = len(records)
            records.append(record)

    content = "".join(json.dumps(item, sort_keys=True) + "\n" for item in records).encode()
    if manifest_path.exists() and manifest_path.read_bytes() == content:
        return
    safe_write(manifest_path, content, overwrite=True)
