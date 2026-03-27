"""HTML parser for .htm/.html files.

Strips script/style tags, extracts text with BeautifulSoup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from corpus.parsers.base import ParseResult

if TYPE_CHECKING:
    from pathlib import Path

_ENCODINGS = ("utf-8", "cp1252", "latin-1")


class HTMLParser:
    """Parse HTML files into text."""

    def parse(self, path: Path) -> ParseResult:
        """Read HTML, strip script/style, extract text."""
        raw_bytes = path.read_bytes()
        html = self._decode(raw_bytes)

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # Collapse excessive blank lines
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line)

        return ParseResult(
            pages=[text],
            text=text,
            page_count=1,
            parse_tool="beautifulsoup",
            parse_version="1.0.0",
        )

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        return raw.decode("utf-8", errors="replace")
