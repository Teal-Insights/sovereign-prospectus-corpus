"""Generate the static snapshot for the web explorer.

Usage:
    uv run python scripts/build_snapshot.py
    uv run python scripts/build_snapshot.py --db-path data/db/corpus.duckdb \
        --output-dir /tmp/snapshot_smoke --limit 100

Writes documents.parquet, text/<slug>.json (one per document), and
MANIFEST.json, then prints total size by component. Logic lives in
src/corpus/snapshot.py.
"""

from pathlib import Path

import click

from corpus.snapshot import build_snapshot


def _human(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} GB"


@click.command()
@click.option(
    "--db-path",
    type=click.Path(exists=True, path_type=Path),
    default="data/db/corpus.duckdb",
    help="Path to the DuckDB database file.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="data/snapshot",
    help="Directory for the snapshot output.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=None,
    help="Only snapshot the first N documents (smoke tests; requires --output-dir).",
)
@click.pass_context
def main(ctx: click.Context, db_path: Path, output_dir: Path, limit: int | None) -> None:
    """Build documents.parquet, text/<slug>.json files, and MANIFEST.json."""
    import duckdb

    if limit is not None and ctx.get_parameter_source("output_dir") is not None:
        from click.core import ParameterSource

        if ctx.get_parameter_source("output_dir") == ParameterSource.DEFAULT:
            raise click.UsageError(
                "--limit would overwrite the production parquet and manifest in "
                "data/snapshot with a partial index. Pass an explicit --output-dir "
                "for smoke tests."
            )

    click.echo(f"Building snapshot from {db_path} into {output_dir}...")
    try:
        stats = build_snapshot(db_path, output_dir, limit=limit)
    except duckdb.IOException as exc:
        raise click.ClickException(
            f"Could not open {db_path} (is a pipeline step like ingest or "
            f"build-pages holding the write lock? retry after it finishes): {exc}"
        ) from exc

    comp = stats["components"]
    click.echo(
        f"Snapshot complete: {stats['document_count']} documents, "
        f"{stats['text_file_count']} text files."
    )
    for source, count in stats["documents_by_source"].items():
        click.echo(f"  {source}: {count}")
    if stats["unmapped_issuers"]:
        click.echo(
            f"WARNING: {len(stats['unmapped_issuers'])} issuer names have no country "
            "mapping (country shows as Unknown). Add them to "
            "src/corpus/reference/issuer_country_map.py:",
            err=True,
        )
        for name in stats["unmapped_issuers"]:
            click.echo(f"  {name!r}", err=True)
    if stats["sovereign_flag_conflicts"]:
        click.echo(
            f"NOTE: {len(stats['sovereign_flag_conflicts'])} issuers where the curated "
            "map and documents.is_sovereign disagree (map wins; see MANIFEST.json).",
            err=True,
        )
    if stats["stale_text_files_removed"]:
        click.echo(f"Removed {stats['stale_text_files_removed']} stale text files.")
    manifest_bytes = (output_dir / "MANIFEST.json").stat().st_size
    click.echo("Size by component:")
    click.echo(f"  documents.parquet: {_human(comp['documents_parquet_bytes'])}")
    click.echo(f"  text/ ({comp['text_files']} files): {_human(comp['text_bytes'])}")
    click.echo(f"  MANIFEST.json: {_human(manifest_bytes)}")
    total = comp["documents_parquet_bytes"] + comp["text_bytes"] + manifest_bytes
    click.echo(f"  total: {_human(total)}")


if __name__ == "__main__":
    main()
