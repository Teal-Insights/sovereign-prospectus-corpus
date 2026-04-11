# SESSION-HANDOFF.md — Spring Meetings Sprint (mid-brainstorm, machine switch)

**Last updated:** 2026-04-11 afternoon (paused for MacBook Air → Mac Mini M4 Pro switch)
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Sprint spec v1 (being revised):** `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md` (commit `e999d45c`)
**Status:** Mid-brainstorm. Spec v1 written, reviewed by three external agents, Docling bug diagnosed, pending smoke test → spec v2 → implementation.

## ⏭️ START HERE (Mac Mini, next session)

You are resuming a brainstorming session that was paused for a machine switch. The MacBook Air session worked through a full reframe of issue #72 (Docling migration) and landed on a plan that needs a smoke test before the spec can be finalized. **Everything the previous session learned is captured below — read this entire file before touching code.**

### The one-sentence summary

The March 28 Docling outputs in `data/parsed_docling/` are broken (silently dropped pages of table-heavy content). A bug was diagnosed in `scripts/docling_reparse.py` on the stale `feature/30-docling-reparse` branch. The immediate next step is to run a smoke test that reproduces the bug and validates a fix, then rewrite the sprint spec as v2, then execute.

### Immediate next actions on the Mac Mini

1. **Pull and sync:**
   ```bash
   cd ~/Dropbox/2026-03_Sovereign-Prospectus-Corpus  # or wherever it lives on Mac Mini
   git checkout main && git pull --ff-only
   uv sync --all-extras  # verify canonical venv is healthy
   uv run python -c "import docling; print(docling.__version__)"  # confirm Docling installed
   ```

