# NSM Source Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an NSM source adapter that downloads all sovereign bond documents from the FCA National Storage Mechanism, fixes Phase 1 bugs (multi-LEI AND→OR, Canada name pollution), and produces `nsm_manifest.jsonl` for downstream ingest.

**Architecture:** The adapter queries the NSM Elasticsearch API with no country/type filters (breadth-first), paginates through all results, resolves two-hop HTML→PDF links, downloads PDFs via `safe_write()`, and writes one JSONL manifest line per document. A circuit breaker aborts on too many consecutive failures. The CLI `corpus download nsm` command wires everything together.

**Tech Stack:** Python 3.12, Click CLI, requests (via `CorpusHTTPClient`), `safe_write()`, `CorpusLogger`, BeautifulSoup4 (for HTML→PDF link extraction)

---

## File Structure

```
src/corpus/
├── sources/
│   ├── __init__.py          # Empty package init
│   └── nsm.py               # NSM adapter: API client, PDF resolver, downloader
├── cli.py                    # Modify: wire up download nsm command
tests/
├── test_nsm.py               # Tests with recorded API responses
├── fixtures/
│   ├── nsm_api_response.json # Recorded API response fixture
│   └── nsm_html_page.html    # Recorded HTML metadata page fixture
```

## Key Design Decisions

1. **No country/type filters at query time.** We query the entire NSM with `latest_flag=Y` only, then download everything. Country resolution happens at ingest/analysis time, not download time.
2. **Single broad query with pagination**, not per-country queries. This avoids the multi-LEI AND bug entirely — we just get everything.
3. **Two-hop PDF resolution.** ~55% of NSM links are HTML metadata pages. We fetch the HTML page, parse it with BeautifulSoup, and extract the actual PDF link.
4. **Manifest-only output.** The adapter writes `nsm_manifest.jsonl` and PDF files. It does NOT touch DuckDB. The existing `corpus ingest` command handles DB loading.
5. **Circuit breaker.** Configurable consecutive failure threshold and total failure abort limit (from `config.toml [nsm.circuit_breaker]`).

## Existing Code to Use

- `src/corpus/io/safe_write.py` — `safe_write(target, data)` for atomic PDF writes
- `src/corpus/io/http.py` — `CorpusHTTPClient` with retry/backoff for all HTTP
- `src/corpus/logging.py` — `CorpusLogger` with `.timed()` context manager
- `config.toml [nsm]` — `delay_api=1.0`, `delay_download=1.0`, `max_retries=5`, etc.
- `config.toml [nsm.circuit_breaker]` — `consecutive_failures_skip=5`, `total_failures_abort=10`
- `config.toml [paths]` — `manifests_dir`, `original_dir`, `api_responses_dir`

---

### Task 1: Create sources package and NSM API query function

**Files:**
- Create: `src/corpus/sources/__init__.py`
- Create: `src/corpus/sources/nsm.py`
- Create: `tests/test_nsm.py`
- Create: `tests/fixtures/nsm_api_response.json`

- [ ] **Step 1: Create the API response fixture**

Save a minimal but realistic NSM API response as a test fixture. This includes the Elasticsearch wrapper format with two hits — one with a direct PDF link, one with an HTML link.

