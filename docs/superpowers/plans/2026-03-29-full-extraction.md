# Full Corpus Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **CRITICAL:** This plan covers the **prerequisites** that must be built before
> the Mac Mini extraction session launches. The actual extraction (LOCATE→EXTRACT→VERIFY
> for each family) is executed by the Mac Mini session, not this plan.

**Goal:** Build all infrastructure needed for Round 1 (governing_law, sovereign_immunity, negative_pledge, events_of_default, document_classification) and Round 2 (acceleration, dispute_resolution, additional_amounts, redemption, indebtedness_definition) extraction on the Mac Mini.

**Architecture:** Extend the existing v2 extraction pipeline (cue_families.py, section_filter.py, verify.py, cli.py) to support all clause families. Add document classification as a new workstream. Add run manifest, round reports, and meta-learning infrastructure.

**Tech Stack:** Python 3.12+, Click CLI, DuckDB, Polars, pytest, ruff, pyright.

**Spec:** `docs/superpowers/specs/2026-03-29-full-extraction-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/corpus/extraction/document_classifier.py` | Document classification pipeline (instrument_family, document_role, document_form) |
| `src/corpus/extraction/run_manifest.py` | Run manifest + per-family completion protocol |
| `scripts/round_report.py` | Round report generation (quality metrics, trust cards, phone-friendly status) |
| `scripts/generate_splits.py` | Generate PDIP calibration/evaluation splits for all families |
| `docs/meta-learning-round-0.md` | Lessons from PR #44 extraction |
| `tests/test_document_classifier.py` | Document classifier tests |
| `tests/test_run_manifest.py` | Run manifest tests |
| `tests/test_round_report.py` | Round report tests |
| `data/pdip/splits/` | Per-family split manifests |

### Modified files

| File | Change |
|------|--------|
| `src/corpus/extraction/cue_families.py` | Add cue definitions for 9 new clause families (Round 1 + Round 2) |
| `src/corpus/extraction/verify.py` | Add completeness checklist patterns for new families + section_capture_similarity |
| `src/corpus/extraction/llm_extractor.py` | Instrument-aware prompt variants, clause descriptions for new families |
| `src/corpus/cli.py` | Dynamic clause family choices, run_id directory structure, document classification command |
| `tests/test_cue_families.py` | Tests for new cue patterns |

---

## Task 1: Extend Cue Families for Round 1

**Files:**
- Modify: `src/corpus/extraction/cue_families.py`
- Test: `tests/test_cue_families.py`

- [ ] **Step 1: Write tests for new cue families**

Add to `tests/test_cue_families.py`:

```python
# --- Round 1 family tests ---

def test_governing_law_cues_have_heading_family() -> None:
    from corpus.extraction.cue_families import GOVERNING_LAW_CUES
    assert "heading" in GOVERNING_LAW_CUES


def test_governing_law_heading_matches() -> None:
    from corpus.extraction.cue_families import GOVERNING_LAW_CUES
    import re
    heading_patterns = GOVERNING_LAW_CUES["heading"]
    assert any(re.search(p, "Governing Law", re.IGNORECASE) for p in heading_patterns)
    assert any(re.search(p, "Applicable Law", re.IGNORECASE) for p in heading_patterns)


def test_sovereign_immunity_cues_have_heading_family() -> None:
    from corpus.extraction.cue_families import SOVEREIGN_IMMUNITY_CUES
    assert "heading" in SOVEREIGN_IMMUNITY_CUES


def test_sovereign_immunity_heading_matches() -> None:
    from corpus.extraction.cue_families import SOVEREIGN_IMMUNITY_CUES
    import re
    patterns = SOVEREIGN_IMMUNITY_CUES["heading"]
    assert any(re.search(p, "Sovereign Immunity", re.IGNORECASE) for p in patterns)
    assert any(re.search(p, "Waiver of Immunity", re.IGNORECASE) for p in patterns)


def test_negative_pledge_cues_have_heading_family() -> None:
    from corpus.extraction.cue_families import NEGATIVE_PLEDGE_CUES
    assert "heading" in NEGATIVE_PLEDGE_CUES


def test_events_of_default_cues_have_heading_family() -> None:
    from corpus.extraction.cue_families import EVENTS_OF_DEFAULT_CUES
    assert "heading" in EVENTS_OF_DEFAULT_CUES


def test_get_cue_families_governing_law() -> None:
    from corpus.extraction.cue_families import get_cue_families, GOVERNING_LAW_CUES
    assert get_cue_families("governing_law") is GOVERNING_LAW_CUES


def test_get_cue_families_all_round1() -> None:
    from corpus.extraction.cue_families import get_cue_families
    for family in ["governing_law", "sovereign_immunity", "negative_pledge", "events_of_default"]:
        assert get_cue_families(family) is not None, f"Missing cue family: {family}"


def test_get_cue_families_all_round2() -> None:
    from corpus.extraction.cue_families import get_cue_families
    for family in ["acceleration", "dispute_resolution", "additional_amounts", "redemption", "indebtedness_definition"]:
        assert get_cue_families(family) is not None, f"Missing cue family: {family}"


def test_all_new_patterns_compile() -> None:
    """Every pattern string in new families must be a valid regex."""
    import re
    from corpus.extraction.cue_families import get_cue_families
    for family in [
        "governing_law", "sovereign_immunity", "negative_pledge",
        "events_of_default", "acceleration", "dispute_resolution",
        "additional_amounts", "redemption", "indebtedness_definition",
    ]:
        cues = get_cue_families(family)
        assert cues is not None
        for _fam, patterns in cues.items():
            for p in patterns:
                re.compile(p, re.IGNORECASE)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cue_families.py -v -k "round1 or round2 or governing or sovereign or negative or events or acceleration or dispute or additional or redemption or indebtedness or new_patterns"`
