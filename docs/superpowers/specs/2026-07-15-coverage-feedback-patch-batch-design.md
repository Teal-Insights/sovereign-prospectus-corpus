# Coverage Feedback Patch Batch Design

**Date:** 2026-07-15
**Issues:** TEA-1004, TEA-1003, TEA-1006, TEA-1005
**Project:** Sovereign Prospectus Explorer v2

## Outcome

Close four coverage gaps from Janet He's explorer review in the requested order,
then generate and publish one coherent snapshot. The batch adds Venezuela's SEC
filings, adds Bolivia's Luxembourg Stock Exchange offering documents, verifies
the reported Bolivia search false positive against production before changing
search behavior, and manually ingests the distinct Republic of Congo offering
documents available from the London Stock Exchange (LSE).

The final snapshot is generated once, after every successful ingest. One live
smoke run then verifies the deployed explorer against that snapshot.

## Verified starting facts

- The linked SEC submissions feed identifies CIK `0000103198` as the
  `BOLIVARIAN REPUBLIC OF VENEZUELA` and contains the cited 2003-05
  prospectus-type filings.
- LuxSE identifies `US29731QAF46` as Bolivia's 9.45% 2031 Rule 144A bond,
  listed 2026-06-03, and `USP37878AC26` as Bolivia's 4.5% 2028 Reg S bond,
  listed 2017-03-22.
- A separate primary-source verification confirmed LuxSE's exact issuer name
  `BOLIVIA (PLURINATIONAL STATE OF)`, issuer ID `29689`, and offering-document
  IDs `105422819` (2026) and `3138724` (2017). The official World Bank FY2027
  workbook lists `BOL` as Latin America & Caribbean, lower middle income, IBRD.
- The reported code pointers were checked before editing:
  - `src/corpus/sources/edgar.py:33` is the `SOVEREIGN_CIKS` map.
  - `src/corpus/sources/luxse.py:29` is a generic search-pattern list, not a
    country map. TEA-1003's suggested edit location is therefore wrong.
  - `explorer-web/src/lib/queries.ts:35` begins the current metadata-search
    clause.
- The controllable browser is unavailable at session start. Production search
  reproduction and LSE document retrieval remain hard gates. Neither will be
  replaced by a local-only simulation or a curl-only retrieval. No final
  snapshot will be built or published until both browser gates pass.

## TEA-1004: Venezuela EDGAR coverage

Add CIK `0000103198` to the existing sovereign issuer list without changing
`PROSPECTUS_FORMS`. The expected batch scope is eight `424B3`/`424B5` filings;
`S-B` and `POS AM` remain outside the ratified adapter filter. Update the
exact-count test and add an identity regression assertion. Add a safe specific-
CIK discovery selector and repeatable storage-key parse selector so the run is
targeted and auditable. Use isolated discovery output, then download, parse,
and ingest through the adapter and CLI.

Add the exact SEC issuer spelling to the country resolver and test that it maps
to `VEN`, Venezuela, sovereign. Before ingest, assert every expected accession
exists in discovery, the canonical manifest, the downloaded files, and parsed
output, with no unresolved target pagination failures.

Record Venezuela counts before and after by source. The snapshot waits for the
end of the full batch.

The issue also requests an observation about other possible omissions from the
27-entry list. Record a bounded observation on TEA-1007 rather than expanding
this patch beyond the verified Venezuela CIK.

## TEA-1003: Bolivia LuxSE coverage

The current LuxSE adapter discovers documents by six generic terms. Bolivia's
canonical LuxSE issuer name may not contain any of those terms, which explains
the gap. Add an injected/repeatable search-term selector and configuration-level
default that uses LuxSE's primary-source canonical name. Do not introduce an
adapter-local country map. Use an isolated discovery output so this run cannot
erase or conflate another adapter's discovery artifact.

Targeted discovery must include the 2026 and 2017 anchor securities and retain
the issuer name supplied by LuxSE. Add the exact issuer spelling to the country
resolver and add `BOL` to the FY2027 World Bank reference table only after a
separate primary-source verification. Download, parse only the target storage
keys, and ingest the offering documents. Validate that both anchors exist in
discovery, manifest, files, parsed output, database, and final Parquet, with no
unresolved target-query or rate-limit failures. No record attributed to Bolivia
may contain the Venezuelan issuer or the `BOLIVIAN Republic of Venezuela` title
typo, and neither country may enter the snapshot's unmapped-issuer audit.

Record Bolivia counts before and after by source. Defer snapshot generation.

## TEA-1006: production-only reproduction gate

Before changing the search implementation for this issue, search `Bolivia` on
`https://prospectus.tealinsights.com` and record the production snapshot date,
slug, source, raw title, issuer, and country for every returned row.

- If Venezuelan rows do not appear, close TEA-1006 as not reproducible with the
  observed results. Make no search or data-normalization change.
- If Venezuelan rows appear, preserve raw source titles and correct the
  user-facing searchable value at the narrowest shared data seam. Add a
  regression test proving `Bolivia` excludes Venezuela while `Venezuela` keeps
  the Venezuelan rows. Verify the two affected LuxSE native IDs against their
  source metadata, record any derived correction and reason, and prohibit a
  corpus-wide replacement of `BOLIVIAN`. Post the chosen layer and rationale to
  Linear.

The snapshot is still generated only once at the end.

## TEA-1005: Republic of Congo LSE stopgap

Use a real browser to inspect issuer page `XZ57` and retrieve every distinct
offering document associated with the November 2025, December 2025, February
2026, and May 2026 issuances. Count documents, not transactions: a tap may share
its base circular or have a separate supplement. Verify every downloaded file
begins with `%PDF`, opens successfully in the project PDF parser, has nonzero
pages and nonempty text, and retain the stable LSE document URL as provenance.
Manually verify the cover-page issuer, title, role, ISIN, and date, including
that the issuer is Republic of Congo rather than the Democratic Republic of the
Congo.