Create `tests/fixtures/nsm_api_response.json`:
```json
{
  "took": 11,
  "timed_out": false,
  "_shards": {"failed": 0, "skipped": 0, "successful": 4, "total": 4},
  "hits": {
    "total": {"relation": "eq", "value": 2},
    "hits": [
      {
        "_index": "fca-nsm-searchdata",
        "_id": "abc-123-pdf",
        "_source": {
          "submitted_date": "2024-06-15T10:30:00Z",
          "publication_date": "2024-06-15T10:22:00Z",
          "company": "REPUBLIC OF KENYA",
          "lei": "549300VVURQQYU45PR87",
          "type": "Publication of a Prospectus",
          "type_code": "PDI",
          "headline": "Offering Circular for USD 1bn Notes",
          "download_link": "NSM/Portal/NI-000131055/NI-000131055.pdf",
          "disclosure_id": "abc-123-pdf",
          "latest_flag": "Y",
          "source": "FCA",
          "seq_id": "abc-123-pdf",
          "hist_seq": "1",
          "classifications": "3.1",
          "classifications_code": "3.1",
          "tag_esef": "",
          "lei_remediation_flag": "N",
          "last_updated_date": "2024-06-15T10:30:00Z"
        }
      },
      {
        "_index": "fca-nsm-searchdata",
        "_id": "def-456-html",
        "_source": {
          "submitted_date": "2024-03-01T08:00:00Z",
          "publication_date": "2024-03-01T07:55:00Z",
          "company": "THE FEDERAL REPUBLIC OF NIGERIA",
          "lei": "549300GSBZD84TNEQ285",
          "type": "Base Prospectus",
          "type_code": "FCA01",
          "headline": "Base Prospectus EMTN Programme",
          "download_link": "NSM/RNS/def-456-html.html",
          "disclosure_id": "def-456-html",
          "latest_flag": "Y",
          "source": "RNS",
          "seq_id": "def-456-html",
          "hist_seq": "1",
          "classifications": "",
          "classifications_code": "0.0",
          "tag_esef": "",
          "lei_remediation_flag": "N",
          "last_updated_date": "2024-03-01T08:00:00Z"
        }
      }
    ]
  }
}
```

- [ ] **Step 2: Write failing tests for query_nsm_api**

Create `tests/test_nsm.py`:
```python
"""Tests for the NSM source adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from corpus.sources.nsm import query_nsm_api, parse_hits

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestQueryNsmApi:
    """Tests for NSM API query construction and response parsing."""

    def test_query_returns_hits(self) -> None:
        """query_nsm_api returns list of hit dicts from API response."""
        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        hits, total = query_nsm_api(mock_client, from_offset=0, size=100)

        assert len(hits) == 2
        assert total == 2

    def test_query_sends_correct_payload(self) -> None:
        """query_nsm_api sends latest_flag=Y, no country filters."""
        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        query_nsm_api(mock_client, from_offset=0, size=500)

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["from"] == 0
        assert payload["size"] == 500
        criteria_names = [c["name"] for c in payload["criteriaObj"]["criteria"]]
        assert "latest_flag" in criteria_names
        # No company_lei filter — breadth over depth
        assert "company_lei" not in criteria_names

    def test_query_empty_response(self) -> None:
        """query_nsm_api returns empty list when no hits."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        mock_client.post.return_value = mock_response

        hits, total = query_nsm_api(mock_client, from_offset=0, size=100)

        assert hits == []
        assert total == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.sources'`

- [ ] **Step 4: Write parse_hits tests**

Append to `tests/test_nsm.py`:
```python
class TestParseHits:
    """Tests for parsing raw API hits into manifest records."""

    def test_parse_direct_pdf_hit(self) -> None:
        """Hit with .pdf download_link produces correct manifest record."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][0]  # PDF link

        records = parse_hits([hit])

        assert len(records) == 1
        rec = records[0]
        assert rec["source"] == "nsm"
        assert rec["native_id"] == "abc-123-pdf"
        assert rec["storage_key"] == "nsm__abc-123-pdf"
        assert rec["download_url"] == "https://data.fca.org.uk/artefacts/NSM/Portal/NI-000131055/NI-000131055.pdf"
        assert rec["issuer_name"] == "REPUBLIC OF KENYA"
        assert rec["lei"] == "549300VVURQQYU45PR87"
        assert rec["doc_type"] == "PDI"
        assert rec["title"] == "Offering Circular for USD 1bn Notes"

    def test_parse_html_hit(self) -> None:
        """Hit with .html download_link still produces a record with full URL."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][1]  # HTML link

        records = parse_hits([hit])

        assert len(records) == 1
        rec = records[0]
        assert rec["native_id"] == "def-456-html"
        assert rec["download_url"] == "https://data.fca.org.uk/artefacts/NSM/RNS/def-456-html.html"

    def test_parse_preserves_source_metadata(self) -> None:
        """Extra NSM fields go into source_metadata."""
        fixture = _load_fixture("nsm_api_response.json")
        hit = fixture["hits"]["hits"][0]

        records = parse_hits([hit])
        meta = records[0].get("source_metadata", {})

        assert meta["nsm_source"] == "FCA"
        assert meta["type_name"] == "Publication of a Prospectus"
        assert meta["classifications_code"] == "3.1"
```

