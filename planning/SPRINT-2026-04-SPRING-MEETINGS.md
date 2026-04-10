# Sprint: Searchable Explorer for IMF/World Bank Spring Meetings

**Sprint start:** 2026-04-10
**Target:** Monday 2026-04-13 (IMF Legal Department presentation)
**Owner:** Teal Emery, Teal Insights

---

## Intent

We are presenting this project to sovereign debt lawyers and economists at the
IMF/World Bank Spring Meetings on Monday. The audience includes people from
IMF Legal, World Bank debt teams, and the broader sovereign debt research
community. These are busy domain experts — they care about whether they can
actually use this tool, not about the engineering behind it.

**What we need to show them:** A shareable URL where they can search across
4,800+ sovereign bond prospectuses from 59 countries, see text snippets showing
why a document matched, and click through to the original source filing. The
tool should feel like something they'd bookmark and come back to.

**Why this matters now:** The sovereign debt community is currently discussing
the Republic of Congo's maiden Eurobond (filed on the London Stock Exchange on
April 8, 2026). If our explorer already has this prospectus searchable — and
they can find the contingent liabilities disclosure on pages 103-104 — the demo
goes from "interesting academic project" to "tool I want to use right now."

**Secondary goal:** Pitch a lawyer-in-the-loop annotation system where their
feedback (30 minutes/week) makes the extraction pipeline smarter over time.
That pitch document is being prepared separately. The explorer is the proof
that the underlying corpus infrastructure works.

## What Already Exists

Phase 1 is complete. Three source adapters are built and have downloaded at
scale:

- **NSM (FCA National Storage Mechanism):** 642 PDFs (591 MB)
- **EDGAR (SEC):** 3,301 PDFs (587 MB)
- **PDIP (Georgetown Law / Sovereign Debt Forum):** 823 documents (5 GB)

The pipeline can discover, download, parse (PyMuPDF), and grep for clause
patterns. DuckDB is the single source of truth. JSONL manifests are canonical
— all new fields go in manifests first, then rebuild the database.

A V1 prototype exists: a Quarto book hosted on GitHub Pages and a Shiny
clause-eval app. These were shared at the Georgetown #PublicDebtIsPublic
roundtable on March 30 and must continue working.

**What doesn't exist yet:** A shareable URL with full-text search. That's what
this sprint builds.

## Architecture Decisions (This Sprint)

1. **MotherDuck** as the cloud-hosted database. DuckDB's full-text search
   extension (BM25 scoring, Porter stemmer) enables searching inside parsed
   prospectus text — not just metadata. MotherDuck's free tier (10 GB) is
   sufficient. Hybrid execution means queries run in the cloud, not in the
   Streamlit container's memory.

2. **Streamlit Cloud** for deployment. Deploys from GitHub, free tier, produces
   a shareable URL. The `explorer/` directory lives in the main repo (not a
   separate repo — that causes schema/config drift).

3. **Page-level text storage.** Parsed text goes into a `document_pages` table
   (one row per page). FTS index on `page_text`. Search returns snippets with
   page numbers, not full documents. This avoids OOM on Streamlit Cloud's 1 GB
   memory limit.

4. **Local DuckDB fallback.** If MotherDuck is down during the demo, the app
   falls back to a local DuckDB file. Show a warning banner, but keep working.

5. **Provenance URLs in JSONL manifests.** `source_page_url` (link to the
   human-facing filing page on the original source) and `source_page_kind`
   (what the link points to: `filing_index`, `artifact_html`, `search_page`,
   etc.) are manifest fields, not derived at query time.

---

## Pre-Sprint Setup

### Step 0A: Tag V1

Before any new work, preserve the current state:

```bash
git tag -a v1-georgetown-2026-03-30 -m "V1: Georgetown roundtable prototype — Quarto book + Shiny clause-eval app"
git push origin v1-georgetown-2026-03-30
```

Verify GitHub Pages still serves the Quarto book. Check repo Settings → Pages
to confirm which branch/folder it deploys from. New work must not modify
anything under `demo/_book/` or `demo/shiny-app/`.

### Step 0B: Archive Stale Planning Documents

After tagging V1, archive planning documents from Phase 1 that are no longer
relevant to the current sprint. Move them to an `archive/` directory so they
don't create confusion or stale context:

- `SESSION-HANDOFF.md` → `archive/phase-1/SESSION-HANDOFF.md` (replace with a
  new handoff doc that references this sprint spec)
- Any Phase 1 task specs, scratch notes, or superseded planning docs that no
  longer reflect the current state of the project

Do NOT archive:
- `CLAUDE.md` (update it instead — see below)
- `docs/RATIFIED-DECISIONS.md` (still authoritative)
- `docs/DOMAIN.md`, `docs/ARCHITECTURE.md` (still relevant)
- Source adapter code, tests, config, Makefile (all still in use)
- `sql/001_corpus.sql` (still the active schema, will be extended)

### Step 0C: Update CLAUDE.md

Update the repo's `CLAUDE.md` to reference this sprint spec as the active
planning document:

- Add a "Current Sprint" section pointing to
  `planning/SPRINT-2026-04-SPRING-MEETINGS.md`
- Update the "Current Status" to reflect that Phase 1 is complete and Phase 2
  (searchable explorer) is in progress
- Add MotherDuck, Streamlit, and LSE RNS to the technology/source lists
- Keep all existing architecture decisions, domain rules, and workflow
  instructions intact

### Step 0D: Create GitHub Issues

Create a GitHub issue for each task below. Use the task title as the issue
title, the completion criteria as the issue body, and label them
`sprint:spring-meetings-2026`. Reference the issue number in commit messages.

---

## Task Breakdown

### Task 1: Deployment Spike

**Branch:** `spike/streamlit-deploy-path`

**What:** Deploy a minimal Streamlit app to Streamlit Cloud that connects to
MotherDuck and runs one query. This proves the entire deployment path before
building features. Everything else is wasted if this doesn't work.

**Steps:**
1. Create MotherDuck account (free tier), create `sovereign_corpus` database
2. Upload a small test table (e.g., 10 rows of document metadata)
3. Create `explorer/app.py` — minimal: one query, one `st.dataframe`
4. Create `explorer/requirements.txt` with pinned `duckdb` and `streamlit`
5. Create `explorer/.streamlit/config.toml` with theme settings
6. Add MotherDuck token to `.env` locally and Streamlit Cloud secrets
7. Deploy to Streamlit Cloud
8. Verify: shareable URL returns query results from a different device

**Technical requirements:**
- `@st.cache_resource` for the MotherDuck connection
- `.streamlit/secrets.toml` in `.gitignore`
- MotherDuck token NEVER in the repo
- Single pinned `requirements.txt` at repo root (Streamlit Cloud uses this;
  do not split between root and `explorer/` — version drift is guaranteed)
- Python version must be set in the Streamlit Cloud **UI** (Advanced
  Settings → Python version dropdown). Streamlit Cloud silently ignores
  `.python-version` files and defaults to the latest Python, which lacks
  pre-built wheels for `duckdb`/`pyarrow` and causes pip installs to hang
  indefinitely.
- MotherDuck connection opens with `read_only=True` to prevent accidental
  writes from exploratory UI queries.
- If `MOTHERDUCK_TOKEN` secret is missing in production, the app must fail
  fast with `st.error()` + `st.stop()`, not silently fall back to a local
  DB path (which is gitignored and absent on Streamlit Cloud).

**Connection pattern:**
```python
import duckdb
import streamlit as st

@st.cache_resource
def get_connection():
    token = st.secrets.get("MOTHERDUCK_TOKEN", None)
    if token:
        return duckdb.connect(f"md:sovereign_corpus?motherduck_token={token}")
    else:
        return duckdb.connect("data/db/corpus.duckdb")
```

**Completion criteria:**
- [ ] Streamlit Cloud URL is live and accessible from a different device
- [ ] App connects to MotherDuck and renders a table of results
- [ ] MotherDuck token is in Streamlit Cloud secrets (not in repo)
- [ ] `.streamlit/secrets.toml` is in `.gitignore`
- [ ] V1 Quarto book site still works (verify GitHub Pages)
- [ ] Pre-commit checks pass

---

### Task 2: Provenance URLs + Schema

**Branch:** `feature/provenance-urls`