Expected: FAIL — ImportError for new constants

- [ ] **Step 3: Add Round 1 cue families**

Add to `src/corpus/extraction/cue_families.py`:

```python
GOVERNING_LAW_CUES: dict[str, list[str]] = {
    "heading": [
        r"governing\s+law",
        r"applicable\s+law",
        r"choice\s+of\s+law",
        r"law\s+and\s+jurisdiction",
    ],
    "jurisdiction": [
        r"governed\s+by\s+(the\s+)?law(s)?\s+of",
        r"construed\s+in\s+accordance\s+with",
        r"subject\s+to\s+(the\s+)?(law(s)?|jurisdiction)\s+of",
        r"(english|new\s+york|german)\s+law",
    ],
}

SOVEREIGN_IMMUNITY_CUES: dict[str, list[str]] = {
    "heading": [
        r"sovereign\s+immunit(y|ies)",
        r"waiver\s+of\s+immunit(y|ies)",
        r"immunit(y|ies)\s+from\s+(jurisdiction|execution|suit)",
        r"consent\s+to\s+(jurisdiction|service|suit)",
    ],
    "waiver": [
        r"irrevocabl(e|y)\s+(waive|consent)",
        r"waive(s|d)?\s+(any|all|its)?\s*immunit(y|ies)",
        r"sovereign\s+or\s+crown\s+immunit(y|ies)",
        r"foreign\s+sovereign\s+immunit(y|ies)\s+act",
        r"state\s+immunit(y|ies)\s+act",
    ],
    "execution": [
        r"attachment\s+(prior|before)\s+to?\s+judgment",
        r"execution\s+of\s+judgment",
        r"immunit(y|ies)\s+from\s+(attachment|execution|seizure)",
    ],
}

NEGATIVE_PLEDGE_CUES: dict[str, list[str]] = {
    "heading": [
        r"negative\s+pledge",
        r"limitation\s+on\s+liens",
        r"restriction\s+on\s+(security|liens|encumbrances)",
    ],
    "pledge": [
        r"will\s+not\s+create\s+(or\s+permit\s+)?(any\s+)?(lien|security\s+interest|encumbrance|mortgage)",
        r"no\s+(lien|security\s+interest|mortgage|charge)\s+(shall|will)\s+be\s+created",
        r"not\s+(to\s+)?grant\s+(or\s+permit\s+)?(any\s+)?(security|lien)",
    ],
    "exception": [
        r"permitted\s+(lien|security|encumbrance|exception)",
        r"(except|unless|provided\s+that).{0,50}(equally|ratabl|pari\s+passu)\s+secured",
    ],
}

EVENTS_OF_DEFAULT_CUES: dict[str, list[str]] = {
    "heading": [
        r"events?\s+of\s+default",
        r"default\s+and\s+enforcement",
        r"acceleration",
    ],
    "trigger": [
        r"(non[\s-]?payment|failure\s+to\s+pay)",
        r"cross[\s-]?default",
        r"breach\s+of\s+(covenant|obligation|undertaking|representation)",
        r"(insolvency|bankruptcy|winding[\s-]?up|liquidation)",
        r"moratorium",
        r"repudiation",
        r"(illegality|unlawfulness|invalidity)",
    ],
    "consequence": [
        r"(may\s+be\s+)?declared\s+(immediately\s+)?due\s+and\s+payable",
        r"accelerat(e|ion|ed)",
        r"shall\s+become\s+(immediately\s+)?due",
    ],
}
```

- [ ] **Step 4: Add Round 2 cue families**

Add to `src/corpus/extraction/cue_families.py`:

```python
ACCELERATION_CUES: dict[str, list[str]] = {
    "heading": [
        r"acceleration",
        r"enforcement\s+of\s+(the\s+)?(notes|bonds|securities)",
    ],
    "mechanism": [
        r"declared\s+(immediately\s+)?due\s+and\s+payable",
        r"accelerat(e|ion|ed)",
        r"principal\s+amount.{0,30}(become|declared)\s+(immediately\s+)?due",
        r"shall\s+become\s+(immediately\s+)?due",
    ],
}

DISPUTE_RESOLUTION_CUES: dict[str, list[str]] = {
    "heading": [
        r"dispute\s+resolution",
        r"arbitration",
        r"jurisdiction",
        r"submission\s+to\s+jurisdiction",
        r"forum\s+selection",
    ],
    "mechanism": [
        r"(ICSID|ICC|LCIA|UNCITRAL|AAA)\s+(arbitration|rules)",
        r"submit(s|ted)?\s+to\s+the\s+(exclusive\s+)?jurisdiction",
        r"(courts?\s+of|tribunal)\s+(England|New\s+York|the\s+State)",
        r"arbitrat(e|ion|ed|or)",
    ],
}

ADDITIONAL_AMOUNTS_CUES: dict[str, list[str]] = {
    "heading": [
        r"additional\s+amounts",
        r"gross[\s-]?up",
        r"tax(ation)?\s+(gross[\s-]?up|indemnit)",
    ],
    "obligation": [
        r"additional\s+amounts\s+(as\s+)?will\s+result\s+in",
        r"(pay|paying)\s+(such\s+)?additional\s+amounts",
        r"without\s+(withholding|deduction)\s+for\s+(or\s+on\s+account\s+of\s+)?(any\s+)?tax",
        r"gross[\s-]?up",
    ],
}

REDEMPTION_CUES: dict[str, list[str]] = {
    "heading": [
        r"(optional|early|mandatory)\s+redemption",
        r"redemption\s+(and\s+)?purchase",
        r"(repurchase|repayment)\s+(at\s+the\s+option|upon\s+request)",
    ],
    "mechanism": [
        r"redeem(ed)?\s+(all\s+or\s+(a\s+)?part|in\s+whole\s+or\s+in\s+part)",
        r"(call|make[\s-]?whole)\s+(premium|amount|price)",
        r"tax\s+redemption",
        r"at\s+a\s+redemption\s+price",
    ],
}

INDEBTEDNESS_DEFINITION_CUES: dict[str, list[str]] = {
    "heading": [
        r"(definition|interpretation)\s+of\s+indebtedness",
        r"indebtedness",
        r"(external|public)\s+(indebtedness|debt)",
    ],
    "definition": [
        r"indebtedness\s+means",
        r"(external|public)\s+(indebtedness|debt)\s+(means|shall\s+mean)",
        r"(obligation|liability)\s+for\s+(borrowed\s+money|the\s+payment)",
    ],
}
```

