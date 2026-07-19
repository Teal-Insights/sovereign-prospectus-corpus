# Source Onboarding + Dublin: Paste-Ready Executor Prompts (D0-D11)

Stage 2 contract artifacts per the Project Shell Runbook. One prompt per
branch, each self-contained: paste it into a FRESH session of the named
venue and walk away. The plan with full task detail:
`docs/superpowers/plans/2026-07-19-source-onboarding-dublin-plan.md`.
The NORMATIVE spec:
`docs/superpowers/specs/2026-07-19-source-onboarding-dublin-design.md`.

**Dispatch schedule:**

| Wave | Branches | Venue | Notes |
|---|---|---|---|
| 1, day one, parallel | D0 spike, D1 PDIP hashes, D2 contract core, D4 country refactor, D6 parquet policy | D0/D2/D4: Claude Code (D2 on Fable 5 xhigh, D0/D4 Opus 4.8 max). D1/D6: Codex, reasoning high | Separate worktrees, separate sessions. D2 merges first among code branches. |
| 2 | D3 shims+parity, D5 filing_url (both after D2); D7 dedup (after D6; its audit task waits for D1 merged + rebased over); D8 allowlist (after D0 MERGED) | D3/D5: Codex high. D7: Claude Code Fable 5 xhigh. D8: Claude Code Opus 4.8 max | D7 rehearses all DB steps on a copy; its real-DB migration runs later as D10 task 0. D8 merge waits for Teal review (governance gate). |
| 3 | D9 Dublin adapter | Claude Code, Opus 4.8 max | After D2+D3+D8 (D3 is a mandatory base). Merges scheduled=false. |
| 4 | D10 skeleton + backfill | Claude Code, Opus 4.8 max | After D1, D3, D4, D5, D6, D7, D9 all merged. Local, long-running. |
| 5 | D11 how-to + paper re-check | Claude Code, Opus 4.8 max | After D10. |

Every branch merges via the Stage 4 review gate (fresh session, council
code review), never by the executor. All handoff comments go on TEA-1035.

**DATA MOUNT (applies to every operational branch: D1, D3, D4, D5, D7,
D10):** fresh worktrees contain NO data/ (gitignored), and DuckDB
silently auto-creates a missing DB file. Before any data step:
`ln -s /Users/teal_emery/code/sovereign-prospectus-corpus/data data`,
then the identity guard: `SELECT count(*) FROM documents` against
data/db/corpus.duckdb must return roughly 9,795; ANY other number
(especially 0) is a STOP, not a proceed.

---

## D0 spike. Claude Code, Opus 4.8 max. Day one.

```
You are the EXECUTOR for branch D0 (TEA-1035): the Euronext Dublin spike,
the first implementation task of the source-onboarding batch. You are not
the architect. Load operating context from AGENTS.md in the repo root.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Work in a git worktree (superpowers:using-git-worktrees), branch
lte/tea-1035-d0-spike, based on current origin/main.

Read YOUR plan section "D0: Spike" in
docs/superpowers/plans/2026-07-19-source-onboarding-dublin-plan.md and
spec section 7.1 in
docs/superpowers/specs/2026-07-19-source-onboarding-dublin-design.md.
The spec is normative. Answer ALL SEVEN burn-downs with recorded
evidence, then write the "Decisions for the adapter" section (incremental
signal, native_id, discovery mechanism) as single unambiguous sentences.

HARD RULES: plain HTTP fetches only for anything the adapter would later
do; no Selenium, no bot-wall circumvention; polite delays (1s+); this is
observation, not a crawl. Timebox: one session. No em-dashes anywhere.
Draft the Dublin ToS one-liner with terms-page link and date, marked
"pending Teal confirmation".

Deliverable: docs/superpowers/specs/2026-07-19-dublin-spike-findings.md
committed, PR opened, handoff comment on TEA-1035 summarizing all seven
answers, metrics line appended to docs/build-metrics.md:
| D0 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT (comment on TEA-1035, end session) if: the documents tab
needs a real browser; the directory has no scriptable endpoint; ToS reads
as prohibiting the corpus's use.
```

