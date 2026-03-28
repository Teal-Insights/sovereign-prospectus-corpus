# Multi-Machine Dev Workflow: What's the Best Setup?

I need advice on the best way to manage a development project across two Mac
machines that share files via cloud sync. I've documented a real incident below
where things went wrong, and I want to find a setup that's ergonomic, safe, and
doesn't require me to think about it constantly.

## My Situation

### The machines

| Machine | Role | Specs |
|---|---|---|
| **MacBook Air M5** | Primary development, code review, writing | 10-core, 32 GB, macOS 26.3, portable |
| **Mac Mini M4 Pro** | Heavy compute, long-running jobs (hours), always-on | 14-core, 64 GB, macOS (recent) |

Both are Apple Silicon. Both have Dropbox, iCloud, and access to Google Drive.

### The project

A Python research project (sovereign bond prospectus analysis) with:

- **Code:** ~3,000 lines of Python across `src/`, `scripts/`, `tests/`, `demo/`
- **Data:** ~7.7 GB of PDFs (2,823 files) + 496 MB of parsed output
- **Git repo** hosted on GitHub, with feature branches and PRs
- **Tooling:** uv for Python/venv management, ruff, pyright, pytest
- **CI agents:** Claude Code and Codex run autonomously on the Mac Mini for
  long compute jobs (4+ hour PDF parsing runs, ML inference)

### What I'm trying to do

- **Develop on the MacBook Air** — write code, run tests, review PRs, iterate
- **Run long compute on the Mac Mini** — kick off multi-hour parsing/ML jobs,
  sometimes autonomously via Claude Code with `--dangerously-skip-permissions`
- **See results on both machines** — when the Mac Mini finishes parsing 1,468
  PDFs, I want to see the output on the MacBook Air without manual file
  transfers
- **Sometimes work on both machines the same day** — e.g., develop on the
  MacBook Air in the morning, kick off a compute job on the Mac Mini at lunch,
  continue developing on the MacBook Air in the afternoon while the job runs

### How I've been working

The entire project lives in `~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/`.
Dropbox syncs everything — code, data, `.git/`, and (until today) `.venv/` —
between both machines in real time.

**This has worked fine for 10-15 years** across many projects, as long as I
only worked on one machine at a time. The problems started when I began working
on both machines concurrently (developing on the Air while a compute job ran on
the Mini).

## What Went Wrong (March 28, 2026)

Here's the full incident timeline. I'm including this level of detail because
the failure modes were subtle, silent, and interacted with each other in ways
I wouldn't have predicted.

### Timeline

```
10:56  MacBook Air: create feature branch, start developing
11:50  MacBook Air: create second feature branch for compute job, switch back
11:54  MacBook Air: continue committing on first branch
12:04  Mac Mini: session starts (Dropbox has synced the repo state)
12:07  Mac Mini: tries to switch branches
       → git index.lock error (Dropbox synced a lock file from the Air)
       → removes lock, git checkout fails ("unable to write new index file")
       → waits for Dropbox sync to settle, retry succeeds
12:07  Mac Mini: tries to install ML dependencies (Docling/PyTorch)
       → stalls indefinitely (Mac Mini had Python 3.14, Docling needs <=3.13)
       → creates venv inside Dropbox folder → Dropbox starts syncing it
       → Dropbox locks prevent deleting the broken venv
       → deletes venv, Dropbox RESURRECTS it from MacBook Air's copy
       → gives up, creates venv outside Dropbox (~/.local/venvs/)
12:11  MacBook Air: 4 more commits on its branch (12:11-12:19)
12:22  Mac Mini: launches 4-hour background parsing job

12:37  ** SILENT FAILURE **: Dropbox syncs MacBook Air's .git/HEAD to Mac Mini
       Mac Mini's branch silently switches from feature/30 → feature/29
       No error, no warning — git just thinks it's on a different branch
       (The parsing job keeps running fine — it's a background process)

12:37  MacBook Air simultaneously: Dropbox syncs Mac Mini's .git/HEAD here
       Reflog shows phantom branch switch (30→29→30) at the same second
       "Bidirectional HEAD thrashing" — both machines briefly see each other's
       branch state

13:00-16:20  Mac Mini: parsing job runs to completion (1,468 docs, 0 failures)
16:35  Mac Mini: commits the results → LANDS ON THE WRONG BRANCH
       Only noticed because the git output said the wrong branch name
       The commit appended to an open PR it wasn't supposed to be part of
```

### The 9 issues we hit

1. **Python version incompatibility** — Mac Mini had 3.14, needed 3.12
2. **Dropbox locks prevent venv deletion** — file locks, timeouts, resurrection
3. **Git index.lock from Dropbox sync** — blocks all git operations
4. **Python import path differs between 3.12/3.13** — code broke on other machine
5. **Silent branch switch via .git/HEAD sync** — the scariest one
6. **Git index write failure** — Dropbox still syncing .git/ after lock removal
7. **uv sync replaces dependencies** — uninstalled 85 ML packages
8. **Bidirectional .git/HEAD thrashing** — both machines raced HEAD writes
9. **MacBook Air using contaminated .venv** — Dropbox synced Mac Mini's venv,
   created conflicted copies of Python symlinks pointing to wrong machine

