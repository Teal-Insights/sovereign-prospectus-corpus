"""Atomic file writes with .part -> rename pattern."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class _Writer(Protocol):
    def __call__(self, path: Path, data: bytes) -> None: ...


def _default_writer(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def safe_write(
    target: str | Path,
    data: bytes,
    *,
    overwrite: bool = False,
    _writer: _Writer | None = None,
) -> Path:
    """Write data atomically via .part temp file.

    Writes to ``target.part``, then renames to ``target``.
    Refuses to overwrite existing files unless ``overwrite=True``.
    Cleans up the .part file on failure.
    """
    target = Path(target)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    writer = _writer or _default_writer

    try:
        writer(part, data)
        part.rename(target)
    except Exception:
        part.unlink(missing_ok=True)
        raise

    return target
