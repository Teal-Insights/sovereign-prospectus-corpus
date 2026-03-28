"""Validate grep results against PDIP annotations.

Computes document-level presence precision and recall per clause family.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def load_pdip_presence(
    clause_annotations_path: Path,
) -> dict[str, set[str]]:
    """Load PDIP annotations as {doc_id: set of label_families}.

    Only includes families that are not None (mapped families).
    """
    doc_families: dict[str, set[str]] = defaultdict(set)
    with clause_annotations_path.open() as f:
        for line in f:
            record = json.loads(line)
            family: str | None = record.get("label_family")
            if family is not None:
                doc_families[record["doc_id"]].add(family)
    return dict(doc_families)


def load_grep_presence(
    *,
    db_path: Path,
    run_id: str | None = None,
) -> dict[str, set[str]]:
    """Load grep results as {storage_key: set of clause families}.

    Maps pattern_name → family using the pattern registry.

    Args:
        db_path: Path to the DuckDB database.
        run_id: If provided, filter to matches from this run only.
    """
    import duckdb

    from corpus.extraction.clause_patterns import CLAUSE_PATTERNS, FEATURE_PATTERNS

    # Build pattern_name → family mapping
    pattern_to_family: dict[str, str] = {}
    for p in list(CLAUSE_PATTERNS.values()) + list(FEATURE_PATTERNS.values()):
        pattern_to_family[p.name] = p.family

    doc_families: dict[str, set[str]] = defaultdict(set)

    con = duckdb.connect(str(db_path), read_only=True)
    if run_id:
        rows = con.execute(
            """SELECT d.storage_key, gm.pattern_name
               FROM grep_matches gm
               JOIN documents d ON gm.document_id = d.document_id
               WHERE gm.run_id = ?""",
            [run_id],
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT d.storage_key, gm.pattern_name
               FROM grep_matches gm
               JOIN documents d ON gm.document_id = d.document_id"""
        ).fetchall()
    con.close()
    for storage_key, pattern_name in rows:
        family: str = pattern_to_family.get(str(pattern_name), str(pattern_name))
        doc_families[str(storage_key)].add(family)
    return dict(doc_families)


def compute_validation_report(
    pdip_presence: dict[str, set[str]],
    grep_presence: dict[str, set[str]],
    *,
    pdip_doc_id_to_storage_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compute precision and recall per family.

    Args:
        pdip_presence: {doc_id: set of families} from PDIP
        grep_presence: {storage_key: set of pattern families} from grep
        pdip_doc_id_to_storage_key: mapping from PDIP doc_id to storage_key
            (e.g., "VEN85" -> "pdip__VEN85"). If None, assumes
            storage_key = f"pdip__{doc_id}".
    """
    families_in_scope = set()
    for fams in pdip_presence.values():
        families_in_scope.update(fams)
    for pats in grep_presence.values():
        families_in_scope.update(pats)

    results: dict[str, Any] = {}

    for family in sorted(families_in_scope):
        # Documents where PDIP says this family is present
        pdip_positive_docs = {doc_id for doc_id, fams in pdip_presence.items() if family in fams}

        # Map PDIP doc_ids to storage_keys for comparison
        if pdip_doc_id_to_storage_key:
            pdip_storage_keys = {
                pdip_doc_id_to_storage_key.get(d, f"pdip__{d}") for d in pdip_positive_docs
            }
        else:
            pdip_storage_keys = {f"pdip__{d}" for d in pdip_positive_docs}

        # Documents where grep says this family is present
        grep_positive_docs = {sk for sk, pats in grep_presence.items() if family in pats}

        tp = len(pdip_storage_keys & grep_positive_docs)
        fn = len(pdip_storage_keys - grep_positive_docs)
        fp = len(grep_positive_docs - pdip_storage_keys)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        results[family] = {
            "true_positives": tp,
            "false_negatives": fn,
            "false_positives": fp,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "pdip_docs": len(pdip_positive_docs),
            "grep_docs": len(grep_positive_docs),
        }

    return {
        "families": results,
        "total_pdip_docs": len(pdip_presence),
        "total_grep_docs": len(grep_presence),
    }


def write_validation_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    """Write validation report to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(report, f, indent=2)
