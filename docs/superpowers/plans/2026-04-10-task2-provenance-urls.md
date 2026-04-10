# Task 2 — Provenance URLs + Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `source_page_url` and `source_page_kind` columns to the `documents` table, populate them via per-source resolver functions, and rebuild the local DuckDB from updated JSONL manifests so future rebuilds preserve the new fields.

**Architecture:** JSONL manifests are canonical. Add two columns to `sql/001_corpus.sql`, extend the ingest allowlist in `src/corpus/db/ingest.py` so the fields land as top-level columns (not in `source_metadata` JSON), write pure resolver functions in a new `src/corpus/sources/provenance.py` module (one per source + a dispatcher), write a one-off bridge script to regenerate `pdip_manifest.jsonl` from the current DB + inventory CSV (because PDIP data predates the manifest-canonical pipeline — see #66), write a backfill script that rewrites each manifest in place with the new fields via atomic `.part` → rename, then do a clean full rebuild of `corpus.duckdb` via `corpus ingest` and verify row counts. Out of scope: MotherDuck publish (Task 3) and surfacing URLs in the Streamlit UI (Task 4).

**Tech Stack:** Python 3.12, uv, DuckDB 1.4.4, Polars (pipeline), pytest, ruff, pyright, Click CLI.

**Issue:** #52 (sprint:spring-meetings-2026)
**Branch:** `feature/provenance-urls` (already created)
**Related:** #66 (PDIP ingest tech debt — worked around, not fixed)

**Review fixes incorporated (2026-04-10):** Three independent reviews of an earlier draft caught (a) a `ConversionException` in the rebuild caused by free-text dates in the PDIP inventory CSV being written straight into `documents.publication_date`, (b) silent loss of `pdip_clauses` (6,251 rows) and `grep_matches` (106,229 rows) on the DB swap, (c) a SEC 403 on `curl -I` against EDGAR filing-index URLs, (d) a commit step that was never going to work because `data/**` is gitignored and the manifests exceed the 500KB large-file hook, and (e) missing `pre-commit run --all-files` in the verification step. Each fix is called out inline where it lives.

**Research input:** `docs/superpowers/specs/2026-04-10-task2-manifest-research.md` has per-source field layouts and resolver logic — read it alongside this plan.

**Key state facts (verified 2026-04-10):**

- Local DB `data/db/corpus.duckdb`: `edgar=3301`, `nsm=645`, `pdip=823`, total `4769`.
- Manifests on disk: `data/manifests/edgar_manifest.jsonl` (3301 lines), `data/manifests/nsm_manifest.jsonl` (645 lines). **No `pdip_manifest.jsonl`** — must be regenerated from DB + inventory.
- EDGAR rows have `source_metadata` JSON with `cik` + `accession_number`.
- NSM `download_url` is the artefact URL itself (e.g. `https://data.fca.org.uk/artefacts/NSM/RNS/{seq_id}.html`). Some are `.pdf`, some are `.html`/`.htm`.
- PDIP DB rows are impoverished: only `source`, `native_id`, `storage_key`, `file_path` populated; no `download_url`, no `source_metadata`, no title/issuer/date.
- PDIP richer metadata lives in `data/pdip/pdip_document_inventory.csv` (825 rows, columns: `id, document_title, tag_status, country, instrument_type, creditor_country, creditor_type, entity_type, document_date, maturity_date`).

---

## File Structure

**Created:**

- `src/corpus/sources/provenance.py` — pure resolver functions: `build_edgar_source_page(record)`, `build_nsm_source_page(record)`, `build_pdip_source_page(record)`, `resolve_source_page(record)` dispatcher. Each returns `(url: str | None, kind: str)`.
- `tests/test_provenance.py` — unit tests for each resolver: happy paths, edge cases, and the dispatcher.
- `tests/test_ingest_provenance.py` — round-trip test: a manifest record with `source_page_url` / `source_page_kind` lands as top-level columns in the `documents` row (not in `source_metadata` JSON).
- `scripts/regenerate_pdip_manifest.py` — one-off bridge (see #66). Reads 823 PDIP rows from current DB, LEFT JOINs `data/pdip/pdip_document_inventory.csv` on `native_id = id` for enrichment, derives `download_url` from `native_id`, writes `data/manifests/pdip_manifest.jsonl`. Idempotent (overwrites via `.part` → rename).
- `scripts/backfill_provenance_urls.py` — rewrites each `data/manifests/*_manifest.jsonl` with `source_page_url` + `source_page_kind` fields added, using the dispatcher. Atomic `.part` → rename.

**Modified:**

- `sql/001_corpus.sql:9-33` — add `source_page_url VARCHAR` and `source_page_kind VARCHAR` to the `documents` CREATE TABLE. Also append an `ALTER TABLE documents ADD COLUMN IF NOT EXISTS` pair after line 59 so existing DBs upgrade in place.
- `src/corpus/db/ingest.py:25-47` — add `source_page_url` and `source_page_kind` to the `_DOCUMENT_COLUMNS` frozenset.

**Untouched but relied on:**

- `src/corpus/db/schema.py` — already runs 001_corpus.sql statement-by-statement.
- `src/corpus/cli.py:1092` — `corpus ingest` CLI command, used as-is for rebuild.
- `src/corpus/sources/edgar.py`, `src/corpus/sources/nsm.py`, `src/corpus/sources/pdip.py` — source adapters stay focused on download flows; resolvers live in a separate module.

---

## Task 1: Schema columns + ingest allowlist

**Files:**
- Modify: `sql/001_corpus.sql` (CREATE TABLE block lines 9-33, plus append ALTER after line 59)
- Modify: `src/corpus/db/ingest.py:25-47` (`_DOCUMENT_COLUMNS` frozenset)
- Test: `tests/test_ingest_provenance.py` (new)

- [ ] **Step 1: Write the failing test** for ingest allowlist

Create `tests/test_ingest_provenance.py`:

```python
"""Round-trip test: provenance URL fields land as top-level columns."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


@pytest.fixture
def tmp_db(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    """Create a fresh DuckDB with the corpus schema."""
    db_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    return conn


def test_provenance_fields_are_top_level_columns(
    tmp_db: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    """source_page_url and source_page_kind must be stored as columns,
    not merged into source_metadata JSON."""
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "edgar",
        "native_id": "0001193125-20-188103",
        "storage_key": "edgar__0001193125-20-188103",
        "title": "TEST FILING",
        "source_page_url": "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm",
        "source_page_kind": "filing_index",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(record) + "\n")

    ingest_manifests(tmp_db, manifest_dir)

    row = tmp_db.execute(
        "SELECT source_page_url, source_page_kind, source_metadata "
        "FROM documents WHERE storage_key = ?",
        ["edgar__0001193125-20-188103"],
    ).fetchone()
    assert row is not None
    assert row[0] == record["source_page_url"]
    assert row[1] == "filing_index"
    # Must NOT have been merged into source_metadata
    if row[2] is not None:
        meta = json.loads(row[2])
        assert "source_page_url" not in meta
        assert "source_page_kind" not in meta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest_provenance.py -v`

Expected: FAIL. Either the schema doesn't have `source_page_url`/`source_page_kind` columns (BinderException on `SELECT`) or the fields end up inside `source_metadata`.

- [ ] **Step 3: Add columns to `sql/001_corpus.sql`**

In the `CREATE TABLE IF NOT EXISTS documents (...)` block (lines 9-33), add two new columns immediately after `source_metadata VARCHAR` and before `created_at`:

```sql
    source_metadata VARCHAR,                     -- JSON blob for source-specific fields
    source_page_url VARCHAR,                     -- URL to human-facing filing page on source
    source_page_kind VARCHAR,                    -- filing_index | artifact_html | artifact_pdf | search_page | none
    created_at      TIMESTAMP DEFAULT current_timestamp,
```

Then, after the existing `ALTER TABLE grep_matches ADD COLUMN IF NOT EXISTS run_id VARCHAR;` at line 59, append two parallel ALTERs so existing DBs upgrade in place:

```sql
ALTER TABLE grep_matches ADD COLUMN IF NOT EXISTS run_id VARCHAR;

ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_page_url VARCHAR;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_page_kind VARCHAR;
```

- [ ] **Step 4: Extend `_DOCUMENT_COLUMNS` in ingest.py**

In `src/corpus/db/ingest.py` around line 25, extend the frozenset:

```python
_DOCUMENT_COLUMNS = frozenset(
    {
        "source",
        "native_id",
        "storage_key",
        "family_id",
        "doc_type",
        "title",
        "issuer_name",
        "lei",
        "publication_date",
        "submitted_date",
        "download_url",
        "file_path",
        "file_hash",
        "page_count",
        "parse_tool",
        "parse_version",
        "is_sovereign",
        "issuer_type",
        "scope_status",
        "source_page_url",
        "source_page_kind",
    }
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_ingest_provenance.py -v`

Expected: PASS.

- [ ] **Step 6: Run the full existing suite to confirm no regressions**

Run: `uv run pytest -v`

Expected: all 361+ tests pass. If any previously-passing test now fails, investigate before proceeding.

- [ ] **Step 7: Commit**

```bash
git add sql/001_corpus.sql src/corpus/db/ingest.py tests/test_ingest_provenance.py
git commit -m "feat: add source_page_url and source_page_kind columns (#52)

Schema change + ingest allowlist entry. Round-trip test confirms the
fields land as top-level columns rather than being merged into the
source_metadata JSON blob. Resolvers and backfill come in follow-up commits."
```

---

## Task 2: EDGAR resolver

**Files:**
- Create: `src/corpus/sources/provenance.py`
- Test: `tests/test_provenance.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_provenance.py`:

```python
"""Unit tests for per-source provenance URL resolvers."""

from __future__ import annotations

import pytest

from corpus.sources.provenance import (
    build_edgar_source_page,
    build_nsm_source_page,
    build_pdip_source_page,
    resolve_source_page,
)


# ── EDGAR ──────────────────────────────────────────────────────────────


def test_edgar_filing_index_url_strips_cik_zeros_and_dashes() -> None:
    """CIK loses leading zeros, accession dashes are stripped for dir path
    but kept for the filename segment."""
    record = {
        "source": "edgar",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    url, kind = build_edgar_source_page(record)
    assert (
        url
        == "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm"
    )
    assert kind == "filing_index"


def test_edgar_handles_source_metadata_as_json_string() -> None:
    """When source_metadata is a JSON string (post-ingest round trip),
    the resolver must still work."""
    record = {
        "source": "edgar",
        "source_metadata": '{"cik": "0000914021", "accession_number": "0001193125-20-188103"}',
    }
    url, kind = build_edgar_source_page(record)
    assert url is not None
    assert "914021" in url
    assert kind == "filing_index"


def test_edgar_missing_cik_returns_none() -> None:
    record = {"source": "edgar", "source_metadata": {"accession_number": "0001193125-20-188103"}}
    url, kind = build_edgar_source_page(record)
    assert url is None
    assert kind == "none"


def test_edgar_missing_accession_returns_none() -> None:
    record = {"source": "edgar", "source_metadata": {"cik": "0000914021"}}
    url, kind = build_edgar_source_page(record)
    assert url is None
    assert kind == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provenance.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'corpus.sources.provenance'`.

- [ ] **Step 3: Create `src/corpus/sources/provenance.py` with the EDGAR resolver**

```python
"""Per-source resolvers for provenance URL fields.

For each document record, these functions return ``(source_page_url, source_page_kind)``
where ``source_page_url`` links to the human-facing filing page on the original
source and ``source_page_kind`` is one of:

    filing_index | artifact_html | artifact_pdf | search_page | none

These are pure functions over the manifest-record dict. They're safe to call
during manifest backfill and during resolver unit tests.

See ``docs/superpowers/specs/2026-04-10-task2-manifest-research.md`` for the
per-source field layouts and URL formats.
"""

from __future__ import annotations

import json
from typing import Any

Resolution = tuple[str | None, str]

_EDGAR_INDEX_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/"
    "{accession_with_dashes}-index.htm"
)


def _coerce_source_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Return source_metadata as a dict regardless of whether it's stored
    as a nested dict or a JSON string in the record."""
    meta = record.get("source_metadata")
    if meta is None:
        return {}
    if isinstance(meta, str):
        try:
            parsed = json.loads(meta)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(meta, dict):
        return meta
    return {}


def build_edgar_source_page(record: dict[str, Any]) -> Resolution:
    """EDGAR: construct the filing-index URL from cik + accession_number.

    Example output:
        https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/0001193125-20-188103-index.htm
    """
    meta = _coerce_source_metadata(record)
    cik = meta.get("cik")
    accession = meta.get("accession_number")
    if not cik or not accession:
        return None, "none"
    try:
        cik_int = str(int(str(cik)))  # strip leading zeros
    except ValueError:
        return None, "none"
    accession_no_dashes = str(accession).replace("-", "")
    url = _EDGAR_INDEX_URL.format(
        cik_int=cik_int,
        accession_no_dashes=accession_no_dashes,
        accession_with_dashes=accession,
    )
    return url, "filing_index"
```

- [ ] **Step 4: Run EDGAR tests to verify they pass**

Run: `uv run pytest tests/test_provenance.py -v -k edgar`

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/corpus/sources/provenance.py tests/test_provenance.py
git commit -m "feat: EDGAR provenance URL resolver (#52)

Pure function that builds the SEC filing-index URL from cik and
accession_number. Handles both dict and JSON-string source_metadata,
leading zero stripping, and missing-field fallbacks."
```

---

## Task 3: NSM resolver

**Files:**
- Modify: `src/corpus/sources/provenance.py` (append `build_nsm_source_page`)
- Modify: `tests/test_provenance.py` (append NSM tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_provenance.py`:

```python
# ── NSM ────────────────────────────────────────────────────────────────


NSM_SEARCH_FALLBACK = "https://data.fca.org.uk/search/"


def test_nsm_html_artefact() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/d5c84201-05ec-4e43-b333-fc8dcbc6ab24.html",
    }
    url, kind = build_nsm_source_page(record)
    assert url == record["download_url"]
    assert kind == "artifact_html"


def test_nsm_htm_artefact_classified_as_html() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.htm",
    }
    url, kind = build_nsm_source_page(record)
    assert kind == "artifact_html"


def test_nsm_pdf_artefact() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/pdf/xyz.pdf",
    }
    url, kind = build_nsm_source_page(record)
    assert url == record["download_url"]
    assert kind == "artifact_pdf"


def test_nsm_case_insensitive_extension() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.HTML",
    }
    url, kind = build_nsm_source_page(record)
    assert kind == "artifact_html"


def test_nsm_missing_download_url_falls_back_to_search() -> None:
    record = {"source": "nsm", "native_id": "unknown"}
    url, kind = build_nsm_source_page(record)
    assert url == NSM_SEARCH_FALLBACK
    assert kind == "search_page"


def test_nsm_unknown_extension_falls_back_to_search() -> None:
    record = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc",
    }
    url, kind = build_nsm_source_page(record)
    assert url == NSM_SEARCH_FALLBACK
    assert kind == "search_page"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_provenance.py -v -k nsm`

Expected: FAIL with `ImportError` (the symbol isn't in provenance.py yet).

- [ ] **Step 3: Add NSM resolver + fallback constant**

Append to `src/corpus/sources/provenance.py`:

```python
NSM_SEARCH_FALLBACK = "https://data.fca.org.uk/search/"


def build_nsm_source_page(record: dict[str, Any]) -> Resolution:
    """NSM: the ``download_url`` IS the artefact URL on the FCA site.
    Classify by extension; fall back to the NSM search page if absent or
    unknown.

    The FCA site is a SPA for the search UI but artefact URLs themselves
    are direct file downloads, so they do resolve as deep links.
    """
    download_url = record.get("download_url")
    if not download_url:
        return NSM_SEARCH_FALLBACK, "search_page"
    lowered = str(download_url).lower()
    if lowered.endswith(".pdf"):
        return download_url, "artifact_pdf"
    if lowered.endswith(".html") or lowered.endswith(".htm"):
        return download_url, "artifact_html"
    return NSM_SEARCH_FALLBACK, "search_page"
```

Then update the top-of-file import line in `tests/test_provenance.py` is already importing `build_nsm_source_page` — nothing further needed there.

- [ ] **Step 4: Run NSM tests to verify they pass**

Run: `uv run pytest tests/test_provenance.py -v -k nsm`

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/corpus/sources/provenance.py tests/test_provenance.py
git commit -m "feat: NSM provenance URL resolver (#52)

NSM download_url is itself the artefact URL on the FCA site.
Classify by extension (.pdf → artifact_pdf, .html/.htm → artifact_html).
Fallback to NSM search page when extension is missing or unknown."
```

---

## Task 4: PDIP resolver + dispatcher

**Files:**
- Modify: `src/corpus/sources/provenance.py` (append `build_pdip_source_page` and `resolve_source_page`)
- Modify: `tests/test_provenance.py` (append PDIP + dispatcher tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_provenance.py`:

```python
# ── PDIP ───────────────────────────────────────────────────────────────


PDIP_SEARCH_PAGE = "https://publicdebtispublic.mdi.georgetown.edu/search/"


def test_pdip_always_returns_search_page() -> None:
    record = {"source": "pdip", "native_id": "VEN85"}
    url, kind = build_pdip_source_page(record)
    assert url == PDIP_SEARCH_PAGE
    assert kind == "search_page"


def test_pdip_ignores_native_id() -> None:
    """PDIP has no per-document deep links — same URL for every record."""
    record_a = build_pdip_source_page({"source": "pdip", "native_id": "VEN85"})
    record_b = build_pdip_source_page({"source": "pdip", "native_id": "GHA42"})
    assert record_a == record_b


# ── Dispatcher ─────────────────────────────────────────────────────────


def test_dispatcher_routes_by_source() -> None:
    edgar_rec = {
        "source": "edgar",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    nsm_rec = {
        "source": "nsm",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
    }
    pdip_rec = {"source": "pdip", "native_id": "VEN85"}

    assert resolve_source_page(edgar_rec)[1] == "filing_index"
    assert resolve_source_page(nsm_rec)[1] == "artifact_pdf"
    assert resolve_source_page(pdip_rec)[1] == "search_page"


def test_dispatcher_unknown_source_returns_none() -> None:
    record = {"source": "lse_rns", "native_id": "whatever"}
    url, kind = resolve_source_page(record)
    assert url is None
    assert kind == "none"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_provenance.py -v -k "pdip or dispatcher"`

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add PDIP resolver + dispatcher**

Append to `src/corpus/sources/provenance.py`:

```python
# PDIP has no per-document deep links. The only stable public entry point is
# the search interface. All PDIP documents share this source_page_url.
# Revisit if/when Georgetown publishes per-document permalinks.
PDIP_SEARCH_PAGE = "https://publicdebtispublic.mdi.georgetown.edu/search/"


def build_pdip_source_page(_record: dict[str, Any]) -> Resolution:
    """PDIP: no per-document deep links exist. Always return the search page."""
    return PDIP_SEARCH_PAGE, "search_page"


_RESOLVERS = {
    "edgar": build_edgar_source_page,
    "nsm": build_nsm_source_page,
    "pdip": build_pdip_source_page,
}


def resolve_source_page(record: dict[str, Any]) -> Resolution:
    """Dispatch to the per-source resolver. Returns ``(None, "none")`` for
    unknown sources so the backfill script can still write the record
    without crashing."""
    source = record.get("source")
    resolver = _RESOLVERS.get(str(source))
    if resolver is None:
        return None, "none"
    return resolver(record)
```

- [ ] **Step 4: Run PDIP + dispatcher tests to verify they pass**

Run: `uv run pytest tests/test_provenance.py -v`

Expected: all 14+ tests PASS.

- [ ] **Step 5: Run full suite to catch regressions**

Run: `uv run pytest -v`

Expected: all prior tests + the 14+ new ones pass.

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/provenance.py tests/test_provenance.py
git commit -m "feat: PDIP resolver + source dispatcher (#52)

PDIP has no per-document deep links, so every record maps to the static
search page. Dispatcher routes by record['source'] and returns (None, 'none')
for unknown sources so backfill cannot crash on future adapters."
```

---

## Task 5: PDIP manifest regeneration bridge script

**Files:**
- Create: `scripts/regenerate_pdip_manifest.py`
- Test: `tests/test_regenerate_pdip_manifest.py`

**Context:** This is the workaround for #66. The current 823 PDIP rows were ingested via a path that predates the manifest-canonical pipeline, so no `pdip_manifest.jsonl` exists. Without one, the rebuild step (Task 7) would lose PDIP data. This script captures the current PDIP state as a manifest so the rebuild preserves it and the backfill script (Task 6) can treat PDIP uniformly.

- [ ] **Step 1: Write the failing test**

Create `tests/test_regenerate_pdip_manifest.py`:

```python
"""Regression tests for the PDIP manifest regeneration bridge script.

Critical: these tests must round-trip the regenerated manifest through
``ingest_manifests`` into DuckDB. Writing a well-formed JSON record is not
enough — free-text dates like "January 20, 2017" in the inventory CSV will
pass JSON serialization but crash the rebuild with a ConversionException on
the DATE column.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb
import pytest

from corpus.db.ingest import ingest_manifests
from corpus.db.schema import create_schema


@pytest.fixture
def fake_corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build a miniature corpus layout:
       - tmp DB with three PDIP rows (impoverished, matches current state)
       - tmp inventory CSV with enrichment for two of them, using the three
         free-text date formats observed in production
       - tmp manifest dir
    Returns (db_path, inventory_csv_path, manifest_dir)."""
    db_path = tmp_path / "corpus.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    conn.execute(
        "INSERT INTO documents (source, native_id, storage_key, file_path) VALUES "
        "('pdip', 'VEN85', 'pdip__VEN85', 'data/pdfs/pdip/venezuela/VEN85.pdf'), "
        "('pdip', 'GHA33', 'pdip__GHA33', 'data/pdfs/pdip/ghana/GHA33.pdf'), "
        "('pdip', 'IDN199', 'pdip__IDN199', 'data/pdfs/pdip/indonesia/IDN199.pdf')"
    )
    conn.close()

    inventory = tmp_path / "pdip_document_inventory.csv"
    # utf-8-sig writer so the test file has a BOM, matching the script's
    # utf-8-sig reader choice (defends against Excel-exported CSVs).
    with inventory.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "document_title",
                "tag_status",
                "country",
                "instrument_type",
                "creditor_country",
                "creditor_type",
                "entity_type",
                "document_date",
                "maturity_date",
            ]
        )
        # Format 1: "Month Day, Year"
        writer.writerow(
            [
                "VEN85",
                "Loan Agreement for Sample Project",
                "Annotated",
                "Venezuela",
                "Loan",
                "",
                "",
                "",
                "January 20, 2017",
                "",
            ]
        )
        # Format 2: "Day Month Year"
        writer.writerow(
            [
                "GHA33",
                "Eurobond Prospectus",
                "Annotated",
                "Ghana",
                "Bond",
                "",
                "",
                "",
                "24 September 2025",
                "",
            ]
        )
        # Format 3: "Month Day[ordinal], Year" — ordinal suffix
        # Deliberately paired with an IDN row that IS in inventory to
        # prove we can parse it.
        writer.writerow(
            [
                "IDN199",
                "Bond with ordinal date",
                "Annotated",
                "Indonesia",
                "Bond",
                "",
                "",
                "",
                "July 6th, 2018",
                "",
            ]
        )

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    return db_path, inventory, manifest_dir


