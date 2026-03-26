# NSM Sovereign Discovery + Download Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the NSM adapter from an unfiltered 5.2M-doc query to a two-phase sovereign-scoped discovery (~1,500 docs) + download pipeline.

**Architecture:** Phase 1 (`corpus discover nsm`) runs ~40 targeted API queries (name patterns + individual LEIs + edge cases), deduplicates by disclosure_id, saves to `data/nsm_discovery.jsonl`. Phase 2 (`corpus download nsm`) reads the discovery file and downloads PDFs. Existing `download_nsm_document`, `resolve_pdf_url`, `parse_hits` are reused.

**Tech Stack:** Python 3.12, Click CLI, requests (via CorpusHTTPClient), csv stdlib

---

## File Structure

```
src/corpus/sources/nsm.py       # Modify: replace unfiltered query with sovereign discovery + download-from-file
tests/test_nsm.py                # Modify: update tests for discovery flow
src/corpus/cli.py                # Modify: add discover group, update download nsm
```

## Existing code kept as-is

- `parse_hits(hits)` — converts API hits to manifest records
- `resolve_pdf_url(url, client)` — two-hop HTML→PDF
- `download_nsm_document(record, client, output_dir)` — single-doc download
- `_load_config()` — config.toml loading
- All constants: `NSM_API_URL`, `NSM_ARTEFACT_BASE`, `PDF_HEADER`

---

### Task 1: Add sovereign query builder

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing tests for build_sovereign_queries**

Append to `tests/test_nsm.py`:
```python
import csv
import io


class TestBuildSovereignQueries:
    """Tests for building sovereign-scoped NSM API queries."""

    def test_includes_name_patterns(self) -> None:
        """Queries include 'Republic of', 'Kingdom of', etc."""
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        labels = [q[0] for q in queries]
        assert "name:Republic of" in labels
        assert "name:Kingdom of" in labels
        assert "name:State of" in labels
        assert "name:Government of" in labels
        assert "name:Sultanate of" in labels
        assert "name:Emirate of" in labels

    def test_includes_edge_cases(self) -> None:
        """Queries include edge case names for Georgia and Chile."""
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        labels = [q[0] for q in queries]
        assert "name:Georgia" in labels
        assert "name:Min of Finance" in labels

    def test_parses_leis_from_csv(self, tmp_path: Path) -> None:
        """Queries include one query per LEI from reference CSV."""
        from corpus.sources.nsm import build_sovereign_queries

        csv_path = tmp_path / "ref.csv"
        csv_path.write_text(
            "country,issuer_types,filing_count,name_variant_count,name_variants,leis,doc_types,earliest,latest\n"
            "Kenya,sovereign,19,1,REPUBLIC OF KENYA,549300VVURQQYU45PR87,,2021-06-29,2026-02-26\n"
            "Uzbekistan,sovereign,63,1,Republic of Uzbekistan,253400TZJ7T1YULTGN68; 213800L6VDKUM3TCM927,,2019-02-04,2025-10-09\n"
        )

        queries = build_sovereign_queries(reference_csv=csv_path)
        labels = [q[0] for q in queries]
        assert "lei:549300VVURQQYU45PR87" in labels
        assert "lei:253400TZJ7T1YULTGN68" in labels
        assert "lei:213800L6VDKUM3TCM927" in labels

    def test_excludes_uk_gilt_lei(self, tmp_path: Path) -> None:
        """UK gilt LEI is excluded from queries."""
        from corpus.sources.nsm import build_sovereign_queries

        csv_path = tmp_path / "ref.csv"
        csv_path.write_text(
            "country,issuer_types,filing_count,name_variant_count,name_variants,leis,doc_types,earliest,latest\n"
            "United Kingdom,uk_sovereign,560,2,HIS MAJESTY'S TREASURY,ECTRVYYCEF89VWYS6K36,Issue of Debt,2023-07-05,2026-03-18\n"
        )

        queries = build_sovereign_queries(reference_csv=csv_path)
        labels = [q[0] for q in queries]
        assert "lei:ECTRVYYCEF89VWYS6K36" not in labels

    def test_query_criteria_format(self) -> None:
        """Each query returns valid NSM API criteria dicts."""
        from corpus.sources.nsm import build_sovereign_queries

        queries = build_sovereign_queries(reference_csv=None)
        for label, criteria in queries:
            assert isinstance(label, str)
            assert isinstance(criteria, list)
            # Every query has latest_flag
            names = [c["name"] for c in criteria]
            assert "latest_flag" in names
            assert "company_lei" in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestBuildSovereignQueries -v`
