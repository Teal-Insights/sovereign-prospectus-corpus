"""Tests for grep runner."""

from __future__ import annotations

import re

from corpus.extraction.clause_patterns import ClausePattern
from corpus.extraction.grep_runner import (
    build_searchable_text,
    grep_document,
    offset_to_page_index,
)

SAMPLE_PAGES = [
    "Republic of Testland\nSovereign Bond Prospectus\n\nThis offering relates to bonds.",
    (
        "Collective Action Clauses\n\n"
        "The terms of the Notes may be modified with the consent of holders of "
        "not less than 75% in aggregate principal amount."
    ),
    (
        "The Notes rank pari passu in right of payment with all other "
        "unsecured and unsubordinated obligations of the Issuer."
    ),
    (
        "This Agreement shall be governed by and construed in accordance "
        "with the laws of the State of New York."
    ),
]

TEST_PATTERN = ClausePattern(
    name="test_cac",
    family="cac",
    version="1.0.0",
    finder=re.compile(r"collective\s+action", re.IGNORECASE),
    description="test",
    instrument_scope="both",
)


def test_build_searchable_text() -> None:
    full_text, offsets = build_searchable_text(SAMPLE_PAGES)
    assert len(offsets) == 4
    assert offsets[0] == 0
    assert "Republic of Testland" in full_text
    assert "pari passu" in full_text


def test_offset_to_page_index() -> None:
    _, offsets = build_searchable_text(SAMPLE_PAGES)
    assert offset_to_page_index(0, offsets) == 0
    assert offset_to_page_index(offsets[1] + 10, offsets) == 1
    assert offset_to_page_index(offsets[3] + 5, offsets) == 3


def test_grep_document_finds_matches() -> None:
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    assert len(matches) >= 1
    assert matches[0].pattern_name == "test_cac"
    assert matches[0].page_index == 1


def test_grep_document_captures_context() -> None:
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    match = matches[0]
    assert len(match.context_before) > 0
    assert len(match.context_after) > 0
    assert len(match.context_before) <= 600
    assert len(match.context_after) <= 600


def test_grep_document_verbatim_assertion() -> None:
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN],
        document_id="TEST1",
        run_id="test-run",
    )
    for match in matches:
        full_text = "\n\n".join(SAMPLE_PAGES)
        assert match.matched_text in full_text


def test_grep_document_no_matches_returns_empty() -> None:
    no_match_pattern = ClausePattern(
        name="no_match",
        family="test",
        version="1.0.0",
        finder=re.compile(r"xyzzy_will_not_match"),
        description="",
        instrument_scope="both",
    )
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[no_match_pattern],
        document_id="TEST1",
        run_id="test-run",
    )
    assert len(matches) == 0


def test_grep_document_multiple_patterns() -> None:
    pari_pattern = ClausePattern(
        name="pari_passu",
        family="pari_passu",
        version="1.0.0",
        finder=re.compile(r"pari\s+passu", re.IGNORECASE),
        description="",
        instrument_scope="both",
    )
    matches = grep_document(
        pages=SAMPLE_PAGES,
        patterns=[TEST_PATTERN, pari_pattern],
        document_id="TEST1",
        run_id="test-run",
    )
    names = {m.pattern_name for m in matches}
    assert "test_cac" in names
    assert "pari_passu" in names
