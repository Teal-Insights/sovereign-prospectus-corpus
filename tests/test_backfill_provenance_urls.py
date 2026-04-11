"""Regression test for the provenance URL backfill script."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def sample_manifests(tmp_path: Path) -> Path:
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()

    edgar = {
        "source": "edgar",
        "native_id": "0001193125-20-188103",
        "storage_key": "edgar__0001193125-20-188103",
        "download_url": "https://www.sec.gov/Archives/edgar/data/914021/000119312520188103/d935251d424b5.htm",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
    }
    nsm = {
        "source": "nsm",
        "native_id": "abc",
        "storage_key": "nsm__abc",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
    }
    pdip = {
        "source": "pdip",
        "native_id": "VEN85",
        "storage_key": "pdip__VEN85",
        "download_url": "https://publicdebtispublic.mdi.georgetown.edu/api/pdf/VEN85",
    }
    (manifest_dir / "edgar_manifest.jsonl").write_text(json.dumps(edgar) + "\n")
    (manifest_dir / "nsm_manifest.jsonl").write_text(json.dumps(nsm) + "\n")
    (manifest_dir / "pdip_manifest.jsonl").write_text(json.dumps(pdip) + "\n")
    return manifest_dir


def test_backfill_adds_both_fields(sample_manifests: Path) -> None:
    from scripts.backfill_provenance_urls import backfill_manifests

    stats = backfill_manifests(manifest_dir=sample_manifests)
    assert stats["files_rewritten"] == 3
    assert stats["records_updated"] == 3

    edgar_rec = json.loads((sample_manifests / "edgar_manifest.jsonl").read_text())
    assert edgar_rec["source_page_kind"] == "filing_index"
    assert "914021" in edgar_rec["source_page_url"]

    nsm_rec = json.loads((sample_manifests / "nsm_manifest.jsonl").read_text())
    assert nsm_rec["source_page_kind"] == "artifact_pdf"
    assert nsm_rec["source_page_url"] == nsm_rec["download_url"]

    pdip_rec = json.loads((sample_manifests / "pdip_manifest.jsonl").read_text())
    assert pdip_rec["source_page_kind"] == "search_page"
    assert pdip_rec["source_page_url"].startswith("https://publicdebtispublic.mdi.georgetown.edu")


def test_backfill_is_idempotent(sample_manifests: Path) -> None:
    """Running backfill twice must produce identical output."""
    from scripts.backfill_provenance_urls import backfill_manifests

    backfill_manifests(manifest_dir=sample_manifests)
    first = (sample_manifests / "edgar_manifest.jsonl").read_text()
    backfill_manifests(manifest_dir=sample_manifests)
    second = (sample_manifests / "edgar_manifest.jsonl").read_text()
    assert first == second


def test_backfill_writes_atomically(sample_manifests: Path) -> None:
    """No .part files should remain after a successful run."""
    from scripts.backfill_provenance_urls import backfill_manifests

    backfill_manifests(manifest_dir=sample_manifests)
    assert list(sample_manifests.glob("*.part")) == []


def test_backfill_skips_records_that_already_have_fields(
    sample_manifests: Path,
) -> None:
    """If a record already has source_page_url set, it is preserved as-is."""
    from scripts.backfill_provenance_urls import backfill_manifests

    rec = {
        "source": "nsm",
        "native_id": "preset",
        "storage_key": "nsm__preset",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/preset.pdf",
        "source_page_url": "https://example.com/manually-set",
        "source_page_kind": "filing_index",
    }
    (sample_manifests / "nsm_manifest.jsonl").write_text(json.dumps(rec) + "\n")

    backfill_manifests(manifest_dir=sample_manifests)

    result = json.loads((sample_manifests / "nsm_manifest.jsonl").read_text())
    assert result["source_page_url"] == "https://example.com/manually-set"
    assert result["source_page_kind"] == "filing_index"


def test_backfill_round_trips_non_ascii_titles(tmp_path: Path) -> None:
    """Document titles commonly contain non-ASCII characters (country
    names like "Côte d'Ivoire", smart quotes, accents). Backfill must
    preserve them verbatim — relying on the system default encoding
    would corrupt them on Windows (cp1252) and json.dumps without
    ensure_ascii=False would escape them to \\uXXXX sequences.
    """
    from scripts.backfill_provenance_urls import backfill_manifests

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "nsm",
        "native_id": "cote-divoire-1",
        "storage_key": "nsm__cote-divoire-1",
        "title": "République de Côte d'Ivoire — Notes de 2030",
        "issuer_name": "Côte d'Ivoire",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/cote.pdf",
    }
    manifest_path = manifest_dir / "nsm_manifest.jsonl"
    manifest_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    backfill_manifests(manifest_dir=manifest_dir)

    rewritten_bytes = manifest_path.read_bytes()
    # The raw bytes must still contain the UTF-8 encoding of "Côte d'Ivoire"
    # (not escaped as \u00f4 etc., and not re-encoded as latin-1).
    assert "Côte d'Ivoire".encode() in rewritten_bytes
    assert b"\\u00f4" not in rewritten_bytes  # no ensure_ascii=True escaping

    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert parsed["title"] == "République de Côte d'Ivoire — Notes de 2030"
    assert parsed["issuer_name"] == "Côte d'Ivoire"
    assert parsed["source_page_kind"] == "artifact_pdf"


def test_backfill_unknown_source_record_is_byte_stable(tmp_path: Path) -> None:
    """A record from an unknown source (e.g. future LSE RNS adapter before
    it has a resolver) gets ``(None, "none")`` from the dispatcher on
    first pass. Repeated runs must produce byte-identical output — the
    resolver is deterministic, so re-derivation on subsequent passes
    writes the same values.

    ``records_updated`` counts records whose values actually changed, so
    the second pass sees 0 updates even though it re-ran the resolver:
    old == new for unknown sources.
    """
    from scripts.backfill_provenance_urls import backfill_manifests

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "lse_rns",
        "native_id": "future-123",
        "storage_key": "lse_rns__future-123",
        "download_url": "https://www.londonstockexchange.com/news-article/future-123",
    }
    manifest_path = manifest_dir / "lse_rns_manifest.jsonl"
    manifest_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    first = backfill_manifests(manifest_dir=manifest_dir)
    assert first["records_updated"] == 1
    first_bytes = manifest_path.read_bytes()
    first_rec = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert first_rec["source_page_url"] is None
    assert first_rec["source_page_kind"] == "none"

    second = backfill_manifests(manifest_dir=manifest_dir)
    # The counter reflects values-changed, not passes-through, so the
    # second run sees (None, 'none') → (None, 'none') and counts 0.
    assert second["records_updated"] == 0
    assert manifest_path.read_bytes() == first_bytes


def test_backfill_re_derives_on_partial_key_records(tmp_path: Path) -> None:
    """A manifest record with only one provenance key present must get
    both re-derived atomically — partial data is bad input. Regression
    test for a convergent 3-reviewer finding where the earlier
    ``if "source_page_url" in record and "source_page_kind" in record``
    gate was overwriting a manually-set value in the partial case while
    leaving it alone in the present-both case (inconsistent).
    """
    from scripts.backfill_provenance_urls import backfill_manifests

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    # URL only, no kind
    record_url_only = {
        "source": "edgar",
        "native_id": "partial-url",
        "storage_key": "edgar__partial-url",
        "source_metadata": {
            "cik": "0000914021",
            "accession_number": "0001193125-20-188103",
        },
        "source_page_url": "https://example.com/manual-bad-input",
    }
    # Kind only, no URL
    record_kind_only = {
        "source": "nsm",
        "native_id": "partial-kind",
        "storage_key": "nsm__partial-kind",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf",
        "source_page_kind": "filing_index",  # wrong for NSM
    }
    edgar_path = manifest_dir / "edgar_manifest.jsonl"
    edgar_path.write_text(json.dumps(record_url_only) + "\n", encoding="utf-8")
    nsm_path = manifest_dir / "nsm_manifest.jsonl"
    nsm_path.write_text(json.dumps(record_kind_only) + "\n", encoding="utf-8")

    backfill_manifests(manifest_dir=manifest_dir)

    edgar_rec = json.loads(edgar_path.read_text(encoding="utf-8"))
    # The bogus manual URL is replaced by the derived one.
    assert "914021" in edgar_rec["source_page_url"]
    assert edgar_rec["source_page_url"] != "https://example.com/manual-bad-input"
    assert edgar_rec["source_page_kind"] == "filing_index"

    nsm_rec = json.loads(nsm_path.read_text(encoding="utf-8"))
    # The bogus manual kind is replaced by the derived one.
    assert nsm_rec["source_page_url"] == "https://data.fca.org.uk/artefacts/NSM/RNS/abc.pdf"
    assert nsm_rec["source_page_kind"] == "artifact_pdf"


def test_backfill_re_derives_on_explicit_null(tmp_path: Path) -> None:
    """A manifest with both keys present but one set to null must still
    trigger re-derivation. "Canonical" = both present AND non-null."""
    from scripts.backfill_provenance_urls import backfill_manifests

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    record = {
        "source": "nsm",
        "native_id": "null-url",
        "storage_key": "nsm__null-url",
        "download_url": "https://data.fca.org.uk/artefacts/NSM/RNS/null-url.pdf",
        "source_page_url": None,
        "source_page_kind": "artifact_pdf",
    }
    manifest_path = manifest_dir / "nsm_manifest.jsonl"
    manifest_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    backfill_manifests(manifest_dir=manifest_dir)

    result = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert result["source_page_url"] == ("https://data.fca.org.uk/artefacts/NSM/RNS/null-url.pdf")
    assert result["source_page_kind"] == "artifact_pdf"
