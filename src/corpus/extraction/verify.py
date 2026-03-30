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
    """Check if extracted text appears verbatim in source."""
    norm_ext = _normalize_whitespace(extracted)
    norm_src = _normalize_whitespace(source)

    if not norm_ext:
        return VerbatimResult(
            passes=False,
            similarity=0.0,
            normalized_extracted=norm_ext,
            normalized_source=norm_src,
        )

    # Fast path: substring containment (handles single-section sources)
    if norm_ext in norm_src:
        return VerbatimResult(
            passes=True,
            similarity=1.0,
            normalized_extracted=norm_ext,
            normalized_source=norm_src,
        )

    # For clustered candidates, the source may be multiple sections joined by
    # "\n\n". The extracted text may span across section boundaries, so also
    # check the concatenation of all source sections with normalized whitespace.
    # This handles the case where the extractor pulled text that crosses a
    # section join boundary.

    # E11: Use find_longest_match to find the best region in source,
    # then compute a localized fuzzy score within that window.
    # This handles minor OCR noise (typos, ligature splits) while still
    # requiring the match to be contiguous (not scattered).
    matcher = SequenceMatcher(None, norm_ext, norm_src)
    match = matcher.find_longest_match(0, len(norm_ext), 0, len(norm_src))

    if match.size == 0:
        return VerbatimResult(
            passes=False,
            similarity=0.0,
            normalized_extracted=norm_ext,
            normalized_source=norm_src,
        )

    # Extract a window around the best match in source, padded to cover
    # the full extracted text length. Padding is proportional (5%) so it
    # doesn't dilute the score for short clauses while still accommodating
    # OCR insertions in longer ones.
    window_start = max(0, match.b - (match.a))
    # Pad is 5% of extracted length so minor OCR insertions fit without
    # diluting the score on short clauses (no fixed minimum).
    pad = len(norm_ext) // 20
    window_end = min(len(norm_src), window_start + len(norm_ext) + pad)
    window = norm_src[window_start:window_end]

    # Compute localized ratio within the window
    local_matcher = SequenceMatcher(None, norm_ext, window)
    similarity = local_matcher.ratio()

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

_GOVERNING_LAW_COMPONENTS: dict[str, list[str]] = {
    "jurisdiction": [
        r"governed\s+by",
        r"laws?\s+of",
        r"(english|new\s+york|german)\s+law",
        r"construed\s+in\s+accordance",
    ],
}

_SOVEREIGN_IMMUNITY_COMPONENTS: dict[str, list[str]] = {
    "waiver": [
        r"waive(s|d)?\s+(any|all|its)?\s*immunit(y|ies)",
        r"irrevocabl(e|y)\s+(waive|consent)",
    ],
    "execution": [
        r"(attachment|execution|seizure)",
    ],
}

_NEGATIVE_PLEDGE_COMPONENTS: dict[str, list[str]] = {
    "pledge": [
        r"(will\s+not|shall\s+not)\s+(create|grant|permit)",
        r"no\s+(lien|security\s+interest|mortgage)",
    ],
    "exception": [
        r"(except|unless|provided\s+that|permitted)",
    ],
}

_EVENTS_OF_DEFAULT_COMPONENTS: dict[str, list[str]] = {
    "trigger": [
        r"(non[\s-]?payment|failure\s+to\s+pay)",
        r"(cross[\s-]?default|insolvency|bankruptcy|moratorium)",
        r"breach\s+of\s+(covenant|obligation)",
    ],
    "consequence": [
        r"(declared|become)\s+(immediately\s+)?due\s+and\s+payable",
        r"accelerat(e|ion|ed)",
    ],
}

_ACCELERATION_COMPONENTS: dict[str, list[str]] = {
    "mechanism": [
        r"declared\s+(immediately\s+)?due\s+and\s+payable",
        r"accelerat(e|ion|ed)",
    ],
}

_DISPUTE_RESOLUTION_COMPONENTS: dict[str, list[str]] = {
    "forum": [
        r"(ICSID|ICC|LCIA|UNCITRAL|courts?)",
        r"(jurisdiction|arbitration|tribunal)",
    ],
}

_ADDITIONAL_AMOUNTS_COMPONENTS: dict[str, list[str]] = {
    "obligation": [
        r"additional\s+amounts",
        r"gross[\s-]?up",
        r"without\s+(withholding|deduction)",
    ],
}

