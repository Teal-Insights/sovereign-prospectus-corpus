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