def test_regenerate_pdip_manifest_enriches_from_csv(
    fake_corpus: tuple[Path, Path, Path],
) -> None:
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(
        db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir
    )

    manifest_path = manifest_dir / "pdip_manifest.jsonl"
    assert manifest_path.exists()
    records = [json.loads(line) for line in manifest_path.read_text().splitlines() if line]
    assert len(records) == 3
    by_id = {r["native_id"]: r for r in records}

    # "January 20, 2017" → "2017-01-20"
    ven = by_id["VEN85"]
    assert ven["source"] == "pdip"
    assert ven["storage_key"] == "pdip__VEN85"
    assert ven["title"] == "Loan Agreement for Sample Project"
    assert ven["issuer_name"] == "Venezuela"
    assert ven["doc_type"] == "Loan"
    assert ven["publication_date"] == "2017-01-20"
    assert ven["download_url"] == "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85"
    assert ven["file_path"] == "data/pdfs/pdip/venezuela/VEN85.pdf"
    assert ven["source_metadata"]["tag_status"] == "Annotated"
    # Raw date preserved in source_metadata for audit trail
    assert ven["source_metadata"]["document_date_raw"] == "January 20, 2017"

    # "24 September 2025" → "2025-09-24"
    assert by_id["GHA33"]["publication_date"] == "2025-09-24"

    # "July 6th, 2018" → "2018-07-06" (ordinal suffix stripped)
    assert by_id["IDN199"]["publication_date"] == "2018-07-06"


