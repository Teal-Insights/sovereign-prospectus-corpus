"""Regex-safe text highlighting and snippet extraction."""

from __future__ import annotations

import re
from typing import Literal, overload


@overload
def highlight_text(
    text: str,
    query: str,
    *,
    max_highlights: int = 100,
    return_count: Literal[True],
) -> tuple[str, int]: ...


@overload
def highlight_text(
    text: str,
    query: str,
    *,
    max_highlights: int = 100,
    return_count: Literal[False] = ...,
) -> str: ...


def highlight_text(
    text: str,
    query: str,
    *,
    max_highlights: int = 100,
    return_count: bool = False,
) -> str | tuple[str, int]:
    """Wrap matches in <mark> tags, skipping inside HTML tags.

    Returns highlighted text, or (text, total_count) if return_count=True.
    """
    if not query or not text:
        return (text, 0) if return_count else text

    # Match the query only when NOT inside an HTML tag.
    # Strategy: split text into (HTML tag, non-tag) segments, only replace
    # in non-tag segments.
    escaped = re.escape(query)
    pattern = re.compile(escaped, re.IGNORECASE)

    # Split on HTML tags, keeping the tags
    parts = re.split(r"(<[^>]+>)", text)

    total_count = 0
    highlighted_count = 0
    result_parts = []

    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            # HTML tag -- pass through unchanged
            result_parts.append(part)
        else:
            # Count all matches in this segment
            matches = list(pattern.finditer(part))
            total_count += len(matches)

            if not matches or highlighted_count >= max_highlights:
                result_parts.append(part)
                continue

            # Replace up to the cap
            new_part = []
            last_end = 0
            for m in matches:
                if highlighted_count >= max_highlights:
                    new_part.append(part[last_end:])
                    break
                new_part.append(part[last_end : m.start()])
                new_part.append(f"<mark>{m.group()}</mark>")
                last_end = m.end()
                highlighted_count += 1
            else:
                new_part.append(part[last_end:])
            result_parts.append("".join(new_part))

    result = "".join(result_parts)
    return (result, total_count) if return_count else result


def extract_snippet(text: str, query: str, context_chars: int = 200) -> str:
    """Extract a snippet centered on the first occurrence of query."""
    if not query or not text:
        return text[:400] if text else ""

    idx = text.lower().find(query.lower())
    if idx < 0:
        return text[:400] + ("..." if len(text) > 400 else "")

    start = max(0, idx - context_chars)
    end = min(len(text), idx + len(query) + context_chars)

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix
