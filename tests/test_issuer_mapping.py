"""Tests for issuer-to-country mapping coverage."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_all_issuers_mapped():
    """Every issuer_name in the mapping resolves to a known WB country."""
    from explorer.country_metadata import WORLD_BANK_CLASSIFICATIONS
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    unmapped = []
    for issuer, (code, _name, _is_sov) in ISSUER_TO_COUNTRY.items():
        if code not in WORLD_BANK_CLASSIFICATIONS:
            unmapped.append(f"{issuer} -> {code}")

    assert not unmapped, "Issuers with unmapped country codes:\n" + "\n".join(unmapped)


def test_no_empty_country_names():
    """Every mapping has a non-empty country name."""
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    empty = [k for k, (_, name, _) in ISSUER_TO_COUNTRY.items() if not name]
    assert not empty, "Issuers with empty country names: " + str(empty)


def test_country_codes_are_alpha3():
    """All country codes are 3-letter uppercase."""
    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    bad = [
        f"{k} -> {code}"
        for k, (code, _, _) in ISSUER_TO_COUNTRY.items()
        if len(code) != 3 or code != code.upper()
    ]
    assert not bad, "Invalid country codes:\n" + "\n".join(bad)


@pytest.mark.skipif(
    not Path("data/db/corpus.duckdb").exists(),
    reason="Local corpus.duckdb not available",
)
def test_mapping_covers_all_corpus_issuers():
    """Every non-null issuer_name in the DB has a mapping entry."""
    import duckdb

    from explorer.issuer_country_map import ISSUER_TO_COUNTRY

    con = duckdb.connect("data/db/corpus.duckdb", read_only=True)
    db_issuers = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT issuer_name FROM documents WHERE issuer_name IS NOT NULL"
        ).fetchall()
    ]
    con.close()

    unmapped = [name for name in db_issuers if name not in ISSUER_TO_COUNTRY]
    assert not unmapped, (
        str(len(unmapped)) + " issuers in DB not in mapping:\n" + "\n".join(unmapped[:20])
    )
