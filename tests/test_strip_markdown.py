"""Tests for strip_markdown — must preserve table content as plain text."""

from __future__ import annotations

from corpus.parsers.markdown import strip_markdown


def test_strips_headings():
    assert strip_markdown("## Section Title\nBody text") == "Section Title\nBody text"


def test_strips_bold_and_italic():
    assert strip_markdown("This is **bold** and *italic*") == "This is bold and italic"


def test_strips_list_markers():
    text = "- Item one\n- Item two\n* Item three"
    result = strip_markdown(text)
    assert "Item one" in result
    assert "Item two" in result
    assert "Item three" in result
    assert not result.startswith("-")
    assert "* " not in result


def test_preserves_table_content():
    """Critical: table cell text must survive for grep/FTS."""
    table = "| Country | Amount | Currency |\n|---|---|---|\n| Ghana | 1,000,000 | USD |\n| Kenya | 500,000 | EUR |"
    result = strip_markdown(table)
    assert "Ghana" in result
    assert "1,000,000" in result
    assert "USD" in result
    assert "Kenya" in result
    assert "|" not in result
    assert "---" not in result


def test_strips_horizontal_rules():
    assert strip_markdown("Above\n---\nBelow").strip() == "Above\n\nBelow"


def test_preserves_plain_text():
    text = "This is plain text with no markdown."
    assert strip_markdown(text) == text


def test_empty_string():
    assert strip_markdown("") == ""


def test_image_placeholders_removed():
    assert (
        strip_markdown("Text before\n<!-- image -->\nText after").strip()
        == "Text before\n\nText after"
    )
