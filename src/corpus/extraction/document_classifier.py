# src/corpus/extraction/document_classifier.py
"""Document classification: instrument_family, document_role, document_form.

Classifies sovereign debt documents by reading the first ~10K characters.
This is a separate workstream from clause extraction -- different pipeline,
different output format.

IMPORTANT CAVEAT: This taxonomy is a best-effort starting point. Domain
expert review (legal scholars, practitioners) is needed to validate.
"""

from __future__ import annotations

import re

# SEC form code -> document metadata mapping
_EDGAR_FORM_MAP: dict[str, tuple[str, str, str]] = {
    # (instrument_family, document_role, document_form)
    "424B5": ("Bond", "Supplement", "Prospectus"),
    "424B4": ("Bond", "Supplement", "Prospectus"),
    "424B2": ("Bond", "Supplement", "Pricing Supplement"),
    "424B3": ("Bond", "Base document", "Prospectus"),
    "424B1": ("Bond", "Base document", "Prospectus"),
    "FWP": ("Bond", "Supplement", "Other"),
    "F-4": ("Bond", "Base document", "Other"),
}

# Keyword patterns for text-based classification, ordered by specificity
_FORM_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex, instrument_family, document_role, document_form)
    (r"(?i)loan\s+agreement", "Loan", "Standalone", "Loan Agreement"),
    (r"(?i)financing\s+agreement", "Loan", "Standalone", "Loan Agreement"),
    (r"(?i)loan\s+contract", "Loan", "Standalone", "Loan Agreement"),
    (r"(?i)credit\s+agreement", "Loan", "Standalone", "Loan Agreement"),
    (r"(?i)indenture", "Bond", "Standalone", "Indenture"),
    (r"(?i)trust\s+deed", "Bond", "Standalone", "Trust Deed"),
    (r"(?i)fiscal\s+agency\s+agreement", "Bond", "Standalone", "Fiscal Agency Agreement"),
    (r"(?i)amendment\s+(agreement|no\.?\s*\d)", "Other", "Amendment", "Other"),
    (r"(?i)supplement(al)?\s+(number|no\.?)\s*\d", "Bond", "Supplement", "Other"),
    (r"(?i)pricing\s+supplement", "Bond", "Supplement", "Pricing Supplement"),
    (r"(?i)final\s+terms", "Bond", "Supplement", "Final Terms"),
    (r"(?i)prospectus\s+supplement", "Bond", "Supplement", "Prospectus"),
    (r"(?i)preliminary\s+(offering\s+)?prospectus", "Bond", "Base document", "Prospectus"),
    (r"(?i)base\s+(offering\s+)?(prospectus|circular)", "Bond", "Base document", "Prospectus"),
    (r"(?i)offering\s+(circular|memorandum)", "Bond", "Base document", "Offering Circular"),
    (r"(?i)(?:^|\n)\s*prospectus\s*(?:\n|$)", "Bond", "Base document", "Prospectus"),
    (r"(?i)tender\s+offer", "Bond", "Other", "Regulatory Filing"),
]

# I4: Handle both raw header ("424B5\n") and "Filed Pursuant to Rule 424(b)(5)"
_EDGAR_FORM_RE = re.compile(
    r"(?:^(424B[1-5]|FWP|F-4|S-\d+)\s*\n)"
    r"|"
    r"(?:Filed\s+Pursuant\s+to\s+Rule\s+(\d+\([a-z]\)\(\d+\)))",
    re.MULTILINE,
)

_EDGAR_RULE_MAP = {
    "424(b)(5)": "424B5",
    "424(b)(4)": "424B4",
    "424(b)(2)": "424B2",
    "424(b)(3)": "424B3",
    "424(b)(1)": "424B1",
}


def parse_edgar_form_code(text: str) -> str | None:
    """Extract SEC form code from EDGAR file header.

    Handles both raw header format ('424B5\\n') and the
    'Filed Pursuant to Rule 424(b)(5)' format found in real filings.
    """
    m = _EDGAR_FORM_RE.search(text[:1000])
    if not m:
        return None
    if m.group(1):
        return m.group(1)
    if m.group(2):
        return _EDGAR_RULE_MAP.get(m.group(2))
    return None


def classify_document(
    text: str,
    *,
    storage_key: str,
    max_chars: int = 10000,
) -> dict:
    """Classify a document by reading its opening text.

    Returns a dict with instrument_family, document_role, document_form,
    confidence, reasoning, evidence_text, novel_types_observed.

    Confidence model (I9):
    - high: EDGAR form code match
    - medium: text pattern match
    - low: no match
    """
    sample = text[:max_chars]

    # Try EDGAR form code first (highest confidence)
    form_code = parse_edgar_form_code(sample)
    if form_code and form_code in _EDGAR_FORM_MAP:
        inst, role, form = _EDGAR_FORM_MAP[form_code]
        return {
            "storage_key": storage_key,
            "instrument_family": inst,
            "document_role": role,
            "document_form": form,
            "confidence": "high",
            "reasoning": f"SEC form code {form_code} in file header",
            "evidence_text": form_code,
            "evidence_page": None,
            "novel_types_observed": [],
            "schema_version": "1.0",
        }

    # Text-based pattern matching
    # If first 500 chars are disclaimer boilerplate, extend the search window
    check_text = sample
    if re.search(r"(?i)^important\s+notice", sample[:500]):
        check_text = text[:15000]

    # Search the full expanded window
    for pattern, inst, role, form in _FORM_PATTERNS:
        m = re.search(pattern, check_text)
        if m:
            evidence = check_text[max(0, m.start() - 20) : m.end() + 50].strip()
            return {
                "storage_key": storage_key,
                "instrument_family": inst,
                "document_role": role,
                "document_form": form,
                "confidence": "medium",
                "reasoning": f"Matched '{m.group()}' in opening text",
                "evidence_text": evidence[:200],
                "evidence_page": None,
                "novel_types_observed": [],
                "schema_version": "1.0",
            }

    # No pattern matched -- look for novel type signals
    novel_types = []
    novel_match = re.search(
        r"(?:^|\n)\s*([A-Z][A-Z\s]{5,60}(?:STATEMENT|MEMORANDUM|CIRCULAR|CERTIFICATE|NOTICE|AGREEMENT))",
        check_text[:3000],
    )
    if novel_match:
        novel_types.append(novel_match.group(1).strip().title())

    return {
        "storage_key": storage_key,
        "instrument_family": "Other",
        "document_role": "Standalone",
        "document_form": "Other",
        "confidence": "low",
        "reasoning": "No known document type pattern matched in opening text",
        "evidence_text": check_text[:200],
        "evidence_page": None,
        "novel_types_observed": novel_types,
        "schema_version": "1.0",
    }
