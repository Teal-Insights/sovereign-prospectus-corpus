"""Parser registry — returns a parser instance by name.

Reads the default from config.toml [parser] default when no name is given.
Swapping parser in config.toml requires zero code changes (decision 11).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from corpus.parsers.docling_parser import DoclingParser

if TYPE_CHECKING:
    from corpus.parsers.base import DocumentParser

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.toml"

# PyMuPDF is kept as a lazy fallback only — Docling is the default for
# all PDFs (Decision 18, updated 2026-04-11). PyMuPDF is NOT imported
# eagerly to avoid pulling in the fitz C extension unnecessarily.
_REGISTRY: dict[str, type[DocumentParser]] = {
    "docling": DoclingParser,  # type: ignore[dict-item]
}


def _lazy_load_pymupdf() -> None:
    """Register PyMuPDFParser on first request — avoids eager fitz import."""
    if "pymupdf" not in _REGISTRY:
        from corpus.parsers.pymupdf_parser import PyMuPDFParser

        _REGISTRY["pymupdf"] = PyMuPDFParser  # type: ignore[assignment]


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
        # Try lazy-loading PyMuPDF before giving up
        _lazy_load_pymupdf()
        cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown parser: {name!r}. Available: {sorted(_REGISTRY)}")
    return cls()
