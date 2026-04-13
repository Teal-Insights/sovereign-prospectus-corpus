"""Tests for shared display helpers."""

from __future__ import annotations


def test_source_display_known():
    from explorer.display import source_display

    assert source_display("edgar") == "SEC EDGAR"
    assert source_display("nsm") == "FCA NSM"
    assert source_display("luxse") == "Luxembourg Stock Exchange"
    assert source_display("pdip") == "#PublicDebtIsPublic"


def test_source_display_unknown():
    from explorer.display import source_display

    assert source_display("unknown_source") == "unknown_source"


def test_ext_link_escapes_html():
    from explorer.display import ext_link

    result = ext_link('http://example.com/"test"', "Click <here>")
    assert "&quot;" in result
    assert "&lt;" in result
    assert 'target="_blank"' in result
    assert 'rel="noopener noreferrer"' in result
