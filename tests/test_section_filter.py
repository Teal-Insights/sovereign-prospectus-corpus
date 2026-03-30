# tests/test_section_filter.py
"""Tests for section filtering, negative rejection, and candidate clustering."""

from __future__ import annotations

from corpus.extraction.section_filter import (
    Candidate,
    CueHit,
    cluster_candidates,
    filter_sections,
)
from corpus.extraction.section_parser import Section


def _make_section(
    heading: str = "Collective Action",
    text: str = "The Bonds contain collective action clauses.",
    storage_key: str = "test__doc1",
    section_id: str = "test__doc1__s0",
    page_range: tuple[int, int] = (47, 49),
    section_index: int = 0,
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
        section_index=section_index,
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


def test_negatives_equal_positives_not_rejected() -> None:
    """When negative count equals positive count, section should pass (strict >)."""
    # This text has 2 positive families (voting_threshold + meeting_quorum)
    # and 1 cross-reference negative. With >=, 1 negative >= 2 families was False
    # anyway, but with 2 negatives and 2 families the old >= was True (rejected).
    # Test: 2 negatives, 2 families — old code rejected, new code passes.
    text = (
        'See "Description of Bonds" for details. '
        "The following is a brief summary of the provisions. "
        "The holders of not less than 75% of the aggregate principal "
        "may pass a resolution at a meeting of noteholders."
    )
    sections = [_make_section(heading="Terms and Conditions", text=text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1


def test_large_section_skips_negative_filtering() -> None:
    """Sections >50K chars skip negative filtering (false positives on large EDGAR filings)."""
    # Create a large section with cross_reference + toc patterns that would normally reject
    base_text = (
        'See "Annex A" for the full provisions. '
        "Collective Action .......................... 47\n"
        "The holders of not less than 75% of the aggregate principal "
        "may pass an extraordinary resolution at a meeting of noteholders."
    )
    # Pad to >50K chars
    large_text = base_text + ("\nAdditional prospectus content. " * 2000)
    sections = [_make_section(heading="Terms and Conditions", text=large_text)]
    candidates = filter_sections(sections, clause_family="collective_action")
    assert len(candidates) == 1


def test_pari_passu_heading_match() -> None:
    sections = [_make_section(heading="Status of the Notes")]
    candidates = filter_sections(sections, clause_family="pari_passu")
    assert len(candidates) == 1


def test_cluster_merges_adjacent_sections() -> None:
    """Adjacent-section candidates from the same doc should be clustered (E1: use section_index)."""
    c1 = Candidate(
        candidate_id="c1",
        storage_key="doc1",
        section_id="doc1__s5",
        section_index=5,
        section_heading="Modification",
        page_range=(0, 0),
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
        section_index=6,
        section_heading="Aggregation",
        page_range=(0, 0),
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
    assert "Part 1" in clustered[0].section_text
    assert "Part 2" in clustered[0].section_text


def test_cluster_does_not_merge_gap_of_two() -> None:
    """Sections with a gap of 2+ in section_index should NOT be merged."""
    c1 = Candidate(
        candidate_id="c1",
        storage_key="doc1",
        section_id="doc1__s5",
        section_index=5,
        section_heading="Modification",
        page_range=(0, 0),
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
        section_id="doc1__s7",
        section_index=7,
        section_heading="Aggregation",
        page_range=(0, 0),
        heading_match=True,
        cue_families_hit=["heading"],
        cue_hits=[],
        negative_signals=[],
        section_text="Part 2...",
        source_format="docling_md",
        run_id="run1",
    )
    clustered = cluster_candidates([c1, c2])
    assert len(clustered) == 2


def test_cluster_keeps_separate_docs_separate() -> None:
    c1 = Candidate(
        candidate_id="c1",
        storage_key="doc1",
        section_id="s1",
        section_index=0,
        section_heading="CAC",
        page_range=(0, 0),
        heading_match=True,
        cue_families_hit=["heading"],
        cue_hits=[],
        negative_signals=[],
        section_text="...",
        source_format="docling_md",
        run_id="run1",
    )
    c2 = Candidate(
        candidate_id="c2",
        storage_key="doc2",
        section_id="s2",
        section_index=0,
        section_heading="CAC",
        page_range=(0, 0),
        heading_match=True,
        cue_families_hit=["heading"],
        cue_hits=[],
        negative_signals=[],
        section_text="...",
        source_format="docling_md",
        run_id="run1",
    )
    clustered = cluster_candidates([c1, c2])
    assert len(clustered) == 2
