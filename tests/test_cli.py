"""Tests for the Click CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from corpus.cli import cli


def test_cli_help_exits_zero() -> None:
    """``corpus --help`` exits cleanly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_cli_shows_version() -> None:
    """``corpus --version`` prints the package version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    import corpus

    assert corpus.__version__ in result.output


def test_download_group_exists() -> None:
    """``corpus download --help`` works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "--help"])
    assert result.exit_code == 0
    assert "download" in result.output.lower()


def test_parse_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["parse", "--help"])
    assert result.exit_code == 0


def test_grep_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["grep", "--help"])
    assert result.exit_code == 0


def test_extract_group_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["extract", "--help"])
    assert result.exit_code == 0


def test_ingest_command_exists() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--help"])
    assert result.exit_code == 0


def test_download_nsm_subcommand_exists() -> None:
    """``corpus download nsm --help`` works (placeholder for Task 4)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "nsm", "--help"])
    assert result.exit_code == 0


def test_download_edgar_subcommand_exists() -> None:
    """``corpus download edgar --help`` works (placeholder for Task 5)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "edgar", "--help"])
    assert result.exit_code == 0


def test_download_pdip_subcommand_exists() -> None:
    """``corpus download pdip --help`` works (placeholder for Task 6)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["download", "pdip", "--help"])
    assert result.exit_code == 0


def test_ingest_accepts_manifest_dir() -> None:
    """``corpus ingest`` accepts --manifest-dir option."""
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "manifest-dir" in result.output


def test_ingest_accepts_db_path() -> None:
    """``corpus ingest`` accepts --db-path option."""
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "db-path" in result.output
