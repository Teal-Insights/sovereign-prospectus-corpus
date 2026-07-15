"""Tests for the markdown sidecar written by `corpus parse run`."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from corpus.cli import cli
from corpus.parsers.base import ParseResult

if TYPE_CHECKING:
    from pathlib import Path


class FakeMarkdownParser:
    """Stands in for DoclingParser: pages plus full-document markdown."""

    def __init__(self, markdown: str) -> None:
        self.markdown = markdown

    def parse(self, path: Path) -> ParseResult:
        page_text = "page one text " * 6
        return ParseResult(
            pages=[page_text],
            text=page_text,
            page_count=1,
            parse_tool="fake",
            parse_version="0.0",
            metadata={"markdown": self.markdown},
        )


class FakeEmptyParser:
    def parse(self, path: Path) -> ParseResult:
        return ParseResult(
            pages=[""],
            text="",
            page_count=1,
            parse_tool="fake",
            parse_version="0.0",
            metadata={},
        )


def _setup_dirs(tmp_path: Path, monkeypatch, markdown: str) -> Path:
    parsed = tmp_path / "parsed"
    manifests = tmp_path / "manifests"
    manifests.mkdir(parents=True)
    telemetry = tmp_path / "telemetry"

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-fake")
    record = {"storage_key": "nsm__t1", "file_path": str(pdf)}
    (manifests / "nsm_manifest.jsonl").write_text(json.dumps(record) + "\n")

    monkeypatch.setattr(
        "corpus.cli._load_config",
        lambda: {
            "paths": {
                "parsed_dir": str(parsed),
                "manifests_dir": str(manifests),
                "telemetry_dir": str(telemetry),
            }
        },
    )
    monkeypatch.setattr(
        "corpus.parsers.registry.get_parser",
        lambda name=None: FakeMarkdownParser(markdown),
    )
    return parsed


class TestParseSidecar:
    def test_help_lists_targeted_keys_and_new_sources(self):
        result = CliRunner().invoke(cli, ["parse", "run", "--help"])

        assert result.exit_code == 0
        assert "--storage-key" in result.output
        assert "luxse" in result.output
        assert "lse" in result.output

    def test_writes_markdown_sidecar_next_to_jsonl(self, tmp_path, monkeypatch):
        parsed = _setup_dirs(tmp_path, monkeypatch, "# Doc\n\n## Terms\n\nbody")

        result = CliRunner().invoke(cli, ["parse", "run", "--run-id", "t", "--source", "nsm"])

        assert result.exit_code == 0, result.output
        assert (parsed / "nsm__t1.jsonl").exists()
        assert (parsed / "nsm__t1.md").read_text() == "# Doc\n\n## Terms\n\nbody"

    def test_rerun_skips_but_keeps_sidecar(self, tmp_path, monkeypatch):
        parsed = _setup_dirs(tmp_path, monkeypatch, "## Only Section")

        runner = CliRunner()
        first = runner.invoke(cli, ["parse", "run", "--run-id", "t1", "--source", "nsm"])
        second = runner.invoke(cli, ["parse", "run", "--run-id", "t2", "--source", "nsm"])

        assert first.exit_code == 0 and second.exit_code == 0
        assert "Skipped: 1" in second.output
        assert (parsed / "nsm__t1.md").exists()

    def test_empty_markdown_writes_no_sidecar(self, tmp_path, monkeypatch):
        parsed = _setup_dirs(tmp_path, monkeypatch, "   \n  ")

        result = CliRunner().invoke(cli, ["parse", "run", "--run-id", "t", "--source", "nsm"])

        assert result.exit_code == 0, result.output
        assert (parsed / "nsm__t1.jsonl").exists()
        assert not (parsed / "nsm__t1.md").exists()

    def test_storage_key_parses_only_exact_selection(self, tmp_path, monkeypatch):
        parsed = tmp_path / "parsed"
        manifests = tmp_path / "manifests"
        manifests.mkdir()
        records = []
        for key in ("edgar__one", "edgar__two"):
            path = tmp_path / f"{key}.htm"
            path.write_text(f"<html><body>{'prospectus text ' * 10}</body></html>")
            records.append({"storage_key": key, "file_path": str(path)})
        (manifests / "edgar_manifest.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records)
        )
        monkeypatch.setattr(
            "corpus.cli._load_config",
            lambda: {
                "paths": {
                    "parsed_dir": str(parsed),
                    "manifests_dir": str(manifests),
                    "telemetry_dir": str(tmp_path / "telemetry"),
                }
            },
        )

        result = CliRunner().invoke(
            cli,
            [
                "parse",
                "run",
                "--run-id",
                "targeted",
                "--source",
                "edgar",
                "--storage-key",
                "edgar__two",
            ],
        )

        assert result.exit_code == 0, result.output
        assert not (parsed / "edgar__one.jsonl").exists()
        assert (parsed / "edgar__two.jsonl").exists()

    def test_resolves_portable_data_path_from_external_manifest_root(self, tmp_path, monkeypatch):
        data = tmp_path / "shadow" / "data"
        manifests = data / "manifests"
        original = data / "original"
        manifests.mkdir(parents=True)
        original.mkdir(parents=True)
        pdf = original / "nsm__portable.pdf"
        pdf.write_bytes(b"%PDF-fake")
        (manifests / "nsm_manifest.jsonl").write_text(
            json.dumps(
                {
                    "storage_key": "nsm__portable",
                    "file_path": "data/original/nsm__portable.pdf",
                }
            )
            + "\n"
        )
        parsed = data / "parsed"
        monkeypatch.setattr(
            "corpus.cli._load_config",
            lambda: {
                "paths": {
                    "parsed_dir": str(parsed),
                    "manifests_dir": str(manifests),
                    "telemetry_dir": str(data / "telemetry"),
                }
            },
        )
        monkeypatch.setattr(
            "corpus.parsers.registry.get_parser",
            lambda name=None: FakeMarkdownParser("## Portable"),
        )

        result = CliRunner().invoke(
            cli,
            [
                "parse",
                "run",
                "--run-id",
                "portable",
                "--source",
                "nsm",
                "--storage-key",
                "nsm__portable",
            ],
        )

        assert result.exit_code == 0, result.output
        assert (parsed / "nsm__portable.jsonl").exists()

    def test_missing_selected_storage_key_exits_nonzero(self, tmp_path, monkeypatch):
        _setup_dirs(tmp_path, monkeypatch, "## Section")

        result = CliRunner().invoke(
            cli,
            [
                "parse",
                "run",
                "--run-id",
                "missing",
                "--source",
                "nsm",
                "--storage-key",
                "nsm__absent",
            ],
        )

        assert result.exit_code != 0
        assert "Storage keys not found" in result.output

    def test_selected_empty_parse_exits_nonzero(self, tmp_path, monkeypatch):
        _setup_dirs(tmp_path, monkeypatch, "")
        monkeypatch.setattr(
            "corpus.parsers.registry.get_parser", lambda name=None: FakeEmptyParser()
        )

        result = CliRunner().invoke(
            cli,
            [
                "parse",
                "run",
                "--run-id",
                "empty",
                "--source",
                "nsm",
                "--storage-key",
                "nsm__t1",
            ],
        )

        assert result.exit_code != 0
        assert "Failed: 1" in result.output