def test_regenerate_pdip_manifest_round_trips_through_ingest(
    fake_corpus: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The regenerated manifest must survive a full ingest into a fresh
    DuckDB without raising ConversionException. This is the canary for the
    date-parsing bug caught in review."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(
        db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir
    )

    rebuild_db_path = tmp_path / "rebuild.duckdb"
    rebuild_conn = duckdb.connect(str(rebuild_db_path))
    try:
        create_schema(rebuild_conn)
        # Must NOT raise. Before the fix, this crashed with
        # ConversionException: invalid date field format: "January 20, 2017"
        stats = ingest_manifests(rebuild_conn, manifest_dir)
        assert stats["documents_inserted"] == 3
        assert stats["documents_skipped"] == 0

        rows = rebuild_conn.execute(
            "SELECT native_id, publication_date FROM documents "
            "WHERE source = 'pdip' ORDER BY native_id"
        ).fetchall()
    finally:
        rebuild_conn.close()

    by_id = {native_id: pub_date for native_id, pub_date in rows}
    # DuckDB stores these as date objects; just check they exist and parse
    import datetime as _dt
    assert by_id["VEN85"] == _dt.date(2017, 1, 20)
    assert by_id["GHA33"] == _dt.date(2025, 9, 24)
    assert by_id["IDN199"] == _dt.date(2018, 7, 6)


