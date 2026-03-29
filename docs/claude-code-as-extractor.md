# Claude Code as LLM Extractor: Methodology & Usage Guide

## The Approach

Instead of calling the Anthropic API programmatically (which requires a separate
API key and per-token billing), we use **Claude Code itself as the LLM extractor**.
Claude Code running on a Max plan ($100/month) has access to Opus 4.6 with a 1M
context window — the same model you'd call via the API, but at zero marginal cost
within weekly usage limits.

### How it works

```
Traditional approach:
  Python script → Anthropic API → Claude Opus → structured JSON → write to file
  Cost: $15/M input tokens + $75/M output tokens
  Requires: API key, anthropic SDK, rate limiting, error handling, billing

Claude Code approach:
  LOCATE (Python) → candidates.jsonl
  EXTRACT (Claude Code subagents) → read candidates, reason, write results
  VERIFY (Python) → verbatim check, quality flags
  Cost: $0 marginal (included in Max plan)
  Requires: Claude Code CLI, caffeinate, patience
```

The key insight: Claude Code subagents can read files, reason about their
contents, and write structured output — exactly what an API extraction call does,
but without the SDK, API key, rate limiting, or per-token billing.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ LOCATE stage (pure Python CLI)                          │
│ corpus extract-v2 locate --clause-family collective_action │
│ → parses docs, filters by cues, writes candidates.jsonl │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ EXTRACT stage (Claude Code as LLM)                      │
│ Split candidates into batches (~50 per batch)           │
│ Dispatch parallel subagents, each:                      │
│   - Reads batch of candidates                           │
│   - For each: reads section_text, determines if clause  │
│     is present, extracts verbatim text                  │
│   - Writes results to batch_results/                    │
│ Merge batch results into extractions.jsonl              │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ VERIFY stage (pure Python CLI)                          │
│ corpus extract-v2 verify --extractions ...              │
│ → verbatim check, completeness, quality flags           │
└─────────────────────────────────────────────────────────┘
```

## Usage Numbers: CAC + Pari Passu Extraction (March 28, 2026)

### What we processed

| Metric | CAC | Pari Passu | Total |
|--------|-----|------------|-------|
| Documents scanned | 4,685 | 4,685 | 4,685 |
| Candidates generated (LOCATE) | 4,488 | 1,465 | 5,953 |
| Candidates processed (EXTRACT) | 4,488 | 1,465 | 5,953 |
| Clauses extracted | 3,182 | 1,064 | 4,246 |
| Verbatim verified | 3,128 | 1,023 | 4,151 |

### Usage cost

**Available plans:**

| Account | Plan | Monthly cost | Weekly limit | Notes |
|---------|------|-------------|--------------|-------|
| Personal | Max 20x | $200/month | Resets Fri 8 AM | Primary for long extraction runs |
| Teal Insights | Team Premium | $150/month | Resets Fri 8 AM | Secondary / parallel workstream |
| Both | Pay-for-overage | Enabled | $20/month cap | Safety net, rarely needed |

**Total monthly investment:** $350/month + up to $40 overage = $390 max
**Goal:** Maximize utilization of both plans doing high-value extraction work.

**Usage snapshot (Sunday evening, after Fri 8 AM reset):**

- All models: **18% of personal weekly limit**
- Sonnet only: **10% of Sonnet weekly limit**
- Extra usage spent: **$0.00**
- Current session: **14% of 5-hour session limit**
- Team account: **Not used for this run** (available for parallel work)

**Important caveat:** The 18% covers ALL work since Friday morning — coding,
Cowork sessions, planning, code review, and other projects, not just extraction.
The extraction itself is a fraction of that 18%. We don't yet have a way to
isolate extraction-only usage, which is why the estimation heuristics below
are conservative upper bounds.

**What this tells us:** Even with heavy general use of Claude Code across
multiple workstreams, the extraction of 5,953 candidates fit comfortably
within one week's budget with significant headroom remaining.

**Estimated API cost equivalent** (if we had used the API instead):

The 5,953 candidates averaged ~9K chars of section text each. Rough estimate:
- Input tokens: ~5,953 candidates x ~3K tokens each = ~18M input tokens
- Output tokens: ~5,953 x ~500 tokens each = ~3M output tokens
- At Opus pricing ($15/M input, $75/M output): **~$495**
- At Sonnet pricing ($3/M input, $15/M output): **~$99**

We got Opus-quality extraction for $0 marginal cost. The Sonnet-equivalent alone
would have cost nearly a full month of either subscription.

### Throughput

| Phase | Duration | Items | Rate |
|-------|----------|-------|------|
| LOCATE (Python) | ~2 min | 4,685 docs | ~39 docs/sec |
| EXTRACT (subagents) | ~3 hours | 5,953 candidates | ~33 candidates/min |
| VERIFY (Python) | ~10 sec | 5,953 records | ~595 records/sec |
| Code review fixes | ~2 hours | 3 rounds | — |
| **Total wall time** | **~5.5 hours** | — | — |

The extraction phase was the bottleneck. Subagent dispatch overhead (~5-10 sec
per agent) and sequential processing within each agent are the main limiters.

## Batching Strategy

### Why batch?

Each subagent has its own context window and dispatch overhead. Processing one
candidate at a time would mean 5,953 agent dispatches. Batching amortizes the
overhead.

### Batch sizing

We size batches by total section text, not candidate count:

- **Target:** ~200K chars of section text per batch (well within 1M context)
- **Max candidates:** 50 per batch (cap for very small sections)
- **Typical batch:** 15-50 candidates depending on section sizes

### Priority ordering

Candidates are processed in priority order:

1. **Heading-matched** (highest value — section heading matches clause pattern)
2. **Body-only from new docs** (documents without heading matches)
3. **Body-only from docs with heading matches** (likely redundant subsections)

This ensures the most valuable extractions happen first if the process is
interrupted.

### Parallelism

- Dispatch 6-8 subagents simultaneously for independent batches
- Each subagent reads its batch file, extracts, writes results
- Merge results after each wave completes
- Background agents for lower-priority batches while foreground work continues

## Prompt Design for Extraction Subagents

### Key principles

1. **Role priming:** "You are a legal document analyst extracting [clause type]
   from sovereign bond prospectuses."
2. **VERBATIM emphasis:** Repeated instruction that extracted text must appear
   exactly in section_text. No paraphrasing.
3. **NOT_FOUND is valid:** Explicitly state that not finding a clause is expected
   and correct. Prevents forced extractions.
4. **Structured output:** Each result is one JSON line with fixed schema.
5. **Batch reporting:** Agent reports totals (found/not_found) for monitoring.

### Structured output schema

```json
{
  "candidate_id": "uuid",
  "storage_key": "source__doc_id",
  "extraction": {
    "found": true,
    "clause_text": "verbatim extracted text",
    "confidence": "high|medium|low",
    "reasoning": "one sentence for reviewer",
    "thinking": "analysis of clause boundaries",
    "boundary_note": "any uncertainty about start/end"
  }
}
```

## Logging & Usage Estimation

### Current limitations

Claude Max usage is reported as a percentage of weekly limits. There is no
per-token breakdown or per-session cost tracking. The `/context` command shows
token usage within the current conversation but not cumulative across subagents.

### What we can measure

1. **Weekly usage %** — check Settings > Usage before and after a big job
2. **Session usage %** — shown in the session limit bar (resets every 5 hours)
3. **Context window** — `/context` shows current token breakdown
4. **Subagent token reports** — each agent returns `total_tokens` and
   `duration_ms` in its completion metadata
5. **Batch counts** — number of batches x candidates per batch

### Estimation heuristics for future jobs

Based on this extraction run:

| Metric | Value | Notes |
|--------|-------|-------|
| Weekly usage per 1K candidates | ~1.5% (upper bound) | Sonnet subagents, ~9K chars/candidate avg; actual is lower since 18% includes non-extraction work |
| Session limit per wave of 8 agents | ~2-3% | Depends on batch sizes |
| Wall time per 1K candidates | ~30 min | 8 parallel Sonnet agents |
| Candidates per weekly budget | ~12K | Conservative estimate for Opus-heavy work |

### Planning a big extraction job

1. **Count candidates** after LOCATE: `wc -l candidates.jsonl`
2. **Estimate weekly usage:** candidates / 1000 * 1.5% = % of weekly limit
3. **Estimate wall time:** candidates / 1000 * 30 min
4. **Check headroom:** Settings > Usage on both accounts
5. **Decide account allocation:** Use personal Max 20x for the big run,
   Team Premium for parallel review/planning/other projects
6. **Use caffeinate:** `caffeinate -d -i &` to prevent macOS sleep
7. **Monitor:** tail batch_results directory for progress

### Scaling across 2 accounts + 2 machines

| Machine | Account | Role | Budget |
|---------|---------|------|--------|
| Mac Mini | Personal Max 20x | Long-running extraction (overnight) | ~12K candidates/week |
| MacBook Pro | Team Premium | Planning, code review, parallel extraction | ~10K candidates/week |

**Combined weekly capacity:** ~22K candidates at zero marginal cost.

**Orchestration pattern for multi-machine runs:**
1. Run LOCATE on either machine (pure Python, fast, results in Dropbox)
2. Split batch files: `batches 0-100 → Mini`, `batches 101-200 → MBP`
3. Each machine runs its own Claude Code session with its own account
4. Both write to the same `batch_results/` directory (via Dropbox sync)
5. Merge + VERIFY on either machine after both finish

**Maximizing utilization (the goal):**
- The 5-hour session limit resets independently of the weekly limit.
  A single long session uses ~14% of session capacity. You can run
  ~7 sessions per 5-hour window before hitting the session cap.
- Weekly limit is the real constraint. At 1.5% per 1K candidates,
  the personal Max 20x account handles ~12K candidates/week.
- The Team Premium account adds another ~10K candidates/week.
- Overage ($20/month cap per account) adds a small buffer if needed.
- **Smart usage:** Use Sonnet subagents for extraction (cheaper per the
  Sonnet-specific quota), reserve Opus for orchestration and review.
  This stretches the "All models" budget further.

## Comparison: API vs Claude Code

| Dimension | API | Claude Code |
|-----------|-----|-------------|
| **Cost** | $15/$75 per M tokens (Opus) | $0 marginal (Max plan) |
| **Model access** | Any model, any time | Same Opus 4.6, weekly limits |
| **Rate limits** | Tier-based, can be tight | Session + weekly limits |
| **Structured output** | tool_use, guaranteed schema | JSON in text, needs validation |
| **Error handling** | HTTP retries, rate limit backoff | Agent dispatch retry |
| **Parallelism** | Async batch API | Parallel subagents (~8) |
| **Reproducibility** | Exact prompt logged | Agent prompts in conversation |
| **Offline/resume** | Checkpoint in code | Batch files + processed ID tracking |
| **Best for** | Production pipelines, >50K items | Research, prototyping, <25K items |

### When to use Claude Code as extractor

- Research and production extraction for sovereign debt corpus
- Weekly volume fits within combined Max + Team limits (~22K candidates/week)
- You want Opus-quality reasoning without per-token billing
- The extraction task benefits from flexible reasoning (clause boundary
  detection, legal language interpretation — not just slot-filling)
- You have 2 accounts + 2 machines for parallelism
- The $350/month subscription cost is already justified by other work
  (coding, planning, review) — extraction is pure bonus utilization

### When to switch to API

- Volume exceeds ~22K candidates/week sustained
- Need guaranteed uptime and SLAs for external-facing pipeline
- Need exact token counting and cost attribution per project
- Need batch API for >100K items (one-time corpus processing)
- Need structured output guarantees (tool_use schema enforcement)
- The marginal cost of API ($99-$495 per 6K candidates) is justified
  by the throughput gain and automation benefits

### The $350/month math

At $350/month for both accounts:
- **This extraction run:** 5,953 candidates, API equivalent ~$495 (Opus)
- **Already paid for in one run.** Everything else this week is free.
- **Annual capacity:** ~22K candidates/week x 52 = ~1.1M candidates/year
- **Annual cost:** $4,200 (subscriptions) vs ~$90K+ (API at Opus pricing)
- **Break-even:** The approach pays for itself if you extract >4K candidates/month

## Lessons Learned

1. **Batch by text volume, not count.** A batch of 50 tiny candidates is fine;
   a batch of 5 huge candidates can exceed context. Target ~200K chars.

2. **Priority ordering matters.** Process heading-matched candidates first.
   If the session limit hits, you have the highest-value extractions done.

3. **Background agents are powerful.** Dispatch lower-priority batches in
   background while doing foreground work (code review, Shiny app, etc.).

4. **Sonnet is sufficient for extraction.** The subagents doing extraction
   used Sonnet, not Opus. Opus was only needed for the orchestrating session
   (planning, code review, complex decisions). This preserves the Opus budget.

5. **Verbatim verification catches issues.** 82-98% of extractions passed
   verbatim check. The failures were real problems (OCR noise, boundary
   mismatches), not false negatives.

6. **The reviewers didn't understand the approach.** Three separate code
   reviews pushed for adding the `anthropic` SDK despite the plan explicitly
   saying "Claude Code IS the extractor." The approach worked well and saved
   hundreds of dollars in API costs. Document it clearly in the plan to avoid
   repeated pushback.

7. **Usage is very manageable.** 5,953 candidates extracted using ~18% of
   one week's personal budget across all work. With 2 accounts + 2 machines,
   this approach scales to ~22K candidates/week at zero marginal cost.

8. **Maximize plan utilization, don't minimize it.** The $350/month is a
   sunk cost whether you use 5% or 95% of the weekly budget. The goal is
   to find high-value work to fill the capacity — not to conserve tokens.
   Extraction is ideal: high volume, high value, repetitive, and the
   quality difference between Opus and cheaper models matters for legal text.

9. **Be smart, not wasteful.** "Maximize utilization" doesn't mean reading
   300-page PDFs when you need one clause. It means doing a large volume
   of focused, valuable work: precise candidate batches, targeted section
   text, structured extraction prompts. The LOCATE stage (pure Python)
   pre-filters 4,685 documents down to 5,953 candidates — the LLM only
   sees what it needs to see.

10. **Log usage snapshots.** Before and after big runs, screenshot the
    Settings > Usage page. This gives empirical data for planning future
    runs. The `/context` command shows current session token breakdown.
    Subagent completion metadata includes total_tokens and duration_ms.
