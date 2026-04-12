# Council of Experts: Multi-Model Review Pattern

**Last updated:** 2026-04-11
**Origin:** Patterns developed during the Spring Meetings sprint, where 15+
reviews across 3 AI models caught critical bugs in a 7-hour overnight pipeline.

## The pattern

Use the three best AI coding models — Claude Opus, GPT-5.4, and Gemini 2.5
Pro — as independent reviewers at key gates in the development workflow.
Each model has different strengths and blind spots. The combination catches
what any single model misses.

### When to invoke the Council

| Gate | After | Before | What to review |
|------|-------|--------|----------------|
| **Spec review** | `superpowers:brainstorming` | `superpowers:writing-plans` | Design doc / spec |
| **Plan review** | `superpowers:writing-plans` | Implementation | Implementation plan |
| **PR review** | Implementation complete | Merge / ship | Code changes |
| **Ad-hoc** | Any time | Any time | Specific aspect, question, or concern |

The main Claude session creates a focused review prompt, dispatches it to
all three models in parallel, triages findings, and fixes everything that
fits the project intent.

### Why this works

While adding review time per step, it dramatically reduces rework:
- Errors caught at the spec stage cost minutes to fix; the same errors
  caught after implementation cost hours.
- Three models find genuinely complementary things. In our testing:
  - **Claude** excels at protocol compliance, architecture, and cross-file consistency
  - **Gemini** excels at crash scenarios, data loss paths, and edge cases
  - **Codex** excels at concurrency bugs, timeout issues, and structured analysis
- When 2+ models independently flag the same issue, it's almost certainly
  real (convergence validation). Single-model findings need verification.
- Multi-round reviews converge: tell reviewers to flag when they're only
  finding nits and it's ready to move on.

---

## Model configuration

All three use top-tier subscriptions with maximum reasoning depth. There is
no marginal cost per review — use the best models every time.

### Claude Code (Max + Team Premium)

| Setting | Value |
|---------|-------|
| Model | `opus[1m]` (Opus 4.6, 1M context) |
| Thinking | `--effort max` |
| Config | `~/.claude/settings.json` → `"model": "opus[1m]"` |

**Invocation from within a session (subagent):**
```python
# Background subagent — shares project context
Agent(
  subagent_type="superpowers:code-reviewer",
  prompt="Review ...",
  run_in_background=True
)
```

**Invocation as fresh external instance (adversarial):**
```bash
claude --model "opus[1m]" --effort max \
  -p "Review ..." \
  --allowedTools "Read,Grep,Glob" \
  --output-format json \
  --no-session-persistence
```

**Piping content:**
```bash
git diff main...HEAD | claude -p "Review this diff..." --model sonnet
```

### Codex CLI (ChatGPT Pro $200)

| Setting | Value |
|---------|-------|
| Model | `gpt-5.4` (GPT-5) |
| Reasoning | `model_reasoning_effort = "xhigh"` |
| Config | `~/.codex/config.toml` |

**Primary invocation (pipe diff):**
```bash
git diff main...HEAD | codex exec \
  -s read-only \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="xhigh"' \
  "Review this diff for bugs, security, and correctness. Report CRITICAL/IMPORTANT/SUGGESTION with file:line."
```

**Built-in review (no custom prompt, uses AGENTS.md):**
```bash
codex review --base main
```

**With structured output:**
```bash
git diff main...HEAD | codex exec \
  -s read-only \
  --output-schema ./review_schema.json \
  -o /tmp/review.json \
  "Review this diff."
```