def test_regenerate_pdip_manifest_handles_row_missing_from_inventory(
    tmp_path: Path,
) -> None:
    """A PDIP row that exists in the DB but not in the inventory CSV must
    still land in the manifest with publication_date = None, not crash."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path = tmp_path / "corpus.duckdb"
    conn = duckdb.connect(str(db_path))
    create_schema(conn)
    conn.execute(
        "INSERT INTO documents (source, native_id, storage_key, file_path) VALUES "
        "('pdip', 'ORPHAN1', 'pdip__ORPHAN1', 'data/pdfs/pdip/xxx/ORPHAN1.pdf')"
    )
    conn.close()

    inventory = tmp_path / "pdip_document_inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "document_title", "document_date"])
        # No ORPHAN1 row at all.

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    regenerate_pdip_manifest(
        db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir
    )

    records = [
        json.loads(line)
        for line in (manifest_dir / "pdip_manifest.jsonl").read_text().splitlines()
        if line
    ]
    assert len(records) == 1
    assert records[0]["native_id"] == "ORPHAN1"
    assert records[0]["publication_date"] is None
    assert records[0]["title"] is None


def test_regenerate_pdip_manifest_is_atomic(
    fake_corpus: tuple[Path, Path, Path],
) -> None:
    """The script must write to .part and rename, never leaving a partial file."""
    from scripts.regenerate_pdip_manifest import regenerate_pdip_manifest

    db_path, inventory, manifest_dir = fake_corpus
    regenerate_pdip_manifest(
        db_path=db_path, inventory_csv=inventory, manifest_dir=manifest_dir
    )
    assert (manifest_dir / "pdip_manifest.jsonl").exists()
    assert not (manifest_dir / "pdip_manifest.jsonl.part").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_regenerate_pdip_manifest.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.regenerate_pdip_manifest'` or `ImportError`.

- [ ] **Step 3: Create the bridge script**

Create `scripts/regenerate_pdip_manifest.py`:

```python
"""Regenerate data/manifests/pdip_manifest.jsonl from the current DB + inventory CSV.

This is a one-off bridge for the tech debt tracked in #66 — PDIP data was
ingested via a path that predates the manifest-canonical pipeline, so no
JSONL manifest exists. Without one, a full DB rebuild from manifests would
lose all 823 PDIP documents.

Approach:
    1. Read the authoritative "what's actually downloaded" list from the
       current DB (data/db/corpus.duckdb, pdip rows).
    2. LEFT JOIN data/pdip/pdip_document_inventory.csv on native_id = id for
       richer metadata (title, country, instrument_type, dates).
    3. Normalize free-text inventory dates (e.g. "January 20, 2017",
       "24 September 2025", "July 6th, 2018") to ISO YYYY-MM-DD so they
       survive DuckDB's DATE column; preserve the raw string in
       source_metadata.document_date_raw for audit.
    4. Derive download_url deterministically from native_id.
    5. Write data/manifests/pdip_manifest.jsonl atomically (.part → rename).

Idempotent: running twice produces the same manifest. Safe to re-run.

Usage:
    uv run python scripts/regenerate_pdip_manifest.py
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

import duckdb

PDIP_PDF_URL = "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/{native_id}"

# Date formats observed in data/pdip/pdip_document_inventory.csv as of 2026-04-10:
#   "January 20, 2017"         → %B %d, %Y
#   "24 September 2025"        → %d %B %Y
#   "December 17, 2018"        → %B %d, %Y
# Ordinal suffixes ("6th", "1st") are stripped before parsing.
_DATE_FORMATS = ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y")
_ORDINAL_RE = re.compile(r"(\d+)(st|nd|rd|th)\b", re.IGNORECASE)


def _parse_free_text_date(raw: str | None) -> str | None:
    """Parse a free-text date from the inventory CSV to ISO YYYY-MM-DD.

    Returns ``None`` if the input is empty or cannot be parsed by any of
    the known formats. Never raises — unparseable dates become ``None``
    rather than crashing the rebuild.
    """
    if not raw:
        return None
    cleaned = _ORDINAL_RE.sub(r"\1", raw.strip())
    if not cleaned:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _load_inventory(inventory_csv: Path) -> dict[str, dict[str, str]]:
    """Read the inventory CSV keyed by id (= native_id).

    Uses ``utf-8-sig`` so Excel-exported CSVs with a UTF-8 BOM don't bleed
    the BOM into the first column name (which would make ``row.get("id")``
    always return ``None``).
    """
    if not inventory_csv.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with inventory_csv.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row.get("id")
            if doc_id:
                rows[doc_id] = row
    return rows


def _build_record(
    db_row: dict[str, Any], inv_row: dict[str, str] | None
) -> dict[str, Any]:
    """Build a single manifest record from DB + optional inventory enrichment."""
    native_id = db_row["native_id"]
    inv = inv_row or {}
    raw_date = inv.get("document_date", "") or ""
    iso_date = _parse_free_text_date(raw_date)
    return {
        "source": "pdip",
        "native_id": native_id,
        "storage_key": db_row["storage_key"],
        "title": (inv.get("document_title") or "").strip() or None,
        "issuer_name": (inv.get("country") or "").strip() or None,
        "doc_type": (inv.get("instrument_type") or "").strip() or None,
        "publication_date": iso_date,
        "download_url": PDIP_PDF_URL.format(native_id=native_id),
        "file_path": db_row.get("file_path"),
        "file_hash": db_row.get("file_hash"),
        "is_sovereign": db_row.get("is_sovereign", True),
        "issuer_type": db_row.get("issuer_type", "sovereign"),
        "scope_status": db_row.get("scope_status", "in_scope"),
        "source_metadata": {
            "tag_status": inv.get("tag_status", ""),
            "country": inv.get("country", ""),
            "instrument_type": inv.get("instrument_type", ""),
            "creditor_country": inv.get("creditor_country", ""),
            "creditor_type": inv.get("creditor_type", ""),
            "entity_type": inv.get("entity_type", ""),
            "maturity_date": inv.get("maturity_date", ""),
            "document_date_raw": raw_date,  # Audit trail for the parser
        },
    }