**What:** Add `source_page_url` and `source_page_kind` to the documents table.
These let users click through to the original filing page on the source
(SEC EDGAR, FCA NSM, PDIP). Populate from adapter-specific logic. Add to JSONL
manifest schema so values survive DB rebuilds.

**Schema additions to `sql/001_corpus.sql`:**
```sql
source_page_url VARCHAR,        -- URL to human-facing filing page
source_page_kind VARCHAR,       -- filing_index | artifact_html | artifact_pdf | search_page | none
```

**Source-specific URL derivation:**
- **EDGAR:** `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession_with_dashes}-index.htm`
  - Note: strip dashes from accession number for the directory path, keep dashes for the filename
  - Extract `cik` and `accession_number` from `source_metadata` JSON
  - Kind: `filing_index`
- **NSM:** Use the existing artefact URL from discovery metadata. The FCA site
  may be a SPA, so deep links from `native_id` alone may not work reliably.
  Kind: `artifact_html` or `artifact_pdf`. If no stable deep link exists,
  fall back to kind: `search_page` linking to the NSM search interface.
- **PDIP:** No per-document deep links exist. Kind: `search_page` linking to
  the main PDIP search interface. Document this limitation in code comments.

**Implementation:**
1. Add fields to JSONL manifest schema
2. Write resolver functions per source (unit tested)
3. Backfill existing manifests
4. Rebuild DuckDB from updated manifests
5. Verify 3 random URLs per source resolve correctly (manual check)

**Completion criteria:**
- [ ] Both columns exist in schema DDL
- [ ] JSONL manifests include `source_page_url` and `source_page_kind`
- [ ] Resolver functions exist per source with unit tests
- [ ] EDGAR URLs use correct accession number format (verified manually)
- [ ] NSM URLs use best available link (artefact URL or search fallback)
- [ ] PDIP documented as `search_page` only
- [ ] DB rebuild from manifests works cleanly
- [ ] 3 URLs per source verified to resolve
- [ ] Pre-commit checks pass

---

### Task 3: Search Index + Parsed Text Loading

**Branch:** `feature/search-index`

**What:** Build everything needed for full-text search to work. Four sub-tasks:

**3A: Denormalized search view.** Create a `documents_search` view/table with
one row per document, pre-joining the primary issuer country from
`document_countries`. This avoids duplicate rows in the explorer.

```
document_id, source, title, issuer_name, publication_date, doc_type,
borrower_country, borrower_country_code,
wb_income_group, wb_region, ida_ibrd_status,
source_page_url, source_page_kind, download_url,
page_count, scope_status
```

**3B: Parsed text table.** Load `data/parsed/*.jsonl` into a `document_pages`
table:
```sql
CREATE TABLE document_pages (
    document_id INTEGER REFERENCES documents(document_id),
    page_number INTEGER,
    page_text VARCHAR,
    PRIMARY KEY (document_id, page_number)
);
```

Then create FTS index:
```sql
PRAGMA create_fts_index('document_pages', 'document_id', 'page_text', stemmer='porter');
```

**3C: Country classifications enrichment.** Build a `country_classifications`
table from World Bank data:
```sql
CREATE TABLE country_classifications (
    country_code VARCHAR PRIMARY KEY,   -- ISO 3166-1 alpha-3
    country_name VARCHAR,
    wb_income_group VARCHAR,            -- Low income / Lower middle income / Upper middle income / High income
    wb_region VARCHAR,                  -- Sub-Saharan Africa / East Asia & Pacific / etc.
    imf_region VARCHAR,                 -- AFR / APD / EUR / MCD / WHD
    ida_ibrd_status VARCHAR,            -- IDA / IBRD / Blend
);
```

Source: World Bank API (`api.worldbank.org/v2/country?format=json`) or their
published classification Excel. ~200 rows, essentially static. Join into
`documents_search` so each document carries its country's income group, region,
and borrowing status.

**Why this matters:** The audience works on emerging and frontier markets.
Developed-market issuances dominate the corpus by volume but are the least
interesting to them. Income group and region filters let them scope to the
countries they care about.

**3D: Country backfill.** For documents where `document_countries` is empty
(likely many EDGAR/NSM filings), extract country heuristically from
`issuer_name` using regex patterns: "Republic of X", "Kingdom of Y",
"State of X", etc. Doesn't need to be perfect — needs to work for the demo.

