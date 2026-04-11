# Spring Meetings Sprint — Resequencing + LuxSE + Single Bulk Parse

**Date:** 2026-04-11
**Sprint deadline:** 2026-04-13 (IMF/World Bank Spring Meetings, Monday morning)
**Replaces:** The "Docling migration + bulk reparse" plan in issue #72
**Related:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md`, issues #53, #54, #55, #56, #72

## Intent

Two things matter for Monday's demo, in this order:

1. **Coverage.** More sovereign prospectuses in the corpus is the single biggest lever for "is this tool useful to the people in the room." The audience is sovereign debt lawyers and economists from IMF Legal, World Bank debt teams, and the broader research community. They will judge the explorer by whether the documents they care about are in it — not by the elegance of the pipeline. That means **committing to the Luxembourg Stock Exchange adapter for this sprint**, not deferring it, and refreshing NSM + EDGAR to capture the last two weeks of new filings (notably the Democratic Republic of the Congo's April 2026 prospectus, which is on NSM — not LSE RNS as the original sprint plan assumed).

2. **Cost discipline on PDF parsing.** Docling takes ~10 s/PDF even with parallelism. The existing 1,468 NSM + PDIP PDFs were already Docling-parsed on 2026-03-28 (clean run, zero errors). The remaining Docling work is only the small number of **new** NSM PDFs from the last two weeks plus however many LuxSE produces. All of it should parse exactly once, after all downloads are settled — no two-phase reparse, no intermediate partial runs. The M4 Pro runs one attended overnight-style job; it does not parse the same document twice.

### A note on time estimates in this spec

Agentic AI systems, including the one writing this spec, consistently and dramatically overestimate the time implementation tasks take. The human author knows this from experience. **The time estimates in this document should be treated as upper bounds to push back on, not floors to plan around.** External reviewers should challenge any number that feels padded. A realistic sprint budget is probably 50-70% of the wall-clock estimates below.

## What changed vs. the original sprint plan

### Four corrections to facts the sprint plan assumed

1. **EDGAR is not PDFs.** The sprint plan spoke about "PyMuPDF → Docling" as if it were a uniform corpus migration. EDGAR is actually 2,947 `.htm` + 275 `.txt` + 84 `.paper` placeholders, parsed via `HTMLParser` (BeautifulSoup with CSS page-break splitting) and `PlainTextParser`. Docling does not apply to EDGAR at all. The "reparse all 4,769 documents" framing in issue #72 was wrong.

2. **NSM + PDIP are already fully Docling-parsed.** `data/parsed_docling/` on this machine contains 1,468 Docling-parsed files from a clean March 28 run. `_summary.json` shows 1,466 completed / 0 failed, `_errors.log` is empty. There is no gap to fill on these two sources.

3. **The Congo document is DRC, not Republic of Congo, and it's on NSM.** The sprint plan (Task 5) described it as "Republic of the Congo" published on LSE RNS on 2026-04-08. The user has independently verified it is the **Democratic Republic of the Congo** and that it appears on FCA NSM. DRC's official name is "Democratic Republic of the Congo," which contains the substring "Republic of" — the NSM adapter's `build_sovereign_queries` already emits a "Republic of" name-pattern search, so DRC should be captured automatically by an incremental NSM discovery. **This assumption must be verified by actually running the incremental and confirming DRC filings appear in the discovery output, before proceeding to any downstream step.**

4. **LSE RNS (Task 5) can be dropped from this sprint.** If DRC comes in via NSM, there is no remaining justification for the LSE RNS adapter in this window. Task 5 goes into a post-Spring-Meetings follow-up.

### The real Docling delta

After those corrections, the Docling work that actually needs to happen before Monday is:

- **New NSM PDFs** from the incremental refresh (estimate: low tens to low hundreds of new filings in two weeks, of which some subset are PDFs — probably <150)
- **LuxSE PDFs** from the new adapter (unknown until the adapter runs, conservative estimate: a few hundred)
- **Parser registry work**: add a `DoclingParser` class, register it, and make it the config default so any PDF processed through the `corpus parse` CLI routes through Docling automatically. This is the parser-layer subset of issue #72 — the bulk-reparse phases of that issue are moot given the landscape corrections above.

## Scope

### In scope for this sprint

- **Docling Phase A:** `DoclingParser` class + registry registration + `config.toml` default flip. Ships as its own small PR. No DB changes, no file moves, no bulk reparse wired in.
- **NSM incremental** discover + download.
- **EDGAR incremental** discover + download.
- **LuxSE adapter:** new source adapter, committed unconditionally per explicit user decision, time-boxed to a hard cliff (see below). No curl-test go/no-go gate — the user has accepted the uncertainty in order to protect coverage.
- **DRC verification gate:** after NSM incremental, confirm the DRC 2026-04 filing is in the discovery output. If not, manual ingest via the FCA artefact URL.
- **Single bulk Docling parse run** on the M4 Pro, after every download is complete. Resume support skips already-parsed files.
- **`parsed_docling/` → `parsed/` in-place merge** inside Task 3's PR (not Docling Phase A's). Overwrites the 1,468 PyMuPDF `.jsonl` files in `data/parsed/` with the corresponding Docling outputs; then `data/parsed_docling/` is deleted.
- **Task 3 (FTS + country backfill + MotherDuck publish)** with the `documents.parse_tool` column updated to `'docling'` for the 1,468 rows at rebuild time.
- **Task 4 (Streamlit explorer)** per the sprint plan.
- **Task 9 polish:** demo script, smoke tests, warm-up for cold start.

### Explicitly out of scope for this sprint

- LSE RNS adapter (Task 5) — replaced by NSM incremental + DRC verification gate.
- ESMA adapter (Task 8).
- Reparsing the 1,468 existing Docling files (they are already correct).
- Touching the V1 Quarto book or V1 Shiny app (frozen per CLAUDE.md).
- Re-running the grep_matches table after the Docling merge. The existing 106,229 matches are good enough for the demo; a re-grep is a follow-up.
- Updating `docs/RATIFIED-DECISIONS.md` Decision 18. Belongs in Docling Phase A's PR as a small doc update — trivial, not a scope question.

## The sequence (Approach Y — gated sequential with time-boxed LuxSE)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1 — Docling Phase A (PR #1)                                         │
│   DoclingParser class + register + config.toml default flip              │
│   Unit tests for the parser class                                        │
│   Decision 18 doc update                                                 │
│   Ships independently; no downloads or merges touched                    │
│   Est. wall: 1-2 hr inclusive of bot review                              │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2 — NSM + EDGAR incrementals (commands, not a PR)                   │
│   corpus discover nsm → corpus download nsm                              │
│   corpus discover edgar → corpus download edgar                          │
│   Both adapters hit disjoint hosts and honor per-source rate limits,     │
│     so they run in parallel shells                                       │
│   Est. wall: 1-2 hr                                                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌══════════════════════════════════════════════════════════════════════════┐
│ GATE A — DRC verification                                                │
│   grep the NSM discovery JSONL for "Democratic Republic of the Congo"    │
│   and for submitted_date ≥ 2026-04-01                                    │
│   PASS: proceed to Step 3                                                │
│   FAIL: manual ingest path — direct FCA artefact URL, write a manual     │
│         manifest entry, continue                                         │
└══════════════════════════════════════════════════════════════════════════┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3 — LuxSE adapter (PR #2)                                           │
│   Build adapter against the LuxSE site                                   │
│   Hard cliff: 5 hours of cumulative wall clock from "branch created"     │
│     until a discovery run produces a non-empty sovereign hit list.       │
│     Bot-review and user-idle time counts; the cliff is about total       │
│     sprint-clock consumed, not developer focus time.                     │
│   If the cliff hits before sovereign PDFs are being discovered +         │
│     downloaded: commit what works, document the gap in                   │
│     docs/SOURCE_INTEGRATION_LOG.md, proceed to Step 4 with whatever      │
│     coverage the adapter achieved                                        │
│   Run full LuxSE download immediately when the adapter lands             │
│   Est. wall: 4-6 hr build + 0.5-1 hr download                            │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌══════════════════════════════════════════════════════════════════════════┐
│ GATE B — downloads settled                                               │
│   All three adapters have finished downloading, no in-flight requests    │
│   Checkpoint: take inventory of data/original/ to compare pre/post       │
└══════════════════════════════════════════════════════════════════════════┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4 — Single bulk Docling parse run on the M4 Pro                     │
│   scripts/docling_reparse.py (cherry-picked from feature/30-docling-     │
│     reparse, same as issue #72 Phase A described)                        │
│   Resume support skips the 1,468 already-parsed files                    │
│   Parses only the new NSM PDFs + all LuxSE PDFs (probably <500 docs)     │
│   User runs on M4 Pro, monitored via tail -f _progress.jsonl             │
│   Est. wall: 0.5-1.5 hr attended                                         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 5 — Task 3 FTS + merge + MotherDuck (PR #3)                         │
│   5a: in-place merge data/parsed_docling/*.jsonl → data/parsed/          │
│   5b: delete data/parsed_docling/ after merge verifies                   │
│   5c: DB rebuild with parse_tool='docling' for the 1,468 NSM+PDIP rows   │
│       (plus all the new NSM + LuxSE rows, which parsed through Docling   │
│        natively)                                                         │
│   5d: country_classifications table (WB API pull, ~200 rows)             │
│   5e: country backfill for EDGAR/NSM documents                           │
│   5f: document_pages + FTS index                                         │
│   5g: publish-motherduck                                                 │
│   Est. wall: 3-5 hr                                                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 6 — Task 4 Streamlit explorer (PR #4)                               │
│   Per sprint plan: landing page, search, filters, detail panel, deep-    │
│     linkable state, deploy to Streamlit Cloud                            │
│   Smoke tests: DRC/Congo, Ghana, Argentina, collective action clause,    │
│     pari passu, New York law, contingent liabilities                     │
│   Est. wall: 4-8 hr                                                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 7 — Task 9 polish                                                   │
│   Demo script, README, flag-this-document button, cold-start warm-up    │
│   Est. wall: 1-2 hr                                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Total wall-clock estimate: 15-26 hours.** Treat as upper bound. See note on AI time-estimate bias above.

## Gates and fallbacks

| Gate | Trigger | PASS action | FAIL action |
|---|---|---|---|
| **A — DRC verification** | NSM incremental complete | Proceed to Step 3 | Manual ingest from FCA artefact URL; write a manual manifest entry; continue |
| **B — Downloads settled** | LuxSE download complete (or cliff hit) | Proceed to Step 4 parse | n/a — this gate can't fail, it's a checkpoint |
| **LuxSE 5-hour cliff** | Cumulative active build time on LuxSE adapter hits 5h | n/a | Commit what works, document in `docs/SOURCE_INTEGRATION_LOG.md`, download whatever the partial adapter can, move to Step 4 |
| **Parse error budget** | `_errors.log` after Step 4 run | If <5% error rate: proceed | If ≥5%: inspect errors, decide per-doc |

## Deliverables

- **PR #1** — Docling Phase A (parser class, registry, config default, tests, Decision 18 update)
- **PR #2** — LuxSE adapter (source adapter, tests, sovereign query config, integration with manifest pipeline)
- **PR #3** — Task 3: FTS + parsed-dir merge + country classifications + MotherDuck publish
- **PR #4** — Task 4: Streamlit explorer deployed to Streamlit Cloud
- **(optional) PR #5** — Task 9 polish if it warrants a PR vs. small commits to main

## Open decisions (pre-spec approval)

The following were my proposals. The user accepted Approach Y but did not explicitly accept or reject these sub-decisions. **External reviewers should push back on any of these that look wrong.**

1. **LuxSE time-box cliff at 5 hours active build time.** Is this the right cliff? Too generous? Too tight?
2. **DRC verification gate after NSM incremental**, with manual fallback if the `"Republic of"` name pattern misses DRC. Is the gate placed in the right spot?
3. **In-place overwrite** as the merge strategy (`data/parsed_docling/*.jsonl` overwrites `data/parsed/*.jsonl`, then delete `data/parsed_docling/`). Alternative: rename dirs. Alternative: per-source routing in the ingest. In-place overwrite has the smallest blast radius for Task 3.
4. **Docling Phase A ships independently of the merge.** This means for ~hours-to-a-day, `config.toml` says `docling` but `data/parsed/` still holds PyMuPDF outputs for NSM+PDIP. That's fine because nothing reads `parse_tool` from disk during that window — the mismatch is only in the DB `documents.parse_tool` column, which gets corrected at Task 3 rebuild. Is this acceptable or should the merge ship with Phase A?

## Risks

- **LuxSE site is a JS SPA.** Mitigation: the 5-hour cliff catches this without consuming the whole sprint.
- **DRC doesn't come in via NSM incremental.** Mitigation: Gate A + manual ingest fallback.
- **Docling takes longer than expected on LuxSE PDFs.** If LuxSE returns e.g. 500 PDFs and they're complex (100+ pages each), the parse run could extend to 2-3 hours rather than <1.5h. Still within budget.
- **Streamlit Cloud deploy friction.** Mitigation: Task 1 (PR #61) already de-risked this. Follow the gotchas documented in `reference_streamlit_cloud_deploy.md`.
- **Time budget overrun on Task 4.** The UI work is the biggest unknown. Mitigation: the polished UI can ship thin — landing page + search + filters + detail panel is enough, deep-linkable state and flag button can slip to Monday morning.

## Non-goals

- Perfect coverage. The demo ships with whatever coverage the adapters achieve in the budget. LuxSE may come in at 50% or 100%. That's fine — "here's what we've got, here's what's coming" is an acceptable narrative for a working demo.
- Perfect text quality on every document. Docling is noticeably better than PyMuPDF but not infallible. Hand-verification of demo-surfaced extractions remains the roundtable-level discipline; Monday's demo is searchable, not hand-curated.
- Zero tech debt. Follow-up issues get filed for anything that must slip. The sprint ships.