**Limitation:** `codex review --base main` cannot combine with a custom
prompt (GitHub issue #7825). Use `codex exec` with piped diff instead.

### Gemini CLI (Gemini Ultra $200)

| Setting | Value |
|---------|-------|
| Model | `gemini-3.1-pro-preview` (Gemini 2.5 Pro) |
| Thinking | Built-in (no separate flag) |
| Config | `~/.gemini/settings.json` |

**Primary invocation:**
```bash
gemini -m gemini-3.1-pro-preview \
  -p "Review scripts/docling_reparse.py for overnight resilience. Report CRITICAL/IMPORTANT/SUGGESTION." \
  --yolo
```

**Read-only review (safest):**
```bash
gemini -p "Review this codebase for bugs..." --approval-mode plan
```

**JSON output:**
```bash
gemini -p "Review and report findings" --output-format json --approval-mode plan
```

**Important:** The prompt must immediately follow `-p`. Put other flags after:
```bash
# CORRECT:
gemini -p "prompt here" --yolo
# WRONG:
gemini --yolo -p "prompt here"
```

---

## Workflow: Spec review

After brainstorming produces a spec, before writing the implementation plan.

**1. Main session creates the review prompt:**
```
Review this spec at docs/superpowers/specs/YYYY-MM-DD-topic-design.md.

Check:
1. Are the requirements complete and unambiguous?
2. Are there contradictions between sections?
3. Is the scope appropriate for a single implementation plan?
4. Are the technical decisions sound?
5. What's missing that will cause problems during implementation?

Report CRITICAL / IMPORTANT / SUGGESTION.
```

**2. Dispatch to all three models** (from within the session, in parallel):
```python
# Claude subagent
Agent(subagent_type="superpowers:code-reviewer", prompt="...", run_in_background=True)

# Gemini
Bash("gemini -p '...' --yolo", run_in_background=True)

# Codex
Bash("cat docs/superpowers/specs/the-spec.md | codex exec -s read-only '...'", run_in_background=True)
```

**3. Triage:** Fix all reasonable findings. File issues for deferred items.

---

## Workflow: Plan review

After writing-plans produces the implementation plan.

**Same dispatch pattern.** Prompt focuses on:
- Will these steps actually achieve the spec's requirements?
- Are there missing steps or wrong ordering?
- Are the time estimates realistic?
- What will go wrong during execution?

---

## Workflow: PR / code review

After implementation, before merge.

**Prompt template:**
```
You are reviewing [COMPONENT] for [PURPOSE]. The code runs [CONTEXT].

Read these files: [FILE LIST]

Focus on:
1. [SPECIFIC CONCERN]
2. [SPECIFIC CONCERN]
3. [SPECIFIC CONCERN]

Report CRITICAL / IMPORTANT / SUGGESTION with file:line references.
```

**For later rounds:** "This code has been through N prior reviews. They
found and fixed: [list]. Your job is to find what they all missed."

**Convergence signal:** When reviewers are only finding nits (formatting,
naming, comments), the code is ready. Tell the reviewers to explicitly
state "no more substantive findings" when they reach that point.

---

## Workflow: Ad-hoc review

For specific questions, design decisions, or risk assessments:

```
We're considering [APPROACH] for [PROBLEM]. The alternatives are [A, B, C].

Given [CONTEXT], which approach is best? What risks does each carry?
What would you recommend and why?
```

Or for a specific file/function:
```
Review [FILE:FUNCTION] specifically for [CONCERN]. Ignore everything else.
```

---

## Triage protocol

After all reviews complete:

1. **Extract** all CRITICAL and IMPORTANT findings from each reviewer
2. **Check convergence** — issues flagged by 2+ reviewers are almost certainly real
3. **Fix all CRITICALs** immediately
4. **Fix IMPORTANTs** that fit the project intent
5. **Evaluate SUGGESTIONs** — fix the easy ones, defer the rest
6. **File issues** for anything consciously deferred (with rationale)
7. **Commit fixes, push** — optionally run another review round on the fixes

**False positive handling:** If a finding doesn't apply (wrong assumption,
out of scope, already handled elsewhere), note the rationale and move on.
Don't fix things that make the code worse to satisfy a reviewer.

---

## Practical lessons from the Spring Meetings sprint

1. **15+ reviews across 3 models caught 8 critical bugs** that would have
   destroyed a 7-hour overnight run. No single model found all of them.

2. **Each model has genuine blind spots.** Claude missed the pool crash loop.
   Gemini missed the dead timeout code. Codex missed the rate-limit handling.
   Together they caught everything.

3. **External instances are better than subagents for adversarial review.**
   Subagents share context with the session that wrote the code. A fresh
   instance has no shared assumptions.

4. **Specific prompts produce better results.** "Check if a hung worker can
   stall the 7-hour run" beats "review for bugs."

5. **Multi-round reviews converge.** Round 1 finds the big issues. Round 2
   finds what Round 1 missed. Round 3 typically finds only nits — that's
   the signal to stop.

6. **The time investment pays for itself.** The reviews added ~2 hours to
   the sprint. Without them, the overnight parse would have failed in at
   least 3 different ways, each requiring hours of debugging and re-running.

---

## Reference: CLI quick-reference

| Action | Claude | Codex | Gemini |
|--------|--------|-------|--------|
| Non-interactive | `-p "prompt"` | `exec "prompt"` | `-p "prompt"` |
| Best model | `--model "opus[1m]"` | `-m gpt-5.4` | `-m gemini-3.1-pro-preview` |
| Max thinking | `--effort max` | `-c model_reasoning_effort="xhigh"` | (built-in) |
| Read-only | `--allowedTools "Read,Grep,Glob"` | `-s read-only` | `--approval-mode plan` |
| Auto-approve | `--dangerously-skip-permissions` | `--full-auto` | `--yolo` |
| JSON output | `--output-format json` | `--json` | `--output-format json` |
| Pipe stdin | `cat file \| claude -p` | `cat file \| codex exec` | (use -p with file reads) |
| Config file | `CLAUDE.md` | `AGENTS.md` | `GEMINI.md` |
