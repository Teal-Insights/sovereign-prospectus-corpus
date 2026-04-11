# SESSION-HANDOFF.md — Current Sprint

**Last updated:** 2026-04-11 (end of Task 2 session)
**Sprint:** Searchable Explorer for IMF/World Bank Spring Meetings
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Sprint spec:** `planning/SPRINT-2026-04-SPRING-MEETINGS.md`
**Status:** Tasks 1 + 2 merged. **Sprint order revised — Docling migration (#72) is now next**, then Task 3.

## ⏭️ START HERE TOMORROW

**Next task:** Issue #72 — "Migrate to Docling as default PDF parser + bulk reparse the corpus"

The full plan is in the issue body. Five phases (A-E), ~6-8 hours wall clock total, ~2-3 hours user-attended (the rest is unattended bulk reparse on the M4 Pro). **Phase A is the only piece that needs an active code session — everything else is "kick off the bulk reparse and check on it."**

**Phase A starting commands** (from the issue):

```bash
# Create the feature branch from current main
git checkout main && git pull --ff-only
git checkout -b feature/docling-default

# Cherry-pick JUST the script file from the stale branch (NOT git cherry-pick — that
# would pull in the commit which touches obsolete pre-Phase-2 files)
git checkout feature/30-docling-reparse -- scripts/docling_reparse.py

# Then: add docling to pyproject.toml, write src/corpus/parsers/docling_parser.py
# implementing the parser protocol, register it in registry.py, set as default,
# add tests, run pytest, commit + PR
```

**Why Docling before Task 3:** Task 3 builds the FTS index over `data/parsed/*.jsonl`. Building it over PyMuPDF text now and reparsing later means rebuilding the FTS index. Reparse first → build FTS once. Saves ~2-3 hours of rework on Task 3.

**Critical fact for Phase A:** `feature/30-docling-reparse` is forked from pre-Phase-2 main and is missing every clause-extraction-v2 file + every Task 2 file. **Do NOT try to merge or cherry-pick the branch wholesale.** Use `git checkout feature/30-docling-reparse -- scripts/docling_reparse.py` to grab just the one file. The rest of Phase A is fresh code on top of current main.

**Bulk reparse context:**
- ~1,470 documents already Docling-parsed at `data/parsed_docling/` (from a prior partial run)
- ~3,300 documents still need work
- Script has resume support, will skip already-parsed docs
- ~4-5 hours unattended on the M4 Pro (user-validated)
- Run with `tail -f data/parsed_docling/_progress.jsonl` to monitor

## Live artifacts

- **Explorer URL:** https://sovereign-prospectus-corpus.streamlit.app
- **MotherDuck database:** `sovereign_corpus` (4,769 documents, duckdb 1.4.4 client/server). **Still on the pre-Task-2 schema** — Task 3 publishes the new provenance columns. Docling migration doesn't touch MotherDuck either.
- **V1 Georgetown demo:** tagged `v1-georgetown-2026-03-30` (Quarto book on `gh-pages` branch — do NOT modify)

## Sprint Tasks (revised order — Docling inserted before Task 3)

- [x] Task 1: Deployment Spike (Streamlit Cloud + MotherDuck) — PR #61 merged
- [x] Task 2: Provenance URLs + Schema — PR #69 merged 2026-04-11
- [ ] **Docling migration + bulk reparse — issue #72** ← NEXT
- [ ] Task 3: Search Index + Parsed Text Loading
- [ ] Task 4: Streamlit Document Explorer
- [ ] Task 5: LSE RNS Adapter + Congo Ingest (gated)
- [ ] Task 6: LuxSE Adapter (gated, overflow)
- [ ] Task 7: Clause Family Display (overflow)
- [ ] Task 8: ESMA Adapter (overflow)
- [ ] Task 9: Demo Polish (overflow)

Sprint GitHub issues: #51-#59 with label `sprint:spring-meetings-2026`. Plus #72 (Docling) added 2026-04-11.

## Task 2 recap (PR #69, merged 2026-04-11 as `d99f9a27`)

The full implementation plan is at `docs/superpowers/plans/2026-04-10-task2-provenance-urls.md`. It went through 6 rounds of review (3 plan-stage external + 1 internal pre-PR + 2 GitHub bot rounds) before merging.

What shipped:
- `documents.source_page_url` + `source_page_kind` columns populated for all 4,769 docs (zero null URLs)
- Per-source resolvers in `src/corpus/sources/provenance.py`:
  - EDGAR: SEC filing-index URL builder from `cik` + `accession_number`
  - NSM: extension classifier via `urllib.parse.urlparse` (handles future query strings)
  - PDIP: static Georgetown search page (no per-doc deep links exist)
  - Dispatcher returns `(None, "none")` for unknown sources — crash-safe for future adapters
- Atomic-pair semantics in both ingest fallback and backfill — no setdefault-and-mix or preserve-explicit-null bugs
- `scripts/regenerate_pdip_manifest.py` — one-off bridge with locale-invariant date parser (`_MONTH_NAMES` lookup table, no `strptime("%B")`)
- `scripts/backfill_provenance_urls.py` — atomic rewrite of all three manifests, idempotent with byte stability
- UTF-8 + `ensure_ascii=False` everywhere JSON gets written
- DB rebuild preserved `pdip_clauses` (6,251) + `grep_matches` (106,229) via `ATTACH` + storage_key remap, zero data loss
- 35 new tests, 397 total passing
- 3 EDGAR + 3 NSM + 1 PDIP URLs verified live with HTTP 200

## PR #71 (env hygiene, merged 2026-04-11 as `04278de1`)

Side effort that surfaced during Task 2 cleanup. Two operational gotchas resolved:

1. **Stray `.venv/` collided with `UV_PROJECT_ENVIRONMENT`.** The project lives inside Dropbox; `~/.zshrc` deliberately sets `UV_PROJECT_ENVIRONMENT=~/.local/venvs/sovereign-corpus` to keep the venv outside Dropbox. Something created a competing `.venv/` in the project root. `uv run` warned + intermittently fell through to `/opt/anaconda3/bin/python`. Fix: stray `.venv/` deleted, canonical venv synced to `pyproject.toml` via `uv sync --all-extras` (it had drifted to duckdb 1.5.1 + missing pytest/polars). New "Environment setup (Dropbox + uv)" section added to `CLAUDE.md`.

2. **`Claude.md` was tracked as mixed-case** while every other doc reference used `CLAUDE.md`. macOS's case-insensitive filesystem hid the mismatch until `git add CLAUDE.md` silently no-op'd. Fix: `git mv Claude.md → _temp → CLAUDE.md` (two-step rename trick). `AGENTS.md` updated to point at the new canonical name.

**Read `CLAUDE.md` (uppercase) tomorrow** — it has the new env setup section.

## Local cleanup done at session end

- 7 merged feature branches deleted (feature/29-review-fixes-and-specs, feature/29-shiny-display-fixes, feature/clause-extraction-v2, feature/clause-extraction-v2-spec, feature/roundtable-demo, feature/scaffold, feature/source-nsm)
- 4 cruft files deleted (`pr_diff.txt`, `pr_code_diff.txt`, 2 logo PNGs)
- 2 DB backups deleted (`corpus.duckdb.bak`, `corpus.duckdb.prev`)
- Stray `.venv/` deleted (~737 MB)
- **~1.02 GB freed total**

## Local branches preserved (do NOT delete tomorrow without checking)

- `feature/19-pdip-annotations-harvester` — unmerged WIP
- `feature/30-docling-reparse` — **the source of `scripts/docling_reparse.py`** for issue #72. Don't delete until Phase A cherry-picks the file. Then can be deleted in Phase E.
- `feature/clause-extraction-docs` — unmerged WIP
- `feature/run-reports` — unmerged WIP
- `feature/source-edgar` — unmerged WIP
- `gh-pages` — V1 Quarto book serving branch, frozen

## Untracked files left in working tree (deliberately not deleted)

- `.claude/settings.local.json` — personal Claude Code settings, gitignored
- `scripts/process_cac_batches_101_150.py` — real batch processing script, related to issue #70
- `demo/data/all_extractions.csv` (79M), `demo/data/classification.csv`, `demo/data/corpus_summary.csv` — substantial extraction outputs, unknown owner
- `demo/shiny-app/data/all_extractions.csv` (79M) — V1 Shiny territory, frozen per CLAUDE.md
- `demo/shiny-app/rsconnect-python/` — shinyapps.io deploy config

## Open follow-up issues filed during Task 2

| # | Title | Priority |
|---|---|---|
| #66 | PDIP ingest bypasses manifest-canonical pipeline | Worked around in Task 2; revisit eventually |
| #67 | Pre-commit broken on main: 163 ruff errors in `scripts/`, 28 pyright errors in `verify.py`/`test_reflow.py`/`test_verify.py` | YAML parse bug fixed in Task 2; the rest is debt |
| #68 | DB rebuild preservation should be a committed script | **Pre-Task-3 work** — resolve before `make publish-motherduck` runs |
| #70 | Stale `clause_candidates_v2.csv` orphan work (rescue branch deleted, intent preserved) | Revisit if/when V1 Shiny is unfrozen |
| **#72** | **Docling migration + bulk reparse** | **NEXT — sprint priority** |

## Phase 1 (Complete, reference only)

All Phase 1 planning docs archived in `archive/phase-1/`.

- NSM: 642 PDFs (591 MB), 899 sovereign filings discovered
- EDGAR: 3,301 PDFs (587 MB), 3,306 filings from 27 CIKs
- PDIP: 823 documents (5 GB), zero download failures
- PDIP annotations: 162/162 processed (122 success, 40 zero-clause)

## Open Pre-Existing Issues

Carried from Phase 1: #5, #6, #7, #8, #9, #11, #12, #13, #16, #18, #19, #24, #25, #30, #33-#42. Don't block on these unless directly relevant to current task.

Task-2-discovered: #66, #67, #68, #70, #72 (see above).

## Environment notes (in CLAUDE.md but worth flagging here too)

- The canonical venv lives at `~/.local/venvs/sovereign-corpus` (NOT `.venv/` in the project root). Configured via `~/.zshrc`'s `UV_PROJECT_ENVIRONMENT`.
- If `uv run` warns about `VIRTUAL_ENV=.venv does not match...`, check that nothing created a new `.venv/` in the project root. Fix with `rm -rf .venv && unset VIRTUAL_ENV` (or open a new terminal).
- To verify the venv is healthy: `uv run python -c "import sys, duckdb, polars, pytest; print(sys.executable, duckdb.__version__, polars.__version__, pytest.__version__)"`. Expect Python 3.12.8, duckdb 1.4.4, polars >=1.39, pytest 9.x.
- If anything's missing: `uv sync --all-extras`.
