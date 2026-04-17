"""Tests for EDGAR HTML/text parsing with SGML stripping and page splitting."""

from __future__ import annotations


def test_strip_sgml_wrapper_htm():
    """SGML envelope is stripped, HTML content extracted."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = (
        "<DOCUMENT>\n<TYPE>424B3\n<SEQUENCE>1\n"
        "<FILENAME>test.htm\n<TEXT>\n"
        "<html><body><h1>Republic of Peru</h1></body></html>\n"
        "</TEXT>\n</DOCUMENT>"
    )
    content, is_html = strip_sgml_wrapper(raw)
    assert "<h1>Republic of Peru</h1>" in content
    assert "<DOCUMENT>" not in content
    assert "<TYPE>" not in content
    assert is_html is True


def test_strip_sgml_wrapper_txt():
    """Plain text .txt files: SGML stripped, detected as non-HTML."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = (
        "<DOCUMENT>\n<TYPE>424B5\n<SEQUENCE>1\n"
        "<FILENAME>test.txt\n<TEXT>\n"
        "                    Filed Pursuant to Rule 424(b)(5)\n"
        "                    Republic of Peru\n"
        "<PAGE>\n"
        "                    9 1/8% Bonds due 2008\n"
        "</TEXT>\n</DOCUMENT>"
    )
    content, is_html = strip_sgml_wrapper(raw)
    assert "Republic of Peru" in content
    assert "<DOCUMENT>" not in content
    assert is_html is False


def test_strip_sgml_wrapper_no_wrapper():
    """Files without SGML wrapper are returned as-is."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = "<html><body><h1>Hello</h1></body></html>"
    content, is_html = strip_sgml_wrapper(raw)
    assert content == raw
    assert is_html is True


def test_strip_sgml_warns_on_multi_text(caplog):
    """Multiple <TEXT> blocks log a warning."""
    from scripts.docling_reparse_edgar import strip_sgml_wrapper

    raw = (
        "<DOCUMENT><TEXT>First block</TEXT></DOCUMENT>\n"
        "<DOCUMENT><TEXT>Second block</TEXT></DOCUMENT>"
    )
    content, _ = strip_sgml_wrapper(raw)
    assert "First block" in content


def test_split_htm_pages_with_page_break_before():
    """HTML files split on page-break-before CSS."""
    from scripts.docling_reparse_edgar import split_htm_pages

    html = (
        "<div>Page 1 content</div>"
        '<div style="page-break-before: always">Page 2 content</div>'
        '<div style="page-break-before: always">Page 3 content</div>'
    )
    pages = split_htm_pages(html)
    assert len(pages) >= 2


def test_split_htm_pages_with_page_break_after():
    """HTML files split on page-break-after CSS (different insertion point)."""
    from scripts.docling_reparse_edgar import split_htm_pages

    html = '<div style="page-break-after: always">Page 1 content</div><div>Page 2 content</div>'
    pages = split_htm_pages(html)
    assert len(pages) >= 2
    assert "Page 1" in pages[0]


def test_split_htm_pages_no_breaks():
    """HTML without page breaks becomes one page."""
    from scripts.docling_reparse_edgar import split_htm_pages

    html = "<html><body><h1>Hello</h1><p>World</p></body></html>"
    pages = split_htm_pages(html)
    assert len(pages) == 1


def test_split_txt_pages():
    """Text files split on <PAGE> markers."""
    from scripts.docling_reparse_edgar import split_txt_pages

    text = "Page one content\n<PAGE>\nPage two content\n<PAGE>\nPage three"
    pages = split_txt_pages(text)
    assert len(pages) == 3
    assert "Page one" in pages[0]
    assert "Page three" in pages[2]


def test_split_txt_pages_no_markers():
    """Text without <PAGE> becomes single page."""
    from scripts.docling_reparse_edgar import split_txt_pages

    text = "Just a plain text document\nwith multiple lines"
    pages = split_txt_pages(text)
    assert len(pages) == 1
