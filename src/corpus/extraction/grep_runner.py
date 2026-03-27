"""Grep runner — search parsed document text with regex patterns.

Core function grep_document() is pure: takes pages and patterns,
returns matches. Used by both single-doc CLI mode and full-corpus mode.

Page convention: all page_index values are 0-indexed.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from corpus.extraction.clause_patterns import ClausePattern

CONTEXT_CHARS = 500


@dataclass(frozen=True)
class GrepMatch:
    """A single regex match in a document."""

    document_id: str
    pattern_name: str
    pattern_version: str
    page_index: int  # 0-indexed
    matched_text: str
    context_before: str
    context_after: str
    run_id: str


def build_searchable_text(pages: list[str]) -> tuple[str, list[int]]:
    """Concatenate pages with separators and return page start offsets.

    Returns:
        (full_text, page_start_offsets) where page_start_offsets[i] is
        the character offset where page i begins in full_text.
    """
    offsets: list[int] = []
    parts: list[str] = []
    pos = 0
    for page_text in pages:
        offsets.append(pos)
        parts.append(page_text)
        pos += len(page_text) + 2  # +2 for "\n\n" separator
    return "\n\n".join(parts), offsets


def offset_to_page_index(offset: int, page_offsets: list[int]) -> int:
    """Map a character offset to a 0-indexed page number."""
    return bisect.bisect_right(page_offsets, offset) - 1


def grep_document(
    *,
    pages: list[str],
    patterns: list[ClausePattern],
    document_id: str,
    run_id: str,
) -> list[GrepMatch]:
    """Search document text with all patterns. Returns matches."""
    if not pages:
        return []

    full_text, page_offsets = build_searchable_text(pages)
    matches: list[GrepMatch] = []

    for pattern in patterns:
        for m in pattern.finder.finditer(full_text):
            start, end = m.start(), m.end()
            page_idx = offset_to_page_index(start, page_offsets)

            context_before = full_text[max(0, start - CONTEXT_CHARS) : start]
            context_after = full_text[end : end + CONTEXT_CHARS]

            matches.append(
                GrepMatch(
                    document_id=document_id,
                    pattern_name=pattern.name,
                    pattern_version=pattern.version,
                    page_index=page_idx,
                    matched_text=m.group(),
                    context_before=context_before,
                    context_after=context_after,
                    run_id=run_id,
                )
            )

    return matches