Manual records use `source="lse"`, `lse_manifest.jsonl`, a stable LSE document
ID as `native_id`, and `lse__{native_id}` as `storage_key`. Each record carries
a relative `file_path`, SHA-256, byte size, exact raw issuer name, document type,
publication date, non-null `source_page_url` and `source_page_kind`, plus source
metadata for XZ57, ISINs, document ID, base/tap role, associated issuance dates,
and retrieval time. Manifest creation is atomic and resume-safe. Add `lse` as a
friendly `London Stock Exchange` source in explorer copy and tests.

Deduplicate artifacts by SHA-256 and create one document row per unique legal
document. Maintain an inventory of URL, hash, document role, family, ISIN, and
associated issuance events. Parse only the resulting storage keys, ingest them,
and report both unique legal documents and coverage of the four issuances.

This stopgap must not grow into the future LSE adapter. TEA-1008 owns that work.

## One final snapshot and live verification

After all four issue gates and all ingests are complete:

1. Rebuild derived database tables required by the snapshot.
2. Generate one successful candidate in `data/snapshot/` with
   `scripts/build_snapshot.py`. Failed pre-publication candidates may be
   discarded and rebuilt; no intermediate per-issue snapshot is published.
3. Validate the Parquet contract: distinct storage-key counts by country and
   source, distinct file hashes, target slugs, `VEN`/`BOL`/`COG` mappings,
   sovereign default visibility, and no target unmapped issuers. Record the
   candidate MANIFEST and Parquet SHA-256 values with the generation timestamp,
   code commit, schema version, and source-record counts.
4. Build the branded wrapper locally against the candidate and run its exact
   two-origin production smoke before publication.
5. Merge the open-repo code; if explorer code changed, bump the private
   wrapper's upstream pin to that merge SHA.
6. Publish with the wrapper's `upload-snapshot.sh`, preserving text, then
   Parquet, then `MANIFEST.json` last. Verify the hosted manifest and Parquet
   carry the candidate generation.
7. Trigger and await the Netlify production build. Confirm the deployed body
   build stamp equals the hosted manifest `generated_at` and no drift notice
   appears.
8. Run the private wrapper's `scripts/live-smoke.mjs`, then run release-specific
   production assertions for the new slugs, text loads, country/source counts,
   provenance URLs, Congo/DRC separation, and both country searches.

Before publication, record the previous hosted snapshot generation and wrapper
deploy. Any build-stamp mismatch, missing target slug, count mismatch, drift
notice, failed provenance load, or live-smoke failure triggers rollback to that
pair.

Do not regenerate an intermediate snapshot between issues.

## Completion criteria

- TEA-1004: Venezuela CIK present; qualifying SEC documents ingested; counts
  posted; TEA-1007 receives the bounded issuer-list observation.
- TEA-1003: both anchor securities represented by offering documents; Bolivia
  appears with correct attribution; no Venezuela contamination; counts posted.
- TEA-1006: production behavior recorded first; either closed as not
  reproducible without code changes or fixed with a regression test.
- TEA-1005: all distinct LSE offering documents retrieved by browser, verified,
  ingested with provenance, and counted against the four issuances.
- Snapshot generated once after the ingests and the live-smoke check passes.
- Ruff, ruff format, pyright (no new errors), pytest, explorer tests, and the
  relevant end-to-end commands pass.
- Each issue is claimed on touch, trailed in comments, and closed on completion.
- The project receives one final status update covering what shipped, new
  country counts, and next work: TEA-1007 coverage ledger and TEA-1008 LSE
  adapter.

## Spec council disposition

Five fresh-context seats reviewed this spec: an independent generalist, a
sovereign-debt/data-credibility reviewer, the downstream explorer consumer, a
Python/DuckDB pipeline specialist, and a CI/release reviewer.

Accepted and incorporated:

- Safe specific-CIK/search-term discovery and repeatable storage-key parsing.
- Exact issuer-country mappings, primary-source World Bank verification, and
  target unmapped-issuer/default-visibility assertions.
- An all-or-nothing browser gate before the one published snapshot.
- Exact LSE source/manifest identity, provenance, stable IDs, relative paths,
  atomic resume behavior, content-hash deduplication, document-family inventory,
  stronger PDF validation, and manual cover checks.
- Form-specific Venezuela expectations and target-stage assertions.
- A complete wrapper upload/deploy/build-stamp/live-smoke/rollback transaction.
- Count grain defined as distinct storage keys, with file-hash and issuance
  coverage reported separately.
- Pre-publication branded smoke, candidate checksums, and separate deterministic
  PR gates versus operator-run network evidence with run IDs.

Pushback or bounded disposition:

- The generalist's statement that the existing map lacks LuxSE's
  `VENEZUELA (BOLIVARIAN REPUBLIC OF)` was factually incorrect; that alias is
  already present. The new SEC spelling still requires its own mapping.
- The consumer proposed `lse_rns`; this batch uses `lse` because the retrieved
  offering documents are LSE company-page artifacts and are not necessarily RNS
  announcements. TEA-1008 can reuse the venue-wide source key.
- GitHub #55 belongs to TEA-1008 and is not rewritten in this stopgap. The new
  lane will comply with #5's relative-path requirement and will not extend #13's
  append-only manifest debt. GitHub #93 concerns expiring LuxSE links, a separate
  venue; this batch still requires durable LSE provenance checks.
- A new snapshot release-ID schema was not added. Existing `generated_at` plus
  recorded artifact SHA-256 values and the upstream commit provide the same
  release identity without changing the consumer contract in this patch.