- [ ] **Step 5: Implement sources package and query_nsm_api + parse_hits**

Create `src/corpus/sources/__init__.py`:
```python
```

Create `src/corpus/sources/nsm.py`:
```python
"""NSM source adapter — download documents from FCA National Storage Mechanism.

Queries the NSM Elasticsearch API with no country/type filters (breadth-first),
downloads PDFs, and writes nsm_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

from typing import Any

from corpus.io.http import CorpusHTTPClient

NSM_API_URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"
NSM_ARTEFACT_BASE = "https://data.fca.org.uk/artefacts"


def query_nsm_api(
    client: CorpusHTTPClient,
    *,
    from_offset: int = 0,
    size: int = 10000,
) -> tuple[list[dict[str, Any]], int]:
    """Query NSM API for all latest filings. Returns (hits, total_count)."""
    payload = {
        "from": from_offset,
        "size": size,
        "sort": "submitted_date",
        "sortorder": "desc",
        "criteriaObj": {
            "criteria": [
                {"name": "latest_flag", "value": "Y"},
            ],
            "dateCriteria": [],
        },
    }
    resp = client.post(NSM_API_URL, json=payload)
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    return hits, total


def parse_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw NSM API hits into manifest records."""
    records = []
    for hit in hits:
        src = hit.get("_source", {})
        disclosure_id = src.get("disclosure_id", hit.get("_id", ""))
        download_link = src.get("download_link", "")
        download_url = f"{NSM_ARTEFACT_BASE}/{download_link}" if download_link else ""

        record: dict[str, Any] = {
            "source": "nsm",
            "native_id": disclosure_id,
            "storage_key": f"nsm__{disclosure_id}",
            "title": src.get("headline", ""),
            "issuer_name": src.get("company", ""),
            "lei": src.get("lei", ""),
            "doc_type": src.get("type_code", ""),
            "publication_date": (src.get("publication_date", "") or "")[:10] or None,
            "submitted_date": src.get("submitted_date"),
            "download_url": download_url,
            "source_metadata": {
                "nsm_source": src.get("source", ""),
                "type_name": src.get("type", ""),
                "classifications": src.get("classifications", ""),
                "classifications_code": src.get("classifications_code", ""),
                "seq_id": src.get("seq_id", ""),
                "hist_seq": src.get("hist_seq", ""),
                "tag_esef": src.get("tag_esef", ""),
                "lei_remediation_flag": src.get("lei_remediation_flag", ""),
            },
        }
        records.append(record)
    return records
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/ tests/test_nsm.py && uv run ruff format --check src/corpus/sources/ tests/test_nsm.py && uv run pyright src/corpus/sources/`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/corpus/sources/__init__.py src/corpus/sources/nsm.py tests/test_nsm.py tests/fixtures/nsm_api_response.json
git commit -m "feat(nsm): add API query and hit parsing with no country filters"
```

---

### Task 2: PDF URL resolution (two-hop HTML→PDF)

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`
- Create: `tests/fixtures/nsm_html_page.html`

- [ ] **Step 1: Create the HTML fixture**

Create `tests/fixtures/nsm_html_page.html`:
```html
<html>
<body>
<h1>Republic of Kenya - Offering Circular</h1>
<p>Click below to download the document:</p>
<a href="/artefacts/NSM/RNS/abc-123/prospectus.pdf">Download PDF</a>
<a href="/other/link.html">Other link</a>
</body>
</html>
```

- [ ] **Step 2: Write failing tests for resolve_pdf_url**

Append to `tests/test_nsm.py`:
```python
class TestResolvePdfUrl:
    """Tests for two-hop HTML→PDF URL resolution."""

    def test_direct_pdf_url_returned_as_is(self) -> None:
        """URL ending in .pdf is returned unchanged."""
        from corpus.sources.nsm import resolve_pdf_url

        url = "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf"
        result = resolve_pdf_url(url, client=MagicMock())
        assert result == url

    def test_html_url_extracts_pdf_link(self) -> None:
        """HTML page with a PDF link returns the resolved PDF URL."""
        from corpus.sources.nsm import resolve_pdf_url

        html_content = (FIXTURES / "nsm_html_page.html").read_text()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = html_content
        mock_client.get.return_value = mock_response

        url = "https://data.fca.org.uk/artefacts/NSM/RNS/def-456.html"
        result = resolve_pdf_url(url, client=mock_client)

        assert result == "https://data.fca.org.uk/artefacts/NSM/RNS/abc-123/prospectus.pdf"

    def test_html_url_no_pdf_link_returns_none(self) -> None:
        """HTML page without any PDF link returns None."""
        from corpus.sources.nsm import resolve_pdf_url

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body>No links here</body></html>"
        mock_client.get.return_value = mock_response

        url = "https://data.fca.org.uk/artefacts/NSM/RNS/no-pdf.html"
        result = resolve_pdf_url(url, client=mock_client)

        assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestResolvePdfUrl -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_pdf_url'`

