"""Parser registry — returns a parser instance by name.

Reads the default from config.toml [parser] default when no name is given.
Swapping parser in config.toml requires zero code changes (decision 11).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from corpus.parsers.pymupdf_parser import PyMuPDFParser

if TYPE_CHECKING:
    from corpus.parsers.base import DocumentParser

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.toml"

_REGISTRY: dict[str, type[DocumentParser]] = {
    "pymupdf": PyMuPDFParser,  # type: ignore[dict-item]
}


def _read_default_parser_name() -> str:
    """Read [parser] default from config.toml."""
    if _CONFIG_PATH.exists():
        import tomllib

        with open(_CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("parser", {}).get("default", "pymupdf")
    return "pymupdf"


def get_parser(name: str | None = None) -> DocumentParser:
    """Return a parser instance. Falls back to config.toml default."""
    if name is None:
        name = _read_default_parser_name()
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown parser: {name!r}. Available: {sorted(_REGISTRY)}")
    return cls()
