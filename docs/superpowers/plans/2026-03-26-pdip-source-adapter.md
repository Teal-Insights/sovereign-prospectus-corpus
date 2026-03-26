# PDIP Source Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PDIP source adapter that discovers documents from the Georgetown PDIP API and downloads their PDFs, following the same two-phase pattern as NSM/EDGAR.

**Architecture:** Two CLI commands (`corpus discover pdip` → `corpus download pdip`). Discovery POSTs to the PDIP search API with browser-like headers, writes `pdip_discovery.jsonl`. Download reads discovery JSONL, fetches PDFs from `/api/pdf/{id}`, validates `%PDF` magic bytes, writes `pdip_manifest.jsonl`. Uses `requests.Session` directly (not `CorpusHTTPClient`) because PDIP requires specific browser-like headers.

**Tech Stack:** Python 3.12+, requests, Click, pytest, safe_write, CorpusLogger

**Spec:** `docs/superpowers/specs/2026-03-26-pdip-source-adapter-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/corpus/sources/pdip.py` | Discovery + download adapter |
| Create | `tests/test_pdip.py` | Unit tests |
| Create | `tests/fixtures/pdip_search_response.json` | Captured API fixture |
| Modify | `src/corpus/cli.py` | Wire discover/download commands |
| Modify | `config.toml` | Add `[pdip.circuit_breaker]` |
| Modify | `src/corpus/reporting.py` | Add `not_found` to non-failure statuses |

---

### Task 1: Test Fixture + Discovery Parsing

**Files:**
- Create: `tests/fixtures/pdip_search_response.json`
- Create: `tests/test_pdip.py`
- Create: `src/corpus/sources/pdip.py`

- [ ] **Step 1: Create the test fixture**

Capture a realistic PDIP search API response with 3 documents covering different metadata shapes (annotated with full metadata, not-annotated sparse, different instrument type):

```json
{
    "total": 3,
    "results": [
        {
            "id": "VEN85",
            "score": null,
            "document_title": "Loan Agreement between the Republic of Venezuela and International Bank for Reconstruction and Development dated December 14, 1990",
            "tag_status": "Annotated",
            "metadata": {
                "DebtorCountry": ["Venezuela"],
                "CreditorCountry": ["Multilateral; Regional; or Plurilateral Lenders"],
                "CreditorType": ["Multilateral Official"],
                "InstrumentType": ["Loan"],
                "BorrowerDebttoGDPRatio": null,
                "BorrowerSizeofEconomy": ["To be filled. "],
                "OtherMultilateralRegionalPlurilateralLenders": ["International Bank for Reconstruction and Development (IBRD / World Bank)"],
                "CreditorSizeofEconomy": ["To be filled. "],
                "InstrumentMaturityDate": ["December 15, 2005"],
                "CommitmentSize": ["To be filled. "],
                "InstrumentMaturityYear": ["2005"]
            }
        },
        {
            "id": "BRA1",
            "score": null,
            "document_title": "Offering Memorandum Federal Republic of Brazil Bonds Due 2037/2041/2045",
            "tag_status": "Not Annotated",
            "metadata": {
                "DebtorCountry": ["Brazil"],
                "InstrumentType": ["Bond"]
            }
        },
        {
            "id": "ARG23",
            "score": null,
            "document_title": "Indenture between the Republic of Argentina and The Bank of New York Mellon",
            "tag_status": "Annotated",
            "metadata": {
                "DebtorCountry": ["Argentina"],
                "CreditorCountry": ["United States"],
                "CreditorType": ["Private Creditor(s)"],
                "InstrumentType": ["Bond"],
                "InstrumentMaturityDate": ["January 15, 2038"],
                "InstrumentMaturityYear": ["2038"]
            }
        }
    ]
}
```

Save to `tests/fixtures/pdip_search_response.json`.

- [ ] **Step 2: Write failing test for `parse_search_results`**

