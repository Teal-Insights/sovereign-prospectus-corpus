# EDGAR Source Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an EDGAR source adapter with two-phase discover/download, following the NSM adapter pattern.

**Architecture:** Query SEC EDGAR submissions API for 27 sovereign CIKs, filter to prospectus form types, download all filings (HTML + PDF) with proper telemetry. Two CLI commands: `corpus discover edgar` and `corpus download edgar`.

**Tech Stack:** Python 3.12, Click CLI, requests (via CorpusHTTPClient), JSONL manifests, config.toml for settings.

**Spec:** `docs/superpowers/specs/2026-03-26-edgar-source-adapter-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/corpus/sources/edgar.py` | EDGAR adapter: CIK list, discovery, download, manifest records |
| Create | `tests/test_edgar.py` | Unit tests with mocked HTTP responses |
| Create | `tests/fixtures/edgar_submissions_response.json` | Fixture: realistic EDGAR submissions API response |
| Modify | `src/corpus/cli.py` | Replace EDGAR stub commands with real implementations |
| Modify | `Makefile` | Add `discover-edgar` target |

---

### Task 1: Create EDGAR Test Fixture

**Files:**
- Create: `tests/fixtures/edgar_submissions_response.json`

This fixture models a real EDGAR submissions API response for a sovereign issuer with a mix of prospectus and non-prospectus filings, plus an older filings page reference.

- [ ] **Step 1: Create the fixture file**

```json
{
  "cik": "0000914021",
  "entityType": "sovereignGovernment",
  "sic": "8888",
  "sicDescription": "Foreign Governments",
  "name": "REPUBLIC OF ARGENTINA",
  "tickers": [],
  "exchanges": [],
  "filings": {
    "recent": {
      "accessionNumber": [
        "0000914021-24-000123",
        "0000914021-23-000456",
        "0000914021-22-000789",
        "0000914021-21-000111",
        "0000914021-20-000222"
      ],
      "filingDate": [
        "2024-06-15",
        "2023-03-20",
        "2022-11-01",
        "2021-08-10",
        "2020-05-05"
      ],
      "form": [
        "424B5",
        "FWP",
        "18-K",
        "424B2",
        "424B5"
      ],
      "primaryDocument": [
        "d12345.htm",
        "d67890.htm",
        "annual-report.htm",
        "d11111.pdf",
        "d22222.htm"
      ],
      "primaryDocDescription": [
        "Prospectus Supplement",
        "Free Writing Prospectus",
        "Annual Report",
        "Prospectus Supplement",
        "Prospectus Supplement"
      ]
    },
    "files": [
      {
        "name": "CIK0000914021-submissions-001.json",
        "filingCount": 50,
        "filingFrom": "2005-01-12",
        "filingTo": "2019-12-31"
      }
    ]
  }
}
```

- [ ] **Step 2: Verify fixture is valid JSON**

Run: `python3 -c "import json; json.load(open('tests/fixtures/edgar_submissions_response.json'))"`
Expected: No error output

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/edgar_submissions_response.json
git commit -m "test: add EDGAR submissions API fixture"
```

---

### Task 2: EDGAR Discovery — Sovereign CIK List and Filing Extraction

**Files:**
- Create: `src/corpus/sources/edgar.py`
- Test: `tests/test_edgar.py`

Build the core discovery logic: sovereign CIK constants, submissions parsing, and filing list building.

- [ ] **Step 1: Write failing tests for CIK list and filing extraction**

Create `tests/test_edgar.py`:

```python
"""Tests for the EDGAR source adapter."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestSovereignCiks:
    """Tests for the sovereign CIK constant list."""

    def test_cik_list_has_all_tiers(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        assert set(SOVEREIGN_CIKS.keys()) == {1, 2, 3, 4}

    def test_cik_entries_have_required_fields(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        for tier, entries in SOVEREIGN_CIKS.items():
            for entry in entries:
                assert "cik" in entry, f"Missing cik in tier {tier}: {entry}"
                assert "country" in entry, f"Missing country in tier {tier}: {entry}"
                assert "name" in entry, f"Missing name in tier {tier}: {entry}"

    def test_total_cik_count(self) -> None:
        from corpus.sources.edgar import SOVEREIGN_CIKS

        total = sum(len(entries) for entries in SOVEREIGN_CIKS.values())
        assert total == 27


class TestBuildFilingList:
    """Tests for extracting prospectus filings from submissions JSON."""

    def test_filters_to_prospectus_forms(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)

        # Fixture has: 424B5, FWP, 18-K, 424B2, 424B5
        # 18-K is NOT a prospectus form, so it should be excluded
        assert len(filings) == 4
        form_types = {f["form_type"] for f in filings}
        assert "18-K" not in form_types
        assert "424B5" in form_types
        assert "FWP" in form_types
        assert "424B2" in form_types

    def test_filing_record_fields(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        f = filings[0]

        assert f["source"] == "edgar"
        assert f["native_id"] == "0000914021-24-000123"
        assert f["storage_key"] == "edgar__0000914021-24-000123"
        assert f["issuer_name"] == "REPUBLIC OF ARGENTINA"
        assert f["doc_type"] == "424B5"
        assert f["publication_date"] == "2024-06-15"
        assert f["title"] == "Prospectus Supplement"
        assert "download_url" in f
        assert "source_metadata" in f

    def test_download_url_construction(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        url = filings[0]["download_url"]

        # URL format: https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{filename}
        assert "sec.gov/Archives/edgar/data/914021/" in url
        assert "000091402124000123" in url
        assert "d12345.htm" in url

    def test_source_metadata_fields(self) -> None:
        from corpus.sources.edgar import build_filing_list

        fixture = _load_fixture("edgar_submissions_response.json")
        filings = build_filing_list(fixture)
        meta = filings[0]["source_metadata"]

        assert meta["cik"] == "0000914021"
        assert meta["accession_number"] == "0000914021-24-000123"
        assert meta["form_type"] == "424B5"
        assert meta["primary_document"] == "d12345.htm"

    def test_empty_submissions(self) -> None:
        from corpus.sources.edgar import build_filing_list

        empty = {
            "cik": "0000000001",
            "name": "EMPTY COUNTRY",
            "filings": {"recent": {"accessionNumber": [], "filingDate": [], "form": [], "primaryDocument": [], "primaryDocDescription": []}, "files": []},
        }
        filings = build_filing_list(empty)
        assert filings == []

    def test_skips_entries_without_accession_or_document(self) -> None:
        from corpus.sources.edgar import build_filing_list

        sparse = {
            "cik": "0000000001",
            "name": "SPARSE COUNTRY",
            "filings": {
                "recent": {
                    "accessionNumber": ["", "0000000001-24-000001"],
                    "filingDate": ["2024-01-01", "2024-01-02"],
                    "form": ["424B5", "424B5"],
                    "primaryDocument": ["doc.htm", ""],
                    "primaryDocDescription": ["Test", "Test"],
                },
                "files": [],
            },
        }
        filings = build_filing_list(sparse)
        assert len(filings) == 0  # both are missing accession or document
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_edgar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus.sources.edgar'`

- [ ] **Step 3: Write the implementation**

Create `src/corpus/sources/edgar.py`:

```python
"""EDGAR source adapter — download documents from SEC EDGAR.

Queries the EDGAR submissions API for sovereign issuers (SIC 8888),
filters to prospectus form types, downloads filings, and writes
edgar_manifest.jsonl for downstream ingest.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from corpus.io.safe_write import safe_write

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_ARCHIVES_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{filename}"
)

PROSPECTUS_FORMS = frozenset({"424B2", "424B5", "424B3", "424B4", "424B1", "FWP"})