---

## D1 PDIP hash backfill. Codex, reasoning high. Day one.

```
You are the EXECUTOR for branch D1 (TEA-1035): the PDIP hash backfill,
the named precondition branch of the source-onboarding batch. You are not
the architect. Use superpowers:executing-plans and
superpowers:test-driven-development. Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d1-pdip-hash-backfill off origin/main.
Read YOUR plan section "D1: PDIP hash backfill" in
docs/superpowers/plans/2026-07-19-source-onboarding-dublin-plan.md and
the hash-coverage precondition paragraph of spec s5.8. Follow the tasks
in order, test-first.

HARD RULES: mount data/ and run the identity guard per the DATA MOUNT
note above BEFORE any data step; rehearse on a DB copy
(/tmp/corpus-rehearsal-d1.duckdb) before touching
data/db/corpus.duckdb; data/ is never committed; the real run updates
ONLY documents.file_hash for pdip rows (the documents table has NO
file_size_bytes column; do not record sizes, do not add columns);
idempotent re-run proven. If more than ~5% of the 823 originals are
unresolvable, STOP before the real run. No em-dashes.

DoD: coverage query pasted into
docs/coverage/pdip-hash-backfill-2026-07.md (pdip missing == absent-list
length, other sources untouched); tests green; full CI green
(ruff check, ruff format --check, pyright, pytest); handoff comment on
TEA-1035 with counts; metrics line:
| D1 | gpt-5.6-sol high | 1 | 0 | pending | <wall time> |

STOP AND REPORT: absent fraction over ~5%; any cross-source hash
collision behavior question (dedup is D7's, not yours).
```

---

## D2 contract core. Claude Code, Fable 5 xhigh. Day one. THE L BRANCH.

```
You are the EXECUTOR for branch D2 (TEA-1035): the adapter contract core
(registry + types + runner + toysource + contract suite + ToS gate), the
L branch of the source-onboarding batch. You are not the architect. Use
superpowers:executing-plans and superpowers:test-driven-development. Load
AGENTS.md context; read the "Lessons Learned" section (you are building
THE source-adapter substrate).

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d2-contract-core off origin/main.
Read YOUR plan section "D2: Adapter contract core" in
docs/superpowers/plans/2026-07-19-source-onboarding-dublin-plan.md and
spec sections 5.1-5.7, 5.9-5.13. The spec is NORMATIVE: protocol names,
DocRecord fields, status vocabulary, envelope/watermark rules, alarm
table values are fixed there; the plan pins file paths, config keys, and
API names. A design decision neither makes is a stop-and-report.

HARD RULES: legacy source commands and behavior are UNTOUCHED this
branch (D3 owns migration); toysource lives under tests/, never src/;
config.toml edits are appends per the plan's exact keys; scheduled
values exactly as spec s6 assigns; docs/sources.md entries marked
"pending Teal confirmation". No em-dashes.

DoD (all of it): AC 1 toysource end-to-end test green through the REAL
CLI; contract suite green; corpus source list prints FIVE rows against
real config (four active tier-b + lse pending; dormant esma never
prints); registry validation is TIERED per the plan (tier-a full
protocol, tier-b importability-only until D3); alarm/ESMA/pending-status
config assertions (ACs 11, 12, 19) green; full CI green; no legacy
behavior change (prove with the existing per-source tests untouched and
green); PR body requests Teal's ToS wording confirmation and records
the #6/#18 issue dispositions per the plan.

Handoff comment on TEA-1035 (Did/Why/Next/Pointer) + metrics line:
| D2 | fable-5 xhigh | 1 | 0 | pending | <wall time> |

STOP AND REPORT: the protocol cannot express something a legacy shim
will need; Click registry-driven subcommands conflict with existing
commands; anything pushing you to edit a legacy adapter.
```

---