```python
"""Tests for the PDIP source adapter."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseSearchResults:
    """Tests for parsing PDIP search API response into discovery records."""

    def test_parses_all_results(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        assert len(records) == 3

    def test_record_has_required_fields(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        r = records[0]

        assert r["native_id"] == "VEN85"
        assert r["source"] == "pdip"
        assert r["title"] == "Loan Agreement between the Republic of Venezuela and International Bank for Reconstruction and Development dated December 14, 1990"
        assert r["tag_status"] == "Annotated"
        assert r["country"] == "Venezuela"
        assert r["instrument_type"] == "Loan"
        assert r["creditor_country"] == "Multilateral; Regional; or Plurilateral Lenders"
        assert r["creditor_type"] == "Multilateral Official"
        assert r["maturity_date"] == "December 15, 2005"
        assert r["maturity_year"] == "2005"

    def test_sparse_metadata_uses_none(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        bra = records[1]  # BRA1 has minimal metadata

        assert bra["native_id"] == "BRA1"
        assert bra["country"] == "Brazil"
        assert bra["creditor_type"] is None
        assert bra["maturity_date"] is None

    def test_extra_metadata_preserved(self) -> None:
        from corpus.sources.pdip import parse_search_results

        fixture = _load_fixture("pdip_search_response.json")
        records = parse_search_results(fixture)
        r = records[0]

        assert "metadata" in r
        assert "BorrowerDebttoGDPRatio" in r["metadata"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pdip.py::TestParseSearchResults -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.sources.pdip'`

- [ ] **Step 4: Implement `parse_search_results`**

Create `src/corpus/sources/pdip.py`:

```python
"""PDIP source adapter — download documents from Georgetown PDIP.

Queries the PDIP search API for sovereign debt documents, downloads PDFs,
and writes pdip_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

from typing import Any

PDIP_BASE_URL = "https://publicdebtispublic.mdi.georgetown.edu"
PDIP_SEARCH_URL = f"{PDIP_BASE_URL}/api/search/"
PDIP_PDF_URL = f"{PDIP_BASE_URL}/api/pdf/{{doc_id}}"

PDIP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Origin": PDIP_BASE_URL,
    "Referer": f"{PDIP_BASE_URL}/search/",
}

# Metadata field mappings: API key -> discovery record key
_META_FIELDS = {
    "DebtorCountry": "country",
    "InstrumentType": "instrument_type",
    "CreditorCountry": "creditor_country",
    "CreditorType": "creditor_type",
    "InstrumentMaturityDate": "maturity_date",
    "InstrumentMaturityYear": "maturity_year",
}

# These metadata keys are promoted to top-level fields; remaining ones go in "metadata"
_PROMOTED_KEYS = set(_META_FIELDS.keys())


def _first_or_none(val: list[str] | None) -> str | None:
    """Extract first element from a list field, or None."""
    if isinstance(val, list) and val:
        return val[0]
    return None


def parse_search_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse PDIP search API response into discovery records."""
    records: list[dict[str, Any]] = []

    for result in response.get("results", []):
        meta = result.get("metadata", {})

        record: dict[str, Any] = {
            "native_id": result["id"],
            "source": "pdip",
            "title": result.get("document_title", ""),
            "tag_status": result.get("tag_status", ""),
        }

        # Promote well-known metadata fields to top level
        for api_key, record_key in _META_FIELDS.items():
            record[record_key] = _first_or_none(meta.get(api_key))

        # Store remaining metadata
        extra_meta = {k: v for k, v in meta.items() if k not in _PROMOTED_KEYS}
        record["metadata"] = extra_meta

        records.append(record)

    return records
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_pdip.py::TestParseSearchResults -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/pdip_search_response.json tests/test_pdip.py src/corpus/sources/pdip.py
git commit -m "feat(pdip): add search result parsing with tests"
```

---

### Task 2: Discovery Function

**Files:**
- Modify: `tests/test_pdip.py`
- Modify: `src/corpus/sources/pdip.py`

- [ ] **Step 1: Write failing test for `discover_pdip`**

Add to `tests/test_pdip.py`:

```python
from unittest.mock import MagicMock, patch

import requests


class TestDiscoverPdip:
    """Tests for the full discovery pipeline."""

    def test_discovers_documents(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, delay=0.0)

        assert stats["total_documents"] == 3
        assert output.exists()
        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        assert len(lines) == 3
        assert lines[0]["native_id"] == "VEN85"

    def test_paginates_when_needed(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        # Simulate: first page returns all 3, total=3
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, page_size=100, delay=0.0)

        # Single API call since 3 < 100
        assert mock_session.post.call_count == 1
        assert stats["pages_fetched"] == 1

    def test_deduplicates_by_native_id(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        # Return same results twice (simulating overlap across pages)
        output = tmp_path / "pdip_discovery.jsonl"

        page1 = dict(fixture)
        page2 = {"total": 3, "results": [fixture["results"][0]]}  # duplicate VEN85

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp1 = MagicMock()
            mock_resp1.status_code = 200
            mock_resp1.json.return_value = page1
            mock_resp1.raise_for_status = MagicMock()
            mock_resp2 = MagicMock()
            mock_resp2.status_code = 200
            mock_resp2.json.return_value = page2
            mock_resp2.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.side_effect = [mock_resp1, mock_resp2]
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, page_size=3, delay=0.0)

        lines = [json.loads(line) for line in output.read_text().strip().split("\n")]
        native_ids = [line["native_id"] for line in lines]
        assert len(native_ids) == len(set(native_ids))
        assert stats["total_documents"] == 3

    def test_handles_api_error(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import discover_pdip

        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            stats = discover_pdip(output_path=output, delay=0.0)

        assert stats["total_documents"] == 0
        assert stats["error"] is not None

    def test_sets_browser_headers(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import PDIP_HEADERS, discover_pdip

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "pdip_discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            discover_pdip(output_path=output, delay=0.0)

        mock_session.headers.update.assert_called_once_with(PDIP_HEADERS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdip.py::TestDiscoverPdip -v`
Expected: FAIL — `ImportError: cannot import name 'discover_pdip'`

- [ ] **Step 3: Implement `discover_pdip`**

Add to `src/corpus/sources/pdip.py`:

```python
import json
import logging
import time

from corpus.io.safe_write import safe_write

# Add at top with other TYPE_CHECKING imports:
if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)


def discover_pdip(
    *,
    output_path: Path,
    page_size: int = 100,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Query PDIP search API for all documents.

    Paginates through results, writes discovery JSONL. Returns stats dict.
    """
    import requests

    session = requests.Session()
    session.headers.update(PDIP_HEADERS)

    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    page = 1
    pages_fetched = 0
    error: str | None = None

    while True:
        payload = {
            "page": page,
            "sortBy": "date",
            "sortOrder": "asc",
            "pageSize": page_size,
        }

        try:
            resp = session.post(PDIP_SEARCH_URL, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            log.error("PDIP search API failed on page %d: %s", page, exc)
            error = str(exc)
            break

        pages_fetched += 1
        results = data.get("results", [])
        records = parse_search_results(data)

        for record in records:
            if record["native_id"] not in seen_ids:
                seen_ids.add(record["native_id"])
                all_records.append(record)

        if len(results) < page_size:
            break

        page += 1
        if delay > 0:
            time.sleep(delay)

    content = "".join(json.dumps(r) + "\n" for r in all_records).encode()
    safe_write(output_path, content, overwrite=True)

    return {
        "total_documents": len(all_records),
        "pages_fetched": pages_fetched,
        "error": error,
    }
```

Update the imports at the top of the file — add `import json`, `import logging`, `import time`, and add the `TYPE_CHECKING` block with `from pathlib import Path`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdip.py::TestDiscoverPdip -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pdip.py src/corpus/sources/pdip.py
git commit -m "feat(pdip): add discovery function with pagination and dedup"
```

---

### Task 3: Single-Document Download

**Files:**
- Modify: `tests/test_pdip.py`
- Modify: `src/corpus/sources/pdip.py`

- [ ] **Step 1: Write failing tests for `download_pdip_document`**

Add to `tests/test_pdip.py`:

```python
import hashlib