### The root causes

The issues fall into three categories:

**A. `.git/` should not be synced by file sync tools.** Git expects exclusive
control of `.git/HEAD`, `.git/index`, `.git/index.lock`, and other mutable
state files. Dropbox treats them as regular files and syncs changes between
machines, causing silent branch switches (Issue 5, 8), lock conflicts (Issue
3, 6), and corrupted state.

**B. `.venv/` is machine-specific.** Virtual environments contain symlinks to
machine-local Python installations and platform-specific compiled extensions.
Syncing them between machines creates cross-contamination (Issue 2, 9) and
version mismatches (Issue 4).

**C. Large data files are fine for cloud sync.** The 7.7 GB of PDFs and parsed
output synced without any issues. Dropbox is actually good at this — atomic
writes (`.part` → rename) mean the other machine never sees half-written files.

## My Constraints

1. **I want data files accessible on both machines without manual transfers.**
   When the Mac Mini finishes a 4-hour parsing job, I want to open the results
   on the MacBook Air without running rsync or scp.

2. **I've used Dropbox + git for 10-15 years without major problems** — so
   long as I was only on one machine at a time. The concurrent usage is new.
   I'm not looking to abandon Dropbox entirely; I'm looking for the right
   boundaries.

3. **I use cloud sync for backup too.** My entire computer is backed up across
   Dropbox, iCloud, and/or Google Drive. If I move the repo out of Dropbox, I
   need to make sure it's still backed up somewhere.

4. **I don't want to think about this.** The ideal solution is one I set up
   once and then forget about. Having to remember protocols ("only run git on
   one machine at a time", "wait 30 seconds after switching") has already
   failed — the silent branch switch happened despite knowing the risks.

5. **Mac Mini runs autonomously.** Claude Code runs long jobs unattended.
   It does git commits and pushes. I can't be there to babysit the workflow.

6. **Python version may differ between machines.** The MacBook Air has
   Python 3.13 (anaconda), the Mac Mini has Python 3.12 (uv-installed). This
   is somewhat intentional — the Mini pins 3.12 for ML compatibility.

7. **Setup should take under 30 minutes.** I have a deadline in 2 days
   (March 30 roundtable). Long-term I can invest more time, but right now I
   need something quick and safe.

8. **I have other projects in Dropbox too.** ~31 folders in Dropbox, some with
   git repos. Any solution should be something I can apply broadly, not a
   one-off hack for this project.

## What I've Already Considered

### Option A: Just be careful (discipline-based)
Already failed. The silent branch switch happened despite knowing the risk.

### Option B: Exclude .git/ from Dropbox sync
Use `xattr -w com.dropbox.ignored 1 .git` on each machine. Each machine has
its own `.git/` state, coordinate via `git push`/`git pull` through GitHub.
Code files still sync via Dropbox. Data files still sync via Dropbox.

**My concern:** If Dropbox syncs the code files (src/, scripts/) but not
`.git/`, what happens when the Mac Mini modifies a file and Dropbox syncs it
to the Air before a `git pull`? Git on the Air would see "uncommitted changes"
that it didn't make. Is this actually better or just a different class of
confusion?

### Option C: Repo out of Dropbox, symlink data in
```
~/Projects/sovereign-prospectus-corpus/     # git repo, NOT in Dropbox
  src/, tests/, scripts/, docs/             # code — synced only via git
  data -> ~/Dropbox/sovereign-corpus-data/  # symlink to Dropbox for data
```

**My concern:** Losing automatic code sync means I have to `git push` + `git
pull` for every change. That's fine for finished features, but annoying for
quick iteration (fix a typo on the Air, want it on the Mini immediately).

### Option D: Repo out of Dropbox, symlink data in, use iCloud/Google Drive as backup
Same as C but add the `~/Projects/` directory to iCloud or Time Machine for
backup purposes. (Not for sync — just backup.)

### Option E: Something I haven't thought of
Maybe there's a better approach entirely. rsync cron job? Syncthing? A
different cloud sync tool that handles .git better? Git-annex for the large
data files? Some Dropbox configuration I'm not aware of?

## What I Want From You

1. **Evaluate the options above** (A-E) for my specific situation. Don't just
   tell me "don't use Dropbox with git" — I know that's the textbook answer.
   I want to know the best *practical* setup given that I use cloud sync for
   backup across my entire machine, I want data files to sync automatically,
   and I want something I don't have to think about.

2. **Be specific about the workflow.** Don't just say "use git for code" —
   tell me exactly what the day-to-day looks like. When I sit down at the
   MacBook Air in the morning, what do I do? When I want to kick off a job
   on the Mac Mini, what's the sequence? When the job finishes, how do I get
   the results?

3. **Address the data sync problem directly.** The 7.7 GB of PDFs and parsed
   output need to be on both machines. Putting them in git is wrong (too large).
   Dropbox handles them well. How does this interact with whatever repo setup
   you recommend?

4. **Consider that I have ~31 Dropbox projects.** Some have git repos. I'd
   like a pattern I can apply broadly, not a bespoke solution for one project.

5. **Tell me what could go wrong** with your recommended approach. Every option
   has failure modes — I want to know what they are so I can decide if they're
   better than the failure modes I already experienced.
