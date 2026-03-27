"""PDIP Label Studio label → clause family mapping.

Each PDIP annotation label maps to exactly one clause family (or None
if unmapped). This mapping is used by both the clause extractor and
the validation module.

The 109 observed labels are from the 2026-03-26 full harvest of 162
annotated PDIP documents.
"""

from __future__ import annotations

# Strictly one label → one family for the demo.
# None = unmapped (not yet assigned to a family).
PDIP_LABEL_TO_FAMILY: dict[str, str | None] = {
    # ── Collective Action / Modification ─────────────────────────
    "VotingCollectiveActionModification_AmendmentandWaiver": "collective_action",
    "VotingCollectiveActionModification_Double_Limb": "collective_action",
    "VotingCollectiveActionModification_Single_Limb": "collective_action",
    "VotingCollectiveActionModification_Supermajority": "collective_action",
    "VotingCollectiveActionModification_UnanimousConsent": "collective_action",
    # ── Acceleration ─────────────────────────────────────────────
    "VotingRequirementforAcceleration_AmendmentandWaiver": "acceleration",
    "Acceleration_Consequences": "acceleration",
    # ── Pari Passu ───────────────────────────────────────────────
    "StatusofObligationPariPassu_RepresentationsWarranties": "pari_passu",
    # ── Negative Pledge ──────────────────────────────────────────
    "NegativePledge_BorrowerCovenantsUndertakings": "negative_pledge",
    # ── Governing Law ────────────────────────────────────────────
    "GoverningLaw_Enforcement": "governing_law",
    # ── Events of Default ────────────────────────────────────────
    "Non-paymentFailuretoPay_EventsofDefaultandConsequences": "events_of_default",
    "CovenantDefault_EventsofDefaultandConsequences": "events_of_default",
    "CrossDefault_EventsofDefaultandConsequences": "events_of_default",
    "Other_EventsofDefaultandConsequences": "events_of_default",
    "UnlawfulnessIllegalityInvalidityBorrower_EventsofDefaultandConsequences": "events_of_default",
    "MoratoriumRepudiationAuthority_EventsofDefaultandConsequences": "events_of_default",
    "InsolvencyBankruptcy_EventsofDefaultandConsequences": "events_of_default",
    "Non-complianceJudgement_EventsofDefaultandConsequences": "events_of_default",
    "MaterialAdverseChange_EventsofDefaultandConsequences": "events_of_default",
    "MisrepresentationRepresentation_EventsofDefaultandConsequences": "events_of_default",
    # ── Amendment and Waiver ─────────────────────────────────────
    "AmendmentandWaiver_AmendmentandWaiver": "amendment_waiver",
    "Meetingsinc.WrittenConsent_AmendmentandWaiver": "amendment_waiver",
    # ── Financial Terms ──────────────────────────────────────────
    "Interest_FinancialTerms": "interest",
    "Commitment_FinancialTerms": "commitment",
    "Fees_FinancialTerms": "fees",
    "Purpose_FinancialTerms": "purpose",
    "CurrencyofDenominationandorPayment_FinancialTerms": "currency",
    # ── Repayment ────────────────────────────────────────────────
    "PaymentMechanics_Repayment": "payment_mechanics",
    "RedemptionRepurchaseEarlyRepayment_Repayment": "redemption",
    "AdditionalAmounts_Repayment": "additional_amounts",
    # ── Enforcement ──────────────────────────────────────────────
    "DisputeResolution_Enforcement": "dispute_resolution",
    "SovereignImmunityWaiver_Enforcement": "sovereign_immunity",
    # ── Conditions ───────────────────────────────────────────────
    "ConditionsUtilization_ConditionsPrecedent": "conditions_precedent",
    "ConditionsEffectiveness_ConditionsPrecedent": "conditions_precedent",
    # ── Borrower Covenants ───────────────────────────────────────
    "Information_BorrowerCovenantsUndertakings": "information_covenants",
    "UseofProceeds_BorrowerCovenantsUndertakings": "use_of_proceeds",
    "BooksandRecords_BorrowerCovenantsUndertakings": "books_records",
    "Other_BorrowerCovenantsUndertakings": None,  # too generic to map
    # ── Coordination / Administration ────────────────────────────
    "DutiesofTrusteeFiscalAgent_CoordinationAdministration": "trustee_duties",
    # ── Definitions ──────────────────────────────────────────────
    "Indebtedness_Definitions": "indebtedness_definition",
    # ── Disbursement ─────────────────────────────────────────────
    "UtilizationBorrowing_Disbursement": "disbursement",
    # ── Internal Reference (not a clause family) ─────────────────
    "InternalReference": None,
    # ── External links (not clause annotations) ──────────────────
    "externallink1": None,
    "externallink2": None,
    "externallink3": None,
}

# For ambiguous labels that could belong to multiple families
MAPPING_NOTES: dict[str, str] = {
    "VotingCollectiveActionModification_AmendmentandWaiver": (
        "Could be 'amendment_waiver' family; mapped to 'collective_action' "
        "because the CAC voting mechanism is the primary semantic content"
    ),
    "Acceleration_Consequences": (
        "Could be 'events_of_default'; mapped to 'acceleration' because "
        "acceleration is the specific mechanism, not just any default consequence"
    ),
}


def map_label(label: str) -> str | None:
    """Map a PDIP label to a clause family. Returns None if unmapped."""
    return PDIP_LABEL_TO_FAMILY.get(label)


def unmapped_labels(observed: list[str]) -> list[str]:
    """Return labels not present in the mapping dict."""
    return [lbl for lbl in observed if lbl not in PDIP_LABEL_TO_FAMILY]
