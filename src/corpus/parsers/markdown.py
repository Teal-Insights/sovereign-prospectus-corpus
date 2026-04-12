"""Markdown-to-plain-text conversion for grep/FTS consumption.

Strips formatting while preserving content — especially table cell text,
which the stale strip_markdown() deleted entirely.
"""

from __future__ import annotations

import re


def strip_markdown(text: str) -> str:
    """Strip markdown formatting, preserving all textual content.

    Designed for sovereign bond prospectuses where tables contain critical
    financial data that must remain searchable.
    """
    if not text:
        return text

    # Remove image placeholders
    text = re.sub(r"<!--\s*image\s*-->", "", text)

    # Headers: "## Title" → "Title"
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold+italic (***text***), bold (**text**), italic (*text*) → text
    # Process triple first, then double, then single to avoid leftover markers
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)

    # Inline code: `text` → text
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Markdown links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Unordered list markers: "- item" or "* item" or "+ item" → "item"
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Numbered list markers: "1. item" → "item"
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Table separator rows: |---|---|---| → remove entirely
    text = re.sub(r"^\|[-:\s|]+\|$", "", text, flags=re.MULTILINE)

    # Table rows: | cell1 | cell2 | → "cell1 cell2"
    def _table_row_to_text(match: re.Match[str]) -> str:
        row = match.group(0)
        cells = [c.strip() for c in row.strip("|").split("|")]
        return " ".join(c for c in cells if c)

    text = re.sub(r"^\|.+\|$", _table_row_to_text, text, flags=re.MULTILINE)

    # Horizontal rules: --- or *** → blank line
    text = re.sub(r"^[-*]{3,}$", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines to single
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text
