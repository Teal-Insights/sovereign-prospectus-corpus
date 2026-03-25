#!/usr/bin/env python3
"""
Clause Extraction Prompt Templates

Standardized prompts for Claude API to extract sovereign bond contract clauses
from prospectus text. Designed for few-shot prompting with high accuracy.

These templates target the Tier 1 and Tier 2 clauses identified in the PoC strategy:
- Collective Action Clauses (CACs)
- Pari Passu Language
- Events of Default
- Negative Pledge
- Governing Law & Dispute Resolution
- Subordination Terms
"""

import json
from typing import Dict, List, Optional

# ==============================================================================
# COLLECTIVE ACTION CLAUSES (CACs)
# ==============================================================================

CAC_EXTRACTION_PROMPT = """
Extract all Collective Action Clause (CAC) language from the provided prospectus text.

Focus on:
1. **Type**: Single-limb aggregated CACs, series-by-series voting, or hybrid
2. **Voting threshold**: Majority definition (50%+1, 66%, 75%, etc.)
3. **Scope**: Can bondholders vote across multiple series together, or per-series only?
4. **Amendment rights**: Which terms can be amended by bondholder vote?
5. **Acceleration**: Does a CAC vote result in automatic acceleration?

Return as JSON with these keys:
- "cac_type": Type of CAC (string)
- "voting_threshold": Percentage or description (string)
- "aggregation_scope": "single_series" | "aggregated_multiple_series" | "hybrid" | "unknown"
- "extracted_text": Full extracted language (string, preserve original wording)
- "key_features": List of notable features (array of strings)
- "confidence": 0-100 score

If no CAC language is found, return:
{
  "cac_found": false,
  "note": "No CAC language identified in provided text"
}

PROSPECTUS TEXT:
{prospectus_text}
"""

# ==============================================================================
# PARI PASSU CLAUSES
# ==============================================================================

PARI_PASSU_EXTRACTION_PROMPT = """
Extract all Pari Passu clause language from the provided prospectus text.

Focus on:
1. **Definition**: Does the language require strict pari passu or allow modifications?
2. **Ratable payments**: Are there carve-outs or exceptions?
3. **Official creditor exception**: Are official creditors (IMF, Paris Club, etc.) excluded?
4. **Structural subordination**: Are some creditors explicitly allowed to be senior?
5. **Enforcement**: How is pari passu enforced in case of default?

Return as JSON with these keys:
- "pari_passu_type": "strict" | "modified_with_exceptions" | "subordinated" | "unknown" (string)
- "official_creditor_carveout": true | false | "unknown"
- "ratable_payments_required": true | false | "unknown"
- "extracted_text": Full extracted language (string, preserve original wording)
- "exceptions": List of carve-outs or exceptions (array of strings)
- "confidence": 0-100 score

If no pari passu language is found, return:
{
  "pari_passu_found": false,
  "note": "No explicit pari passu clause identified in provided text"
}

PROSPECTUS TEXT:
{prospectus_text}
"""

# ==============================================================================
# EVENTS OF DEFAULT
# ==============================================================================

EVENTS_OF_DEFAULT_EXTRACTION_PROMPT = """
Extract all Events of Default clause language from the provided prospectus text.

Focus on:
1. **Cross-default**: Defaults on other debt? What threshold?
2. **Payment default**: Grace period? Amount threshold?
3. **Acceleration**: What happens when default occurs?
4. **Covenant defaults**: Breach of financial covenants, etc.
5. **Force majeure**: Are acts of war, pandemic, etc. carved out?
6. **Remedy period**: Any cure periods before acceleration?

Return as JSON with these keys:
- "event_types": List of identified events (array of strings like ["payment_default", "cross_default", "covenant_breach"])
- "payment_default_threshold": Amount or description (string, or null)
- "grace_period_days": Number of days (integer, or null)
- "cross_default_threshold": Amount or description (string, or null)
- "force_majeure_carveout": true | false | "unknown"
- "extracted_text": Full extracted language (string, preserve original wording)
- "key_triggers": List of specific default triggers (array of strings)
- "confidence": 0-100 score

If no events of default language is found, return:
{
  "events_found": false,
  "note": "No Events of Default clause identified in provided text"
}

PROSPECTUS TEXT:
{prospectus_text}
"""

# ==============================================================================
# NEGATIVE PLEDGE CLAUSES
# ==============================================================================

NEGATIVE_PLEDGE_EXTRACTION_PROMPT = """
Extract all Negative Pledge clause language from the provided prospectus text.

Focus on:
1. **Breadth**: Does it cover all assets or specific collateral types?
2. **Exceptions**: Carve-outs for trade finance, official development finance, etc.
3. **Permitted liens**: What types of liens are allowed (purchase money, security deposits, etc.)?
4. **Enforcement**: How is the pledge enforced?

Return as JSON with these keys:
- "pledge_scope": "all_assets" | "specific_categories" | "limited" | "unknown" (string)
- "exceptions": List of carved-out categories (array of strings)
- "odf_carveout": true | false | "unknown" (official development finance carveout)
- "extracted_text": Full extracted language (string, preserve original wording)
- "confidence": 0-100 score

If no negative pledge language is found, return:
{
  "pledge_found": false,
  "note": "No Negative Pledge clause identified in provided text"
}

PROSPECTUS TEXT:
{prospectus_text}
"""

# ==============================================================================
# GOVERNING LAW & DISPUTE RESOLUTION
# ==============================================================================

