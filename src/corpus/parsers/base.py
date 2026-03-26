"""Parser protocol and result types for document text extraction.

Decision 11: Protocol-based parser swapping — PyMuPDF now, Docling later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ParseResult:
    """Result of parsing a single document."""

    pages: list[str]
    text: str
    page_count: int
    parse_tool: str
    parse_version: str
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class DocumentParser(Protocol):
    """Protocol that all parsers must satisfy."""

    def parse(self, path: Path) -> ParseResult:
        """Extract text from a document at *path*."""
        ...