SOVEREIGN_CIKS: dict[int, list[dict[str, str]]] = {
    1: [
        {"cik": "0001627521", "country": "Nigeria", "name": "Federal Republic of Nigeria"},
        {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        {"cik": "0000917142", "country": "Colombia", "name": "REPUBLIC OF COLOMBIA"},
        {"cik": "0001719614", "country": "Indonesia", "name": "Republic of Indonesia"},
        {"cik": "0000869687", "country": "Turkey", "name": "REPUBLIC OF TURKEY"},
        {"cik": "0000205317", "country": "Brazil", "name": "FEDERATIVE REPUBLIC OF BRAZIL"},
        {"cik": "0000932419", "country": "South Africa", "name": "REPUBLIC OF SOUTH AFRICA"},
    ],
    2: [
        {"cik": "0000101368", "country": "Mexico", "name": "UNITED MEXICAN STATES"},
        {"cik": "0000019957", "country": "Chile", "name": "REPUBLIC OF CHILE"},
        {"cik": "0000076027", "country": "Panama", "name": "PANAMA REPUBLIC OF"},
        {"cik": "0000077694", "country": "Peru", "name": "PERU REPUBLIC OF"},
        {"cik": "0000102385", "country": "Uruguay", "name": "URUGUAY REPUBLIC OF"},
        {"cik": "0001030717", "country": "Philippines", "name": "REPUBLIC OF THE PHILIPPINES"},
        {"cik": "0001163395", "country": "Jamaica", "name": "GOVERNMENT OF JAMICA"},
        {"cik": "0000053078", "country": "Jamaica", "name": "JAMAICA GOVERNMENT OF"},
        {"cik": "0001179453", "country": "Belize", "name": "GOVERNMENT OF BELIZE"},
    ],
    3: [
        {"cik": "0000873465", "country": "Korea", "name": "REPUBLIC OF KOREA"},
        {"cik": "0000052749", "country": "Israel", "name": "ISRAEL, STATE OF"},
        {"cik": "0000889414", "country": "Hungary", "name": "HUNGARY"},
        {"cik": "0000052782", "country": "Italy", "name": "ITALY REPUBLIC OF"},
    ],
    4: [
        {"cik": "0000931106", "country": "Greece", "name": "HELLENIC REPUBLIC"},
        {"cik": "0000035946", "country": "Finland", "name": "FINLAND REPUBLIC OF"},
        {"cik": "0000225913", "country": "Sweden", "name": "SWEDEN KINGDOM OF"},
        {"cik": "0000230098", "country": "Canada", "name": "CANADA"},
        {"cik": "0000837056", "country": "Japan", "name": "JAPAN"},
        {"cik": "0000216105", "country": "New Zealand", "name": "HER MAJESTY THE QUEEN IN RIGHT OF NEW ZEALAND"},
        {"cik": "0000911076", "country": "Portugal", "name": "REPUBLIC OF PORTUGAL"},
    ],
}


def build_filing_list(
    submissions: dict[str, Any],
    *,
    forms: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Extract prospectus filings from an EDGAR submissions JSON response.

    Returns a list of manifest-shaped records ready for download.
    """
    if forms is None:
        forms = PROSPECTUS_FORMS

    cik = submissions.get("cik", "")
    issuer_name = submissions.get("name", "")
    recent = submissions.get("filings", {}).get("recent", {})

    form_list = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    filings: list[dict[str, Any]] = []
    for i, form in enumerate(form_list):
        if form not in forms:
            continue

        acc = accessions[i] if i < len(accessions) else ""
        doc = primary_docs[i] if i < len(primary_docs) else ""
        desc = descriptions[i] if i < len(descriptions) else ""
        date = dates[i] if i < len(dates) else ""

        if not acc or not doc:
            continue

        cik_int = str(int(cik))
        acc_nodash = acc.replace("-", "")
        download_url = EDGAR_ARCHIVES_URL.format(
            cik_int=cik_int, acc_nodash=acc_nodash, filename=doc,
        )
        ext = doc.rsplit(".", 1)[-1].lower() if "." in doc else "htm"

        filings.append({
            "source": "edgar",
            "native_id": acc,
            "storage_key": f"edgar__{acc}",
            "title": desc or f"{form} - {issuer_name}",
            "issuer_name": issuer_name,
            "doc_type": form,
            "publication_date": date,
            "download_url": download_url,
            "file_ext": ext,
            "source_metadata": {
                "cik": cik,
                "accession_number": acc,
                "form_type": form,
                "primary_document": doc,
            },
        })

    return filings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_edgar.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Run linting**

Run: `uv run ruff check src/corpus/sources/edgar.py tests/test_edgar.py && uv run ruff format --check src/corpus/sources/edgar.py tests/test_edgar.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/edgar.py tests/test_edgar.py
git commit -m "feat(edgar): add sovereign CIK list and filing extraction"
```

---

### Task 3: EDGAR Discovery — Full Discovery Pipeline

**Files:**
- Modify: `src/corpus/sources/edgar.py`
- Test: `tests/test_edgar.py`

Add `fetch_submissions()` and `discover_edgar()` — query the API for each CIK, paginate through older filings, deduplicate, write discovery JSONL.

- [ ] **Step 1: Write failing tests for discovery**

Append to `tests/test_edgar.py`:

```python
class TestFetchSubmissions:
    """Tests for fetching submissions JSON from EDGAR API."""

    def test_fetches_and_returns_json(self) -> None:
        from corpus.sources.edgar import fetch_submissions

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        result = fetch_submissions(mock_client, cik="0000914021")

        assert result is not None
        assert result["name"] == "REPUBLIC OF ARGENTINA"
        mock_client.get.assert_called_once()
        url = mock_client.get.call_args[0][0]
        assert "CIK0000914021" in url

    def test_returns_none_on_error(self) -> None:
        from corpus.sources.edgar import fetch_submissions

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("network error")

        result = fetch_submissions(mock_client, cik="0000914021")
        assert result is None


class TestDiscoverEdgar:
    """Tests for the full discovery pipeline."""

    def test_discovers_filings_for_cik_entries(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 1
        assert stats["total_filings"] == 4  # 4 prospectus forms in fixture
        assert output.exists()
        lines = [json.loads(l) for l in output.read_text().strip().split("\n")]
        assert len(lines) == 4

    def test_deduplicates_across_ciks(self, tmp_path: Path) -> None:
        """Same filing from two CIK queries is deduplicated by native_id."""
        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_client.get.return_value = mock_resp

        # Same CIK twice — should deduplicate
        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 2
        assert stats["total_filings"] == 4  # deduplicated
        lines = [json.loads(l) for l in output.read_text().strip().split("\n")]
        assert len(lines) == 4

    def test_paginates_older_filings(self, tmp_path: Path) -> None:
        """Discovery fetches older filing pages referenced in filings.files."""
        from corpus.sources.edgar import discover_edgar

        fixture = _load_fixture("edgar_submissions_response.json")
        older_page = {
            "accessionNumber": ["0000914021-15-000999"],
            "filingDate": ["2015-06-01"],
            "form": ["424B5"],
            "primaryDocument": ["older.htm"],
            "primaryDocDescription": ["Old Prospectus"],
        }

        mock_client = MagicMock()
        main_resp = MagicMock()
        main_resp.json.return_value = fixture
        older_resp = MagicMock()
        older_resp.json.return_value = older_page
        mock_client.get.side_effect = [main_resp, older_resp]

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["total_filings"] == 5  # 4 from main + 1 from older
        lines = [json.loads(l) for l in output.read_text().strip().split("\n")]
        native_ids = {l["native_id"] for l in lines}
        assert "0000914021-15-000999" in native_ids

    def test_handles_failed_cik(self, tmp_path: Path) -> None:
        """Failed CIK fetch is logged and skipped, not fatal."""
        from corpus.sources.edgar import discover_edgar

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("network error")

        cik_entries = [
            {"cik": "0000914021", "country": "Argentina", "name": "REPUBLIC OF ARGENTINA"},
        ]
        output = tmp_path / "discovery.jsonl"

        stats = discover_edgar(
            client=mock_client,
            cik_entries=cik_entries,
            output_path=output,
            delay=0.0,
        )

        assert stats["ciks_queried"] == 1
        assert stats["ciks_failed"] == 1
        assert stats["total_filings"] == 0
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `uv run pytest tests/test_edgar.py::TestFetchSubmissions -v && uv run pytest tests/test_edgar.py::TestDiscoverEdgar -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_submissions'`

- [ ] **Step 3: Implement fetch_submissions and discover_edgar**

Add to `src/corpus/sources/edgar.py`:

```python
def fetch_submissions(
    client: CorpusHTTPClient,
    *,
    cik: str,
) -> dict[str, Any] | None:
    """Fetch submissions.json for a CIK. Returns None on failure."""
    url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
    try:
        return client.get(url).json()
    except Exception:
        return None


def discover_edgar(
    *,
    client: CorpusHTTPClient,
    cik_entries: list[dict[str, str]],
    output_path: Path,
    delay: float = 0.25,
) -> dict[str, Any]:
    """Query EDGAR submissions API for each CIK, extract prospectus filings.

    Writes discovery JSONL to output_path. Returns stats dict.
    """
    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    ciks_failed = 0

    for entry in cik_entries:
        cik = entry["cik"]
        submissions = fetch_submissions(client, cik=cik)
        if submissions is None:
            ciks_failed += 1
            continue

        # Extract filings from recent submissions
        filings = build_filing_list(submissions)

        # Paginate through older filing pages
        older_files = submissions.get("filings", {}).get("files", [])
        for older_file in older_files:
            older_url = f"https://data.sec.gov/submissions/{older_file['name']}"
            try:
                older_data = client.get(older_url).json()
                older_subs = {
                    "cik": submissions["cik"],
                    "name": submissions.get("name", ""),
                    "filings": {"recent": older_data, "files": []},
                }
                filings.extend(build_filing_list(older_subs))
            except Exception:
                pass  # skip failed older pages, not fatal

            if delay > 0:
                time.sleep(delay)

        # Deduplicate by native_id
        for filing in filings:
            native_id = filing["native_id"]
            if native_id not in seen_ids:
                seen_ids.add(native_id)
                all_records.append(filing)

        if delay > 0:
            time.sleep(delay)

    content = "".join(json.dumps(r) + "\n" for r in all_records).encode()
    safe_write(output_path, content, overwrite=True)

    return {
        "ciks_queried": len(cik_entries),
        "ciks_failed": ciks_failed,
        "total_filings": len(all_records),
    }
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_edgar.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/corpus/sources/edgar.py tests/test_edgar.py && uv run ruff format --check src/corpus/sources/edgar.py tests/test_edgar.py`

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/edgar.py tests/test_edgar.py
git commit -m "feat(edgar): add discovery pipeline with pagination"
```

---

### Task 4: EDGAR Download — Single Document + Full Pipeline

**Files:**
- Modify: `src/corpus/sources/edgar.py`
- Test: `tests/test_edgar.py`

Add `download_edgar_document()` and `run_edgar_download()` with circuit breaker and SEC 429 handling.

- [ ] **Step 1: Write failing tests for download**

Append to `tests/test_edgar.py`:

```python
class TestDownloadEdgarDocument:
    """Tests for single-document download."""

    def test_downloads_and_returns_record(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        html_bytes = b"<html><body>Prospectus content</body></html>"
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = html_bytes
        mock_client.get.return_value = mock_resp

        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000091402124000123/d12345.htm",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=mock_client, output_dir=tmp_path)

        assert status == "downloaded"
        assert result is not None
        assert result["file_path"] == str(tmp_path / "edgar__0000914021-24-000123.htm")
        assert result["file_hash"] == hashlib.sha256(html_bytes).hexdigest()
        assert result["file_size_bytes"] == len(html_bytes)
        assert (tmp_path / "edgar__0000914021-24-000123.htm").exists()

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        target = tmp_path / "edgar__0000914021-24-000123.htm"
        target.write_bytes(b"already here")

        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "download_url": "https://example.com/doc.htm",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_exists"

    def test_skips_no_url(self, tmp_path: Path) -> None:
        from corpus.sources.edgar import download_edgar_document

        record = {
            "source": "edgar",
            "native_id": "no-url",
            "storage_key": "edgar__no-url",
            "download_url": "",
            "file_ext": "htm",
        }

        result, status = download_edgar_document(record, client=MagicMock(), output_dir=tmp_path)
        assert result is None
        assert status == "skipped_no_url"


class TestRunEdgarDownload:
    """Tests for the full download pipeline."""

    def test_reads_discovery_and_downloads(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "source": "edgar",
            "native_id": "0000914021-24-000123",
            "storage_key": "edgar__0000914021-24-000123",
            "title": "Prospectus Supplement",
            "issuer_name": "REPUBLIC OF ARGENTINA",
            "doc_type": "424B5",
            "publication_date": "2024-06-15",
            "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000091402124000123/d12345.htm",
            "file_ext": "htm",
            "source_metadata": {"cik": "0000914021", "accession_number": "0000914021-24-000123", "form_type": "424B5", "primary_document": "d12345.htm"},
        }
        discovery.write_text(json.dumps(record) + "\n")

        html_bytes = b"<html>Prospectus</html>"
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = html_bytes
        mock_client.get.return_value = mock_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_edgar_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay=0.0,
        )

        assert stats["downloaded"] == 1
        manifest = manifest_dir / "edgar_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(l) for l in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "0000914021-24-000123"

    def test_circuit_breaker_aborts(self, tmp_path: Path) -> None:
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        lines = []
        for i in range(15):
            lines.append(json.dumps({
                "source": "edgar",
                "native_id": f"fail-{i:03d}",
                "storage_key": f"edgar__fail-{i:03d}",
                "title": f"Fail {i}",
                "issuer_name": "TEST",
                "doc_type": "424B5",
                "publication_date": "2024-01-01",
                "download_url": f"https://example.com/fail-{i}.htm",
                "file_ext": "htm",
                "source_metadata": {},
            }))
        discovery.write_text("\n".join(lines) + "\n")

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("connection refused")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_edgar_download(
            client=mock_client,
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

    def test_telemetry_logs_failure(self, tmp_path: Path) -> None:
        """Download failures log the actual status, not 'success'."""
        from corpus.logging import CorpusLogger
        from corpus.sources.edgar import run_edgar_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "source": "edgar",
            "native_id": "err-doc",
            "storage_key": "edgar__err-doc",
            "title": "Error Doc",
            "issuer_name": "TEST",
            "doc_type": "424B5",
            "publication_date": "2024-01-01",
            "download_url": "https://example.com/err.htm",
            "file_ext": "htm",
            "source_metadata": {},
        }
        discovery.write_text(json.dumps(record) + "\n")

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("timeout")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        run_edgar_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=tmp_path / "original",
            manifest_dir=tmp_path / "manifests",
            logger=logger,
            run_id="test-run",
            delay=0.0,
        )

        log_entries = [json.loads(l) for l in log_file.read_text().strip().split("\n")]
        assert len(log_entries) == 1
        assert log_entries[0]["status"] == "error"
        assert log_entries[0]["duration_ms"] >= 0
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `uv run pytest tests/test_edgar.py::TestDownloadEdgarDocument -v`
Expected: FAIL — `ImportError: cannot import name 'download_edgar_document'`

- [ ] **Step 3: Implement download functions**

Add to `src/corpus/sources/edgar.py`:

```python
def download_edgar_document(
    record: dict[str, Any],
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
) -> tuple[dict[str, Any] | None, str]:
    """Download a single EDGAR filing.

    Returns (enriched_record, status) where status is one of:
    "downloaded", "skipped_exists", "skipped_no_url".
    """
    storage_key = record.get("storage_key", "")
    ext = record.get("file_ext", "htm")
    target = output_dir / f"{storage_key}.{ext}"

    if target.exists():
        return None, "skipped_exists"

    download_url = record.get("download_url", "")
    if not download_url:
        return None, "skipped_no_url"

    resp = client.get(download_url)
    content = resp.content

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched = dict(record)
    enriched["file_path"] = str(target)
    enriched["file_hash"] = file_hash
    enriched["file_size_bytes"] = len(content)
    return enriched, "downloaded"


def run_edgar_download(
    *,
    client: CorpusHTTPClient,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay: float = 0.25,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Download EDGAR filings from a discovery JSONL file.

    Reads discovery results, downloads each document, writes edgar_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "edgar_manifest.jsonl"

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
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
            result, dl_status = download_edgar_document(
                record, client=client, output_dir=output_dir,
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
            if delay > 0:
                time.sleep(delay)
            continue

        elapsed_ms = int((time.monotonic() - _start) * 1000)

        if dl_status == "downloaded" and result is not None:
            with manifest_path.open("a") as f:
                f.write(json.dumps(result) + "\n")
            stats["downloaded"] += 1
            logger.log(
                document_id=doc_id, step="download", duration_ms=elapsed_ms, status="success",
            )
        elif dl_status.startswith("skipped"):
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status=dl_status,
                error_message=f"Download failed: {dl_status}",
            )
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True

        if delay > 0:
            time.sleep(delay)

    return stats
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_edgar.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/corpus/sources/edgar.py tests/test_edgar.py && uv run ruff format --check src/corpus/sources/edgar.py tests/test_edgar.py`

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/edgar.py tests/test_edgar.py
git commit -m "feat(edgar): add download pipeline with circuit breaker"
```

---

### Task 5: CLI Commands + Makefile

**Files:**
- Modify: `src/corpus/cli.py`
- Modify: `Makefile`
- Test: `tests/test_edgar.py`

Replace the stub EDGAR CLI commands with real implementations and add a Makefile target for discovery.

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_edgar.py`:

```python
class TestEdgarCli:
    """Tests for EDGAR CLI commands."""

    def test_discover_edgar_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "edgar", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--output" in result.output

    def test_download_edgar_help(self) -> None:
        from click.testing import CliRunner

        from corpus.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["download", "edgar", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--discovery-file" in result.output

    def test_discover_edgar_runs(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from click.testing import CliRunner

        from corpus.cli import cli

        fixture = _load_fixture("edgar_submissions_response.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.status_code = 200

        output = tmp_path / "discovery.jsonl"

        with patch("corpus.sources.edgar.fetch_submissions") as mock_fetch:
            mock_fetch.return_value = fixture
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["discover", "edgar", "--output", str(output), "--tiers", "1"],
            )

        assert result.exit_code == 0
        assert "filings" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_edgar.py::TestEdgarCli -v`
Expected: FAIL — help text won't match expected options yet

- [ ] **Step 3: Update CLI with real EDGAR commands**

Replace the EDGAR stubs in `src/corpus/cli.py`. Replace the `edgar` function under the `download` group and add a `discover edgar` command:

Replace the existing `edgar` download stub:

```python
@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--discovery-file",
    type=click.Path(exists=True, path_type=Path),
    default="data/edgar_discovery.jsonl",
    help="Path to discovery JSONL from 'corpus discover edgar'.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="data/original",
    help="Directory for downloaded files.",
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
def edgar(
    run_id: str | None,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    log_dir: Path,
) -> None:
    """Download documents from SEC EDGAR (reads discovery file)."""
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger
    from corpus.sources.edgar import run_edgar_download

    cfg = _load_config().get("edgar", {})
    cb_cfg = cfg.get("circuit_breaker", {})

    if run_id is None:
        run_id = f"edgar-{uuid.uuid4().hex[:12]}"

    contact_email = None
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        contact_email = os.getenv("CONTACT_EMAIL")
    except ImportError:
        pass

    client = CorpusHTTPClient(
        contact_email=contact_email,
        max_retries=int(cfg.get("max_retries", 3)),
        backoff_factor=float(cfg.get("backoff_factor", 0.5)),
        timeout=int(cfg.get("timeout", 60)),
    )

    log_file = log_dir / f"edgar_{run_id}.jsonl"
    logger = CorpusLogger(log_file, run_id=run_id)

    click.echo(f"Starting EDGAR download from {discovery_file} (run_id={run_id})...")
    stats = run_edgar_download(
        client=client,
        discovery_file=discovery_file,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id=run_id,
        delay=float(cfg.get("delay", 0.25)),
        total_failures_abort=int(cb_cfg.get("total_failures_abort", 10)),
    )

    click.echo(
        f"EDGAR download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed "
        f"(of {stats['total_in_discovery']} in discovery)."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
```

Add `discover edgar` command:

```python
@discover.command("edgar")
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="data/edgar_discovery.jsonl",
    help="Output path for discovery JSONL.",
)
@click.option(
    "--tiers",
    default="1,2,3,4",
    help="Comma-separated tier numbers (default: all).",
)
def discover_edgar_cmd(run_id: str | None, output: Path, tiers: str) -> None:
    """Discover sovereign filings from SEC EDGAR (metadata only)."""
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.sources.edgar import SOVEREIGN_CIKS, discover_edgar

    cfg = _load_config().get("edgar", {})

    if run_id is None:
        run_id = f"discover-edgar-{uuid.uuid4().hex[:8]}"

    contact_email = None
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        contact_email = os.getenv("CONTACT_EMAIL")
    except ImportError:
        pass

    client = CorpusHTTPClient(
        contact_email=contact_email,
        max_retries=int(cfg.get("max_retries", 3)),
        backoff_factor=float(cfg.get("backoff_factor", 0.5)),
        timeout=int(cfg.get("timeout", 60)),
    )

    requested_tiers = [int(t.strip()) for t in tiers.split(",")]
    cik_entries: list[dict[str, str]] = []
    for tier in sorted(requested_tiers):
        cik_entries.extend(SOVEREIGN_CIKS.get(tier, []))

    click.echo(
        f"Discovering EDGAR filings for {len(cik_entries)} sovereign CIKs "
        f"(tiers {tiers}, run_id={run_id})..."
    )

    stats = discover_edgar(
        client=client,
        cik_entries=cik_entries,
        output_path=output,
        delay=float(cfg.get("delay", 0.25)),
    )

    click.echo(
        f"Discovery complete: {stats['total_filings']} filings from "
        f"{stats['ciks_queried']} CIKs ({stats['ciks_failed']} failed)."
    )
    click.echo(f"Output: {output}")
```

- [ ] **Step 4: Add discover-edgar Makefile target**

Add to the Makefile `.PHONY` line and targets:

```makefile
discover-edgar: ## Discover sovereign filings from SEC EDGAR (metadata only)
	uv run corpus discover edgar --run-id $(RUN_ID)
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/test_edgar.py -v`
Expected: All tests PASS

- [ ] **Step 6: Lint and type check**

Run: `uv run ruff check src/corpus/sources/edgar.py src/corpus/cli.py tests/test_edgar.py && uv run ruff format --check src/corpus/sources/edgar.py src/corpus/cli.py tests/test_edgar.py && uv run pyright src/corpus/`

- [ ] **Step 7: Commit**

```bash
git add src/corpus/cli.py src/corpus/sources/edgar.py tests/test_edgar.py Makefile
git commit -m "feat(edgar): add CLI commands and Makefile target"
```

---

### Task 6: Full Verification — Lint, Typecheck, All Tests, End-to-End Run

**Files:**
- All files from Tasks 1-5

Run the full verification suite and the actual EDGAR pipeline against SEC's API.

- [ ] **Step 1: Run ruff lint**

Run: `uv run ruff check src/ tests/`
Expected: No errors

- [ ] **Step 2: Run ruff format check**

Run: `uv run ruff format --check src/ tests/`
Expected: No reformatting needed

- [ ] **Step 3: Run pyright**

Run: `uv run pyright src/corpus/`
Expected: No errors

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass (both NSM and EDGAR)

- [ ] **Step 5: Run actual discovery against SEC EDGAR**

Run: `uv run corpus discover edgar --tiers 1 --output data/edgar_discovery.jsonl`
Expected: Discovers filings for tier 1 countries (Nigeria, Argentina, Colombia, Indonesia, Turkey, Brazil, South Africa). Should find hundreds of filings. Check output file exists and has content.

- [ ] **Step 6: Inspect discovery results**

Run: `wc -l data/edgar_discovery.jsonl && head -1 data/edgar_discovery.jsonl | python3 -m json.tool`
Expected: Multiple lines, valid JSON records with expected fields.

- [ ] **Step 7: Run actual download (small test)**

Run: `uv run corpus download edgar --discovery-file data/edgar_discovery.jsonl --run-id edgar-test-001`
Expected: Downloads start, files appear in `data/original/`, manifest written. Let it run for ~50 docs then Ctrl-C if needed — we just need to verify it works.

- [ ] **Step 8: Verify downloaded files and manifest**

Run: `ls data/original/edgar__* | head -10 && wc -l data/manifests/edgar_manifest.jsonl && head -1 data/manifests/edgar_manifest.jsonl | python3 -m json.tool`
Expected: Files exist with `edgar__` prefix, manifest has valid JSON records.

- [ ] **Step 9: Run full discovery for all tiers**

Run: `uv run corpus discover edgar --output data/edgar_discovery.jsonl`
Expected: Discovers filings across all 27 CIKs, all 4 tiers.

- [ ] **Step 10: Run full download**

Run: `uv run corpus download edgar --discovery-file data/edgar_discovery.jsonl`
Expected: Downloads all filings. Based on Phase 0, expect ~3000+ filings. At 4 req/sec this takes ~15 minutes.
