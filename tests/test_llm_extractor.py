# tests/test_llm_extractor.py
"""Tests for LLM clause extractor (no API — Claude Code is the extractor)."""

from __future__ import annotations

from corpus.extraction.llm_extractor import (
    ExtractionResult,
    build_extraction_prompt,
    parse_extraction_response,
)
from corpus.extraction.section_filter import Candidate


def _make_candidate(
    section_text: str = "## Collective Action\n\nThe Bonds may be modified...",
    section_heading: str = "Collective Action",
) -> Candidate:
    return Candidate(
        candidate_id="test1",
        storage_key="test__doc1",
        section_id="test__doc1__s5",
        section_index=5,
        section_heading=section_heading,
        page_range=(47, 49),
        heading_match=True,
        cue_families_hit=["heading", "voting_threshold"],
        cue_hits=[],
        negative_signals=[],
        section_text=section_text,
        source_format="docling_md",
        run_id="run1",
    )


def test_build_prompt_includes_system() -> None:
    candidate = _make_candidate()
    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family="collective_action",
        country="Indonesia",
        few_shot_examples=[],
    )
    assert messages[0]["role"] == "system"
    assert "verbatim" in messages[0]["content"].lower()


def test_build_prompt_includes_section_text() -> None:
    candidate = _make_candidate(section_text="The Bonds contain CAC provisions.")
    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family="collective_action",
        country="Indonesia",
        few_shot_examples=[],
    )
    full_text = " ".join(m["content"] for m in messages if isinstance(m["content"], str))
    assert "The Bonds contain CAC provisions" in full_text


def test_parse_found_response() -> None:
    tool_input = {
        "found": True,
        "clause_text": "The Bonds may be modified by holders of 75%.",
        "confidence": "high",
        "reasoning": "Clear CAC with voting threshold.",
    }
    result = parse_extraction_response(tool_input)
    assert isinstance(result, ExtractionResult)
    assert result.found is True
    assert result.clause_text == "The Bonds may be modified by holders of 75%."
    assert result.confidence == "high"


def test_parse_not_found_response() -> None:
    tool_input = {
        "found": False,
        "clause_text": "",
        "confidence": "high",
        "reasoning": "This is a cross-reference, not the clause.",
    }
    result = parse_extraction_response(tool_input)
    assert result.found is False
    assert result.clause_text == ""
