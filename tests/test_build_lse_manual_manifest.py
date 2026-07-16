"""Tests for the bounded LSE manual-ingest manifest helper."""

from __future__ import annotations

import hashlib
import json
import shutil
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _inventory(pdf_path: Path, *, file_hash: str | None = None) -> dict[str, Any]:
    digest = file_hash or hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return {
        "retrieved_at": "2026-07-16T02:15:00Z",
        "issuer_page_url": (
            "https://www.londonstockexchange.com/stock/XZ57/the-republic-of-congo/company-page"
        ),
        "issuance_events": [
            {
                "event_date": "2025-11-07",
                "description": "US$670 million return",
                "artifact_native_ids": ["THEREPUBLICOFCONGO-YK35-BASE"],
            },
            {
                "event_date": "2026-02-19",
                "description": "US$700 million private placement",
                "artifact_native_ids": [],
                "status": "no_public_lse_document",
            },
        ],
        "documents": [
            {
                "native_id": "THEREPUBLICOFCONGO-YK35-BASE",
                "source_file": pdf_path.name,
                "title": "US$670,000,000 9.875% Amortising Notes due 2032",
                "issuer_name": "THE REPUBLIC OF CONGO",
                "doc_type": "offering_circular",
                "publication_date": "2025-11-05",
                "download_url": (
                    "https://assets.lsegissuerservices.com/assets/"
                    "THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032.zip"
                ),
                "expected_sha256": digest,
                "expected_size_bytes": pdf_path.stat().st_size,
                "expected_page_count": 2,
                "family_id": "lse__congo-2032",
                "document_role": "base",
                "instrument_codes": ["YK35"],
                "isins": ["XS3223166409"],
                "associated_issuance_dates": ["2025-11-07"],
            }
        ],
    }


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    pdf_path = input_dir / "base.pdf"
    shutil.copyfile("tests/fixtures/sample.pdf", pdf_path)
    inventory_path = tmp_path / "inventory.json"
    data_root = tmp_path / "data"
    return pdf_path, inventory_path, data_root


def test_builds_portable_resume_safe_manifest(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory_path.write_text(json.dumps(_inventory(pdf_path)))

    first = build_lse_manual_manifest(
        inventory_path=inventory_path,
        input_dir=pdf_path.parent,
        data_root=data_root,
    )
    manifest_path = data_root / "manifests" / "lse_manifest.jsonl"
    first_bytes = manifest_path.read_bytes()
    second = build_lse_manual_manifest(
        inventory_path=inventory_path,
        input_dir=pdf_path.parent,
        data_root=data_root,
    )

    assert first == second == {"documents": 1, "issuance_events": 2, "events_with_files": 1}
    assert manifest_path.read_bytes() == first_bytes
    record = json.loads(first_bytes)
    assert record["source"] == "lse"
    assert record["storage_key"] == "lse__THEREPUBLICOFCONGO-YK35-BASE"
    assert record["file_path"] == ("data/original/lse__THEREPUBLICOFCONGO-YK35-BASE.pdf")
    assert record["source_page_url"] == record["download_url"]
    assert record["source_page_kind"] == "artifact_archive"
    assert record["countries"] == [
        {
            "country_code": "COG",
            "country_name": "Republic of Congo",
            "role": "issuer",
        }
    ]
    assert record["source_metadata"]["document_role"] == "base"
    assert record["source_metadata"]["retrieved_at"] == "2026-07-16T02:15:00Z"
    assert (data_root / "original" / f"{record['storage_key']}.pdf").read_bytes() == (
        pdf_path.read_bytes()
    )


def test_rejects_non_pdf_magic_before_manifest_write(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    pdf_path.write_bytes(b"not a PDF")
    inventory_path.write_text(json.dumps(_inventory(pdf_path)))

    with pytest.raises(ValueError, match="%PDF"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )

    assert not (data_root / "manifests" / "lse_manifest.jsonl").exists()


def test_rejects_hash_mismatch(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory_path.write_text(json.dumps(_inventory(pdf_path, file_hash="0" * 64)))

    with pytest.raises(ValueError, match="SHA-256"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_duplicate_artifact_hashes(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    duplicate = {**inventory["documents"][0], "native_id": "DUPLICATE"}
    inventory["documents"].append(duplicate)
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="Duplicate artifact SHA-256"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_unknown_event_artifact_reference(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory["issuance_events"][0]["artifact_native_ids"] = ["MISSING"]
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="unknown artifact"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )
