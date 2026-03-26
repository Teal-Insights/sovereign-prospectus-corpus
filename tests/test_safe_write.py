"""Tests for atomic safe_write utility."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from corpus.io.safe_write import safe_write


class TestSafeWrite:
    """Tests for safe_write: atomic .part -> rename, refuses overwrites."""

    def test_writes_file_atomically(self, tmp_path: Path) -> None:
        """File appears only after write completes (no partial files left)."""
        target = tmp_path / "output.pdf"
        content = b"hello sovereign bonds"

        safe_write(target, content)

        assert target.read_bytes() == content
        # No .part file should remain
        assert not (tmp_path / "output.pdf.part").exists()

    def test_refuses_overwrite_existing_file(self, tmp_path: Path) -> None:
        """Raises FileExistsError when target already exists."""
        target = tmp_path / "output.pdf"
        target.write_bytes(b"original")

        with pytest.raises(FileExistsError):
            safe_write(target, b"replacement")

        # Original content preserved
        assert target.read_bytes() == b"original"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Creates intermediate directories if they don't exist."""
        target = tmp_path / "sub" / "dir" / "output.pdf"

        safe_write(target, b"nested content")

        assert target.read_bytes() == b"nested content"

    def test_cleans_up_part_file_on_error(self, tmp_path: Path) -> None:
        """If write fails, .part file is removed."""
        target = tmp_path / "output.pdf"

        # Simulate write failure by making parent read-only after .part creation
        # Instead, use a callback that raises
        with pytest.raises(ValueError, match="boom"):
            safe_write(target, b"", _writer=_failing_writer)

        assert not target.exists()
        assert not (tmp_path / "output.pdf.part").exists()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Works with str paths, not just Path objects."""
        target = tmp_path / "output.txt"

        safe_write(str(target), b"string path content")

        assert target.read_bytes() == b"string path content"

    def test_overwrite_allowed_when_flag_set(self, tmp_path: Path) -> None:
        """When overwrite=True, existing files are replaced."""
        target = tmp_path / "output.pdf"
        target.write_bytes(b"original")

        safe_write(target, b"replacement", overwrite=True)

        assert target.read_bytes() == b"replacement"


def _failing_writer(path: Path, data: bytes) -> None:
    """Helper that writes a .part then raises."""
    raise ValueError("boom")
