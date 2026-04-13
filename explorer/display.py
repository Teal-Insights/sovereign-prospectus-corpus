"""Shared display helpers for Streamlit and Shiny explorer apps."""

from __future__ import annotations

import html as html_mod

SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "edgar": "SEC EDGAR",
    "nsm": "FCA NSM",
    "luxse": "Luxembourg Stock Exchange",
    "pdip": "#PublicDebtIsPublic",
}

GITHUB_URL = "https://github.com/Teal-Insights/sovereign-prospectus-corpus"
QCRAFT_URL = "https://teal-insights.github.io/QCraft-App/"
PROTOTYPE_URL = "https://teal-insights.github.io/sovereign-prospectus-corpus/"


def source_display(source: str) -> str:
    """Convert internal source key to human-readable name."""
    return SOURCE_DISPLAY_NAMES.get(source, source)


def ext_link(url: str, text: str) -> str:
    """HTML for an external link that opens in a new tab."""
    return (
        f'<a href="{html_mod.escape(url)}" target="_blank"'
        f' rel="noopener noreferrer">{html_mod.escape(text)} \u2197</a>'
    )
