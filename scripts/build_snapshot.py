"""Generate the static snapshot for the web explorer.

Usage:
    uv run python scripts/build_snapshot.py
    uv run python scripts/build_snapshot.py --db-path data/db/corpus.duckdb \
        --output-dir data/snapshot --limit 100

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
@click.option("--limit", type=int, default=None, help="Only snapshot the first N documents.")
def main(db_path: Path, output_dir: Path, limit: int | None) -> None:
    """Build documents.parquet, text/<slug>.json files, and MANIFEST.json."""
    click.echo(f"Building snapshot from {db_path} into {output_dir}...")
    stats = build_snapshot(db_path, output_dir, limit=limit)

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
            "src/corpus/reference/issuer_country_map.py:"
        )
        for name in stats["unmapped_issuers"]:
            click.echo(f"  {name!r}")
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