- [ ] **Step 5: Register all new families in _CLAUSE_CUES**

Update the `_CLAUSE_CUES` dict:

```python
_CLAUSE_CUES: dict[str, dict[str, list[str]]] = {
    "collective_action": CAC_CUES,
    "pari_passu": PARI_PASSU_CUES,
    "governing_law": GOVERNING_LAW_CUES,
    "sovereign_immunity": SOVEREIGN_IMMUNITY_CUES,
    "negative_pledge": NEGATIVE_PLEDGE_CUES,
    "events_of_default": EVENTS_OF_DEFAULT_CUES,
    "acceleration": ACCELERATION_CUES,
    "dispute_resolution": DISPUTE_RESOLUTION_CUES,
    "additional_amounts": ADDITIONAL_AMOUNTS_CUES,
    "redemption": REDEMPTION_CUES,
    "indebtedness_definition": INDEBTEDNESS_DEFINITION_CUES,
}
```

- [ ] **Step 6: Run tests to verify all pass**

Run: `uv run pytest tests/test_cue_families.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 7: Commit**

```bash
git add src/corpus/extraction/cue_families.py tests/test_cue_families.py
git commit -m "feat: cue families for Round 1 + Round 2 clause types (9 new families)"
```

---

## Task 2: Extend CLI to Accept All Clause Families

**Files:**
- Modify: `src/corpus/cli.py`

- [ ] **Step 1: Replace hardcoded Click.Choice with dynamic lookup**

In `src/corpus/cli.py`, find the two `click.Choice(["collective_action", "pari_passu"])` at lines ~1162 and ~1331. Replace both with a callback that validates against `_CLAUSE_CUES`:

```python
def _validate_clause_family(ctx, param, value):
    """Validate clause family against registered cue families."""
    from corpus.extraction.cue_families import get_cue_families
    if get_cue_families(value) is None:
        raise click.BadParameter(
            f"Unknown clause family '{value}'. "
            f"Check _CLAUSE_CUES in cue_families.py."
        )
    return value
```

Replace:
```python
@click.option("--clause-family", required=True, type=click.Choice(["collective_action", "pari_passu"]))
```
With:
```python
@click.option("--clause-family", required=True, callback=_validate_clause_family, is_eager=True)
```

Do this for BOTH the `locate` and `verify` commands.

- [ ] **Step 2: Add run-id directory structure to locate**

In the `extract_v2_locate` command, update the output path to use run_id-scoped directories:

```python
    # Output path: data/extracted_v2/<run_id>/<family>/candidates.jsonl
    run_dir = _PROJECT_ROOT / "data" / "extracted_v2" / run_id / clause_family
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(output) if output else run_dir / "candidates.jsonl"
```

Similarly update the verify command's output path.

- [ ] **Step 3: Test that new families are accepted**

```bash
uv run corpus extract-v2 locate --clause-family governing_law --help
uv run corpus extract-v2 locate --clause-family events_of_default --help
uv run corpus extract-v2 locate --clause-family nonexistent_family --help  # should error
```

- [ ] **Step 4: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: CLI accepts all registered clause families dynamically"
```

---

## Task 3: Add Completeness Checklist for New Families

**Files:**
- Modify: `src/corpus/extraction/verify.py`
- Test: `tests/test_verify.py`

- [ ] **Step 1: Write tests for new completeness checks**

Add to `tests/test_verify.py`:

```python
def test_completeness_governing_law() -> None:
    text = "This Agreement shall be governed by and construed in accordance with the laws of the State of New York."
    report = check_completeness(text, clause_family="governing_law")
    assert report["jurisdiction"] is True


def test_completeness_sovereign_immunity() -> None:
    text = "The Issuer irrevocably waives all immunity from jurisdiction, attachment and execution."
    report = check_completeness(text, clause_family="sovereign_immunity")
    assert report["waiver"] is True


def test_completeness_negative_pledge() -> None:
    text = "The Issuer will not create or permit any lien on its assets, except for permitted liens."
    report = check_completeness(text, clause_family="negative_pledge")
    assert report["pledge"] is True
    assert report["exception"] is True


def test_completeness_events_of_default() -> None:
    text = "If an Event of Default occurs: non-payment, cross-default, insolvency, the bonds may be declared due and payable."
    report = check_completeness(text, clause_family="events_of_default")
    assert report["trigger"] is True
    assert report["consequence"] is True


def test_completeness_unknown_family_returns_empty() -> None:
    report = check_completeness("any text", clause_family="nonexistent")
    assert report == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_verify.py -v -k "governing or sovereign or negative or events_of_default or unknown_family"`
Expected: FAIL — completeness returns empty dict for new families

- [ ] **Step 3: Add completeness patterns**

Add to `src/corpus/extraction/verify.py`:

```python
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
```

Update `check_completeness()` to use all component dicts:

