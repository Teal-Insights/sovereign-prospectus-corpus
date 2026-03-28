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
        version="1.1.0",
        finder=re.compile(
            r"(?:"
            r"collective\s+action"
            r"|modification\s+(?:of|to)\s+(?:the\s+)?(?:terms|debt\s+securities|bonds?|notes?)"
            r"|amendment\s+(?:of|to)\s+(?:the\s+)?(?:terms|conditions)"
            r"|consent\s+of\s+(?:the\s+)?holders?\s+of\s+not\s+less\s+than"
            r"|aggregation\s+provisions?"
            r"|single[- ]limb\s+voting"
            r"|two[- ]limb\s+voting"
            r"|double[- ]limb\s+voting"
            r"|reserved\s+matter"
            r"|meeting(?:s)?\s+of\s+(?:the\s+)?(?:note|bond)holders"
            r")",
            re.IGNORECASE,
        ),
        description="Collective action clauses — modification of bond terms by majority vote",
        instrument_scope="both",
    ),
    "pari_passu": ClausePattern(
        name="pari_passu",
        family="pari_passu",
        version="1.1.0",
        finder=re.compile(
            r"(?:"
            r"pari\s+passu"
            r"|rank(?:s|ing)?\s+(?:at\s+least\s+)?equal(?:ly)?\s+(?:in\s+right\s+of\s+payment|and\s+ratably)"
            r"|equal\s+ranking\s+(?:with|to)"
            r"|rank\s+without\s+(?:any\s+)?preference\s+among\s+themselves"
            r"|(?:at\s+least\s+)?equal\s+priority\s+status"
            r"|unsecured\s+and\s+unsubordinated\s+(?:public\s+)?(?:external\s+)?(?:indebtedness|obligations)"
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
        version="1.1.0",
        finder=re.compile(
            r"(?:"
            # Explicit "governed by" with any jurisdiction
            r"governed\s+by\s+(?:and\s+(?:construed|interpreted)\s+in\s+accordance\s+with\s+)?(?:the\s+)?(?:laws?\s+of\b|English\s+law)"
            # "subject to X law"
            r"|subject\s+to\s+(?:the\s+)?(?:laws?\s+of\b|Netherlands\s+law)"
            # "choice of X law"
            r"|choice\s+of\s+\w+\s+law\s+as\s+(?:the\s+)?governing\s+law"
            # Section headers
            r"|governing\s+law(?:\s+and\s+(?:jurisdiction|enforcement|arbitration))?"
            # "applicable law"
            r"|applicable\s+law\s+and\s+jurisdiction"
            r")",
            re.IGNORECASE,
        ),
        description="Governing law identification — matches any jurisdiction",
        instrument_scope="both",
    ),
}


def get_all_patterns() -> list[ClausePattern]:
    """Return all registered patterns (clause + feature)."""
    return list(CLAUSE_PATTERNS.values()) + list(FEATURE_PATTERNS.values())