- [ ] **Step 4: Implement resolve_pdf_url**

Add to `src/corpus/sources/nsm.py`:
```python
import re
from urllib.parse import urljoin


def resolve_pdf_url(url: str, *, client: CorpusHTTPClient) -> str | None:
    """Resolve a download URL to a direct PDF link.

    Direct .pdf URLs are returned unchanged. HTML metadata pages are
    fetched and parsed to extract the PDF link (two-hop pattern).
    Returns None if no PDF link can be found.
    """
    if url.lower().endswith(".pdf"):
        return url

    resp = client.get(url)
    html = resp.text

    # Look for <a> tags with href ending in .pdf
    pdf_pattern = re.compile(r'href=["\']([^"\']*\.pdf)["\']', re.IGNORECASE)
    match = pdf_pattern.search(html)
    if match:
        return urljoin(url, match.group(1))

    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestResolvePdfUrl -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py tests/fixtures/nsm_html_page.html
git commit -m "feat(nsm): add two-hop HTML→PDF URL resolution"
```

---

### Task 3: Download orchestrator with manifest writing

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing test for download_nsm_document**

Append to `tests/test_nsm.py`:
```python
import hashlib


class TestDownloadNsmDocument:
    """Tests for single-document download + manifest record creation."""

    def test_downloads_pdf_and_returns_record(self, tmp_path: Path) -> None:
        """Successful PDF download returns manifest record with file_path and file_hash."""
        from corpus.sources.nsm import download_nsm_document

        pdf_bytes = b"%PDF-1.4 fake pdf content here"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = pdf_bytes
        mock_client.get.return_value = mock_response

        record = {
            "source": "nsm",
            "native_id": "abc-123-pdf",
            "storage_key": "nsm__abc-123-pdf",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(
            record, client=mock_client, output_dir=tmp_path
        )

        assert result is not None
        assert result["file_path"] == str(tmp_path / "nsm__abc-123-pdf.pdf")
        assert result["file_hash"] == hashlib.sha256(pdf_bytes).hexdigest()
        assert (tmp_path / "nsm__abc-123-pdf.pdf").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        """If the PDF already exists on disk, returns None (skip)."""
        from corpus.sources.nsm import download_nsm_document

        target = tmp_path / "nsm__abc-123-pdf.pdf"
        target.write_bytes(b"%PDF-1.4 already here")

        record = {
            "source": "nsm",
            "native_id": "abc-123-pdf",
            "storage_key": "nsm__abc-123-pdf",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(
            record, client=MagicMock(), output_dir=tmp_path
        )
        assert result is None

    def test_html_link_resolves_then_downloads(self, tmp_path: Path) -> None:
        """HTML download URL triggers resolution before downloading."""
        from corpus.sources.nsm import download_nsm_document

        html_content = '<html><a href="/artefacts/NSM/RNS/real.pdf">PDF</a></html>'
        pdf_bytes = b"%PDF-1.4 real content"

        mock_client = MagicMock()
        html_resp = MagicMock()
        html_resp.text = html_content
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        mock_client.get.side_effect = [html_resp, pdf_resp]

        record = {
            "source": "nsm",
            "native_id": "def-456-html",
            "storage_key": "nsm__def-456-html",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/def-456.html",
        }

        result = download_nsm_document(
            record, client=mock_client, output_dir=tmp_path
        )

        assert result is not None
        assert (tmp_path / "nsm__def-456-html.pdf").exists()

    def test_invalid_pdf_returns_none(self, tmp_path: Path) -> None:
        """Non-PDF content (no %PDF header) returns None."""
        from corpus.sources.nsm import download_nsm_document

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"<html>not a pdf</html>"
        mock_client.get.return_value = mock_response

        record = {
            "source": "nsm",
            "native_id": "bad-content",
            "storage_key": "nsm__bad-content",
            "download_url": "https://data.fca.org.uk/artefacts/NSM/Portal/doc.pdf",
        }

        result = download_nsm_document(
            record, client=mock_client, output_dir=tmp_path
        )
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestDownloadNsmDocument -v`
Expected: FAIL — `ImportError: cannot import name 'download_nsm_document'`

