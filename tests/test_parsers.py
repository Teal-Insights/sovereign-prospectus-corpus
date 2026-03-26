"""Tests for parser protocol, PyMuPDF adapter, and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from corpus.parsers.base import DocumentParser, ParseResult
from corpus.parsers.pymupdf_parser import PyMuPDFParser
from corpus.parsers.registry import get_parser

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "sample.pdf"


@pytest.fixture(autouse=True)
def _require_fixture_pdf() -> None:
    if not FIXTURE_PDF.exists():
        pytest.skip("fixture PDF not found; generate with tests/fixtures/make_sample_pdf.py")


def test_pymupdf_parser_satisfies_protocol() -> None:
    parser = PyMuPDFParser()
    assert isinstance(parser, DocumentParser)


def test_pymupdf_parse_returns_parse_result() -> None:
    parser = PyMuPDFParser()
    result = parser.parse(FIXTURE_PDF)
    assert isinstance(result, ParseResult)


def test_parse_result_has_pages() -> None:
    parser = PyMuPDFParser()
    result = parser.parse(FIXTURE_PDF)
    assert len(result.pages) > 0
    assert isinstance(result.pages[0], str)


def test_parse_result_has_full_text() -> None:
    parser = PyMuPDFParser()
    result = parser.parse(FIXTURE_PDF)
    assert len(result.text) > 0
    # Full text should be the concatenation of pages
    for page in result.pages:
        assert page in result.text


def test_parse_result_metadata() -> None:
    parser = PyMuPDFParser()
    result = parser.parse(FIXTURE_PDF)
    assert result.page_count > 0
    assert result.parse_tool == "pymupdf"
    assert isinstance(result.parse_version, str)


def test_get_parser_default_returns_pymupdf() -> None:
    parser = get_parser()
    assert isinstance(parser, PyMuPDFParser)


def test_get_parser_explicit_pymupdf() -> None:
    parser = get_parser("pymupdf")
    assert isinstance(parser, PyMuPDFParser)


def test_get_parser_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown parser"):
        get_parser("nonexistent")


def test_fixture_pdf_content() -> None:
    """Verify the fixture PDF has extractable text."""
    parser = PyMuPDFParser()
    result = parser.parse(FIXTURE_PDF)
    assert (
        "sovereign" in result.text.lower()
        or "bond" in result.text.lower()
        or len(result.text) > 10
    )
