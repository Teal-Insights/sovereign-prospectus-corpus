# Spec-lite: ontology pilots 1 and 2 (document classes, issuer canonicalization)

**Date:** 2026-07-19 (v0.2, revised same day after the external reviewer
pass). **Mode:** spec-lite per the consolidation roadmap section 9 (one
architect session, one external reviewer pass, Teal domain gate on every
class decision; no full council). **Downstream:** implementation rides Lane
A Stage 2 branches; this session ships reference tables and definitions
only. No UI code.

**Attribution:** the architect session proposed every row
(`proposed_by=fable-architect-session`); Kweku owns table maintenance and
consumer implementation going forward; Teal approves (the status flip is
the activation switch).

## What shipped

| Deliverable | Where |
|---|---|
| Class taxonomy, definitions, edge rules, consumer contract | `docs/ontology/document-classes.md` |
| Class registry (machine-readable) | `src/corpus/reference/data/doc_classes.csv` (11 classes) |
| Source-code-to-class mapping | `doc_class_map.csv` (44 rows, needs_review column), `doc_class_title_rules.csv` (27 per-source rules), `doc_class_overrides.csv` (4 rows) |
| Governance note (new code, new class, review queue) | `docs/ontology/document-classes.md` |
| Issuer canonicalization | `issuer_canonical.csv` (268 raw names), `issuer_entities.csv` (146 entities, 41 LEIs with lei_status), `issuer_entity_members.csv` (13 composites) |
| Consumer list | this document, below |

## Method trail (locked: open coding, then axial coding)

1. Pulled the published snapshot parquet (data host, generation 2026-07-16,
   9,795 documents; matches the roadmap's numbers: 43 raw codes, 664-row
   PDIP null bucket, 268 issuer names).
2. Open coding: sampled titles for every (source, code) bucket; broke the
   PDIP null bucket down by title pattern (roughly 63 percent loan
   documentation); probed the heterogeneous codes (NSM FCA07/MSCL/LIS,
   LuxSE D455/D318/D290/XOA1) with per-title frequency counts.
3. Axial coding: grouped observed document functions into 10 substantive
   classes plus `other` and an explicit unclassified state. Two classes
   were forced by the data, not the plan: `bond_contract` (indentures,
   underwriting agreements, global note certificates in the PDIP tail) and
   the supplement/final-terms split (high-volume and legally distinct:
   amendment vs tranche completion).
4. Classification mechanics: code map plus per-source ordered title rules
   (EDGAR pricing reroutes, LuxSE D010/D290/D318 title routing, PDIP full
   rule set) plus storage-key overrides; everything else unclassified plus
   review. Projected coverage on this snapshot: 8,821 classified, 974
   unclassified (947 title-opaque LuxSE D318, 25 ambiguous PDIP, 2
   registration documents).
5. Issuer pass: 268 raw strings resolved to 146 entities under explicit
   entity rules; multi-issuer composites keyed by order-independent member
   set with a members bridge. LEIs only from GLEIF exact-alias matches (35)
   and the NSM-researched seeds (6), zero conflicts, registration status
   recorded per LEI; 42 entities carry review flags with candidate evidence
   inline.

Evidence provenance: LuxSE D-code and NSM category-code meanings are
inferred from observed titles (recorded per row in `observed_meaning`), not
from official source documentation.

## Consumers of the vocabulary

1. **Browse class filter** (Lane A): filter on `doc_class` instead of 43
   raw codes plus a null bucket.
2. **Doc-page provenance line**: "Class: Final terms. Source code: D090
   (LuxSE)." Raw code stays visible; the class never replaces provenance.
3. **Dedup near-duplicate signal** (roadmap section 7): the soft key
   (canonical issuer, doc_class, publication_date) routed to review;
   SHA-256 remains the only hard key.
4. **Feed routing** (Lane B): per-class feeds; pricing supplements stop
   drowning prospectuses; the restructuring collection gets a class.
5. **Docs data dictionary** (Lane C): `docs/ontology/document-classes.md`
   is the page the data dictionary links.
