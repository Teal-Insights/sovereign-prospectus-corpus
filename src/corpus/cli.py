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


def _load_config() -> dict:
    """Load config.toml from the project root. Returns empty dict if missing."""
    import tomllib

    # Try CWD first, then resolve relative to the package location
    for candidate in [
        Path("config.toml"),
        Path(__file__).resolve().parent.parent.parent / "config.toml",
    ]:
        if candidate.exists():
            with candidate.open("rb") as f:
                return tomllib.load(f)
    return {}


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
    )

    if stats.get("error"):
        click.echo(f"WARNING: Discovery encountered an error: {stats['error']}")

    click.echo(f"Discovery complete: {stats['total_documents']} documents found.")
    click.echo(f"Output: {output}")


# ── Parse group ─────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def parse(ctx: click.Context) -> None:
    """Parse downloaded PDFs into text."""
    if ctx.invoked_subcommand is None:
        click.echo("Parse not yet implemented. Use --help for subcommands.")


# ── Grep group ──────────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def grep(ctx: click.Context) -> None:
    """Run grep-first pattern matching on parsed text."""
    if ctx.invoked_subcommand is None:
        click.echo("Grep not yet implemented. Use --help for subcommands.")


# ── Extract group ───────────────────────────────────────────────────


@cli.group(invoke_without_command=True)
@click.pass_context
def extract(ctx: click.Context) -> None:
    """Extract structured clause data from grep matches."""
    if ctx.invoked_subcommand is None:
        click.echo("Extract not yet implemented. Use --help for subcommands.")


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


# ── Entry point ─────────────────────────────────────────────────────


def main() -> None:
    """Entry point for ``corpus`` console script."""
    cli()