_REDEMPTION_COMPONENTS: dict[str, list[str]] = {
    "mechanism": [
        r"redeem(ed)?",
        r"redemption\s+price",
        r"(call|make[\s-]?whole)",
    ],
}

_INDEBTEDNESS_DEFINITION_COMPONENTS: dict[str, list[str]] = {
    "definition": [
        r"indebtedness\s+means",
        r"(obligation|liability)",
        r"borrowed\s+money",
    ],
}

_COMPLETENESS_COMPONENTS: dict[str, dict[str, list[str]]] = {
    "collective_action": _CAC_COMPONENTS,
    "pari_passu": _PARI_PASSU_COMPONENTS,
    "governing_law": _GOVERNING_LAW_COMPONENTS,
    "sovereign_immunity": _SOVEREIGN_IMMUNITY_COMPONENTS,
    "negative_pledge": _NEGATIVE_PLEDGE_COMPONENTS,
    "events_of_default": _EVENTS_OF_DEFAULT_COMPONENTS,
    "acceleration": _ACCELERATION_COMPONENTS,
    "dispute_resolution": _DISPUTE_RESOLUTION_COMPONENTS,
    "additional_amounts": _ADDITIONAL_AMOUNTS_COMPONENTS,
    "redemption": _REDEMPTION_COMPONENTS,
    "indebtedness_definition": _INDEBTEDNESS_DEFINITION_COMPONENTS,
}


def check_completeness(
    extracted_text: str,
    *,
    clause_family: str,
) -> dict[str, bool]:
    """Check which clause components are present in the extracted text."""
    components = _COMPLETENESS_COMPONENTS.get(clause_family, {})
    report: dict[str, bool] = {}
    for component, patterns in components.items():
        report[component] = any(re.search(p, extracted_text, re.IGNORECASE) for p in patterns)
    return report


# Mode 3 families use section capture instead of clause extraction.
# These extract full sections verbatim (not individual clauses) and are
# verified with a lower similarity threshold (0.85 vs 0.95) because
# long sections may have minor formatting differences from OCR/page splits.
# See docs/superpowers/specs/2026-03-29-full-extraction-design.md Section 8.
_SECTION_CAPTURE_FAMILIES = {
    "events_of_default",
    "conditions_precedent",
    "payment_mechanics",
    "trustee_duties",
    "disbursement",
}


def check_section_capture(
    extracted: str,
    source: str,
) -> VerbatimResult:
    """Check section capture quality.

    Uses the same normalization but reports as section_capture_similarity,
    not verbatim. If the extraction is an exact source slice, it passes.
    Otherwise uses SequenceMatcher ratio with a lower threshold (0.85)
    since full sections may have minor formatting differences.
    """
    norm_ext = _normalize_whitespace(extracted)
    norm_src = _normalize_whitespace(source)

    if not norm_ext:
        return VerbatimResult(
            passes=False,
            similarity=0.0,
            normalized_extracted=norm_ext,
            normalized_source=norm_src,
        )

    if norm_ext in norm_src:
        return VerbatimResult(
            passes=True,
            similarity=1.0,
            normalized_extracted=norm_ext,
            normalized_source=norm_src,
        )

    # For long sections, use SequenceMatcher ratio (more lenient than find_longest_match)
    matcher = SequenceMatcher(None, norm_ext, norm_src)
    similarity = matcher.ratio()

    return VerbatimResult(
        passes=similarity >= 0.85,
        similarity=similarity,
        normalized_extracted=norm_ext,
        normalized_source=norm_src,
    )


def is_section_capture_family(clause_family: str) -> bool:
    """Check if a family uses section capture mode."""
    return clause_family in _SECTION_CAPTURE_FAMILIES


def compute_quality_flags(
    *,
    extracted: str,
    source: str,
) -> list[str]:
    """Compute quality flags for an extraction."""
    flags: list[str] = []

    # Truncation: extracted ends mid-sentence (last character is alphabetic)
    if extracted and not extracted.rstrip().endswith((".", ")", '"', "'", ";")):
        last_word = extracted.rstrip().split()[-1] if extracted.strip() else ""
        if last_word and last_word[-1].isalpha():
            flags.append("truncation_suspect")

    # OCR quality: high non-alphanumeric ratio in source
    if source:
        alpha_count = sum(1 for c in source if c.isalpha())
        total = len(source)
        if total > 20 and alpha_count / total < 0.6:
            flags.append("ocr_suspect")

    return flags
