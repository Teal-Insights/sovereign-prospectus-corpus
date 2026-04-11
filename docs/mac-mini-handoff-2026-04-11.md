# Mac Mini Handoff — 2026-04-11 (Spring Meetings Sprint, Docling Migration)

**Predecessor:** `docs/mac-mini-handoff-2026-03-29.md` — same workflow pattern, different task.
**Session context:** `SESSION-HANDOFF.md` (mandatory read before starting)
**Sprint deadline:** Monday 2026-04-13 (IMF/World Bank Spring Meetings)

## Why this handoff exists

The MacBook Air started a full reframe of issue #72 (Docling migration) but the actual Docling work — smoke-testing the bug fix and running the overnight bulk parse — belongs on the Mac Mini M4 Pro (much heftier, already has Docling installed from the March run). This doc is the step-by-step for switching machines **without** re-learning the lessons from the late-March extraction sprint.

## Lessons from the March 29 handoff (DO NOT FORGET)

1. **The Mac Mini does NOT work inside the Dropbox folder.** It clones the repo to `~/Projects/sovereign-prospectus-corpus` and uses a **symlink** `data → ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data`. This separates code (git) from data (Dropbox sync). Working inside Dropbox causes git lockfile churn, partial sync corruption, and random `uv` venv failures.

2. **Dropbox `data/` must be "Available offline."** Right-click `~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/` in Finder → **Make available offline**. Smart Sync will evict files mid-extraction otherwise, and you'll get silent read failures during the overnight parse.

3. **Each machine works on its own feature branch.** Never the same branch from both. Never `main` from either.

4. **Only read directories that have `COMPLETE.json`** (when reading results produced by the other machine via Dropbox sync). For the Docling bulk parse, the equivalent gate is reading `data/parsed_docling/_summary.json` only after the parse run has finished (`"shutdown_requested": false`).

5. **Dropbox sync can take minutes to propagate** code commits between machines. Always `git pull` on the receiving machine — don't rely on Dropbox to carry git state.

6. **MacBook Air stays read-only on `data/extracted_v2/`-style outputs.** The Air does analysis / Quarto / writing; the Mini does compute. This sprint is slightly different because the overnight parse is a compute task, but the discipline is the same: the Mini is the authoritative writer, the Air reads.

---

## Pre-flight on the MacBook Air (do this NOW, before closing)

These steps are already done by the end of this session; listed here so you can verify nothing got missed.

### ✅ 1. PR #74 is open and pushed

```bash
gh pr view 74
# expected: Teal-Insights/sovereign-prospectus-corpus#74
# branch: feature/session-handoff-mac-mini-switch
# contains spec v1 (e999d45c) + SESSION-HANDOFF rewrite + this handoff doc
```

### ✅ 2. Local `main` reset to match `origin/main`

Local main had diverged by 1 commit (`e999d45c`, the spec v1) which is preserved on the feature branch. Resetting local main prevents future `git pull --ff-only` failures on this laptop.

```bash
git checkout main
git reset --hard origin/main      # safe: e999d45c is on feature branch
git log --oneline -3              # should match origin
git checkout feature/session-handoff-mac-mini-switch
```

### ✅ 3. Everything pushed to GitHub

```bash
git status                        # should be clean (or only show the deliberately-untracked files listed in SESSION-HANDOFF.md)
git log --oneline origin/main..HEAD   # should show 2 commits on the feature branch
```

