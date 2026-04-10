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


def test_backfill_unknown_source_record_is_idempotent(tmp_path: Path) -> None:
    """A record from an unknown source (e.g. future LSE RNS adapter before
    it has a resolver) gets ``(None, "none")`` on first pass. The second
    pass must NOT re-update it — the presence of both keys is the idempotency
    signal, not the truthiness of their values.

    Regression test for a latent bug where ``if record.get("source_page_url")
    and record.get("source_page_kind")`` evaluated to False for ``None`` and
    caused unknown-source records to re-resolve every run.
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
    manifest_path.write_text(json.dumps(record) + "\n")

    first = backfill_manifests(manifest_dir=manifest_dir)
    assert first["records_updated"] == 1
    first_rec = json.loads(manifest_path.read_text())
    assert first_rec["source_page_url"] is None
    assert first_rec["source_page_kind"] == "none"

    second = backfill_manifests(manifest_dir=manifest_dir)
    assert second["records_updated"] == 0, (
        "second pass must treat (None, 'none') as already-resolved"
    )
    second_rec = json.loads(manifest_path.read_text())
    assert second_rec == first_rec
