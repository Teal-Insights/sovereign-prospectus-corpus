# Explorer V2 + EDGAR HTML Parse — Design Spec

**Date:** 2026-04-12
**Context:** Overnight Docling PDF parse running on Mac Mini (ETA tonight).
User building explorer UI on MacBook Air in parallel. EDGAR HTML files (3,222)
need Docling parsing to complete the corpus with consistent markdown quality.

**Goal:** Ship a polished, searchable document explorer with ~8,000+ sovereign
bond prospectuses from 4 sources (NSM, PDIP, LuxSE, EDGAR) for the IMF/World
Bank Spring Meetings presentation on Monday April 13.

**Council of Experts review:** Plan will be reviewed by Claude Opus, Gemini 3.1
Pro, and Codex at plan, EDGAR script, and explorer code stages.

---

## 1. EDGAR HTML Parse Script

A lightweight `scripts/docling_reparse_edgar.py` that parses EDGAR HTML/text
filings into the same output format as the PDF parser.

### Input files

| Extension | Count | Method |
|-----------|-------|--------|
| `.htm` | 2,947 | `DocumentConverter().convert(path)` directly |
| `.txt` | 275 | `DocumentStream(name='x.html', stream=BytesIO(content))` to hint HTML format |
| `.paper` | 84 | **Skip** — empty stubs ("AUTO-GENERATED PAPER DOCUMENT") |

### Why this is fast and safe

Docling HTML parsing uses `SimplePipeline` (BeautifulSoup), NOT
`StandardPdfPipeline` (ML models). Key differences from PDF parsing:

- **Zero ML models loaded** — no layout detection, no table structure, no OCR
- **~1.3 MB memory per conversion** — no memory leak
- **No GPU/MPS usage** — pure Python
- **No worker recycling needed** — memory stays flat
- **Sequential processing is fine** — no process pool overhead justified

Estimated time: 30-60 minutes for 3,222 files.

### Output format

Same as PDF parser, to `data/parsed_docling/`:

- `{storage_key}.jsonl` — header line + single page record (page 0)
- `{storage_key}.md` — full Docling markdown

Header fields:
```json
{
  "storage_key": "edgar__0000903423-04-000474",
  "page_count": 1,
  "parse_tool": "docling-html",
  "parse_version": "2.86.0",
  "parse_status": "parse_ok",
  "parsed_at": "2026-04-13T..."
}
```

`page_count` is 1 (HTML has no pages — the whole document is one "page").
`parse_tool` is `"docling-html"` to distinguish from `"docling"` (PDF).

### Resume support

Same as PDF parser: skip files where both `.jsonl` AND `.md` exist with
size > 0.

### Atomic writes

Same `.part` → `os.replace` pattern.

### Progress logging

Append to `data/parsed_docling/_progress.jsonl` with same schema. `memory_gb`
will be near-zero (no ML models).

## 2. Auto-chain wrapper

`scripts/chain_overnight.sh` — starts automatically after the PDF parse,
runs EDGAR HTML parse, then validates.

### Sequence

```
PDF parse (currently running) → EDGAR HTML parse (30-60 min) → validation → done
```

### Behavior

1. Poll `pgrep -f "docling_reparse.py"` every 5 minutes
2. When PDF parse exits, check `_summary.json` for completion
3. Start EDGAR HTML parse: `uv run python scripts/docling_reparse_edgar.py`
4. When EDGAR finishes, run `uv run python scripts/validate_parse_output.py`
5. Write `data/parsed_docling/_chain_complete.json` with timestamps and stats

### What it does NOT do

Does not run `corpus ingest`, `build-pages`, `build-markdown`, or
`publish-motherduck`. Those are manual morning steps that depend on branch
state and should be verified before running.

### Remote monitoring

From phone via SSH:
```bash
bash scripts/parse_status.sh
cat data/parsed_docling/_chain_complete.json
```

## 3. Explorer UI (MacBook Air)

### Branch

`feature/explorer-v2` off `main`. Separate from Mac Mini's
`feature/docling-bug-fix-and-sprint-v2`.

### Database

Rebuild from scratch on the Air using Docling outputs synced via Dropbox:
```bash
rm -f data/db/corpus.duckdb
uv run corpus ingest --run-id explorer-dev-$(date +%Y%m%d)
uv run corpus build-pages --parsed-dir data/parsed_docling
uv run corpus build-markdown --parsed-dir data/parsed_docling
```