- [ ] **Step 3: Implement download_nsm_document**

Add to `src/corpus/sources/nsm.py`:
```python
import hashlib
from pathlib import Path

from corpus.io.safe_write import safe_write

PDF_HEADER = b"%PDF"


def download_nsm_document(
    record: dict[str, Any],
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
) -> dict[str, Any] | None:
    """Download a single NSM document. Returns enriched record or None on skip/fail.

    Skips if the file already exists on disk. Resolves HTML→PDF two-hop links.
    Validates that downloaded content starts with %PDF header.
    """
    storage_key = record.get("storage_key", "")
    target = output_dir / f"{storage_key}.pdf"

    if target.exists():
        return None

    download_url = record.get("download_url", "")
    if not download_url:
        return None

    # Resolve two-hop HTML links
    pdf_url = resolve_pdf_url(download_url, client=client)
    if pdf_url is None:
        return None

    resp = client.get(pdf_url)
    content = resp.content

    if not content.startswith(PDF_HEADER):
        return None

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched = dict(record)
    enriched["file_path"] = str(target)
    enriched["file_hash"] = file_hash
    return enriched
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestDownloadNsmDocument -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): add single-document download with safe_write and PDF validation"
```

---

### Task 4: Full download pipeline with manifest writing and circuit breaker

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing test for run_nsm_download**

Append to `tests/test_nsm.py`:
```python
from corpus.logging import CorpusLogger


class TestRunNsmDownload:
    """Tests for the full NSM download pipeline orchestrator."""

    def test_writes_manifest_jsonl(self, tmp_path: Path) -> None:
        """run_nsm_download writes one JSONL line per downloaded document."""
        from corpus.sources.nsm import run_nsm_download

        fixture = _load_fixture("nsm_api_response.json")
        pdf_bytes = b"%PDF-1.4 fake pdf content"

        mock_client = MagicMock()
        # First call: API query returns fixture; Second+ calls: PDF downloads
        api_resp = MagicMock()
        api_resp.json.return_value = fixture
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        pdf_resp.text = pdf_bytes.decode("utf-8", errors="replace")
        mock_client.post.return_value = api_resp
        mock_client.get.return_value = pdf_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_api=0.0,
            delay_download=0.0,
            page_size=100,
        )

        manifest_file = manifest_dir / "nsm_manifest.jsonl"
        assert manifest_file.exists()
        lines = [json.loads(l) for l in manifest_file.read_text().strip().split("\n") if l.strip()]
        # Both hits have .pdf-ending download URLs (after resolution)
        # The HTML one will fail since mock returns PDF bytes for text too
        assert stats["downloaded"] >= 1
        assert stats["api_pages_fetched"] == 1

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        """Pipeline aborts after total_failures_abort threshold."""
        from corpus.sources.nsm import run_nsm_download

        # Create a fixture with many hits that will all fail
        bad_hits = []
        for i in range(15):
            bad_hits.append({
                "_id": f"fail-{i}",
                "_source": {
                    "disclosure_id": f"fail-{i}",
                    "download_link": f"NSM/Portal/fail-{i}.pdf",
                    "company": "BADCORP",
                    "lei": "",
                    "type_code": "PDI",
                    "type": "Test",
                    "headline": f"Fail doc {i}",
                    "submitted_date": "2024-01-01T00:00:00Z",
                    "publication_date": "2024-01-01T00:00:00Z",
                    "source": "FCA",
                    "seq_id": f"fail-{i}",
                    "hist_seq": "1",
                    "classifications": "",
                    "classifications_code": "",
                    "tag_esef": "",
                    "lei_remediation_flag": "N",
                    "last_updated_date": "2024-01-01T00:00:00Z",
                },
            })

        mock_client = MagicMock()
        api_resp = MagicMock()
        api_resp.json.return_value = {
            "hits": {"total": {"value": 15}, "hits": bad_hits}
        }
        mock_client.post.return_value = api_resp
        # All downloads return non-PDF content
        bad_resp = MagicMock()
        bad_resp.content = b"not a pdf"
        mock_client.get.return_value = bad_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_api=0.0,
            delay_download=0.0,
            total_failures_abort=5,
        )

        assert stats["aborted"]
        assert stats["failed"] <= 6  # abort triggers at threshold, may overshoot by 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestRunNsmDownload -v`