6. Secondary: refresh QA alarms (unmapped code, unmapped issuer; extends
   issue #85) and the text classifier prior art
   (`document_classifier.py`), the sampling mechanism for the 947
   title-opaque D318 documents.

## Decisions for Teal (the domain gate)

**RULING (Teal, 2026-07-19):** decisions 1 through 9 approved as proposed;
decision 10 resolved to `annual_report`. All table rows flipped to
`status=approved` in the sign-off commit on PR #128.

1. **Merge prospectus and offering circular/memorandum into one class.**
   Same function, regime difference stays in the raw code. (Reviewer
   endorsed.)
2. **Split supplement from final terms.** Legally distinct, high-volume,
   different feed/dedup semantics. (Reviewer endorsed.)
3. **Mint `bond_contract`** (50 members, data-driven) vs fold into
   `other`.
4. **Mint `restructuring_document` now** (3 members incl. dealer
   management agreements, plus the planned hand-collect wave) vs reserve.
5. **Registration documents stay unclassified** (2 docs) with
   `registration_document` named as the future class; minting a 2-member
   class fails the governance bar. (Replaces v0.1's base_prospectus
   placement, which the reviewer showed is legally wrong under EU PR
   Articles 6/10.)
6. **EDGAR 424(b) treatment** (edge rule 7): B1/B4 prospectus; B2/B3/B5
   fall back to supplement with title rules routing pricing titles to
   final_terms and "prospectus only" to prospectus.
7. **LuxSE D318 is not code-classifiable.** Title rules route what titles
   reveal; 947 opaque rows stay unclassified pending text sampling. This
   is the largest honesty cost in the projection (annual_report drops from
   a v0.1 projection of 1,869 to 634) and the correct one.
8. **Issuer display convention**: official English legal form for
   sovereigns; raw legal names preserved for corporates (no cosmetic
   recapitalization); National Treasury of South Africa collapses into the
   Republic; Hong Kong SAR typed sub_sovereign under its own country code.
9. **LEI policy**: exact-alias GLEIF matches auto-proposed (alias set
   includes accent-folded Romance forms); ministry-registered near-misses
   (DRC, Gabon, Costa Rica) held for review; LAPSED registrations used as
   identifiers with `lei_status` recorded (Jordan, Kazakhstan LAPSED).
10. **Class name `annual_report`** for the periodic-disclosure class;
    alternative name: `periodic_disclosure`.

## Non-goals (this session)

No UI code. No pipeline wiring (Lane A Stage 2 consumes the tables). No
within-document ontology (parked until the clause track). No
reclassification of the corpus in the database; tables are reference data
until a consumer lands and statuses flip. No em-dashes.

## Session notes

- mgrep was unavailable (expired login, known pending item); filesystem and
  SQL search were used instead. No effect on deliverables.
- The snapshot parquet was fetched from the public data host with curl
  because the host serves pre-compressed content DuckDB httpfs does not
  decode; noted for anyone repeating the queries.

## Reviewer dispositions (Codex gpt-5.6-sol, read-only, xhigh; verdict on v0.1: NOT SOUND)

Every data claim was re-verified against the snapshot before any change.
All twelve findings and their dispositions; v0.2 is the post-disposition
revision.

| # | Finding (severity) | Disposition |
|---|---|---|
| 1 | LuxSE D318 code-only annual_report misclassifies; D010 has 58 supplement titles, not 1 (CRITICAL) | Accepted, verified (947 opaque titles counted). D318 fallback removed; LuxSE title rules added; D010/D290 now title_rules_then_code; opaque rows unclassified |
| 2 | Registration document is not a base prospectus (EU PR Arts. 6/10) (IMPORTANT) | Accepted via the reviewer's second option: D005/FCA14 unclassified + review, `registration_document` named as future class. Not minting a 2-member class (would break our own governance bar) |
| 3 | 424(b) codes are filing triggers; B2/B5 not homogeneous supplements (IMPORTANT) | Accepted via the title-split option: EDGAR pricing titles route to final_terms, "prospectus only" to prospectus. New prospectus_supplement class rejected: cross-regime class unity is the point of the vocabulary |
| 4 | PDIP rule-order collisions; bare "agreement between" overbroad; dealer management is liability management (IMPORTANT) | Accepted, all verified (2+1+1 collision docs counted). Supplement-form rules ordered first; "agreement between" dropped (falls to review); dealer management agreements routed to restructuring_document |
| 5 | Fedtn-of-BiH raw mapped to the state; UniCredit CZ/SK is one bank, not a composite; HKG sovereign_state overstates legal status (IMPORTANT) | Accepted, all three verified and fixed (overrides + sub_sovereign type with TEAL GATE note) |
| 6 | Composites split by punctuation/ordering; no member bridge; arbitrary country on composites (IMPORTANT) | Accepted in substance: identity is now the order-independent normalized member set (Belgacom, Bank of Cyprus, Fresenius variants unified; 16 to 13 composites); issuer_entity_members.csv added; country blanked on composites. Fully automated member parsing rejected (legal names contain commas, the exact cause of the UniCredit bug); parsing stays review-flagged |
| 7 | No executable consumer contract (status gating, join sentinel, regex dialect, fallback semantics, review column, class registry) (IMPORTANT) | Accepted in full: normative contract section added; needs_review now a real column; doc_classes.csv registry added; pdip NULL row fallback removed (was silently converting review docs to `other`) |
| 8 | Review-queue metric understated (21 vs 70 code-level docs) (IMPORTANT) | Accepted: both metrics now defined and reported (974 unclassified docs; 2,658 docs under review-flagged mappings) |
| 9 | Argentina narrative contradicted the table; LEI status not structural (IMPORTANT) | Accepted: narrative was stale after the Romance-alias addition; doc now states the alias policy and uses DRC/Gabon/Costa Rica as held examples. lei_status column added; all 9 seed LEIs' statuses fetched from GLEIF |
| 10 | Projected counts ignored overrides (MINOR) | Accepted: projection now computed by the reference implementation of the contract (override > rule > code) |
| 11 | Titlecasing damaged legal capitalization (MINOR) | Accepted in effect, different remedy: titlecasing removed, raw legal names preserved; cosmetic normalization deferred rather than hand-fabricating legal caps |
| 12 | proposed_by attribution unclear (MINOR) | Accepted: attribution paragraph added above |

Reviewer items that came back sound (per the reviewer, no action): the
supplement/final-terms legal distinction, the prospectus/OC merge,
drawdown-to-prospectus, the notice-vs-offer-document rule, raw-name
preservation, entity distinctness for central banks / Abu Dhabi / Srpska /
Oman SPV, LEI checksum validity and uniqueness, storage_key as override
key, and all row-count reconciliations.
