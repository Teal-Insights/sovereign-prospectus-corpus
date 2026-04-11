"""Docling-based PDF parser for sovereign bond prospectuses.

Uses Docling's per-page markdown export, then strips formatting for the
plain-text ParseResult consumed by grep/FTS. Raw markdown is preserved
in result.metadata["markdown"] for the Streamlit detail panel.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from pathlib import Path

from corpus.parsers.base import ParseResult
from corpus.parsers.markdown import strip_markdown


class DoclingParser:
    """Parse PDFs using Docling with per-page markdown export."""

    def parse(self, path: Path) -> ParseResult:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document

        page_count = doc.num_pages()

        # Full-document markdown for the .md sidecar / detail panel
        full_markdown = doc.export_to_markdown()

        # Per-page plain text for JSONL / grep / FTS
        pages: list[str] = []
        for page_no in sorted(doc.pages.keys()):
            page_md = doc.export_to_markdown(page_no=page_no)
            pages.append(strip_markdown(page_md))

        text = "\n\n".join(pages)

        return ParseResult(
            pages=pages,
            text=text,
            page_count=page_count,
            parse_tool="docling",
            parse_version=pkg_version("docling"),
            metadata={"markdown": full_markdown},
        )
