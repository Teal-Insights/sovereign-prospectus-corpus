"""Tests for PDIP label → clause family mapping."""

from __future__ import annotations

from corpus.extraction.label_mapping import (
    MAPPING_NOTES,
    PDIP_LABEL_TO_FAMILY,
    map_label,
    unmapped_labels,
)


def test_cac_modification_maps_to_collective_action() -> None:
    assert (
        map_label("VotingCollectiveActionModification_AmendmentandWaiver") == "collective_action"
    )
    assert map_label("VotingCollectiveActionModification_Double_Limb") == "collective_action"


def test_pari_passu_maps() -> None:
    assert map_label("StatusofObligationPariPassu_RepresentationsWarranties") == "pari_passu"


def test_negative_pledge_maps() -> None:
    assert map_label("NegativePledge_BorrowerCovenantsUndertakings") == "negative_pledge"


def test_governing_law_maps() -> None:
    assert map_label("GoverningLaw_Enforcement") == "governing_law"


def test_unmapped_label_returns_none() -> None:
    assert map_label("SomeUnknownLabel_Category") is None


def test_every_label_in_dict_is_string() -> None:
    for label, family in PDIP_LABEL_TO_FAMILY.items():
        assert isinstance(label, str)
        assert family is None or isinstance(family, str)


def test_mapping_notes_only_for_mapped_labels() -> None:
    for label in MAPPING_NOTES:
        assert label in PDIP_LABEL_TO_FAMILY


def test_unmapped_labels_returns_labels_not_in_dict() -> None:
    observed = ["GoverningLaw_Enforcement", "TotallyNewLabel_Unknown"]
    result = unmapped_labels(observed)
    assert "TotallyNewLabel_Unknown" in result
    assert "GoverningLaw_Enforcement" not in result