## D3 Tier B shims + parity. Codex, reasoning high. After D2 merges.

```
You are the EXECUTOR for branch D3 (TEA-1035): Tier B legacy shims,
generic CLI dispatch, the parity matrix, the live smoke, and the LuxSE
mini-spike. You are not the architect. Use superpowers:executing-plans
and superpowers:test-driven-development. Load AGENTS.md context,
including "Lessons Learned".

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d3-tierb-parity off origin/main (must
contain merged D2). Read YOUR plan section "D3: Tier B shims" and spec
sections 6 and 5.11. Parity is a matrix, not a vibe: write
docs/parity-matrix-sources.md FIRST from reading all four legacy
modules, then lock it with tests, then migrate.

HARD RULES: behavior parity is the whole point: flags, defaults, NSM
delay split, EDGAR CONTACT_EMAIL User-Agent and 660s sleep, abort exit
codes (nsm/edgar 0+warning, pdip/luxse 1), manifest FORMAT unchanged.
Per-source cli_options are DECLARED in config.toml (in your file list),
never hardcoded in cli.py. You also tighten the registry's tier-b
validation from importability-only to shim shape. Status translation
happens at the reporting boundary only. The live smoke (one migrated
source, real run, expect mass skipped_exists) is DoD-blocking and
REQUIRES the DATA MOUNT + identity guard first: Tier B skips are
disk-keyed, and an unmounted worktree would re-download the window.
LuxSE mini-spike timeboxed ~30 min. No em-dashes.

DoD: parity tests + contract Tier B rows green; live smoke stats pasted
in the PR; four command bodies collapsed into generic dispatch;
mini-spike dispositioned (follow-up issue referencing #93, or
landing-page end state recorded); full CI green.

Handoff on TEA-1035 + metrics line:
| D3 | gpt-5.6-sol high | 1 | 0 | pending | <wall time> |

STOP AND REPORT: any legacy behavior unpreservable through generic
dispatch; the live smoke downloads anything unexpected (abort, report,
do not re-run).
```

---

## D4 country refactor. Claude Code, Opus 4.8 max. Day one.

```
You are the EXECUTOR for branch D4 (TEA-1035): snapshot country
resolution from document_countries with obligor-first precedence, plus
the obligor role migration. You are not the architect. Use
superpowers:executing-plans and superpowers:test-driven-development.
Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d4-country-obligor off origin/main.
Read YOUR plan section "D4" and spec s5.14 refactor 1 + s7.3 + AC 15.

HARD RULES: precedence is obligor row, then issuer row, then the legacy
ISSUER_TO_COUNTRY map; docs with no document_countries rows resolve
BYTE-IDENTICALLY to today. The audited delta must be EXACTLY the three
LSE Congo rows (spec-disclosed); any other changed row is a STOP. Local
snapshot builds go to an alternate output dir; never touch
data/snapshot/. No em-dashes.

DoD: three-way fixture tests green (AC 15); delta run pasted in the PR
showing only the three Congo rows changing; role vocabulary comment
updated; full CI green; issue #80 referenced.

Handoff on TEA-1035 + metrics line:
| D4 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT: any non-Congo row changes in the delta run; a hardcoded
role enumeration you cannot extend safely.
```

---

## D5 filing_url fallback. Codex, reasoning high. After D2 merges.

```
You are the EXECUTOR for branch D5 (TEA-1035): the filing_url
landing-page fallback (source_page_url, then landing_url, then
download_url, registry sources only). You are not the architect. Use
superpowers:executing-plans and superpowers:test-driven-development.
Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d5-filing-url-fallback off origin/main
(must contain merged D2). Read YOUR plan section "D5" and spec s5.14
refactor 2 + AC 14.

HARD RULES: every landing_url you set must curl-200 and be cited in the
PR body; a download_url with expiry material never becomes filing_url
for a registry source; non-registry rows keep today's behavior; the
expected delta is ~4,965 LuxSE rows flipping to the landing page and
NOTHING else. No em-dashes.

DoD: fixture tests green; delta counts by source pasted (luxse only);
issue #93 referenced; full CI green.

Handoff on TEA-1035 + metrics line:
| D5 | gpt-5.6-sol high | 1 | 0 | pending | <wall time> |

STOP AND REPORT: delta shows edgar/nsm/pdip rows changing; a registered
source with no defensible landing_url.
```