**3E: Makefile targets.** Add:
- `make build-search-index` — builds `document_pages`, FTS index, `documents_search` view, country classifications
- `make publish-motherduck` — pushes all tables to MotherDuck cloud database

**MotherDuck publish pattern:**
```sql
ATTACH 'md:sovereign_corpus' AS md;
CREATE OR REPLACE TABLE md.documents AS SELECT * FROM local.documents;
CREATE OR REPLACE TABLE md.document_countries AS SELECT * FROM local.document_countries;
CREATE OR REPLACE TABLE md.document_pages AS SELECT * FROM local.document_pages;
CREATE OR REPLACE TABLE md.documents_search AS SELECT * FROM local.documents_search;
CREATE OR REPLACE TABLE md.grep_matches AS SELECT * FROM local.grep_matches;
CREATE OR REPLACE TABLE md.country_classifications AS SELECT * FROM local.country_classifications;
-- Rebuild FTS index on MotherDuck (CREATE OR REPLACE drops indexes)
PRAGMA create_fts_index('md.document_pages', 'document_id', 'page_text', stemmer='porter');
```

**Completion criteria:**
- [ ] `documents_search` view returns one row per document with country + classifications
- [ ] `document_pages` table populated from parsed JSONL files
- [ ] FTS index created on `document_pages.page_text`
- [ ] FTS query `match_bm25(document_id, 'collective action clause')` returns results
- [ ] `country_classifications` table populated with WB income group, region, IDA/IBRD/Blend
- [ ] Country backfill improves country coverage for EDGAR/NSM documents
- [ ] `make build-search-index` works end-to-end
- [ ] `make publish-motherduck` pushes to MotherDuck cloud
- [ ] MotherDuck database has all tables + FTS index
- [ ] Pre-commit checks pass

---

### Task 4: Streamlit Document Explorer

**Branch:** `feature/streamlit-explorer`

**What:** Build the full explorer app. This is the thing people will actually
see and use.

**App structure:**
```
explorer/
├── app.py                  # Main Streamlit app
├── requirements.txt        # Pinned dependencies
├── .streamlit/
│   ├── config.toml         # Theme/settings
│   └── secrets.toml        # MotherDuck token (gitignored)
└── README.md
```

**UI components:**

1. **Landing page (default view).** When the app opens with no search query,
   show the most recent prospectuses sorted by `publication_date DESC LIMIT 50`.
   The user sees what's new without typing anything. This is important — the
   newest document in the corpus should be immediately visible.

2. **Header.** "Sovereign Bond Prospectus Explorer" + corpus stats (X
   documents, Y countries, Z sources).

3. **Search.** `st.form` with text input + submit button. Queries FTS index on
   `document_pages`. Returns documents ranked by BM25 relevance with text
   snippets showing the matched text and page number. No query-on-keystroke.

4. **Filters.** Country, Source (EDGAR/NSM/PDIP), Date range, Income Group
   (from `country_classifications`), Region, IDA/IBRD/Blend. Applied as SQL
   `WHERE` clauses. Consider a toggle or default: "Show emerging & frontier
   markets only."

5. **Results table.** Columns: Issuer, Title, Date, Source, Country, Relevance
   Score. Sorted by relevance (if search active) or date DESC (if browsing).
   Always `LIMIT 50`.

6. **Document detail panel.** When a result is selected:
   - Provenance links: "View on [Source] ↗" (using `source_page_url`),
     "Download PDF ↓" (using `download_url`)
   - Scrollable text pane showing parsed text (loaded page-by-page from
     MotherDuck, NOT all at once — OOM risk on 1 GB free tier)

7. **Deep-linkable state.** Search query, filters, and selected document
   encoded in URL query params (`?q=ghana&source=edgar&doc_id=123`). Someone
   can share a link to a specific search result.

**FTS query pattern:**
```sql
SELECT
    ds.document_id, ds.issuer_name, ds.title, ds.publication_date,
    ds.source, ds.borrower_country, ds.source_page_url, ds.download_url,
    fts_main_document_pages.match_bm25(dp.document_id, ?) AS score,
    dp.page_number
FROM document_pages dp
JOIN documents_search ds ON dp.document_id = ds.document_id
WHERE score IS NOT NULL
ORDER BY score DESC
LIMIT 50;
```

