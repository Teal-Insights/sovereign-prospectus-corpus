# Mac Mini Handoff — March 29, 2026

## Pre-flight: MacBook Air (do this FIRST, before touching the Mac Mini)

### 1. Ensure everything is pushed from MacBook Air

```bash
cd ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus
git status          # must be clean
git push            # push any unpushed commits
git log --oneline -3  # note the latest commit SHA
```

### 2. Create the MacBook Air analysis branch NOW

This prevents branch collisions later. The Air works on its own branch:

```bash
git checkout -b feature/roundtable-demo
git push -u origin feature/roundtable-demo
```

The Air stays on `feature/roundtable-demo` for all Quarto/Shiny/analysis work.
The Mini will use `feature/full-extraction-round-1` (created during execution).

### 3. Note what you expect to see

After the Mini finishes each family, results appear in Dropbox at:
```
~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/extracted_v2/<run_id>/
├── document_classification/
│   ├── classification.jsonl
│   └── COMPLETE.json          ← safe to read when this exists
├── governing_law/
│   ├── candidates.jsonl
│   ├── verified.jsonl
│   └── COMPLETE.json
├── ...
└── RUN_MANIFEST.json          ← shows which families are done
```

**Rule: Only read directories that have COMPLETE.json.**

---

## On the Mac Mini

### 4. Clone the repo fresh (if not already done)

```bash
mkdir -p ~/Projects
cd ~/Projects

# If sovereign-prospectus-corpus already exists here, just pull:
# cd sovereign-prospectus-corpus && git pull && uv sync

# Otherwise clone fresh:
git clone git@github.com:Teal-Insights/sovereign-prospectus-corpus.git
cd sovereign-prospectus-corpus
```

### 5. Set up the data symlink

```bash
# Create the symlink to Dropbox data
ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data

# Verify it works
ls data/parsed_docling/ | head -5    # should see .md files
ls data/parsed/ | head -5            # should see .jsonl files
ls data/pdip/ | head -5              # should see annotations
```

### 6. Make Dropbox data available offline

**CRITICAL:** Right-click `~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/`
in Finder → "Make available offline". Otherwise Smart Sync may evict files
mid-extraction.

### 7. Build the environment

```bash
uv sync
uv run pytest -v 2>&1 | tail -5     # should see "XXX passed"
uv run corpus extract-v2 --help      # should show locate, verify, classify
```

### 8. Verify the plan is accessible

```bash
cat docs/superpowers/plans/2026-03-29-full-extraction.md | head -20
cat docs/meta-learning-round-0.md 2>/dev/null || echo "Will be created during execution"
```

### 9. Launch Claude Code

```bash
cd ~/Projects/sovereign-prospectus-corpus
claude --dangerously-skip-permissions
```

### 10. Paste the session prompt

```
Read the implementation plan at docs/superpowers/plans/2026-03-29-full-extraction.md.
Read the design spec at docs/superpowers/specs/2026-03-29-full-extraction-design.md.
Read docs/meta-learning-round-0.md if it exists (lessons from prior extraction).

Execute the plan task by task using subagent-driven development.

After the prerequisite tasks (Tasks 0-13) are complete, proceed to Round 1 extraction:
1. Document classification (separate workstream)
2. governing_law
3. sovereign_immunity
4. negative_pledge
5. events_of_default (if budget allows after LOCATE count check)

BEFORE any EXTRACT work: run LOCATE for ALL Round 1 families and report
candidate counts + estimated wall time.

After EACH family completes:
- Run: uv run python3 scripts/round_report.py --family <family> --run-id <run_id>
- Print the Quick Status summary
- Continue to next family

After ALL Round 1 families complete:
- Run the full round report
- Commit reports to git and push
- STOP and wait for my review before Round 2

Use caffeinate -d -i to prevent sleep.
Process clause families using the Claude Code as extractor approach
(read each candidate, extract verbatim, write results — see docs/claude-code-as-extractor.md).
```

### 11. Monitor from iPhone

Open Claude Code remote control on your iPhone. You'll see:
- Task progress as the plan executes
- LOCATE candidate counts
- Per-family extraction progress
- Round report status summaries

Reply "go" to continue between families, or give feedback.

---

## Branch Coordination Rules

| Machine | Branch | Writes to data/ | Pushes code |
|---------|--------|-----------------|-------------|
| Mac Mini | `feature/full-extraction-round-1` | YES (extraction results) | YES (prerequisites + commits) |
| MacBook Air | `feature/roundtable-demo` | NO (reads only) | YES (Quarto, Shiny, analysis) |

**NEVER:**
- Work on the same branch from both machines
- Write to `data/extracted_v2/` from the MacBook Air
- Pull the Mini's branch on the Air (or vice versa) while work is in progress

**SAFE:**
- Both machines push to their own branches independently
- MacBook Air reads extraction results via Dropbox (check COMPLETE.json first)
- Both can merge to main independently AFTER their work is done (Mini first, then Air)

---

## Workflow Log Template

After the session, fill this in to capture what worked and what didn't:

### Setup
- [ ] MacBook Air pushed clean, created feature/roundtable-demo
- [ ] Mac Mini cloned/pulled, symlink created, env built
- [ ] Dropbox data marked offline
- [ ] Tests pass on Mac Mini
- [ ] Claude Code launched on Mac Mini

### Execution
- [ ] Prerequisite tasks (0-13) completed
- [ ] LOCATE candidate counts reported
- [ ] Document classification completed
- [ ] governing_law completed
- [ ] sovereign_immunity completed
- [ ] negative_pledge completed
- [ ] events_of_default completed (or deferred)
- [ ] Round 1 report generated

### What worked well
- (fill in after)

### What went wrong / needs improvement
- (fill in after)

### Dropbox sync observations
- Did results appear on Air promptly?
- Any conflicted copies?
- Any Smart Sync eviction issues?

### Timing actuals (for future estimation)
- Prerequisites build time: ___
- LOCATE time (all families): ___
- Classification time: ___
- Per-family extraction times: ___
- Total session time: ___
- Sessions used (5-hour limit): ___
