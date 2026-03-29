# src/corpus/extraction/llm_extractor.py
"""LLM clause extraction prompt building and result parsing.

Claude Code IS the LLM extractor. This module provides:
- Prompt construction (system prompt, few-shot examples, extraction task)
- Result parsing (dict -> ExtractionResult)
- Schema definitions (for documentation)

No API calls. No anthropic dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from corpus.extraction.section_filter import Candidate

SYSTEM_PROMPT = """\
You are a legal document analyst specializing in sovereign bond contracts.
Your task is to extract specific clause text verbatim from bond prospectuses.

Rules:
1. Extract the EXACT text as it appears in the source. Do not paraphrase,
   summarize, correct typos, or rephrase in any way.
2. Preserve all original formatting, whitespace, numbered lists, and
   punctuation exactly as they appear.
3. The clause begins where the substantive legal language starts and ends
   where the subject matter clearly changes or a new section of equal or
   higher heading level begins.
4. For CACs: ensure you extract ALL related sub-paragraphs including
   voting thresholds, reserved matters, aggregation provisions, meeting
   rules, and notice requirements. Do not stop at the first paragraph.
5. If the section does not contain the requested clause (e.g., it's a
   cross-reference, table of contents entry, or summary), return NOT_FOUND.
6. NOT_FOUND is a valid and expected answer. Never force an extraction."""

EXTRACTION_TOOL_SCHEMA = {
    "name": "extract_clause",
    "description": "Extract a clause from a bond prospectus section, or report NOT_FOUND.",
    "input_schema": {
        "type": "object",
        "properties": {
            "thinking": {
                "type": "string",
                "description": "Step-by-step analysis of clause boundaries and components.",
            },
            "found": {
                "type": "boolean",
                "description": "True if the clause was found in this section.",
            },
            "clause_text": {
                "type": "string",
                "description": "The verbatim clause text. Empty string if not found.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence summary for the reviewing lawyer.",
            },
            "boundary_note": {
                "type": "string",
                "description": "Any uncertainty about clause start/end boundaries.",
            },
        },
        "required": ["thinking", "found", "clause_text", "confidence", "reasoning"],
    },
}

CLAUSE_DESCRIPTIONS = {
    "collective_action": (
        "Collective Action Clause (CAC) — provisions allowing a qualified majority of "
        "bondholders to modify the terms of the bonds, including voting thresholds, "
        "reserved matters, aggregation mechanisms, and meeting/written resolution procedures."
    ),
    "pari_passu": (
        "Pari Passu Clause — provisions establishing that the bonds rank equally in right "
        "of payment with other unsecured and unsubordinated obligations of the issuer."
    ),
}


@dataclass(frozen=True)
class ExtractionResult:
    found: bool
    clause_text: str
    confidence: str
    reasoning: str
    thinking: str = ""
    boundary_note: str = ""


@dataclass(frozen=True)
class FewShotExample:
    section_text: str
    extracted_text: str
    country: str
    is_negative: bool  # True = NOT_FOUND example


def build_extraction_prompt(
    *,
    candidate: Candidate,
    clause_family: str,
    country: str,
    few_shot_examples: list[FewShotExample],
    icma_reference: str = "",
) -> list[dict]:
    """Build the message list for extraction (used as reference for Claude Code)."""
    # Note: "system" role is used for reference/documentation. When calling
    # the Anthropic API directly, system would be a top-level parameter.
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    clause_desc = CLAUSE_DESCRIPTIONS.get(clause_family, clause_family)

    if icma_reference:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"For reference, here is the ICMA model {clause_family} language:\n\n"
                    f"{icma_reference}"
                ),
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "Understood. I'll use this as a reference for what this type of clause "
                    "looks like, while recognizing that real-world clauses vary substantially."
                ),
            }
        )

    for ex in few_shot_examples:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Extract the {clause_desc} from this section of a {ex.country} "
                    f"bond prospectus:\n\n{ex.section_text}"
                ),
            }
        )
        if ex.is_negative:
            messages.append(
                {
                    "role": "assistant",
                    "content": (
                        f"This section does not contain the {clause_family} clause "
                        f"— it is a cross-reference. NOT_FOUND."
                    ),
                }
            )
        else:
            messages.append(
                {
                    "role": "assistant",
                    "content": (
                        f"Here is the extracted {clause_family} clause:\n\n{ex.extracted_text}"
                    ),
                }
            )

    # Show page info only for sources with real page data
    page_info = ""
    if candidate.source_format == "flat_jsonl":
        page_info = f", pages {candidate.page_range[0] + 1}-{candidate.page_range[1] + 1}"

    messages.append(
        {
            "role": "user",
            "content": (
                f"Extract the {clause_desc} from this section of a {country} "
                f'bond prospectus (section heading: "{candidate.section_heading}"'
                f"{page_info}):\n\n"
                f"{candidate.section_text}"
            ),
        }
    )

    return messages


def parse_extraction_response(tool_input: dict) -> ExtractionResult:
    """Parse a structured extraction response dict into an ExtractionResult."""
    return ExtractionResult(
        found=tool_input["found"],
        clause_text=tool_input.get("clause_text", ""),
        confidence=tool_input.get("confidence", "low"),
        reasoning=tool_input.get("reasoning", ""),
        thinking=tool_input.get("thinking", ""),
        boundary_note=tool_input.get("boundary_note", ""),
    )
