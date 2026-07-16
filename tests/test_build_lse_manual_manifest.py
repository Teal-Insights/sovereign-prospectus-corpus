"""Tests for the bounded LSE manual-ingest manifest helper."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest


def _inventory(pdf_path: Path, *, file_hash: str | None = None) -> dict[str, Any]:
    base_bytes = pdf_path.read_bytes()
    tap_path = pdf_path.with_name("tap.pdf")
    may_path = pdf_path.with_name("may.pdf")
    tap_path.write_bytes(base_bytes + b"\n% distinct tap fixture")
    may_path.write_bytes(base_bytes + b"\n% distinct may fixture")

    def document(
        *,
        native_id: str,
        source_path: Path,
        instrument_code: str,
        isin: str,
        issuance_date: str,
        role: str,
        family_id: str,
    ) -> dict[str, Any]:
        content = source_path.read_bytes()
        archive_path = source_path.with_suffix(".zip")
        archive_member = f"source/{source_path.name}"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(archive_member, content)
        archive_content = archive_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if native_id.endswith("due2032") and file_hash is not None:
            digest = file_hash
        return {
            "native_id": native_id,
            "source_file": source_path.name,
            "source_archive_file": archive_path.name,
            "source_archive_member": archive_member,
            "source_archive_sha256": hashlib.sha256(archive_content).hexdigest(),
            "source_archive_size_bytes": len(archive_content),
            "title": f"{instrument_code} offering circular",
            "issuer_name": "THE REPUBLIC OF CONGO",
            "doc_type": "offering_circular",
            "publication_date": issuance_date,
            "download_url": ("https://assets.lsegissuerservices.com/assets/" + native_id + ".zip"),
            "expected_sha256": digest,
            "expected_size_bytes": len(content),
            "expected_page_count": 2,
            "family_id": family_id,
            "document_role": role,
            "instrument_codes": [instrument_code],
            "isins": [isin],
            "associated_issuance_dates": [issuance_date],
        }

    return {
        "retrieved_at": "2026-07-16T02:15:00Z",
        "issuer_page_url": (
            "https://www.londonstockexchange.com/stock/XZ57/the-republic-of-congo/company-page"
        ),
        "issuance_events": [
            {
                "event_date": "2025-11-07",
                "description": "US$670 million return",
                "instrument_code": "YK35",
                "isin": "XS3223166409",
                "artifact_native_ids": [
                    "THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032"
                ],
            },
            {
                "event_date": "2025-12-19",
                "description": "US$260 million tap",
                "instrument_code": "YK35",
                "isin": "XS3223166409",
                "artifact_native_ids": ["THEREPUBLICOFCONGO-YK35"],
            },
            {
                "event_date": "2026-02-19",
                "description": "US$700 million private placement",
                "instrument_code": "XP53",
                "isin": "XS3295059367",
                "artifact_native_ids": [],
                "status": "no_public_lse_document",
            },
            {
                "event_date": "2026-05-26",
                "description": "US$850 million return",
                "instrument_code": "XZ57",
                "isin": "XS3376882687",
                "artifact_native_ids": ["THEREPUBLICOFCONGO-XZ57"],
            },
        ],
        "documents": [
            document(
                native_id="THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032",
                source_path=pdf_path,
                instrument_code="YK35",
                isin="XS3223166409",
                issuance_date="2025-11-07",
                role="base",
                family_id="lse__congo-2032",
            ),
            document(
                native_id="THEREPUBLICOFCONGO-YK35",
                source_path=tap_path,
                instrument_code="YK35",
                isin="XS3223166409",
                issuance_date="2025-12-19",
                role="tap",
                family_id="lse__congo-2032",
            ),
            document(
                native_id="THEREPUBLICOFCONGO-XZ57",
                source_path=may_path,
                instrument_code="XZ57",
                isin="XS3376882687",
                issuance_date="2026-05-26",
                role="base",
                family_id="lse__congo-2036",
            ),
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

    assert first == second == {"documents": 3, "issuance_events": 4, "events_with_files": 3}
    assert manifest_path.read_bytes() == first_bytes
    records = [json.loads(line) for line in first_bytes.splitlines()]
    record = next(
        item
        for item in records
        if item["storage_key"] == "lse__THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032"
    )
    assert record["source"] == "lse"
    assert record["storage_key"] == (
        "lse__THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032"
    )
    assert record["file_path"] == (
        "data/original/lse__THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032.pdf"
    )
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


def test_custom_data_root_keeps_absolute_manifest_path(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, _ = _layout(tmp_path)
    data_root = tmp_path / "lse-run"
    inventory_path.write_text(json.dumps(_inventory(pdf_path)))

    build_lse_manual_manifest(
        inventory_path=inventory_path,
        input_dir=pdf_path.parent,
        data_root=data_root,
    )

    records = [
        json.loads(line)
        for line in (data_root / "manifests" / "lse_manifest.jsonl").read_text().splitlines()
    ]
    assert all(Path(record["file_path"]).is_absolute() for record in records)


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


def test_rejects_symlinked_staging_file(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(pdf_path.read_bytes())
    pdf_path.unlink()
    pdf_path.symlink_to(outside)
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="must not be a symlink"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


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


def test_rejects_archive_url_that_does_not_match_native_id(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory["documents"][0]["download_url"] = (
        "https://assets.lsegissuerservices.com/assets/THEREPUBLICOFCONGO-XZ57.zip"
    )
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="basename does not match"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_extracted_pdf_that_differs_from_archive_member(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    archive_path = pdf_path.with_name(inventory["documents"][0]["source_archive_file"])
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            inventory["documents"][0]["source_archive_member"],
            pdf_path.read_bytes() + b"\n% altered archive member",
        )
    inventory["documents"][0]["source_archive_sha256"] = hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    inventory["documents"][0]["source_archive_size_bytes"] = archive_path.stat().st_size
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="do not match archive member"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_duplicate_artifact_hashes(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    tap_path = pdf_path.with_name("tap.pdf")
    tap_path.write_bytes(pdf_path.read_bytes())
    archive_path = pdf_path.with_name(inventory["documents"][1]["source_archive_file"])
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(inventory["documents"][1]["source_archive_member"], pdf_path.read_bytes())
    inventory["documents"][1]["expected_sha256"] = hashlib.sha256(
        pdf_path.read_bytes()
    ).hexdigest()
    inventory["documents"][1]["expected_size_bytes"] = pdf_path.stat().st_size
    inventory["documents"][1]["source_archive_sha256"] = hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    inventory["documents"][1]["source_archive_size_bytes"] = archive_path.stat().st_size
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


def test_rejects_document_not_referenced_by_issuance_event(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    orphan = {**inventory["documents"][0], "native_id": "ORPHAN"}
    inventory["documents"].append(orphan)
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="document identities"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_document_issuance_dates_that_disagree_with_events(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory["documents"][0]["associated_issuance_dates"] = ["2025-11-08"]
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="associated_issuance_dates do not match"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_rejects_missing_expected_issuance_event(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory["issuance_events"] = inventory["issuance_events"][:-1]
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match="missing expected"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


def test_manifest_conflict_is_preflighted_before_file_copy(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory_path.write_text(json.dumps(inventory))
    manifest = data_root / "manifests" / "lse_manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "storage_key": ("lse__THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032"),
                "file_hash": "0" * 64,
            }
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="manifest conflicts"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )

    assert not (
        data_root
        / "original"
        / "lse__THEREPUBLICOFCONGO-US6700000009875AmortisingNotesdue2032.pdf"
    ).exists()


def test_rejects_hash_owned_by_another_manifest_key(tmp_path: Path) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory_path.write_text(json.dumps(inventory))
    manifest = data_root / "manifests" / "lse_manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "storage_key": "lse__OLD-KEY",
                "file_hash": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            }
        )
        + "\n"
    )

    with pytest.raises(ValueError, match="already belongs"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )


@pytest.mark.parametrize(
    ("event_field", "document_field", "bad_value"),
    [
        ("instrument_code", "instrument_codes", "WRONG"),
        ("isin", "isins", "XS0000000000"),
    ],
)
def test_rejects_event_security_that_disagrees_with_document(
    tmp_path: Path,
    event_field: str,
    document_field: str,
    bad_value: str,
) -> None:
    from scripts.build_lse_manual_manifest import build_lse_manual_manifest

    pdf_path, inventory_path, data_root = _layout(tmp_path)
    inventory = _inventory(pdf_path)
    inventory["issuance_events"][0]["instrument_code"] = "YK35"
    inventory["issuance_events"][0]["isin"] = "XS3223166409"
    inventory["documents"][0][document_field] = [bad_value]
    inventory_path.write_text(json.dumps(inventory))

    with pytest.raises(ValueError, match=f"event {event_field} does not match"):
        build_lse_manual_manifest(
            inventory_path=inventory_path,
            input_dir=pdf_path.parent,
            data_root=data_root,
        )
