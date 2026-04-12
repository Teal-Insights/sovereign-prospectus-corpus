"""Tests for regex-safe text highlighting."""

from __future__ import annotations


def test_basic_highlight():
    from explorer.highlight import highlight_text

    result = highlight_text("The cat sat on the mat", "cat")
    assert "<mark>cat</mark>" in result
    assert result.count("<mark>") == 1


def test_case_insensitive():
    from explorer.highlight import highlight_text

    result = highlight_text("The CAT sat on the Cat mat", "cat")
    assert result.count("<mark>") == 2


def test_html_safe():
    """Must not replace inside HTML tags."""
    from explorer.highlight import highlight_text

    text = 'Click <a href="http://cat.com">here</a> to see the cat'
    result = highlight_text(text, "cat")
    # Should highlight "cat" in text, not in the URL
    assert 'href="http://cat.com"' in result
    assert result.count("<mark>") == 1


def test_cap_at_100():
    from explorer.highlight import highlight_text

    text = " ".join(["the"] * 500)
    result, count = highlight_text(text, "the", return_count=True)
    assert count == 500
    assert result.count("<mark>") == 100


def test_empty_query():
    from explorer.highlight import highlight_text

    result = highlight_text("some text", "")
    assert "<mark>" not in result


def test_snippet_extraction():
    from explorer.highlight import extract_snippet

    text = "A" * 200 + "collective action clause" + "B" * 200
    snippet = extract_snippet(text, "collective action")
    assert "collective action" in snippet
    assert len(snippet) < len(text)
