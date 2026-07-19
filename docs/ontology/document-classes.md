# Document classes and issuer canonicalization (ontology pilots 1 and 2)

**Version:** v0.1 (2026-07-19). **Status:** proposed, pending Teal sign-off.
**Tables:** `src/corpus/reference/data/` (doc_class_map.csv,
doc_class_title_rules.csv, doc_class_overrides.csv, issuer_canonical.csv,
issuer_entities.csv).
**Method:** open coding over every raw source code (43 codes across EDGAR,
LuxSE, NSM, LSE, PDIP) plus the 664-row PDIP null bucket and title patterns,
all drawn from the published snapshot parquet (generated 2026-07-16, 9,795
documents); then axial coding of what was actually observed into classes.
Nothing was designed top-down. Where a document does not fit, it is flagged
for review, never forced.

## The class taxonomy

| Class | Definition | Typical members | Docs |
|---|---|---|---|
| `prospectus` | Standalone disclosure document for a specific offer or listing; readable on its own | Prospectuses, offering circulars and memoranda, listing particulars, drawdown and unitary prospectuses | 960 |
| `base_prospectus` | Programme-level disclosure under which individual tranches are issued later; no tranche pricing | Base prospectuses, base offering circulars (EMTN/GMTN programmes), registration documents (edge rule 3) | 218 |
| `supplement` | Amends or updates an existing prospectus or base prospectus | Supplementary prospectuses, prospectus supplements, SEC Rule 424(b)(2)/(3)/(5) filings | 2,001 |
| `final_terms` | Completes a base prospectus for one tranche; carries the tranche economics | Final terms, pricing supplements | 1,091 |
| `free_writing_prospectus` | SEC Rule 433 offering communications, mostly final pricing term sheets | EDGAR FWP filings | 1,613 |
| `annual_report` | Periodic or standing issuer disclosure not tied to a specific offer | Form 18-K and amendments, annual and interim financial reports, information statements | 1,869 |
| `notice` | Exchange or regulatory announcements about issuers or instruments | Admission applications, results announcements, press releases, errata, tender and exchange offer announcements | 1,447 |
| `loan_documentation` | Loan contracts and related official-lender documentation | Loan/credit/facility/financing agreements, lender general conditions, guarantees, bilateral financing agreements | 503 |
| `bond_contract` | Contractual machinery of a bond issue (the legal instruments, not the disclosure) | Indentures, fiscal agency agreements, trust deeds, global note certificates, underwriting agreements | 51 |
| `restructuring_document` | Documents proposing or effecting liability management | Exchange offer memoranda, invitation memoranda, restructuring agreements | 2 |
| `other` | Reviewed and does not fit any class | Mixed transparency filings (LuxSE XOA1), unresolved singletons | 19 |
| (unclassified) | No code mapping, title rule, or override matched; sits in the review queue | Ambiguous or typo-titled PDIP rows | 21 |

Counts are the projected distribution over snapshot 2026-07-16.
`restructuring_document` is deliberately sparse: it exists because two real
members exist and because the planned restructuring-documents hand-collect
wave (roadmap section 7) needs a home; it is not a speculative class.

## Edge rules

1. **"Publication of X" headlines (NSM) classify as X.** The filing wraps the
   document it announces.
2. **Drawdown prospectuses and drawdown offering circulars are `prospectus`,
   not `final_terms`.** They are complete disclosure documents even though
   they sit under a programme.
3. **Registration documents map to `base_prospectus`.** They are reusable
   issuer-level disclosure components (tripartite regime), not standalone
   deal documents. [TEAL GATE]
4. **An erratum is `notice`** unless it formally supplements a prospectus, in
   which case an override moves it to `supplement`.
5. **Announcements OF an exchange offer are `notice`; the offer document
   itself is `restructuring_document`.**
6. **Form 18-K exhibits and amendments follow the 18-K to `annual_report`.**
7. **Results presentations and investor slides are `notice`; annual and
   interim financial reports are `annual_report`.**
8. **EDGAR 424(b) family:** 424B1/424B4 map to `prospectus` (first-time
   prospectus after effectiveness); 424B2/424B3/424B5 map to `supplement`
   (dominant sovereign shelf practice). [TEAL GATE]
9. **Never force.** A document with no code mapping, no title-rule match, and
   no override stays unclassified and enters the review queue. Typos in
   source titles ("Indeture", "Princing Supplement") are why this rule
   exists.
10. **Precedence:** per-document overrides beat title rules; title rules beat
    the code map. Title rules currently apply to PDIP only (the one source
    whose codes are instrument labels, not document types).

## Mapping mechanism and governance

Three diffable CSVs under `src/corpus/reference/data/`, all carrying
`proposed_by`, `proposed_date`, `status` (`proposed` until Teal flips to
`approved` in a reviewed PR):