**OOM prevention (critical):**
- Push all computation to MotherDuck (Streamlit only renders what's on screen)
- FTS returns snippets, not full text
- Document text pane loads page-by-page, not all at once
- All queries use `LIMIT`
- Pin `duckdb` version exactly in `requirements.txt`

**Search relevance smoke tests:**
- "Ghana" → Ghana-issued documents in top results
- "Argentina" → Argentina-issued documents in top results
- "collective action clause" → documents with CAC language
- "pari passu" → documents with pari passu clauses
- "New York law" → documents governed by NY law
- "Total Return Swaps" → documents mentioning TRS
- "Congo" → DRC April 2026 base offering circular in results
- "contingent liabilities" → DRC prospectus pages 103-104 in results
- "arbitration" → DRC prospectus in results (ongoing legal proceedings)

**Completion criteria:**
- [ ] App runs locally with `streamlit run explorer/app.py`
- [ ] Landing page shows newest documents by date (no search required)
- [ ] Full-text search works for all smoke test queries above
- [ ] Country filter works
- [ ] Source filter works
- [ ] Income group filter works
- [ ] Region filter works
- [ ] Date range filter works
- [ ] "View on [Source]" links open correct pages (where available)
- [ ] "Download PDF" links work
- [ ] Document text pane shows parsed text for selected document
- [ ] Results are capped at 50 rows
- [ ] No OOM crash when searching broad terms (test: search "the")
- [ ] Deployed to Streamlit Cloud with shareable URL
- [ ] URL works from a different device / incognito window
- [ ] Deep-linkable: `?q=ghana` reopens Ghana search
- [ ] V1 Quarto book site still works
- [ ] Pre-commit checks pass

---

### Task 5: LSE RNS Adapter + Congo Ingest (Gated)

**Branch:** `feature/lse-rns-adapter`

**Gated:** Only attempt the full adapter after Tasks 1-4 are deployed and
working. However, the **Congo manual ingest is non-negotiable** — this document
must be in the explorer for Monday regardless of whether the full adapter
ships.

**Context:** The London Stock Exchange's Regulatory News Service (RNS) is the
real-time disclosure feed for UK-listed securities. Sovereign Eurobond
prospectuses are published here first, then propagated to the FCA National
Storage Mechanism (NSM) with a lag of hours to days. For a corpus that wants
to be current, LSE RNS is the live source; NSM is the historical archive.

**The Congo document:**
- PDF: `https://www.rns-pdf.londonstockexchange.com/rns/6796Z_1-2026-4-8.pdf`
- Filing page: `https://www.londonstockexchange.com/news-article/market-news/publication-of-a-base-offering-circular/17537850`
- Issuer: Republic of the Congo (verify from actual prospectus — Congo-Brazzaville, not DRC)
- Date: 2026-04-08
- Key content: Contingent liabilities from arbitration cases (pages 103-104)

**Manual ingest (do this first, regardless of adapter progress):**
1. Download the PDF
2. Create manifest entry with source = `lse_rns`, proper metadata
3. Parse via PyMuPDF → populate `document_pages`
4. Rebuild FTS index, publish to MotherDuck
5. Verify: searching "contingent liabilities" returns pages 103-104

**Full adapter (gated on time):**
- 5-minute curl test: can we list recent sovereign bond announcements? Are
  PDF URLs predictable? Server-rendered HTML or JS SPA?
- Known URL patterns:
  - Filing page: `londonstockexchange.com/news-article/market-news/{slug}/{announcement_id}`
  - PDF: `rns-pdf.londonstockexchange.com/rns/{ticker}_{sequence}-{date}.pdf`
- Source = `lse_rns` (distinct from `nsm`)
- Dedup with NSM: don't deduplicate at ingestion. Keep both rows in
  `documents`. Same prospectus from two sources is actually a feature, not a
  bug — "we track the same filing across multiple regulatory archives."
  Link via `document_families` if needed. `documents_search` can prefer the
  most recent source or flag duplicates.
- Stop signals: JS rendering required, no sovereign filtering, PDFs don't
  resolve, rate limited without retry policy

**Completion criteria:**
- [ ] Congo prospectus is in the corpus and searchable (NON-NEGOTIABLE)
- [ ] Searching "Congo" returns the document
- [ ] Searching "contingent liabilities" returns pages 103-104
- [ ] "View on Source" links to LSE filing page
- [ ] (Adapter, if attempted) Curl test documented with go/no-go evidence
- [ ] (Adapter, if go) Discovers + downloads sovereign prospectuses
- [ ] (Adapter, if go) JSONL manifest with `source_page_url`
- [ ] (Adapter, if go) Dedup strategy with NSM documented
- [ ] Published to MotherDuck and visible in deployed explorer
- [ ] Pre-commit checks pass

---

### Task 6: LuxSE Adapter (Gated, Overflow)

**Branch:** `feature/luxse-adapter`

**Gated:** Only attempt after Tasks 1-5 are done. Same pattern as LSE RNS.

5-minute curl test against Luxembourg Stock Exchange. Go/no-go based on:
server-rendered HTML? Sovereign bond prospectus links visible? PDF URLs
resolve?

Stop signals: JS rendering required, no programmatic sovereign filtering,
PDF links don't resolve, rate limited without retry policy, architecture
fundamentally incompatible with adapter pattern.

**Completion criteria:**
- [ ] Curl test documented (go/no-go with evidence)
- [ ] If go: Adapter discovers + downloads sovereign prospectuses
- [ ] If go: JSONL manifest with `source_page_url`
- [ ] If go: Ingested into DuckDB and visible in explorer
- [ ] If go: Published to MotherDuck
- [ ] If no-go: Documented in `docs/SOURCE_INTEGRATION_LOG.md`
- [ ] Pre-commit checks pass

---

### Task 7 (Overflow): Clause Family Display

**Branch:** `feature/explorer-clause-display`

When a document is selected in the explorer, show detected clause families
from the `grep_matches` table:

```
Clause Matches Found:
• Collective Action Clause — pages 12, 45, 46
• Governing Law — page 3
• Pari Passu — page 28
```

This is the "wow factor" for lawyers — they can see at a glance what contract
terms a prospectus contains, without reading 200 pages.

---

### Task 8 (Overflow): ESMA Adapter

Same gated pattern as LuxSE. Use `priii_documents` Solr core, NOT
`priii_securities`.

---

### Task 9 (Overflow): Demo Polish

- Write a 3-minute demo script with talking points
- Add a "Flag this document" button (writes to a `user_flags` table — this
  sells the annotation/feedback vision without requiring backend infrastructure)
- Update README.md to reflect new architecture
- Smoke test all provenance links from the deployed environment
- Wake the Streamlit app 5-10 minutes before the meeting (cold start ~30-45s)

---

## Workflow for Each Task

For every task in this sprint:

1. **Create branch** from updated `main`
2. **Plan** using superpowers planning mode — think through the approach before
   writing code
3. **Execute** using subagent-driven development in auto mode
4. **Verify** — lint (ruff), typecheck (pyright), test (pytest), and run the
   relevant completion criteria checks
5. **PR + code review** — open a PR, run three-agent code review, fix anything
   non-trivial
6. **Merge** to `main`
7. **Update SESSION-HANDOFF.md** with what was done and what's next

## Key Constraints (Apply to All Tasks)

- **Do not modify V1 artifacts.** `demo/_book/`, `demo/shiny-app/`, and the
  GitHub Pages deployment configuration are off-limits.
- **JSONL manifests are canonical.** All new fields go in manifests first. The
  database is rebuilt from manifests. If a field isn't in the manifest, it
  doesn't survive a rebuild.
- **Pre-commit hooks must pass.** ruff → pyright → pytest. No exceptions.
- **No Pandas in pipeline code.** Polars only. Pandas is acceptable in
  `explorer/` (Streamlit's ecosystem uses it).
- **Pin DuckDB version exactly** in both `pyproject.toml` and
  `explorer/requirements.txt`. MotherDuck compatibility depends on version
  matching.
- **All queries use LIMIT.** Never load unbounded result sets into Streamlit
  memory.