Untracked files NOT to commit (flagged in SESSION-HANDOFF.md):
- `.claude/settings.local.json` (personal)
- `demo/data/*.csv`, `demo/shiny-app/data/*.csv` (79M each, unknown owner, left alone)
- `demo/shiny-app/rsconnect-python/` (deploy config)
- `scripts/process_cac_batches_101_150.py` (related to issue #70, not this sprint)

### ✅ 4. Note the latest hashes so you can verify on the Mac Mini

Current state (at time of handoff write):
- `origin/main` latest: `a7ac1a55` (SESSION-HANDOFF Task 2 end)
- `feature/session-handoff-mac-mini-switch`: `e999d45c` (spec v1) + `70149d70` (handoff) + this commit
- PR #74: open, ready to merge

After Mac Mini merges PR #74 (squash), `origin/main` will be a new hash with spec v1 + SESSION-HANDOFF + this handoff doc. Record it when you do.

---

## On the Mac Mini

### Step 1. Update the existing repo at `~/Projects/sovereign-prospectus-corpus`

(It should already exist from the March run. If not, clone fresh — see "First-time setup" below.)

```bash
cd ~/Projects/sovereign-prospectus-corpus
git fetch origin
git status                                    # verify clean before switching branches
git checkout main
git pull --ff-only                            # pull any commits since March
git checkout feature/session-handoff-mac-mini-switch    # check out the open PR branch
git pull --ff-only                            # sync the feature branch
```

### Step 2. Merge PR #74 (the session handoff + spec v1)

This is a docs-only PR, safe to admin-merge. You do not need bot review for an operational handoff.

```bash
gh pr merge 74 --squash --admin --delete-branch
git checkout main
git pull --ff-only                            # fast-forward to the new squash commit
git log --oneline -3                          # verify the squash landed
```

### Step 3. Verify the symlink

The `data/` entry in the Mac Mini repo should be a symlink to Dropbox, not a real directory.

```bash
ls -la data
# expected output (paraphrased):
# data -> /Users/<you>/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data
```

If it's a real directory or missing, fix it:

```bash
# If a stale real directory exists from a bad setup, MOVE it aside first — never delete
# without inspection in case there's unique state:
# mv data data.stale.$(date +%s)

ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data
ls -la data                                   # verify symlink
ls data/parsed_docling/ | head -5             # should see the existing (broken) Docling outputs
ls data/original/nsm__* | head -5             # should see NSM PDFs
```

### Step 4. Confirm Dropbox `data/` is "Available offline"

In **Finder**, navigate to `~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/`, right-click the `data/` folder, select **Make Available Offline** if it isn't already. Wait for Dropbox to finish syncing if any files are still downloading.

**This is non-negotiable for the overnight parse.** Smart Sync eviction mid-run will silently corrupt reads.

### Step 5. Verify the canonical venv

```bash
echo $UV_PROJECT_ENVIRONMENT                  # should point to ~/.local/venvs/sovereign-corpus or similar
uv sync --all-extras                          # sync any dependency drift since March
uv run python -c "import sys, duckdb, polars, pytest; print(sys.executable, duckdb.__version__, polars.__version__, pytest.__version__)"
# expected: Python 3.12.x, duckdb 1.4.4, polars >=1.39, pytest 9.x
```

### Step 6. Verify Docling is installed

```bash
uv run python -c "import docling; print(docling.__version__)"
# expected: some version number, probably 2.x
```

If Docling is NOT installed in the canonical venv (possible — the March run may have used a one-off install):

```bash
uv add docling
uv sync --all-extras
# first sync downloads ~1-2 GB of models; give it a few minutes
uv run python -c "import docling; print(docling.__version__)"
```

### Step 7. Smoke-test that the repo is healthy

```bash
uv run pytest -v 2>&1 | tail -10              # expect ~397 passing
uv run ruff check src/ tests/                  # expect clean
uv run corpus --help                           # verify CLI
```

### Step 8. Launch Claude Code

```bash
cd ~/Projects/sovereign-prospectus-corpus
caffeinate -d -i claude --dangerously-skip-permissions
```

`caffeinate -d -i` keeps the Mac Mini awake during long operations (essential for the overnight parse).

### Step 9. Paste this session prompt

```
Read SESSION-HANDOFF.md in full — it contains the state of a brainstorm
session that was paused on the MacBook Air for a machine switch.

Then read docs/mac-mini-handoff-2026-04-11.md for the Mac Mini-specific
setup lessons from the March run.

Then read docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md
(spec v1 — being revised as v2 after the smoke test you're about to run).

We are mid-brainstorm. The immediate next action is Step 0 from the handoff:
smoke-test the Docling bug fix on a known-broken PDF
(data/original/nsm__101126915_20200330172131895.pdf — confirmed to have
dropped 46 of 58 pages in the March 28 run due to a
TextItem/SectionHeaderItem-only iteration bug in scripts/docling_reparse.py).

Locked-in decisions (do NOT re-litigate):
- Docling for all PDFs, PyMuPDF nowhere, EDGAR stays on BeautifulSoup
- LuxSE adapter committed unconditionally (no curl-test gate)
- LSE RNS dropped (DRC confirmed on NSM via live API)
- Single overnight bulk parse of all 2,291 NSM+PDIP + new incremental + LuxSE
- Delete data/parsed_docling/ entirely before the overnight run (broken outputs)
- Markdown rendering in the Streamlit detail panel is a Monday requirement

Your Step 0 smoke test sequence:
1. Verify Docling API for per-page iteration using context7
   (mcp__plugin_context7_context7__query-docs for Docling DocumentConverter
   and doc.pages iteration)
2. Reproduce the bug on nsm__101126915_20200330172131895.pdf — expect
   emitted pages [0,1,2,3,4,5,6,7,23,40] out of 58 with the stale script logic
3. Write the fix (iterate by doc.pages, not by item type)
4. Verify the fix on the same file — expect all 58 pages with content
5. Spot check on one PDIP with heavy tables and one long NSM supplementary
6. Measure elapsed time per doc — should be within 2x of the 9.7s/doc baseline

After the smoke test passes:
7. Rewrite spec v2 at
   docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md
   incorporating the confirmed bug fix + all accepted review findings from
   SESSION-HANDOFF.md's "Spec v1 → v2 rewrite" section
8. Stop and ask me to approve v2 before invoking superpowers:writing-plans

DO NOT work on main. Create feature/docling-bug-fix-and-sprint-v2
(or similar) and work there. Respect the branch coordination rules in
docs/mac-mini-handoff-2026-04-11.md.

Use caffeinate -d -i for any long operations.
```

### Step 10. Monitor from your phone (optional)

Open Claude Code remote control on iPhone. You'll see:
- The smoke test step-by-step
- Docling API findings
- Bug reproduction + fix verification
- Spec v2 draft
- Your approval gate before execution

---

## Branch coordination rules (same as March 29, updated for this sprint)

| Machine | Branch | Writes to `data/` | Pushes code |
|---------|--------|-------------------|-------------|
| **Mac Mini** | `feature/docling-bug-fix-and-sprint-v2` (or whatever the new session picks) | YES (overnight parse writes to `data/parsed_docling/`) | YES |
| **MacBook Air** | If you open it: `feature/any-analysis-work-not-this-sprint` | NO (read-only on any sprint output) | YES for non-sprint work only |

**NEVER:**
- Work on the same branch from both machines
- Push to `main` from either machine (always feature branches + PRs)
- Edit sprint code from the MacBook Air while the Mac Mini is executing
- Pull the Mac Mini's feature branch on the Air while the Mac Mini is mid-work
- Delete `data/parsed_docling/` on the Air while the Mac Mini is parsing
- Commit to `main` under any circumstances — there's a pre-commit hook that blocks it

**SAFE:**
- Both machines `git pull --ff-only` on `main` after a PR merges
- Mac Mini writes to `data/parsed_docling/` during overnight parse (no one else is touching it)
- MacBook Air reads results ONLY after the parse finishes and `_summary.json` shows clean completion
- Both machines push their own feature branches independently

---

## First-time setup on Mac Mini (if `~/Projects/sovereign-prospectus-corpus` does NOT exist)

Skip this if the March 29 setup is still intact. Run this only if the Mac Mini repo is gone.

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone git@github.com:Teal-Insights/sovereign-prospectus-corpus.git
cd sovereign-prospectus-corpus

# Data symlink
ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data
ls -la data

# Make Dropbox data offline (Finder right-click)

# Environment
uv sync --all-extras
uv run pytest -v 2>&1 | tail -5

# Docling
uv run python -c "import docling; print(docling.__version__)" || uv add docling && uv sync --all-extras

# Launch
caffeinate -d -i claude --dangerously-skip-permissions
```

---

## What changes if the Mac Mini session finds something the MacBook Air session missed

The MacBook Air session committed spec v1 and SESSION-HANDOFF based on its best read of the state. It's possible the Mac Mini session discovers:

- The Docling bug fix is more complex than "iterate by page" (different API shape, different root cause)
- The existing Docling outputs are not uniformly broken (maybe only some are, and a partial reparse is possible)
- The Mac Mini already has a newer Docling version that fixes the bug without code changes
- LuxSE has a discoverable sovereign filter and the adapter is faster than estimated

Any of these should be captured in spec v2 and flagged to the user (me, the human) for approval. The spec v1 + SESSION-HANDOFF is context, not gospel.

---

## Rollback if things go sideways

If the overnight parse fails or the smoke test reveals the fix doesn't work:

1. The March 28 broken outputs in `data/parsed_docling/` are gitignored and can be deleted/restored freely
2. The `data/parsed/` PyMuPDF outputs are preserved on disk (nothing touches them in Step 0-4 of the sprint plan)
3. Spec v1 is preserved in git history as the "what we started from" reference
4. Feature branches can be abandoned and re-created
5. The Congo/DRC filing can be manually ingested from its FCA artefact URL if NSM incremental misses it for any reason (unlikely, pattern confirmed)
6. If the entire sprint goes sideways, the Monday demo has a fallback: the current deployed explorer at `https://sovereign-prospectus-corpus.streamlit.app` works against the current MotherDuck database (Task 1 + Task 2 shipped)

The worst-case Monday is "the current explorer, minus LuxSE, minus DRC, minus markdown rendering." That's still a shipping demo, not a disaster.

---

## One more time, in order

1. **On MacBook Air:** verify PR #74 is open and pushed (done), reset local main to origin/main (command below), close the laptop
2. **On Mac Mini:** `git pull` main, merge PR #74, verify symlink, verify Dropbox offline, verify venv + Docling, launch Claude, paste the session prompt
3. **Mac Mini Claude session:** runs Step 0 smoke test, writes spec v2, asks for your approval
4. **You:** approve spec v2 (or request changes), then the session proceeds with `superpowers:writing-plans` → implementation
5. **Overnight Saturday:** Mac Mini runs the bulk Docling parse (~6 hours), you sleep
6. **Sunday morning:** Mac Mini session verifies the parse, proceeds to Task 3 (FTS) and Task 4 (Streamlit explorer)
7. **Monday morning:** smoke tests, polish, demo

Godspeed.
