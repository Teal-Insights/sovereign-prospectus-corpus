# src/corpus/extraction/section_filter.py
"""LOCATE stage: filter sections, reject negatives, cluster candidates."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from corpus.extraction.cue_families import NEGATIVE_PATTERNS, get_cue_families

if TYPE_CHECKING:
    from corpus.extraction.section_parser import Section


@dataclass(frozen=True)
class CueHit:
    family: str
    pattern: str
    matched_text: str


@dataclass
class Candidate:
    candidate_id: str
    storage_key: str
    section_id: str
    section_index: int  # E1: for clustering
    section_heading: str
    page_range: tuple[int, int]
    heading_match: bool
    cue_families_hit: list[str]
    cue_hits: list[CueHit]
    negative_signals: list[str]
    section_text: str
    source_format: str
    run_id: str


def _scan_cues(text: str, cue_families: dict[str, list[str]]) -> tuple[list[str], list[CueHit]]:
    """Scan text for cue hits. Returns (families_hit, cue_hits)."""
    families_hit: set[str] = set()
    hits: list[CueHit] = []
    for family, patterns in cue_families.items():
        if family == "heading":
            continue
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                families_hit.add(family)
                hits.append(CueHit(family=family, pattern=pattern, matched_text=m.group()))
    return sorted(families_hit), hits


def _check_heading(heading: str, heading_patterns: list[str]) -> tuple[bool, list[CueHit]]:
    """Check heading against cue patterns. Returns (matched, cue_hits)."""
    hits: list[CueHit] = []
    for pattern in heading_patterns:
        m = re.search(pattern, heading, re.IGNORECASE)
        if m:
            hits.append(CueHit(family="heading", pattern=pattern, matched_text=m.group()))
    return bool(hits), hits


def _check_negatives(text: str) -> list[str]:
    found: list[str] = []
    for category, patterns in NEGATIVE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                found.append(category)
                break
    return found


def _negatives_dominate(negatives: list[str], families: list[str], text_len: int = 0) -> bool:
    # For large sections (>50K chars, typical of full EDGAR filings), skip
    # negative filtering entirely — false-positive negatives are near-certain
    # on financial data tables, dotted leaders in formatted numbers, and
    # inline citations like "as set forth in the Indenture".
    if text_len > 50_000:
        return False
    # Strict inequality: negatives must outnumber positive families to reject.
    # Previously >= which meant 2 negatives cancelled 2 positives.
    return len(negatives) > len(families)


def filter_sections(
    sections: list[Section],
    *,
    clause_family: str,
    run_id: str = "",
) -> list[Candidate]:
    """Filter sections to produce clause candidates.

    A section passes if:
    - Its heading matches a heading cue pattern (heading_match=True), OR
    - Its body hits cues from 2+ distinct non-heading families AND negatives
      do not dominate.

    Heading-matched sections are never auto-rejected by negative signals.
    """
    cue_defs = get_cue_families(clause_family)
    if cue_defs is None:
        return []

    heading_patterns = cue_defs.get("heading", [])
    candidates: list[Candidate] = []

    for section in sections:
        heading_match, heading_hits = _check_heading(section.heading, heading_patterns)
        families_hit, body_cue_hits = _scan_cues(section.text, cue_defs)
        negative_signals = _check_negatives(section.text)
        cue_hits = heading_hits + body_cue_hits

        if heading_match:
            candidates.append(
                Candidate(
                    candidate_id=str(uuid.uuid4()),
                    storage_key=section.storage_key,
                    section_id=section.section_id,
                    section_index=section.section_index,
                    section_heading=section.heading,
                    page_range=section.page_range,
                    heading_match=True,
                    cue_families_hit=["heading", *families_hit],
                    cue_hits=cue_hits,
                    negative_signals=negative_signals,
                    section_text=section.text,
                    source_format=section.source_format,
                    run_id=run_id,
                )
            )
        elif len(families_hit) >= 2 and not _negatives_dominate(
            negative_signals, families_hit, text_len=len(section.text)
        ):
            candidates.append(
                Candidate(
                    candidate_id=str(uuid.uuid4()),
                    storage_key=section.storage_key,
                    section_id=section.section_id,
                    section_index=section.section_index,
                    section_heading=section.heading,
                    page_range=section.page_range,
                    heading_match=False,
                    cue_families_hit=families_hit,
                    cue_hits=body_cue_hits,
                    negative_signals=negative_signals,
                    section_text=section.text,
                    source_format=section.source_format,
                    run_id=run_id,
                )
            )

    return candidates


def cluster_candidates(
    candidates: list[Candidate],
    *,
    max_cluster_chars: int = 25000,
) -> list[Candidate]:
    """Cluster adjacent-section candidates from the same document.

    E1: Uses section_index for adjacency, NOT page_range.
    Merges candidates whose section indices are strictly adjacent (diff == 1).
    Caps merged text at max_cluster_chars to prevent defeating parser splits.
    """
    if not candidates:
        return []

    by_doc: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_doc.setdefault(c.storage_key, []).append(c)

    result: list[Candidate] = []
    for doc_candidates in by_doc.values():
        doc_candidates.sort(key=lambda c: c.section_index)
        clusters: list[list[Candidate]] = [[doc_candidates[0]]]

        for c in doc_candidates[1:]:
            prev_idx = clusters[-1][-1].section_index
            cluster_len = sum(len(x.section_text) for x in clusters[-1])
            if (
                c.section_index == prev_idx + 1
                and cluster_len + len(c.section_text) <= max_cluster_chars
            ):
                clusters[-1].append(c)
            else:
                clusters.append([c])

        for cluster in clusters:
            if len(cluster) == 1:
                result.append(cluster[0])
            else:
                merged = Candidate(
                    candidate_id=str(uuid.uuid4()),
                    storage_key=cluster[0].storage_key,
                    section_id=cluster[0].section_id,
                    section_index=cluster[0].section_index,
                    section_heading=cluster[0].section_heading,
                    page_range=(
                        min(c.page_range[0] for c in cluster),
                        max(c.page_range[1] for c in cluster),
                    ),
                    heading_match=any(c.heading_match for c in cluster),
                    cue_families_hit=sorted(set(f for c in cluster for f in c.cue_families_hit)),
                    cue_hits=[h for c in cluster for h in c.cue_hits],
                    negative_signals=sorted(set(s for c in cluster for s in c.negative_signals)),
                    section_text="\n\n".join(c.section_text for c in cluster),
                    source_format=cluster[0].source_format,
                    run_id=cluster[0].run_id,
                )
                result.append(merged)

    return result
