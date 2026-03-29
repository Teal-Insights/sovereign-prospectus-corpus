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


def check_completeness(
    extracted_text: str,
    *,
    clause_family: str,
) -> dict[str, bool]:
    """Check which clause components are present in the extracted text."""
    components = (
        _CAC_COMPONENTS
        if clause_family == "collective_action"
        else _PARI_PASSU_COMPONENTS
        if clause_family == "pari_passu"
        else {}
    )

    report: dict[str, bool] = {}
    for component, patterns in components.items():
        report[component] = any(re.search(p, extracted_text, re.IGNORECASE) for p in patterns)
    return report


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