- **doc_class_map.csv**: one row per (source, source_code). Key columns:
  `doc_class`, `confidence` (high/medium/low), `mechanism` (`code`,
  `title_rules_then_code`, `title_rules_only`), `observed_meaning` (what the
  code was observed to contain; LuxSE D-codes and NSM category codes are
  inferred from titles, not from official source documentation), `notes`
  (REVIEW markers and known exceptions).
- **doc_class_title_rules.csv**: ordered regex rules, first match wins.
  v0.1 scope: PDIP.
- **doc_class_overrides.csv**: storage_key-level assignments with evidence,
  for documents whose code and title disagree.

**How a new source code gets classified.** (1) The pipeline surfaces any
(source, code) pair absent from doc_class_map.csv as an unmapped-code alarm
in the refresh QA output; unmapped documents are NEVER silently classified.
(2) Whoever triages pulls a sample of titles (and 2 or 3 documents) for the
new code: open coding, same as this pilot. (3) A PR adds the row with
`observed_meaning`, evidence in `notes`, `status=proposed`. (4) Teal approves
the class decision (domain gate) and the row flips to `approved` in that PR.

**How a new class gets minted.** A class needs either roughly 20 observed
members or a named consumer (a filter, feed, or collection that needs it),
plus Teal sign-off. Renaming or merging classes is a schema change for every
consumer and takes a deliberate migration PR.

**Review queue.** Unclassified documents plus every row whose notes carry
REVIEW. Reviews resolve into overrides or new title rules, never by editing
the raw data.

## Issuer canonicalization

Two tables. Raw strings are preserved exactly (including trailing spaces and
typos such as "GOVERNMENT OF JAMICA"); canonicalization is a mapping, never a
rewrite of source data.

- **issuer_canonical.csv**: one row per raw `issuer_name` string (268 rows).
  Maps to `canonical_issuer_id`.
- **issuer_entities.csv**: one row per canonical entity (148 rows):
  `canonical_display_name`, `issuer_type`, `country_code`, `lei`,
  `lei_source`, `needs_review`, `notes`.

**Entity rules.**

1. Ministry-of-finance, treasury, and "acting through" variants collapse
   into the sovereign state (State of Israel Ministry of Finance is the
   State of Israel). South Africa's National Treasury rows are mapped to the
   Republic on the same logic. [TEAL GATE]
2. Distinct legal entities NEVER merge with the state: central banks
   (Central Bank of Iceland), sub-sovereigns (Republika Srpska, Federation
   of Bosnia and Herzegovina, Emirate of Abu Dhabi), issuance SPVs (Oman
   Sovereign Sukuk S.A.O.C.), state-owned entities (Banco de Reservas,
   Kazakhstan Temir Zholy Finance).
3. LuxSE joint filings by multiple issuers stay `multi_issuer` composites;
   they are not collapsed onto one issuer.
4. Display names use the official English legal form as it appears on deal
   covers (Republic of Ghana, State of the Netherlands, Republic of
   Turkiye with the u-umlaut). Raw variants remain queryable. [TEAL GATE]
5. The 215 PDIP rows with no issuer_name stay null and are a review backlog,
   not a table row.

**LEI sourcing.** Only two sources are accepted: (a) GLEIF API lookups
against entity category RESIDENT_GOVERNMENT_ENTITY filtered to the entity's
country, taken only on an exact normalized-name match to a known alias of
the state (35 entities); (b) the LEIs researched during the NSM adapter
build, recorded in docs/nsm_api_reference.md (6 more entities; 3 overlaps
agreed with GLEIF, zero conflicts). Near-miss candidates (for example DRC's
LEI registered to its Ministry of Finance, Argentina's to "Republica
Argentina") are recorded in `lei_source` and review-flagged, not auto-taken.
A LAPSED registration status does not invalidate an LEI as an identifier;
status is recorded alongside. Everything else is blank plus `pending`. No
LEI is ever guessed.

**Governance.** Same lifecycle as the class tables: propose by PR with
evidence, Teal approves, status flips. New raw spellings arriving with a
refresh surface as unmapped-issuer alarms (extends the existing
unmapped_issuers audit, GitHub issue #85).

## Relationship to prior art

- `src/corpus/extraction/document_classifier.py` (text-based three-axis
  classifier, self-labeled "best-effort, domain review needed"): its
  instrument_family/role/form distinctions fold into these classes; its
  text-pattern engine is the natural backfill mechanism for the PDIP review
  queue later. The mapping tables here are the authoritative metadata layer.
- `src/corpus/reference/issuer_country_map.py` (issuer to country):
  unchanged and still the country authority; issuer_canonical.csv keys on
  the same raw strings and adds the entity layer.
- The roadmap memo (2026-07-17) sketched "order of 8 classes"; the observed
  data added `bond_contract` (51 real members) and split supplements from
  final terms. Differences are argued from the data and gated by Teal.
