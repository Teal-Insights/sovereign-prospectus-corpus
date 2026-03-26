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
def nsm(run_id: str | None) -> None:
    """Download documents from FCA National Storage Mechanism."""
    click.echo("NSM download not yet implemented (see Task 4).")


# ── Parse group ─────────────────────────────────────────────────────


@cli.group()
def parse() -> None:
    """Parse downloaded PDFs into text."""


# ── Grep group ──────────────────────────────────────────────────────


@cli.group()
def grep() -> None:
    """Run grep-first pattern matching on parsed text."""


# ── Extract group ───────────────────────────────────────────────────


@cli.group()
def extract() -> None:
    """Extract structured clause data from grep matches."""


# ── Ingest command ──────────────────────────────────────────────────


@cli.command()
@click.option(
    "--manifest-dir",
    type=click.Path(exists=True, path_type=Path),
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

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    create_schema(conn)

    stats = ingest_manifests(conn, manifest_dir, run_id=run_id)
    conn.close()

    click.echo(
        f"Ingest complete: {stats['documents_inserted']} inserted, "
        f"{stats['documents_skipped']} skipped."
    )


# ── Entry point ─────────────────────────────────────────────────────


def main() -> None:
    """Entry point for ``corpus`` console script."""
    cli()
