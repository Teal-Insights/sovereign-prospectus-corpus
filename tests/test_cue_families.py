# tests/test_cue_families.py
"""Tests for cue family definitions."""

import re

from corpus.extraction.cue_families import (
    CAC_CUES,
    DISPUTE_RESOLUTION_CUES,
    EVENTS_OF_DEFAULT_CUES,
    GOVERNING_LAW_CUES,
    INDEBTEDNESS_DEFINITION_CUES,
    NEGATIVE_PATTERNS,
    NEGATIVE_PLEDGE_CUES,
    PARI_PASSU_CUES,
    SOVEREIGN_IMMUNITY_CUES,
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


# ---------------------------------------------------------------------------
# New families: Round 1 + Round 2
# ---------------------------------------------------------------------------


def test_governing_law_cues_have_heading_family() -> None:
    assert "heading" in GOVERNING_LAW_CUES


def test_governing_law_heading_matches() -> None:
    heading_patterns = GOVERNING_LAW_CUES["heading"]
    assert any(re.search(p, "Governing Law", re.IGNORECASE) for p in heading_patterns)
    assert any(re.search(p, "Applicable Law", re.IGNORECASE) for p in heading_patterns)


def test_sovereign_immunity_cues_have_heading_family() -> None:
    assert "heading" in SOVEREIGN_IMMUNITY_CUES


def test_sovereign_immunity_heading_matches() -> None:
    patterns = SOVEREIGN_IMMUNITY_CUES["heading"]
    assert any(re.search(p, "Sovereign Immunity", re.IGNORECASE) for p in patterns)
    assert any(re.search(p, "Waiver of Immunity", re.IGNORECASE) for p in patterns)
    assert any(re.search(p, "No Immunity", re.IGNORECASE) for p in patterns)


def test_negative_pledge_cues_have_heading_family() -> None:
    assert "heading" in NEGATIVE_PLEDGE_CUES


def test_negative_pledge_heading_matches_covenants() -> None:
    patterns = NEGATIVE_PLEDGE_CUES["heading"]
    # Should match "Restrictive Covenants" but NOT bare "Covenants"
    assert any(re.search(p, "Restrictive Covenants", re.IGNORECASE) for p in patterns)


def test_events_of_default_cues_have_heading_family() -> None:
    assert "heading" in EVENTS_OF_DEFAULT_CUES


def test_events_of_default_heading_no_bare_acceleration() -> None:
    """C8: bare 'acceleration' must NOT be in EoD headings (too broad)."""
    patterns = EVENTS_OF_DEFAULT_CUES["heading"]
    for p in patterns:
        m = re.search(p, "acceleration", re.IGNORECASE)
        if m:
            assert "default" in p.lower(), f"Heading pattern '{p}' matches bare 'acceleration'"


def test_dispute_resolution_heading_no_bare_jurisdiction() -> None:
    """I3: bare 'jurisdiction' must NOT be in heading."""
    patterns = DISPUTE_RESOLUTION_CUES["heading"]
    for p in patterns:
        m = re.fullmatch(p, "jurisdiction", re.IGNORECASE)
        assert m is None, f"Heading pattern '{p}' matches bare 'jurisdiction'"


def test_indebtedness_heading_no_bare_indebtedness() -> None:
    """I3: bare 'indebtedness' must NOT be in heading."""
    patterns = INDEBTEDNESS_DEFINITION_CUES["heading"]
    for p in patterns:
        m = re.fullmatch(p, "indebtedness", re.IGNORECASE)
        assert m is None, f"Heading pattern '{p}' matches bare 'indebtedness'"


def test_get_cue_families_governing_law() -> None:
    assert get_cue_families("governing_law") is GOVERNING_LAW_CUES


def test_get_cue_families_all_round1() -> None:
    for family in ["governing_law", "sovereign_immunity", "negative_pledge", "events_of_default"]:
        assert get_cue_families(family) is not None, f"Missing cue family: {family}"


def test_get_cue_families_all_round2() -> None:
    for family in [
        "acceleration",
        "dispute_resolution",
        "additional_amounts",
        "redemption",
        "indebtedness_definition",
    ]:
        assert get_cue_families(family) is not None, f"Missing cue family: {family}"


def test_all_families_have_two_plus_non_heading_families() -> None:
    """C2: Every family must have at least 2 non-heading cue families for body-only recall."""
    from corpus.extraction.cue_families import get_all_families

    for family_name in get_all_families():
        cues = get_cue_families(family_name)
        assert cues is not None, f"Missing cue family: {family_name}"
        non_heading = [k for k in cues if k != "heading"]
        assert len(non_heading) >= 2, (
            f"{family_name} has only {len(non_heading)} non-heading families "
            f"({non_heading}), need >= 2 for body-only LOCATE"
        )


def test_negative_pledge_pledge_matches_real_text() -> None:
    """Fixed patterns should match real sovereign bond negative pledge language."""
    patterns = NEGATIVE_PLEDGE_CUES["pledge"]
    # Colombia: "will not create or permit to exist any lien"
    assert any(
        re.search(p, "will not create or permit to exist any lien", re.IGNORECASE)
        for p in patterns
    )
    # Brazil: "will not create or permit to subsist any Security Interest"
    assert any(
        re.search(p, "will not create or permit to subsist any Security Interest", re.IGNORECASE)
        for p in patterns
    )
    # Chile: "will not grant or allow any lien"
    assert any(re.search(p, "will not grant or allow any lien", re.IGNORECASE) for p in patterns)


def test_negative_pledge_exception_matches_secured_equally() -> None:
    """Fixed exception pattern matches real word order: 'secured equally and ratably'."""
    patterns = NEGATIVE_PLEDGE_CUES["exception"]
    assert any(re.search(p, "secured equally and ratably", re.IGNORECASE) for p in patterns)
    assert any(re.search(p, "secured equally and rateably", re.IGNORECASE) for p in patterns)


def test_get_all_families_returns_all_registered() -> None:
    """Guard against accidental deletion from _CLAUSE_CUES."""
    from corpus.extraction.cue_families import get_all_families

    families = get_all_families()
    assert len(families) == 17
    assert "collective_action" in families
    assert "indebtedness_definition" in families


def test_all_new_patterns_compile() -> None:
    """Every pattern string in all families must be a valid regex."""
    from corpus.extraction.cue_families import get_all_families

    for family in get_all_families():
        cues = get_cue_families(family)
        assert cues is not None
        for _fam, patterns in cues.items():
            for p in patterns:
                re.compile(p, re.IGNORECASE)
