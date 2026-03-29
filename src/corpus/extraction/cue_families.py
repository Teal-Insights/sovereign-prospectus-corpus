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

GOVERNING_LAW_CUES: dict[str, list[str]] = {
    "heading": [
        r"governing\s+law",
        r"applicable\s+law",
        r"choice\s+of\s+law",
        r"law\s+and\s+jurisdiction",
        r"governing\s+law\s+and\s+enforcement",
    ],
    "jurisdiction": [
        r"governed\s+by\s+(the\s+)?law(s)?\s+of",
        r"construed\s+in\s+accordance\s+with",
        r"subject\s+to\s+(the\s+)?(law(s)?|jurisdiction)\s+of",
    ],
    "law_reference": [
        r"(english|new\s+york|german|japanese)\s+law",
        r"laws?\s+of\s+(the\s+)?(state\s+of\s+)?(new\s+york|england|germany|japan)",
        r"(interpreted|construed)\s+in\s+accordance\s+with\s+(the\s+)?law",
    ],
}

SOVEREIGN_IMMUNITY_CUES: dict[str, list[str]] = {
    "heading": [
        r"sovereign\s+immunit(y|ies)",
        r"waiver\s+of\s+immunit(y|ies)",
        r"immunit(y|ies)\s+from\s+(jurisdiction|execution|suit)",
        r"consent\s+to\s+(jurisdiction|service|suit)",
        r"no\s+immunit(y|ies)",
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
        r"negative\s+pledge\s+covenant",
        r"restrictive\s+covenants",
    ],
    "pledge": [
        # Active voice: "will not create or permit to exist any lien" (Colombia, Brazil, Peru)
        r"will\s+not[^.]{0,60}create\s+(or\s+(permit|allow)(\s+to\s+(exist|subsist))?\s+)?(any\s+)?(lien|security\s+interest|encumbrance|mortgage)",
        # Mid-sentence: "create or permit to exist ... any Lien" (Turkey with qualifying clause)
        r"create\s+or\s+(permit|allow)\s+(to\s+(?:exist|subsist)\s+)?[^.]{0,40}?(lien|security\s+interest|encumbrance|mortgage)",
        # Grant/allow variant: "will not grant or allow any lien" (Chile)
        r"not\s+(to\s+)?(grant|create)\s+(or\s+(allow|permit)\s+)?(any\s+)?(lien|security\s+interest|encumbrance|mortgage)",
        # Passive voice fallback
        r"no\s+(lien|security\s+interest|mortgage|charge)\s+(shall|will)\s+be\s+created",
    ],
    "exception": [
        r"permitted\s+(lien|security|encumbrance|exception)",
        # Fixed: real text says "secured equally and ratably" not "equally secured"
        r"(except|unless|provided\s+that).{0,80}secured\s+(?:equally|ratabl|pari\s+passu)",
        # Standalone "secured equally/ratably/pari passu"
        r"secured\s+(equally|ratabl|rateabl|pari\s+passu)",
        # "equally and ratably/rateably" (handles UK spelling)
        r"equally\s+and\s+(ratabl|rateabl)",
    ],
}