Expected: FAIL — `ImportError: cannot import name 'build_sovereign_queries'`

- [ ] **Step 3: Implement build_sovereign_queries**

Add to `src/corpus/sources/nsm.py` (after the imports, before `query_nsm_api`):

```python
import csv as csv_mod

# UK gilt LEI — excluded from sovereign queries (Issue of Debt notices, not prospectuses)
_UK_GILT_LEI = "ECTRVYYCEF89VWYS6K36"

_NAME_PATTERNS = [
    "Republic of",
    "Kingdom of",
    "State of",
    "Government of",
    "Sultanate of",
    "Emirate of",
]

_EDGE_CASE_NAMES = [
    "Georgia",
    "Min of Finance",
]


def _lei_criteria(lei: str) -> list[dict[str, Any]]:
    """Build criteria list for a single LEI query."""
    return [
        {"name": "company_lei", "value": ["", lei, "disclose_org", ""]},
        {"name": "latest_flag", "value": "Y"},
    ]


def _name_criteria(name: str) -> list[dict[str, Any]]:
    """Build criteria list for a name pattern query."""
    return [
        {"name": "company_lei", "value": [name, "", "disclose_org", "related_org"]},
        {"name": "latest_flag", "value": "Y"},
    ]


def build_sovereign_queries(
    *, reference_csv: Path | None = None,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Build list of (label, criteria) for sovereign-scoped NSM queries.

    Returns queries for: name patterns, individual LEIs from reference CSV,
    and edge case names. Excludes UK gilt LEI.
    """
    queries: list[tuple[str, list[dict[str, Any]]]] = []

    # A) Name pattern queries
    for pattern in _NAME_PATTERNS:
        queries.append((f"name:{pattern}", _name_criteria(pattern)))

    # B) LEI queries from reference CSV
    if reference_csv is not None and reference_csv.exists():
        with reference_csv.open() as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                lei_str = row.get("leis", "").strip()
                if not lei_str:
                    continue
                for lei in lei_str.split(";"):
                    lei = lei.strip()
                    if len(lei) == 20 and lei.isalnum() and lei != _UK_GILT_LEI:
                        queries.append((f"lei:{lei}", _lei_criteria(lei)))

    # C) Edge case name queries
    for name in _EDGE_CASE_NAMES:
        queries.append((f"name:{name}", _name_criteria(name)))

    return queries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestBuildSovereignQueries -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): add sovereign query builder with name patterns, LEIs, edge cases"
```

---

### Task 2: Refactor query_nsm_api to accept criteria and add discover_nsm

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing tests for updated query_nsm_api and discover_nsm**

Append to `tests/test_nsm.py`:
```python
class TestQueryWithCriteria:
    """Tests for query_nsm_api with custom criteria."""

    def test_query_with_lei_criteria(self) -> None:
        """query_nsm_api passes custom criteria to the API."""
        from corpus.sources.nsm import query_nsm_api, _lei_criteria

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        criteria = _lei_criteria("549300VVURQQYU45PR87")
        hits, total = query_nsm_api(mock_client, criteria=criteria, from_offset=0, size=100)

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        sent_criteria = payload["criteriaObj"]["criteria"]
        names = [c["name"] for c in sent_criteria]
        assert "company_lei" in names
        assert "latest_flag" in names
        assert len(hits) == 2


class TestDiscoverNsm:
    """Tests for the sovereign discovery orchestrator."""

    def test_deduplicates_by_disclosure_id(self, tmp_path: Path) -> None:
        """discover_nsm deduplicates hits across queries by disclosure_id."""
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        # Two queries that return the same hits — should deduplicate
        queries = [
            ("test:q1", [{"name": "latest_flag", "value": "Y"}, {"name": "company_lei", "value": ["test", "", "disclose_org", ""]}]),
            ("test:q2", [{"name": "latest_flag", "value": "Y"}, {"name": "company_lei", "value": ["test2", "", "disclose_org", ""]}]),
        ]

        output = tmp_path / "discovery.jsonl"
        stats = discover_nsm(
            client=mock_client,
            queries=queries,
            output_path=output,
            delay=0.0,
        )

        lines = [json.loads(l) for l in output.read_text().strip().split("\n")]
        assert len(lines) == 2  # 2 unique disclosure_ids, not 4
        assert stats["unique_filings"] == 2
        assert stats["total_hits_raw"] == 4  # 2 queries × 2 hits each
        assert stats["queries_run"] == 2

    def test_writes_discovery_jsonl(self, tmp_path: Path) -> None:
        """discover_nsm writes one line per unique filing to output path."""
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        queries = [("test:q1", [{"name": "latest_flag", "value": "Y"}, {"name": "company_lei", "value": ["test", "", "disclose_org", ""]}])]
        output = tmp_path / "discovery.jsonl"

        discover_nsm(client=mock_client, queries=queries, output_path=output, delay=0.0)

        lines = [json.loads(l) for l in output.read_text().strip().split("\n")]
        assert len(lines) == 2
        # Each line has _source fields
        assert "disclosure_id" in lines[0]
        assert "company" in lines[0]

    def test_logs_per_query_stats(self, tmp_path: Path) -> None:
        """discover_nsm returns per-query hit counts."""
        from corpus.sources.nsm import discover_nsm

        fixture = _load_fixture("nsm_api_response.json")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = fixture
        mock_client.post.return_value = mock_response

        queries = [("test:q1", [{"name": "latest_flag", "value": "Y"}, {"name": "company_lei", "value": ["t", "", "disclose_org", ""]}])]
        output = tmp_path / "discovery.jsonl"

        stats = discover_nsm(client=mock_client, queries=queries, output_path=output, delay=0.0)

        assert len(stats["per_query"]) == 1
        assert stats["per_query"][0]["label"] == "test:q1"
        assert stats["per_query"][0]["hits"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestQueryWithCriteria tests/test_nsm.py::TestDiscoverNsm -v`
