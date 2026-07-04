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
        return ParseResult(
            pages=["page one text"],
            text="page one text",
            page_count=1,
            parse_tool="fake",
            parse_version="0.0",
            metadata={"markdown": self.markdown},
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