```python
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
        report[component] = any(
            re.search(p, extracted_text, re.IGNORECASE) for p in patterns
        )
    return report
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/test_verify.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/verify.py tests/test_verify.py
git commit -m "feat: completeness checklist patterns for Round 1 + Round 2 families"
```

---

## Task 4: Instrument-Aware Prompting

**Files:**
- Modify: `src/corpus/extraction/llm_extractor.py`
- Test: `tests/test_llm_extractor.py`

- [ ] **Step 1: Write test**

Add to `tests/test_llm_extractor.py`:

```python
def test_build_prompt_includes_clause_description_governing_law() -> None:
    from corpus.extraction.llm_extractor import CLAUSE_DESCRIPTIONS
    assert "governing_law" in CLAUSE_DESCRIPTIONS


def test_build_prompt_adapts_to_loan() -> None:
    candidate = _make_candidate()
    messages = build_extraction_prompt(
        candidate=candidate,
        clause_family="governing_law",
        country="Indonesia",
        few_shot_examples=[],
        instrument_type="Loan",
    )
    full_text = " ".join(m["content"] for m in messages if isinstance(m["content"], str))
    assert "loan agreement" in full_text.lower() or "loan" in full_text.lower()
```

- [ ] **Step 2: Add clause descriptions and instrument-aware prompt**

Add to `CLAUSE_DESCRIPTIONS` in `llm_extractor.py`:

```python
CLAUSE_DESCRIPTIONS = {
    "collective_action": "Collective Action Clause (CAC) — provisions allowing a qualified majority of bondholders to modify the terms of the bonds.",
    "pari_passu": "Pari Passu Clause — provisions establishing that the bonds rank equally with other unsecured obligations.",
    "governing_law": "Governing Law Clause — provisions specifying which jurisdiction's laws govern the contract.",
    "sovereign_immunity": "Sovereign Immunity Waiver — provisions where the sovereign waives immunity from suit, jurisdiction, and/or execution.",
    "negative_pledge": "Negative Pledge Clause — provisions restricting the borrower from granting security interests over assets, with permitted exceptions.",
    "events_of_default": "Events of Default — provisions defining circumstances that constitute a default and their consequences (acceleration, remedies).",
    "acceleration": "Acceleration Clause — provisions allowing creditors to declare obligations immediately due and payable upon default.",
    "dispute_resolution": "Dispute Resolution Clause — provisions specifying how disputes are resolved (arbitration, court jurisdiction, governing forum).",
    "additional_amounts": "Additional Amounts / Gross-Up — provisions requiring the issuer to pay additional amounts to compensate for tax withholding.",
    "redemption": "Redemption Clause — provisions for optional, mandatory, or tax-related early redemption of the securities.",
    "indebtedness_definition": "Indebtedness Definition — the contractual definition of what constitutes 'indebtedness' or 'external debt'.",
}
```

Update `build_extraction_prompt()` to accept `instrument_type` parameter:

```python
def build_extraction_prompt(
    *,
    candidate: Candidate,
    clause_family: str,
    country: str,
    few_shot_examples: list[FewShotExample],
    icma_reference: str = "",
    instrument_type: str = "Bond",
) -> list[dict]:
    """Build the message list for extraction."""
    # Adapt system prompt for instrument type
    instrument_label = "bond prospectus" if instrument_type == "Bond" else "loan agreement"
    system = SYSTEM_PROMPT.replace("bond prospectuses", f"{instrument_label}s")
    system = system.replace("bond contracts", f"sovereign debt contracts")

    # Note: "system" role is for reference/documentation. When calling
    # the Anthropic API directly, system would be a top-level parameter.
    messages: list[dict] = [{"role": "system", "content": system}]
    # ... rest of function unchanged
```

- [ ] **Step 3: Run tests, commit**

Run: `uv run pytest tests/test_llm_extractor.py -v`

```bash
git add src/corpus/extraction/llm_extractor.py tests/test_llm_extractor.py
git commit -m "feat: instrument-aware prompting + clause descriptions for all families"
```

---

## Task 5: Document Classification Pipeline

**Files:**
- Create: `src/corpus/extraction/document_classifier.py`
- Create: `tests/test_document_classifier.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_document_classifier.py
"""Tests for document classification pipeline."""

from __future__ import annotations

from corpus.extraction.document_classifier import (
    classify_document,
    parse_edgar_form_code,
)


def test_classify_base_prospectus() -> None:
    text = "BASE PROSPECTUS dated 15 March 2024\n\nGlobal Medium Term Note Programme"
    result = classify_document(text, storage_key="nsm__12345")
    assert result["instrument_family"] == "Bond"
    assert result["document_role"] == "Base document"
    assert result["document_form"] == "Prospectus"
    assert result["confidence"] in ("high", "medium", "low")


def test_classify_pricing_supplement() -> None:
    text = "PRICING SUPPLEMENT dated 20 March 2024\n\nSeries 2024-1 Notes"
    result = classify_document(text, storage_key="nsm__67890")
    assert result["document_role"] == "Supplement"
    assert result["document_form"] == "Pricing Supplement"


def test_classify_loan_agreement() -> None:
    text = "LOAN AGREEMENT\n\nbetween\n\nRepublic of Kenya\nand\nInternational Bank"
    result = classify_document(text, storage_key="pdip__KEN28")
    assert result["instrument_family"] == "Loan"
    assert result["document_form"] == "Loan Agreement"


def test_classify_novel_type() -> None:
    text = "CONSENT SOLICITATION STATEMENT\n\nRelating to the outstanding bonds"
    result = classify_document(text, storage_key="edgar__123")
    assert result["document_form"] == "Other"
    assert "Consent Solicitation Statement" in result.get("novel_types_observed", [])


def test_parse_edgar_form_code_424b5() -> None:
    text = "424B5\n1\nPROSPECTUS SUPPLEMENT\nRepublic of Panama"
    code = parse_edgar_form_code(text)
    assert code == "424B5"


def test_parse_edgar_form_code_missing() -> None:
    text = "This is a bond prospectus with no SEC header."
    code = parse_edgar_form_code(text)
    assert code is None


def test_classify_includes_evidence() -> None:
    text = "BASE PROSPECTUS dated 15 March 2024\n\nSome content"
    result = classify_document(text, storage_key="nsm__12345")
    assert result.get("evidence_text", "") != ""
    assert result.get("reasoning", "") != ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_document_classifier.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write the implementation**

```python
# src/corpus/extraction/document_classifier.py
"""Document classification: instrument_family, document_role, document_form.

Classifies sovereign debt documents by reading the first ~10K characters.
This is a separate workstream from clause extraction — different pipeline,
different output format.

IMPORTANT CAVEAT: This taxonomy is a best-effort starting point. Domain
expert review (legal scholars, practitioners) is needed to validate.
"""

