# tests/test_section_parser.py
"""Tests for Docling markdown section parser."""

from __future__ import annotations

from corpus.extraction.section_parser import parse_docling_markdown

SAMPLE_MD = """\
## Risk Factors

Some risk factor text here spanning
multiple lines.

## Collective Action Clauses

The Bonds contain collective action clauses.
Under these provisions, holders of not less than
75% of the aggregate principal amount may modify
the terms.

### Aggregation

Cross-series modification is permitted.

## Governing Law

This prospectus is governed by English law.
"""


def test_parse_returns_sections() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    # E20: Only shallowest level (##) emitted; ### absorbed by parent
    assert len(sections) == 3


def test_section_has_heading() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    headings = [s.heading for s in sections]
    assert "Collective Action Clauses" in headings


def test_section_text_includes_body() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    cac = next(s for s in sections if s.heading == "Collective Action Clauses")
    assert "75% of the aggregate principal" in cac.text


def test_subsection_included_in_parent_or_separate() -> None:
    """Subsections (###) should either be part of parent or separate sections."""
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    all_text = " ".join(s.text for s in sections)
    assert "Cross-series modification" in all_text


def test_section_id_format() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    for s in sections:
        assert s.section_id.startswith("test__doc1__s")


def test_heading_level() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    cac = next(s for s in sections if s.heading == "Collective Action Clauses")
    assert cac.heading_level == 2


def test_all_caps_heading_detection() -> None:
    """ALL CAPS lines should be detected as headings."""
    md = """\
COLLECTIVE ACTION CLAUSES

The Bonds contain collective action clauses.

GOVERNING LAW

English law applies.
"""
    sections = parse_docling_markdown(md, storage_key="test__doc2")
    headings = [s.heading for s in sections]
    assert "COLLECTIVE ACTION CLAUSES" in headings


def test_max_section_size_split() -> None:
    """Sections exceeding max_chars should be split."""
    long_body = "word " * 4000  # ~20,000 chars
    md = f"## Very Long Section\n\n{long_body}\n\n## Next Section\n\nShort."
    sections = parse_docling_markdown(md, storage_key="test__doc3", max_section_chars=15000)
    # The long section should be split or capped
    for s in sections:
        assert s.char_count <= 16000  # allow some margin


def test_subsection_not_emitted_separately() -> None:
    """E20 regression: ### headings should NOT produce separate sections when ## exists."""
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    headings = [s.heading for s in sections]
    assert "Aggregation" not in headings
    # But the text should be absorbed into the parent ## section
    cac = next(s for s in sections if s.heading == "Collective Action Clauses")
    assert "Cross-series modification" in cac.text


def test_empty_input() -> None:
    sections = parse_docling_markdown("", storage_key="test__empty")
    assert sections == []


# --- EDGAR flat JSONL tests ---


def test_parse_flat_jsonl_returns_page_sections() -> None:
    """Flat JSONL (EDGAR) should produce one section per page."""
    pages = [
        {"page": 0, "text": "Page zero text about risk factors.", "char_count": 34},
        {"page": 1, "text": "Page one has collective action clauses.", "char_count": 39},
    ]
    from corpus.extraction.section_parser import parse_flat_jsonl

    sections = parse_flat_jsonl(pages, storage_key="edgar__test1")
    assert len(sections) == 2
    assert sections[0].heading == "(page 1)"  # display is 1-indexed
    assert sections[1].heading == "(page 2)"
    assert sections[0].source_format == "flat_jsonl"
    assert "risk factors" in sections[0].text


def test_parse_flat_jsonl_skips_empty_pages() -> None:
    pages = [
        {"page": 0, "text": "", "char_count": 0},
        {"page": 1, "text": "Some content.", "char_count": 13},
    ]
    from corpus.extraction.section_parser import parse_flat_jsonl

    sections = parse_flat_jsonl(pages, storage_key="edgar__test2")
    assert len(sections) == 1