Expected: FAIL — `ImportError: cannot import name 'run_nsm_download'`

- [ ] **Step 3: Implement run_nsm_download**

Add to `src/corpus/sources/nsm.py`:
```python
import json
import time

from corpus.logging import CorpusLogger


def run_nsm_download(
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay_api: float = 1.0,
    delay_download: float = 1.0,
    page_size: int = 10000,
    consecutive_failures_skip: int = 5,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Run the full NSM download pipeline.

    Paginates through all NSM results, downloads PDFs, writes manifest JSONL.
    Circuit breaker aborts after total_failures_abort failures.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "nsm_manifest.jsonl"

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "api_pages_fetched": 0,
        "total_hits": 0,
        "aborted": False,
    }

    from_offset = 0
    consecutive_failures = 0

    while True:
        if stats["aborted"]:
            break

        with logger.timed("nsm-api", "query", page=from_offset):
            hits, total = query_nsm_api(client, from_offset=from_offset, size=page_size)

        stats["api_pages_fetched"] += 1
        if stats["total_hits"] == 0:
            stats["total_hits"] = total

        if not hits:
            break

        records = parse_hits(hits)

        for record in records:
            if stats["aborted"]:
                break

            doc_id = record.get("native_id", "unknown")

            try:
                with logger.timed(doc_id, "download"):
                    result = download_nsm_document(
                        record, client=client, output_dir=output_dir
                    )
            except Exception as exc:
                logger.log(
                    document_id=doc_id,
                    step="download",
                    duration_ms=0,
                    status="error",
                    error_message=str(exc),
                )
                result = None

            if result is not None:
                with manifest_path.open("a") as f:
                    f.write(json.dumps(result) + "\n")
                stats["downloaded"] += 1
                consecutive_failures = 0
            elif record.get("download_url"):
                # Only count as failure if we actually tried (not a skip)
                target = output_dir / f"{record.get('storage_key', '')}.pdf"
                if not target.exists():
                    stats["failed"] += 1
                    consecutive_failures += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["skipped"] += 1

            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break

            if consecutive_failures >= consecutive_failures_skip:
                consecutive_failures = 0  # Reset after skip window

            if delay_download > 0:
                time.sleep(delay_download)

        from_offset += page_size
        if from_offset >= total:
            break

        if delay_api > 0:
            time.sleep(delay_api)

    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestRunNsmDownload -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): add full download pipeline with manifest writing and circuit breaker"
```

---

### Task 5: Wire CLI command and add BeautifulSoup dependency

**Files:**
- Modify: `src/corpus/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Add beautifulsoup4 dependency**

In `pyproject.toml`, add `beautifulsoup4>=4.12` to the `dependencies` list. This is needed for HTML parsing in the two-hop resolution (the regex approach from Task 2 handles simple cases, but BS4 is more robust for production and was used in Phase 1).

Actually — the regex approach in Task 2 is sufficient and simpler. Skip the BS4 dependency. No change needed to pyproject.toml.

- [ ] **Step 2: Write failing test for CLI integration**

Append to `tests/test_nsm.py`:
```python
from click.testing import CliRunner
from corpus.cli import cli