from __future__ import annotations

import re

# SEC form code → document metadata mapping
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

_EDGAR_FORM_RE = re.compile(r"^(424B[1-5]|FWP|F-4|S-\d+)\s*\n", re.MULTILINE)


def parse_edgar_form_code(text: str) -> str | None:
    """Extract SEC form code from EDGAR file header."""
    m = _EDGAR_FORM_RE.search(text[:500])
    return m.group(1) if m else None


def classify_document(
    text: str,
    *,
    storage_key: str,
    max_chars: int = 10000,
) -> dict:
    """Classify a document by reading its opening text.

    Returns a dict with instrument_family, document_role, document_form,
    confidence, reasoning, evidence_text, novel_types_observed.
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
    # If first 500 chars are disclaimer boilerplate, extend
    check_text = sample
    if re.search(r"(?i)^important\s+notice", sample[:500]):
        check_text = text[:15000]

    for pattern, inst, role, form in _FORM_PATTERNS:
        m = re.search(pattern, check_text[:5000])
        if m:
            evidence = check_text[max(0, m.start() - 20) : m.end() + 50].strip()
            return {
                "storage_key": storage_key,
                "instrument_family": inst,
                "document_role": role,
                "document_form": form,
                "confidence": "high",
                "reasoning": f"Matched '{m.group()}' in opening text",
                "evidence_text": evidence[:200],
                "evidence_page": None,
                "novel_types_observed": [],
                "schema_version": "1.0",
            }

    # No pattern matched — look for novel type signals
    novel_types = []
    # Check for capitalized multi-word phrases that look like document types
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_document_classifier.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/corpus/extraction/document_classifier.py tests/test_document_classifier.py
git commit -m "feat: document classification pipeline — 3-axis taxonomy with novel type discovery"
```

---

## Task 6: Run Manifest + Completion Protocol

**Files:**
- Create: `src/corpus/extraction/run_manifest.py`
- Test: `tests/test_run_manifest.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_run_manifest.py
"""Tests for run manifest and completion protocol."""

from __future__ import annotations

import json
from pathlib import Path

from corpus.extraction.run_manifest import (
    RunManifest,
    mark_family_complete,
    mark_family_in_progress,
    create_manifest,
    load_manifest,
    is_family_complete,
)


def test_create_manifest(tmp_path: Path) -> None:
    families = ["governing_law", "sovereign_immunity"]
    manifest = create_manifest(
        run_dir=tmp_path,
        run_id="test_run",
        families=families,
    )
    assert manifest.run_id == "test_run"
    assert manifest.families_pending == families
    assert manifest.families_completed == []
    assert (tmp_path / "RUN_MANIFEST.json").exists()


def test_mark_family_in_progress(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law", "sovereign_immunity"])
    mark_family_in_progress(tmp_path, "governing_law")
    m = load_manifest(tmp_path)
    assert "governing_law" in m.families_in_progress
    assert "governing_law" not in m.families_pending


def test_mark_family_complete(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law"])
    mark_family_in_progress(tmp_path, "governing_law")
    family_dir = tmp_path / "governing_law"
    family_dir.mkdir()
    mark_family_complete(tmp_path, "governing_law")
    m = load_manifest(tmp_path)
    assert "governing_law" in m.families_completed
    assert (family_dir / "COMPLETE.json").exists()


def test_is_family_complete(tmp_path: Path) -> None:
    create_manifest(tmp_path, "test", ["governing_law"])
    assert is_family_complete(tmp_path, "governing_law") is False
    mark_family_in_progress(tmp_path, "governing_law")
    (tmp_path / "governing_law").mkdir()
    mark_family_complete(tmp_path, "governing_law")
    assert is_family_complete(tmp_path, "governing_law") is True
```

- [ ] **Step 2: Write implementation**

```python
# src/corpus/extraction/run_manifest.py
"""Run manifest and per-family completion protocol.

Each extraction run uses a run_id directory. Each family within the run
gets its own subdirectory with a COMPLETE.json sentinel written last.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class RunManifest:
    run_id: str
    families_completed: list[str] = field(default_factory=list)
    families_in_progress: list[str] = field(default_factory=list)
    families_pending: list[str] = field(default_factory=list)
    created_at: str = ""


def create_manifest(
    run_dir: Path,
    run_id: str,
    families: list[str],
) -> RunManifest:
    """Create a new run manifest."""
    manifest = RunManifest(
        run_id=run_id,
        families_pending=list(families),
        created_at=datetime.now(UTC).isoformat(),
    )
    _save(run_dir, manifest)
    return manifest


