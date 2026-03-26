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
EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{filename}"

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
        {
            "cik": "0000216105",
            "country": "New Zealand",
            "name": "HER MAJESTY THE QUEEN IN RIGHT OF NEW ZEALAND",
        },
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
            cik_int=cik_int,
            acc_nodash=acc_nodash,
            filename=doc,
        )
        ext = doc.rsplit(".", 1)[-1].lower() if "." in doc else "htm"

        filings.append(
            {
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
            }
        )

    return filings


def fetch_submissions(
    client: CorpusHTTPClient,
    *,
    cik: str,
) -> dict[str, Any] | None:
    """Fetch submissions.json for a CIK. Returns None on failure."""
    url = EDGAR_SUBMISSIONS_URL.format(cik=cik)
    try:
        return client.get(url).json()  # type: ignore[no-any-return]
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
                pass

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
    rate_limit_sleep: int = 660,
) -> dict[str, Any]:
    """Download EDGAR filings from a discovery JSONL file.

    Reads discovery results, downloads each document, writes edgar_manifest.jsonl.
    On SEC 429 rate-limit response, sleeps rate_limit_sleep seconds before retrying.
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
                record,
                client=client,
                output_dir=output_dir,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - _start) * 1000)

            # SEC 429 rate-limit: sleep and retry once before counting as failure
            is_429 = hasattr(exc, "response") and getattr(exc.response, "status_code", 0) == 429
            if is_429:
                logger.log(
                    document_id=doc_id,
                    step="download",
                    duration_ms=elapsed_ms,
                    status="rate_limited",
                    error_message=f"SEC 429 — sleeping {rate_limit_sleep}s",
                )
                time.sleep(rate_limit_sleep)
                # Retry once after sleeping
                try:
                    result, dl_status = download_edgar_document(
                        record,
                        client=client,
                        output_dir=output_dir,
                    )
                    if dl_status == "downloaded" and result is not None:
                        retry_ms = int((time.monotonic() - _start) * 1000)
                        with manifest_path.open("a") as mf:
                            mf.write(json.dumps(result) + "\n")
                        stats["downloaded"] += 1
                        logger.log(
                            document_id=doc_id,
                            step="download",
                            duration_ms=retry_ms,
                            status="success_after_429",
                        )
                        if delay > 0:
                            time.sleep(delay)
                        continue
                except Exception:
                    pass  # fall through to normal failure handling

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

        if dl_status == "downloaded" and result is not None:
            with manifest_path.open("a") as mf:
                mf.write(json.dumps(result) + "\n")
            stats["downloaded"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="success",
            )
        elif dl_status.startswith("skipped"):
            stats["skipped"] += 1

        if delay > 0:
            time.sleep(delay)

    return stats
