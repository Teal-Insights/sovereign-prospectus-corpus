# Multi-Model Code Review: Council of Experts

**Last updated:** 2026-04-11
**Context:** Patterns learned during the Spring Meetings sprint, where 15+
independent reviews across 3 AI models caught critical bugs that would have
destroyed a 7-hour overnight pipeline run.

## Why multi-model review works

Each model has different blind spots. In our testing:

| Model | Strength | Blind spot |
|-------|----------|------------|
| **Claude (subagents)** | Deep architectural reasoning, protocol compliance | Can miss low-level concurrency bugs |
| **Gemini CLI** | Excellent at finding crash/data-loss scenarios | Less focused on style/consistency |
| **Codex CLI** | Strong on concurrency, timeouts, edge cases | Sandbox limits prevent execution-based verification |

**Real example from this sprint:**
- Claude found: parse_status divergence, FTS not on MotherDuck, rate-limit misclassification
- Gemini found: **infinite crash loop** on pool restart (same PDF resubmitted forever)
- Codex found: **mass data loss** (submit-all pattern), **dead timeout** code, catalog alias bug
- External Claude instances found: **pool shutdown hangs forever** on C-extension deadlock, **poison pill** crash loop, **validation script passes bad runs**

Every reviewer caught something the others missed. The convergence on the top
issues (3+ reviewers independently flagged the same pool management bugs)
confirmed the findings were real, not hallucinated.

---

## Invocation Patterns

### Claude Code (subagents from within a session)

Use the built-in `Agent` tool with `subagent_type: "superpowers:code-reviewer"`.
Each subagent gets its own context window and returns findings to the parent.

```
# In Claude Code, use the Agent tool:
Agent(
  subagent_type="superpowers:code-reviewer",
  description="Review overnight parse resilience",
  prompt="Review scripts/docling_reparse.py focusing on...",
  run_in_background=True
)
```

**Strengths:** Deep file access, can read multiple files, understands project context from CLAUDE.md.
**Limits:** Same model as the parent session. For true diversity, spawn external instances.

### Claude Code (fresh external instances)

Spawn a completely independent Claude Code process via Bash. Best for
adversarial review (fresh context, no shared assumptions).

```bash
# Non-interactive review with file access
claude -p "Review scripts/docling_reparse.py for overnight resilience..." \
  --allowedTools "Read,Grep,Glob" \
  --model opus \
  --output-format json \
  --no-session-persistence

# Pipe a diff for focused review
git diff main...HEAD | claude -p "Review this diff for bugs..." \
  --allowedTools "Read,Grep,Glob" \
  --output-format json

# Structured output with JSON schema
claude -p "Review src/ for issues" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"issues":{"type":"array","items":{"type":"object","properties":{"file":{"type":"string"},"severity":{"type":"string","enum":["critical","important","suggestion"]},"description":{"type":"string"}},"required":["file","severity","description"]}}}}'

# Fast, bare-mode review (skips CLAUDE.md, hooks, plugins)
claude --bare -p "Review this code" \
  --allowedTools "Read,Grep,Glob" \
  --model sonnet \
  --no-session-persistence
```

**Key flags:**
| Flag | Purpose |
|------|---------|
| `-p "prompt"` | Non-interactive mode (required) |
| `--model sonnet` / `opus` | Model selection |
| `--output-format json` | Machine-parseable output |
| `--json-schema '{...}'` | Structured output enforcement |
| `--allowedTools "Read,Grep,Glob"` | Read-only tool access |
| `--no-session-persistence` | Don't save session to disk |
| `--bare` | Skip CLAUDE.md, hooks, plugins (faster) |
| `--continue` | Continue most recent conversation |
| `--max-budget-usd 5.00` | Cost cap |
| `--append-system-prompt "..."` | Add custom instructions |

### Gemini CLI

Non-interactive mode via `-p` flag with `--yolo` for auto-approval of tool
calls (file reads, shell commands).

```bash
# Basic review with file access
gemini -p "Review scripts/docling_reparse.py for resilience..." --yolo

# Read-only review (safest)
gemini -p "Review this codebase for bugs..." --approval-mode plan

# JSON output for parsing
gemini -p "Review and report findings as JSON" \
  --output-format json \
  --approval-mode plan

# Specific model
gemini -m gemini-2.5-flash -p "Quick review of this diff"
```

**Key flags:**
| Flag | Purpose |
|------|---------|
| `-p "prompt"` | Non-interactive/headless mode |
| `--yolo` / `--approval-mode yolo` | Auto-approve all tools |
| `--approval-mode plan` | Read-only (safest for review) |
| `--output-format json` | Single JSON object output |
| `--output-format stream-json` | NDJSON streaming events |
| `-m gemini-2.5-flash` | Model override |
| `--sandbox` | Additional sandbox isolation |

**Important:** The prompt must be the direct value of `-p`:
```bash
# CORRECT:
gemini -p "Your prompt here" --yolo

# WRONG (fails with "Not enough arguments following: p"):
gemini --yolo -p "Your prompt here"
```

**Config files:** `GEMINI.md` (project-level) or `~/.gemini/GEMINI.md` (global)
for persistent review instructions. Supports `@path/to/file` imports.

**Rate limits:** 1,000 requests/day (free), 1,500 (Pro), 2,000 (Ultra).

### Codex CLI

