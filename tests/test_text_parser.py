"""Tests for plain text parser."""

from __future__ import annotations

from typing import TYPE_CHECKING

from corpus.parsers.text_parser import PlainTextParser

if TYPE_CHECKING:
    from pathlib import Path


def test_parse_simple_text(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("This is a test document.\nWith two lines.", encoding="utf-8")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count == 1
    assert "This is a test document." in result.pages[0]
    assert result.parse_tool == "plaintext"


def test_parse_sec_page_markers(tmp_path: Path) -> None:
    f = tmp_path / "edgar.txt"
    f.write_text("Page 1 content\n<PAGE>\nPage 2 content\n<PAGE>\nPage 3", encoding="utf-8")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count == 3
    assert "Page 1 content" in result.pages[0]
    assert "Page 2 content" in result.pages[1]
    assert "Page 3" in result.pages[2]


def test_parse_sgml_preamble_stripped(tmp_path: Path) -> None:
    """SGML wrapper before first <PAGE> should not become a page."""
    f = tmp_path / "edgar.txt"
    f.write_text(
        "<DOCUMENT>\n<TYPE>424B3\n<TEXT>\n<PAGE>\n"
        "Real page 1 content\n<PAGE>\nReal page 2 content",
        encoding="utf-8",
    )
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count == 2
    assert "Real page 1 content" in result.pages[0]
    assert "Real page 2 content" in result.pages[1]
    # SGML metadata should not appear in any page
    assert all("<DOCUMENT>" not in p for p in result.pages)
    assert all("<TYPE>" not in p for p in result.pages)


def test_parse_latin1_encoding(tmp_path: Path) -> None:
    f = tmp_path / "latin1.txt"
    f.write_bytes("Côte d'Ivoire prospectus".encode("latin-1"))
    parser = PlainTextParser()
    result = parser.parse(f)
    assert "Côte d'Ivoire" in result.text


def test_parse_windows_1252_encoding(tmp_path: Path) -> None:
    f = tmp_path / "win.txt"
    # Windows-1252 smart quotes
    f.write_bytes(b"\x93smart quotes\x94")
    parser = PlainTextParser()
    result = parser.parse(f)
    assert result.page_count >= 1
    assert len(result.text) > 0