def regenerate_pdip_manifest(
    *,
    db_path: Path,
    inventory_csv: Path,
    manifest_dir: Path,
) -> int:
    """Regenerate pdip_manifest.jsonl. Returns number of records written."""
    manifest_dir.mkdir(parents=True, exist_ok=True)
    target = manifest_dir / "pdip_manifest.jsonl"
    part = manifest_dir / "pdip_manifest.jsonl.part"

    inventory = _load_inventory(inventory_csv)

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            "SELECT native_id, storage_key, file_path, file_hash, "
            "is_sovereign, issuer_type, scope_status "
            "FROM documents WHERE source = 'pdip' ORDER BY native_id"
        ).fetchall()
        columns = [d[0] for d in conn.description or []]
    finally:
        conn.close()

    with part.open("w") as f:
        for row in rows:
            db_row = dict(zip(columns, row, strict=True))
            inv_row = inventory.get(db_row["native_id"])
            record = _build_record(db_row, inv_row)
            f.write(json.dumps(record) + "\n")

    os.replace(part, target)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/db/corpus.duckdb"),
        help="Path to corpus.duckdb",
    )
    parser.add_argument(
        "--inventory-csv",
        type=Path,
        default=Path("data/pdip/pdip_document_inventory.csv"),
        help="Path to PDIP inventory CSV",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifests"),
        help="Directory for manifest JSONL files",
    )
    args = parser.parse_args()
    count = regenerate_pdip_manifest(
        db_path=args.db_path,
        inventory_csv=args.inventory_csv,
        manifest_dir=args.manifest_dir,
    )
    print(f"Wrote {count} PDIP records to {args.manifest_dir / 'pdip_manifest.jsonl'}")


if __name__ == "__main__":
    main()
```

Also, ensure `scripts/` is importable as a module for the test. Create `scripts/__init__.py` unconditionally (creating it when it already exists is a no-op, and it's cheaper than branching):

```python
# Makes scripts/ importable for tests.
```

Write this with:

```bash
touch scripts/__init__.py  # safe even if the file already exists
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_regenerate_pdip_manifest.py -v`

Expected: 5 PASS. Specifically, `test_regenerate_pdip_manifest_round_trips_through_ingest` must pass — that's the canary for the date-parsing bug. If it raises `ConversionException`, the parser isn't handling some format in the fixture.

- [ ] **Step 5: Commit**

```bash
git add scripts/regenerate_pdip_manifest.py scripts/__init__.py tests/test_regenerate_pdip_manifest.py
git commit -m "feat: PDIP manifest regeneration bridge script (#52, #66)