---

## D6 parquet policy. Codex, reasoning high. Day one.

```
You are the EXECUTOR for branch D6 (TEA-1035): the parquet
additive-within-version policy reconciliation. You are not the
architect. Use superpowers:executing-plans and
superpowers:test-driven-development. Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d6-parquet-policy off origin/main.
Read YOUR plan section "D6" and spec s5.14 refactor 3 + AC 20.

HARD RULES: this is a comment rewrite + a data-contract fixture test,
NOT a UI change (the explorer-web touch is the spec's named carve-out).
SCHEMA_VERSION stays 1. The widened fixture parquet is generated by a
committed script step, never by hand, and the test runs through the
same client path the deployed site uses. The producer comment text is
verbatim in the plan. explorer-web needs Node >= 22.12. No em-dashes.

DoD: vitest green proving a version-1 parquet with an extra column
reads normally; producer comment states additive-within-version;
npm test + npx astro check green in explorer-web; repo CI green.

Handoff on TEA-1035 + metrics line:
| D6 | gpt-5.6-sol high | 1 | 0 | pending | <wall time> |

STOP AND REPORT: the deployed client path genuinely fails on the
widened parquet (do NOT patch the client; that falsifies a ratified
contract assumption and the architect must know).
```

---

## D7 dedup pass + audit. Claude Code, Fable 5 xhigh. After D6 (audit task after D1).

```
You are the EXECUTOR for branch D7 (TEA-1035): the corpus-wide dedup
pass and the one-time cross-source audit, the second L branch. You are
not the architect. Use superpowers:executing-plans and
superpowers:test-driven-development. Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d7-dedup-pass off origin/main (must
contain merged D6; do not start the audit task until D1 is merged).
Read YOUR plan section "D7" IN FULL and spec s5.8 IN FULL (plus AC
3/4/5/6/7/18). The spec fixes the mechanism: SHA-256 only hard key,
document_listings DDL verbatim, root eligibility, basis integrity,
suppressed handling with the three-leg skip set, final_terms-only
suppression, fixed-point equivalence class, forward-only. The plan pins
the design-open points: documents.suppressed_at as the suppression
predicate, the suppression_records table, advisory API names.

HARD RULES: mount data/ + identity guard per the DATA MOUNT note; the
schema migration and listings backfill are REHEARSAL-ONLY in this
branch, on /tmp/corpus-rehearsal-d7.duckdb (the real-DB run is D10's
task 0, post-review-gate); the ONLY real-DB touch you make is the
READ-ONLY audit; data/ never committed; no retroactive merges;
scope_status is NEVER used for demotion; suppressed_at and
suppression_records are synchronized PROJECTIONS of the platform's
suppressions ledger (ship apply_suppressions() per the plan); the
invariant query (every non-demoted, non-suppressed document has exactly
one original listing) plus the cardinality assertions must return clean
on the rehearsal DB. No em-dashes.

DoD: every named AC demonstrated by a named test (including the dedup
attach + idempotent re-ingest cases INSIDE tests/sources/
test_contract.py and the listings-vs-documents counter test);
docs/coverage/duplicate-audit-2026-07.md committed (read-only run,
after rebasing over merged D1); decisions file + idempotent corpus
dedup apply working; snapshot emits the additive duplicate_of column at
SCHEMA_VERSION 1; full CI green; rehearsal invariant + cardinality
output pasted in the PR.

Handoff on TEA-1035 + metrics line:
| D7 | fable-5 xhigh | 1 | 0 | pending | <wall time> |

STOP AND REPORT: backfill rehearsal shows any document getting zero or
two original listings; the transactional document+listing insert cannot
be made atomic in DuckDB as designed; anything tempts you to mutate
during the audit.
```

