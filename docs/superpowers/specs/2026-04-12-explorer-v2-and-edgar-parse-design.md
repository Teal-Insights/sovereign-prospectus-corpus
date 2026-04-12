# Explorer V2 + EDGAR HTML Parse — Design Spec

**Date:** 2026-04-12
**Context:** Overnight Docling PDF parse running on Mac Mini (ETA tonight).
User building explorer UI on MacBook Air in parallel. EDGAR HTML files (3,222)
need Docling parsing to complete the corpus with consistent markdown quality.

**Goal:** Ship a polished, searchable document explorer with ~8,000+ sovereign
bond prospectuses from 4 sources (NSM, PDIP, LuxSE, EDGAR) for the IMF/World
Bank Spring Meetings presentation on Monday April 13.

**Council of Experts review:** Spec reviewed by Claude Opus, Gemini 3.1 Pro,
and Codex. Findings incorporated below (SGML stripping, page splitting,
Congo filing, chain robustness, explorer filters).

---

## 1. EDGAR Parse Script

`scripts/docling_reparse_edgar.py` — parses EDGAR HTML/text filings with
SGML stripping, page splitting, and Docling markdown generation.

### Preprocessing: SGML wrapper stripping

Every EDGAR file (`.htm`, `.txt`) is wrapped in an SGML envelope:
```
<DOCUMENT>
<TYPE>424B5
<SEQUENCE>1
<FILENAME>...
<TEXT>
...actual content here...
</TEXT>
</DOCUMENT>
```

**Step 1:** Extract content between `<TEXT>` and `</TEXT>` tags. Discard the
SGML envelope. This is mandatory — passing raw files to Docling would include
`<DOCUMENT>`, `<TYPE>` etc. as rendered text.

### Page splitting

EDGAR files contain page markers that the existing parsers already handle:

| Extension | Count | Page markers | Prevalence |
|-----------|-------|-------------|------------|
| `.htm` | 2,947 | CSS `page-break-before/after:always` | ~65% of files |
| `.txt` | 275 | `<PAGE>` markers | ~98% of files |
| `.paper` | 84 | **Skip** — empty stubs | N/A |

**Step 2:** After SGML stripping:
- For `.htm` files: use CSS page-break detection (same logic as
  `src/corpus/parsers/html_parser.py`) to split into pages. Files without
  page breaks become a single page.
- For `.txt` files: split on `<PAGE>` markers (same logic as
  `src/corpus/parsers/text_parser.py`). This preserves page citations.

### Markdown generation

**Step 3:** Pass each page's HTML content through Docling's HTML pipeline
(`SimplePipeline` / BeautifulSoup) for structured markdown. This gives us
headings, tables, and formatting — not just raw text.

