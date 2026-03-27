"""Clause pattern definitions for grep-first extraction.

Patterns are defined in code (not config) because they require complex
regex with flags, inline comments, and per-pattern logic. Each pattern
is a finder that locates candidate sections in document text.

Page convention: all page references use 0-indexed page_index internally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClausePattern:
    """A regex pattern for finding clause sections in document text."""

    name: str
    family: str
    version: str
    finder: re.Pattern[str]
    description: str
    instrument_scope: str  # "bond" | "loan" | "both"


CLAUSE_PATTERNS: dict[str, ClausePattern] = {
    "collective_action": ClausePattern(
        name="collective_action",
        family="collective_action",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"collective\s+action"
            r"|modification\s+of\s+(?:the\s+)?terms"
            r"|amendment\s+(?:of|to)\s+(?:the\s+)?(?:terms|conditions)"
            r"|consent\s+of\s+(?:the\s+)?holders?\s+of\s+not\s+less\s+than"
            r"|aggregation\s+provisions?"
            r"|single[- ]limb\s+voting"
            r"|two[- ]limb\s+voting"
            r"|double[- ]limb\s+voting"
            r"|reserved\s+matter"
            r")",
            re.IGNORECASE,
        ),
        description="Collective action clauses — modification of bond terms by majority vote",
        instrument_scope="both",
    ),
    "pari_passu": ClausePattern(
        name="pari_passu",
        family="pari_passu",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"pari\s+passu"
            r"|rank(?:s|ing)?\s+(?:at\s+least\s+)?equal(?:ly)?\s+(?:in\s+right\s+of\s+payment|and\s+ratably)"
            r"|equal\s+ranking\s+(?:with|to)"
            r")",
            re.IGNORECASE,
        ),
        description="Pari passu — equal ranking in right of payment",
        instrument_scope="both",
    ),
}

FEATURE_PATTERNS: dict[str, ClausePattern] = {
    "feature__governing_law": ClausePattern(
        name="feature__governing_law",
        family="governing_law",
        version="1.0.0",
        finder=re.compile(
            r"(?:"
            r"governed\s+by\s+(?:and\s+(?:construed|interpreted)\s+in\s+accordance\s+with\s+)?(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+State\s+of\s+)?(?:New\s+York|England|English)"
            r"|subject\s+to\s+(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+State\s+of\s+)?(?:New\s+York|England|English)"
            r")",
            re.IGNORECASE,
        ),
        description="Governing law identification — NY vs English law",
        instrument_scope="both",
    ),
}


def get_all_patterns() -> list[ClausePattern]:
    """Return all registered patterns (clause + feature)."""
    return list(CLAUSE_PATTERNS.values()) + list(FEATURE_PATTERNS.values())
