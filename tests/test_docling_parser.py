"""Tests for DoclingParser — Docling-based PDF parser."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from corpus.parsers.base import DocumentParser, ParseResult
from corpus.parsers.docling_parser import DoclingParser


def test_satisfies_protocol():
    """DoclingParser must implement DocumentParser protocol."""
    parser = DoclingParser()
    assert isinstance(parser, DocumentParser)


def test_parse_returns_parse_result():
    """parse() must return a ParseResult with correct fields."""
    # Mock Docling's DocumentConverter to avoid loading ML models in tests
    mock_doc = MagicMock()
    mock_doc.num_pages.return_value = 3
    mock_doc.pages = {1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    mock_doc.export_to_markdown.side_effect = [
        "# Full Document\n\nPage 1 text\n\nPage 2 text\n\nPage 3 text",  # full doc
        "# Page 1\n\nPage 1 text",  # page_no=1
        "Page 2 text with **bold**",  # page_no=2
        "| Col | Val |\n|---|---|\n| A | B |",  # page_no=3
    ]

    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("docling.document_converter.DocumentConverter") as mock_converter:
        mock_converter.return_value.convert.return_value = mock_result
        parser = DoclingParser()
        result = parser.parse(MagicMock())

    assert isinstance(result, ParseResult)
    assert result.page_count == 3
    assert result.parse_tool == "docling"
    assert len(result.pages) == 3
    # Pages should be plain text (stripped markdown)
    assert "#" not in result.pages[0]
    assert "**" not in result.pages[1]
    assert "|" not in result.pages[2]
    # But content preserved
    assert "Page 1 text" in result.pages[0]
    assert "bold" in result.pages[1]
    assert "A" in result.pages[2] and "B" in result.pages[2]
    # Full text is pages joined
    assert result.text == "\n\n".join(result.pages)
    # Metadata has full markdown
    assert "markdown" in result.metadata


def test_parse_empty_pdf():
    """Empty PDFs should return parse_ok with 0 pages."""
    mock_doc = MagicMock()
    mock_doc.num_pages.return_value = 0
    mock_doc.pages = {}
    mock_doc.export_to_markdown.return_value = ""

    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("docling.document_converter.DocumentConverter") as mock_converter:
        mock_converter.return_value.convert.return_value = mock_result
        parser = DoclingParser()
        result = parser.parse(MagicMock())

    assert result.page_count == 0
    assert result.pages == []
    assert result.text == ""


def test_registry_returns_docling_by_default():
    """get_parser() with config default='docling' returns DoclingParser."""
    from corpus.parsers.registry import get_parser

    parser = get_parser("docling")
    assert isinstance(parser, DoclingParser)
