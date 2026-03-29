"""Click CLI entry point for the sovereign prospectus corpus pipeline.

Groups: discover, download, parse, grep, extract.
Commands: ingest.

Entry point registered in pyproject.toml as ``corpus = "corpus.cli:main"``.
"""

from __future__ import annotations

from pathlib import Path

import click

import corpus
from corpus.db.ingest import ingest_manifests
from corpus.extraction.country import guess_country as _guess_country

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_config() -> dict:
    """Load config.toml from the project root. Returns empty dict if missing."""
    import tomllib

    # Try CWD first, then resolve relative to the package location
    for candidate in [
        Path("config.toml"),
        _PROJECT_ROOT / "config.toml",
    ]:
        if candidate.exists():
            with candidate.open("rb") as f:
                return tomllib.load(f)
    return {}


def _resolve_path(config: dict, section: str, key: str, default: str) -> Path:
    """Resolve a config path relative to the project root."""
    raw = config.get(section, {}).get(key, default)
    p = Path(raw)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


@click.group()
@click.version_option(version=corpus.__version__, prog_name="corpus")
def cli() -> None:
    """Sovereign bond prospectus corpus pipeline."""


# ── Download group ──────────────────────────────────────────────────


@cli.group()
def download() -> None:
    """Download prospectuses from sources (nsm, edgar, pdip)."""


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

    from corpus.reporting import write_run_report

    report_path = write_run_report(
        source="nsm",
        run_id=run_id,
        stats=stats,
        telemetry_dir=log_dir,
    )

    click.echo(
        f"NSM download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['skipped_no_pdf']} html-only, "
        f"{stats['failed']} failed "
        f"(of {stats['total_in_discovery']} in discovery)."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
    click.echo(f"Report: {report_path}")


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
    import os
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.logging import CorpusLogger
    from corpus.sources.edgar import run_edgar_download

    cfg = _load_config().get("edgar", {})
    cb_cfg = cfg.get("circuit_breaker", {})

    if run_id is None:
        run_id = f"edgar-{uuid.uuid4().hex[:12]}"

    client = CorpusHTTPClient(
        contact_email=os.environ.get("CONTACT_EMAIL"),
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
        rate_limit_sleep=int(cb_cfg.get("rate_limit_sleep_seconds", 660)),
    )

    from corpus.reporting import write_run_report

    report_path = write_run_report(
        source="edgar",
        run_id=run_id,
        stats=stats,
        telemetry_dir=log_dir,
    )

    click.echo(
        f"EDGAR download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed "
        f"(of {stats['total_in_discovery']} in discovery)."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")
    click.echo(f"Report: {report_path}")


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
        max_retries=int(cfg.get("max_retries", 3)),
        timeout=int(cfg.get("timeout", 60)),
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
        click.echo("ERROR: Download aborted due to too many failures.", err=True)
    click.echo(f"Report: {report_path}")
    if stats["aborted"]:
        raise SystemExit(1)


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

    click.echo(
        f"Discovery complete: {stats['unique_filings']} unique filings from {stats['total_hits_raw']} raw hits."
    )
    click.echo(f"Output: {output}")
    for pq in stats["per_query"]:
        click.echo(f"  {pq['label']}: {pq['hits']} hits, {pq['new']} new")


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
    import os
    import uuid

    from corpus.io.http import CorpusHTTPClient
    from corpus.sources.edgar import SOVEREIGN_CIKS, discover_edgar

    cfg = _load_config().get("edgar", {})

    if run_id is None:
        run_id = f"discover-edgar-{uuid.uuid4().hex[:8]}"

    client = CorpusHTTPClient(
        contact_email=os.environ.get("CONTACT_EMAIL"),
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
        max_retries=int(cfg.get("max_retries", 3)),
        timeout=int(cfg.get("timeout", 60)),
    )

    if stats.get("error"):
        click.echo(f"ERROR: Discovery failed: {stats['error']}", err=True)
        if stats["total_documents"] == 0:
            raise SystemExit(1)

    click.echo(f"Discovery complete: {stats['total_documents']} documents found.")
    click.echo(f"Output: {output}")


# ── Scrape group ───────────────────────────────────────────────────


@cli.group()
def scrape() -> None:
    """Scrape structured data from source APIs (pdip-annotations)."""


@scrape.command("pdip-annotations")
@click.option("--run-id", required=True, help="Pipeline run identifier.")
@click.option(
    "--inventory-file",
    type=click.Path(exists=True, path_type=Path),
    default="data/pdip/pdip_document_inventory.csv",
    help="Path to PDIP document inventory CSV.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="/var/tmp/pdip_annotations",
    help="Output directory for run artifacts.",
)
@click.option("--limit", type=int, default=None, help="Max documents to process.")
@click.option(
    "--doc-id",
    "doc_ids",
    multiple=True,
    help="Specific doc IDs to process (repeatable).",
)
@click.option("--annotated-only/--all", default=True, help="Filter to annotated docs.")
@click.option(
    "--insecure",
    is_flag=True,
    default=False,
    help="Skip TLS verification (emergency override).",
)
def scrape_pdip_annotations(
    run_id: str,
    inventory_file: Path,
    output_dir: Path,
    limit: int | None,
    doc_ids: tuple[str, ...],
    annotated_only: bool,
    insecure: bool,
) -> None:
    """Harvest PDIP clause annotations from /api/details."""
    from corpus.sources.pdip_annotations import run_annotations_harvest

    cfg = _load_config().get("pdip_annotations", {})
    cb_cfg = cfg.get("circuit_breaker", {})
    zc_cfg = cfg.get("zero_clause_gate", {})

    # Resolve output dir with run_id
    run_output = output_dir / run_id

    click.echo(f"PDIP annotations harvest (run_id={run_id})")
    click.echo(f"  inventory: {inventory_file}")
    click.echo(f"  output:    {run_output}")
    if insecure:
        click.echo("  WARNING: TLS verification disabled (--insecure)")
    if doc_ids:
        click.echo(f"  doc_ids:   {', '.join(doc_ids)}")
    if limit:
        click.echo(f"  limit:     {limit}")

    try:
        summary = run_annotations_harvest(
            inventory_path=inventory_file,
            output_dir=run_output,
            run_id=run_id,
            annotated_only=annotated_only,
            doc_ids=list(doc_ids) if doc_ids else None,
            limit=limit,
            insecure=insecure,
            timeout=int(cfg.get("timeout", 60)),
            max_retries=int(cfg.get("max_retries", 3)),
            delay=float(cfg.get("delay", 1.0)),
            consecutive_failures_pause=int(cb_cfg.get("consecutive_failures_pause", 3)),
            consecutive_failures_abort=int(cb_cfg.get("consecutive_failures_abort", 8)),
            zero_clause_early_abort_count=int(zc_cfg.get("early_abort_count", 10)),
            zero_clause_early_abort_window=int(zc_cfg.get("early_abort_window", 20)),
            zero_clause_rate_threshold=float(zc_cfg.get("rate_threshold", 0.40)),
            zero_clause_rate_min_docs=int(zc_cfg.get("rate_min_docs", 50)),
        )
    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"ERROR: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo("")
    click.echo("── Results ──")
    click.echo(f"  selected:   {summary['selected_total']}")
    click.echo(f"  attempted:  {summary['new_attempted']}")
    click.echo(f"  resumed:    {summary['skipped_via_resume']}")
    click.echo(f"  terminal:   {summary['terminal_total']}")
    click.echo(f"  statuses:   {summary['status_counts']}")
    click.echo(f"  CAC candidates: {summary['cac_candidate_count']}")
    click.echo(f"  zero-clause:    {summary['zero_clause_on_annotated_count']}")
    click.echo(f"  summary:    {run_output / 'summary.json'}")

    if summary.get("aborted"):
        click.echo(f"\nABORTED: {summary.get('abort_reason', 'unknown')}", err=True)
        raise SystemExit(1)


# ── Parse group ─────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def parse(ctx: click.Context) -> None:
    """Parse downloaded PDFs into text."""
    if ctx.invoked_subcommand is None:
        click.echo("Parse not yet implemented. Use --help for subcommands.")


@parse.command("run")
@click.option("--run-id", required=True, help="Unique run identifier.")
@click.option(
    "--source",
    type=click.Choice(["nsm", "edgar", "pdip", "all"]),
    default="all",
    help="Which source to parse.",
)
@click.option("--limit", type=int, default=None, help="Max documents to parse.")
def parse_run(run_id: str, source: str, limit: int | None) -> None:
    """Parse downloaded documents into per-page text JSONL."""
    import json as _json
    import time
    from datetime import UTC, datetime

    from corpus.logging import CorpusLogger
    from corpus.parsers.html_parser import HTMLParser
    from corpus.parsers.pymupdf_parser import PyMuPDFParser
    from corpus.parsers.text_parser import PlainTextParser

    config = _load_config()
    text_dir = _resolve_path(config, "paths", "parsed_dir", "data/parsed")
    text_dir.mkdir(parents=True, exist_ok=True)

    log_path = _resolve_path(config, "paths", "telemetry_dir", "data/telemetry") / "parse.jsonl"
    logger = CorpusLogger(log_path, run_id=run_id)

    parsers = {
        ".pdf": PyMuPDFParser(),
        ".txt": PlainTextParser(),
        ".htm": HTMLParser(),
        ".html": HTMLParser(),
    }

    # Collect files to parse from manifests
    manifest_dir = _resolve_path(config, "paths", "manifests_dir", "data/manifests")
    files_to_parse: list[tuple[str, Path]] = []

    for manifest_path in sorted(manifest_dir.glob("*_manifest.jsonl")):
        source_name = manifest_path.stem.replace("_manifest", "")
        if source != "all" and source_name != source:
            continue
        with manifest_path.open() as f:
            for line in f:
                record = _json.loads(line)
                storage_key = record.get("storage_key", "")
                file_path = record.get("file_path")
                if file_path:
                    p = Path(file_path)
                    if not p.is_absolute():
                        p = _PROJECT_ROOT / p
                    files_to_parse.append((storage_key, p))

    # Also check legacy PDIP path
    if source in ("pdip", "all"):
        pdip_pdf_dir = _PROJECT_ROOT / "data/pdfs/pdip"
        if pdip_pdf_dir.exists():
            seen_keys = {sk for sk, _ in files_to_parse}
            for pdf_path in pdip_pdf_dir.rglob("*.pdf"):
                storage_key = f"pdip__{pdf_path.stem}"
                if storage_key not in seen_keys:
                    files_to_parse.append((storage_key, pdf_path))
                    seen_keys.add(storage_key)

    if limit:
        files_to_parse = files_to_parse[:limit]

    click.echo(f"Parsing {len(files_to_parse)} documents...")

    parsed = 0
    skipped = 0
    failed = 0

    for storage_key, file_path in files_to_parse:
        output_path = text_dir / f"{storage_key}.jsonl"

        # Idempotent: skip if already parsed
        if output_path.exists():
            skipped += 1
            continue

        if not file_path.exists():
            logger.log(
                document_id=storage_key,
                step="parse",
                duration_ms=0,
                status="file_not_found",
            )
            failed += 1
            continue

        suffix = file_path.suffix.lower()
        parser = parsers.get(suffix)
        if parser is None:
            logger.log(
                document_id=storage_key,
                step="parse",
                duration_ms=0,
                status="unsupported_format",
                file_ext=suffix,
            )
            failed += 1
            continue

        start = time.monotonic()
        try:
            result = parser.parse(file_path)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            # Determine quality status
            total_chars = sum(len(p.strip()) for p in result.pages)
            if result.page_count == 0 or total_chars == 0:
                parse_status = "parse_empty"
            else:
                empty_pages = sum(1 for p in result.pages if len(p.strip()) < 50)
                if empty_pages == result.page_count:
                    parse_status = "parse_empty"
                elif empty_pages > result.page_count / 2:
                    parse_status = "parse_partial"
                else:
                    parse_status = "parse_ok"

            # Write output JSONL (atomic: .part → rename)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            part_path = output_path.with_suffix(".jsonl.part")
            with part_path.open("w") as out:
                header = {
                    "storage_key": storage_key,
                    "page_count": result.page_count,
                    "parse_tool": result.parse_tool,
                    "parse_version": result.parse_version,
                    "parse_status": parse_status,
                    "parsed_at": datetime.now(UTC).isoformat(),
                }
                out.write(_json.dumps(header) + "\n")
                for i, page_text in enumerate(result.pages):
                    page_record = {
                        "page": i,
                        "text": page_text,
                        "char_count": len(page_text),
                    }
                    out.write(_json.dumps(page_record) + "\n")
            part_path.rename(output_path)

            logger.log(
                document_id=storage_key,
                step="parse",
                duration_ms=elapsed_ms,
                status=parse_status,
                page_count=result.page_count,
                file_ext=suffix,
            )
            parsed += 1

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.log(
                document_id=storage_key,
                step="parse",
                duration_ms=elapsed_ms,
                status="parse_failed",
                error_message=str(exc),
                file_ext=suffix,
            )
            failed += 1

    click.echo(f"Done. Parsed: {parsed}, Skipped: {skipped}, Failed: {failed}")


# ── Grep group ──────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def grep(ctx: click.Context) -> None:
    """Run grep-first pattern matching on parsed text."""
    if ctx.invoked_subcommand is None:
        click.echo("Grep not yet implemented. Use --help for subcommands.")


@grep.command("doc")
@click.option("--pattern", "pattern_name", required=True, help="Pattern name to search for.")
@click.option("--doc", "doc_id", required=True, help="Document ID (storage_key).")
@click.option("--verbose", is_flag=True, help="Show full context around matches.")
def grep_doc(pattern_name: str, doc_id: str, verbose: bool) -> None:
    """Search a single document with a pattern (dev mode)."""
    import json as _json

    from corpus.extraction.clause_patterns import CLAUSE_PATTERNS, FEATURE_PATTERNS
    from corpus.extraction.grep_runner import grep_document

    all_patterns = {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}
    if pattern_name not in all_patterns:
        click.echo(f"Unknown pattern: {pattern_name}", err=True)
        click.echo(f"Available: {', '.join(sorted(all_patterns.keys()))}", err=True)
        raise SystemExit(1)

    pattern = all_patterns[pattern_name]

    # Find parsed text file
    config = _load_config()
    text_dir = _resolve_path(config, "paths", "parsed_dir", "data/parsed")
    text_path = (text_dir / f"{doc_id}.jsonl").resolve()
    if not text_path.is_relative_to(text_dir.resolve()):
        click.echo(f"Invalid document ID: {doc_id}", err=True)
        raise SystemExit(1)
    if not text_path.exists():
        click.echo(f"Parsed text not found: {text_path}", err=True)
        raise SystemExit(1)

    # Load pages from JSONL
    pages: list[str] = []
    with text_path.open() as f:
        for line in f:
            record = _json.loads(line)
            if "page" in record:  # skip header line
                pages.append(record["text"])

    matches = grep_document(
        pages=pages,
        patterns=[pattern],
        document_id=doc_id,
        run_id="dev",
    )

    if not matches:
        click.echo(f"No matches for '{pattern_name}' in {doc_id}")
        return

    click.echo(f"Found {len(matches)} match(es) for '{pattern_name}' in {doc_id}:\n")
    for i, m in enumerate(matches, 1):
        page_display = m.page_index + 1  # 1-indexed for display
        click.echo(f"--- Match {i} (page {page_display}) ---")
        if verbose:
            click.secho(f"  ...{m.context_before[-200:]}", dim=True)
        click.secho(f"  >>> {m.matched_text}", fg="green", bold=True)
        if verbose:
            click.secho(f"  {m.context_after[:200]}...", dim=True)
        click.echo()


@grep.command("run")
@click.option("--run-id", required=True, help="Unique run identifier.")
@click.option(
    "--pattern", "pattern_names", multiple=True, help="Specific pattern(s) to run. Omit for all."
)
@click.option("--source", type=click.Choice(["nsm", "edgar", "pdip", "all"]), default="all")
@click.option("--limit", type=int, default=None, help="Max documents to process.")
def grep_run(run_id: str, pattern_names: tuple[str, ...], source: str, limit: int | None) -> None:
    """Run patterns across all parsed documents, write to DuckDB."""
    import json as _json
    import time

    import duckdb

    from corpus.extraction.clause_patterns import (
        CLAUSE_PATTERNS,
        FEATURE_PATTERNS,
        get_all_patterns,
    )
    from corpus.extraction.grep_runner import grep_document
    from corpus.logging import CorpusLogger

    config = _load_config()
    text_dir = _resolve_path(config, "paths", "parsed_dir", "data/parsed")
    db_path = _resolve_path(config, "paths", "db_path", "data/db/corpus.duckdb")
    log_path = _resolve_path(config, "paths", "telemetry_dir", "data/telemetry") / "grep.jsonl"
    logger = CorpusLogger(log_path, run_id=run_id)

    # Select patterns
    all_registered = {**CLAUSE_PATTERNS, **FEATURE_PATTERNS}
    if pattern_names:
        patterns = [all_registered[n] for n in pattern_names if n in all_registered]
    else:
        patterns = get_all_patterns()

    if not patterns:
        click.echo("No patterns selected.", err=True)
        raise SystemExit(1)

    click.echo(f"Running {len(patterns)} pattern(s) across parsed documents...")

    # Collect parsed text files
    text_files = sorted(text_dir.glob("*.jsonl"))
    if source != "all":
        text_files = [f for f in text_files if f.stem.startswith(f"{source}__")]
    if limit:
        text_files = text_files[:limit]

    con = duckdb.connect(str(db_path))

    # Ensure schema is up to date
    with (_PROJECT_ROOT / "sql/001_corpus.sql").open() as _f:
        con.execute(_f.read())

    # Delete only results from THIS run_id + selected patterns + selected
    # source (idempotent partial re-run). Prior runs are preserved.
    pattern_name_list = [p.name for p in patterns]
    placeholders = ", ".join("?" for _ in pattern_name_list)
    if source == "all":
        con.execute(
            f"DELETE FROM grep_matches WHERE run_id = ? AND pattern_name IN ({placeholders})",
            [run_id, *pattern_name_list],
        )
    else:
        con.execute(
            f"""DELETE FROM grep_matches
                WHERE run_id = ?
                  AND pattern_name IN ({placeholders})
                  AND document_id IN (
                      SELECT document_id FROM documents WHERE source = ?
                  )""",
            [run_id, *pattern_name_list, source],
        )

    # Prefetch storage_key -> document_id mapping
    doc_id_map: dict[str, int] = {}
    for row in con.execute("SELECT storage_key, document_id FROM documents").fetchall():
        doc_id_map[row[0]] = row[1]

    total_matches = 0
    docs_with_matches = 0

    for text_path in text_files:
        doc_id = text_path.stem

        # Load pages
        pages: list[str] = []
        with text_path.open() as f:
            for line in f:
                record = _json.loads(line)
                if "page" in record:
                    pages.append(record["text"])

        if not pages:
            continue

        start = time.monotonic()
        matches = grep_document(
            pages=pages,
            patterns=patterns,
            document_id=doc_id,
            run_id=run_id,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if matches:
            document_id = doc_id_map.get(doc_id)
            if document_id is None:
                logger.log(
                    document_id=doc_id,
                    step="grep",
                    duration_ms=elapsed_ms,
                    status="skipped_no_document",
                    match_count=len(matches),
                )
                continue

            docs_with_matches += 1
            for m in matches:
                con.execute(
                    """INSERT INTO grep_matches
                       (document_id, pattern_name, pattern_version,
                        page_number, matched_text, context_before,
                        context_after, run_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        document_id,
                        m.pattern_name,
                        m.pattern_version,
                        m.page_index + 1,  # Store 1-indexed in DB
                        m.matched_text,
                        m.context_before,
                        m.context_after,
                        m.run_id,
                    ],
                )
            total_matches += len(matches)

        logger.log(
            document_id=doc_id,
            step="grep",
            duration_ms=elapsed_ms,
            status="success",
            match_count=len(matches),
        )

    con.commit()
    con.close()

    click.echo(
        f"Done. {total_matches} matches across {docs_with_matches} documents "
        f"(of {len(text_files)} scanned)."
    )


# ── Extract group ───────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def extract(ctx: click.Context) -> None:
    """Extract structured clause data from grep matches."""
    if ctx.invoked_subcommand is None:
        click.echo("Use --help for subcommands.")


@extract.command("pdip")
@click.option("--run-id", required=True, help="Unique run identifier.")
def extract_pdip(run_id: str) -> None:
    """Extract PDIP clause annotations → JSONL + DuckDB."""
    import json as _json

    import duckdb

    from corpus.extraction.pdip_clause_extractor import process_raw_files

    config = _load_config()
    raw_dir = _resolve_path(config, "paths", "pdip_raw_dir", "data/pdip/annotations/raw")
    output_path = _resolve_path(
        config, "paths", "pdip_clauses_jsonl", "data/pdip/clause_annotations.jsonl"
    )
    db_path = _resolve_path(config, "paths", "db_path", "data/db/corpus.duckdb")

    if not raw_dir.exists():
        click.echo(f"Raw PDIP annotations not found: {raw_dir}", err=True)
        raise SystemExit(1)

    click.echo(f"Extracting clauses from {raw_dir}...")
    summary = process_raw_files(raw_dir=raw_dir, output_path=output_path)

    click.echo(
        f"Extracted {summary['total_clauses']} clauses from "
        f"{summary['documents_processed']} documents "
        f"({summary['clauses_with_text']} with text, "
        f"{summary['zero_clause_documents']} zero-clause docs)"
    )

    if summary["unmapped_labels"]:
        click.echo(f"Unmapped labels: {len(summary['unmapped_labels'])}")

    # Ingest into DuckDB
    click.echo("Loading into DuckDB...")
    con = duckdb.connect(str(db_path))
    with (_PROJECT_ROOT / "sql/001_corpus.sql").open() as _f:
        con.execute(_f.read())

    con.execute("DELETE FROM pdip_clauses")

    with output_path.open() as f:
        for line in f:
            r = _json.loads(line)
            storage_key = f"pdip__{r['doc_id']}"
            con.execute(
                """INSERT INTO pdip_clauses (doc_id, storage_key, clause_id,
                    label, label_family, page_index, text, text_status,
                    bbox, original_dims, country, instrument_type,
                    governing_law, currency, document_title)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    r["doc_id"],
                    storage_key,
                    r["clause_id"],
                    r["label"],
                    r.get("label_family"),
                    r.get("page_index"),
                    r.get("text"),
                    r["text_status"],
                    _json.dumps(r.get("bbox")),
                    _json.dumps(r.get("original_dims")),
                    r.get("country"),
                    r.get("instrument_type"),
                    r.get("governing_law"),
                    r.get("currency"),
                    r.get("document_title"),
                ],
            )

    con.commit()
    count = con.execute("SELECT COUNT(*) FROM pdip_clauses").fetchone()
    con.close()
    click.echo(f"Loaded {count[0] if count else 0} records into pdip_clauses")


# ── Ingest command ──────────────────────────────────────────────────


@cli.command()
@click.option(
    "--manifest-dir",
    type=click.Path(path_type=Path),
    default="data/manifests",
    help="Directory containing *_manifest.jsonl files.",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default="data/db/corpus.duckdb",
    help="Path to the DuckDB database file.",
)
@click.option("--run-id", default=None, help="Pipeline run identifier.")
def ingest(manifest_dir: Path, db_path: Path, run_id: str | None) -> None:
    """Load JSONL manifests into DuckDB (serial, single-writer)."""
    import duckdb

    from corpus.db.schema import create_schema

    manifest_dir.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(str(db_path)) as conn:
        create_schema(conn)
        stats = ingest_manifests(conn, manifest_dir, run_id=run_id)

    click.echo(
        f"Ingest complete: {stats['documents_inserted']} inserted, "
        f"{stats['documents_skipped']} skipped."
    )


# ── Status command ─────────────────────────────────────────────────


@cli.command()
@click.argument("source", required=False, default=None)
def status(source: str | None) -> None:
    """Show download status. Optionally filter by SOURCE (nsm, edgar, pdip)."""
    from corpus.reporting import (
        DISCOVERY_PATHS,
        format_status_summary,
        get_source_status,
    )

    sources = [source] if source else list(DISCOVERY_PATHS.keys())

    if source:
        # Detailed per-source view
        s = get_source_status(source)
        if s.get("status") == "not_discovered":
            click.echo(f"  {source.upper()}: not discovered")
            return

        click.echo(
            f"  {s['source'].upper()}: {s['manifest_count']} / {s['discovery_count']} "
            f"downloaded ({s['outstanding_count']} outstanding)"
        )

        if s["outstanding"]:
            click.echo("")
            click.echo(f"  Outstanding ({s['outstanding_count']}):")
            for item in s["outstanding"]:
                error = f"  last error: {item['last_error']}" if item.get("last_error") else ""
                click.echo(f"    {item['native_id']:40s}  {item['title'][:40]:40s}{error}")

            click.echo("")
            discovery_path = DISCOVERY_PATHS.get(source, f"data/{source}_discovery.jsonl")
            click.echo(f"  To retry: corpus download {source} --discovery-file {discovery_path}")
    else:
        # Cross-source summary
        statuses = [get_source_status(s) for s in sources]
        click.echo(format_status_summary(statuses))


# ── Extract-v2 group ────────────────────────────────────────────────


@cli.group("extract-v2")
def extract_v2_group() -> None:
    """Clause extraction v2: section-aware pipeline."""


@extract_v2_group.command("locate")
@click.option(
    "--clause-family",
    required=True,
    type=click.Choice(["collective_action", "pari_passu"]),
)
@click.option("--docling-dir", default="data/parsed_docling", type=click.Path())
@click.option("--flat-dir", default="data/parsed", type=click.Path())
@click.option("--output", default=None, type=click.Path())
@click.option("--run-id", default=None)
@click.option("--skip-flat", is_flag=True, help="Skip flat-parsed EDGAR documents")
def extract_v2_locate(
    clause_family: str,
    docling_dir: str,
    flat_dir: str,
    output: str | None,
    run_id: str | None,
    skip_flat: bool,
) -> None:
    """Stage 1: Parse sections, filter by cues, reject negatives, cluster."""
    import json
    import time

    from corpus.extraction.section_filter import cluster_candidates, filter_sections
    from corpus.extraction.section_parser import parse_docling_markdown, parse_flat_jsonl
    from corpus.io.safe_write import safe_write
    from corpus.logging import CorpusLogger

    run_id = run_id or f"locate_{int(time.time())}"

    config = _load_config()
    # E9: Default output path includes clause family
    prefix = "cac" if clause_family == "collective_action" else "pp"
    output_path = (
        Path(output)
        if output
        else _resolve_path(config, "paths", "extracted_v2_dir", "data/extracted_v2")
        / f"{prefix}_candidates.jsonl"
    )
    if not output_path.is_absolute():
        output_path = _PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log_path = (
        _resolve_path(config, "paths", "telemetry_dir", "data/telemetry") / "extract_v2.jsonl"
    )
    logger = CorpusLogger(log_path, run_id=run_id)

    all_candidates: list = []
    docs_with_candidates = 0

    # --- Docling markdown (NSM, PDIP) ---
    docling_resolved = Path(docling_dir)
    if not docling_resolved.is_absolute():
        docling_resolved = _PROJECT_ROOT / docling_resolved
    if docling_resolved.exists():
        md_files = sorted(docling_resolved.glob("*.md"))
        click.echo(f"Scanning {len(md_files)} Docling markdown files for {clause_family}...")

        for md_file in md_files:
            storage_key = md_file.stem
            markdown_text = md_file.read_text(encoding="utf-8")
            start = time.monotonic()
            sections = parse_docling_markdown(markdown_text, storage_key=storage_key)
            candidates = filter_sections(sections, clause_family=clause_family, run_id=run_id)
            elapsed = int((time.monotonic() - start) * 1000)
            if candidates:
                docs_with_candidates += 1
                all_candidates.extend(candidates)
            logger.log(
                document_id=storage_key,
                step="locate",
                duration_ms=elapsed,
                status="candidates_found" if candidates else "no_candidates",
                candidate_count=len(candidates),
            )

        click.echo(f"  Docling: {len(all_candidates)} candidates from {docs_with_candidates} docs")
    else:
        click.echo(f"  Docling dir not found: {docling_resolved}")

    # --- Flat-parsed JSONL (EDGAR) ---
    if not skip_flat:
        flat_resolved = Path(flat_dir)
        if not flat_resolved.is_absolute():
            flat_resolved = _PROJECT_ROOT / flat_resolved
        if flat_resolved.exists():
            jsonl_files = sorted(flat_resolved.glob("edgar__*.jsonl"))
            click.echo(
                f"Scanning {len(jsonl_files)} EDGAR flat-parsed files for {clause_family}..."
            )

            edgar_candidates = 0
            edgar_docs = 0
            for jsonl_file in jsonl_files:
                storage_key = jsonl_file.stem
                pages = []
                with jsonl_file.open() as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                        except json.JSONDecodeError:
                            continue  # E10: skip malformed lines
                        # E6: Skip header by field presence, not line number
                        if "page" not in rec:
                            continue
                        pages.append(rec)
                start = time.monotonic()
                sections = parse_flat_jsonl(pages, storage_key=storage_key)
                candidates = filter_sections(sections, clause_family=clause_family, run_id=run_id)
                elapsed = int((time.monotonic() - start) * 1000)
                if candidates:
                    edgar_docs += 1
                    edgar_candidates += len(candidates)
                    all_candidates.extend(candidates)
                logger.log(
                    document_id=storage_key,
                    step="locate",
                    duration_ms=elapsed,
                    status="candidates_found" if candidates else "no_candidates",
                    candidate_count=len(candidates),
                )

            docs_with_candidates += edgar_docs
            click.echo(f"  EDGAR: {edgar_candidates} candidates from {edgar_docs} docs")
        else:
            click.echo(f"  Flat dir not found: {flat_resolved}")

    # Cluster adjacent candidates
    clustered = cluster_candidates(all_candidates)

    # Write JSONL (atomic: .part → rename)
    all_records = []
    for c in clustered:
        record = {
            "candidate_id": c.candidate_id,
            "storage_key": c.storage_key,
            "country": _guess_country(c.storage_key),
            "document_title": c.storage_key,
            "section_id": c.section_id,
            "section_index": c.section_index,
            "section_heading": c.section_heading,
            "page_range": list(c.page_range),
            "heading_match": c.heading_match,
            "cue_families_hit": c.cue_families_hit,
            "cue_hits": [
                {
                    "family": h.family,
                    "pattern": h.pattern,
                    "matched_text": h.matched_text,
                }
                for h in c.cue_hits
            ],
            "negative_signals": c.negative_signals,
            "section_text": c.section_text,
            "source_format": c.source_format,
            "run_id": c.run_id,
            "clause_family": clause_family,
        }
        all_records.append(record)

    content = "".join(json.dumps(record) + "\n" for record in all_records)
    safe_write(output_path, content.encode(), overwrite=True)

    click.echo(f"Found {len(clustered)} candidates from {docs_with_candidates} documents.")
    click.echo(f"Written to {output_path}")


@extract_v2_group.command("verify")
@click.option("--extractions", required=True, type=click.Path(exists=True))
@click.option(
    "--clause-family",
    required=True,
    type=click.Choice(["collective_action", "pari_passu"]),
)
@click.option("--output", default=None, type=click.Path())
@click.option("--run-id", default=None)
def extract_v2_verify(
    extractions: str, clause_family: str, output: str | None, run_id: str | None
) -> None:
    """Stage 3: Verify extractions — verbatim check, completeness, quality flags."""
    import json
    import time

    from corpus.extraction.verify import (
        check_completeness,
        check_verbatim,
        compute_quality_flags,
    )
    from corpus.io.safe_write import safe_write
    from corpus.logging import CorpusLogger

    run_id = run_id or f"verify_{int(time.time())}"

    config = _load_config()
    extractions_path = Path(extractions)
    if not extractions_path.is_absolute():
        extractions_path = _PROJECT_ROOT / extractions_path
    # E9: Default output includes clause family prefix
    prefix = "cac" if clause_family == "collective_action" else "pp"
    output_path = (
        Path(output)
        if output
        else _resolve_path(config, "paths", "extracted_v2_dir", "data/extracted_v2")
        / f"{prefix}_verified.jsonl"
    )
    if not output_path.is_absolute():
        output_path = _PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log_path = (
        _resolve_path(config, "paths", "telemetry_dir", "data/telemetry") / "extract_v2.jsonl"
    )
    logger = CorpusLogger(log_path, run_id=run_id)

    records: list[dict] = []
    with extractions_path.open() as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                click.echo(f"  Warning: skipping malformed line in {extractions_path}", err=True)
                continue

    click.echo(f"Verifying {len(records)} extractions...")
    verified: list[dict] = []
    pass_count = 0

    for rec in records:
        ext = rec.get("extraction", {})
        candidate_id = rec.get("candidate_id", "")

        # E19: Skip api_error records entirely
        if ext.get("status") == "api_error":
            rec["verification"] = {"status": "error_skipped"}
            verified.append(rec)
            logger.log(
                document_id=candidate_id,
                step="verify",
                duration_ms=0,
                status="error_skipped",
            )
            continue

        if not ext.get("found"):
            rec["verification"] = {"status": "not_found"}
            verified.append(rec)
            logger.log(
                document_id=candidate_id,
                step="verify",
                duration_ms=0,
                status="not_found",
            )
            continue

        clause_text = ext["clause_text"]
        source_text = rec["section_text"]

        start = time.monotonic()
        verbatim = check_verbatim(clause_text, source_text)
        completeness = check_completeness(clause_text, clause_family=clause_family)
        quality_flags = compute_quality_flags(extracted=clause_text, source=source_text)
        elapsed = int((time.monotonic() - start) * 1000)

        if not verbatim.passes:
            quality_flags.append("verification_failed")

        components_present = sum(1 for v in completeness.values() if v)
        components_total = len(completeness)
        if components_present <= 1 and components_total >= 3:
            quality_flags.append("partial_extraction")

        verbatim_status = "verified" if verbatim.passes else "failed"
        rec["verification"] = {
            "status": verbatim_status,
            "verbatim_similarity": round(verbatim.similarity, 3),
            "completeness": completeness,
            "quality_flags": quality_flags,
            "components_present": components_present,
            "components_total": components_total,
        }

        if verbatim.passes:
            pass_count += 1

        logger.log(
            document_id=candidate_id,
            step="verify",
            duration_ms=elapsed,
            status=verbatim_status,
        )

        verified.append(rec)

    content = "".join(json.dumps(r) + "\n" for r in verified)
    safe_write(output_path, content.encode(), overwrite=True)

    found = sum(1 for r in verified if r.get("extraction", {}).get("found"))
    error_count = sum(1 for r in verified if r.get("extraction", {}).get("status") == "api_error")
    click.echo(f"\nVerification: {pass_count}/{found} passed verbatim check.")
    if error_count:
        click.echo(f"  {error_count} error records skipped.")
    click.echo(f"Written to {output_path}")


# ── Entry point ─────────────────────────────────────────────────────


def main() -> None:
    """Entry point for ``corpus`` console script."""
    cli()
