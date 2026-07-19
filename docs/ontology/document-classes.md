# Document classes and issuer canonicalization (ontology pilots 1 and 2)

**Version:** v0.2 (2026-07-19; revised after the external reviewer pass).
**Status:** proposed, pending Teal sign-off.
**Tables:** `src/corpus/reference/data/` (doc_classes.csv, doc_class_map.csv,
doc_class_title_rules.csv, doc_class_overrides.csv, issuer_canonical.csv,
issuer_entities.csv, issuer_entity_members.csv).
**Method:** open coding over every raw source code (43 codes across EDGAR,
LuxSE, NSM, LSE, PDIP) plus the 664-row PDIP null bucket and title patterns,
all drawn from the published snapshot parquet (generated 2026-07-16, 9,795
documents); then axial coding of what was actually observed into classes.
Nothing was designed top-down. Where a document does not fit, it is flagged
for review, never forced.

## The class taxonomy

The machine-readable registry is `doc_classes.csv`; this table is its
human-readable mirror plus the projected distribution.

| Class | Definition | Typical members | Docs |
|---|---|---|---|
| `prospectus` | Standalone disclosure document for a specific offer or listing; readable on its own | Prospectuses, offering circulars and memoranda, listing particulars, drawdown and unitary prospectuses | 1,029 |
| `base_prospectus` | Programme-level disclosure under which individual tranches are issued later; no tranche pricing | Base prospectuses, base offering circulars (EMTN/GMTN programmes) | 234 |
| `supplement` | Amends or updates an existing prospectus or base prospectus | Supplementary prospectuses, prospectus supplements, most SEC Rule 424(b)(2)/(3)/(5) filings | 2,060 |
| `final_terms` | Completes a base prospectus for one tranche; carries the tranche economics | Final terms, pricing supplements (including pricing-titled 424(b) filings) | 1,118 |
| `free_writing_prospectus` | SEC Rule 433 offering communications, mostly final pricing term sheets | EDGAR FWP filings | 1,613 |
| `annual_report` | Periodic or standing issuer disclosure not tied to a specific offer | Form 18-K and amendments, annual and interim financial reports, information statements | 634 |
| `notice` | Exchange or regulatory announcements about issuers or instruments | Admission applications, results announcements, press releases, errata, tender and exchange offer announcements | 1,562 |
| `loan_documentation` | Loan contracts and related official-lender documentation | Loan/credit/facility/financing agreements, lender general conditions, guarantees | 499 |
| `bond_contract` | Contracts of bond issuance and administration | Indentures, fiscal agency agreements, trust deeds, global note certificates, underwriting and subscription agreements | 50 |
| `restructuring_document` | Documents proposing, executing, or contracting liability management | Exchange offer and invitation memoranda, restructuring agreements, dealer management agreements | 3 |
| `other` | Reviewed and does not fit any class | Mixed transparency filings (LuxSE XOA1) | 19 |
| (unclassified) | Nothing matched; review queue | 947 opaque LuxSE D318 titles, 25 ambiguous PDIP rows, 2 registration documents | 974 |

Counts are the projected distribution over snapshot 2026-07-16 under the
consumer contract below (override, then title rule, then code fallback).