Expected: FAIL

- [ ] **Step 3: Update query_nsm_api to accept optional criteria**

Modify `query_nsm_api` in `src/corpus/sources/nsm.py`:

```python
def query_nsm_api(
    client: CorpusHTTPClient,
    *,
    criteria: list[dict[str, Any]] | None = None,
    from_offset: int = 0,
    size: int = 10000,
) -> tuple[list[dict[str, Any]], int]:
    """Query NSM API. Uses provided criteria or defaults to latest_flag=Y only."""
    if criteria is None:
        criteria = [{"name": "latest_flag", "value": "Y"}]

    payload = {
        "from": from_offset,
        "size": size,
        "sort": "submitted_date",
        "sortorder": "desc",
        "criteriaObj": {
            "criteria": criteria,
            "dateCriteria": [],
        },
    }
    resp = client.post(NSM_API_URL, json=payload)
    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    return hits, total
```

- [ ] **Step 4: Implement discover_nsm**

Add to `src/corpus/sources/nsm.py`:

```python
def discover_nsm(
    *,
    client: CorpusHTTPClient,
    queries: list[tuple[str, list[dict[str, Any]]]],
    output_path: Path,
    delay: float = 1.0,
) -> dict[str, Any]:
    """Run sovereign discovery queries, deduplicate, write discovery JSONL.

    Each query is a (label, criteria) tuple. Results are deduplicated by
    disclosure_id. Output file is overwritten (not appended).
    """
    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    total_hits_raw = 0

    for label, criteria in queries:
        hits, _total = query_nsm_api(client, criteria=criteria, size=10000)
        total_hits_raw += len(hits)

        new_count = 0
        for hit in hits:
            src = hit.get("_source", {})
            disc_id = src.get("disclosure_id", hit.get("_id", ""))
            if disc_id and disc_id not in seen_ids:
                seen_ids.add(disc_id)
                all_records.append(src)
                new_count += 1

        per_query.append({"label": label, "hits": len(hits), "new": new_count})

        if delay > 0:
            time.sleep(delay)

    # Write discovery file (overwrite)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    return {
        "queries_run": len(queries),
        "total_hits_raw": total_hits_raw,
        "unique_filings": len(seen_ids),
        "per_query": per_query,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): add discover_nsm orchestrator with dedup and per-query stats"
```

---

### Task 3: Refactor run_nsm_download to read from discovery file

