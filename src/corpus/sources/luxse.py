"""LuxSE source adapter — download documents from Luxembourg Stock Exchange.

Queries the LuxSE GraphQL gateway (graphqlaz.luxse.com) for sovereign bond
prospectuses, then downloads PDFs via dl.luxse.com.

Two-phase: discover (GraphQL metadata queries) → download (PDF retrieval).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from corpus.io.manifest import (
    portable_data_path,
    shared_data_root,
    upsert_manifest_records,
)
from corpus.io.safe_write import safe_write

if TYPE_CHECKING:
    from pathlib import Path

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger

GRAPHQL_ENDPOINT = "https://graphqlaz.luxse.com/v1/graphql"
DOWNLOAD_BASE_URL = "https://dl.luxse.com/dl?v="
PDF_HEADER = b"%PDF"

_SOVEREIGN_PATTERNS = [
    "Republic",
    "Kingdom",
    "Government",
    "Sultanate",
    "Emirate",
    "State",
]

_DOCUMENT_QUERY = """\
query LuxseDocSearch($term: String!, $size: Int!, $page: Int!, $issuerId: String) {
  luxseDocumentsSearch(
    searchTerm: $term
    size: $size
    page: $page
    sort: "publishDate"
    issuerId: $issuerId
  ) {
    totalHits
    documents {
      id
      name
      description
      publishDate
      downloadUrl
      documentTypeCode
      documentPublicTypeCode
      categories
      complement
    }
  }
}"""

_ISSUER_QUERY = """\
query LuxseIssuerSearch($term: String!) {
  luxseIssuersSearch(searchTerm: $term, size: 100, page: 0, sort: "name") {
    totalHits
    issuers {
      id
      name
    }
  }
}"""


class LuxseQueryError(RuntimeError):
    """Raised when a targeted LuxSE query remains unresolved after retries."""


def resolve_luxse_issuer_id(
    client: CorpusHTTPClient,
    *,
    issuer_name: str,
    graphql_endpoint: str = GRAPHQL_ENDPOINT,
) -> str:
    """Resolve one exact LuxSE issuer name to its native tier ID."""
    response = client.post(
        graphql_endpoint,
        json={"query": _ISSUER_QUERY, "variables": {"term": issuer_name}},
    )
    data = response.json()
    if data.get("errors"):
        raise LuxseQueryError(f"Issuer lookup failed for {issuer_name!r}")
    result = (data.get("data") or {}).get("luxseIssuersSearch", {})
    exact = [issuer for issuer in result.get("issuers", []) if issuer.get("name") == issuer_name]
    if len(exact) != 1 or not exact[0].get("id"):
        raise LuxseQueryError(
            f"Expected one exact LuxSE issuer for {issuer_name!r}; found {len(exact)}"
        )
    return str(exact[0]["id"])


def _extract_issuer_name(complement: str) -> str:
    """Extract issuer name from the complement field.

    Format: "VENEZUELA (BOLIVARIAN REPUBLIC OF) - XS0029456067 ..."
    """
    if " - " in complement:
        return complement.split(" - ")[0].strip()
    return complement.strip()


def _build_download_url(token: str) -> str:
    """Build the full download URL from a GraphQL download token."""
    return DOWNLOAD_BASE_URL + quote(token, safe="")


def query_luxse_documents(
    client: CorpusHTTPClient,
    *,
    search_term: str,
    page: int = 0,
    size: int = 100,
    issuer_id: str | None = None,
    graphql_endpoint: str = GRAPHQL_ENDPOINT,
) -> tuple[list[dict[str, Any]], int, int, bool]:
    """Return documents, total hits, effective page size, and failure status.

    Some documents have null non-nullable fields (publishDate) which causes
    GraphQL errors. On error, retries with smaller page size to skip bad records.
    """
    for attempt_size in [size, size // 2, size // 4]:
        if attempt_size < 1:
            attempt_size = 1
        payload = {
            "query": _DOCUMENT_QUERY,
            "variables": {
                "term": search_term,
                "size": attempt_size,
                "page": page,
                "issuerId": issuer_id,
            },
        }
        resp = client.post(graphql_endpoint, json=payload)
        data = resp.json()

        if "errors" not in data:
            result = (data.get("data") or {}).get("luxseDocumentsSearch", {})
            documents = result.get("documents", [])
            total_hits = result.get("totalHits", 0)
            return documents, total_hits, attempt_size, False

    logging.getLogger(__name__).warning(
        "GraphQL query failed after retries: term=%r page=%d", search_term, page
    )
    return [], 0, size, True


def discover_luxse(
    *,
    client: CorpusHTTPClient,
    output_path: Path,
    delay: float = 1.0,
    graphql_endpoint: str = GRAPHQL_ENDPOINT,
    page_size: int = 100,
    search_terms: list[str] | None = None,
    exact_issuer_terms: set[str] | None = None,
    fail_on_query_error: bool = False,
) -> dict[str, Any]:
    """Query LuxSE for sovereign documents and write discovery JSONL.

    Returns stats dict with queries_run, total_hits_raw, unique_filings,
    and per_query breakdown.
    """
    seen_ids: set[str] = set()
    all_records: list[dict[str, Any]] = []
    per_query: list[dict[str, Any]] = []
    total_hits_raw = 0
    query_failures = 0
    terms = _SOVEREIGN_PATTERNS if search_terms is None else search_terms
    exact_terms = exact_issuer_terms or set()

    for pattern in terms:
        query_hits = 0
        new_count = 0
        accepted_exact_count = 0
        filtered_issuer_mismatch = 0
        page = 0
        effective_page_size = page_size
        term_failed = False
        issuer_id: str | None = None

        if pattern in exact_terms:
            try:
                issuer_id = resolve_luxse_issuer_id(
                    client,
                    issuer_name=pattern,
                    graphql_endpoint=graphql_endpoint,
                )
            except LuxseQueryError:
                query_failures += 1
                term_failed = True
                if fail_on_query_error:
                    raise

        while not term_failed:
            requested_page = page
            documents, total, returned_page_size, failed = query_luxse_documents(
                client,
                search_term="" if issuer_id else pattern,
                page=page,
                size=effective_page_size,
                issuer_id=issuer_id,
                graphql_endpoint=graphql_endpoint,
            )
            if failed:
                query_failures += 1
                term_failed = True
                if fail_on_query_error:
                    raise LuxseQueryError(
                        f"Unresolved LuxSE query for {pattern!r} page {requested_page}"
                    )
                break

            if returned_page_size != effective_page_size and requested_page > 0:
                # A page-size change alters GraphQL's page offset. Restart this
                # term at page zero and rely on native-ID deduplication.
                effective_page_size = returned_page_size
                page = 0
                continue
            effective_page_size = returned_page_size
            query_hits += len(documents)

            for doc in documents:
                raw_id = doc.get("id", "")
                # Sanitize: LuxSE returns numeric IDs but defend against path traversal
                doc_id = str(raw_id).replace("/", "_").replace("..", "_").replace("\\", "_")
                complement = doc.get("complement") or ""
                issuer_name = _extract_issuer_name(complement)
                if pattern in exact_terms and issuer_name != pattern:
                    filtered_issuer_mismatch += 1
                    continue
                if pattern in exact_terms:
                    accepted_exact_count += 1

                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)

                    download_token = doc.get("downloadUrl") or ""

                    record: dict[str, Any] = {
                        "source": "luxse",
                        "native_id": doc_id,
                        "storage_key": f"luxse__{doc_id}",
                        "title": doc.get("name") or "",
                        "issuer_name": issuer_name,
                        "doc_type": doc.get("documentTypeCode") or "",
                        "publication_date": (doc.get("publishDate") or "")[:10],
                        "download_token": download_token,
                        "download_url": _build_download_url(download_token)
                        if download_token
                        else "",
                        "file_ext": "pdf",
                        "source_metadata": {
                            "complement": complement,
                            "categories": doc.get("categories") or [],
                            "document_type_code": doc.get("documentTypeCode") or "",
                            "document_public_type_code": doc.get("documentPublicTypeCode") or "",
                            "description": doc.get("description") or "",
                            "issuer_id": issuer_id,
                            "issuer_resolution_method": (
                                "exact_issuer_id" if issuer_id else "search_term"
                            ),
                            "queried_issuer_name": pattern,
                        },
                    }
                    all_records.append(record)
                    new_count += 1

            page += 1
            fetched = page * effective_page_size
            if not documents or fetched >= total:
                break
            if delay > 0:
                time.sleep(delay)

        if pattern in exact_terms and not term_failed and accepted_exact_count == 0:
            if fail_on_query_error:
                raise LuxseQueryError(
                    f"LuxSE query for {pattern!r} accepted no exact issuer documents "
                    f"({filtered_issuer_mismatch} issuer mismatch(es))"
                )
            query_failures += 1
            term_failed = True

        total_hits_raw += query_hits
        per_query.append(
            {
                "label": pattern,
                "hits": query_hits,
                "new": new_count,
                "filtered_issuer_mismatch": filtered_issuer_mismatch,
                "query_failures": int(term_failed),
                "effective_page_size": effective_page_size,
                "issuer_id": issuer_id,
            }
        )
        if delay > 0:
            time.sleep(delay)

    content = "".join(json.dumps(r) + "\n" for r in all_records).encode()
    safe_write(output_path, content, overwrite=True)

    return {
        "queries_run": len(terms),
        "total_hits_raw": total_hits_raw,
        "unique_filings": len(seen_ids),
        "query_failures": query_failures,
        "per_query": per_query,
    }


def download_luxse_document(
    record: dict[str, Any],
    *,
    client: CorpusHTTPClient,
    output_dir: Path,
    data_root: Path | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Download a single LuxSE document.

    Returns (enriched_record, status) where status is one of:
    "downloaded", "skipped_exists", "skipped_no_url", "failed_invalid_pdf",
    "failed_http".
    """
    storage_key = record.get("storage_key", "")
    target = output_dir / f"{storage_key}.pdf"

    if target.exists():
        import fitz

        content = target.read_bytes()
        if not content.startswith(PDF_HEADER):
            return None, "failed_invalid_pdf"
        try:
            document = fitz.open(target)
            page_count = document.page_count
            document.close()
        except Exception:
            return None, "failed_invalid_pdf"
        if page_count <= 0:
            return None, "failed_invalid_pdf"
        enriched = dict(record)
        enriched["file_path"] = portable_data_path(target, data_root=data_root)
        enriched["file_hash"] = hashlib.sha256(content).hexdigest()
        enriched["file_size_bytes"] = len(content)
        return enriched, "skipped_exists"

    download_url = record.get("download_url", "")
    if not download_url:
        return None, "skipped_no_url"

    resp = client.get(download_url)

    # Rate limit: 429, or 302 → 200 HTML page at /download-limit-reached
    if resp.status_code == 429 or "download-limit-reached" in resp.url.lower():
        return None, "rate_limited"

    if resp.status_code != 200:
        return None, "failed_http"

    content = resp.content
    if not content.startswith(PDF_HEADER):
        return None, "failed_invalid_pdf"

    import fitz

    try:
        document = fitz.open(stream=content, filetype="pdf")
        page_count = document.page_count
        document.close()
    except Exception:
        return None, "failed_invalid_pdf"
    if page_count <= 0:
        return None, "failed_invalid_pdf"

    safe_write(target, content)
    file_hash = hashlib.sha256(content).hexdigest()

    enriched = dict(record)
    enriched["file_path"] = portable_data_path(target, data_root=data_root)
    enriched["file_hash"] = file_hash
    enriched["file_size_bytes"] = len(content)
    return enriched, "downloaded"


