# Spec-lite: ontology pilots 1 and 2 (document classes, issuer canonicalization)

**Date:** 2026-07-19. **Mode:** spec-lite per the consolidation roadmap
section 9 (one architect session, one external reviewer pass, Teal domain
gate on every class decision; no full council). **Builder:** Kweku.
**Downstream:** implementation rides Lane A Stage 2 branches; this session
ships reference tables and definitions only. No UI code.

## What shipped

| Deliverable | Where |
|---|---|
| Class taxonomy, definitions, edge rules (one page) | `docs/ontology/document-classes.md` |
| Source-code-to-class mapping (versioned, diffable) | `src/corpus/reference/data/doc_class_map.csv` (44 rows), `doc_class_title_rules.csv` (19 rules), `doc_class_overrides.csv` (4 rows) |
| Governance note (new code, new class, review queue) | `docs/ontology/document-classes.md`, "Mapping mechanism and governance" |
| Issuer canonicalization | `src/corpus/reference/data/issuer_canonical.csv` (268 raw names), `issuer_entities.csv` (148 entities, 41 LEIs) |
| Consumer list | this document, below |

## Method trail (locked: open coding, then axial coding)

1. Pulled the published snapshot parquet (data host, generation 2026-07-16,
   9,795 documents; matches the roadmap's numbers: 43 raw codes, 664-row
   PDIP null bucket, 268 issuer names).
2. Open coding: sampled titles for every (source, code) bucket; broke the
   PDIP null bucket down by title pattern (roughly 63 percent loan
   documentation); probed the heterogeneous codes (NSM FCA07/MSCL/LIS,
   LuxSE D455/D318/D290/XOA1) with per-title frequency counts.
3. Axial coding: grouped observed document functions into 10 active classes
   plus `other` and an explicit unclassified state. Two classes were forced
   by the data, not the plan: `bond_contract` (indentures, underwriting
   agreements, global note certificates kept surfacing in the PDIP tail, 51
   members) and the supplement/final-terms split (both are high-volume and
   legally distinct: amendment vs tranche completion).
4. Classification mechanics: code map for the four coded sources; ordered
   title rules for PDIP (whose codes are instrument labels, not document
   types); storage-key overrides where code and title disagree; everything
   else unclassified plus review. Projected coverage: 9,774 of 9,795 (99.8
   percent), 21 in review.
5. Issuer pass: 268 raw strings resolved to 148 entities under explicit
   entity rules (collapse ministry variants into the state; never merge
   central banks, sub-sovereigns, SPVs, state-owned entities, or
   multi-issuer composites). LEIs only from GLEIF exact-alias matches (35)
   and the NSM-researched seeds (6), zero conflicts between the two; 45
   entities carry review flags with candidate evidence inline.

Evidence provenance note: LuxSE D-code and NSM category-code meanings are
inferred from observed titles (recorded per row in `observed_meaning`), not
from official source documentation. The external reviewer and Teal should
treat them as observations, which is what the column says.

## Consumers of the vocabulary

1. **Browse class filter** (Lane A): filter on `doc_class` instead of 43 raw
   codes plus a null bucket.
2. **Doc-page provenance line**: "Class: Final terms. Source code: D090
   (LuxSE)." Raw code stays visible; the class never replaces provenance.
3. **Dedup near-duplicate signal** (roadmap section 7): the soft key
   (canonical issuer, doc_class, publication_date) routed to review; SHA-256
   remains the only hard key.
4. **Feed routing** (Lane B): per-class feeds; pricing supplements stop
   drowning prospectuses; the restructuring collection gets a class, not a
   hand-curated list.
5. **Docs data dictionary** (Lane C): `docs/ontology/document-classes.md` is
   the page the data dictionary links.
6. Secondary: refresh QA alarms (unmapped code, unmapped issuer; extends
   issue #85) and the text classifier prior art
   (`document_classifier.py`), which becomes a backfill mechanism for the
   review queue.

## Decisions for Teal (the domain gate)

1. **Merge prospectus and offering circular/memorandum into one class.** The
   roadmap sketch listed them separately. Argument: same function
   (standalone deal disclosure); the regulatory-regime difference stays
   visible in the raw code. Alternative: split them.
2. **Split supplement from final terms.** The roadmap sketch merged them.
   Argument: legally distinct (amendment vs tranche completion), both
   high-volume (2,001 vs 1,091), and feeds/dedup treat them differently.
3. **Mint `bond_contract`** (51 members, data-driven) vs fold into `other`.
4. **Mint `restructuring_document` now** (2 members, plus the planned
   hand-collect wave) vs reserve the name.
5. **Registration documents to `base_prospectus`** (edge rule 3).
6. **EDGAR 424(b) mapping** (edge rule 8): B1/B4 prospectus, B2/B3/B5
   supplement.
7. **LuxSE D318 to `annual_report`** at medium confidence: 1,853 documents,
   observed dominantly 18-K filings and annual reports, but 444 titles are
   the opaque "Document incorpore par reference". Accept with later title
   rules, or demand a sampling pass first.
8. **Issuer display convention**: official English legal form (Republic of
   Turkiye with u-umlaut, State of the Netherlands, Oriental Republic of
   Uruguay); National Treasury of South Africa collapses into the Republic;
   Hong Kong SAR treated as a government issuer under its own country code.
9. **LEI policy**: exact-alias GLEIF matches auto-proposed; ministry-registered
   near-misses (DRC, Gabon, Costa Rica) held for review; LAPSED
   registrations used as identifiers with status recorded.
10. **Class name `annual_report`** for the periodic-disclosure class (it
    also holds interim reports and information statements); alternative
    name: `periodic_disclosure`.

## Non-goals (this session)

No UI code. No pipeline wiring (Lane A Stage 2 consumes the tables). No
within-document ontology (stays parked until the clause track). No
reclassification of the corpus in the database; tables are reference data
until a consumer lands. No em-dashes.

## Session notes

- mgrep was unavailable (expired login, known pending item); filesystem and
  SQL search were used instead. No effect on deliverables.
- The snapshot parquet was fetched from the public data host with curl
  because the host serves pre-compressed content DuckDB httpfs does not
  decode; noted for anyone repeating the queries.

## Reviewer dispositions

(One external reviewer pass per spec-lite mode; filled after the pass.)