**Files:**
- Modify: `src/corpus/sources/nsm.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing test for download-from-discovery**

Append to `tests/test_nsm.py`:
```python
class TestRunNsmDownloadFromDiscovery:
    """Tests for downloading from a discovery JSONL file."""

    def test_reads_discovery_file_and_downloads(self, tmp_path: Path) -> None:
        """run_nsm_download reads discovery JSONL and downloads each document."""
        from corpus.sources.nsm import run_nsm_download

        # Write a discovery file with one record
        discovery = tmp_path / "discovery.jsonl"
        record = {
            "disclosure_id": "test-doc-001",
            "download_link": "NSM/Portal/test.pdf",
            "company": "REPUBLIC OF TESTLAND",
            "lei": "549300TEST00000000",
            "type_code": "PDI",
            "type": "Publication of a Prospectus",
            "headline": "Test Prospectus",
            "submitted_date": "2024-01-01T00:00:00Z",
            "publication_date": "2024-01-01T00:00:00Z",
            "source": "FCA",
            "seq_id": "test-doc-001",
            "hist_seq": "1",
            "classifications": "",
            "classifications_code": "",
            "tag_esef": "",
            "lei_remediation_flag": "N",
            "last_updated_date": "2024-01-01T00:00:00Z",
        }
        discovery.write_text(json.dumps(record) + "\n")

        pdf_bytes = b"%PDF-1.4 test content"
        mock_client = MagicMock()
        pdf_resp = MagicMock()
        pdf_resp.content = pdf_bytes
        mock_client.get.return_value = pdf_resp

        output_dir = tmp_path / "original"
        manifest_dir = tmp_path / "manifests"
        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=mock_client,
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=manifest_dir,
            logger=logger,
            run_id="test-run",
            delay_download=0.0,
        )

        assert stats["downloaded"] == 1
        manifest = manifest_dir / "nsm_manifest.jsonl"
        assert manifest.exists()
        lines = [json.loads(l) for l in manifest.read_text().strip().split("\n")]
        assert len(lines) == 1
        assert lines[0]["native_id"] == "test-doc-001"

    def test_skips_already_downloaded(self, tmp_path: Path) -> None:
        """Documents already on disk are skipped."""
        from corpus.sources.nsm import run_nsm_download

        discovery = tmp_path / "discovery.jsonl"
        record = {
            "disclosure_id": "existing-doc",
            "download_link": "NSM/Portal/test.pdf",
            "company": "TESTCORP",
            "lei": "",
            "type_code": "PDI",
            "type": "Test",
            "headline": "Existing",
            "submitted_date": "2024-01-01T00:00:00Z",
            "publication_date": "2024-01-01T00:00:00Z",
            "source": "FCA",
            "seq_id": "existing-doc",
            "hist_seq": "1",
            "classifications": "",
            "classifications_code": "",
            "tag_esef": "",
            "lei_remediation_flag": "N",
            "last_updated_date": "2024-01-01T00:00:00Z",
        }
        discovery.write_text(json.dumps(record) + "\n")

        # Pre-create the file
        output_dir = tmp_path / "original"
        output_dir.mkdir(parents=True)
        (output_dir / "nsm__existing-doc.pdf").write_bytes(b"%PDF already here")

        log_file = tmp_path / "test.jsonl"
        logger = CorpusLogger(log_file, run_id="test-run")

        stats = run_nsm_download(
            client=MagicMock(),
            discovery_file=discovery,
            output_dir=output_dir,
            manifest_dir=tmp_path / "manifests",
            logger=logger,
            run_id="test-run",
            delay_download=0.0,
        )

        assert stats["downloaded"] == 0
        assert stats["skipped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestRunNsmDownloadFromDiscovery -v`
Expected: FAIL — `run_nsm_download` doesn't accept `discovery_file`

- [ ] **Step 3: Rewrite run_nsm_download to read from discovery file**

Replace the existing `run_nsm_download` function in `src/corpus/sources/nsm.py`:

```python
def run_nsm_download(
    *,
    client: CorpusHTTPClient,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay_download: float = 1.0,
    total_failures_abort: int = 10,
) -> dict[str, Any]:
    """Download PDFs from a discovery JSONL file.

    Reads discovery results, converts to manifest records via parse_hits,
    downloads each document, writes nsm_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "nsm_manifest.jsonl"

    stats: dict[str, Any] = {
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "total_in_discovery": 0,
        "aborted": False,
    }

    # Read discovery file and convert to manifest records
    with discovery_file.open() as f:
        raw_records = [json.loads(line) for line in f if line.strip()]

    stats["total_in_discovery"] = len(raw_records)

    # Wrap each raw _source record as a fake hit for parse_hits
    hits = [{"_id": r.get("disclosure_id", ""), "_source": r} for r in raw_records]
    records = parse_hits(hits)

    for record in records:
        if stats["aborted"]:
            break

        doc_id = record.get("native_id", "unknown")

        try:
            with logger.timed(doc_id, "download"):
                result, dl_status = download_nsm_document(
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
            result, dl_status = None, "error"

        if dl_status == "downloaded" and result is not None:
            with manifest_path.open("a") as f:
                f.write(json.dumps(result) + "\n")
            stats["downloaded"] += 1
        elif dl_status.startswith("skipped"):
            stats["skipped"] += 1
        else:
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=0,
                status=dl_status,
                error_message=f"Download failed: {dl_status}",
            )

        if stats["failed"] >= total_failures_abort:
            stats["aborted"] = True
            break

        if delay_download > 0:
            time.sleep(delay_download)

    return stats
```

- [ ] **Step 4: Update old TestRunNsmDownload tests**

The old `TestRunNsmDownload` tests used the API-querying flow. Delete the entire `TestRunNsmDownload` class from `tests/test_nsm.py` (the `test_writes_manifest_jsonl` and `test_circuit_breaker_aborts` tests). The new `TestRunNsmDownloadFromDiscovery` replaces them.

Also delete the `TestApiResponseSaving` class — API response saving was for the old unfiltered flow. Discovery doesn't need it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run ruff check src/corpus/sources/nsm.py tests/test_nsm.py && uv run pyright src/corpus/sources/nsm.py`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/corpus/sources/nsm.py tests/test_nsm.py
git commit -m "feat(nsm): rewrite run_nsm_download to read from discovery JSONL"
```

---

### Task 4: Wire CLI — add `discover` group, update `download nsm`

**Files:**
- Modify: `src/corpus/cli.py`
- Modify: `tests/test_nsm.py`

- [ ] **Step 1: Write failing tests for CLI commands**

Append to `tests/test_nsm.py`:
```python
class TestDiscoverNsmCli:
    """Tests for the CLI discover nsm command."""

    def test_discover_nsm_help(self) -> None:
        """corpus discover nsm --help shows options."""
        runner = CliRunner()
        result = runner.invoke(cli, ["discover", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--run-id" in result.output
        assert "--output" in result.output

    def test_discover_nsm_runs(self, tmp_path: Path) -> None:
        """corpus discover nsm runs discovery queries and writes output."""
        runner = CliRunner()
        fixture = _load_fixture("nsm_api_response.json")
        mock_resp = MagicMock()
        mock_resp.json.return_value = fixture
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        output = tmp_path / "discovery.jsonl"

        with patch("corpus.sources.nsm.CorpusHTTPClient") as MockClient:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_resp
            MockClient.return_value = mock_client

            result = runner.invoke(cli, [
                "discover", "nsm",
                "--output", str(output),
            ])

        assert result.exit_code == 0
        assert "unique" in result.output.lower()


class TestDownloadNsmCliUpdated:
    """Tests for the updated CLI download nsm command."""

    def test_download_nsm_help(self) -> None:
        """corpus download nsm --help shows discovery-file option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["download", "nsm", "--help"])
        assert result.exit_code == 0
        assert "--discovery-file" in result.output

    def test_download_nsm_requires_discovery_file(self, tmp_path: Path) -> None:
        """corpus download nsm fails if discovery file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "download", "nsm",
            "--discovery-file", str(tmp_path / "nonexistent.jsonl"),
        ])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py::TestDiscoverNsmCli tests/test_nsm.py::TestDownloadNsmCliUpdated -v`
Expected: FAIL

- [ ] **Step 3: Add discover group and nsm command to CLI**

In `src/corpus/cli.py`, after the download group section, add:

```python
# ── Discover group ─────────────────────────────────────────────────


@cli.group()
def discover() -> None:
    """Discover sovereign filings from sources (metadata only, no downloads)."""


@discover.command("nsm")
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default="data/nsm_discovery.jsonl",
    help="Output path for discovery JSONL.",
)
@click.option(
    "--reference-csv",
    type=click.Path(path_type=Path),
    default="data/raw/sovereign_issuer_reference.csv",
    help="Path to sovereign issuer reference CSV.",
)
def discover_nsm_cmd(run_id: str | None, output: Path, reference_csv: Path) -> None:
    """Discover sovereign filings from FCA NSM (metadata only)."""
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.sources.nsm import build_sovereign_queries, discover_nsm

    cfg = _load_config().get("nsm", {})

    if run_id is None:
        run_id = f"discover-nsm-{uuid.uuid4().hex[:8]}"

    client = CorpusHTTPClient(
        max_retries=int(cfg.get("max_retries", 5)),
        backoff_factor=float(cfg.get("backoff_factor", 0.5)),
        timeout=int(cfg.get("timeout", 60)),
    )

    ref_path = reference_csv if reference_csv.exists() else None
    queries = build_sovereign_queries(reference_csv=ref_path)
    click.echo(f"Running {len(queries)} sovereign discovery queries (run_id={run_id})...")

    stats = discover_nsm(
        client=client,
        queries=queries,
        output_path=output,
        delay=float(cfg.get("delay_api", 1.0)),
    )

    click.echo(f"Discovery complete: {stats['unique_filings']} unique filings from {stats['total_hits_raw']} raw hits.")
    click.echo(f"Output: {output}")
    for pq in stats["per_query"]:
        click.echo(f"  {pq['label']}: {pq['hits']} hits, {pq['new']} new")
