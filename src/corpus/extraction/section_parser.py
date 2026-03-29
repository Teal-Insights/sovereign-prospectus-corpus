# src/corpus/extraction/section_parser.py
"""Parse Docling markdown or EDGAR flat JSONL into sections for clause extraction.

Sections are the unit of analysis for the LOCATE stage. Each section has a
heading, body text (markdown preserved), heading level, and character count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    section_id: str
    storage_key: str
    heading: str
    heading_level: int
    text: str
    page_range: tuple[int, int]  # placeholder until page mapping added
    source_format: str
    char_count: int
    section_index: int  # E1: used for clustering instead of page_range


# Matches markdown headings: # Heading, ## Heading, ### Heading
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# ALL CAPS lines that look like headings (short, no lowercase)
_ALL_CAPS_RE = re.compile(r"^([A-Z][A-Z\s,;:\-\u2013\u2014&/()]{4,78}[A-Z)])$", re.MULTILINE)


def _split_at_headings(
    text: str,
) -> list[tuple[str, int, int]]:
    """Find all heading positions. Returns [(heading_text, level, start_pos)]."""
    headings: list[tuple[str, int, int]] = []

    for m in _MD_HEADING_RE.finditer(text):
        level = len(m.group(1))
        heading_text = m.group(2).strip()
        headings.append((heading_text, level, m.start()))

    # Also detect ALL CAPS lines as level-2 headings
    for m in _ALL_CAPS_RE.finditer(text):
        candidate = m.group(1).strip()
        pos = m.start()
        if any(abs(pos - h[2]) < 5 for h in headings):
            continue
        after = text[m.end() : m.end() + 50].strip()
        if after and not after.startswith("#"):
            headings.append((candidate, 2, pos))

    headings.sort(key=lambda h: h[2])
    return headings


def parse_docling_markdown(
    markdown_text: str,
    *,
    storage_key: str,
    max_section_chars: int = 15000,
) -> list[Section]:
    if not markdown_text.strip():
        return []

    headings = _split_at_headings(markdown_text)

    if not headings:
        full_text = markdown_text.strip()
        if len(full_text) > max_section_chars:
            chunks = _split_large_section(full_text, max_section_chars)
            return [
                Section(
                    section_id=f"{storage_key}__s{i}",
                    storage_key=storage_key,
                    heading="(no heading)",
                    heading_level=0,
                    text=chunk,
                    page_range=(-1, -1),
                    source_format="docling_md",
                    char_count=len(chunk),
                    section_index=i,
                )
                for i, chunk in enumerate(chunks)
            ]
        return [
            Section(
                section_id=f"{storage_key}__s0",
                storage_key=storage_key,
                heading="(no heading)",
                heading_level=0,
                text=full_text,
                page_range=(-1, -1),
                source_format="docling_md",
                char_count=len(full_text),
                section_index=0,
            )
        ]

    # E20: Determine the structural heading level. If the shallowest level
    # has only one heading (a document title like "# Prospectus"), skip it
    # and use the next level as sections. Subsections deeper than the
    # structural level are absorbed by E2 (same-or-higher boundary rule).
    level_counts: dict[int, int] = {}
    for _, lvl, _ in headings:
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    sorted_levels = sorted(level_counts.keys())
    if len(sorted_levels) >= 2 and level_counts[sorted_levels[0]] == 1:
        # Singleton shallowest (document title) — use next level
        emit_levels = {sorted_levels[1]}
    else:
        # Shallowest level IS the structural level
        emit_levels = {sorted_levels[0]}

    # Fix 1: If we skip a singleton title, capture any preamble text between
    # the title heading line and the first structural heading, so it is not lost.
    preamble = ""
    if len(sorted_levels) >= 2 and level_counts[sorted_levels[0]] == 1:
        title_heading = next(h for h in headings if h[1] == sorted_levels[0])
        first_structural = next(h for h in headings if h[1] == sorted_levels[1])
        title_line_end = markdown_text.find("\n", title_heading[2])
        if title_line_end == -1:
            title_line_end = len(markdown_text)
        preamble_text = markdown_text[title_line_end : first_structural[2]].strip()
        if preamble_text:
            preamble = preamble_text + "\n\n"

    sections: list[Section] = []
    for i, (heading_text, level, start) in enumerate(headings):
        # E20: Skip headings deeper than the shallowest level
        if level not in emit_levels:
            continue

        # E2: Section ends at next heading of SAME or HIGHER level
        end = len(markdown_text)
        for j in range(i + 1, len(headings)):
            if headings[j][1] <= level:  # same or higher level
                end = headings[j][2]
                break

        body = markdown_text[start:end].strip()

        # Prepend preamble to the first emitted section
        if preamble and not sections:
            body = preamble + body
        char_count = len(body)

        if char_count > max_section_chars:
            chunks = _split_large_section(body, max_section_chars)
            for chunk in chunks:
                sections.append(
                    Section(
                        section_id=f"{storage_key}__s{len(sections)}",
                        storage_key=storage_key,
                        heading=heading_text,
                        heading_level=level,
                        text=chunk,
                        page_range=(-1, -1),
                        source_format="docling_md",
                        char_count=len(chunk),
                        section_index=len(sections),
                    )
                )
        else:
            sections.append(
                Section(
                    section_id=f"{storage_key}__s{len(sections)}",
                    storage_key=storage_key,
                    heading=heading_text,
                    heading_level=level,
                    text=body,
                    page_range=(-1, -1),
                    source_format="docling_md",
                    char_count=char_count,
                    section_index=len(sections),
                )
            )

    return sections


def _split_large_section(text: str, max_chars: int) -> list[str]:
    """Split a large section at paragraph boundaries, falling back to word boundaries."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        # If a single paragraph exceeds max_chars, split it at word boundaries
        if len(para) > max_chars:
            # Flush any accumulated current chunks first
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            # Split oversized paragraph at word boundaries
            words = para.split(" ")
            word_current: list[str] = []
            word_len = 0
            for word in words:
                word_with_space = len(word) + 1  # +1 for space
                if word_len + word_with_space > max_chars and word_current:
                    chunks.append(" ".join(word_current))
                    word_current = [word]
                    word_len = len(word)
                else:
                    word_current.append(word)
                    word_len += word_with_space
            if word_current:
                chunks.append(" ".join(word_current))
        elif current_len + len(para) + 2 > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + (2 if current_len > 0 else 0)  # +2 for \n\n separator

    if current:
        chunks.append("\n\n".join(current))

    # Post-process: merge tiny leading chunks (e.g., heading-only) into the next chunk
    if len(chunks) >= 2 and len(chunks[0]) < 200:
        chunks[1] = chunks[0] + "\n\n" + chunks[1]
        chunks = chunks[1:]

    return chunks


def parse_flat_jsonl(
    pages: list[dict],
    *,
    storage_key: str,
) -> list[Section]:
    """Parse flat JSONL page records into sections (one per non-empty page)."""
    sections: list[Section] = []
    for page_rec in pages:
        text = page_rec.get("text", "")
        if not text.strip():
            continue
        page_idx = page_rec["page"]
        sections.append(
            Section(
                section_id=f"{storage_key}__s{len(sections)}",
                storage_key=storage_key,
                heading=f"(page {page_idx + 1})",
                heading_level=0,
                text=text,
                page_range=(page_idx, page_idx),
                source_format="flat_jsonl",
                char_count=len(text),
                section_index=len(sections),
            )
        )
    return sections