GOVERNING_LAW_EXTRACTION_PROMPT = """
Extract Governing Law and Dispute Resolution clause language from the provided prospectus text.

Focus on:
1. **Governing law**: Which jurisdiction's law governs? (English, New York, etc.)
2. **Jurisdiction**: Where can disputes be brought? (exclusive vs. non-exclusive)
3. **Arbitration**: Is there ISDA master agreement reference? Arbitration clause?
4. **Waiver of immunity**: Does the sovereign waive sovereign immunity?

Return as JSON with these keys:
- "governing_law": Jurisdiction (string, e.g., "English Law")
- "jurisdiction": Jurisdiction for disputes (string)
- "arbitration": true | false (is arbitration available?)
- "isda_reference": true | false (does it reference ISDA master agreement?)
- "immunity_waiver": true | false | "unknown" (does sovereign waive immunity?)
- "extracted_text": Full extracted language (string, preserve original wording)
- "confidence": 0-100 score

If no governing law/dispute resolution language is found, return:
{
  "gl_found": false,
  "note": "No Governing Law clause identified in provided text"
}

PROSPECTUS TEXT:
{prospectus_text}
"""

# ==============================================================================
# MULTI-CLAUSE BATCH EXTRACTION
# ==============================================================================

BATCH_EXTRACTION_PROMPT = """
Extract key contract clauses from the provided sovereign bond prospectus text.

For each clause type below, extract the relevant language and classify it:

1. COLLECTIVE ACTION CLAUSES (CACs)
   - Type: Single-limb aggregated? Series-by-series? Hybrid?
   - Voting threshold
   - Aggregation scope (single series vs. multiple series)

2. PARI PASSU LANGUAGE
   - Type: Strict or modified?
   - Exceptions for official creditors?
   - Ratable payments requirement?

3. EVENTS OF DEFAULT
   - Key triggers (payment default, cross-default, covenant breach, etc.)
   - Thresholds (amount, grace period)
   - Force majeure carve-outs?

4. NEGATIVE PLEDGE
   - Scope (all assets or specific?)
   - Exceptions

5. GOVERNING LAW & DISPUTE RESOLUTION
   - Jurisdiction
   - Arbitration available?
   - Immunity waiver?

Return as JSON object with these top-level keys:
- "issuer_name": (if identifiable)
- "document_type": (if identifiable)
- "document_date": (if identifiable)
- "clauses": Object containing:
  - "collective_action_clauses": {...}
  - "pari_passu": {...}
  - "events_of_default": {...}
  - "negative_pledge": {...}
  - "governing_law": {...}
- "extraction_notes": Any relevant notes (string)
- "confidence": Overall confidence (0-100)

For clauses not found, include: {"found": false, "note": "..."}

PROSPECTUS TEXT:
{prospectus_text}
"""


def create_cac_prompt(text: str) -> str:
    """Format CAC extraction prompt with prospectus text."""
    return CAC_EXTRACTION_PROMPT.format(prospectus_text=text)


def create_pari_passu_prompt(text: str) -> str:
    """Format pari passu extraction prompt with prospectus text."""
    return PARI_PASSU_EXTRACTION_PROMPT.format(prospectus_text=text)


def create_events_of_default_prompt(text: str) -> str:
    """Format events of default extraction prompt with prospectus text."""
    return EVENTS_OF_DEFAULT_EXTRACTION_PROMPT.format(prospectus_text=text)


def create_negative_pledge_prompt(text: str) -> str:
    """Format negative pledge extraction prompt with prospectus text."""
    return NEGATIVE_PLEDGE_EXTRACTION_PROMPT.format(prospectus_text=text)


def create_governing_law_prompt(text: str) -> str:
    """Format governing law extraction prompt with prospectus text."""
    return GOVERNING_LAW_EXTRACTION_PROMPT.format(prospectus_text=text)


def create_batch_extraction_prompt(text: str) -> str:
    """Format batch extraction prompt with prospectus text."""
    return BATCH_EXTRACTION_PROMPT.format(prospectus_text=text)


# ==============================================================================
# PROMPT CHAINING FOR ITERATIVE EXTRACTION
# ==============================================================================

def create_refinement_prompt(
    clause_type: str, 
    extracted_text: str, 
    context: str
) -> str:
    """
    Create a refinement prompt to clarify or validate extracted clause language.
    
    Args:
        clause_type: Type of clause (e.g., "CAC", "pari_passu")
        extracted_text: Previously extracted clause language
        context: Additional context from prospectus
    
    Returns:
        Refinement prompt (string)
    """
    return f"""
Review the following extracted {clause_type} language and clarify any ambiguities:

EXTRACTED TEXT:
{extracted_text}

SURROUNDING CONTEXT:
{context}

Based on the full context, provide:
1. **Clarification**: Any ambiguities in the extracted language?
2. **Classification**: Which category best describes this clause?
3. **Alternative wording**: Any alternative phrasing that better captures the intent?
4. **Confidence**: 0-100 confidence in the extraction

Return as JSON.
"""


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == "__main__":
    # Example prospectus excerpt
    sample_text = """
    TERMS AND CONDITIONS OF THE NOTES
    ...
    Collective Action Clauses. The Noteholders shall have the right, by extraordinary 
    resolution, to amend or waive any provision of these Conditions. An extraordinary 
    resolution is passed when holders of not less than 75% in principal amount of 
    outstanding Notes, voting together as a single class, vote in favor of the resolution.
    ...
    Pari Passu. The Notes rank pari passu with all other unsecured and unsubordinated 
    obligations of the Republic, save for exceptions in favour of official sector creditors 
    as defined in the Common Framework.
    ...
    """
    
    # Example: Extract CACs
    prompt = create_cac_prompt(sample_text)
    print("CAC Extraction Prompt:")
    print(prompt[:200] + "...")
    print()
    
    # Example: Batch extraction
    batch_prompt = create_batch_extraction_prompt(sample_text)
    print("Batch Extraction Prompt:")
    print(batch_prompt[:200] + "...")