```

- [ ] **Step 4: Update download nsm command**

Replace the existing `nsm` download command in `src/corpus/cli.py`:

```python
@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
@click.option(
    "--discovery-file",
    type=click.Path(exists=True, path_type=Path),
    default="data/nsm_discovery.jsonl",
    help="Path to discovery JSONL from 'corpus discover nsm'.",
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
def nsm(
    run_id: str | None,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    log_dir: Path,
) -> None:
    """Download documents from FCA NSM (reads discovery file)."""
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger
    from corpus.sources.nsm import run_nsm_download

    cfg = _load_config().get("nsm", {})
    cb_cfg = cfg.get("circuit_breaker", {})

    if run_id is None:
        run_id = f"nsm-{uuid.uuid4().hex[:12]}"

    client = CorpusHTTPClient(
        max_retries=int(cfg.get("max_retries", 5)),
        backoff_factor=float(cfg.get("backoff_factor", 0.5)),
        timeout=int(cfg.get("timeout", 60)),
    )

    log_file = log_dir / f"nsm_{run_id}.jsonl"
    logger = CorpusLogger(log_file, run_id=run_id)

    click.echo(f"Starting NSM download from {discovery_file} (run_id={run_id})...")
    stats = run_nsm_download(
        client=client,
        discovery_file=discovery_file,
        output_dir=output_dir,
        manifest_dir=manifest_dir,
        logger=logger,
        run_id=run_id,
        delay_download=float(cfg.get("delay_download", 1.0)),
        total_failures_abort=int(cb_cfg.get("total_failures_abort", 10)),
    )

    click.echo(
        f"NSM download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed "
        f"(of {stats['total_in_discovery']} in discovery)."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest tests/test_nsm.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite and linting**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run pytest -v && uv run ruff check src/corpus/ tests/ && uv run pyright src/corpus/`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/corpus/cli.py tests/test_nsm.py
git commit -m "feat(nsm): add discover CLI group, update download nsm to read discovery file"
```

---

### Task 5: Update Makefile and run discovery + download

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Update Makefile targets**

Read the existing Makefile. Add/update targets:

```makefile
discover-nsm:
	uv run corpus discover nsm --run-id $(RUN_ID)

download-nsm:
	uv run corpus download nsm --run-id $(RUN_ID)
```

Replace the old `download-nsm` target if it exists. Add `discover-nsm` before `download-nsm`.

- [ ] **Step 2: Run discovery**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run corpus discover nsm`

This should take a few minutes. Verify:
- Output shows per-query hit counts
- `data/nsm_discovery.jsonl` is created
- Total unique filings is ~1,500-2,000

- [ ] **Step 3: Inspect discovery results**

Run: `wc -l data/nsm_discovery.jsonl` to check total count.
Run: `head -3 data/nsm_discovery.jsonl | python3 -m json.tool` to check format.

- [ ] **Step 4: Start download**

Run: `cd /Users/teal_emery/Dropbox/2026-03_Sovereign-Prospectus-Corpus && uv run corpus download nsm`

This will take hours. Let it run overnight.

- [ ] **Step 5: Commit Makefile**

```bash
git add Makefile
git commit -m "feat(nsm): add discover-nsm and update download-nsm Makefile targets"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `uv run corpus discover nsm --help` shows --run-id, --output, --reference-csv
- [ ] `uv run corpus download nsm --help` shows --discovery-file, --output-dir, --manifest-dir, --log-dir
- [ ] `uv run corpus discover nsm` produces `data/nsm_discovery.jsonl` with ~1,500-2,000 filings
- [ ] `uv run corpus download nsm` reads discovery file and downloads PDFs
- [ ] `uv run pytest -v` — all tests pass
- [ ] `uv run ruff check src/corpus/ tests/` — no errors
- [ ] `uv run pyright src/corpus/` — no errors
- [ ] `make discover-nsm` and `make download-nsm` work
