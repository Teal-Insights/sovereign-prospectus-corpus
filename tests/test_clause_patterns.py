"""Tests for clause pattern definitions."""

from __future__ import annotations

import re

from corpus.extraction.clause_patterns import (
    CLAUSE_PATTERNS,
    FEATURE_PATTERNS,
    ClausePattern,
    get_all_patterns,
)


def test_clause_pattern_dataclass() -> None:
    p = ClausePattern(
        name="test",
        family="test_family",
        version="1.0.0",
        finder=re.compile(r"test pattern", re.IGNORECASE),
        description="A test pattern",
        instrument_scope="both",
    )
    assert p.name == "test"
    assert p.family == "test_family"


def test_cac_pattern_family_matches_label_mapping() -> None:
    """Pattern family must match PDIP label mapping family name."""
    p = CLAUSE_PATTERNS["collective_action"]
    assert p.family == "collective_action"


def test_all_patterns_compile() -> None:
    for name, pattern in {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}.items():
        assert isinstance(pattern.finder, re.Pattern), f"{name} finder is not compiled"


def test_cac_pattern_matches_known_text() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = (
        "The Terms and Conditions of the Notes may be amended, modified or "
        "waived with the consent of holders of not less than 75% in aggregate "
        "principal amount (collective action clauses)."
    )
    assert p.finder.search(text) is not None


def test_cac_pattern_matches_modification_text() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "modification of the terms of the Notes requires the consent of holders"
    assert p.finder.search(text) is not None


def test_pari_passu_pattern_matches() -> None:
    p = CLAUSE_PATTERNS["pari_passu"]
    text = "The Notes rank pari passu in right of payment with all other unsecured obligations"
    assert p.finder.search(text) is not None


def test_governing_law_pattern_matches_ny() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York"
    assert p.finder.search(text) is not None


def test_governing_law_pattern_matches_english() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "governed by English law"
    assert p.finder.search(text) is not None


def test_cac_pattern_matches_modification_to_debt_securities() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "Any Modification to the Debt Securities or the Indenture"
    assert p.finder.search(text) is not None


def test_cac_pattern_matches_meetings_of_noteholders() -> None:
    p = CLAUSE_PATTERNS["collective_action"]
    text = "meetings of the Noteholders may be convened"
    assert p.finder.search(text) is not None


def test_pari_passu_rank_without_preference() -> None:
    p = CLAUSE_PATTERNS["pari_passu"]
    text = "rank without any preference among themselves and equally with all other"
    assert p.finder.search(text) is not None


def test_pari_passu_unsecured_unsubordinated() -> None:
    p = CLAUSE_PATTERNS["pari_passu"]
    text = "unsecured and unsubordinated Public External Indebtedness of Jamaica"
    assert p.finder.search(text) is not None


def test_pari_passu_equal_priority_status() -> None:
    p = CLAUSE_PATTERNS["pari_passu"]
    text = "at least equal priority status with all other current and future unsecured"
    assert p.finder.search(text) is not None


def test_governing_law_matches_china() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "governed by and construed in accordance with the laws of China"
    assert p.finder.search(text) is not None


def test_governing_law_matches_netherlands() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "subject to Netherlands law"
    assert p.finder.search(text) is not None


def test_governing_law_matches_section_header() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "Governing Law and Jurisdiction"
    assert p.finder.search(text) is not None


def test_governing_law_matches_choice_of_law() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "choice of French law as the governing law"
    assert p.finder.search(text) is not None


def test_governing_law_matches_applicable_law() -> None:
    p = FEATURE_PATTERNS["feature__governing_law"]
    text = "Applicable law and jurisdiction"
    assert p.finder.search(text) is not None


def test_get_all_patterns() -> None:
    all_patterns = get_all_patterns()
    assert len(all_patterns) >= 3
    names = [p.name for p in all_patterns]
    assert "collective_action" in names
    assert "pari_passu" in names
    assert "feature__governing_law" in names
