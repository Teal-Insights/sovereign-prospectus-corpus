"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_fixture_pdf() -> None:
    """Generate the fixture PDF if it doesn't exist."""
    fixture_pdf = Path(__file__).parent / "fixtures" / "sample.pdf"
    if not fixture_pdf.exists():
        from tests.fixtures.make_sample_pdf import main

        main()
