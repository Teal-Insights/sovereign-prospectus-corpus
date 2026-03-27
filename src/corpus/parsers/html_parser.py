"""HTML parser for .htm/.html files.

Strips script/style tags, extracts text with BeautifulSoup.
Splits pages on CSS page-break markers (common in SEC EDGAR filings).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from corpus.parsers.base import ParseResult

if TYPE_CHECKING:
    from pathlib import Path

_ENCODINGS = ("utf-8", "cp1252")
_PAGE_BREAK_BEFORE_RE = re.compile(r"page-break-before\s*:\s*always", re.IGNORECASE)
_PAGE_BREAK_AFTER_RE = re.compile(r"page-break-after\s*:\s*always", re.IGNORECASE)


class HTMLParser:
    """Parse HTML files into text."""

    def parse(self, path: Path) -> ParseResult:
        """Read HTML, strip script/style, extract text.

        Splits on elements with CSS page-break-before/after:always style
        attributes, which are common in SEC EDGAR HTML filings.
        """
        raw_bytes = path.read_bytes()
        html = self._decode(raw_bytes)

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Find page-break elements and split
        has_breaks = self._insert_page_markers(soup)

        if has_breaks:
            pages = self._split_on_markers(soup)
        else:
            text = self._extract_text(soup)
            pages = [text] if text else []

        full_text = "\n\n".join(pages)

        return ParseResult(
            pages=pages,
            text=full_text,
            page_count=len(pages),
            parse_tool="beautifulsoup",
            parse_version="1.0.0",
        )

    @staticmethod
    def _insert_page_markers(soup: BeautifulSoup) -> bool:
        """Insert page-break markers into the DOM. Returns True if any found."""
        marker = "\x00PAGE_BREAK\x00"
        found = False
        for tag in soup.find_all(True):
            style = tag.get("style", "")
            if not isinstance(style, str):
                continue
            if _PAGE_BREAK_BEFORE_RE.search(style):
                tag.insert_before(marker)
                found = True
            elif _PAGE_BREAK_AFTER_RE.search(style):
                tag.insert_after(marker)
                found = True
        return found

    @staticmethod
    def _split_on_markers(soup: BeautifulSoup) -> list[str]:
        """Split document text at pre-inserted page-break markers."""
        marker = "\x00PAGE_BREAK\x00"
        full_text = soup.get_text(separator="\n")
        raw_pages = full_text.split(marker)

        pages: list[str] = []
        for page in raw_pages:
            lines = [line.strip() for line in page.splitlines()]
            cleaned = "\n".join(line for line in lines if line)
            if cleaned:
                pages.append(cleaned)
        return pages

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        """Extract and clean text from soup."""
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode("latin-1")
