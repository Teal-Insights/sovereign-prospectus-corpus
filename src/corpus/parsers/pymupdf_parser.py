"""PyMuPDF-based document parser.

Extracts text page-by-page using PyMuPDF (fitz). Returns a ParseResult
with per-page text and full concatenated text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import fitz  # PyMuPDF

from corpus.parsers.base import ParseResult

if TYPE_CHECKING:
    from pathlib import Path


class PyMuPDFParser:
    """Parse PDFs using PyMuPDF."""

    def parse(self, path: Path) -> ParseResult:
        doc = fitz.open(str(path))
        try:
            pages: list[str] = [str(page.get_text()) for page in doc]
            text = "\n\n".join(pages)
            return ParseResult(
                pages=pages,
                text=text,
                page_count=len(pages),
                parse_tool="pymupdf",
                parse_version=fitz.VersionBind,
            )
        finally:
            doc.close()