class TestDownloadPdipDocument:
    """Tests for single-document PDF download."""

    def test_downloads_valid_pdf(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        pdf_bytes = b"%PDF-1.6\nfake pdf content"
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = pdf_bytes
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp

        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test Loan Agreement",
            "tag_status": "Annotated",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }

        result, status = download_pdip_document(
            record, session=mock_session, output_dir=tmp_path
        )

        assert status == "success"
        assert result is not None
        assert result["file_path"] == str(tmp_path / "pdip__VEN85.pdf")
        assert result["file_hash"] == hashlib.sha256(pdf_bytes).hexdigest()
        assert result["file_size_bytes"] == len(pdf_bytes)
        assert result["source"] == "pdip"
        assert result["storage_key"] == "pdip__VEN85"
        assert result["download_url"] == "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85"
        assert (tmp_path / "pdip__VEN85.pdf").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        target = tmp_path / "pdip__VEN85.pdf"
        target.write_bytes(b"already here")

        record = {"native_id": "VEN85", "source": "pdip"}

        result, status = download_pdip_document(
            record, session=MagicMock(), output_dir=tmp_path
        )
        assert result is None
        assert status == "skipped_exists"

    def test_handles_404(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_session.get.return_value = mock_resp

        record = {"native_id": "MISSING1", "source": "pdip"}

        result, status = download_pdip_document(
            record, session=mock_session, output_dir=tmp_path
        )
        assert result is None
        assert status == "not_found"

    def test_rejects_invalid_pdf(self, tmp_path: Path) -> None:
        from corpus.sources.pdip import download_pdip_document

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = b'{"error": "something went wrong"}'
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp

        record = {"native_id": "BAD1", "source": "pdip"}

        result, status = download_pdip_document(
            record, session=mock_session, output_dir=tmp_path
        )
        assert result is None
        assert status == "invalid_pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdip.py::TestDownloadPdipDocument -v`
Expected: FAIL — `ImportError: cannot import name 'download_pdip_document'`

- [ ] **Step 3: Implement `download_pdip_document`**

Add to `src/corpus/sources/pdip.py`:

```python
import hashlib

from corpus.io.safe_write import safe_write

# Add to TYPE_CHECKING block:
# import requests as requests_mod  # for type hints


def download_pdip_document(
    record: dict[str, Any],
    *,
    session: Any,
    output_dir: Path,
) -> tuple[dict[str, Any] | None, str]:
    """Download a single PDIP document.

    Returns (enriched_record, status) where status is one of:
    "success", "skipped_exists", "not_found", "invalid_pdf".
    """
    native_id = record["native_id"]
    target = output_dir / f"pdip__{native_id}.pdf"

    if target.exists():
        return None, "skipped_exists"

    url = PDIP_PDF_URL.format(doc_id=native_id)
    resp = session.get(url, timeout=60)

    if resp.status_code == 404:
        return None, "not_found"

    resp.raise_for_status()
    content = resp.content

    if not content[:5].startswith(b"%PDF"):
        return None, "invalid_pdf"

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched: dict[str, Any] = {
        "source": "pdip",
        "native_id": native_id,
        "storage_key": f"pdip__{native_id}",
        "title": record.get("title", ""),
        "issuer_name": record.get("country", ""),
        "doc_type": record.get("instrument_type", ""),
        "publication_date": None,
        "download_url": url,
        "file_ext": "pdf",
        "file_path": str(target),
        "file_hash": file_hash,
        "file_size_bytes": len(content),
        "source_metadata": {
            "tag_status": record.get("tag_status", ""),
            "country": record.get("country", ""),
            "instrument_type": record.get("instrument_type", ""),
            "creditor_country": record.get("creditor_country"),
            "creditor_type": record.get("creditor_type"),
            "maturity_date": record.get("maturity_date"),
            "maturity_year": record.get("maturity_year"),
        },
    }

    return enriched, "success"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdip.py::TestDownloadPdipDocument -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pdip.py src/corpus/sources/pdip.py
git commit -m "feat(pdip): add single-document download with PDF validation"
```

---

### Task 4: Download Orchestrator

**Files:**
- Modify: `tests/test_pdip.py`
- Modify: `src/corpus/sources/pdip.py`

- [ ] **Step 1: Write failing tests for `run_pdip_download`**

Add to `tests/test_pdip.py`:

```python
class TestRunPdipDownload:
    """Tests for the full download pipeline."""

    def test_reads_discovery_and_downloads(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test Loan",
            "tag_status": "Annotated",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.6\ntest content"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.content = pdf_bytes
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        assert stats["downloaded"] == 1
        assert stats["failed"] == 0
        manifest = tmp_path / "manifests" / "pdip_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(line) for line in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "VEN85"

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        lines = []
        for i in range(15):
            lines.append(
                json.dumps({
                    "native_id": f"FAIL{i}",
                    "source": "pdip",
                    "title": f"Fail {i}",
                    "tag_status": "",
                    "country": "Test",
                    "instrument_type": "",
                    "creditor_country": None,
                    "creditor_type": None,
                    "maturity_date": None,
                    "maturity_year": None,
                    "metadata": {},
                })
            )
        discovery.write_text("\n".join(lines) + "\n")

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("connection refused")
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
                total_failures_abort=5,
            )

        assert stats["aborted"]
        assert stats["failed"] <= 6

    def test_not_found_does_not_count_as_failure(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "MISSING1",
            "source": "pdip",
            "title": "Missing Doc",
            "tag_status": "",
            "country": "Test",
            "instrument_type": "",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            stats = run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        assert stats["failed"] == 0
        assert stats["not_found"] == 1
        assert not stats["aborted"]

    def test_telemetry_logs_download(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.pdip import run_pdip_download

        discovery = tmp_path / "pdip_discovery.jsonl"
        record = {
            "native_id": "VEN85",
            "source": "pdip",
            "title": "Test",
            "tag_status": "",
            "country": "Venezuela",
            "instrument_type": "Loan",
            "creditor_country": None,
            "creditor_type": None,
            "maturity_date": None,
            "maturity_year": None,
            "metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.6\ntest"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.content = pdf_bytes
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.get.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            log_file = tmp_path / "test.jsonl"
            logger = CorpusLogger(log_file, run_id="test-run")

            run_pdip_download(
                discovery_file=discovery,
                output_dir=tmp_path / "original",
                manifest_dir=tmp_path / "manifests",
                logger=logger,
                run_id="test-run",
                delay=0.0,
            )

        log_entries = [json.loads(line) for line in log_file.read_text().strip().split("\n")]
        assert len(log_entries) == 1
        assert log_entries[0]["status"] == "success"
        assert log_entries[0]["document_id"] == "VEN85"
        assert log_entries[0]["step"] == "download"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdip.py::TestRunPdipDownload -v`
Expected: FAIL — `ImportError: cannot import name 'run_pdip_download'`

- [ ] **Step 3: Implement `run_pdip_download`**

Add to `src/corpus/sources/pdip.py`:

```python
def run_pdip_download(
    *,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay: float = 1.0,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Download PDIP documents from a discovery JSONL file.

    Reads discovery results, downloads each PDF, writes pdip_manifest.jsonl.
    """
    import requests

    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "pdip_manifest.jsonl"

    session = requests.Session()
    session.headers.update(PDIP_HEADERS)

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "not_found": 0,
        "failed": 0,
        "total_in_discovery": 0,
        "aborted": False,
    }

    with discovery_file.open() as f:
        records = [json.loads(line) for line in f if line.strip()]

    stats["total_in_discovery"] = len(records)

    for record in records:
        if stats["aborted"]:
            break

        doc_id = record.get("native_id", "unknown")
        _start = time.monotonic()

        try:
            result, dl_status = download_pdip_document(
                record, session=session, output_dir=output_dir
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - _start) * 1000)
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="error",
                error_message=str(exc),
            )
            stats["failed"] += 1
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break
            if delay > 0:
                time.sleep(delay)
            continue

        elapsed_ms = int((time.monotonic() - _start) * 1000)

        if dl_status == "success" and result is not None:
            with manifest_path.open("a") as mf:
                mf.write(json.dumps(result) + "\n")
            stats["downloaded"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="success",
            )
        elif dl_status == "skipped_exists":
            stats["skipped"] += 1
        elif dl_status == "not_found":
            stats["not_found"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="not_found",
            )
        elif dl_status == "invalid_pdf":
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="invalid_pdf",
            )
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break

        if delay > 0:
            time.sleep(delay)

    return stats
```

Add `CorpusLogger` to the `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from pathlib import Path

    from corpus.logging import CorpusLogger
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdip.py::TestRunPdipDownload -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_pdip.py src/corpus/sources/pdip.py
git commit -m "feat(pdip): add download orchestrator with circuit breaker and telemetry"
```

---

### Task 5: CLI Wiring + Config

**Files:**
- Modify: `tests/test_pdip.py`
- Modify: `src/corpus/cli.py`
- Modify: `config.toml`
- Modify: `src/corpus/reporting.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_pdip.py`:

```python
class TestPdipCli:
    """Tests for PDIP CLI commands."""

    def test_discover_pdip_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "pdip", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--output" in result.output

    def test_download_pdip_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "pdip", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--discovery-file" in result.output

    def test_discover_pdip_runs(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        fixture = _load_fixture("pdip_search_response.json")
        output = tmp_path / "discovery.jsonl"

        with patch("corpus.sources.pdip.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = fixture
            mock_resp.raise_for_status = MagicMock()
            mock_session = MagicMock()
            mock_session.post.return_value = mock_resp
            mock_requests.Session.return_value = mock_session

            runner = CliRunner()
            result = runner.invoke(
                cli, ["discover", "pdip", "--output", str(output)]
            )

        assert result.exit_code == 0
        assert "3" in result.output  # total documents
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pdip.py::TestPdipCli -v`
Expected: FAIL — help text doesn't match (placeholder `pdip` command has no options)

- [ ] **Step 3: Add `[pdip.circuit_breaker]` to config.toml**

Add after the existing `[pdip]` section in `config.toml`:

```toml
[pdip.circuit_breaker]
total_failures_abort = 10
```

- [ ] **Step 4: Add `not_found` to non-failure statuses in reporting.py**

In `src/corpus/reporting.py`, change line 79:

```python
_NON_FAILURE_STATUSES = frozenset({"success", "success_after_429", "rate_limited", "not_found"})
```

- [ ] **Step 5: Replace the placeholder `pdip` download command in cli.py**

Replace the existing placeholder `pdip` download command (lines 224-228) with:

```python
@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--discovery-file",
    type=click.Path(exists=True, path_type=Path),
    default="data/pdip_discovery.jsonl",
    help="Path to discovery JSONL from 'corpus discover pdip'.",
)
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
def pdip(
    run_id: str | None,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    log_dir: Path,
) -> None:
    """Download documents from Georgetown PDIP (reads discovery file)."""
    import uuid

    from corpus.logging import CorpusLogger
    from corpus.sources.pdip import run_pdip_download

    cfg = _load_config().get("pdip", {})
    cb_cfg = cfg.get("circuit_breaker", {})

    if run_id is None:
        run_id = f"pdip-{uuid.uuid4().hex[:12]}"

    log_file = log_dir / f"pdip_{run_id}.jsonl"
    logger = CorpusLogger(log_file, run_id=run_id)

    click.echo(f"Starting PDIP download from {discovery_file} (run_id={run_id})...")
    stats = run_pdip_download(
        discovery_file=discovery_file,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id=run_id,
        delay=float(cfg.get("delay", 1.0)),
        total_failures_abort=int(cb_cfg.get("total_failures_abort", 10)),
    )

    from corpus.reporting import write_run_report

    report_path = write_run_report(
        source="pdip",
        run_id=run_id,
        stats=stats,
        telemetry_dir=log_dir,
    )

    click.echo(
        f"PDIP download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['not_found']} not found, "
        f"{stats['failed']} failed "
        f"(of {stats['total_in_discovery']} in discovery)."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
    click.echo(f"Report: {report_path}")
```

- [ ] **Step 6: Add `discover pdip` CLI command**

Add after the `discover_edgar_cmd` function in `cli.py`:

```python
@discover.command("pdip")
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="data/pdip_discovery.jsonl",
    help="Output path for discovery JSONL.",
)
def discover_pdip_cmd(run_id: str | None, output: Path) -> None:
    """Discover sovereign debt documents from Georgetown PDIP (metadata only)."""
    import uuid

    from corpus.sources.pdip import discover_pdip

    cfg = _load_config().get("pdip", {})

    if run_id is None:
        run_id = f"discover-pdip-{uuid.uuid4().hex[:8]}"

    click.echo(f"Discovering PDIP documents (run_id={run_id})...")

    stats = discover_pdip(
        output_path=output,
        delay=float(cfg.get("delay", 1.0)),
    )

    if stats.get("error"):
        click.echo(f"WARNING: Discovery encountered an error: {stats['error']}")

    click.echo(f"Discovery complete: {stats['total_documents']} documents found.")
    click.echo(f"Output: {output}")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_pdip.py::TestPdipCli -v`
Expected: All 3 tests PASS

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest tests/test_pdip.py -v`
Expected: All tests PASS (parsing, discovery, download, orchestrator, CLI)

- [ ] **Step 9: Commit**

```bash
git add src/corpus/cli.py config.toml src/corpus/reporting.py tests/test_pdip.py
git commit -m "feat(pdip): wire CLI commands, config, and reporting integration"
```

---

### Task 6: Lint, Type Check, and Full Test Suite

**Files:**
- Possibly modify: any files with lint/type issues

- [ ] **Step 1: Run ruff check**

Run: `uv run ruff check src/corpus/sources/pdip.py tests/test_pdip.py`
Expected: No errors. Fix any that appear.

- [ ] **Step 2: Run ruff format check**

Run: `uv run ruff format --check src/corpus/sources/pdip.py tests/test_pdip.py`
Expected: No reformatting needed. Run `uv run ruff format src/corpus/sources/pdip.py tests/test_pdip.py` if needed.

- [ ] **Step 3: Run pyright**

Run: `uv run pyright src/corpus/sources/pdip.py`
Expected: No errors. Fix any that appear.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (existing NSM/EDGAR tests + new PDIP tests).

- [ ] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve lint and type issues in PDIP adapter"
```

---

### Task 7: End-to-End Validation

**Files:** None (runtime validation only)

- [ ] **Step 1: Run PDIP discovery against real API**

Run: `uv run corpus discover pdip --output data/pdip_discovery.jsonl`
Expected: Output like "Discovery complete: 823 documents found."

- [ ] **Step 2: Verify discovery JSONL**

Run: `wc -l data/pdip_discovery.jsonl && head -1 data/pdip_discovery.jsonl | python3 -m json.tool`
Expected: 823 lines, first record has `native_id`, `source`, `title`, `country`, etc.

- [ ] **Step 3: Run PDIP download (all documents)**

Run: `uv run corpus download pdip --discovery-file data/pdip_discovery.jsonl`
Expected: Downloads ~823 PDFs to `data/original/pdip__*.pdf`, prints stats.

- [ ] **Step 4: Verify download results**

Run: `ls data/original/pdip__*.pdf | wc -l && uv run corpus status pdip`
Expected: File count matches downloaded count. Status shows discovery vs manifest counts.

- [ ] **Step 5: Check run report**

Run: `cat data/telemetry/pdip_*_report.txt`
Expected: Report shows download stats, any failures with doc IDs and error messages.

- [ ] **Step 6: Commit discovery and any config tweaks**

Only commit if there are code changes needed from the E2E run. Do not commit data files.
