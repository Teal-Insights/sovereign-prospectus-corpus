"""Tests for reflow_text in demo/data/export_data.py."""

import sys
from pathlib import Path

# demo/data is not a package — add it to the path directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo" / "data"))

from export_data import reflow_text


def test_single_word_per_line_joined() -> None:
    """Words split one-per-line should be joined into flowing text."""
    text = "The\nBonds\ncontain\ncollective\naction"
    result = reflow_text(text)
    assert "\n" not in result
    assert result == "The Bonds contain collective action"


def test_long_lines_unchanged() -> None:
    """Lines already long enough to be flowing prose are left alone."""
    line = "The Bonds are issued under the terms of the Fiscal Agency Agreement dated 2024."
    result = reflow_text(line)
    assert result == line


def test_paragraph_breaks_preserved() -> None:
    """Blank lines that separate paragraphs must survive reflowing."""
    text = "First paragraph text.\n\nSecond paragraph text."
    result = reflow_text(text)
    assert "\n\n" in result
    parts = result.split("\n\n")
    assert len(parts) == 2
    assert parts[0].strip() == "First paragraph text."
    assert parts[1].strip() == "Second paragraph text."


def test_hyphenation_joined() -> None:
    """Hyphenated line breaks should be joined without the hyphen."""
    text = "bond-\nholders shall vote"
    result = reflow_text(text)
    assert "bondholders shall vote" in result
    assert "-\n" not in result


def test_terminal_punctuation_prevents_joining() -> None:
    """A line ending with '.' should not be joined to the next line."""
    text = "This sentence ends here.\nThis is a new sentence."
    result = reflow_text(text)
    lines = [ln for ln in result.split("\n") if ln.strip()]
    assert len(lines) == 2, f"Expected 2 lines, got: {lines}"
