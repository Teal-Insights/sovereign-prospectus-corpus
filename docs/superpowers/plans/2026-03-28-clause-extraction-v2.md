# Clause Extraction v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a section-aware clause extraction pipeline that locates CAC clauses using document structure, extracts verbatim text via LLM, validates extractions, and presents results in a lawyer-friendly Shiny explorer.

**Architecture:** Three-stage pipeline (LOCATE → EXTRACT → VERIFY). Stage 1 parses Docling markdown into sections, filters by heading/body cues, rejects obvious false positives, and clusters adjacent hits. Stage 2 sends shortlisted sections to Claude Sonnet with multi-shot examples for verbatim extraction. Stage 3 validates extractions against source text and runs a completeness checklist. Results feed into an updated Shiny explorer designed for expert legal review.

**Tech Stack:** Python 3.12+, Click CLI, DuckDB, Polars, Anthropic SDK (Claude Sonnet), Shiny for Python, pytest, ruff, pyright.

**Spec:** `docs/superpowers/specs/2026-03-28-clause-extraction-v2-design.md`
**Design guide:** `docs/lawyer-centered-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `src/corpus/extraction/section_parser.py` | Parse Docling markdown into `Section` objects |
| `src/corpus/extraction/section_filter.py` | Heading/body cue matching, negative rejection, candidate clustering |
| `src/corpus/extraction/llm_extractor.py` | LLM clause extraction with multi-shot prompt |
| `src/corpus/extraction/verify.py` | Verbatim validation, completeness checklist, quality flags |
| `src/corpus/extraction/cue_families.py` | Cue family definitions for CAC, pari passu (config, not logic) |
| `data/pdip/pdip_split_manifest.json` | Frozen calibration/evaluation document split |
| `tests/test_section_parser.py` | Section parser tests |
| `tests/test_section_filter.py` | Filter, rejector, clustering tests |
| `tests/test_llm_extractor.py` | LLM extractor tests (mocked API) |
| `tests/test_verify.py` | Verification tests |
| `demo/data/export_v2.py` | Export v2 extraction results for Shiny |
| `demo/shiny-app/app_v2.py` | Updated Shiny app for clause validation |

### Modified files

| File | Change |
|---|---|
| `src/corpus/cli.py` | Add `corpus extract-v2 locate`, `corpus extract-v2 extract`, `corpus extract-v2 verify` commands |
| `pyproject.toml` | Add `anthropic` dependency |

---

## Task 1: Cue Family Definitions

**Files:**
- Create: `src/corpus/extraction/cue_families.py`
- Test: `tests/test_cue_families.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_cue_families.py
"""Tests for cue family definitions."""

import re

from corpus.extraction.cue_families import (
    CAC_CUES,
    NEGATIVE_PATTERNS,
    PARI_PASSU_CUES,
    get_cue_families,
)


def test_cac_cues_have_heading_family() -> None:
    assert "heading" in CAC_CUES


def test_cac_cues_have_voting_threshold_family() -> None:
    assert "voting_threshold" in CAC_CUES


def test_pari_passu_cues_have_heading_family() -> None:
    assert "heading" in PARI_PASSU_CUES


def test_negative_patterns_have_cross_reference() -> None:
    assert "cross_reference" in NEGATIVE_PATTERNS


def test_all_patterns_compile() -> None:
    """Every pattern string must be a valid regex."""
    for family, patterns in CAC_CUES.items():
        for p in patterns:
            re.compile(p, re.IGNORECASE)
    for family, patterns in PARI_PASSU_CUES.items():
        for p in patterns:
            re.compile(p, re.IGNORECASE)
    for family, patterns in NEGATIVE_PATTERNS.items():
        for p in patterns:
            re.compile(p, re.IGNORECASE)


def test_get_cue_families_cac() -> None:
    families = get_cue_families("collective_action")
    assert families is CAC_CUES


def test_get_cue_families_pari_passu() -> None:
    families = get_cue_families("pari_passu")
    assert families is PARI_PASSU_CUES


def test_get_cue_families_unknown_returns_none() -> None:
    assert get_cue_families("nonexistent") is None


def test_cac_heading_matches_collective_action() -> None:
    heading_patterns = CAC_CUES["heading"]
    text = "Collective Action Clauses"
    assert any(re.search(p, text, re.IGNORECASE) for p in heading_patterns)


def test_cac_heading_matches_modification_of_conditions() -> None:
    heading_patterns = CAC_CUES["heading"]
    text = "Modification of the Conditions"
    assert any(re.search(p, text, re.IGNORECASE) for p in heading_patterns)


def test_negative_cross_ref_matches() -> None:
    patterns = NEGATIVE_PATTERNS["cross_reference"]
    text = 'See "Description of the Securities — Collective Action"'
    assert any(re.search(p, text, re.IGNORECASE) for p in patterns)


def test_negative_toc_dot_leaders() -> None:
    patterns = NEGATIVE_PATTERNS["table_of_contents"]
    text = "Collective Action .......................... 47"
    assert any(re.search(p, text, re.IGNORECASE) for p in patterns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cue_families.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.extraction.cue_families'`

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/cue_families.py
"""Cue family definitions for clause extraction v2.

Each clause type defines cues organized by family. Cue diversity (hits from
multiple families) is a stronger signal than multiple hits from one family.
"""

from __future__ import annotations

CAC_CUES: dict[str, list[str]] = {
    "heading": [
        r"collective\s+action",
        r"modification\s+of\s+(the\s+)?(conditions|terms)",
        r"amendment\s+and\s+waiver",
        r"meetings?\s+of\s+(note|bond)holders",
        r"voting\s+and\s+amendments",
    ],
    "voting_threshold": [
        r"consent\s+of\s+(the\s+)?holders\s+of\s+not\s+less\s+than",
        r"holders?\s+of\s+\d+%",
        r"\d+%\s+of\s+the\s+aggregate\s+principal",
        r"extraordinary\s+resolution",
        r"written\s+resolution",
    ],
    "aggregation": [
        r"aggregat(ion|ed)\s+(provisions?|voting)",
        r"single[\s-]+(series|limb)\s+(voting|modification)",
        r"cross[\s-]+series",
        r"uniformly\s+applicable",
    ],
    "reserved_matter": [
        r"reserved\s+matter",
        r"reserve[d]?\s+matter\s+modification",
    ],
    "meeting_quorum": [
        r"quorum",
        r"meeting\s+of\s+(note|bond)?holders",
    ],
}

PARI_PASSU_CUES: dict[str, list[str]] = {
    "heading": [
        r"status\s+of\s+the\s+(notes|bonds|securities)",
        r"ranking",
        r"pari\s+passu",
    ],
    "ranking": [
        r"pari\s+passu",
        r"rank\s+(equally|pari\s+passu)",
        r"equal\s+(ranking|priority)",
        r"without\s+preference",
    ],
    "obligation": [
        r"unsecured\s+and\s+unsubordinated",
        r"direct,?\s+(unconditional,?\s+)?unsecured",
    ],
}

NEGATIVE_PATTERNS: dict[str, list[str]] = {
    "cross_reference": [
        r"""(see|refer\s+to|described\s+(under|in))\s+["']""",
        r"as\s+set\s+forth\s+in",
        r"""under\s+["'].+["']""",
    ],
    "table_of_contents": [
        r"\.{4,}",
        r"^\s*\d+\s*$",
    ],
    "summary_overview": [
        r"(the\s+)?following\s+is\s+a\s+(brief\s+)?summary",
        r"brief\s+description",
        r"summary\s+of\s+(the\s+)?(principal\s+)?provisions",
    ],
}

_CLAUSE_CUES: dict[str, dict[str, list[str]]] = {
    "collective_action": CAC_CUES,
    "pari_passu": PARI_PASSU_CUES,
}


def get_cue_families(clause_family: str) -> dict[str, list[str]] | None:
    """Return cue families for a clause type, or None if unknown."""
    return _CLAUSE_CUES.get(clause_family)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cue_families.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/cue_families.py tests/test_cue_families.py
git commit -m "feat: cue family definitions for CAC and pari passu"
```

---

## Task 2: Section Parser

**Files:**
- Create: `src/corpus/extraction/section_parser.py`
- Test: `tests/test_section_parser.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_section_parser.py
"""Tests for Docling markdown section parser."""

from __future__ import annotations

from corpus.extraction.section_parser import Section, parse_docling_markdown


SAMPLE_MD = """\
## Risk Factors

Some risk factor text here spanning
multiple lines.

## Collective Action Clauses

The Bonds contain collective action clauses.
Under these provisions, holders of not less than
75% of the aggregate principal amount may modify
the terms.

### Aggregation

Cross-series modification is permitted.

## Governing Law

This prospectus is governed by English law.
"""


def test_parse_returns_sections() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    assert len(sections) >= 3


def test_section_has_heading() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    headings = [s.heading for s in sections]
    assert "Collective Action Clauses" in headings


def test_section_text_includes_body() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    cac = [s for s in sections if s.heading == "Collective Action Clauses"][0]
    assert "75% of the aggregate principal" in cac.text


def test_subsection_included_in_parent_or_separate() -> None:
    """Subsections (###) should either be part of parent or separate sections."""
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    all_text = " ".join(s.text for s in sections)
    assert "Cross-series modification" in all_text


def test_section_id_format() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    for s in sections:
        assert s.section_id.startswith("test__doc1__s")


def test_heading_level() -> None:
    sections = parse_docling_markdown(SAMPLE_MD, storage_key="test__doc1")
    cac = [s for s in sections if s.heading == "Collective Action Clauses"][0]
    assert cac.heading_level == 2


def test_all_caps_heading_detection() -> None:
    """ALL CAPS lines should be detected as headings."""
    md = """\
COLLECTIVE ACTION CLAUSES

The Bonds contain collective action clauses.

GOVERNING LAW

English law applies.
"""
    sections = parse_docling_markdown(md, storage_key="test__doc2")
    headings = [s.heading for s in sections]
    assert "COLLECTIVE ACTION CLAUSES" in headings


def test_max_section_size_split() -> None:
    """Sections exceeding max_chars should be split."""
    long_body = "word " * 4000  # ~20,000 chars
    md = f"## Very Long Section\n\n{long_body}\n\n## Next Section\n\nShort."
    sections = parse_docling_markdown(
        md, storage_key="test__doc3", max_section_chars=15000
    )
    # The long section should be split or capped
    for s in sections:
        assert s.char_count <= 16000  # allow some margin


def test_empty_input() -> None:
    sections = parse_docling_markdown("", storage_key="test__empty")
    assert sections == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_section_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/section_parser.py
"""Parse Docling markdown into sections for clause extraction.

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


# Matches markdown headings: # Heading, ## Heading, ### Heading
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# ALL CAPS lines that look like headings (short, no lowercase)
_ALL_CAPS_RE = re.compile(
    r"^([A-Z][A-Z\s,;:\-–—&/()]{4,78}[A-Z)])$", re.MULTILINE
)


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
        # Skip if it's inside a markdown heading (already captured)
        pos = m.start()
        if any(abs(pos - h[2]) < 5 for h in headings):
            continue
        # Must be followed by body text (not another heading immediately)
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
    """Parse markdown into sections.

    Args:
        markdown_text: Full document markdown from Docling.
        storage_key: Document identifier.
        max_section_chars: Split sections exceeding this size.

    Returns:
        List of Section objects, one per heading.
    """
    if not markdown_text.strip():
        return []

    headings = _split_at_headings(markdown_text)

    if not headings:
        # No headings found — treat entire doc as one section
        return [
            Section(
                section_id=f"{storage_key}__s0",
                storage_key=storage_key,
                heading="(no heading)",
                heading_level=0,
                text=markdown_text.strip(),
                page_range=(0, 0),
                source_format="docling_md",
                char_count=len(markdown_text.strip()),
            )
        ]

    sections: list[Section] = []
    for i, (heading_text, level, start) in enumerate(headings):
        # Section body runs from this heading to the next heading of same/higher level
        end = headings[i + 1][2] if i + 1 < len(headings) else len(markdown_text)
        body = markdown_text[start:end].strip()
        char_count = len(body)

        if char_count > max_section_chars:
            # Split at paragraph boundaries
            chunks = _split_large_section(body, max_section_chars)
            for ci, chunk in enumerate(chunks):
                sections.append(
                    Section(
                        section_id=f"{storage_key}__s{len(sections)}",
                        storage_key=storage_key,
                        heading=heading_text,
                        heading_level=level,
                        text=chunk,
                        page_range=(0, 0),
                        source_format="docling_md",
                        char_count=len(chunk),
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
                    page_range=(0, 0),
                    source_format="docling_md",
                    char_count=char_count,
                )
            )

    return sections


def _split_large_section(text: str, max_chars: int) -> list[str]:
    """Split a large section at paragraph boundaries."""
    paragraphs = re.split(r"\n\n+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_section_parser.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/section_parser.py tests/test_section_parser.py
git commit -m "feat: Docling markdown section parser"
```

---

## Task 3: Section Filter (LOCATE Stage)

**Files:**
- Create: `src/corpus/extraction/section_filter.py`
- Test: `tests/test_section_filter.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_section_filter.py
"""Tests for section filtering, negative rejection, and candidate clustering."""

from __future__ import annotations

from corpus.extraction.section_filter import (
    Candidate,
    CueHit,
    filter_sections,
    cluster_candidates,
)
from corpus.extraction.section_parser import Section


def _make_section(
    heading: str = "Collective Action",
    text: str = "The Bonds contain collective action clauses.",
    storage_key: str = "test__doc1",
    section_id: str = "test__doc1__s0",
    page_range: tuple[int, int] = (47, 49),
) -> Section:
    return Section(
        section_id=section_id,
        storage_key=storage_key,
        heading=heading,
        heading_level=2,
        text=text,
        page_range=page_range,
        source_format="docling_md",
        char_count=len(text),
    )


def test_heading_match_produces_candidate() -> None:
    sections = [_make_section(heading="Collective Action Clauses")]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1
    assert candidates[0].heading_match is True


def test_body_cue_diversity_produces_candidate() -> None:
    """Body with 2+ cue families should produce a candidate even without heading match."""
    text = (
        "The holders of not less than 75% may modify the reserved "
        "matter provisions through a meeting of noteholders."
    )
    sections = [_make_section(heading="Terms and Conditions", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1
    assert candidates[0].heading_match is False
    assert len(candidates[0].cue_families_hit) >= 2


def test_single_keyword_mention_rejected() -> None:
    """A section with just 'collective action' once and no heading match should be rejected."""
    text = "The collective action provisions are described elsewhere."
    sections = [_make_section(heading="Summary", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 0


def test_cross_reference_rejected() -> None:
    """Sections with cross-reference language should be rejected (body-only)."""
    text = 'See "Description of the Securities — Collective Action" for details about reserved matter modifications.'
    sections = [_make_section(heading="Summary", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 0


def test_toc_dot_leaders_rejected() -> None:
    text = "Collective Action .......................... 47\nGoverning Law .......................... 52"
    sections = [_make_section(heading="TABLE OF CONTENTS", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 0


def test_heading_match_not_rejected_by_negative() -> None:
    """Heading-matched sections are never auto-rejected."""
    text = 'See "Collective Action" below for the full clause.'
    sections = [_make_section(heading="Collective Action Clauses", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1


def test_candidate_has_cue_hits() -> None:
    sections = [_make_section()]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1
    assert len(candidates[0].cue_hits) > 0
    assert isinstance(candidates[0].cue_hits[0], CueHit)


def test_pari_passu_heading_match() -> None:
    sections = [_make_section(heading="Status of the Notes")]
    candidates = filter_sections(sections, clause_family="pari_passu")
    assert len(candidates) == 1


def test_cluster_merges_adjacent_pages() -> None:
    """Adjacent-page candidates from the same doc should be clustered."""
    c1 = Candidate(
        candidate_id="c1",
        storage_key="doc1",
        section_id="doc1__s5",
        section_heading="Modification",
        page_range=(47, 48),
        heading_match=True,
        cue_families_hit=["heading"],
        cue_hits=[],
        negative_signals=[],
        section_text="Part 1...",
        source_format="docling_md",
        run_id="run1",
    )
    c2 = Candidate(
        candidate_id="c2",
        storage_key="doc1",
        section_id="doc1__s6",
        section_heading="Aggregation",
        page_range=(49, 50),
        heading_match=True,
        cue_families_hit=["heading", "aggregation"],
        cue_hits=[],
        negative_signals=[],
        section_text="Part 2...",
        source_format="docling_md",
        run_id="run1",
    )
    clustered = cluster_candidates([c1, c2])
    assert len(clustered) == 1
    assert clustered[0].page_range == (47, 50)


def test_cluster_keeps_separate_docs_separate() -> None:
    c1 = Candidate(
        candidate_id="c1", storage_key="doc1", section_id="s1",
        section_heading="CAC", page_range=(10, 12),
        heading_match=True, cue_families_hit=["heading"], cue_hits=[],
        negative_signals=[], section_text="...", source_format="docling_md",
        run_id="run1",
    )
    c2 = Candidate(
        candidate_id="c2", storage_key="doc2", section_id="s2",
        section_heading="CAC", page_range=(10, 12),
        heading_match=True, cue_families_hit=["heading"], cue_hits=[],
        negative_signals=[], section_text="...", source_format="docling_md",
        run_id="run1",
    )
    clustered = cluster_candidates([c1, c2])
    assert len(clustered) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_section_filter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/section_filter.py
"""LOCATE stage: filter sections, reject negatives, cluster candidates.

Filters sections by heading patterns and body cues, rejects obvious false
positives (cross-references, ToC entries, summaries), and clusters adjacent-
page candidates from the same document into clause-level candidates.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from corpus.extraction.cue_families import NEGATIVE_PATTERNS, get_cue_families
from corpus.extraction.section_parser import Section


@dataclass(frozen=True)
class CueHit:
    family: str
    pattern: str
    matched_text: str


@dataclass
class Candidate:
    candidate_id: str
    storage_key: str
    section_id: str
    section_heading: str
    page_range: tuple[int, int]
    heading_match: bool
    cue_families_hit: list[str]
    cue_hits: list[CueHit]
    negative_signals: list[str]
    section_text: str
    source_format: str
    run_id: str


def _scan_cues(
    text: str, cue_families: dict[str, list[str]]
) -> tuple[list[str], list[CueHit]]:
    """Scan text for cue hits. Returns (families_hit, cue_hits)."""
    families_hit: set[str] = set()
    hits: list[CueHit] = []
    for family, patterns in cue_families.items():
        if family == "heading":
            continue  # heading cues are matched against heading, not body
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                families_hit.add(family)
                hits.append(CueHit(family=family, pattern=pattern, matched_text=m.group()))
    return sorted(families_hit), hits


def _check_heading(heading: str, heading_patterns: list[str]) -> bool:
    """Check if heading matches any heading pattern."""
    for pattern in heading_patterns:
        if re.search(pattern, heading, re.IGNORECASE):
            return True
    return False


def _check_negatives(text: str) -> list[str]:
    """Check for negative signals. Returns list of negative categories found."""
    found: list[str] = []
    for category, patterns in NEGATIVE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                found.append(category)
                break
    return found


def filter_sections(
    sections: list[Section],
    *,
    clause_family: str,
    run_id: str = "",
) -> list[Candidate]:
    """Filter sections to produce clause candidates.

    A section becomes a candidate if:
    - Heading matches a heading pattern (always passes), OR
    - Body has cues from 2+ different cue families with no dominant negatives

    Heading-matched sections are never auto-rejected by negatives.
    """
    cue_defs = get_cue_families(clause_family)
    if cue_defs is None:
        return []

    heading_patterns = cue_defs.get("heading", [])
    candidates: list[Candidate] = []

    for section in sections:
        heading_match = _check_heading(section.heading, heading_patterns)
        families_hit, cue_hits = _scan_cues(section.text, cue_defs)
        negative_signals = _check_negatives(section.text)

        if heading_match:
            # Heading match always produces a candidate
            candidates.append(
                Candidate(
                    candidate_id=str(uuid.uuid4())[:8],
                    storage_key=section.storage_key,
                    section_id=section.section_id,
                    section_heading=section.heading,
                    page_range=section.page_range,
                    heading_match=True,
                    cue_families_hit=["heading"] + families_hit,
                    cue_hits=cue_hits,
                    negative_signals=negative_signals,
                    section_text=section.text,
                    source_format=section.source_format,
                    run_id=run_id,
                )
            )
        elif len(families_hit) >= 2 and not _negatives_dominate(negative_signals, families_hit):
            # Body-only: require cue diversity and no dominant negatives
            candidates.append(
                Candidate(
                    candidate_id=str(uuid.uuid4())[:8],
                    storage_key=section.storage_key,
                    section_id=section.section_id,
                    section_heading=section.heading,
                    page_range=section.page_range,
                    heading_match=False,
                    cue_families_hit=families_hit,
                    cue_hits=cue_hits,
                    negative_signals=negative_signals,
                    section_text=section.text,
                    source_format=section.source_format,
                    run_id=run_id,
                )
            )

    return candidates


def _negatives_dominate(negatives: list[str], families: list[str]) -> bool:
    """Negatives dominate if there are more negative categories than positive families."""
    return len(negatives) >= len(families)


def cluster_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Cluster adjacent-page candidates from the same document.

    Merges candidates whose page ranges overlap or are adjacent (gap <= 1).
    """
    if not candidates:
        return []

    # Group by storage_key
    by_doc: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_doc.setdefault(c.storage_key, []).append(c)

    result: list[Candidate] = []
    for doc_candidates in by_doc.values():
        doc_candidates.sort(key=lambda c: c.page_range[0])
        clusters: list[list[Candidate]] = [[doc_candidates[0]]]

        for c in doc_candidates[1:]:
            prev_end = clusters[-1][-1].page_range[1]
            if c.page_range[0] <= prev_end + 2:  # adjacent or overlapping
                clusters[-1].append(c)
            else:
                clusters.append([c])

        for cluster in clusters:
            if len(cluster) == 1:
                result.append(cluster[0])
            else:
                # Merge cluster into single candidate
                merged = Candidate(
                    candidate_id=str(uuid.uuid4())[:8],
                    storage_key=cluster[0].storage_key,
                    section_id=cluster[0].section_id,
                    section_heading=cluster[0].section_heading,
                    page_range=(
                        cluster[0].page_range[0],
                        cluster[-1].page_range[1],
                    ),
                    heading_match=any(c.heading_match for c in cluster),
                    cue_families_hit=sorted(
                        set(f for c in cluster for f in c.cue_families_hit)
                    ),
                    cue_hits=[h for c in cluster for h in c.cue_hits],
                    negative_signals=sorted(
                        set(s for c in cluster for s in c.negative_signals)
                    ),
                    section_text="\n\n".join(c.section_text for c in cluster),
                    source_format=cluster[0].source_format,
                    run_id=cluster[0].run_id,
                )
                result.append(merged)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_section_filter.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/section_filter.py tests/test_section_filter.py
git commit -m "feat: section filter with cue families, negative rejection, clustering"
```

---

## Task 4: PDIP Calibration/Evaluation Split

**Files:**
- Create: `data/pdip/pdip_split_manifest.json`
- Create: `src/corpus/extraction/pdip_split.py`
- Test: `tests/test_pdip_split.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_pdip_split.py
"""Tests for PDIP calibration/evaluation split."""

from __future__ import annotations

import json
from pathlib import Path

from corpus.extraction.pdip_split import load_split, create_split


def test_create_split_returns_two_sets() -> None:
    annotations_path = Path("data/pdip/clause_annotations.jsonl")
    if not annotations_path.exists():
        import pytest
        pytest.skip("PDIP annotations not available")

    split = create_split(annotations_path, clause_family="collective_action", calibration_count=5)
    assert "calibration" in split
    assert "evaluation" in split
    assert len(split["calibration"]) == 5
    assert len(split["evaluation"]) > 0
    # No overlap
    assert set(split["calibration"]).isdisjoint(set(split["evaluation"]))


def test_load_split_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "clause_family": "collective_action",
        "created_at": "2026-03-28",
        "calibration": ["DOC1", "DOC2"],
        "evaluation": ["DOC3", "DOC4", "DOC5"],
    }
    path = tmp_path / "split.json"
    path.write_text(json.dumps(manifest))
    split = load_split(path)
    assert split["calibration"] == ["DOC1", "DOC2"]
    assert split["evaluation"] == ["DOC3", "DOC4", "DOC5"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pdip_split.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/pdip_split.py
"""PDIP calibration/evaluation split management.

Creates and loads a frozen split of PDIP-annotated documents for prompt
development (calibration) vs. metric reporting (evaluation). The split
must be frozen and committed before any LLM extraction runs.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path


def create_split(
    annotations_path: Path,
    *,
    clause_family: str,
    calibration_count: int = 5,
    seed: int = 42,
) -> dict:
    """Create a calibration/evaluation split from PDIP annotations.

    Args:
        annotations_path: Path to clause_annotations.jsonl.
        clause_family: Which clause family to split on.
        calibration_count: Number of docs for calibration set.
        seed: Random seed for reproducibility.

    Returns:
        Dict with 'calibration' and 'evaluation' doc_id lists.
    """
    doc_ids: set[str] = set()
    with annotations_path.open() as f:
        for line in f:
            record = json.loads(line)
            if record.get("label_family") == clause_family:
                doc_ids.add(record["doc_id"])

    doc_list = sorted(doc_ids)
    rng = random.Random(seed)
    rng.shuffle(doc_list)

    calibration = doc_list[:calibration_count]
    evaluation = doc_list[calibration_count:]

    return {
        "clause_family": clause_family,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "calibration": sorted(calibration),
        "evaluation": sorted(evaluation),
    }


def save_split(split: dict, path: Path) -> None:
    """Save split manifest to JSON file."""
    path.write_text(json.dumps(split, indent=2) + "\n")


def load_split(path: Path) -> dict:
    """Load split manifest from JSON file."""
    return json.loads(path.read_text())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pdip_split.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Create and commit the frozen split manifest**

```bash
uv run python3 -c "
from pathlib import Path
from corpus.extraction.pdip_split import create_split, save_split
split = create_split(Path('data/pdip/clause_annotations.jsonl'), clause_family='collective_action', calibration_count=5)
save_split(split, Path('data/pdip/pdip_split_manifest.json'))
print(f'Calibration ({len(split[\"calibration\"])}): {split[\"calibration\"]}')
print(f'Evaluation ({len(split[\"evaluation\"])}): {split[\"evaluation\"]}')
"
git add src/corpus/extraction/pdip_split.py tests/test_pdip_split.py data/pdip/pdip_split_manifest.json
git commit -m "feat: frozen PDIP calibration/evaluation split for CAC"
```

---

## Task 5: LLM Clause Extractor

**Files:**
- Create: `src/corpus/extraction/llm_extractor.py`
- Test: `tests/test_llm_extractor.py`
- Modify: `pyproject.toml` (add anthropic dependency)

- [ ] **Step 1: Add anthropic dependency**

```bash
uv add anthropic
```

- [ ] **Step 2: Write the test**

```python
# tests/test_llm_extractor.py
"""Tests for LLM clause extractor (mocked API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from corpus.extraction.llm_extractor import (
    ExtractionResult,
    build_extraction_prompt,
    parse_extraction_response,
)
from corpus.extraction.section_filter import Candidate


def _make_candidate(
    section_text: str = "## Collective Action\n\nThe Bonds may be modified...",
    section_heading: str = "Collective Action",
) -> Candidate:
    return Candidate(
        candidate_id="test1",
        storage_key="test__doc1",
        section_id="test__doc1__s5",
        section_heading=section_heading,
        page_range=(47, 49),
        heading_match=True,
        cue_families_hit=["heading", "voting_threshold"],
        cue_hits=[],
        negative_signals=[],
        section_text=section_text,
        source_format="docling_md",
        run_id="run1",
    )


def test_build_prompt_includes_system() -> None:
    candidate = _make_candidate()
    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family="collective_action",
        country="Indonesia",
        few_shot_examples=[],
    )
    assert messages[0]["role"] == "system"
    assert "verbatim" in messages[0]["content"].lower()


def test_build_prompt_includes_section_text() -> None:
    candidate = _make_candidate(section_text="The Bonds contain CAC provisions.")
    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family="collective_action",
        country="Indonesia",
        few_shot_examples=[],
    )
    full_text = " ".join(m["content"] for m in messages if isinstance(m["content"], str))
    assert "The Bonds contain CAC provisions" in full_text


def test_parse_found_response() -> None:
    tool_input = {
        "found": True,
        "clause_text": "The Bonds may be modified by holders of 75%.",
        "confidence": "high",
        "reasoning": "Clear CAC with voting threshold.",
    }
    result = parse_extraction_response(tool_input)
    assert isinstance(result, ExtractionResult)
    assert result.found is True
    assert result.clause_text == "The Bonds may be modified by holders of 75%."
    assert result.confidence == "high"


def test_parse_not_found_response() -> None:
    tool_input = {
        "found": False,
        "clause_text": "",
        "confidence": "high",
        "reasoning": "This is a cross-reference, not the clause.",
    }
    result = parse_extraction_response(tool_input)
    assert result.found is False
    assert result.clause_text == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write the implementation**

```python
# src/corpus/extraction/llm_extractor.py
"""LLM clause extraction with multi-shot prompt.

Sends shortlisted candidate sections to Claude Sonnet for verbatim clause
extraction. Uses structured output (tool_use) for guaranteed schema compliance.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic

from corpus.extraction.section_filter import Candidate

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192

SYSTEM_PROMPT = """\
You are a legal document analyst specializing in sovereign bond contracts.
Your task is to extract specific clause text verbatim from bond prospectuses.

Rules:
1. Extract the EXACT text as it appears in the source. Do not paraphrase,
   summarize, correct typos, or rephrase in any way.
2. Preserve all original formatting, whitespace, numbered lists, and
   punctuation exactly as they appear.
3. The clause begins where the substantive legal language starts and ends
   where the subject matter clearly changes or a new section of equal or
   higher heading level begins.
4. For CACs: ensure you extract ALL related sub-paragraphs including
   voting thresholds, reserved matters, aggregation provisions, meeting
   rules, and notice requirements. Do not stop at the first paragraph.
5. If the section does not contain the requested clause (e.g., it's a
   cross-reference, table of contents entry, or summary), return NOT_FOUND.
6. NOT_FOUND is a valid and expected answer. Never force an extraction."""

EXTRACTION_TOOL = {
    "name": "extract_clause",
    "description": "Extract a clause from a bond prospectus section, or report NOT_FOUND.",
    "input_schema": {
        "type": "object",
        "properties": {
            "found": {
                "type": "boolean",
                "description": "True if the clause was found in this section.",
            },
            "clause_text": {
                "type": "string",
                "description": "The verbatim clause text extracted from the section. Empty string if not found.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Confidence in the extraction quality.",
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence explaining why this is or isn't the clause.",
            },
        },
        "required": ["found", "clause_text", "confidence", "reasoning"],
    },
}

CLAUSE_DESCRIPTIONS = {
    "collective_action": "Collective Action Clause (CAC) — provisions allowing a qualified majority of bondholders to modify the terms of the bonds, including voting thresholds, reserved matters, aggregation mechanisms, and meeting/written resolution procedures.",
    "pari_passu": "Pari Passu Clause — provisions establishing that the bonds rank equally in right of payment with other unsecured and unsubordinated obligations of the issuer.",
}


@dataclass(frozen=True)
class ExtractionResult:
    found: bool
    clause_text: str
    confidence: str
    reasoning: str


@dataclass(frozen=True)
class FewShotExample:
    section_text: str
    extracted_text: str
    country: str
    is_negative: bool  # True = NOT_FOUND example


def build_extraction_prompt(
    *,
    candidate: Candidate,
    clause_family: str,
    country: str,
    few_shot_examples: list[FewShotExample],
    icma_reference: str = "",
) -> list[dict]:
    """Build the message list for the extraction API call."""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    clause_desc = CLAUSE_DESCRIPTIONS.get(clause_family, clause_family)

    # ICMA reference (if provided)
    if icma_reference:
        messages.append({
            "role": "user",
            "content": f"For reference, here is the ICMA model {clause_family} language:\n\n{icma_reference}",
        })
        messages.append({
            "role": "assistant",
            "content": "Understood. I'll use this as a reference for what this type of clause looks like, while recognizing that real-world clauses vary substantially.",
        })

    # Few-shot examples
    for ex in few_shot_examples:
        messages.append({
            "role": "user",
            "content": f"Extract the {clause_desc} from this section of a {ex.country} bond prospectus:\n\n{ex.section_text}",
        })
        if ex.is_negative:
            # Simulate tool use response for NOT_FOUND
            messages.append({
                "role": "assistant",
                "content": f"This section does not contain the {clause_family} clause — it is a cross-reference. NOT_FOUND.",
            })
        else:
            messages.append({
                "role": "assistant",
                "content": f"Here is the extracted {clause_family} clause:\n\n{ex.extracted_text}",
            })

    # The actual task
    messages.append({
        "role": "user",
        "content": (
            f"Extract the {clause_desc} from this section of a {country} "
            f"bond prospectus (section heading: \"{candidate.section_heading}\", "
            f"pages {candidate.page_range[0]}-{candidate.page_range[1]}):\n\n"
            f"{candidate.section_text}"
        ),
    })

    return messages


def parse_extraction_response(tool_input: dict) -> ExtractionResult:
    """Parse the structured tool_use response into an ExtractionResult."""
    return ExtractionResult(
        found=tool_input["found"],
        clause_text=tool_input.get("clause_text", ""),
        confidence=tool_input.get("confidence", "low"),
        reasoning=tool_input.get("reasoning", ""),
    )


def extract_clause(
    *,
    candidate: Candidate,
    clause_family: str,
    country: str,
    few_shot_examples: list[FewShotExample],
    icma_reference: str = "",
    api_key: str | None = None,
) -> ExtractionResult:
    """Call Claude Sonnet to extract a clause from a candidate section.

    Args:
        candidate: The candidate section to extract from.
        clause_family: Which clause type to extract.
        country: Issuer country for context.
        few_shot_examples: Multi-shot examples for the prompt.
        icma_reference: Optional ICMA model language.
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var).

    Returns:
        ExtractionResult with found, clause_text, confidence, reasoning.
    """
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family=clause_family,
        country=country,
        few_shot_examples=few_shot_examples,
        icma_reference=icma_reference,
    )

    # Separate system message from conversation
    system = messages[0]["content"]
    conversation = messages[1:]

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=conversation,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_clause"},
    )

    # Extract tool use result
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_clause":
            return parse_extraction_response(block.input)

    # Fallback if no tool use in response
    return ExtractionResult(
        found=False,
        clause_text="",
        confidence="low",
        reasoning="LLM did not return structured extraction.",
    )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_llm_extractor.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/corpus/extraction/llm_extractor.py tests/test_llm_extractor.py pyproject.toml uv.lock
git commit -m "feat: LLM clause extractor with structured output"
```

---

## Task 6: Verification Stage

**Files:**
- Create: `src/corpus/extraction/verify.py`
- Test: `tests/test_verify.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_verify.py
"""Tests for extraction verification: verbatim check, completeness, quality flags."""

from __future__ import annotations

from corpus.extraction.verify import (
    check_completeness,
    check_verbatim,
    compute_quality_flags,
)


def test_verbatim_exact_match() -> None:
    result = check_verbatim(
        extracted="The Bonds may be modified.",
        source="Some preamble. The Bonds may be modified. Some conclusion.",
    )
    assert result.passes is True
    assert result.similarity >= 0.99


def test_verbatim_whitespace_normalized() -> None:
    result = check_verbatim(
        extracted="The  Bonds\nmay be modified.",
        source="Some text. The Bonds may be modified. More text.",
    )
    assert result.passes is True


def test_verbatim_fails_on_paraphrase() -> None:
    result = check_verbatim(
        extracted="Bond terms can be changed by majority vote.",
        source="The Bonds may be modified by holders of 75%.",
    )
    assert result.passes is False


def test_completeness_cac_full() -> None:
    text = (
        "holders of not less than 75% of the aggregate principal amount "
        "may modify reserved matter provisions through a meeting of "
        "noteholders. Cross-series aggregation applies."
    )
    report = check_completeness(text, clause_family="collective_action")
    assert report["voting_threshold"] is True
    assert report["reserved_matter"] is True
    assert report["meeting_quorum"] is True
    assert report["aggregation"] is True


def test_completeness_cac_partial() -> None:
    text = "The bonds contain collective action clauses."
    report = check_completeness(text, clause_family="collective_action")
    assert report["voting_threshold"] is False
    assert report["reserved_matter"] is False


def test_completeness_pari_passu() -> None:
    text = "The Notes rank pari passu with all unsecured and unsubordinated obligations."
    report = check_completeness(text, clause_family="pari_passu")
    assert report["ranking"] is True
    assert report["obligation"] is True


def test_quality_flags_truncation() -> None:
    flags = compute_quality_flags(
        extracted="The bonds may be modified by holders of",
        source="The bonds may be modified by holders of not less than 75%.",
    )
    assert "truncation_suspect" in flags


def test_quality_flags_ocr_suspect() -> None:
    # High non-alpha ratio suggests OCR issues
    source = "Th3 B0nds m@y b3 m0d!f!3d by h0ld3rs 0f n0t l3ss th@n 75%."
    flags = compute_quality_flags(extracted="", source=source)
    assert "ocr_suspect" in flags
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_verify.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/verify.py
"""VERIFY stage: verbatim validation, completeness checklist, quality flags.