One-off workaround for PDIP tech debt (#66). Reads current DB rows,
left-joins the inventory CSV for enrichment, normalizes free-text dates
to ISO, derives download_url, writes data/manifests/pdip_manifest.jsonl
atomically. Unblocks Task 2's full rebuild without losing the 823 PDIP
documents. Raw dates preserved in source_metadata.document_date_raw.

The test suite includes a round-trip assertion through ingest_manifests
because the previous draft crashed the rebuild on free-text dates like
'January 20, 2017' that pass JSON serialization but not DuckDB's DATE
column parser."
```

---

## Task 6: Backfill script for all three manifests

**Files:**
- Create: `scripts/backfill_provenance_urls.py`
- Test: `tests/test_backfill_provenance_urls.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_backfill_provenance_urls.py`:

```python
"""Regression test for the provenance URL backfill script."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_manifests(tmp_path: Path) -> Path:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    edgar = {
        "source": "edgar",
        "native_id": "0001193125-20-188103",
        "storage_key": "edgar__0001193125-20-188103",
        "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/d935251d424b5.htm",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    nsm = {
        "source": "nsm",
        "native_id": "abc",
        "storage_key": "nsm__abc",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
    }
    pdip = {
        "source": "pdip",
        "native_id": "VEN85",
        "storage_key": "pdip__VEN85",
        "download_url": "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(edgar) + "\n")
    (manifest_dir / "nsm_manifest.jsonl").write_text(json.dumps(nsm) + "\n")
    (manifest_dir / "pdip_manifest.jsonl").write_text(json.dumps(pdip) + "\n")
    return manifest_dir


def test_backfill_adds_both_fields(sample_manifests: Path) -> None:
    from scripts.backfill_provenance_urls import backfill_manifests

    stats = backfill_manifests(manifest_dir=sample_manifests)
    assert stats["files_rewritten"] == 3
    assert stats["records_updated"] == 3

    edgar_rec = json.loads((sample_manifests / "edgar_manifest.jsonl").read_text())
    assert edgar_rec["source_page_kind"] == "filing_index"
    assert "914021" in edgar_rec["source_page_url"]

    nsm_rec = json.loads((sample_manifests / "nsm_manifest.jsonl").read_text())
    assert nsm_rec["source_page_kind"] == "artifact_pdf"
    assert nsm_rec["source_page_url"] == nsm_rec["download_url"]

    pdip_rec = json.loads((sample_manifests / "pdip_manifest.jsonl").read_text())
    assert pdip_rec["source_page_kind"] == "search_page"
    assert pdip_rec["source_page_url"].startswith("https://publicdebtispublic.mdi.georgetown.edu")


def test_backfill_is_idempotent(sample_manifests: Path) -> None:
    """Running backfill twice must produce identical output."""
    from scripts.backfill_provenance_urls import backfill_manifests

    backfill_manifests(manifest_dir=sample_manifests)
    first = (sample_manifests / "edgar_manifest.jsonl").read_text()
    backfill_manifests(manifest_dir=sample_manifests)
    second = (sample_manifests / "edgar_manifest.jsonl").read_text()
    assert first == second


def test_backfill_writes_atomically(sample_manifests: Path) -> None:
    """No .part files should remain after a successful run."""
    from scripts.backfill_provenance_urls import backfill_manifests

    backfill_manifests(manifest_dir=sample_manifests)
    assert list(sample_manifests.glob("*.part")) == []


def test_backfill_skips_records_that_already_have_fields(sample_manifests: Path) -> None:
    """If a record already has source_page_url set, it is preserved as-is."""
    from scripts.backfill_provenance_urls import backfill_manifests

    rec = {
        "source": "nsm",
        "native_id": "preset",
        "storage_key": "nsm__preset",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/preset.pdf",
        "source_page_url": "https://example.com/manually-set",
        "source_page_kind": "filing_index",
    }
    (sample_manifests / "nsm_manifest.jsonl").write_text(json.dumps(rec) + "\n")

    backfill_manifests(manifest_dir=sample_manifests)

    result = json.loads((sample_manifests / "nsm_manifest.jsonl").read_text())
    assert result["source_page_url"] == "https://example.com/manually-set"
    assert result["source_page_kind"] == "filing_index"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backfill_provenance_urls.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create the backfill script**

Create `scripts/backfill_provenance_urls.py`:

```python
"""Backfill source_page_url and source_page_kind into existing JSONL manifests.

For each ``data/manifests/*_manifest.jsonl`` file, read every record, call
``resolve_source_page`` from ``corpus.sources.provenance``, and write the
record back with the two new fields. Atomic ``.part`` → rename per file.
Idempotent — records that already have both fields set are preserved as-is.

Usage:
    uv run python scripts/backfill_provenance_urls.py
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from corpus.sources.provenance import resolve_source_page


def _backfill_one(path: Path) -> tuple[int, int]:
    """Rewrite a single manifest file with provenance URL fields added.

    Returns ``(records_total, records_updated)``.
    """
    part = path.with_suffix(path.suffix + ".part")
    total = 0
    updated = 0
    with path.open() as src, part.open("w") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            total += 1
            record: dict[str, Any] = json.loads(line)
            if record.get("source_page_url") and record.get("source_page_kind"):
                # Already has both fields — preserve as-is.
                dst.write(json.dumps(record) + "\n")
                continue
            url, kind = resolve_source_page(record)
            record["source_page_url"] = url
            record["source_page_kind"] = kind
            dst.write(json.dumps(record) + "\n")
            updated += 1
    os.replace(part, path)
    return total, updated


def backfill_manifests(*, manifest_dir: Path) -> dict[str, int]:
    """Backfill all ``*_manifest.jsonl`` files in the given directory."""
    files = sorted(manifest_dir.glob("*_manifest.jsonl"))
    totals = {"files_rewritten": 0, "records_total": 0, "records_updated": 0}
    for path in files:
        total, updated = _backfill_one(path)
        totals["files_rewritten"] += 1
        totals["records_total"] += total
        totals["records_updated"] += updated
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("data/manifests"),
        help="Directory containing *_manifest.jsonl files",
    )
    args = parser.parse_args()
    stats = backfill_manifests(manifest_dir=args.manifest_dir)
    print(
        f"Rewrote {stats['files_rewritten']} manifest file(s): "
        f"{stats['records_updated']} / {stats['records_total']} records updated."
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_backfill_provenance_urls.py -v`

Expected: 4 PASS.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest -v`

Expected: all previously-passing tests + new ones pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_provenance_urls.py tests/test_backfill_provenance_urls.py
git commit -m "feat: backfill script for provenance URL fields (#52)

Reads each data/manifests/*_manifest.jsonl, calls the source dispatcher,
writes back atomically via .part → rename. Idempotent: records that
already have both fields are preserved unchanged.

Caveat: if a resolver bug is discovered later, a simple re-run of this
script will NOT overwrite the buggy values — it skips records that
already have both fields set. The intended recovery path is either (a)
re-run the PDIP bridge / discover-download flow to regenerate the raw
manifests, or (b) add a --force flag to this script when needed. We're
not adding --force now because YAGNI."
```

---

## Task 7: Run the bridge + backfill + rebuild the DB

This is execution of the scripts built above, not new code. Each step is a command with expected output.

**Blast radius of the rebuild** (verified 2026-04-10, must stay accurate across re-runs):

| Table | Pre-rebuild rows | What happens on swap | Why |
| --- | --- | --- | --- |
| `documents` | 4769 | Recreated from manifests | This is the entire point of Task 2. |
| `document_countries` | 0 | Recreated (empty in and out) | Nothing to preserve. |
| `pdip_clauses` | 6,251 | **Must be preserved** via ATTACH + INSERT from `.bak` | Uses `storage_key`, not `document_id` FK — safe to copy verbatim. Not regenerated by Task 3. Real annotation data. |
| `grep_matches` | 106,229 | **Must be preserved** via ATTACH + INSERT from `.bak`, remapping `document_id` through `storage_key` | Phase 1 extraction data, not regenerated by Task 3. `document_id` FK is not stable across rebuild because the new PDIP manifest shifts the sequence. |
| `pipeline_runs` | N/A | Dropped | History-only; Task 2 adds its own `task2-rebuild-*` run. |
| `source_events` | N/A | Dropped | History-only. |

If any of these row counts have changed by the time the plan is executed, rerun the "Snapshot pre-rebuild row counts" step and update the expected values before proceeding — don't let drift mask data loss.

- [ ] **Step 1: Confirm current manifest state**

Run: `ls -la data/manifests/`

Expected: `edgar_manifest.jsonl` and `nsm_manifest.jsonl` exist; no `pdip_manifest.jsonl`; no `.part` files.

Run: `wc -l data/manifests/*_manifest.jsonl`

Expected: ~3301 edgar, ~645 nsm.

- [ ] **Step 2: Snapshot pre-rebuild row counts for every table we care about**

Run:

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb', read_only=True)
print('documents by source:', c.execute('SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY source').fetchall())
print('document_countries:', c.execute('SELECT COUNT(*) FROM document_countries').fetchone())
print('pdip_clauses:', c.execute('SELECT COUNT(*) FROM pdip_clauses').fetchone())
print('grep_matches:', c.execute('SELECT COUNT(*) FROM grep_matches').fetchone())
"
```

Expected baseline from 2026-04-10 (update the plan's blast-radius table if these have drifted):
- `documents`: `[('edgar', 3301), ('nsm', 645), ('pdip', 823)]`
- `document_countries`: `(0,)`
- `pdip_clauses`: `(6251,)`
- `grep_matches`: `(106229,)`

Write these numbers down — Step 9 verifies parity after the preservation step.

- [ ] **Step 3: Regenerate pdip_manifest.jsonl**

Run: `uv run python scripts/regenerate_pdip_manifest.py`

Expected output: `Wrote 823 PDIP records to data/manifests/pdip_manifest.jsonl`.

Run: `wc -l data/manifests/pdip_manifest.jsonl`

Expected: 823.

- [ ] **Step 4: Spot-check the regenerated PDIP manifest**

Run: `head -1 data/manifests/pdip_manifest.jsonl | uv run python -m json.tool`

Expected: a valid JSON object with `source: "pdip"`, a `native_id`, a `storage_key`, and a `download_url` starting with `https://publicdebtispublic.mdi.georgetown.edu/api/pdf/`. Title and issuer may be present (if the row existed in the inventory CSV) or null.

- [ ] **Step 5: Run the backfill script against all manifests**

Run: `uv run python scripts/backfill_provenance_urls.py`

Expected output: `Rewrote 3 manifest file(s): 4769 / 4769 records updated.` (counts may differ slightly if discovery/download is run between sessions — the important thing is files_rewritten == 3 and records_updated is nonzero.)

Run: `ls data/manifests/*.part 2>/dev/null || echo "no .part files"`

Expected: `no .part files`.

- [ ] **Step 6: Spot-check one record per source for the new fields**

Run:

```bash
for src in edgar nsm pdip; do
    echo "── $src ──"
    head -1 "data/manifests/${src}_manifest.jsonl" | uv run python -c "
import json, sys
r = json.loads(sys.stdin.read())
print('source_page_url:', r.get('source_page_url'))
print('source_page_kind:', r.get('source_page_kind'))
"
done
```

Expected:
- EDGAR: a `https://www.sec.gov/Archives/edgar/data/.../...-index.htm` URL and kind `filing_index`.
- NSM: the `data.fca.org.uk/artefacts/...` URL and kind `artifact_html` or `artifact_pdf`.
- PDIP: `https://publicdebtispublic.mdi.georgetown.edu/search/` and kind `search_page`.

- [ ] **Step 7: Rebuild the DB into a fresh file**

The ingest path is "insert if storage_key doesn't exist already" — re-running against the existing DB would skip all rows and leave the new columns null. Rebuild into a fresh DB file, verify, then atomic-swap.

Run:

```bash
rm -f data/db/corpus.duckdb.new
uv run corpus ingest --manifest-dir data/manifests --db-path data/db/corpus.duckdb.new --run-id "task2-rebuild-$(date +%Y%m%d-%H%M%S)"
```

Expected final line: `Ingest complete: 4769 inserted, 0 skipped.` (give or take, same order of magnitude as pre-rebuild counts).

- [ ] **Step 8: Verify the new DB has the expected rows per source and kind**

Run:

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb.new', read_only=True)
print('by source:')
for row in c.execute('SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY source').fetchall():
    print(' ', row)
print()
print('by source + kind:')
for row in c.execute('SELECT source, source_page_kind, COUNT(*) FROM documents GROUP BY 1,2 ORDER BY 1,2').fetchall():
    print(' ', row)
print()
print('null provenance url count:')
print(' ', c.execute(\"SELECT COUNT(*) FROM documents WHERE source_page_url IS NULL\").fetchone())
"
```

Expected:
- `edgar`: 3301 with `filing_index`
- `nsm`: 645 split across `artifact_pdf`, `artifact_html`, and possibly a small `search_page` tail
- `pdip`: 823 with `search_page`
- Null URL count should only include EDGAR rows missing cik/accession (likely 0) — anything else needs investigation before proceeding.

- [ ] **Step 9: Preserve `pdip_clauses` and `grep_matches` from the backup**

Before the swap, stage the current live DB as the backup-to-read-from, then ATTACH it into the new DB and copy the two non-manifest tables we care about. `pdip_clauses` is safe to copy verbatim because it joins on `storage_key`. `grep_matches.document_id` is an FK that won't match the fresh sequence, so remap via `storage_key`.

Run:

```bash
cp data/db/corpus.duckdb data/db/corpus.duckdb.bak
```

Then run the preservation script as a heredoc (one DuckDB session so the ATTACH + INSERTs run together):

```bash
uv run python <<'PY'
import duckdb

conn = duckdb.connect("data/db/corpus.duckdb.new")
try:
    conn.execute("ATTACH 'data/db/corpus.duckdb.bak' AS bak (READ_ONLY)")

    # pdip_clauses: safe to copy — uses storage_key, not document_id FK.
    # Omit pdip_clause_id so the new sequence assigns fresh values.
    conn.execute("""
        INSERT INTO pdip_clauses (
            doc_id, storage_key, clause_id, label, label_family,
            page_index, text, text_status, bbox, original_dims,
            country, instrument_type, governing_law, currency,
            document_title, created_at
        )
        SELECT
            doc_id, storage_key, clause_id, label, label_family,
            page_index, text, text_status, bbox, original_dims,
            country, instrument_type, governing_law, currency,
            document_title, created_at
        FROM bak.pdip_clauses
    """)
    pdip_copied = conn.execute("SELECT COUNT(*) FROM pdip_clauses").fetchone()[0]
    print(f"pdip_clauses: copied {pdip_copied} rows")

    # grep_matches: remap document_id via storage_key join between old and new documents.
    # Any row whose source document no longer exists is silently dropped —
    # shouldn't happen for Task 2 since the manifest set is a strict superset.
    conn.execute("""
        INSERT INTO grep_matches (
            document_id, pattern_name, pattern_version, page_number,
            matched_text, context_before, context_after, created_at, run_id
        )
        SELECT
            new_d.document_id, bm.pattern_name, bm.pattern_version, bm.page_number,
            bm.matched_text, bm.context_before, bm.context_after, bm.created_at, bm.run_id
        FROM bak.grep_matches bm
        JOIN bak.documents old_d ON bm.document_id = old_d.document_id
        JOIN documents new_d ON old_d.storage_key = new_d.storage_key
    """)
    grep_copied = conn.execute("SELECT COUNT(*) FROM grep_matches").fetchone()[0]
    grep_orig = conn.execute("SELECT COUNT(*) FROM bak.grep_matches").fetchone()[0]
    print(f"grep_matches: copied {grep_copied} of {grep_orig} rows")
    if grep_copied != grep_orig:
        dropped = grep_orig - grep_copied
        print(f"WARNING: dropped {dropped} grep_matches rows with unresolvable storage_key")

    conn.execute("DETACH bak")
finally:
    conn.close()
PY
```

Expected:
- `pdip_clauses: copied 6251 rows`
- `grep_matches: copied 106229 of 106229 rows` (no warning line)

If the grep_matches copied count is less than the original, investigate before swapping. The most likely cause is a storage_key mismatch between old and new manifests — dig into the first few dropped rows and decide whether it's real data loss or stale references.

- [ ] **Step 10: Swap the new DB into place**

Run:

```bash
mv data/db/corpus.duckdb data/db/corpus.duckdb.prev
mv data/db/corpus.duckdb.new data/db/corpus.duckdb
```

Note: `data/db/corpus.duckdb.bak` already exists from Step 9 as the read-only snapshot used for preservation. `data/db/corpus.duckdb.prev` is the live path renamed out of the way so the atomic swap is reversible.

Run a full sanity check:

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb', read_only=True)
print('documents by source:', c.execute('SELECT source, COUNT(*) FROM documents GROUP BY source ORDER BY source').fetchall())
print('pdip_clauses:', c.execute('SELECT COUNT(*) FROM pdip_clauses').fetchone())
print('grep_matches:', c.execute('SELECT COUNT(*) FROM grep_matches').fetchone())
print('documents with non-null source_page_url:', c.execute('SELECT COUNT(*) FROM documents WHERE source_page_url IS NOT NULL').fetchone())
"
```

Expected: `documents` counts match Step 2, `pdip_clauses = 6251`, `grep_matches = 106229`, `source_page_url` non-null count ≈ 4769 (all rows populated except any EDGAR rows with malformed source_metadata — should be 0).

**Note:** `data/db/corpus.duckdb.bak` and `corpus.duckdb.prev` are kept locally as rollback safety nets. Neither is committed (DB files are gitignored). Delete both after the PR is merged if disk space is tight.

**Note on manifests:** the backfilled manifest files are NOT committed to git. `data/**` is gitignored (`.gitignore:6`), and the current EDGAR/NSM manifests already exceed the 500KB large-file pre-commit hook (`.pre-commit-config.yaml`). Manifests are intermediate artifacts — the source of truth is `scripts/backfill_provenance_urls.py` + `scripts/regenerate_pdip_manifest.py`, which anyone can re-run from a clean checkout. If you need to share the regenerated manifests, push them to MotherDuck via Task 3's publish step (not this PR).

---

## Task 8: Manual URL verification (3 per source)

**Files:** none (verification only; capture results for the PR description).

**SEC User-Agent note:** SEC's fair-access policy rejects `HEAD` requests and generic User-Agents with a 403. Use a `GET` request with a descriptive User-Agent that includes a contact email. See https://www.sec.gov/os/webmaster-faq#developers. The plan's reviewer reproduced the 403 on `curl -I -A "corpus-task2-verify/1.0"` and confirmed the same URL returns 200 via `GET` with a proper UA.

Set this once per shell before running Step 1:

```bash
export SEC_UA="Teal Insights sovereign-corpus verify (teal@tealinsights.com)"
```

(Substitute your own contact email; any real address works.)

- [ ] **Step 1: Pick 3 random EDGAR rows and GET the source_page_url**

Run:

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb', read_only=True)
rows = c.execute(
    'SELECT storage_key, source_page_url FROM documents '
    \"WHERE source='edgar' AND source_page_url IS NOT NULL \"
    'USING SAMPLE 3 ROWS'
).fetchall()
for sk, url in rows:
    print(sk, url)
"
```

Save the 3 URLs. For each, run:

```bash
curl -sSL -o /dev/null -w "%{http_code} %{url_effective}\n" -A "$SEC_UA" "URL_HERE"
```

Notes:
- `GET`, not `HEAD` (`-I` flag omitted) — SEC rejects HEAD.
- `-A "$SEC_UA"` must be a SEC-compliant UA with a contact email; a generic UA like `corpus-task2-verify/1.0` returns 403.
- `-L` follows redirects; the final URL should remain under `www.sec.gov/Archives/edgar/...`.

Expected: each returns `200`.

Record the `storage_key`, URL, and HTTP status for the PR description.

- [ ] **Step 2: Pick 3 random NSM artifact rows (not search-page fallbacks) and curl each**

Filter the sample to `artifact_html` or `artifact_pdf` so all three rows test an actual deep link, not the search-page fallback URL (which would only verify one unique URL no matter how many rows you sample):

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb', read_only=True)
rows = c.execute(
    'SELECT storage_key, source_page_url, source_page_kind FROM documents '
    \"WHERE source='nsm' AND source_page_kind IN ('artifact_html', 'artifact_pdf') \"
    'USING SAMPLE 3 ROWS'
).fetchall()
for row in rows:
    print(row)
"
```

For each URL:

```bash
curl -sSL -o /dev/null -w "%{http_code} %{url_effective}\n" -A "corpus-task2-verify/1.0 (teal@tealinsights.com)" "URL_HERE"
```

Expected: `200` for each. Redirects are acceptable as long as the final URL stays under `data.fca.org.uk`.

Record results.

- [ ] **Step 3: Verify the PDIP search page**

Run:

```bash
curl -sSL -o /dev/null -w "%{http_code}\n" -A "corpus-task2-verify/1.0 (teal@tealinsights.com)" "https://publicdebtispublic.mdi.georgetown.edu/search/"
```

Expected: `200`.

Record the result. Since every PDIP row maps to the same constant URL, the "3 URLs" criterion is satisfied by verifying the one URL plus spot-checking the DB that all 823 rows have the same `source_page_url` and `source_page_kind = 'search_page'`:

```bash
uv run python -c "
import duckdb
c = duckdb.connect('data/db/corpus.duckdb', read_only=True)
print(c.execute(\"SELECT source_page_url, source_page_kind, COUNT(*) FROM documents WHERE source='pdip' GROUP BY 1,2\").fetchall())
"
```

Expected: one row, `[('https://publicdebtispublic.mdi.georgetown.edu/search/', 'search_page', 823)]`. Record 3 PDIP `native_id` values (e.g. from `LIMIT 3`) in the PR description to document which dispatcher wirings were implicitly exercised.

- [ ] **Step 4: Paste the verification results into a local scratch file**

Create `/tmp/task2-url-verification.md` and paste the 9 results (3 per source) so you can lift them verbatim into the PR description in Task 9. Do not commit this file.

---

## Task 9: Phase 4 verification + Phase 5 ship

**Files:** no new code; this is the CLAUDE.md verification-and-ship workflow.

- [ ] **Step 1: Lint**

Run: `uv run ruff check src/ tests/ scripts/`

Expected: no errors. Fix anything that comes up.

- [ ] **Step 2: Format check**

Run: `uv run ruff format --check src/ tests/ scripts/`

Expected: all files already formatted. If not, run `uv run ruff format src/ tests/ scripts/` and commit the formatting diff separately.

- [ ] **Step 3: Type check**

Run: `uv run pyright src/corpus/`

Expected: 0 errors. Fix any typing errors in `provenance.py` or `ingest.py`.

- [ ] **Step 4: Full test suite**

Run: `uv run pytest -v`

Expected: 361 prior tests + 20+ new tests all pass (exact count depends on how you split the provenance tests).

- [ ] **Step 5: Pre-commit run (this catches hook-only checks that the individual tool commands above miss)**

Run: `uv run pre-commit run --all-files`

Expected: all hooks pass — ruff, ruff-format, pyright, pytest, check-yaml, check-toml, check-json, `check-added-large-files --maxkb=500`, `no-commit-to-branch`.

If `check-added-large-files` fails on `data/manifests/*.jsonl`, those shouldn't be staged in the first place — the plan's rebuild step explicitly does not commit manifests (see Task 7 Step 10 note). Verify with `git status`; if manifests are somehow staged, `git reset data/manifests/`.

If `no-commit-to-branch` fails, check you're on `feature/provenance-urls` and not `main`: `git branch --show-current`.

- [ ] **Step 6: Run the superpowers:verification-before-completion skill**

Use the Skill tool: `superpowers:verification-before-completion`. Walk through its checklist against your actual command output — do not assume.

- [ ] **Step 7: Push the branch and open a PR**

Run:

```bash
git push -u origin feature/provenance-urls
```

Then use `gh pr create` with a HEREDOC body. The body should include:

- Summary: what was added and why
- Link to issue #52 and the workaround link to #66
- Row counts: pre- vs post-rebuild by source and by kind
- The 9 URL verification results from `/tmp/task2-url-verification.md`
- Test plan checklist

Example:

```bash
gh pr create --title "feat: provenance URLs and schema (#52)" --body "$(cat <<'EOF'
## Summary

- Adds \`source_page_url\` and \`source_page_kind\` columns to the \`documents\` table
- Pure resolver functions per source in \`src/corpus/sources/provenance.py\`
- Bridge script to regenerate \`pdip_manifest.jsonl\` from current DB + inventory CSV (workaround for #66)
- Backfill script that rewrites all three \`data/manifests/*_manifest.jsonl\` files atomically
- Local DB rebuilt from updated manifests; row counts match pre-rebuild state

Closes #52. Workaround for #66 (PDIP ingest tech debt) — does not close it.

## Row counts

Pre-rebuild → post-rebuild (by source):
- edgar: 3301 → 3301
- nsm: 645 → 645
- pdip: 823 → 823

Post-rebuild (by source_page_kind): <paste from Step 8 of Task 7>

## URL verification

<paste the 9 verification results from /tmp/task2-url-verification.md>

## Test plan

- [x] ruff check passes
- [x] pyright passes
- [x] pytest passes (including 20+ new tests)
- [x] 3 EDGAR URLs resolve (200)
- [x] 3 NSM URLs resolve (200)
- [x] PDIP search page resolves (200)
- [x] Full DB rebuild preserves row counts

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Capture the PR URL from the output.

- [ ] **Step 8: Request external reviews**

Run:

```bash
gh pr comment <PR_NUMBER> --body "@codex review"
gh pr comment <PR_NUMBER> --body "@claude review"
```

- [ ] **Step 9: Wait for reviews**

Wait ~3 minutes. Then read the comments:

```bash
gh api repos/Teal-Insights/sovereign-prospectus-corpus/pulls/<PR_NUMBER>/comments
```

- [ ] **Step 10: Evaluate feedback with superpowers:receiving-code-review**

Use the Skill tool: `superpowers:receiving-code-review`. For each comment:
- If it's a reasonable fix, make the fix, commit, push.
- If it's out of scope or wrong, reply explaining why.
- If it's reasonable but out of scope, `gh issue create` with the comment quoted and the issue labeled appropriately. Reply on the PR with the new issue number.

- [ ] **Step 11: Update SESSION-HANDOFF.md**

Edit `SESSION-HANDOFF.md`:
- Mark Task 2 as `[x]` in the Sprint Tasks list.
- Replace the "Task 2 — what's ready" section with a "Task 2 recap (what shipped)" section listing: the two new columns, the three manifest files, the bridge script, and the #66 workaround.
- Update the status line at the top to `Task 2 merged. Next up: Task 3 (Search Index + Parsed Text Loading).`

Commit:

```bash
git add SESSION-HANDOFF.md
git commit -m "chore: session handoff for Task 2 completion"
git push
```

- [ ] **Step 12: Merge when reviews are green**

Merge via `gh pr merge <PR_NUMBER> --squash --delete-branch`. Confirm `main` is clean and the V1 Quarto book site is still serving.

---

## Out of scope (for this plan)

- **MotherDuck publish.** Task 3's `make publish-motherduck` handles pushing the updated schema + data to the cloud DB that the live explorer uses. The explorer will keep running on the current 4,769-row MotherDuck table without the new columns until Task 3.
- **Streamlit explorer UI changes.** "View on Source" links come in Task 4.
- **FTS index / `document_pages` table.** Task 3.
- **PDIP file path migration** (`data/pdfs/pdip/{country}/` → `data/original/pdip__{id}.pdf`). Tracked in #66, out of sprint scope.
- **Committing manifest JSONL files.** `data/**` is gitignored and the manifests exceed the 500KB large-file pre-commit hook. Manifests are intermediate artifacts regenerable from `scripts/regenerate_pdip_manifest.py` + `scripts/backfill_provenance_urls.py`, which are committed. If anyone needs the actual manifest bytes, they re-run the scripts.

## Deliberately in scope (addresses reviewer findings)

The rebuild step preserves both `pdip_clauses` (6,251 rows, real annotation data) and `grep_matches` (106,229 rows, Phase 1 extraction data) via ATTACH + INSERT from the backup — see Task 7 Step 9. An earlier draft of this plan assumed `grep_matches` would be regenerated by Task 3 and could be left dirty; that assumption was wrong. `pdip_clauses` uses `storage_key` and is copied verbatim; `grep_matches.document_id` is remapped through `storage_key` because the rebuild's fresh `documents_seq` would otherwise silently misalign FKs.