---

## D8 allowlist sweep. Claude Code, Opus 4.8 max. After D0.

```
You are the EXECUTOR for branch D8 (TEA-1035): the Dublin issuer
allowlist sweep, review-then-commit reference data under the pilots'
governance. You are not the architect. Use superpowers:executing-plans.
Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d8-dublin-allowlist off origin/main.
Read YOUR plan section "D8" and spec s7.2. D0's findings doc
(docs/superpowers/specs/2026-07-19-dublin-spike-findings.md) gives you
the discovery mechanism and volume bounds.

HARD RULES: every SPV row is hand-checked with a cover-page-cited
obligor in its evidence note (fetch the actual prospectus cover). The
Aramco-class trap is real: sovereign-sounding corporate vehicles
classify corporate and stay OUT. Uncertain rows get status=review,
never active. Pilot-table rows land status=proposed; sukuk SPVs stay
DISTINCT entities. Sweep politely (1s+ delays). Raw sweep output goes
in the PR, not under data/. No em-dashes.

DoD: dublin_issuers.csv committed with every spec column populated;
schema tests green; proposals in all three pilot tables + Dublin
doc_class_map rows; classification evidence summary in the PR body;
the PR states plainly that MERGE WAITS FOR TEAL'S REVIEW (the
governance gate); full CI green.

Handoff on TEA-1035 + metrics line:
| D8 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT: the sweep cannot enumerate the full directory with
D0's mechanism; classification confidence is low for a large fraction
(report the fraction, never guess).
```

---

## D9 Dublin adapter. Claude Code, Opus 4.8 max. After D2 + D3 + D8 (Teal-approved).

```
You are the EXECUTOR for branch D9 (TEA-1035): the Euronext Dublin
adapter module, the first Tier A source. You are not the architect. Use
superpowers:executing-plans and superpowers:test-driven-development.
Load AGENTS.md context, including "Lessons Learned" (you are building a
source adapter).

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d9-dublin-adapter off origin/main (must
contain merged D2, merged D3, and Teal-approved D8; D3 is a mandatory
base, you ride its generic dispatch). Read YOUR plan section "D9" and
spec s7.2/7.3/7.5 + s5.13.

THE BAR (spec s5.13, enforced): your diff touches EXACTLY
src/corpus/sources/dublin.py, tests/sources/test_dublin.py + fixtures,
the [dublin] config block + active_sources append, and the
docs/sources.md Dublin section (Teal-confirmed wording from D0). If you
need to edit cli.py, the runner, the snapshot builder, or the schema,
THE CONTRACT FAILED: stop and report the defect, do not work around it.
Registration is not activation: scheduled = false. Adapters never write
ANYTHING outside state_dir/staged/<run-id>/ and never sleep (the runner
owns both). Review-lane items go through the STAGED channel: read live
review_lane.jsonl read-only, merge append-if-absent keyed on normalized
name (first_detected stays stable), write the merged file to
state_dir/staged/<run-id>/review_lane.jsonl; never write live state.
Reach the allowlist ONLY via ReferenceData.table("dublin_issuers"). No
em-dashes.

DoD: contract suite green including Dublin (Tier A runner assertions
now bind to a real source); end-to-end fixture run through the REAL CLI
(discover, download, ingest, envelope-bound, watermark advances);
corpus source list shows dublin enrolled-not-scheduled with ToS
recorded; the zero-edit bar proven by the diff in the PR body; full CI
green.

Handoff on TEA-1035 + metrics line:
| D9 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT: any s5.13 bar violation; the D0-chosen incremental
signal fails on live data during fixture recording; S3 fetches blocked
from your network.
```

---

## D10 skeleton + backfill. Claude Code, Opus 4.8 max. After D1/D3/D4/D5/D6/D7/D9.