Two deliberate honesty notes. First, LuxSE D318 ("document incorporated by
reference") describes a filing relationship, not a document class; title
rules classify the members whose titles reveal what they are (18-K filings,
base prospectuses, supplements, press material), and the 947 title-opaque
rows stay unclassified pending text sampling rather than inheriting a class
from their code. Second, `restructuring_document` is deliberately sparse: it
exists because real members exist and because the planned
restructuring-documents hand-collect wave (roadmap section 7) needs a home.

Registration documents (LuxSE D005, NSM FCA14, 2 documents) are issuer-level
disclosure constituents under the EU Prospectus Regulation (Articles 6 and
10), not base prospectuses and not standalone prospectuses. They stay
unclassified with a review note naming `registration_document` as the future
class; minting a 2-member class fails the governance bar below. [TEAL GATE]

## Edge rules

1. **"Publication of X" headlines (NSM) classify as X.** The filing wraps
   the document it announces.
2. **Drawdown prospectuses and drawdown offering circulars are
   `prospectus`, not `final_terms`.** They are complete disclosure documents
   even though they sit under a programme.
3. **An erratum is `notice`** unless it formally supplements a prospectus,
   in which case an override moves it to `supplement`.
4. **Announcements OF an exchange offer are `notice`; the offer document
   itself, and the contracts executing the transaction (dealer management
   agreements), are `restructuring_document`.**
5. **Form 18-K exhibits and amendments follow the 18-K to `annual_report`.**
6. **Results presentations and investor slides are `notice`; annual and
   interim financial reports are `annual_report`.**
7. **EDGAR 424(b) codes are filing triggers, not document forms.**
   424B1/424B4 map to `prospectus`; 424B2/424B3/424B5 fall back to
   `supplement`, with title rules routing pricing-supplement titles to
   `final_terms` and "prospectus only" titles to `prospectus`. [TEAL GATE]
8. **Never force.** A document with no code mapping, no title-rule match,
   and no override stays unclassified and enters the review queue. Typos in
   source titles ("Indeture", "Princing Supplement") are why this rule
   exists.
9. **Precedence:** per-document overrides beat title rules; title rules beat
   the code fallback. Title rules fire only for documents whose
   (source, code) mechanism includes title rules, and only rules whose
   `applies_to_source` matches the document's source.

## The consumer contract (normative)

Every consumer MUST classify identically. The reference implementation:

```
raw_code   = coalesce(documents.doc_type, '<NULL>')      # join sentinel
map_row    = doc_class_map WHERE source = documents.source
                             AND source_code = raw_code   # exactly one row
1. if documents.storage_key in doc_class_overrides: use its doc_class.
2. elif map_row.mechanism includes 'title_rules':
     first rule in doc_class_title_rules (ascending rule_order) where
     applies_to_source = documents.source AND the pattern matches
     coalesce(documents.title, '') case-insensitively (Python re syntax):
     use its doc_class.
3. if still unresolved: use map_row.doc_class if non-empty
   (mechanism 'title_rules_only' and empty doc_class mean: no fallback).
4. otherwise the document is UNCLASSIFIED: doc_class NULL, review queue.
```

Contract details consumers MUST honor:

- **Status gating:** consumers read rows with `status=approved` only. Every
  row ships as `proposed`; Teal's sign-off PR flips statuses, which is the
  activation switch. A consumer running against all-proposed tables
  classifies nothing, by design.
- **Join key:** `documents.doc_type` joins `doc_class_map.source_code` via
  the `coalesce(doc_type, '<NULL>')` expression above; `'<NULL>'` is the
  sentinel for SQL NULL.
- **Review propagation:** `needs_review` is a real column on
  doc_class_map.csv and issuer_entities.csv. UI consumers MUST NOT hide it;
  a review-flagged classification renders with a review marker or renders
  the raw code only.
- **Class names** come from doc_classes.csv; a doc_class value absent from
  the registry is a validation error, as is a registry rename without a
  migration PR touching every consumer.

## Mapping governance

**How a new source code gets classified.** (1) The pipeline surfaces any
(source, code) pair absent from doc_class_map.csv as an unmapped-code alarm
in the refresh QA output; unmapped documents are NEVER silently classified.
(2) Whoever triages pulls a sample of titles (and 2 or 3 documents) for the
new code: open coding, same as this pilot. (3) A PR adds the row with
`observed_meaning`, evidence in `notes`, `status=proposed`. (4) Teal
approves the class decision (domain gate) and the row flips to `approved`
in that PR.

**How a new class gets minted.** A class needs either roughly 20 observed
members or a named consumer (a filter, feed, or collection that needs it),
plus Teal sign-off. Renaming or merging classes is a schema change for
every consumer and takes a deliberate migration PR.

**Review queue metrics (report both):** documents with no class (974 on
this snapshot), and documents sitting under review-flagged mappings (2,658,
dominated by D318's 1,853; they may carry a class from a title rule but the
mapping itself is flagged). Reviews resolve into overrides or new title
rules, never by editing raw data.

**Evidence provenance.** LuxSE D-code and NSM category-code meanings are
inferred from observed titles (per-row in `observed_meaning`), not from
official source documentation.

## Issuer canonicalization

Three tables. Raw strings are preserved exactly (including trailing spaces
and typos such as "GOVERNMENT OF JAMICA"); canonicalization is a mapping,
never a rewrite of source data.

- **issuer_canonical.csv**: one row per raw `issuer_name` string (268).
  Maps to `canonical_issuer_id`.
- **issuer_entities.csv**: one row per canonical entity (146):
  `canonical_display_name`, `issuer_type`, `country_code`, `lei`,
  `lei_status`, `lei_source`, `needs_review`, `notes`.
- **issuer_entity_members.csv**: constituents of `multi_issuer` composites
  (13 composites), with `member_entity_id` where the member also exists as
  a standalone entity.

**Entity rules.**

1. Ministry-of-finance, treasury, and "acting through" variants collapse
   into the sovereign state (State of Israel Ministry of Finance is the
   State of Israel). South Africa's National Treasury rows are mapped to
   the Republic on the same logic. [TEAL GATE]
2. Distinct legal entities NEVER merge with the state: central banks
   (Central Bank of Iceland), sub-sovereigns (Republika Srpska, Federation
   of Bosnia and Herzegovina, Emirate of Abu Dhabi, Hong Kong SAR), issuance
   SPVs (Oman Sovereign Sukuk S.A.O.C.), state-owned entities (Banco de
   Reservas, Kazakhstan Temir Zholy Finance). Hong Kong keeps its own
   country code analytically but is typed `sub_sovereign`, not a sovereign
   state. [TEAL GATE]
3. Joint filings by multiple issuers are `multi_issuer` entities whose
   identity is the ORDER-INDEPENDENT member set (punctuation and ordering
   variants of the same set unify). They carry no single country_code; the
   members bridge carries the constituents. A comma inside one legal name
   (UniCredit Bank Czech Republic and Slovakia, a.s.) is NOT a composite;
   known cases are pinned by override, and member parsing stays
   review-flagged.
4. Sovereign display names use the official English legal form as it
   appears on deal covers (Republic of Ghana, State of the Netherlands,
   Republic of Turkiye with the u-umlaut). Corporate display names keep the
   raw legal name unmodified; cosmetic normalization is deferred rather
   than risk corrupting legal capitalization. [TEAL GATE]
5. The 215 PDIP rows with no issuer_name stay null and are a review
   backlog, not a table row.

**LEI sourcing.** Only two sources are accepted: (a) GLEIF API lookups
against entity category RESIDENT_GOVERNMENT_ENTITY filtered to the entity's
country, taken only on an exact normalized-name match to a known alias of
the state, where the alias set includes English legal forms plus
accent-folded Romance-language forms such as "Republica Argentina" (35
entities); (b) the LEIs researched during the NSM adapter build, recorded
in docs/nsm_api_reference.md (6 more; the 3 overlaps agreed with GLEIF,
zero conflicts). `lei_status` records the GLEIF registration status for
every LEI (a LAPSED registration remains a valid identifier; Jordan and
Kazakhstan are LAPSED today). Near-miss candidates (DRC's LEI registered to
its Ministry of Finance, Gabon's to a ministry, Costa Rica's to Ministerio
de Hacienda) are recorded in `lei_source` and review-flagged, not
auto-taken. Everything else is blank plus `pending`. No LEI is ever
guessed.

**Governance.** Same lifecycle as the class tables: propose by PR with
evidence, Teal approves, status flips. New raw spellings arriving with a
refresh surface as unmapped-issuer alarms (extends the existing
unmapped_issuers audit, GitHub issue #85).

## Relationship to prior art

- `src/corpus/extraction/document_classifier.py` (text-based three-axis
  classifier, self-labeled "best-effort, domain review needed"): its
  instrument_family/role/form distinctions fold into these classes; its
  text-pattern engine is the natural mechanism for sampling the 947
  title-opaque D318 documents and the PDIP review queue. The mapping tables
  here are the authoritative metadata layer.
- `src/corpus/reference/issuer_country_map.py` (issuer to country):
  unchanged and still the country authority; issuer_canonical.csv keys on
  the same raw strings and adds the entity layer.
- The roadmap memo (2026-07-17) sketched "order of 8 classes"; the observed
  data added `bond_contract` and split supplements from final terms, and
  the reviewer pass pushed D318 and the registration documents out of
  code-level classification. Differences are argued from the data and gated
  by Teal.