def load_manifest(run_dir: Path) -> RunManifest:
    """Load manifest from run directory."""
    path = run_dir / "RUN_MANIFEST.json"
    data = json.loads(path.read_text())
    return RunManifest(**data)


def mark_family_in_progress(run_dir: Path, family: str) -> None:
    """Mark a family as in-progress."""
    m = load_manifest(run_dir)
    if family in m.families_pending:
        m.families_pending.remove(family)
    if family not in m.families_in_progress:
        m.families_in_progress.append(family)
    _save(run_dir, m)


def mark_family_complete(run_dir: Path, family: str) -> None:
    """Mark a family as complete. Writes COMPLETE.json sentinel."""
    m = load_manifest(run_dir)
    if family in m.families_in_progress:
        m.families_in_progress.remove(family)
    if family not in m.families_completed:
        m.families_completed.append(family)
    _save(run_dir, m)

    # Write per-family COMPLETE.json
    family_dir = run_dir / family
    family_dir.mkdir(parents=True, exist_ok=True)
    completion = {
        "family": family,
        "completed_at": datetime.now(UTC).isoformat(),
        "run_id": m.run_id,
    }
    (family_dir / "COMPLETE.json").write_text(json.dumps(completion, indent=2) + "\n")


def is_family_complete(run_dir: Path, family: str) -> bool:
    """Check if a family has been completed."""
    return (run_dir / family / "COMPLETE.json").exists()


def _save(run_dir: Path, manifest: RunManifest) -> None:
    """Save manifest to disk."""
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": manifest.run_id,
        "families_completed": manifest.families_completed,
        "families_in_progress": manifest.families_in_progress,
        "families_pending": manifest.families_pending,
        "created_at": manifest.created_at,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    (run_dir / "RUN_MANIFEST.json").write_text(json.dumps(data, indent=2) + "\n")
```

- [ ] **Step 3: Run tests, commit**

```bash
uv run pytest tests/test_run_manifest.py -v
git add src/corpus/extraction/run_manifest.py tests/test_run_manifest.py
git commit -m "feat: run manifest + per-family completion protocol"
```

---

## Task 7: PDIP Splits for All Families

**Files:**
- Create: `scripts/generate_splits.py`
- Output: `data/pdip/splits/` directory with per-family manifests

- [ ] **Step 1: Write the split generation script**

```python
# scripts/generate_splits.py
"""Generate PDIP calibration/evaluation splits for all clause families."""

from __future__ import annotations

import json
from pathlib import Path

from corpus.extraction.pdip_split import create_split, save_split

ANNOTATIONS_PATH = Path("data/pdip/clause_annotations.jsonl")
SPLITS_DIR = Path("data/pdip/splits")


