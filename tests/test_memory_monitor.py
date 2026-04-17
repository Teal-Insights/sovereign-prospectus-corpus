"""Tests for memory monitoring functions in docling_reparse."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT_PATH = str(Path(__file__).resolve().parent.parent / "scripts" / "docling_reparse.py")


def _load_module():
    """Load docling_reparse as a module without __main__ side effects."""
    spec = importlib.util.spec_from_file_location("docling_reparse", SCRIPT_PATH)
    assert spec is not None, f"Could not find module spec for {SCRIPT_PATH}"
    assert spec.loader is not None, "Module spec has no loader"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_get_total_python_rss_gb_includes_supervisor():
    """RSS sum must include the supervisor process, not just workers."""
    mod = _load_module()

    mock_pool = MagicMock()
    mock_pool._processes = {100: None, 200: None}

    def fake_process(pid):
        p = MagicMock()
        mem = MagicMock()
        rss_map = {100: 2 * 1024**3, 200: 3 * 1024**3, os.getpid(): 1 * 1024**3}
        mem.rss = rss_map.get(pid, 0)
        p.memory_info.return_value = mem
        return p

    with patch("psutil.Process", side_effect=fake_process):
        total = mod.get_total_python_rss_gb(mock_pool)
        # 2 + 3 + 1 = 6 GB
        assert abs(total - 6.0) < 0.01


def test_get_total_python_rss_gb_psutil_failure_counts_as_8gb():
    """If psutil can't read a PID, count it as 8 GB (fail-safe)."""
    mod = _load_module()

    mock_pool = MagicMock()
    mock_pool._processes = {100: None, 200: None}

    def fake_process(pid):
        if pid == 200:
            raise OSError("Permission denied")
        p = MagicMock()
        mem = MagicMock()
        mem.rss = 2 * 1024**3  # 2 GB for readable PIDs
        p.memory_info.return_value = mem
        return p

    with patch("psutil.Process", side_effect=fake_process):
        total = mod.get_total_python_rss_gb(mock_pool)
        # PID 100: 2 GB, PID 200: 8 GB (fail-safe), supervisor: 2 GB
        assert total >= 10.0


def test_get_total_python_rss_gb_empty_pool():
    """Empty pool should still include supervisor RSS."""
    mod = _load_module()

    mock_pool = MagicMock()
    mock_pool._processes = {}

    def fake_process(pid):
        p = MagicMock()
        mem = MagicMock()
        mem.rss = 1 * 1024**3
        p.memory_info.return_value = mem
        return p

    with patch("psutil.Process", side_effect=fake_process):
        total = mod.get_total_python_rss_gb(mock_pool)
        assert abs(total - 1.0) < 0.01  # Just supervisor
