# Mac Mini Handoff — 2026-04-11 (Spring Meetings Sprint, Docling Migration)

**Predecessor:** `docs/mac-mini-handoff-2026-03-29.md` — same dual-machine pattern, different task.
**Session context:** `SESSION-HANDOFF.md` (Claude will read this as Phase 1).
**Sprint deadline:** Monday 2026-04-13 (IMF/World Bank Spring Meetings).

---

## For the human (you, Teal)

You have exactly two things to do:

1. **Open Claude Code** on the Mac Mini, in the **same directory you used for the March run** (should be `~/Projects/sovereign-prospectus-corpus`, where `data/` is a symlink to Dropbox). Verify the directory is correct before launching — if it's gone or moved, see "If the Mac Mini repo doesn't exist anymore" at the bottom of this file.

2. **Paste the entire section below** (everything between the two `═══` bars) into the Claude Code chat as the opening message.

Then just watch. Claude will:
- Read the context it needs (no clarifying questions)
- Verify the environment and data files are all present and accessible
- Sync git state, merge the handoff PR (#74)
- Run the Docling bug smoke test on a known-broken file
- Write spec v2
- **Stop and ask you to approve spec v2 before doing any further implementation**

You reply "approved" or "change X, Y, Z", and it continues.

**⏸ Pause points** (where Claude will stop and wait for you):
- If Docling isn't installed in the canonical venv — Claude asks before `uv add`ing it
- If the data integrity test fails — Claude asks before proceeding with any work
- After writing spec v2 — Claude stops for your approval
- Before `superpowers:writing-plans` — Claude confirms you're ready to go

---

## ═══ PASTE EVERYTHING BELOW INTO CLAUDE CODE ═══

You are Claude Code, opened on a Mac Mini M4 Pro in the existing sovereign-prospectus-corpus project directory from the March extraction sprint. A previous session on the MacBook Air worked through a full reframe of issue #72 (Docling migration) and is paused for a machine switch. Everything that session learned is captured in `SESSION-HANDOFF.md`, `docs/mac-mini-handoff-2026-04-11.md` (this file), and spec v1 at `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md`.

**Your job:** execute Phases 1-7 below in order, reporting progress at each phase. Stop at any ⏸ marker and wait for user confirmation. Do NOT re-litigate decisions that the handoff doc marks as locked-in.

**Locked-in decisions (do NOT question these — they were reached after a full design discussion):**

- Docling for all PDFs, PyMuPDF nowhere, EDGAR stays on BeautifulSoup `HTMLParser`
- LuxSE adapter committed unconditionally (no curl-test gate)
- LSE RNS dropped (DRC confirmed on NSM via live API — disclosure ID `d7a0206a-b71e-4af1-bc6e-63976b122475`, submitted 2026-04-08)
- Single overnight bulk parse of all 2,291 NSM+PDIP + new incrementals + LuxSE, after all downloads settle
- The March 28 `data/parsed_docling/` outputs are broken (confirmed data loss) and will be deleted before the overnight parse, not resumed
- Markdown rendering in the Streamlit detail panel is a Monday requirement
- Work happens on a new feature branch, never on `main` (pre-commit hook blocks it anyway)

**The one clarifying question you must NOT ask:** whether to re-run the DRC verification. It's been done. Move on.

---

### Phase 1 — Context load (read, do not act)

Use the `Read` tool to read, in order:

1. `SESSION-HANDOFF.md` (full — this is the primary context)
2. `docs/mac-mini-handoff-2026-04-11.md` (this file — you're partway through it already)
3. `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md` (spec v1 — the first draft, being rewritten as v2)
4. `CLAUDE.md` (workflow rules and environment notes)
5. `docs/mac-mini-handoff-2026-03-29.md` (the predecessor — same dual-machine pattern, different task; useful for branch-coordination rules)

Then **report to the user**:

> Phase 1 complete. I've loaded the full context. Here is my one-paragraph understanding: [summary of state, decisions, and what's about to happen]. Proceeding to Phase 2.

No questions yet.

---

### Phase 2 — Environment verification

Run these checks via `Bash` (each in a single command, reporting stdout verbatim):

**2a. Git state:**
```bash
git rev-parse --abbrev-ref HEAD && git rev-parse HEAD && git status --short | head
```

Expected: some branch (probably `main`), a commit hash, clean working tree (or only the deliberately-untracked files listed in SESSION-HANDOFF.md: `.claude/settings.local.json`, `demo/data/*.csv`, etc.).

**2b. Data symlink:**
```bash
ls -la data 2>&1 | head -3
```

Expected: `data -> /Users/<you>/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data` (a symlink, not a real directory).

If `data` is a real directory or missing: **⏸ STOP and ask the user what happened** — this is the March 29 pattern and should already be set up. Do NOT create or delete anything until confirmed.

**2c. Canonical venv:**
```bash
echo "UV_PROJECT_ENVIRONMENT=$UV_PROJECT_ENVIRONMENT" && uv run python -c "import sys; print('python:', sys.executable)"
```

Expected: `UV_PROJECT_ENVIRONMENT` points somewhere outside Dropbox (typically `~/.local/venvs/sovereign-corpus`), and `sys.executable` points to that venv.

**2d. Core dependencies:**
```bash
uv run python -c "import sys, duckdb, polars, pytest; print('duckdb:', duckdb.__version__, 'polars:', polars.__version__, 'pytest:', pytest.__version__)"
```

Expected: duckdb 1.4.4, polars ≥1.39, pytest 9.x.

**2e. Docling:**
```bash
uv run python -c "import docling; print('docling:', docling.__version__)"
```

If this fails: **⏸ STOP and ask the user:** "Docling is not installed in the canonical venv. The Mac Mini probably had a separate install for the March 28 run that isn't in the project dependencies yet. Do you want me to `uv add docling` now? (This will take several minutes and ~1-2 GB of model downloads.)"

Report a tidy green-check / red-X summary of all five checks.

---

### Phase 3 — Data file integrity test (the critical one)

The user's concern is that data files sync via Dropbox but may be Smart Sync placeholders rather than local files. A file can appear to exist (`ls` shows it, `stat` shows size) but actually live in Dropbox's cloud and fail on read. This phase verifies every expected data file cluster is **actually readable on disk**.

Write the following to `/tmp/verify_data_integrity.py`, then run it with `uv run python /tmp/verify_data_integrity.py`:

```python
"""Verify all expected data files are locally present and readable on the Mac Mini.

Expected counts from the MacBook Air inventory on 2026-04-11:
    data/original/*.htm         : 2947
    data/original/*.txt         : 275
    data/original/*.paper       : 84
    data/original/nsm__*.pdf    : 645
    data/pdfs/pdip/**/*.pdf     : 823 (nested under country subdirs)
    data/parsed/edgar__*.jsonl  : 3217
    data/parsed/nsm__*.jsonl    : 645
    data/parsed/pdip__*.jsonl   : 823
    data/parsed_docling/*.jsonl : 1468   (these are broken, will be deleted)
    data/parsed_docling/*.md    : 1468   (these are broken, will be deleted)
    data/db/corpus.duckdb       : present, >10 MB
    data/manifests/*.jsonl      : 3 files (edgar, nsm, pdip)
    data/raw/sovereign_issuer_reference.csv : present, >1 KB

For each expected cluster:
  1. Count files (exact match required)
  2. Read 3 random files end-to-end (catches Smart Sync placeholders)
  3. Report PASS/FAIL per cluster
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent if "/tmp" not in str(Path(__file__)) else Path.cwd()
DATA_DIR = PROJECT_ROOT / "data"

# Expected (cluster_name, glob, expected_count, min_size_bytes)
CLUSTERS = [
    ("data/original htm (EDGAR)",       "original/*.htm",           2947, 100),
    ("data/original txt (EDGAR)",       "original/*.txt",            275, 100),
    ("data/original paper (EDGAR)",     "original/*.paper",           84,   1),
    ("data/original nsm pdf",           "original/nsm__*.pdf",       645, 1000),
    ("data/pdfs/pdip (nested)",         "pdfs/pdip/**/*.pdf",        823, 1000),
    ("data/parsed edgar jsonl",         "parsed/edgar__*.jsonl",    3217, 100),
    ("data/parsed nsm jsonl",           "parsed/nsm__*.jsonl",       645, 100),
    ("data/parsed pdip jsonl",          "parsed/pdip__*.jsonl",      823, 100),
    ("data/parsed_docling jsonl (stale, to delete)", "parsed_docling/*.jsonl",        1468, 100),
    ("data/parsed_docling md (stale, to delete)",    "parsed_docling/*.md",           1468, 100),
]

SINGLETONS = [
    ("data/db/corpus.duckdb",                "db/corpus.duckdb",                              10_000_000),
    ("data/manifests/edgar_manifest.jsonl",  "manifests/edgar_manifest.jsonl",                     10_000),
    ("data/manifests/nsm_manifest.jsonl",    "manifests/nsm_manifest.jsonl",                       10_000),
    ("data/manifests/pdip_manifest.jsonl",   "manifests/pdip_manifest.jsonl",                      10_000),
    ("data/raw/sovereign_issuer_reference.csv", "raw/sovereign_issuer_reference.csv",               1_000),
]

# The known-broken Docling file we'll use in the smoke test later
SMOKE_TEST_FILE = "original/nsm__101126915_20200330172131895.pdf"

results: list[tuple[str, bool, str]] = []


def check_cluster(name: str, pattern: str, expected: int, min_size: int) -> tuple[bool, str]:
    found = sorted(DATA_DIR.glob(pattern))
    count = len(found)
    if count != expected:
        return (False, f"count {count} != expected {expected}")
    if count == 0:
        return (True, "0 files expected, 0 found")
    sample_size = min(3, count)
    sample = random.sample(found, sample_size)
    for f in sample:
        try:
            size = f.stat().st_size
            if size < min_size:
                return (False, f"sample file {f.name} size {size} < min {min_size}")
            # Read first and last 1KB to catch truncation / Smart Sync placeholders
            with f.open("rb") as fh:
                head = fh.read(1024)
                if not head:
                    return (False, f"sample file {f.name} empty read")
                fh.seek(max(0, size - 1024))
                tail = fh.read(1024)
                if not tail and size > 0:
                    return (False, f"sample file {f.name} tail read failed")
        except OSError as exc:
            return (False, f"sample file {f.name} read error: {exc}")
    return (True, f"count={count}, {sample_size} samples read end-to-end")


def check_singleton(name: str, rel: str, min_size: int) -> tuple[bool, str]:
    f = DATA_DIR / rel
    if not f.exists():
        return (False, "missing")
    size = f.stat().st_size
    if size < min_size:
        return (False, f"size {size} < min {min_size}")
    try:
        with f.open("rb") as fh:
            head = fh.read(1024)
            if not head:
                return (False, "empty read")
            fh.seek(max(0, size - 1024))
            tail = fh.read(1024)
            if not tail and size > 0:
                return (False, "tail read failed")
    except OSError as exc:
        return (False, f"read error: {exc}")
    return (True, f"size={size:,} bytes, read OK")


def main() -> int:
    print(f"Data root: {DATA_DIR}")
    print(f"Symlink target: {DATA_DIR.resolve()}")
    print()
    print(f"{'STATUS':6}  {'CLUSTER':<50}  DETAIL")
    print("-" * 100)

    ok = True
    for name, pattern, expected, min_size in CLUSTERS:
        passed, detail = check_cluster(name, pattern, expected, min_size)
        mark = "PASS" if passed else "FAIL"
        print(f"{mark:6}  {name:<50}  {detail}")
        if not passed:
            ok = False
        results.append((name, passed, detail))

    print()
    print("Singletons:")
    for name, rel, min_size in SINGLETONS:
        passed, detail = check_singleton(name, rel, min_size)
        mark = "PASS" if passed else "FAIL"
        print(f"{mark:6}  {name:<50}  {detail}")
        if not passed:
            ok = False

    # Smoke test file — must exist and be readable, this is what we'll use in Phase 5
    print()
    print("Smoke test target:")
    smoke = DATA_DIR / SMOKE_TEST_FILE
    if not smoke.exists():
        print(f"FAIL    {SMOKE_TEST_FILE}  missing")
        ok = False
    else:
        try:
            with smoke.open("rb") as fh:
                head = fh.read(4)
            if head != b"%PDF":
                print(f"FAIL    {SMOKE_TEST_FILE}  header {head!r} != b'%PDF'")
                ok = False
            else:
                print(f"PASS    {SMOKE_TEST_FILE}  header OK, size={smoke.stat().st_size:,} bytes")
        except OSError as exc:
            print(f"FAIL    {SMOKE_TEST_FILE}  read error: {exc}")
            ok = False

    print()
    print("=" * 100)
    print(f"OVERALL: {'PASS — all data clusters local and readable' if ok else 'FAIL — see above'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

Then run:

```bash
uv run python /tmp/verify_data_integrity.py
```

**Expected outcome:** `OVERALL: PASS — all data clusters local and readable`.

**If any cluster FAILs:** ⏸ **STOP and report to the user.** Possible causes:
- Dropbox `data/` folder is not "Available offline" (Smart Sync eviction) → user needs to right-click `~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/` → Make Available Offline
- Count mismatch means the MacBook Air has files the Mac Mini doesn't (or vice versa) — investigate before proceeding
- Read error means the file is a Smart Sync placeholder — Dropbox needs to finish syncing

Do not proceed to Phase 4 unless this phase passes in full.

---

### Phase 4 — Git sync and merge the handoff PR

The MacBook Air session opened PR #74 with spec v1 + SESSION-HANDOFF rewrite + this handoff doc. Merge it, then create a new feature branch for the Docling bug fix work.

```bash
git fetch origin
git status --short
```

If status shows unexpected local changes or commits ahead of origin/main: ⏸ **STOP** — there is stale Mac Mini state that needs investigation.

```bash
git checkout main
git pull --ff-only
gh pr view 74 --json state,title,headRefName --jq '{state, title, headRefName}'
```

Expected PR state: `OPEN`. If it says `MERGED`, skip to the final pull; if `CLOSED`, ⏸ STOP and ask.

Merge the PR (admin merge is fine — it's docs-only operational state, no bot review needed):

```bash
gh pr merge 74 --squash --admin --delete-branch
git pull --ff-only
git log --oneline -3
```

Expected: the squashed commit for PR #74 is at HEAD.

Create the new feature branch for the Docling bug fix + sprint v2 work:

```bash
git checkout -b feature/docling-bug-fix-and-sprint-v2
```

All remaining work happens on this branch. Never commit to `main`.

Report: "Phase 4 complete. On branch `feature/docling-bug-fix-and-sprint-v2`, synced with origin."

---

### Phase 5 — Docling bug smoke test

**Goal:** reproduce the page-drop bug diagnosed on the MacBook Air, then write and verify a fix, so the overnight parse run (Saturday night) produces clean output.

**Background from Phase 1 reading:** `scripts/docling_reparse.py` on `feature/30-docling-reparse` (commit `47dfa8a9`) only recognizes `TextItem` and `SectionHeaderItem`. Pages that contain only `TableItem`, `PictureItem`, etc. are silently dropped. For `data/original/nsm__101126915_20200330172131895.pdf`, the March 28 run emitted 10 pages out of 58, dropping 46 pages of content.

**5a. Fetch the stale script for reference:**

```bash
git show feature/30-docling-reparse:scripts/docling_reparse.py > /tmp/docling_reparse_stale.py
wc -l /tmp/docling_reparse_stale.py
```

**5b. Verify the current Docling API** for per-page iteration. The stale script used `doc.iterate_items()` filtered to TextItem + SectionHeaderItem. The fix needs to iterate by actual page. Use `context7` (`mcp__plugin_context7_context7__query-docs`) to fetch current Docling docs.

Specifically, query for:
- "Docling DocumentConverter export_to_markdown per page"
- "Docling DoclingDocument pages iteration"
- "Docling 2.x page_no prov"

Document the exact API method(s) you find. If context7 doesn't return useful info, fall back to inspecting the installed Docling package directly:

```bash
uv run python -c "
import docling
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument
print('docling:', docling.__version__)
print()
print('DoclingDocument attributes:')
print([a for a in dir(DoclingDocument) if not a.startswith('_') and 'page' in a.lower()])
print()
print('DocumentConverter methods:')
print([a for a in dir(DocumentConverter) if not a.startswith('_')])
"
```

**5c. Reproduce the bug** on the known-broken file using the stale script's logic. Write a minimal repro script to `/tmp/docling_repro_bug.py`:

```python
"""Reproduce the page-drop bug from scripts/docling_reparse.py on a known-broken PDF."""
from __future__ import annotations
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling_core.types.doc import SectionHeaderItem, TextItem

PDF = Path("data/original/nsm__101126915_20200330172131895.pdf")
print(f"Converting {PDF.name}...")
converter = DocumentConverter()
result = converter.convert(str(PDF))
doc = result.document

# Stale script's logic
pages_stale: dict[int, list[str]] = {}
for item, _level in doc.iterate_items():
    if isinstance(item, (TextItem, SectionHeaderItem)):
        for prov in item.prov:
            pages_stale.setdefault(prov.page_no, []).append(item.text)
            break

print(f"Stale logic emitted {len(pages_stale)} pages with TextItem/SectionHeaderItem")
print(f"Page numbers: {sorted(pages_stale.keys())}")
print()

# What's Docling's actual page count?
# (Resolve exact attribute name from Phase 5b research)
print("Docling's actual doc structure:")
if hasattr(doc, "pages"):
    print(f"  doc.pages keys: {sorted(doc.pages.keys()) if hasattr(doc.pages, 'keys') else 'not a dict'}")
if hasattr(doc, "num_pages"):
    print(f"  doc.num_pages: {doc.num_pages}")
```

Run:

```bash
uv run python /tmp/docling_repro_bug.py
```

Expected: stale logic reports around 10 pages with page numbers like `[1, 2, 3, 4, 5, 6, 7, 8, 24, 41]` (original had them 0-indexed, but either way you should see large gaps). The "actual page count" section tells you what the correct API call is.

If the stale logic reports all 58 pages: the bug may be fixed in the current Docling version. In that case, note this finding and continue to 5d to verify the fix isn't needed.

**5d. Write the fix.** Based on Phase 5b's API discovery, patch the per-page extraction so:
- Page iteration uses Docling's native page structure (e.g., `doc.pages.keys()` or `doc.num_pages` range)
- Each page's content includes ALL item types with `prov.page_no == page_no` (not just TextItem + SectionHeaderItem), OR uses Docling's per-page markdown export if such a method exists
- `page_count` header is sourced from the actual PDF page count, not from `len(pages)`

Write the fix to `/tmp/docling_repro_fix.py`:

```python
"""Fixed version — iterate by actual page, capture all item types."""
from __future__ import annotations
from pathlib import Path
from docling.document_converter import DocumentConverter

PDF = Path("data/original/nsm__101126915_20200330172131895.pdf")
converter = DocumentConverter()
result = converter.convert(str(PDF))
doc = result.document

# FIX: iterate by actual page number, collect all items on that page
# (exact API shape TBD from Phase 5b — this is the template)

# Option A: if doc.pages is a dict keyed by page_no
if hasattr(doc, "pages") and hasattr(doc.pages, "keys"):
    page_count = len(doc.pages)
    pages_out = {}
    for page_no in sorted(doc.pages.keys()):
        # Collect all items whose first prov is this page
        content = []
        for item, _lvl in doc.iterate_items():
            if hasattr(item, "prov") and item.prov:
                if item.prov[0].page_no == page_no and hasattr(item, "text"):
                    content.append(item.text)
        pages_out[page_no] = "\n".join(content)
    print(f"Fixed logic emitted {len(pages_out)} / {page_count} pages")
    print(f"Page numbers: {sorted(pages_out.keys())}")
    print()
    print("Char counts per page (first 20):")
    for p in sorted(pages_out.keys())[:20]:
        print(f"  page {p}: {len(pages_out[p])} chars")

# Option B: if there's a per-page markdown export (preferred for the actual fix)
if hasattr(doc, "export_to_markdown"):
    import inspect
    sig = inspect.signature(doc.export_to_markdown)
    print(f"\nexport_to_markdown signature: {sig}")
    # Try per-page call if the method supports it
    # doc.export_to_markdown(page_no=3) — or whatever the param name is
```

Run:

```bash
uv run python /tmp/docling_repro_fix.py
```

Expected: fixed logic reports all 58 pages (or whatever `doc.num_pages` says the PDF actually has), with non-trivial char counts on the pages that the stale logic dropped (pages 8-22 and 24-39 and 41-57 in this file).

Iterate on the fix until every expected page is present with content. If the first attempt doesn't work, debug the Docling API until it does — this is the whole point of Phase 5.

**5e. Spot check the fix on 2 more representative files:**

```bash
# Pick a PDIP with tables and a long NSM
ls data/pdfs/pdip/kazakhstan/*.pdf 2>/dev/null | head -1
ls data/original/nsm__* | shuf -n 1   # or pick any you like
```

Adapt the fix script to run against each, verify no page drops.

**5f. Measure per-doc elapsed time.** The March 28 baseline was ~9.7 s/doc (1,466 docs in 14,208 s on M4 Pro). The fix should be within 2x of that. If the fix is 30+ s/doc, the overnight run balloons from 6h to 16h+ and the plan has to adjust.

**5g. Report the smoke test results** to the user:

> Phase 5 complete. Bug reproduced: stale logic emitted X of Y pages. Fix verified: new logic emits Y of Y pages with content. Elapsed: Xs/doc (within 2x baseline). Ready to write spec v2.

If the fix works: proceed to Phase 6.
If the fix doesn't work after honest effort: ⏸ **STOP and report the obstacle** — do not proceed to writing spec v2.

---

### Phase 6 — Write spec v2

Write spec v2 to `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md`. Use spec v1 as the starting structure, but apply **all** the accepted review findings from `SESSION-HANDOFF.md` §"Spec v1 → v2 rewrite" and the Phase 5 bug-fix details. Specifically:

1. **Correctness fixes:**
   - `src/corpus/cli.py:618-623` CLI rewire (call `get_parser()` instead of hardcoding `PyMuPDFParser()`)
   - The confirmed Docling bug fix from Phase 5 (including the exact API shape you discovered)
   - `scripts/docling_reparse.py` `discover_pdfs()` glob addition for `luxse__*.pdf`
   - `documents.parse_tool` + `page_count` population as new code in the Task 3 ingest
   - Delete Gate A (DRC already verified)
   - Delete the in-place merge strategy (nuke `data/parsed_docling/` and re-parse from scratch)
   - Re-run `grep_matches` after the overnight parse (now safe, because the fix eliminates sparse page numbering)

2. **Time estimate compression** per the reviewers' table in SESSION-HANDOFF.md §"Time-estimate corrections".

3. **LuxSE cliff reshape:** delete the 5h wall-clock cliff, replace with 90-min soft checkpoint + 4h hard cliff.

4. **Step 0 added:** the Docling bug fix + smoke test you just completed becomes the "Step 0" of the implementation plan, already done. Spec v2 documents it as complete and proceeds from Step 1.

5. **Saturday-to-Sunday sequencing:**
   - Saturday: Phase A PR (parser class + CLI rewire + fixed docling_reparse.py), NSM + EDGAR incrementals, LuxSE adapter + download
   - Saturday evening: user kicks off overnight Docling bulk parse against ALL 2,291 NSM+PDIP + new NSM + LuxSE PDFs (after deleting `data/parsed_docling/` entirely)
   - Sunday morning: verify overnight parse, Task 3 (FTS + markdown storage + MotherDuck), Task 4 (Streamlit explorer with markdown rendering)
   - Monday morning: smoke tests, polish, demo

6. **Markdown storage layer:** the detail panel renders markdown. Decide in v2 where the markdown lives — probably a new `documents.markdown_text` column or a `document_markdown` table keyed by document_id, populated from the `.md` files Docling emits alongside the JSONL.

7. **Self-review** the spec using the brainstorming skill's checklist: placeholder scan, internal consistency, scope check, ambiguity check. Fix inline.

---

### Phase 7 — ⏸ STOP for user approval of spec v2

After writing spec v2 and self-reviewing, commit it to the feature branch:

```bash
git add docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md
git commit -m "docs: spec v2 for Spring Meetings sprint with confirmed Docling bug fix

- Bug fix verified in Phase 5 smoke test (see commit message for details)
- All accepted review findings from three external agents applied
- Revised time estimates, reshaped LuxSE cliff, deleted Gate A and in-place merge
- Step 0 (Docling bug fix smoke test) documented as complete
- Saturday-Sunday-Monday sequencing with overnight bulk parse

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

Push the branch (do NOT open a PR yet — the user reviews the spec first):

```bash
git push -u origin feature/docling-bug-fix-and-sprint-v2
```

Then **STOP** and tell the user:

> Phase 7: spec v2 is committed at `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design-v2.md` on branch `feature/docling-bug-fix-and-sprint-v2` (pushed to origin). The Docling bug fix is confirmed working. Please review the spec and let me know if you want any changes before I invoke `superpowers:writing-plans` to build the implementation plan.

Do NOT invoke `writing-plans` until the user explicitly approves.

---

## ═══ END OF CLAUDE PROMPT ═══

## If the Mac Mini repo doesn't exist anymore

If `~/Projects/sovereign-prospectus-corpus` is gone (unlikely — it was set up for the March run), first-time setup:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone git@github.com:Teal-Insights/sovereign-prospectus-corpus.git
cd sovereign-prospectus-corpus

# Data symlink
ln -s ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data data
ls -la data   # verify symlink

# In Finder: right-click ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus/data/
# and select "Make Available Offline" if not already

# Environment
uv sync --all-extras
uv run pytest -v 2>&1 | tail -5

# Launch with caffeinate to prevent sleep
caffeinate -d -i claude --dangerously-skip-permissions
```

Then paste the Claude prompt above.

## Branch coordination rules (same as March 29, updated for this sprint)

| Machine | Branch | Writes to `data/` | Pushes code |
|---------|--------|-------------------|-------------|
| **Mac Mini** | `feature/docling-bug-fix-and-sprint-v2` (created in Phase 4) | YES (overnight parse writes to `data/parsed_docling/`) | YES |
| **MacBook Air** (if opened) | `feature/<any-non-sprint-work>` only | NO (read-only on sprint outputs, and only after `_summary.json` shows clean completion) | YES for non-sprint work only |

**NEVER:**
- Work on the same branch from both machines
- Push to `main` from either machine (feature branches + PRs only)
- Edit sprint code from the MacBook Air while the Mac Mini is executing
- Pull the Mac Mini's feature branch on the Air while the Mac Mini is mid-work
- Delete `data/parsed_docling/` on the Air while the Mac Mini is parsing

**SAFE:**
- Both machines `git pull --ff-only` on `main` after a PR merges
- Mac Mini writes to `data/parsed_docling/` during overnight parse (no one else is touching it)
- MacBook Air reads results ONLY after `_summary.json` shows clean completion
- Both machines push their own feature branches independently

## Rollback if things go sideways

- The March 28 broken outputs in `data/parsed_docling/` are gitignored and can be deleted/restored freely from Dropbox Time Machine if needed
- `data/parsed/` (PyMuPDF outputs) stays untouched until Task 3 on Sunday, preserving the current working explorer as a fallback
- Spec v1 is preserved in git history for reference
- Feature branches can be abandoned and re-created
- DRC filing can be manually ingested from its FCA artefact URL if NSM incremental misses it (unlikely)
- Worst-case Monday: the currently-deployed explorer at `https://sovereign-prospectus-corpus.streamlit.app` still works against the current MotherDuck database (Task 1 + Task 2 shipped). That's a shipping demo, not a disaster.