EVENTS_OF_DEFAULT_CUES: dict[str, list[str]] = {
    "heading": [
        r"events?\s+of\s+default",
        r"default\s+and\s+enforcement",
        r"default.{0,40}acceleration",
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

ACCELERATION_CUES: dict[str, list[str]] = {
    "heading": [
        # Tightened: bare "acceleration" matched "Industrial Acceleration Zones",
        # "Growth Acceleration Program", and "Cross-acceleration" sub-clauses.
        r"acceleration\s+of\s+(maturity|the\s+notes|the\s+bonds|the\s+securities)",
        r"enforcement\s+of\s+(the\s+)?(notes|bonds|securities)",
        r"default\s*;\s*acceleration",
    ],
    "mechanism": [
        r"declared\s+(immediately\s+)?due\s+and\s+payable",
        r"principal\s+amount.{0,30}(become|declared)\s+(immediately\s+)?due",
    ],
    "trigger_reference": [
        r"accelerat(e|ion|ed)",
        r"shall\s+become\s+(immediately\s+)?due",
        r"upon\s+(the\s+)?occurrence\s+of",
    ],
}

DISPUTE_RESOLUTION_CUES: dict[str, list[str]] = {
    "heading": [
        r"dispute\s+resolution",
        r"arbitration",
        r"submission\s+to\s+jurisdiction",
        r"forum\s+selection",
        r"law\s+and\s+jurisdiction",
    ],
    "forum": [
        r"(ICSID|ICC|LCIA|UNCITRAL|AAA)\s+(arbitration|rules)",
        r"submit(s|ted)?\s+to\s+the\s+(exclusive\s+)?jurisdiction",
        r"(courts?\s+of|tribunal)\s+(England|New\s+York|the\s+State)",
    ],
    "mechanism": [
        r"arbitrat(e|ion|ed|or)",
        r"exclusive\s+jurisdiction",
        r"(irrevocably\s+)?submit",
    ],
}

ADDITIONAL_AMOUNTS_CUES: dict[str, list[str]] = {
    "heading": [
        r"additional\s+amounts",
        r"gross[\s-]?up",
        r"tax(ation)?\s+(gross[\s-]?up|indemnit)",
        # Operative gross-up clauses often live in "Taxation" conditions sections
        r"taxation\s+and\s+additional\s+amounts",
    ],
    "obligation": [
        r"additional\s+amounts\s+(as\s+)?will\s+result\s+in",
        r"(pay|paying)\s+(such\s+)?additional\s+amounts",
        r"gross[\s-]?up",
    ],
    "tax_context": [
        r"without\s+(withholding|deduction)\s+for\s+(or\s+on\s+account\s+of\s+)?(any\s+)?tax",
        r"(withholding|deduction)\s+(is\s+)?required\s+by\s+law",
        r"tax(es)?\s+(imposed|levied|assessed)\s+by",
    ],
}

REDEMPTION_CUES: dict[str, list[str]] = {
    "heading": [
        r"(optional|early|mandatory|scheduled|partial)\s+redemption",
        r"redemption\s+(and\s+)?purchase",
        r"(repurchase|repayment)\s+(at\s+the\s+option|upon\s+request)",
        r"no\s+(other\s+)?redemption",
    ],
    "mechanism": [
        r"redeem(ed)?\s+(all\s+or\s+(a\s+)?part|in\s+whole\s+or\s+in\s+part)",
        r"at\s+a\s+redemption\s+price",
        r"tax\s+redemption",
    ],
    "terms": [
        r"(call|make[\s-]?whole)\s+(premium|amount|price)",
        r"redemption\s+date",
        r"notice\s+of\s+redemption",
    ],
}

INDEBTEDNESS_DEFINITION_CUES: dict[str, list[str]] = {
    "heading": [
        r"(definition|interpretation)\s+of\s+indebtedness",
        # Tightened: bare "external debt" / "public debt" matched country debt
        # statistics sections (748 false positives in Round 2). Now requires
        # "definition" or "means" context, or the specific compound term.
        r"(external|public)\s+(indebtedness|debt)\s+(definition|means)",
        r"(relevant|financial)\s+indebtedness",
        r"certain\s+definitions",
    ],
    "definition": [
        r"indebtedness\s+means",
        r"(external|public)\s+(indebtedness|debt)\s+(means|shall\s+mean)",
    ],
    "scope": [
        r"(obligation|liability)\s+for\s+(borrowed\s+money|the\s+payment)",
        r"(guarantee|guaranty|indemnity)\s+of\s+(any\s+)?indebtedness",
        r"(bonds?|notes?|debentures?|loan\s+stock)",
    ],
}

# ── Round 3 families (Modes 1-3) ──────────────────────────────────────

AMENDMENT_WAIVER_CUES: dict[str, list[str]] = {
    "heading": [
        r"amendment\s+and\s+waiver",
        r"modification\s+and\s+waiver",
        r"amendments?\s+to\s+(the\s+)?(conditions|terms)",
        r"waiver\s+and\s+amendment",
    ],
    "mechanism": [
        r"(amend|modify|supplement|waive)\s+(any|all|the)\s+(provisions?|conditions?|terms?)",
        r"(written\s+)?consent\s+of\s+(the\s+)?holders?\s+of",
        r"without\s+the\s+consent\s+of\s+(any\s+)?holder",
    ],
    "threshold": [
        r"\d+%\s+of\s+the\s+(aggregate|outstanding)\s+principal",
        r"extraordinary\s+resolution",
        r"(unanimous|majority)\s+consent",
    ],
}

CONDITIONS_PRECEDENT_CUES: dict[str, list[str]] = {
    "heading": [
        r"conditions?\s+precedent",
        r"conditions?\s+to\s+(effectiveness|disbursement|drawdown|closing)",
        r"conditions?\s+for\s+(effectiveness|disbursement|drawdown)",
    ],
    "condition": [
        r"(shall|will)\s+not\s+(be\s+)?obligat?ed\s+to\s+(make|disburse|fund)",
        r"condition\s+precedent\s+to\s+(each|the|any)",
        r"(effectiveness|availability)\s+of\s+(the\s+)?(loan|facility|credit)",
    ],
    "requirement": [
        r"(legal\s+opinion|certificate|evidence)\s+(satisfactory|acceptable)\s+to",
        r"no\s+(event\s+of\s+)?default\s+(shall\s+have\s+)?occurred",
        r"representations?\s+and\s+warranties?\s+(are|shall\s+be)\s+true",
    ],
}

PAYMENT_MECHANICS_CUES: dict[str, list[str]] = {
    "heading": [
        r"payments?\s+(of\s+)?(principal|interest)",
        r"method\s+of\s+payment",
        r"payments?\s+(and\s+)?calculations?",
        r"payments?\s+on\s+the\s+(notes|bonds|securities)",
    ],
    "mechanism": [
        r"(principal|interest)\s+(shall|will)\s+be\s+(payable|paid)\s+(on|at|in)",
        r"payments?\s+(shall|will)\s+be\s+made\s+(in|by|through)",
        r"(paying|fiscal)\s+agent",
    ],
    "timing": [
        r"(interest|coupon)\s+payment\s+date",
        r"(maturity|redemption)\s+date",
        r"(business|banking)\s+day\s+convention",
    ],
}

TRUSTEE_DUTIES_CUES: dict[str, list[str]] = {
    "heading": [
        r"(duties|responsibilities|role)\s+of\s+(the\s+)?trustee",
        r"trustee\s+(duties|responsibilities|obligations)",
        r"the\s+trustee",
    ],
    "duty": [
        r"trustee\s+(shall|will|may)\s+(not\s+)?(be\s+)?(liable|responsible|obligat?ed)",
        r"(indemnif|compensat)(y|ied|ion)\s+(the\s+)?trustee",
        r"trustee\s+(shall|will)\s+(act|exercise|perform)",
    ],
    "limitation": [
        r"trustee\s+(shall\s+)?not\s+be\s+(required|bound|obligat?ed)\s+to",
        r"(no|without)\s+(liability|responsibility)\s+on\s+the\s+part\s+of\s+(the\s+)?trustee",
        r"(reasonable|due)\s+(care|diligence)",
    ],
}

DISBURSEMENT_CUES: dict[str, list[str]] = {
    "heading": [
        r"disbursement",
        r"drawdown",
        r"(loan|credit)\s+disbursement",
        r"availability\s+of\s+(the\s+)?(loan|facility|credit)",
    ],
    "mechanism": [
        r"(disburse|draw\s*down|withdraw)\s+(the\s+)?(loan|proceeds|funds)",
        r"(disbursement|drawdown|withdrawal)\s+(request|application|notice)",
        r"(special|designated)\s+account",
    ],
    "condition": [
        r"(disbursement|drawdown)\s+(shall|will)\s+be\s+(made|available)",
        r"(proceeds|funds)\s+(shall|will)\s+be\s+(deposited|credited|transferred)",
        r"(tranche|instalment|installment)",
    ],
}

COMMITMENT_CUES: dict[str, list[str]] = {
    "heading": [
        r"commitment\s+of\s+the\s+(bank|lender|issuer)",
        r"the\s+commitment",
        r"commitment\s+to\s+(lend|provide|make\s+available)",
    ],
    "obligation": [
        r"(agrees|commits|undertakes)\s+to\s+(lend|make\s+available|provide)",
        r"commitment\s+(amount|sum|total)",
        r"(aggregate|total)\s+commitment",
    ],
    "terms": [
        r"commitment\s+(fee|period|termination)",
        r"(reduce|cancel|terminate)\s+(the\s+)?commitment",
        r"(unutilized|undrawn|available)\s+(commitment|amount|portion)",
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
    # Round 0
    "collective_action": CAC_CUES,
    "pari_passu": PARI_PASSU_CUES,
    # Round 1
    "governing_law": GOVERNING_LAW_CUES,
    "sovereign_immunity": SOVEREIGN_IMMUNITY_CUES,
    "negative_pledge": NEGATIVE_PLEDGE_CUES,
    "events_of_default": EVENTS_OF_DEFAULT_CUES,
    # Round 2
    "acceleration": ACCELERATION_CUES,
    "dispute_resolution": DISPUTE_RESOLUTION_CUES,
    "additional_amounts": ADDITIONAL_AMOUNTS_CUES,
    "redemption": REDEMPTION_CUES,
    "indebtedness_definition": INDEBTEDNESS_DEFINITION_CUES,
    # Round 3
    "amendment_waiver": AMENDMENT_WAIVER_CUES,
    "conditions_precedent": CONDITIONS_PRECEDENT_CUES,
    "payment_mechanics": PAYMENT_MECHANICS_CUES,
    "trustee_duties": TRUSTEE_DUTIES_CUES,
    "disbursement": DISBURSEMENT_CUES,
    "commitment": COMMITMENT_CUES,
}


def get_cue_families(clause_family: str) -> dict[str, list[str]] | None:
    """Return cue families for a clause type, or None if unknown."""
    return _CLAUSE_CUES.get(clause_family)


def get_all_families() -> list[str]:
    """Return all registered clause family names."""
    return sorted(_CLAUSE_CUES.keys())