Post-LLM verification to catch paraphrasing, truncation, and OCR issues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class VerbatimResult:
    passes: bool
    similarity: float
    normalized_extracted: str
    normalized_source: str


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison: collapse runs, strip."""
    return re.sub(r"\s+", " ", text).strip()


def check_verbatim(
    extracted: str,
    source: str,
    *,
    threshold: float = 0.95,
) -> VerbatimResult:
    """Check if extracted text appears verbatim in source.

    Uses whitespace-normalized comparison. The extracted text should be a
    substring of the source (with whitespace flexibility), scoring >= threshold.
    """
    norm_ext = _normalize_whitespace(extracted)
    norm_src = _normalize_whitespace(source)

    if not norm_ext:
        return VerbatimResult(passes=False, similarity=0.0,
                              normalized_extracted=norm_ext, normalized_source=norm_src)

    # Check substring containment first (fast path)
    if norm_ext in norm_src:
        return VerbatimResult(passes=True, similarity=1.0,
                              normalized_extracted=norm_ext, normalized_source=norm_src)

    # Fall back to sequence matching for near-verbatim
    matcher = SequenceMatcher(None, norm_ext, norm_src)
    # Find the best matching block region
    blocks = matcher.get_matching_blocks()
    if not blocks:
        return VerbatimResult(passes=False, similarity=0.0,
                              normalized_extracted=norm_ext, normalized_source=norm_src)

    # Compute ratio of extracted text that matches source
    total_matched = sum(b.size for b in blocks)
    similarity = total_matched / len(norm_ext) if norm_ext else 0.0

    return VerbatimResult(
        passes=similarity >= threshold,
        similarity=similarity,
        normalized_extracted=norm_ext,
        normalized_source=norm_src,
    )


# Completeness checklist components per clause family
_CAC_COMPONENTS: dict[str, list[str]] = {
    "voting_threshold": [
        r"holders?\s+of\s+(not\s+less\s+than\s+)?\d+%",
        r"\d+%\s+of\s+the\s+aggregate",
        r"extraordinary\s+resolution",
    ],
    "reserved_matter": [
        r"reserved\s+matter",
    ],
    "meeting_quorum": [
        r"quorum",
        r"meeting\s+of\s+(note|bond)?holders",
        r"written\s+resolution",
    ],
    "aggregation": [
        r"aggregat(ion|ed)",
        r"cross[\s-]+series",
        r"single[\s-]+limb",
    ],
}

_PARI_PASSU_COMPONENTS: dict[str, list[str]] = {
    "ranking": [
        r"rank\s*(s|ing)?",
        r"pari\s+passu",
        r"equally",
        r"without\s+preference",
    ],
    "obligation": [
        r"unsecured",
        r"unsubordinated",
        r"direct",
    ],
}


def check_completeness(
    extracted_text: str,
    *,
    clause_family: str,
) -> dict[str, bool]:
    """Check which clause components are present in the extracted text."""
    components = (
        _CAC_COMPONENTS if clause_family == "collective_action"
        else _PARI_PASSU_COMPONENTS if clause_family == "pari_passu"
        else {}
    )

    report: dict[str, bool] = {}
    for component, patterns in components.items():
        report[component] = any(
            re.search(p, extracted_text, re.IGNORECASE) for p in patterns
        )
    return report


def compute_quality_flags(
    *,
    extracted: str,
    source: str,
) -> list[str]:
    """Compute quality flags for an extraction."""
    flags: list[str] = []

    # Truncation: extracted ends mid-sentence
    if extracted and not extracted.rstrip().endswith((".", ")", '"', "'", ";")):
        last_word = extracted.rstrip().split()[-1] if extracted.strip() else ""
        if last_word and last_word[-1].isalpha():
            flags.append("truncation_suspect")

    # OCR quality: high non-alphanumeric ratio in source
    if source:
        alpha_count = sum(1 for c in source if c.isalpha())
        total = len(source)
        if total > 100 and alpha_count / total < 0.6:
            flags.append("ocr_suspect")

    return flags
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_verify.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/verify.py tests/test_verify.py
git commit -m "feat: verification stage — verbatim check, completeness, quality flags"
```

---

## Task 7: CLI Commands (LOCATE + EXTRACT + VERIFY)

**Files:**
- Modify: `src/corpus/cli.py`
- Test: Integration test via command line

This is the orchestration layer that ties Tasks 1-6 together into runnable
CLI commands. The three commands can run independently (LOCATE produces
JSONL, EXTRACT reads JSONL, VERIFY reads JSONL).

- [ ] **Step 1: Add the extract-v2 command group to cli.py**

Add at the end of `src/corpus/cli.py`, before the `app = App(...)` line or at the module level:

```python
# Add these imports at the top of cli.py
import json as _json
import time as _time
from pathlib import Path as _Path

@main.group("extract-v2")
def extract_v2_group():
    """Clause extraction v2: section-aware pipeline."""
    pass


@extract_v2_group.command("locate")
@click.option("--clause-family", required=True, type=click.Choice(["collective_action", "pari_passu"]))
@click.option("--parsed-dir", default="data/parsed_docling", type=click.Path(exists=True))
@click.option("--output", default="data/extracted_v2/candidates.jsonl", type=click.Path())
@click.option("--run-id", default=None)
def extract_v2_locate(clause_family: str, parsed_dir: str, output: str, run_id: str | None):
    """Stage 1: Parse sections, filter by cues, reject negatives, cluster."""
    from corpus.extraction.section_parser import parse_docling_markdown
    from corpus.extraction.section_filter import filter_sections, cluster_candidates

    run_id = run_id or f"locate_{int(_time.time())}"
    parsed_path = _Path(parsed_dir)
    output_path = _Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md_files = sorted(parsed_path.glob("*.md"))
    click.echo(f"Scanning {len(md_files)} Docling markdown files for {clause_family}...")

    all_candidates = []
    docs_with_candidates = 0

    for md_file in md_files:
        storage_key = md_file.stem
        markdown_text = md_file.read_text(encoding="utf-8")
        sections = parse_docling_markdown(markdown_text, storage_key=storage_key)
        candidates = filter_sections(sections, clause_family=clause_family, run_id=run_id)
        if candidates:
            docs_with_candidates += 1
            all_candidates.extend(candidates)

    # Cluster adjacent candidates
    clustered = cluster_candidates(all_candidates)

    # Write JSONL
    with output_path.open("w") as f:
        for c in clustered:
            record = {
                "candidate_id": c.candidate_id,
                "storage_key": c.storage_key,
                "section_id": c.section_id,
                "section_heading": c.section_heading,
                "page_range": list(c.page_range),
                "heading_match": c.heading_match,
                "cue_families_hit": c.cue_families_hit,
                "cue_hits": [{"family": h.family, "pattern": h.pattern, "matched_text": h.matched_text} for h in c.cue_hits],
                "negative_signals": c.negative_signals,
                "section_text": c.section_text,
                "source_format": c.source_format,
                "run_id": c.run_id,
                "clause_family": clause_family,
            }
            f.write(_json.dumps(record) + "\n")

    click.echo(f"Found {len(clustered)} candidates from {docs_with_candidates} documents.")
    click.echo(f"Written to {output_path}")


@extract_v2_group.command("extract")
@click.option("--candidates", required=True, type=click.Path(exists=True))
@click.option("--clause-family", required=True, type=click.Choice(["collective_action", "pari_passu"]))
@click.option("--output", default="data/extracted_v2/extractions.jsonl", type=click.Path())
@click.option("--split-manifest", default="data/pdip/pdip_split_manifest.json", type=click.Path())
@click.option("--limit", default=0, type=int, help="Max candidates to process (0=all)")
def extract_v2_extract(candidates: str, clause_family: str, output: str, split_manifest: str, limit: int):
    """Stage 2: LLM extraction on shortlisted candidates."""
    from corpus.extraction.llm_extractor import extract_clause, FewShotExample
    from corpus.extraction.section_filter import Candidate, CueHit

    candidates_path = _Path(candidates)
    output_path = _Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load candidates
    candidate_records = []
    with candidates_path.open() as f:
        for line in f:
            candidate_records.append(_json.loads(line))

    if limit > 0:
        candidate_records = candidate_records[:limit]

    click.echo(f"Extracting {clause_family} from {len(candidate_records)} candidates...")

    # TODO: Load few-shot examples from calibration set
    # For now, use empty examples (the system prompt is sufficient for a first run)
    few_shot_examples: list[FewShotExample] = []

    results = []
    for i, rec in enumerate(candidate_records):
        candidate = Candidate(
            candidate_id=rec["candidate_id"],
            storage_key=rec["storage_key"],
            section_id=rec["section_id"],
            section_heading=rec["section_heading"],
            page_range=tuple(rec["page_range"]),
            heading_match=rec["heading_match"],
            cue_families_hit=rec["cue_families_hit"],
            cue_hits=[CueHit(**h) for h in rec.get("cue_hits", [])],
            negative_signals=rec.get("negative_signals", []),
            section_text=rec["section_text"],
            source_format=rec["source_format"],
            run_id=rec["run_id"],
        )

        # Determine country from storage_key (best effort)
        country = rec.get("country", "Unknown")

        try:
            result = extract_clause(
                candidate=candidate,
                clause_family=clause_family,
                country=country,
                few_shot_examples=few_shot_examples,
            )
            output_rec = {
                **rec,
                "extraction": {
                    "found": result.found,
                    "clause_text": result.clause_text,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning,
                },
            }
        except Exception as e:
            click.echo(f"  Error on {rec['candidate_id']}: {e}", err=True)
            output_rec = {
                **rec,
                "extraction": {
                    "found": False,
                    "clause_text": "",
                    "confidence": "low",
                    "reasoning": f"API error: {e}",
                },
                "error": str(e),
            }

        results.append(output_rec)
        status = "FOUND" if output_rec["extraction"]["found"] else "NOT_FOUND"
        click.echo(f"  [{i+1}/{len(candidate_records)}] {rec['storage_key']}: {status} ({output_rec['extraction']['confidence']})")

    # Write results
    with output_path.open("w") as f:
        for r in results:
            f.write(_json.dumps(r) + "\n")

    found_count = sum(1 for r in results if r["extraction"]["found"])
    click.echo(f"\nDone: {found_count}/{len(results)} clauses found. Written to {output_path}")


@extract_v2_group.command("verify")
@click.option("--extractions", required=True, type=click.Path(exists=True))
@click.option("--clause-family", required=True, type=click.Choice(["collective_action", "pari_passu"]))
@click.option("--output", default="data/extracted_v2/verified.jsonl", type=click.Path())
def extract_v2_verify(extractions: str, clause_family: str, output: str):
    """Stage 3: Verify extractions — verbatim check, completeness, quality flags."""
    from corpus.extraction.verify import check_completeness, check_verbatim, compute_quality_flags

    extractions_path = _Path(extractions)
    output_path = _Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    with extractions_path.open() as f:
        for line in f:
            records.append(_json.loads(line))

    click.echo(f"Verifying {len(records)} extractions...")
    verified = []
    pass_count = 0

    for rec in records:
        ext = rec.get("extraction", {})
        if not ext.get("found"):
            rec["verification"] = {"status": "not_found"}
            verified.append(rec)
            continue

        clause_text = ext["clause_text"]
        source_text = rec["section_text"]

        verbatim = check_verbatim(clause_text, source_text)
        completeness = check_completeness(clause_text, clause_family=clause_family)
        quality_flags = compute_quality_flags(extracted=clause_text, source=source_text)

        if not verbatim.passes:
            quality_flags.append("verification_failed")

        components_present = sum(1 for v in completeness.values() if v)
        components_total = len(completeness)
        if components_present <= 1 and components_total >= 3:
            quality_flags.append("partial_extraction")

        rec["verification"] = {
            "status": "verified" if verbatim.passes else "failed",
            "verbatim_similarity": round(verbatim.similarity, 3),
            "completeness": completeness,
            "quality_flags": quality_flags,
            "components_present": components_present,
            "components_total": components_total,
        }

        if verbatim.passes:
            pass_count += 1

        verified.append(rec)

    with output_path.open("w") as f:
        for r in verified:
            f.write(_json.dumps(r) + "\n")

    found = sum(1 for r in verified if r.get("extraction", {}).get("found"))
    click.echo(f"\nVerification: {pass_count}/{found} passed verbatim check.")
    click.echo(f"Written to {output_path}")
```

- [ ] **Step 2: Test the CLI commands exist**

Run: `uv run corpus extract-v2 --help`
Expected: Shows the three subcommands: locate, extract, verify

Run: `uv run corpus extract-v2 locate --help`
Expected: Shows options: --clause-family, --parsed-dir, --output, --run-id

- [ ] **Step 3: Run LOCATE on a small sample**

```bash
uv run corpus extract-v2 locate \
  --clause-family collective_action \
  --output data/extracted_v2/cac_candidates.jsonl
```

Expected: Scans ~1,468+ markdown files, outputs candidates JSONL. Should find significantly fewer candidates than the 1,570 raw grep hits.

- [ ] **Step 4: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: CLI commands for extract-v2 pipeline (locate, extract, verify)"
```

---

## Task 8: Shiny Explorer v2

**Files:**
- Create: `demo/shiny-app/app_v2.py`
- Create: `demo/data/export_v2.py`

- [ ] **Step 1: Write the export script**

```python
# demo/data/export_v2.py
"""Export v2 extraction results for the Shiny clause eval explorer."""

from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
VERIFIED_PATH = Path("data/extracted_v2/verified.jsonl")
OUTPUT_PATH = DATA_DIR / "clause_candidates_v2.csv"


def export_v2_candidates(
    verified_path: Path = VERIFIED_PATH,
    output_path: Path = OUTPUT_PATH,
) -> None:
    """Export verified extractions to CSV for Shiny app."""
    records = []
    with verified_path.open() as f:
        for line in f:
            rec = json.loads(line)
            ext = rec.get("extraction", {})
            ver = rec.get("verification", {})

            if not ext.get("found"):
                continue

            records.append({
                "candidate_id": rec["candidate_id"],
                "storage_key": rec["storage_key"],
                "country": rec.get("country", ""),
                "document_title": rec.get("document_title", rec["storage_key"]),
                "section_heading": rec["section_heading"],
                "page_start": rec["page_range"][0] if rec.get("page_range") else "",
                "page_end": rec["page_range"][1] if rec.get("page_range") else "",
                "heading_match": "Yes" if rec.get("heading_match") else "No",
                "cue_families": ", ".join(rec.get("cue_families_hit", [])),
                "llm_confidence": ext.get("confidence", ""),
                "llm_reasoning": ext.get("reasoning", ""),
                "clause_text": ext.get("clause_text", ""),
                "clause_length": len(ext.get("clause_text", "")),
                "section_text": rec.get("section_text", ""),
                "verbatim_status": ver.get("status", ""),
                "verbatim_similarity": ver.get("verbatim_similarity", ""),
                "components_present": ver.get("components_present", ""),
                "components_total": ver.get("components_total", ""),
                "quality_flags": ", ".join(ver.get("quality_flags", [])),
                "completeness": json.dumps(ver.get("completeness", {})),
                "source_format": rec.get("source_format", ""),
                "run_id": rec.get("run_id", ""),
                "clause_family": rec.get("clause_family", ""),
            })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if records:
        with output_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)

    print(f"Exported {len(records)} verified extractions to {output_path}")


if __name__ == "__main__":
    export_v2_candidates()
```

- [ ] **Step 2: Write the Shiny app v2**

Create `demo/shiny-app/app_v2.py` — this is a substantial file implementing the lawyer-centered design. The key changes from `app.py`:

- Primary object is extracted clause, not keyword hit
- Table shows: Country, Document, Section, Page, Surfaced By, LLM Confidence, Clause Preview
- Detail view: extracted clause (primary), section context (expandable), signals
- Structured feedback: Correct / Wrong Boundaries / Not a Clause / Partial / Needs Second Look
- Feedback log captures timestamp and elapsed time
- Sanitized markdown rendering
- Copy reflects "validate" not "rate"

Due to the size of this file (~350 lines), the implementing agent should:
1. Copy `app.py` as a starting point
2. Restructure the card layout per the design doc
3. Update the data loading to use `clause_candidates_v2.csv`
4. Update the table columns and detail view
5. Update the feedback options and logging

The full code is the implementation agent's task, guided by `docs/lawyer-centered-design.md`.

- [ ] **Step 3: Test the app locally**

```bash
cd demo/shiny-app
uv run shiny run app_v2.py --port 8001
```

Open http://localhost:8001 and verify:
- Table shows clause candidates with correct columns
- Clicking a row shows extracted clause as primary element
- Section context is available (expandable)
- Feedback buttons work with structured options
- Feedback log captures timestamp

- [ ] **Step 4: Commit**

```bash
git add demo/data/export_v2.py demo/shiny-app/app_v2.py
git commit -m "feat: Shiny explorer v2 — clause-first layout, structured validation"
```

---

## Task 9: End-to-End Integration Test

**Files:**
- No new files — this validates the full pipeline

- [ ] **Step 1: Run the full pipeline on a small sample**

```bash
# Stage 1: LOCATE
uv run corpus extract-v2 locate \
  --clause-family collective_action \
  --output data/extracted_v2/cac_candidates.jsonl

# Check results
echo "Candidates:" && wc -l data/extracted_v2/cac_candidates.jsonl
head -1 data/extracted_v2/cac_candidates.jsonl | python3 -m json.tool | head -20

# Stage 2: EXTRACT (limit to 5 for testing)
uv run corpus extract-v2 extract \
  --candidates data/extracted_v2/cac_candidates.jsonl \
  --clause-family collective_action \
  --output data/extracted_v2/cac_extractions.jsonl \
  --limit 5

# Stage 3: VERIFY
uv run corpus extract-v2 verify \
  --extractions data/extracted_v2/cac_extractions.jsonl \
  --clause-family collective_action \
  --output data/extracted_v2/cac_verified.jsonl

# Export for Shiny
uv run python3 demo/data/export_v2.py
```

- [ ] **Step 2: Run lint and type checks**

```bash
ruff check src/corpus/extraction/section_parser.py src/corpus/extraction/section_filter.py \
  src/corpus/extraction/llm_extractor.py src/corpus/extraction/verify.py \
  src/corpus/extraction/cue_families.py src/corpus/extraction/pdip_split.py
ruff format --check src/ tests/
uv run pytest -v tests/test_cue_families.py tests/test_section_parser.py \
  tests/test_section_filter.py tests/test_llm_extractor.py tests/test_verify.py \
  tests/test_pdip_split.py
```

Expected: All lint clean, all tests pass.

- [ ] **Step 3: Commit integration test results**

```bash
git add -A
git commit -m "feat: end-to-end pipeline validated with sample extraction"
```

---

## Task 10: Full Overnight Run

**Files:**
- No new files — this is the production run

- [ ] **Step 1: Run LOCATE on full corpus**

```bash
uv run corpus extract-v2 locate \
  --clause-family collective_action \
  --output data/extracted_v2/cac_candidates.jsonl
```

Record the candidate count.

- [ ] **Step 2: Run EXTRACT on all candidates (overnight)**

```bash
export ANTHROPIC_API_KEY="..."  # or already in environment

nohup uv run corpus extract-v2 extract \
  --candidates data/extracted_v2/cac_candidates.jsonl \
  --clause-family collective_action \
  --output data/extracted_v2/cac_extractions.jsonl \
  > data/extracted_v2/_extract_stdout.log 2>&1 &

echo "Started PID $!. Monitor: tail -f data/extracted_v2/_extract_stdout.log"
```

- [ ] **Step 3: After extraction completes, run VERIFY**

```bash
uv run corpus extract-v2 verify \
  --extractions data/extracted_v2/cac_extractions.jsonl \
  --clause-family collective_action \
  --output data/extracted_v2/cac_verified.jsonl
```

- [ ] **Step 4: Export and review in Shiny**

```bash
uv run python3 demo/data/export_v2.py
cd demo/shiny-app
uv run shiny run app_v2.py --port 8001
```

- [ ] **Step 5: If time permits, run pari passu**

```bash
uv run corpus extract-v2 locate \
  --clause-family pari_passu \
  --output data/extracted_v2/pp_candidates.jsonl

uv run corpus extract-v2 extract \
  --candidates data/extracted_v2/pp_candidates.jsonl \
  --clause-family pari_passu \
  --output data/extracted_v2/pp_extractions.jsonl

uv run corpus extract-v2 verify \
  --extractions data/extracted_v2/pp_extractions.jsonl \
  --clause-family pari_passu \
  --output data/extracted_v2/pp_verified.jsonl
```

---

## Known Risks and Mitigations

| Risk | Mitigation | When to check |
|---|---|---|
| Docling markdown has inconsistent headings | ALL CAPS heuristic in section parser | After LOCATE — check candidate count |
| LLM truncates long CAC clauses | Explicit prompt instruction + completeness checklist flags partials | After VERIFY — check truncation_suspect count |
| Verbatim check rejects good extractions | 95% threshold + whitespace normalization. If reject rate is high, lower to 90% | After VERIFY — check pass rate |
| PDIP validation recall is low (<50%) | Run PDIP eval early (Task 9). Debug: are heading patterns missing? OCR issues? | Saturday morning |
| ANTHROPIC_API_KEY not set | Extract command will fail immediately with clear error | Before overnight run |
| Too many candidates (>500) | Check LOCATE output. If >500, tighten heading patterns or add more negative patterns | After LOCATE |
| Shiny app crashes on large CSV | Test with full dataset before demo. Paginate if needed | After export |
| Docling .md files not in data/parsed_docling/ | Check path. May need to set --parsed-dir | Before LOCATE |
