# Meta-Learning Report: Round 0 (CAC + Pari Passu Extraction)

**Session:** PR #44, March 28, 2026
**Families:** collective_action, pari_passu
**Results:** 4,246 clauses extracted, 4,151 verbatim verified

## Bug Patterns from Code Review

### E20: Heading level emission
**Bug:** "Top two levels" meant H2/H3 docs emitted both, duplicating text.
**Fix:** Only emit shallowest structural level; skip singleton H1 titles.
**Prevention:** Test with real document heading structures, not just ## examples.

### Clustering gap semantics
**Bug:** Docstring said "gap <= 1" but code used `prev + 2`, merging non-adjacent.
**Fix:** Strict adjacency (diff == 1).
**Prevention:** Test the boundary case explicitly.

### Logger missing duration_ms
**Bug:** CorpusLogger.log() requires duration_ms kwarg; new code omitted it.
**Fix:** Wrap timed operations with time.monotonic().
**Prevention:** Run the actual CLI command (not just unit tests) before committing.

### candidate_id collision
**Bug:** 8-char UUID truncation -> near-certain collisions at scale.
**Fix:** Full UUID.
**Prevention:** Never truncate identifiers.

## What Worked Well

- **Batching by text volume** (~200K chars per batch, ~50 candidates max)
- **Priority ordering** (heading-matched first, body-only later)
- **Sonnet subagents for extraction** (reserves Opus budget for orchestration)
- **Background agents** for lower-priority batches while foreground work continues
- **Incremental JSONL writes** with per-batch immutable files
- **3-model review** before execution caught major issues (E20, clustering, session limits)

## Throughput Actuals

| Metric | Value |
|--------|-------|
| Candidates processed | 5,953 |
| Wall time (EXTRACT) | ~3 hours |
| Candidates/minute | ~33 |
| Verbatim pass (CAC) | 98.3% |
| Verbatim pass (PP) | 96.1% |
| Weekly usage | ~18% (includes all other work) |

## Reviewer Patterns

All three code reviewers pushed for adding the anthropic SDK despite the plan
explicitly saying "Claude Code IS the extractor." Document this decision clearly
in plan headers to avoid repeated pushback.

## Recommendations for Future Rounds

1. Run LOCATE first for all families; estimate time from actual candidate counts
2. Process one family at a time within sessions (5-hour limit)
3. Use per-family COMPLETE.json sentinels, not round-level completion
4. For long sections (EoD), use section_capture_similarity, not verbatim pass
5. Generate round reports AFTER each family, not just after each round
6. Keep calibration/evaluation split integrity -- tune on calibration only
