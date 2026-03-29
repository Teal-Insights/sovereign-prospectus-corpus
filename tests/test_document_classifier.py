# tests/test_document_classifier.py
"""Tests for document classification pipeline."""

from __future__ import annotations

from corpus.extraction.document_classifier import (
    classify_document,
    parse_edgar_form_code,
)


def test_classify_base_prospectus() -> None:
    text = "BASE PROSPECTUS dated 15 March 2024\n\nGlobal Medium Term Note Programme"
    result = classify_document(text, storage_key="nsm__12345")
    assert result["instrument_family"] == "Bond"
    assert result["document_role"] == "Base document"
    assert result["document_form"] == "Prospectus"
    assert result["confidence"] in ("high", "medium", "low")


def test_classify_pricing_supplement() -> None:
    text = "PRICING SUPPLEMENT dated 20 March 2024\n\nSeries 2024-1 Notes"
    result = classify_document(text, storage_key="nsm__67890")
    assert result["document_role"] == "Supplement"
    assert result["document_form"] == "Pricing Supplement"


def test_classify_loan_agreement() -> None:
    text = "LOAN AGREEMENT\n\nbetween\n\nRepublic of Kenya\nand\nInternational Bank"
    result = classify_document(text, storage_key="pdip__KEN28")
    assert result["instrument_family"] == "Loan"
    assert result["document_form"] == "Loan Agreement"


def test_classify_novel_type() -> None:
    text = "CONSENT SOLICITATION STATEMENT\n\nRelating to the outstanding bonds"
    result = classify_document(text, storage_key="edgar__123")
    assert result["document_form"] == "Other"
    assert "Consent Solicitation Statement" in result.get("novel_types_observed", [])


def test_parse_edgar_form_code_424b5_raw_header() -> None:
    text = "424B5\n1\nPROSPECTUS SUPPLEMENT\nRepublic of Panama"
    code = parse_edgar_form_code(text)
    assert code == "424B5"


def test_parse_edgar_form_code_filed_pursuant_to_rule() -> None:
    """I4: Real EDGAR files say 'Filed Pursuant to Rule 424(b)(5)', not '424B5'."""
    text = "Filed Pursuant to Rule 424(b)(5)\nRegistration No. 333-123456\n\nPROSPECTUS SUPPLEMENT"
    code = parse_edgar_form_code(text)
    assert code == "424B5"


def test_parse_edgar_form_code_filed_pursuant_424b2() -> None:
    text = "Filed Pursuant to Rule 424(b)(2)\nSome other text"
    code = parse_edgar_form_code(text)
    assert code == "424B2"


def test_parse_edgar_form_code_missing() -> None:
    text = "This is a bond prospectus with no SEC header."
    code = parse_edgar_form_code(text)
    assert code is None


def test_classify_includes_evidence() -> None:
    text = "BASE PROSPECTUS dated 15 March 2024\n\nSome content"
    result = classify_document(text, storage_key="nsm__12345")
    assert result.get("evidence_text", "") != ""
    assert result.get("reasoning", "") != ""


def test_classify_edgar_form_code_high_confidence() -> None:
    """I9: EDGAR form code match should be high confidence."""
    text = "424B5\n1\nPROSPECTUS SUPPLEMENT"
    result = classify_document(text, storage_key="edgar__1")
    assert result["confidence"] == "high"


def test_classify_text_match_medium_confidence() -> None:
    """I9: Text-only pattern match should be medium confidence."""
    text = "LOAN AGREEMENT between Republic of Kenya and Bank"
    result = classify_document(text, storage_key="pdip__KEN28")
    assert result["confidence"] == "medium"


def test_classify_no_match_low_confidence() -> None:
    """I9: No match at all should be low confidence."""
    text = "Random text with no recognizable document type patterns at all."
    result = classify_document(text, storage_key="unknown__1")
    assert result["confidence"] == "low"


def test_classify_fwp_as_pricing_supplement() -> None:
    """FWP should now default to Pricing Supplement, not Other."""
    text = "FWP\n1\nFinal Term Sheet"
    result = classify_document(text, storage_key="edgar__fwp1")
    assert result["document_form"] == "Pricing Supplement"
    assert result["confidence"] == "high"


def test_parse_edgar_form_code_18k() -> None:
    text = "18-K\n1\nANNUAL REPORT"
    code = parse_edgar_form_code(text)
    assert code == "18-K"


def test_parse_edgar_form_code_rule_424b3() -> None:
    """Handle 'Rule 424(b)(3)' format (without 'Filed Pursuant to')."""
    text = "Rule 424(b)(3)\nRegistration No. 333-123456"
    code = parse_edgar_form_code(text)
    assert code == "424B3"


def test_classify_facility_agreement() -> None:
    text = "FACILITY AGREEMENT\n\nDATED 15 MARCH 2024\n\nFOR THE REPUBLIC OF GHANA"
    result = classify_document(text, storage_key="pdip__GHA99")
    assert result["instrument_family"] == "Loan"
    assert result["document_form"] == "Loan Agreement"


def test_classify_annual_report() -> None:
    text = "FORM 18-K\nFor Foreign Governments and Political Subdivisions\nRepublic of Turkey"
    result = classify_document(text, storage_key="edgar__18k1")
    assert result["document_form"] == "Annual Report"
