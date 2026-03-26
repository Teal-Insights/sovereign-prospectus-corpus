"""Click CLI entry point for the sovereign prospectus corpus pipeline.

Groups: download, parse, grep, extract.
Commands: ingest.

Entry point registered in pyproject.toml as ``corpus = "corpus.cli:main"``.
"""

from __future__ import annotations

from pathlib import Path

import click

import corpus
from corpus.db.ingest import ingest_manifests


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
@click.option(
    "--api-responses-dir",
    type=click.Path(path_type=Path),
    default="data/api_responses",
    help="Directory for raw API response JSON files.",
)
def nsm(
    run_id: str | None,
    output_dir: Path,
    manifest_dir: Path,
    log_dir: Path,
    dry_run: bool,
    api_responses_dir: Path,
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
        api_responses_dir=api_responses_dir,
    )

    click.echo(
        f"NSM download complete: {stats['downloaded']} downloaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed."
    )
    if stats["aborted"]:
        click.echo("WARNING: Download aborted due to too many failures.")


@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
def edgar(run_id: str | None) -> None:
    """Download documents from SEC EDGAR."""
    click.echo("EDGAR download not yet implemented (see Task 5).")


@download.command()
@click.option("--run-id", default=None, help="Pipeline run identifier.")
def pdip(run_id: str | None) -> None:
    """Download documents from World Bank PDIP."""
    click.echo("PDIP download not yet implemented (see Task 6).")


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


# ── Entry point ─────────────────────────────────────────────────────


def main() -> None:
    """Entry point for ``corpus`` console script."""
    cli()
