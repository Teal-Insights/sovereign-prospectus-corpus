"""Docling-based PDF parser for sovereign bond prospectuses.

Uses Docling's per-page markdown export, then strips formatting for the
plain-text ParseResult consumed by grep/FTS. Raw markdown is preserved
in result.metadata["markdown"] for the Streamlit detail panel.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

from corpus.parsers.base import ParseResult
from corpus.parsers.markdown import strip_markdown

if TYPE_CHECKING:
    from pathlib import Path


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
        # Iterate range(1, page_count+1) to guarantee contiguous output,
        # matching docling_reparse.py — fills gaps with empty strings.
        pages: list[str] = []
        for page_no in range(1, page_count + 1):
            if page_no in doc.pages:
                page_md = doc.export_to_markdown(page_no=page_no)
                pages.append(strip_markdown(page_md))
            else:
                pages.append("")

        text = "\n\n".join(pages)

        return ParseResult(
            pages=pages,
            text=text,
            page_count=page_count,
            parse_tool="docling",
            parse_version=pkg_version("docling"),
            metadata={"markdown": full_markdown},
        )