Non-interactive mode via `codex exec`. The dedicated `codex review` subcommand
exists but has limitations (cannot combine `--base` with a custom prompt).

```bash
# Pipe diff for review (recommended pattern)
git diff main...HEAD | codex exec \
  -s read-only \
  "Review this diff for bugs, security, and correctness."

# With structured JSON output
git diff main...HEAD | codex exec \
  -s read-only \
  --output-schema ./review_schema.json \
  -o /tmp/codex_review.json \
  "Review the diff. Report findings as structured JSON."

# With project-specific instructions
git diff main...HEAD | codex exec \
  -s read-only \
  -c 'developer_instructions="Focus on concurrency bugs and data loss."' \
  "Review this code change."

# Built-in review (no custom prompt, but uses AGENTS.md)
codex review --base main
codex review --uncommitted
codex review --commit abc123
```

**Key flags:**
| Flag | Purpose |
|------|---------|
| `exec "prompt"` | Non-interactive execution |
| `-s read-only` | Read-only sandbox (safest) |
| `--json` | NDJSON event stream output |
| `--output-schema path` | Structured JSON output schema |
| `-o path` | Write final message to file |
| `--ephemeral` | Don't persist session |
| `-m gpt-5.3-codex` | Model selection |
| `-c key=value` | Override config inline |
| `--full-auto` | Workspace-write + auto-approve |

**The `--base` + PROMPT limitation:** `codex review --base main "custom prompt"`
does NOT work (GitHub issue #7825, closed as not planned). Workaround: pipe
the diff to `codex exec` instead.

**Config files:** `AGENTS.md` (project root or `~/.codex/AGENTS.md`) for
persistent review instructions. Supports hierarchy from global to project level.

**Auth:** Set `CODEX_API_KEY` environment variable. OAuth doesn't work in
non-interactive mode.

---

## Recommended Review Orchestration

### From within a Claude Code session

Dispatch all reviews in parallel using Bash background commands:

```python
# 1. Claude subagents (use Agent tool with run_in_background=True)
Agent(subagent_type="superpowers:code-reviewer", prompt="...", run_in_background=True)

# 2. Gemini (via Bash tool)
Bash("gemini -p '...' --yolo 2>&1", run_in_background=True)

# 3. Codex (via Bash tool, pipe diff)
Bash("git diff main...HEAD | codex exec -s read-only '...' 2>&1", run_in_background=True)

# 4. Fresh Claude instance (via Bash tool)
Bash("claude -p '...' --allowedTools 'Read,Grep,Glob' --model sonnet --output-format json 2>&1", run_in_background=True)
```

### Review prompt template

```
You are reviewing [COMPONENT] for [PURPOSE]. The code runs [CONTEXT].

Read these files: [FILE LIST]

Focus on:
1. [SPECIFIC CONCERN 1]
2. [SPECIFIC CONCERN 2]
3. [SPECIFIC CONCERN 3]

Report findings as CRITICAL / IMPORTANT / SUGGESTION with file:line references.
[Optional: This code has been through N prior reviews. You are looking for
what they missed.]
```

### Triage pattern

After all reviews complete:
1. Extract CRITICAL findings from each
2. Check for **convergence** — issues flagged by 2+ reviewers are almost certainly real
3. Fix all CRITICALs immediately
4. Fix IMPORTANTs that affect the immediate workflow
5. File issues for deferred SUGGESTIONs
6. Commit fixes, push, optionally re-review the fixes

---

## Practical Lessons

1. **Each model finds different things.** Don't assume one review is enough.
   Claude is best at protocol/architecture compliance. Gemini excels at
   crash/data-loss scenarios. Codex catches concurrency and timeout bugs.

2. **Provide specific focus areas.** Generic "review this code" produces
   generic findings. "Check if a hung worker can stall the entire 7-hour
   run" produces actionable results.

3. **Tell later reviewers what earlier ones found.** "This code has been
   through 12 reviews. Prior reviews found and fixed: [list]. Your job is
   to find what they all missed." This focuses attention on gaps.

4. **Convergence validates findings.** When 3 reviewers independently flag
   the same issue, it's real. When only 1 reviewer flags something, verify
   before fixing — it may be a hallucination.

5. **External instances are better than subagents for adversarial review.**
   A subagent shares context with the parent session that wrote the code.
   A fresh `claude -p` instance or Gemini/Codex has no shared assumptions.

6. **Run reviews in parallel.** All three CLIs support background execution.
   A round of 6 reviews takes 3-5 minutes wall-clock, not 30 minutes serial.

7. **The `codex review` subcommand is limited.** Use `codex exec` with piped
   diffs for custom prompts. Use `AGENTS.md` for persistent review standards.

8. **Gemini's `-p` flag is positional-sensitive.** The prompt must immediately
   follow `-p`. Put other flags after the prompt string.

---

## Cost Estimates

For a typical code review session (6 parallel reviews on a medium PR):

| Reviewer | Tokens (approx) | Cost |
|----------|-----------------|------|
| Claude subagent (Opus) | ~50k | ~$0.75 |
| Claude external (Sonnet) | ~30k | ~$0.10 |
| Gemini (free tier) | ~40k | $0.00 |
| Codex (API key) | ~100k | ~$0.50 |
| **Total per round** | | **~$1.35** |

Two rounds of review on a critical overnight pipeline: ~$3-5. Extremely
cheap insurance against a failed 7-hour run.
