"""Plain text parser for .txt files.

Handles SEC EDGAR <PAGE> markers and encoding fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from corpus.parsers.base import ParseResult

if TYPE_CHECKING:
    from pathlib import Path

_ENCODINGS = ("utf-8", "cp1252")
_PAGE_MARKER = "<PAGE>"


class PlainTextParser:
    """Parse plain text files into page-segmented results."""

    def parse(self, path: Path) -> ParseResult:
        """Read text file with encoding fallback, split on <PAGE> markers."""
        raw_bytes = path.read_bytes()
        text = self._decode(raw_bytes)

        if _PAGE_MARKER in text:
            pages = [p.strip() for p in text.split(_PAGE_MARKER)]
            # Remove empty trailing page from final marker
            if pages and not pages[-1]:
                pages.pop()
        else:
            pages = [text]

        return ParseResult(
            pages=pages,
            text="\n\n".join(pages),
            page_count=len(pages),
            parse_tool="plaintext",
            parse_version="1.0.0",
        )

    @staticmethod
    def _decode(raw: bytes) -> str:
        for enc in _ENCODINGS:
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, ValueError):
                continue
        # CP1252 covers all single-byte values 0x00-0xFF except 5 holes,
        # so this fallback is rarely reached.  Use latin-1 (maps all 256
        # byte values) as a safe last resort.
        return raw.decode("latin-1")
