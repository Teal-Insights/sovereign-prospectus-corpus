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


def test_verbatim_fuzzy_match_minor_typo() -> None:
    """Minor OCR noise (1-2 char differences) should still pass verification."""
    # Simulate a ligature split: "fi" -> "f i"
    extracted = "The Bonds may be modif ied by holders of not less than 75%."
    source = "Preamble. The Bonds may be modified by holders of not less than 75%. End."
    result = check_verbatim(extracted, source)
    assert result.passes is True
    assert result.similarity >= 0.95


def test_quality_flags_ocr_suspect() -> None:
    # High non-alpha ratio suggests OCR issues
    source = "Th3 B0nds m@y b3 m0d!f!3d by h0ld3rs 0f n0t l3ss th@n 75%."
    flags = compute_quality_flags(extracted="", source=source)
    assert "ocr_suspect" in flags


def test_completeness_governing_law() -> None:
    text = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York."
    report = check_completeness(text, clause_family="governing_law")
    assert report["jurisdiction"] is True


def test_completeness_sovereign_immunity() -> None:
    text = (
        "The Issuer irrevocably waives all immunity from jurisdiction, attachment and execution."
    )
    report = check_completeness(text, clause_family="sovereign_immunity")
    assert report["waiver"] is True


def test_completeness_negative_pledge() -> None:
    text = (
        "The Issuer will not create or permit any lien on its assets, except for permitted liens."
    )
    report = check_completeness(text, clause_family="negative_pledge")
    assert report["pledge"] is True
    assert report["exception"] is True


def test_completeness_events_of_default() -> None:
    text = "If an Event of Default occurs: non-payment, cross-default, insolvency, the bonds may be declared due and payable."
    report = check_completeness(text, clause_family="events_of_default")
    assert report["trigger"] is True
    assert report["consequence"] is True


def test_completeness_unknown_family_returns_empty() -> None:
    report = check_completeness("any text", clause_family="nonexistent")
    assert report == {}


def test_section_capture_exact_slice_passes() -> None:
    from corpus.extraction.verify import check_section_capture

    source = "The following events shall constitute Events of Default: (a) non-payment, (b) cross-default, (c) insolvency."
    extracted = "The following events shall constitute Events of Default: (a) non-payment, (b) cross-default, (c) insolvency."
    result = check_section_capture(extracted, source)
    assert result.passes is True
    assert result.similarity == 1.0


def test_section_capture_substring_passes() -> None:
    from corpus.extraction.verify import check_section_capture

    source = "Preamble text. The following events shall constitute Events of Default: (a) non-payment. End of section."
    extracted = "The following events shall constitute Events of Default: (a) non-payment."
    result = check_section_capture(extracted, source)
    assert result.passes is True
    assert result.similarity == 1.0


def test_section_capture_empty_extracted_fails() -> None:
    from corpus.extraction.verify import check_section_capture

    result = check_section_capture("", "some source text")
    assert result.passes is False
    assert result.similarity == 0.0


def test_section_capture_high_similarity_passes() -> None:
    from corpus.extraction.verify import check_section_capture

    source = "Events of Default include non-payment, cross-default, and insolvency of the issuer."
    extracted = (
        "Events of Default include non-payment, cross-default,  and insolvency of the issuer."
    )
    result = check_section_capture(extracted, source)
    assert result.passes is True
    assert result.similarity >= 0.85


def test_section_capture_low_similarity_fails() -> None:
    from corpus.extraction.verify import check_section_capture

    source = "Events of Default include non-payment, cross-default, and insolvency."
    extracted = "Completely different text about redemption and maturity dates."
    result = check_section_capture(extracted, source)
    assert result.passes is False


def test_is_section_capture_family() -> None:
    from corpus.extraction.verify import is_section_capture_family

    assert is_section_capture_family("events_of_default") is True
    assert is_section_capture_family("conditions_precedent") is True
    assert is_section_capture_family("governing_law") is False
    assert is_section_capture_family("collective_action") is False