def run_luxse_download(
    *,
    client: CorpusHTTPClient,
    discovery_file: Path,
    output_dir: Path,
    manifest_dir: Path,
    logger: CorpusLogger,
    run_id: str,
    delay: float = 1.0,
    total_failures_abort: int = 10,
    rate_limit_sleep: int = 60,
) -> dict[str, Any]:
    """Download PDFs from a discovery JSONL file.

    Reads discovery results, downloads each document, writes
    luxse_manifest.jsonl.
    """
    manifest_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "luxse_manifest.jsonl"
    data_root = shared_data_root(output_dir, manifest_dir)
    manifest_records: list[dict[str, Any]] = []

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
            result, dl_status = download_luxse_document(
                record, client=client, output_dir=output_dir, data_root=data_root
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
            result, dl_status = None, "failed_exception"
        else:
            elapsed_ms = int((time.monotonic() - _start) * 1000)

        if dl_status == "downloaded" and result is not None:
            manifest_records.append(result)
            stats["downloaded"] += 1
            logger.log(
                document_id=doc_id, step="download", duration_ms=elapsed_ms, status="success"
            )
        elif dl_status == "rate_limited":
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="failed_rate_limited",
                error_message="LuxSE rate limit reached",
            )
            if rate_limit_sleep > 0:
                time.sleep(rate_limit_sleep)
            if stats["failed"] >= total_failures_abort:
                stats["aborted"] = True
                break
            continue
        elif dl_status == "skipped_exists" and result is not None:
            manifest_records.append(result)
            stats["skipped"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status="skipped_exists",
            )
        elif dl_status == "skipped_no_url":
            stats["failed"] += 1
            logger.log(
                document_id=doc_id,
                step="download",
                duration_ms=elapsed_ms,
                status=dl_status,
                error_message="LuxSE discovery record has no download URL",
            )
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
            break

        if delay > 0:
            time.sleep(delay)

    upsert_manifest_records(manifest_path, manifest_records)
    return stats
