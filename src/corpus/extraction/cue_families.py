# src/corpus/extraction/cue_families.py
"""Cue family definitions for clause extraction v2.

Each clause type defines cues organized by family. Cue diversity (hits from
multiple families) is a stronger signal than multiple hits from one family.
"""

from __future__ import annotations

CAC_CUES: dict[str, list[str]] = {
    "heading": [
        r"collective\s+action",
        r"modification\s+of\s+(the\s+)?(conditions|terms)",
        r"amendment\s+and\s+waiver",
        r"meetings?\s+of\s+(note|bond)holders",
        r"voting\s+and\s+amendments",
    ],
    "voting_threshold": [
        r"consent\s+of\s+(the\s+)?holders\s+of\s+not\s+less\s+than",
        r"holders?\s+of\s+\d+%",
        r"\d+%\s+of\s+the\s+aggregate\s+principal",
        r"extraordinary\s+resolution",
        r"written\s+resolution",
        r"two[\s-]+thirds",
        r"66\s*(?:⅔|2/3)",
    ],
    "aggregation": [
        r"aggregat(ion|ed)\s+(provisions?|voting)",
        r"single[\s-]+(series|limb)\s+(voting|modification)",
        r"cross[\s-]+series",
        r"uniformly\s+applicable",
    ],
    "reserved_matter": [
        r"reserved\s+matter",
        r"reserve[d]?\s+matter\s+modification",
    ],
    "meeting_quorum": [
        r"quorum",
        r"meeting\s+of\s+(note|bond)?holders",
    ],
}

PARI_PASSU_CUES: dict[str, list[str]] = {
    "heading": [
        r"status\s+of\s+the\s+(notes|bonds|securities)",
        r"ranking",
        r"pari\s+passu",
    ],
    "ranking": [
        r"pari\s+passu",
        r"rank\s+(equally|pari\s+passu)",
        r"equal\s+(ranking|priority)",
        r"without\s+preference",
    ],
    "obligation": [
        r"unsecured\s+and\s+unsubordinated",
        r"direct,?\s+(unconditional,?\s+)?unsecured",
    ],
}

NEGATIVE_PATTERNS: dict[str, list[str]] = {
    "cross_reference": [
        r"""(see|refer\s+to|described\s+(under|in))\s+["']""",
        r"as\s+set\s+forth\s+in",
        r"""under\s+["'].+["']""",
    ],
    "table_of_contents": [
        r"\.{4,}",
        r"^\s*\d+\s*$",
    ],
    "summary_overview": [
        r"(the\s+)?following\s+is\s+a\s+(brief\s+)?summary",
        r"brief\s+description",
        r"summary\s+of\s+(the\s+)?(principal\s+)?provisions",
    ],
}

_CLAUSE_CUES: dict[str, dict[str, list[str]]] = {
    "collective_action": CAC_CUES,
    "pari_passu": PARI_PASSU_CUES,
}


def get_cue_families(clause_family: str) -> dict[str, list[str]] | None:
    """Return cue families for a clause type, or None if unknown."""
    return _CLAUSE_CUES.get(clause_family)