2. **Read, in order:**
   - `SESSION-HANDOFF.md` (this file)
   - `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md` (spec v1 — the previous session's first attempt; being rewritten as v2 after the smoke test)
   - `CLAUDE.md` (always, but especially the Environment Setup + NSM Lessons Learned sections)
   - `planning/SPRINT-2026-04-SPRING-MEETINGS.md` (original sprint plan that v1 partially supersedes)

3. **Run the smoke test** (details in the "Smoke test" section below)

4. **Rewrite spec v2** incorporating all accepted review findings (listed below)

5. **Get user approval on v2**, then invoke `superpowers:writing-plans` to build the implementation plan

---

## The bug (critical — diagnosed but not yet verified on current Docling version)

`scripts/docling_reparse.py` on `feature/30-docling-reparse` (commit `47dfa8a9`), lines roughly 118-124:

```python
pages: dict[int, list[str]] = {}
for item, _level in doc.iterate_items():
    if isinstance(item, (TextItem, SectionHeaderItem)):
        for prov in item.prov:
            pages.setdefault(prov.page_no, []).append(item.text)
            break
```

**The bug:** only `TextItem` and `SectionHeaderItem` are recognized. Pages that contain only `TableItem`, `PictureItem`, `ListItem`, `FormulaItem`, `FloatingItem`, etc. get zero entries in the `pages` dict and are silently dropped from the output. In sovereign debt prospectuses, the statistical annexes, financial tables, and reserve-adequacy charts live on exactly those table-heavy pages — which is why the dropped pages cluster in the middle of documents.

Additionally: `page_count = len(pages)` on line ~130 reports the count of pages that had TextItems, not the actual PDF page count. The header field becomes a lie.

**Verified impact on one file (MacBook Air session):**
```
nsm__101126915_20200330172131895 — PyMuPDF saw 58 pages
Docling header.page_count: 10
Docling emitted page numbers: [0, 1, 2, 3, 4, 5, 6, 7, 23, 40]
Missing pages: 8-22, 24-39, 41-57 (46 pages of content dropped)
```

**Review C (third external reviewer) found this pattern across 243 of the 1,468 outputs** — more than 2 pages of drift, with 84 showing >10 pages of drift. Example drifts: `pdip__KAZ4` 207→18, `nsm__4189777` 180→29.

### The fix shape (unverified — depends on current Docling API)

Iterate by actual page, not by item type. Rough shape:

```python
page_count = len(doc.pages)  # or doc.num_pages — verify exact attribute
pages_out: dict[int, str] = {}
for page_no in sorted(doc.pages.keys()):
    # Per-page markdown export, preserves tables/figures as markdown tables/images
    page_md = doc.export_to_markdown(page_no=page_no)
    # Or: iterate items with prov.page_no == page_no across ALL item types
    pages_out[page_no] = page_md
```

**Unknowns to resolve via smoke test + `context7` docs lookup:**
- Exact Docling 2.x API for "give me the markdown for page N" — may be `export_to_markdown(page_no=...)`, may be something else
- Whether `doc.pages` is the right accessor or if it's `doc.iterate_pages()` or similar
- Whether the fix should emit per-page markdown (for the explorer detail panel) AND plain text (for FTS and grep), or just markdown with a strip pass for FTS

---

## Smoke test plan

On the Mac Mini, using the existing Docling install:

1. **Confirm Docling version:**
   ```bash
   uv run python -c "import docling; print(docling.__version__)"
   ```

2. **Verify Docling page-iteration API** via `mcp__plugin_context7_context7__query-docs` (context7 MCP tool). Query for "Docling DocumentConverter export_to_markdown per page" and "Docling iterate items page_no". Document the exact method name in the spec v2.

3. **Reproduce the bug:** run the stale script's worker logic on `data/original/nsm__101126915_20200330172131895.pdf` (confirmed broken). Expect emitted page numbers `[0,1,2,3,4,5,6,7,23,40]`.

4. **Write the fix:** patch `process_one_pdf` to iterate by page. Keep the markdown output AND the per-page JSONL output (the spec v2 needs both: markdown for the detail panel, JSONL for FTS).

5. **Verify the fix on the same file:** expect all 58 pages emitted, each with content, `page_count` header field matching PDF reality.

6. **Spot check 2 more representative files** — one PDIP with complex tables, one NSM supplementary prospectus. Verify no page drops.

7. **Measure elapsed time per doc** — the old script averaged 9.7s/doc on the M4 Pro. The fix should be within 2x of that. If it balloons to 30s/doc, the overnight run becomes 16+ hours instead of 6 and the plan has to adjust.

8. **If the fix works:** document it, write spec v2, get user approval, proceed.

9. **If the fix doesn't work:** investigate further, consider Docling's VLM pipeline (slower but more robust), or fall back to a different PDF-to-markdown tool.

---

## Locked-in decisions (user-confirmed, do NOT re-litigate)

1. **Docling for all PDFs. PyMuPDF nowhere.** The user's phrasing: "PyMuPDF nowhere. It is terrible. Docling everywhere." This applies to every PDF in the corpus.
2. **EDGAR stays on BeautifulSoup `HTMLParser`.** It's not PyMuPDF; it's tuned for EDGAR's `page-break-before:always` convention. Keep it.
3. **Intent: nicely formatted markdown viewing in the explorer detail panel**, regardless of whether the source was PDF or HTML. This is the user's stated end-goal for Task 4.
4. **LuxSE adapter committed unconditionally** for this sprint. No curl-test go/no-go gate. User accepted the uncertainty in exchange for coverage upside.
5. **LSE RNS adapter dropped.** DRC is on NSM — confirmed via live API query by Review C, disclosure ID `d7a0206a-b71e-4af1-bc6e-63976b122475`, submitted `2026-04-08T11:57:24Z`, headline "Publication of a Base Offering Circular".
6. **Single bulk Docling parse runs overnight on the M4 Pro** — ONE run, after all downloads settle, covering the entire 2,291 NSM+PDIP corpus plus whatever the incrementals and LuxSE produced. User's phrasing: "I'd rather do everything and then make it look nice."
7. **The March 28 Docling outputs will be deleted, not resumed.** The resume-from-existing-outputs approach is off the table — too much risk of masking the bug. Fresh start.
8. **DRC verification is already complete.** Do not run a verification curl — it's been done. DRC will land via the existing `"Republic of"` NSM name pattern during the incremental.

---

## Spec v1 → v2 rewrite: what to change

Spec v1 is committed at `docs/superpowers/specs/2026-04-11-spring-meetings-sequencing-design.md` (`e999d45c`). It got three external reviews that collectively identified ~10 correctness issues and ~8 time-estimate corrections. Apply all of these in v2:

### Critical correctness fixes

1. **`src/corpus/cli.py:618-623` hardcodes `PyMuPDFParser()` for `.pdf` and never calls `get_parser()`.** The registry is unused. Spec v1's PR #1 "flip the config default" is cargo-culting without also rewiring the CLI. **Fix in PR #1:** change the parser dict to `".pdf": get_parser()` (or equivalent), so the config flip actually routes `.pdf` files through Docling. ~3 lines.

2. **Fix the page-drop bug in `scripts/docling_reparse.py`** before the overnight run (see smoke test section above).

3. **`scripts/docling_reparse.py:discover_pdfs()` only globs `data/pdfs/pdip/` and `data/original/nsm__*.pdf`.** It will silently skip LuxSE. Add `data/original/luxse__*.pdf` to the glob.

4. **`documents.parse_tool` population is new code, not just a config flip.** `src/corpus/db/ingest.py:26` only copies `parse_tool` from manifests, which don't carry it. All 4,769 rows currently have NULL `parse_tool`. Spec v2 must call out reading the JSONL header during Task 3's rebuild and populating the column there. Small but explicit new work.

5. **Delete Gate A (DRC verification gate).** DRC is already verified on NSM via live API (`d7a0206a-b71e-4af1-bc6e-63976b122475`). No reactive gate needed.

6. **Delete the in-place merge strategy.** The whole "overwrite 1,468 PyMuPDF files with Docling files" approach is dead. Instead: overnight parse writes clean Docling outputs to `data/parsed_docling/`; Task 3's ingest reads per-source (EDGAR from `data/parsed/`, everything else from `data/parsed_docling/`). OR (simpler): rename `data/parsed` → `data/parsed.pymupdf.bak` and `data/parsed_docling` → `data/parsed`, then re-add EDGAR's `.htm/.txt/.paper` outputs to the new `data/parsed/` by running `corpus parse --source edgar` once. Pick one in v2.

7. **Re-run `grep_matches` after the overnight parse.** The existing 106,229 matches reference PyMuPDF text offsets. After the Docling re-parse, those offsets are invalid. `corpus grep` is fast (~15-30 min). Slot it into Task 3.

8. **`documents.page_count` population.** Same issue as `parse_tool` — null for all 4,769 rows. Backfill from the JSONL header during Task 3 rebuild.

### Time-estimate corrections (accept the compressed ranges)

| Step | Spec v1 | Revised ceiling |
|---|---|---|
| Docling Phase A | 1-2 hr | 45-90 min (incl. CLI rewire + bug fix + tests) |
| NSM + EDGAR incrementals | 1-2 hr | 30-60 min (both adapters exist and are fast) |
| LuxSE adapter build | 4-6 hr | 2-4 hr happy path (cliff at 90m + 4h if hostile) |
| LuxSE download | 0.5-1 hr | unchanged |
| Bulk Docling parse | 0.5-1.5 hr | ~6 hr (FULL 2,291 + LuxSE, overnight — spec v1 only budgeted the delta) |
| Task 3 (FTS + merge + MD publish) | 3-5 hr | 4-6 hr (add grep rerun + parse_tool + page_count backfill) |
| Task 4 (Streamlit explorer) | 4-8 hr | 3-6 hr (Task 1 already de-risked deploy) |
| Task 9 polish | 1-2 hr | 30-60 min |

### LuxSE cliff reshape

**Delete:** "5 hours cumulative wall clock from branch created, including idle time."

**Replace with:**
- **90-minute soft checkpoint:** by T+90m, adapter must have retrieved at least one non-empty sovereign artefact URL via non-interactive curl. If not → abandon LuxSE, document in `docs/SOURCE_INTEGRATION_LOG.md`, ship the sprint without it.
- **4-hour hard cliff:** by T+4h active build time, adapter must be discovering + downloading sovereign PDFs. If not → commit whatever partial work exists, document the gap, move on.

### Saturday evening smoke test + overnight parse as a new Step 0

Spec v1's sequence didn't have a dedicated step for "fix the bug and smoke-test the fixed script." Spec v2 does:

```
STEP 0 — Docling bug fix + smoke test (Saturday afternoon/evening)
  0a: Install Docling in the canonical venv (Mac Mini likely already has it)
  0b: Verify Docling API via context7
  0c: Reproduce bug on nsm__101126915_20200330172131895.pdf
  0d: Write fixed process_one_pdf (iterate by page, not item type)
  0e: Spot check fix on 3 representative files, verify no page drops
  0f: Fix is now ready for the overnight run

STEP 1 — Docling Phase A (PR #1)
  DoclingParser class + register + config.toml default flip
  cli.py parse_run rewire to use get_parser()
  Fixed scripts/docling_reparse.py worker (from Step 0)
  luxse__*.pdf glob addition to discover_pdfs()
  Unit tests for DoclingParser
  Decision 18 doc update

STEP 2 — NSM + EDGAR incrementals (commands)
  corpus discover nsm → corpus download nsm
  corpus discover edgar → corpus download edgar
  Both in parallel shells (disjoint hosts)
  DRC confirmed present — no verification gate needed

STEP 3 — LuxSE adapter (PR #2)
  Build + 90-min soft cliff / 4-hr hard cliff
  Full LuxSE download once adapter lands

STEP 4 — Overnight Docling bulk parse (Saturday night, Mac Mini)
  Delete data/parsed_docling/ entirely (fresh start)
  Run scripts/docling_reparse.py against ALL 2,291 NSM+PDIP + new NSM + LuxSE
  ~6 hours on M4 Pro
  Monitor via tail -f data/parsed_docling/_progress.jsonl from another terminal
  User kicks off before bed; Claude is paused for the night

STEP 5 — Verify overnight parse (Sunday morning)
  Check _errors.log is empty or has only known-bad PDFs
  Spot check 5 random files — page counts match PDF reality, content present
  If issues: diagnose + partial re-parse
  If clean: proceed

STEP 6 — Task 3 (PR #3): FTS + parsed-dir promotion + grep rerun
  Delete data/parsed.pymupdf.bak (if dual-dir strategy) OR promote parsed_docling → parsed
  Update documents.parse_tool + page_count by reading JSONL headers during rebuild
  Re-run grep_matches against Docling text
  Country classifications + country backfill
  document_pages + FTS index (Docling markdown as source text)
  publish-motherduck

STEP 7 — Task 4 (PR #4): Streamlit explorer
  Landing page, search, filters, detail panel with markdown rendering
  Deep-linkable state, deploy to Streamlit Cloud
  Smoke tests: DRC, Ghana, Argentina, CAC, pari passu, governing law

STEP 8 — Polish (Monday morning)
  Demo script, warm-up ping, smoke tests, present
```

---

## Review findings synthesis (from three external agents, applied in v2)

**Review A (Gemini-style, 7 items)** — applied: compressed time estimates, atomic merge, DRC pre-step curl, re-run grep_matches, Streamlit cold-start callout, 3 PRs vs 4 (deferred — keeping 4 for clean conceptual units).

**Review B (12-item "Review of the spring-meetings sequencing spec")** — applied: CLI rewire in PR #1, LuxSE `.pdf` glob fix, DRC curl earlier, LuxSE cliff reshape, merge reversibility (moot — overnight re-parse means no merge), `grep_matches` re-run, `parse_tool` population as new code, MotherDuck schema republish sanity, Streamlit secret propagation reminder, time estimates table.

**Review C ("• Findings", 7 items)** — applied: confirmed page-count mismatch is actual content loss (not cosmetic sparsity), confirmed `documents.parse_tool` / `page_count` / `parse_version` all currently NULL, confirmed DRC is live on NSM (API query hit).

**Reviewer disagreement on one item:** Reviews A+B said "re-run grep_matches is cheap, do it"; Review C said "don't, because Docling's sparse page numbering would corrupt citations." **Resolution:** Review C's concern is obviated by the bug fix — with the fix, Docling's page numbers are no longer sparse. Re-run grep_matches after the fix is applied. Aligned with A+B.

---

## Task list state (resume here)

The MacBook Air session created these tasks; the Mac Mini session should recreate them as TaskCreate entries and continue from where this leaves off:

| # | Status | Task |
|---|---|---|
| 9 | ✅ done | Explore project context |
| 10 | ✅ done | Ask clarifying questions about scope / risk tolerance |
| 11 | ✅ done | Propose 2-3 approaches with tradeoffs |
| 12 | ✅ done | Present design for user approval (Approach Y) |
| 13 | ✅ done | Write design doc (spec v1 committed as `e999d45c`) |
| 14 | ✅ done | Spec self-review (v1) |
| 15 | ⏳ in progress | User reviews written spec (v1 reviewed by 3 agents; v2 pending) |
| 16 | ⏸️ pending | Invoke `superpowers:writing-plans` to build implementation plan |
| 17 | ⏸️ pending | Install/verify Docling in Mac Mini venv |
| 18 | ⏸️ pending | Verify Docling API for per-page iteration (via context7) |
| 19 | ⏸️ pending | Reproduce page-drop bug on `nsm__101126915_20200330172131895.pdf` |
| 20 | ⏸️ pending | Write fixed Docling worker, verify no page drops |
| 21 | ⏸️ pending | Spot check fix on 3 representative docs |
| 22 | ⏸️ pending | Rewrite spec v2 with bug fix + review findings |

**Next immediate task on the Mac Mini: #17 → #22, then continue from #15 (user reviews v2) → #16 (writing-plans).**

---

## Context: what shipped before this session

- **Task 1 (PR #61)** — Streamlit Cloud deploy spike, MotherDuck wired up, URL live at `https://sovereign-prospectus-corpus.streamlit.app`. Explorer connects to MotherDuck with a 4,769-row `documents` table. Task 1 de-risked the entire deploy path.
- **Task 2 (PR #69)** — Provenance URLs. `source_page_url` + `source_page_kind` populated for all 4,769 docs. EDGAR uses filing-index URLs, NSM uses artefact URLs, PDIP uses the search page. Zero null URLs.
- **PR #71** — Environment hygiene. `.venv/` collision with `UV_PROJECT_ENVIRONMENT` fixed, `CLAUDE.md` case-sensitivity fixed.

**The MotherDuck database is on the pre-Task-3 schema** — `document_pages`, `country_classifications`, and FTS index do not yet exist. Task 3 creates them.

---

## Corpus state (as of end-of-session 2026-04-11 afternoon)

- **NSM:** 645 PDFs parsed, 4,769-row `documents` table. Last refresh: 2026-03-28. Needs incremental.
- **EDGAR:** 2,947 HTML + 275 txt + 84 paper placeholders, last refresh 2026-03-28. Needs incremental.
- **PDIP:** 823 documents, annotation archive (not a live feed). No refresh needed.
- **LuxSE:** zero adapter, zero content. Needs to be built this sprint.
- **Docling parsed outputs (broken):** 1,468 files in `data/parsed_docling/`. Will be deleted in Step 4.
- **PyMuPDF parsed outputs:** 4,685 files in `data/parsed/`. Will be replaced at Task 3 (Step 6).

---

## Environment notes (Mac Mini specifics)

- Project lives in Dropbox. Dropbox sync handles everything EXCEPT the canonical venv (which is outside Dropbox at `~/.local/venvs/sovereign-corpus` per `UV_PROJECT_ENVIRONMENT` in `~/.zshrc`).
- Each machine has its own venv. The Mac Mini venv likely already has Docling from the March 28 run.
- To verify venv health: `uv run python -c "import sys, duckdb, polars, pytest, docling; print(sys.executable, duckdb.__version__, polars.__version__, docling.__version__)"`
- If Docling isn't installed on the Mac Mini's canonical venv, install with `uv add docling && uv sync --all-extras`. Download is ~1-2 GB of models on first run.
- **NEVER create `.venv/` in the project root** — it collides with the canonical venv and breaks `uv run`. See `CLAUDE.md` for the full explanation.

---

## Open pre-existing issues (not blocking this sprint unless flagged)

Phase 1 carryover: #5, #6, #7, #8, #9, #11, #12, #13, #16, #18, #19, #24, #25, #30, #33-#42.

Task-2 discovered: #66, #67, #68 (pre-Task-3 blocker — review before Step 6), #70, #72 (this sprint's subject, now largely superseded by the v2 spec).

**New follow-up to file this session (do it on the Mac Mini, after v2 is approved):** data-quality fix to add DRC to `data/raw/sovereign_issuer_reference.csv`. Currently only Republic of Congo is in the seed list. Standalone follow-up, not blocking.

---

## Critical reminders for the Mac Mini session

- **Do not re-run the Docling API verification curl for DRC.** It's been done, DRC is confirmed present.
- **Do not try to merge or patch the existing `data/parsed_docling/` outputs.** They're broken. Delete and re-parse.
- **Do not use `.venv/` in the project root.** Use `uv run` against the canonical venv.
- **Read `CLAUDE.md` before starting work** — it has the mandatory task execution workflow and the environment setup section.
- **The user runs with `--dangerously-skip-permissions`** — autonomous execution is expected for clearly-scoped tasks.
- **Keep using superpowers skills.** Next step after v2 spec approval is `superpowers:writing-plans`, not direct implementation.