For `.txt` pages that contain plain text (not HTML): write the text directly
as markdown (it's already readable). Set `parse_tool` to `"text-passthrough"`.

### Why this is fast and safe

Docling HTML parsing uses `SimplePipeline` (BeautifulSoup), NOT
`StandardPdfPipeline` (ML models):

- **Zero ML models loaded** — no layout detection, no table structure, no OCR
- **~1.3 MB memory per conversion** — no memory leak
- **No GPU/MPS usage** — pure Python
- **No worker recycling needed** — memory stays flat
- **Sequential processing is fine** — no process pool overhead justified

Estimated time: 30-60 minutes for 3,222 files.

### Output format

Same as PDF parser, to `data/parsed_docling/`:

- `{storage_key}.jsonl` — header line + per-page records (0-indexed)
- `{storage_key}.md` — full Docling markdown (all pages concatenated)

Header fields:
```json
{
  "storage_key": "edgar__0000903423-04-000474",
  "page_count": 17,
  "parse_tool": "docling-html",
  "parse_version": "2.86.0",
  "parse_status": "parse_ok",
  "parsed_at": "2026-04-13T..."
}
```

`page_count` reflects actual page count from page-break splitting (not always
1). `parse_tool` is `"docling-html"` for HTML files, `"text-passthrough"` for
plain text `.txt` files.

### Error handling

Try/except per file with error logging to `_errors.log`. Progress counter and
final summary — mirror the PDF parser's reporting pattern. Files that fail
Docling conversion are logged and skipped, not fatal.

### Resume support

Same as PDF parser: skip files where both `.jsonl` AND `.md` exist with
size > 0.

### Atomic writes

Same `.part` → `os.replace` pattern.

### Smoke test before full run

Before starting the full batch, parse 5 representative files as a canary:
one `.htm` with page breaks, one `.htm` without, one `.txt` with `<PAGE>`
markers, one `.txt` without, and verify one `.paper` is correctly skipped.
Abort if any canary fails.

## 2. Congo Filing (non-negotiable demo item)

The sprint spec makes the Republic of Congo's April 2026 LSE RNS Eurobond
filing a **non-negotiable** demo item. The killer demo is searching
"contingent liabilities" and finding pages 103-104 of this prospectus.

### Manual ingest steps (before Monday demo)

1. Download Congo PDF from LSE RNS to `data/original/`
2. Create manifest entry in `data/manifests/lse_rns_manifest.jsonl`
3. Parse with Docling (single file — can do on either machine)
4. Ingest, build-pages, build-markdown, publish
5. Verify: search "contingent liabilities" returns Congo filing

This is a separate task from the EDGAR batch parse. It can be done on the
Air as part of explorer development, or on the Mini after the chain completes.

## 3. Auto-chain wrapper

`scripts/chain_overnight.sh` — starts after the PDF parse, runs EDGAR HTML
parse, then validates.

### Sequence

```
PDF parse (running) → verify success → EDGAR HTML parse → validation → done
```

### Behavior

1. Record start time
2. Wait for PDF parse to finish: poll for `_summary.json` with `finished_at`
   timestamp newer than chain start time (not `pgrep` — avoids PID race)
3. Verify PDF parse succeeded: check `shutdown_requested: false` and
   `failed < total * 0.05` (error budget)
4. If PDF parse failed/aborted: write `_chain_complete.json` with error, exit
5. Run EDGAR smoke test (5 canary files). If any fail, write error and exit.
6. Start EDGAR HTML parse: `uv run python scripts/docling_reparse_edgar.py`
7. When EDGAR finishes, run `uv run python scripts/validate_parse_output.py`
8. Write `data/parsed_docling/_chain_complete.json` with timestamps, stats,
   and stage-by-stage results

### Chain telemetry

Write a `_chain_log.jsonl` with one entry per stage transition:
```json
{"stage": "waiting_for_pdf", "timestamp": "...", "status": "started"}
{"stage": "pdf_complete", "timestamp": "...", "completed": 6420, "failed": 8}
{"stage": "edgar_smoke_test", "timestamp": "...", "status": "passed"}
{"stage": "edgar_parse", "timestamp": "...", "status": "started"}
{"stage": "edgar_complete", "timestamp": "...", "completed": 3138, "failed": 12}
{"stage": "validation", "timestamp": "...", "status": "passed"}
{"stage": "chain_complete", "timestamp": "...", "total_elapsed_s": 28800}
```

This makes phone monitoring unambiguous — `tail -1 _chain_log.jsonl` shows
exactly which stage we're in.

### What it does NOT do

Does not run `corpus ingest`, `build-pages`, `build-markdown`, or
`publish-motherduck`. Those are manual morning steps that depend on branch
state and should be verified before running.

### Remote monitoring

From phone via SSH:
```bash
tail -1 data/parsed_docling/_chain_log.jsonl    # Current stage
bash scripts/parse_status.sh                     # Full status
cat data/parsed_docling/_chain_complete.json     # Final result
```

## 4. Explorer UI (MacBook Air)

### Branch

`feature/explorer-v2` off `main`. Separate from Mac Mini's
`feature/docling-bug-fix-and-sprint-v2`.

### Merge order (Monday morning)

1. Mac Mini: merge `feature/docling-bug-fix-and-sprint-v2` → `main` first
   (parse scripts, memory monitoring, data pipeline changes)
2. MacBook Air: rebase `feature/explorer-v2` onto updated `main`
3. Resolve any conflicts (likely `SESSION-HANDOFF.md` only)
4. Run full pipeline: ingest → build-pages → build-markdown → publish

### Database

Rebuild from scratch on the Air using Docling outputs synced via Dropbox:
```bash
rm -f data/db/corpus.duckdb
uv run corpus ingest --run-id explorer-dev-$(date +%Y%m%d)
uv run corpus build-pages --parsed-dir data/parsed_docling
uv run corpus build-markdown --parsed-dir data/parsed_docling
```

**Before starting ingest:** verify Dropbox sync is complete. Check file counts:
```bash
ls data/parsed_docling/nsm__*.jsonl | wc -l    # expect ~461
ls data/parsed_docling/pdip__*.jsonl | wc -l   # expect ~434
ls data/parsed_docling/luxse__*.jsonl | wc -l  # expect ~3500+
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
- Source filter (`st.multiselect`) and country filter (if country data available)
- Click result → detail page

**Detail page:**
- Docling markdown rendered page-by-page (not full document at once — avoids
  Streamlit OOM on large EDGAR filings that can produce 2M+ chars of markdown)
- Page navigation (prev/next or page selector)
- Metadata sidebar: source, publication date, issuer, download link to
  original filing (`source_page_url`)
- Back to search results

### Tech stack

Streamlit (already deployed as spike), MotherDuck for cloud queries, local
DuckDB fallback. Pandas OK in explorer/ (per CLAUDE.md).

### Deployment checklist

- [ ] Streamlit Cloud Python version matches 3.12
- [ ] `.streamlit/secrets.toml` has MotherDuck token
- [ ] Cold-start warm-up: ping the URL 5 min before demo
- [ ] Test from phone/incognito to verify shareable URL works
- [ ] Local Streamlit on Air as fallback if MotherDuck is unreachable

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

## 5. Council of Experts review gates

| Gate | When | What | Risk if skipped |
|------|------|------|----------------|
| **Plan review** | After writing implementation plan | Plan document | Structural mistakes, wrong task ordering |
| **EDGAR script + chain wrapper review** | After implementing both | Code, before overnight chain | Script failure loses overnight window |
| **Explorer code review** | After explorer UI is functional | Streamlit code, before MotherDuck publish | Broken demo in front of IMF Legal |

The EDGAR script review is time-sensitive — must pass before bed tonight so
the chain can run overnight. Include `chain_overnight.sh` in the same review.

## 6. What we're NOT doing

- Not modifying v1 (`demo/_book/`, `demo/shiny-app/`)
- Not parsing `.paper` files (84 empty stubs)
- Not building a separate EDGAR adapter (manifests and files already exist)
- Not running EDGAR parse on the Air (Mac Mini is faster, files are local)
- Not changing the running PDF parse script
- Not doing clause extraction re-run (depends on full corpus, can do Tuesday)
- Not building deep-linkable URL state for Monday (can add later in week)

## 7. Files changed

| File | Machine | Action |
|------|---------|--------|
| `scripts/docling_reparse_edgar.py` | Mac Mini | New — EDGAR HTML/text parser with SGML stripping and page splitting |
| `scripts/chain_overnight.sh` | Mac Mini | New — auto-chain with stage telemetry |
| `explorer/app.py` | MacBook Air | Rewrite — search, page-by-page detail, filters, polish |

## 8. Completion criteria

1. EDGAR script strips SGML wrappers and splits pages correctly
2. EDGAR script parses 3,222 `.htm`/`.txt` files to `data/parsed_docling/`
3. Chain wrapper verifies PDF parse success before starting EDGAR
4. Chain wrapper writes stage-by-stage telemetry to `_chain_log.jsonl`
5. Congo filing manually ingested and searchable
6. Explorer has landing page with stats, logo, invitation text
7. Explorer has full-text search with BM25 snippets
8. Explorer has page-by-page detail view (not full doc — avoids OOM)
9. Explorer has source filter (country filter if data available)
10. Explorer works on MotherDuck (shareable URL) and local DuckDB (fallback)
11. Council reviews pass on plan, EDGAR script + chain, and explorer code
12. All data published to MotherDuck with FTS index
13. Shareable URL works from a phone/different device
14. Smoke test (5 EDGAR canary files) passes before full batch

## 9. Timeline

| When | What | Where |
|------|------|-------|
| Sunday afternoon | Build explorer UI on ~4,400 Docling docs | MacBook Air |
| Sunday evening | Implement EDGAR script + chain, council review, start chain | Mac Mini |
| Sunday evening | Manual Congo ingest | Air or Mini |
| Sunday night | PDF parse finishes → EDGAR parse runs → validation | Mac Mini (unattended) |
| Monday morning | Check chain_log.jsonl, re-ingest full corpus, publish | Phone/Air/Mini |
| Monday pre-demo | Warm up Streamlit Cloud, test from phone | Phone |
| Monday noon | Demo to IMF Legal with ~8,000 docs | Shareable URL |
| Mon–Wed | Fix issues, polish, add filters/deep-links | Both machines |
| Wed–Thu | Full corpus demos to other meetings | Shareable URL |