```
You are the EXECUTOR for branch D10 (TEA-1035): the walking skeleton
and the EXECUTED Dublin backfill. This is an operational branch: you
run the system, you do not extend it. You are not the architect. Load
AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d10-skeleton-backfill off origin/main
(must contain D1, D3, D4, D5, D6, D7, D9 all merged). Read YOUR plan
section "D10", spec s13 (the skeleton, executed clause by clause), and
spec s7.4 (dedup expectations).

HARD RULES: no product code in this branch; any defect routes back as a
stop-and-report. Mount data/ + identity guard per the DATA MOUNT note,
and apply the plan's canonical-state gate BEFORE any mutation. YOUR
TASK 0 (new, post-review-gate execution of D7's rehearsed steps): dated
backup copy of corpus.duckdb, apply the schema migration, run the
original-listing backfill, paste the invariant + cardinality evidence;
any violation is a STOP. Then run locally with politeness delay 1.0s,
caffeinate for the long run, run id dublin-backfill-<date>, circuit
breaker armed and never loosened. Pick the skeleton's dedup issuer via
the READ-ONLY overlap scout (metadata-level against post-D1 holdings;
Dublin-vs-PDIP is the spec's likelier pair); the cross-source
attestation clause may close after the backfill if the scouted issuer
yields no pair. Local snapshot builds to an alternate dir only. No
em-dashes.

THE STOP-AND-ASSESS RULE (spec s7.4, not waivable): if the backfill
finds ZERO cross-source exact-hash pairs, write the assessment section,
post it on TEA-1035, and STOP. No D11, no scheduled=true talk, until
the architect and Teal disposition it.

DoD: every s13 skeleton clause demonstrated with pasted command+output
evidence in docs/coverage/dublin-backfill-2026-07.md; backfill executed
and reported (counts by issuer_type and country; minted vs attested vs
advisories raised vs suppressed); idempotent re-ingest proof pasted;
snapshot spot-check shows an SPV document with its obligor country;
evidence links on TEA-1035.

Handoff on TEA-1035 + metrics line:
| D10 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT: breaker aborts; any ingest defect; volume wildly over
D0's bound; the zero-pairs outcome (per the rule above).
```

---

## D11 how-to + paper re-check. Claude Code, Opus 4.8 max. After D10.

```
You are the EXECUTOR for branch D11 (TEA-1035): the how-to doc (the
pattern as product) and the ESMA/SGX paper re-check. You are not the
architect. Load AGENTS.md context.

Repo: /Users/teal_emery/code/sovereign-prospectus-corpus
Worktree branch lte/tea-1035-d11-howto-doc off origin/main (after D10).
Read YOUR plan section "D11" and spec s10, s8, s9.

Write docs/how-to/add-a-source.md with Dublin as the worked example END
TO END: ToS gate first, spike shape, the five s5.13 artifacts, contract
hooks with REAL Dublin code pointers (file paths, PR numbers), fixture
recording, the contract suite, register/alarm declarations, dedup
expectations, backfill etiquette, enrollment (the scheduled flip), ship
checklist. Every step cites the real artifact that instantiates it; no
hypothetical code blocks. BLUF; skim-test headings. No em-dashes.

Then re-walk spec s8 (ESMA) and s9 (SGX) against the contract AS BUILT.
Record either the explicit friction-delta list or "holds as specified"
with checked items enumerated, in the PR body. (The architect posts the
outcome to TEA-1053/TEA-1055; you do not touch those issues.)

DoD: how-to merged from real artifacts; paper re-check recorded;
docs/sources.md carries ZERO "pending Teal confirmation" markers (if
any remain from D2/D9, obtain Teal's confirmation via this PR and clear
them; this is the named close-out for spec s14's Teal-confirmed line);
full CI green (docs-only, run anyway).

Handoff on TEA-1035 + metrics line:
| D11 | opus-4.8 max | 1 | 0 | pending | <wall time> |

STOP AND REPORT: the re-check finds friction that would change ESMA or
SGX from config-plus-one-module (pivot-memo trigger; the architect
decides).
```
