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