def main() -> None:
    # Discover all families in annotations
    families: dict[str, int] = {}
    with ANNOTATIONS_PATH.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            lf = r.get("label_family")
            if lf:
                families[lf] = families.get(lf, 0) + 1

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    for family, count in sorted(families.items()):
        split_path = SPLITS_DIR / f"{family}_split.json"
        if split_path.exists():
            print(f"  {family}: split already exists, skipping")
            continue

        # For small families (<15 docs), use 2 calibration docs
        # For medium (15-40), use 3
        # For large (>40), use 5
        doc_count = count  # rough — annotations != docs
        cal_count = 2 if doc_count < 30 else 3 if doc_count < 80 else 5

        try:
            split = create_split(
                ANNOTATIONS_PATH,
                clause_family=family,
                calibration_count=cal_count,
            )
            save_split(split, split_path, overwrite=False)
            cal = len(split["calibration"])
            eva = len(split["evaluation"])
            print(f"  {family}: {cal} calibration, {eva} evaluation")
        except ValueError as e:
            print(f"  {family}: SKIPPED — {e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
uv run python3 scripts/generate_splits.py
```

- [ ] **Step 3: Commit splits**

```bash
git add scripts/generate_splits.py data/pdip/splits/
git commit -m "feat: PDIP calibration/evaluation splits for all clause families"
```

---

## Task 8: Round Report Script

**Files:**
- Create: `scripts/round_report.py`
- Test: `tests/test_round_report.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_round_report.py
"""Tests for round report generation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.round_report import generate_family_report


def test_generate_family_report(tmp_path: Path) -> None:
    # Create mock verified JSONL
    verified_dir = tmp_path / "governing_law"
    verified_dir.mkdir()
    records = [
        {"candidate_id": "c1", "storage_key": "doc1", "source_format": "docling_md",
         "heading_match": True,
         "extraction": {"found": True, "clause_text": "governed by English law", "confidence": "high"},
         "verification": {"status": "verified", "verbatim_similarity": 1.0}},
        {"candidate_id": "c2", "storage_key": "doc2", "source_format": "flat_jsonl",
         "heading_match": False,
         "extraction": {"found": False, "clause_text": "", "confidence": "high"},
         "verification": {"status": "not_found"}},
    ]
    with (verified_dir / "verified.jsonl").open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    report = generate_family_report(
        family="governing_law",
        verified_path=verified_dir / "verified.jsonl",
    )
    assert report["family"] == "governing_law"
    assert report["total_candidates"] == 2
    assert report["found_count"] == 1
    assert report["not_found_count"] == 1
    assert report["verbatim_pass_count"] == 1
```

- [ ] **Step 2: Write implementation**

```python
#!/usr/bin/env python3
# scripts/round_report.py
"""Generate round reports for extraction quality metrics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def generate_family_report(
    *,
    family: str,
    verified_path: Path,
    annotations_path: Path | None = None,
) -> dict:
    """Generate quality metrics for a single family extraction."""
    records = []
    with verified_path.open() as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    found = [r for r in records if r.get("extraction", {}).get("found")]
    not_found = [r for r in records if not r.get("extraction", {}).get("found")]
    verified = [r for r in found if r.get("verification", {}).get("status") == "verified"]
    failed = [r for r in found if r.get("verification", {}).get("status") == "failed"]

    # Source mix
    source_mix = Counter(r.get("source_format", "unknown") for r in records)
    heading_match_count = sum(1 for r in records if r.get("heading_match"))

    # Confidence distribution
    confidence_dist = Counter(
        r.get("extraction", {}).get("confidence", "unknown") for r in found
    )

    return {
        "family": family,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_candidates": len(records),
        "found_count": len(found),
        "not_found_count": len(not_found),
        "verbatim_pass_count": len(verified),
        "verbatim_fail_count": len(failed),
        "verbatim_pass_rate": round(len(verified) / len(found), 3) if found else 0,
        "source_mix": dict(source_mix),
        "heading_match_count": heading_match_count,
        "body_only_count": len(records) - heading_match_count,
        "confidence_distribution": dict(confidence_dist),
    }


def format_phone_status(reports: list[dict], run_id: str) -> str:
    """Format a concise status for iPhone review."""
    lines = [f"Run {run_id} status:\n"]
    for r in reports:
        fam = r["family"]
        found = r["found_count"]
        vpass = r["verbatim_pass_count"]
        total = r["total_candidates"]
        rate = f"{r['verbatim_pass_rate']:.0%}" if r["found_count"] else "N/A"
        lines.append(f"  {fam}: {found}/{total} found, {rate} verbatim")
    lines.append("\nReady for next family? Reply 'go' or give feedback.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate round report")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--family", type=str, default=None, help="Single family or all")
    parser.add_argument("--run-id", type=str, default="unknown")
    args = parser.parse_args()

    run_dir = args.run_dir
    reports = []

    if args.family:
        families = [args.family]
    else:
        families = [
            d.name for d in sorted(run_dir.iterdir())
            if d.is_dir() and (d / "verified.jsonl").exists()
        ]

    for family in families:
        verified_path = run_dir / family / "verified.jsonl"
        if not verified_path.exists():
            print(f"  {family}: no verified.jsonl found, skipping")
            continue
        report = generate_family_report(family=family, verified_path=verified_path)
        reports.append(report)
        print(f"  {family}: {report['found_count']}/{report['total_candidates']} found, "
              f"{report['verbatim_pass_rate']:.0%} verbatim")

    # Write JSON report
    report_path = run_dir / "round_report.json"
    report_path.write_text(json.dumps(reports, indent=2) + "\n")
    print(f"\nReport written to {report_path}")

    # Print phone-friendly status
    print("\n" + format_phone_status(reports, args.run_id))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests, commit**

```bash
uv run pytest tests/test_round_report.py -v
git add scripts/round_report.py tests/test_round_report.py
git commit -m "feat: round report script — quality metrics + phone-friendly status"
```

---

## Task 9: Meta-Learning Report

**Files:**
- Create: `docs/meta-learning-round-0.md`

- [ ] **Step 1: Write the report**

This captures lessons from the PR #44 extraction session. Write `docs/meta-learning-round-0.md`:

```markdown
# Meta-Learning Report: Round 0 (CAC + Pari Passu Extraction)

**Session:** PR #44, March 28, 2026
**Families:** collective_action, pari_passu
**Results:** 4,246 clauses extracted, 4,151 verbatim verified

## Bug Patterns from Code Review

### E20: Heading level emission
**Bug:** "Top two levels" meant H2/H3 docs emitted both, duplicating text.
**Fix:** Only emit shallowest structural level; skip singleton H1 titles.
**Prevention:** Test with real document heading structures, not just ## examples.

### Clustering gap semantics
**Bug:** Docstring said "gap <= 1" but code used `prev + 2`, merging non-adjacent.
**Fix:** Strict adjacency (diff == 1).
**Prevention:** Test the boundary case explicitly.

### Logger missing duration_ms
**Bug:** CorpusLogger.log() requires duration_ms kwarg; new code omitted it.
**Fix:** Wrap timed operations with time.monotonic().
**Prevention:** Run the actual CLI command (not just unit tests) before committing.

### candidate_id collision
**Bug:** 8-char UUID truncation → near-certain collisions at scale.
**Fix:** Full UUID.
**Prevention:** Never truncate identifiers.

## What Worked Well

- **Batching by text volume** (~200K chars per batch, ~50 candidates max)
- **Priority ordering** (heading-matched first, body-only later)
- **Sonnet subagents for extraction** (reserves Opus budget for orchestration)
- **Background agents** for lower-priority batches while foreground work continues
- **Incremental JSONL writes** with per-batch immutable files
- **3-model review** before execution caught major issues (E20, clustering, session limits)

## Throughput Actuals

| Metric | Value |
|--------|-------|
| Candidates processed | 5,953 |
| Wall time (EXTRACT) | ~3 hours |
| Candidates/minute | ~33 |
| Verbatim pass (CAC) | 98.3% |
| Verbatim pass (PP) | 96.1% |
| Weekly usage | ~18% (includes all other work) |

## Reviewer Patterns

All three code reviewers pushed for adding the anthropic SDK despite the plan
explicitly saying "Claude Code IS the extractor." Document this decision clearly
in plan headers to avoid repeated pushback.

## Recommendations for Future Rounds

1. Run LOCATE first for all families; estimate time from actual candidate counts
2. Process one family at a time within sessions (5-hour limit)
3. Use per-family COMPLETE.json sentinels, not round-level completion
4. For long sections (EoD), use section_capture_similarity, not verbatim pass
5. Generate round reports AFTER each family, not just after each round
6. Keep calibration/evaluation split integrity — tune on calibration only
```

- [ ] **Step 2: Commit**

```bash
git add docs/meta-learning-round-0.md
git commit -m "docs: meta-learning report from Round 0 (CAC + pari passu extraction)"
```

---

## Task 10: Document Classification CLI Command

**Files:**
- Modify: `src/corpus/cli.py`

- [ ] **Step 1: Add classify command to extract-v2 group**

Add to `src/corpus/cli.py` in the extract-v2 group:

```python
@extract_v2_group.command("classify")
@click.option("--docling-dir", default="data/parsed_docling", type=click.Path())
@click.option("--flat-dir", default="data/parsed", type=click.Path())
@click.option("--output", default=None, type=click.Path())
@click.option("--run-id", default=None)
@click.option("--skip-flat", is_flag=True)
def extract_v2_classify(
    docling_dir: str, flat_dir: str, output: str | None,
    run_id: str | None, skip_flat: bool,
) -> None:
    """Classify documents by type (instrument, role, form)."""
    import json
    import time

    from corpus.extraction.document_classifier import classify_document
    from corpus.io.safe_write import safe_write
    from corpus.logging import CorpusLogger

    run_id = run_id or f"classify_{int(time.time())}"
    config = _load_config()

    docling_resolved = Path(docling_dir)
    if not docling_resolved.is_absolute():
        docling_resolved = _PROJECT_ROOT / docling_resolved
    flat_resolved = Path(flat_dir)
    if not flat_resolved.is_absolute():
        flat_resolved = _PROJECT_ROOT / flat_resolved

    run_dir = _PROJECT_ROOT / "data" / "extracted_v2" / run_id / "document_classification"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(output) if output else run_dir / "classification.jsonl"

    log_path = _PROJECT_ROOT / "data" / "telemetry" / "extract_v2.jsonl"
    logger = CorpusLogger(log_path, run_id=run_id)

    results = []

    # Docling markdown
    if docling_resolved.exists():
        md_files = sorted(docling_resolved.glob("*.md"))
        click.echo(f"Classifying {len(md_files)} Docling documents...")
        for md_file in md_files:
            start = time.monotonic()
            storage_key = md_file.stem
            text = md_file.read_text(encoding="utf-8")
            result = classify_document(text, storage_key=storage_key)
            elapsed = int((time.monotonic() - start) * 1000)
            results.append(result)
            logger.log(
                document_id=storage_key, step="classify",
                duration_ms=elapsed, status=result["confidence"],
            )

    # EDGAR flat JSONL
    if not skip_flat and flat_resolved.exists():
        jsonl_files = sorted(flat_resolved.glob("edgar__*.jsonl"))
        click.echo(f"Classifying {len(jsonl_files)} EDGAR documents...")
        for jsonl_file in jsonl_files:
            start = time.monotonic()
            storage_key = jsonl_file.stem
            # Read first 3 pages
            pages_text = []
            with jsonl_file.open() as f:
                for i, line in enumerate(f):
                    if i > 3:
                        break
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "text" in rec:
                        pages_text.append(rec["text"])
            text = "\n\n".join(pages_text)
            result = classify_document(text, storage_key=storage_key)
            elapsed = int((time.monotonic() - start) * 1000)
            results.append(result)
            logger.log(
                document_id=storage_key, step="classify",
                duration_ms=elapsed, status=result["confidence"],
            )

    # Write results
    content = "".join(json.dumps(r) + "\n" for r in results)
    safe_write(output_path, content.encode(), overwrite=True)

    # Summary
    from collections import Counter
    forms = Counter(r["document_form"] for r in results)
    families = Counter(r["instrument_family"] for r in results)
    roles = Counter(r["document_role"] for r in results)
    novel = Counter(t for r in results for t in r.get("novel_types_observed", []))

    click.echo(f"\nClassified {len(results)} documents.")
    click.echo(f"  Instrument families: {dict(families)}")
    click.echo(f"  Document roles: {dict(roles)}")
    click.echo(f"  Document forms: {dict(forms.most_common(10))}")
    if novel:
        click.echo(f"  Novel types discovered: {dict(novel.most_common(10))}")
    click.echo(f"Written to {output_path}")
```

- [ ] **Step 2: Test it**

```bash
uv run corpus extract-v2 classify --help
# Quick smoke test with a small subset
uv run corpus extract-v2 classify --docling-dir data/parsed_docling --skip-flat --run-id test_classify 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat: document classification CLI command with novel type discovery"
```

---

## Task 11: Lint, Type Check, Full Test Suite

- [ ] **Step 1: Run all checks**

```bash
uv run ruff check src/corpus/extraction/ src/corpus/cli.py scripts/
uv run ruff format --check src/ tests/ scripts/
uv run pyright src/corpus/extraction/
uv run pytest -v
```

- [ ] **Step 2: Fix any issues**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: lint + type check clean for full extraction prerequisites"
```

---

## Task 12: Push and Create PR

- [ ] **Step 1: Push**

```bash
git push -u origin feature/full-extraction-round-1
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat: full extraction prerequisites — cue families, classification, round reports" \
  --body "Prerequisites for Mac Mini extraction session. See docs/superpowers/specs/2026-03-29-full-extraction-design.md"
```

---

## Known Risks

| Risk | Mitigation |
|------|-----------|
| Cue patterns too broad/narrow | Tune on calibration set after first LOCATE run |
| Document classifier fails on unexpected formats | novel_types_observed captures what we miss |
| EDGAR EoD sections split across pages | Source caveat flag, accept lower recall |
| Session limit hit mid-family | Per-batch immutable files + crash recovery prompt |
| Dropbox sync lag on large files | COMPLETE.json sentinel, don't read without it |
