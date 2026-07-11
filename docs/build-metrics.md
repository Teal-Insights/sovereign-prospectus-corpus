# Build metrics (Project Shell Runbook, per-branch)

One line per branch at handoff. A rebase conflict on this file is
mechanical: keep both lines. Feeds the Stage 5 scoreboard and ADM-153.

| branch | model+effort | attempts | escalations | council C/I post-exec | wall time |
|---|---|---|---|---|---|
| B0 | fable-5 max | 1 | 0 | light gate, docs only | 21 min |
| B2 | opus-4.8 max | 1 | 0 | 0C/2I fixed | ~20m |
| B1 | opus-4.8 max | 1 | 0 | 0C/7I fixed | ~1h |
| B5 | codex high | 1 | 0 | 0C/2I (fixed in-branch, 1 round) | 36m |
| B4 | opus-4.8 max | 1 | 0 | 9C/2I: 7 fixed in-branch, 2 deferred (#107, #108) | ~40 min (deployed slot 4 clean 2026-07-10, live-smoke 3/3) |
| B3 | codex high | 1 | 0 | 0C/1I: 1 deferred (#110); 1 convergent finding refuted on verify | ~35m |
| B6 | opus-4.8 max | 1 | 0 | 0C/0I (1 convergent IMPORTANT refuted on verify: sticky bar measured 132px <= 140px offset); MINORs deferred (#114 disabled-input, #115 sticky-offset robustness, #112 og:url) | ~40m |
| B8 | gpt-5.6-sol high | 1 | 0 | 0C/2I: 1 fixed in-branch (CSV formula-injection guard, closes #116), 1 deferred (UTF-8 BOM #120, ratified no-BOM contract, owner call); 1 CRITICAL (concurrent-query crash) refuted on verify (refresh already runs Promise.all on the shared conn + smoke drives the race); parity test hardened for the M4 override | ~40m |
| B7 | opus-4.8 max | 1 | 0 | 0C/2I both fixed in-branch: S5 long-URL wrap now locked on luxse-100026526 (synthetic docs have filing_url=null so the gate-doc check guarded nothing; convergent Codex+Claude, red-green verified), gate-button smoke asserts height>=44 not either-dimension (Codex) | ~40m |
| S5 audit | fable-5 xhigh | 1 | 0 | 0C/1I found, fixed same session (rendered white-space, PR); MINORs filed | ~2h |
| TEA-989 | fable-5 xhigh | 1 | 0 | pending | ~50m |