Today: ~4,400+ docs (NSM + PDIP + LuxSE with Docling markdown).
Tomorrow after chain: ~8,000+ docs (adding EDGAR).

### Pages

**Landing page:**
- Corpus stats: document count, source count, country count
- Teal Insights logo
- Brief description: "X sovereign bond prospectuses from Y countries across
  Z sources — searchable full text with structured document view"
- Invitation: "This is an early version. We'd love your feedback on what
  would be most useful for your work."

**Search page:**
- Full-text search bar
- DuckDB FTS with BM25 scoring
- Results show: document title, issuer name, source, publication date,
  text snippet with highlighted match term
- Click result → detail page

**Detail page:**
- Full Docling markdown rendered inline (via `st.markdown()`)
- Metadata sidebar: source, publication date, issuer, download link to
  original filing (`source_page_url`)
- Back to search results

### What it does NOT need for Monday

- Country/source/date filters — nice-to-have, not critical
- Clause extraction display — separate task
- User accounts or saved searches
- Flag/feedback button — can add later in the week

### Tech stack

Streamlit (already deployed as spike), MotherDuck for cloud queries, local
DuckDB fallback. Pandas OK in explorer/ (per CLAUDE.md).

### Data flow

```
Air: ingest → build-pages → build-markdown → publish-motherduck
                                                    ↓
                                        MotherDuck (cloud DB)
                                                    ↓
                                        Streamlit Cloud (app.py)
                                                    ↓
                                        Shareable URL for demo
```

## 4. Council of Experts review gates

| Gate | When | What | Risk if skipped |
|------|------|------|----------------|
| **Plan review** | After writing implementation plan | Plan document | Structural mistakes, wrong task ordering |
| **EDGAR script review** | After implementing `docling_reparse_edgar.py` | Code, before overnight chain | Script failure loses overnight window |
| **Explorer code review** | After explorer UI is functional | Streamlit code, before MotherDuck publish | Broken demo in front of IMF Legal |

The EDGAR script review is time-sensitive — must pass before bed tonight so
the chain can run overnight.

## 5. What we're NOT doing

- Not modifying v1 (`demo/_book/`, `demo/shiny-app/`)
- Not parsing `.paper` files (84 empty stubs)
- Not adding country filters for Monday (search alone is compelling)
- Not building a separate EDGAR adapter (manifests and files already exist)
- Not running EDGAR parse on the Air (Mac Mini is faster, files are local)
- Not changing the running PDF parse script
- Not doing clause extraction re-run (depends on full corpus, can do Tuesday)

## 6. Files changed

| File | Machine | Action |
|------|---------|--------|
| `scripts/docling_reparse_edgar.py` | Mac Mini | New — sequential EDGAR HTML parser |
| `scripts/chain_overnight.sh` | Mac Mini | New — auto-chain wrapper |
| `explorer/app.py` | MacBook Air | Rewrite — search, detail, polish |

## 7. Completion criteria

1. EDGAR HTML script parses 3,222 `.htm`/`.txt` files to `data/parsed_docling/`
2. Chain wrapper runs PDF → EDGAR → validation unattended overnight
3. Explorer has landing page with stats, logo, invitation text
4. Explorer has full-text search with BM25 snippets
5. Explorer has detail page with rendered Docling markdown
6. Explorer works on MotherDuck (shareable URL) and local DuckDB (fallback)
7. Council reviews pass on plan, EDGAR script, and explorer code
8. All data published to MotherDuck with FTS index
9. Shareable URL works from a phone/different device

## 8. Timeline

| When | What | Where |
|------|------|-------|
| Sunday afternoon | Build explorer UI on ~4,400 Docling docs | MacBook Air |
| Sunday evening | Council review EDGAR script, start chain wrapper | Mac Mini |
| Sunday night | PDF parse finishes → EDGAR parse runs → validation | Mac Mini (unattended) |
| Monday morning | Check chain_complete.json, re-ingest full corpus, publish | Phone/Air/Mini |
| Monday noon | Demo to IMF Legal with ~8,000 docs | Shareable URL |
| Mon–Wed | Fix issues, add EDGAR if still running, polish | Both machines |
| Wed–Thu | Full corpus demos to other meetings | Shareable URL |