class TestNsmCli:
    """Tests for the CLI download nsm command."""

    def test_download_nsm_help(self) -> None:
        """corpus download nsm --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["download", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output

    def test_download_nsm_dry_run(self, tmp_path: Path) -> None:
        """corpus download nsm --dry-run lists total without downloading."""
        runner = CliRunner()

        fixture = _load_fixture("nsm_api_response.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        with patch("corpus.sources.nsm.CorpusHTTPClient") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            MockClient.return_value = mock_client

            result = runner.invoke(cli, [
                "download", "nsm",
                "--dry-run",
                "--output-dir", str(tmp_path / "original"),
                "--manifest-dir", str(tmp_path / "manifests"),
            ])

        assert result.exit_code == 0
        assert "2" in result.output  # total count from fixture
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestNsmCli -v`
Expected: FAIL — the current CLI just prints a stub message

- [ ] **Step 4: Update CLI to wire up NSM download**

Replace the `nsm` command in `src/corpus/cli.py` with:
```python
@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="data/original",
    help="Directory for downloaded PDFs.",
)
@click.option(
    "--manifest-dir",
    type=click.Path(path_type=Path),
    default="data/manifests",
    help="Directory for manifest JSONL files.",
)
@click.option(
    "--log-dir",
    type=click.Path(path_type=Path),
    default="data/telemetry",
    help="Directory for structured log files.",
)
@click.option("--dry-run", is_flag=True, help="Query API and report count without downloading.")
def nsm(
    run_id: str | None,
    output_dir: Path,
    manifest_dir: Path,
    log_dir: Path,
    dry_run: bool,
) -> None:
    """Download documents from FCA National Storage Mechanism."""
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger
    from corpus.sources.nsm import query_nsm_api, run_nsm_download

    if run_id is None:
        run_id = f"nsm-{uuid.uuid4().hex[:12]}"

    client = CorpusHTTPClient()

    if dry_run:
        _, total = query_nsm_api(client, from_offset=0, size=1)
        click.echo(f"NSM dry run: {total} total documents available.")
        return

    log_file = log_dir / f"nsm_{run_id}.jsonl"
    logger = CorpusLogger(log_file, run_id=run_id)

    click.echo(f"Starting NSM download (run_id={run_id})...")
    stats = run_nsm_download(
        client=client,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id=run_id,
    )

    click.echo(
        f"NSM download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
```

Also add the import at the top:
```python
from unittest.mock import patch, MagicMock
```
(only in the test file, not in cli.py)

- [ ] **Step 5: Add missing import to test file**

Add to the imports section of `tests/test_nsm.py`:
```python
from unittest.mock import MagicMock, patch
```

(Replace the existing `from unittest.mock import MagicMock` import.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestNsmCli -v`
Expected: All 2 tests PASS

- [ ] **Step 7: Run full test suite**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 8: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/ tests/ && uv run ruff format --check src/corpus/ tests/ && uv run pyright src/corpus/`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/corpus/cli.py tests/test_nsm.py
git commit -m "feat(nsm): wire CLI download nsm command with dry-run support"
```

---

### Task 6: Save API responses for debugging and add related_org handling

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing test for API response saving**

Append to `tests/test_nsm.py`:
```python
class TestApiResponseSaving:
    """Tests for saving raw API responses to disk."""

    def test_saves_api_response_to_file(self, tmp_path: Path) -> None:
        """run_nsm_download saves raw API response pages to api_responses_dir."""
        from corpus.sources.nsm import run_nsm_download

        fixture = _load_fixture("nsm_api_response.json")
        pdf_bytes = b"%PDF-1.4 test content"

        mock_client = MagicMock()
        api_resp = MagicMock()
        api_resp.json.return_value = fixture
        mock_client.post.return_value = api_resp
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        mock_client.get.return_value = pdf_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        api_dir = tmp_path / "api_responses"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        run_nsm_download(
            client=mock_client,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_api=0.0,
            delay_download=0.0,
            api_responses_dir=api_dir,
        )

        assert api_dir.exists()
        response_files = list(api_dir.glob("nsm_page_*.json"))
        assert len(response_files) == 1
```

- [ ] **Step 2: Write failing test for related_org parsing**

Append to `tests/test_nsm.py`:
```python
class TestRelatedOrgParsing:
    """Tests for parsing related_org field from NSM API hits."""

    def test_related_org_included_in_source_metadata(self) -> None:
        """Related organisations are included in source_metadata."""
        hit = {
            "_id": "rel-org-test",
            "_source": {
                "disclosure_id": "rel-org-test",
                "download_link": "NSM/Portal/test.pdf",
                "company": "REPUBLIC OF KENYA",
                "lei": "549300VVURQQYU45PR87",
                "type_code": "PDI",
                "type": "Publication of a Prospectus",
                "headline": "Test doc",
                "submitted_date": "2024-01-01T00:00:00Z",
                "publication_date": "2024-01-01T00:00:00Z",
                "source": "RNS",
                "seq_id": "rel-org-test",
                "hist_seq": "1",
                "classifications": "",
                "classifications_code": "",
                "tag_esef": "",
                "lei_remediation_flag": "N",
                "last_updated_date": "2024-01-01T00:00:00Z",
                "related_org": [
                    {"lei": "ABC123", "company": "Some Bank Ltd"}
                ],
            },
        }

        records = parse_hits([hit])
        meta = records[0]["source_metadata"]
        assert meta["related_org"] == [{"lei": "ABC123", "company": "Some Bank Ltd"}]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestApiResponseSaving tests/test_nsm.py::TestRelatedOrgParsing -v`
Expected: FAIL

- [ ] **Step 4: Update run_nsm_download to save API responses**

Add `api_responses_dir: Path | None = None` parameter to `run_nsm_download`. After each API query, if `api_responses_dir` is set, save the raw response:

```python
# Inside run_nsm_download, after the query_nsm_api call:
        if api_responses_dir is not None:
            api_responses_dir.mkdir(parents=True, exist_ok=True)
            resp_path = api_responses_dir / f"nsm_page_{from_offset:06d}.json"
            resp_path.write_text(json.dumps(data_for_save, indent=2))
```

This requires `query_nsm_api` to also return the raw response data. Update `query_nsm_api` to accept an optional `raw_responses` list that it appends to:

Actually, simpler approach — have `run_nsm_download` do a separate save by re-serializing the hits. Update the `run_nsm_download` function signature to accept `api_responses_dir: Path | None = None`, and after the query, save the raw data:

```python
        if api_responses_dir is not None:
            api_responses_dir.mkdir(parents=True, exist_ok=True)
            page_data = {"total": total, "from": from_offset, "hit_count": len(hits)}
            resp_file = api_responses_dir / f"nsm_page_{from_offset:06d}.json"
            resp_file.write_text(json.dumps(page_data, indent=2))
```

- [ ] **Step 5: Update parse_hits to include related_org**

In the `parse_hits` function, add to the `source_metadata` dict:
```python
                "related_org": src.get("related_org", []),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All tests PASS

- [ ] **Step 7: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/ tests/test_nsm.py && uv run pyright src/corpus/sources/`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): save API responses for debugging, parse related_org"
```

---

### Task 7: Update CLI with api-responses-dir and update Makefile

**Files:**
- Modify: `src/corpus/cli.py`
- Modify: `Makefile`

- [ ] **Step 1: Add --api-responses-dir to CLI nsm command**

In the `nsm` CLI command, add:
```python
@click.option(
    "--api-responses-dir",
    type=click.Path(path_type=Path),
    default="data/api_responses",
    help="Directory for raw API response JSON files.",
)
```

And pass it through to `run_nsm_download`:
```python
    stats = run_nsm_download(
        client=client,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id=run_id,
        api_responses_dir=api_responses_dir,
    )
```

- [ ] **Step 2: Update Makefile download-nsm target**

The Makefile `download-nsm` target already invokes `uv run corpus download nsm --run-id=$(RUN_ID)`. No changes needed — the defaults from config.toml align with the CLI defaults.

- [ ] **Step 3: Run full test suite and linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest -v && uv run ruff check src/corpus/ tests/ && uv run pyright src/corpus/`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/corpus/cli.py
git commit -m "feat(nsm): add api-responses-dir CLI option"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `uv run corpus download nsm --help` shows all options (--run-id, --output-dir, --manifest-dir, --log-dir, --dry-run, --api-responses-dir)
- [ ] `uv run corpus download nsm --dry-run` queries the API and reports total count
- [ ] `uv run pytest -v` — all tests pass
- [ ] `uv run ruff check src/corpus/ tests/` — no lint errors
- [ ] `uv run ruff format --check src/corpus/ tests/` — formatting OK
- [ ] `uv run pyright src/corpus/` — no type errors
- [ ] `make download-nsm` invokes the CLI correctly
- [ ] nsm_manifest.jsonl format is compatible with `corpus ingest` (verified by existing ingest tests)
