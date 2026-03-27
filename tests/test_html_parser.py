"""Tests for HTML parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from corpus.parsers.html_parser import HTMLParser

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_simple_html(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_text("<html><body><p>Hello world</p></body></html>", encoding="utf-8")
    parser = HTMLParser()
    result = parser.parse(f)
    assert result.page_count == 1
    assert "Hello world" in result.pages[0]
    assert result.parse_tool == "beautifulsoup"


def test_strips_script_and_style_tags(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_text(
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>alert('hi')</script><p>Content</p></body></html>",
        encoding="utf-8",
    )
    parser = HTMLParser()
    result = parser.parse(f)
    assert "color:red" not in result.text
    assert "alert" not in result.text
    assert "Content" in result.text


def test_splits_on_page_break_before(tmp_path: Path) -> None:
    """CSS page-break-before:always should create page boundaries."""
    f = tmp_path / "edgar.htm"
    f.write_text(
        "<html><body>"
        "<div>Page 1 content</div>"
        '<div style="page-break-before:always">Page 2 content</div>'
        '<div style="page-break-before: always">Page 3 content</div>'
        "</body></html>",
        encoding="utf-8",
    )
    parser = HTMLParser()
    result = parser.parse(f)
    assert result.page_count == 3
    assert "Page 1 content" in result.pages[0]
    assert "Page 2 content" in result.pages[1]
    assert "Page 3 content" in result.pages[2]


def test_splits_on_page_break_after(tmp_path: Path) -> None:
    """CSS page-break-after:always should also create page boundaries."""
    f = tmp_path / "edgar.htm"
    f.write_text(
        "<html><body>"
        '<div style="page-break-after:always">Page 1 content</div>'
        "<div>Page 2 content</div>"
        "</body></html>",
        encoding="utf-8",
    )
    parser = HTMLParser()
    result = parser.parse(f)
    assert result.page_count == 2
    assert "Page 1 content" in result.pages[0]
    assert "Page 2 content" in result.pages[1]


def test_no_page_breaks_single_page(tmp_path: Path) -> None:
    """HTML without page breaks should remain single page."""
    f = tmp_path / "simple.htm"
    f.write_text(
        "<html><body><div>Just one page</div></body></html>",
        encoding="utf-8",
    )
    parser = HTMLParser()
    result = parser.parse(f)
    assert result.page_count == 1


def test_parse_latin1_html(tmp_path: Path) -> None:
    f = tmp_path / "test.htm"
    f.write_bytes("<html><body>Côte d'Ivoire</body></html>".encode("latin-1"))
    parser = HTMLParser()
    result = parser.parse(f)
    assert "Côte d'Ivoire" in result.text
