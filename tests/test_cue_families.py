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
    for _family, patterns in CAC_CUES.items():
        for p in patterns:
            re.compile(p, re.IGNORECASE)
    for _family, patterns in PARI_PASSU_CUES.items():
        for p in patterns:
            re.compile(p, re.IGNORECASE)
    for _family, patterns in NEGATIVE_PATTERNS.items():
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
