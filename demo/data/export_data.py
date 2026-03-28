"""Export DuckDB data to CSV for Quarto visualizations and Shiny app."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data/db/corpus.duckdb"
MANIFEST_DIR = PROJECT_ROOT / "data/manifests"
OUTPUT_DIR = Path(__file__).resolve().parent
COUNTRY_MAP_PATH = OUTPUT_DIR / "issuer_country_map.csv"


def load_country_map() -> dict[str, tuple[str, str]]:
    """Load issuer pattern -> (country_name, country_code) mapping."""
    mapping: dict[str, tuple[str, str]] = {}
    with COUNTRY_MAP_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["issuer_pattern"].upper()] = (
                row["country_name"],
                row["country_code"],
            )
    return mapping


def match_country(
    issuer_name: str, country_map: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Match an issuer name to a country using substring matching."""
    upper = issuer_name.upper()
    for pattern, country_info in country_map.items():
        if pattern in upper:
            return country_info
    return None


def export_corpus_by_country() -> None:
    """Export document counts by country and source."""
    country_map = load_country_map()
    counts: Counter[tuple[str, str, str]] = Counter()

    for manifest_name in ["nsm_manifest.jsonl", "edgar_manifest.jsonl"]:
        manifest_path = MANIFEST_DIR / manifest_name
        if not manifest_path.exists():
            continue
        source = manifest_name.split("_")[0]
        with manifest_path.open() as f:
            for line in f:
                record = json.loads(line)
                issuer = record.get("issuer_name", "")
                match = match_country(issuer, country_map)
                if match:
                    counts[(match[0], match[1], source)] += 1

    pdip_country_to_code = {
        "Indonesia": "IDN",
        "Jamaica": "JAM",
        "Kenya": "KEN",
        "Philippines": "PHL",
        "Netherlands": "NLD",
        "Sierra Leone": "SLE",
        "Peru": "PER",
        "Ecuador": "ECU",
        "Moldova": "MDA",
        "Cameroon": "CMR",
        "Venezuela": "VEN",
        "Italy": "ITA",
        "Senegal": "SEN",
        "Rwanda": "RWA",
        "Albania": "ALB",
        "Ghana": "GHA",
        "Angola": "AGO",
    }

    # Count from PDIP inventory (all 823 docs, not just annotated)
    inventory_path = PROJECT_ROOT / "data/pdip/pdip_document_inventory.csv"
    if inventory_path.exists():
        with inventory_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                country = row.get("country", "").strip()
                if country:
                    code = pdip_country_to_code.get(country, "")
                    if code:
                        counts[(country, code, "pdip")] += 1

    output_path = OUTPUT_DIR / "corpus_by_country.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["country_name", "country_code", "source", "doc_count"])
        for (country_name, country_code, source), count in sorted(counts.items()):
            writer.writerow([country_name, country_code, source, count])

    print(f"Wrote {len(counts)} rows to {output_path}")


def export_clause_families() -> None:
    """Export clause family annotation counts from PDIP."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        """SELECT label_family,
                  COUNT(*) as annotations,
                  COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses
           WHERE label_family IS NOT NULL
           GROUP BY label_family
           ORDER BY docs DESC"""
    ).fetchall()

    unmapped = con.execute(
        """SELECT COUNT(*) as annotations, COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses WHERE label_family IS NULL"""
    ).fetchone()

    con.close()

    output_path = OUTPUT_DIR / "clause_families.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label_family", "annotations", "docs"])
        for row in rows:
            writer.writerow(row)
        if unmapped and unmapped[0] > 0:
            writer.writerow(["(unmapped)", unmapped[0], unmapped[1]])

    print(f"Wrote {len(rows) + (1 if unmapped and unmapped[0] > 0 else 0)} rows to {output_path}")


def export_grep_candidates(run_id: str | None = None) -> None:
    """Export grep match candidates with context for the Shiny eval explorer."""
    con = duckdb.connect(str(DB_PATH), read_only=True)

    params: list[str] = []
    where_clauses = ["d.source = 'pdip'"]
    if run_id:
        where_clauses.append("gm.run_id = ?")
        params.append(run_id)
    where_str = " AND ".join(where_clauses)

    rows = con.execute(
        f"""SELECT d.storage_key,
                  gm.pattern_name,
                  gm.page_number,
                  gm.matched_text,
                  gm.context_before,
                  gm.context_after,
                  gm.run_id,
                  pc.country,
                  pc.document_title,
                  pc.instrument_type
           FROM grep_matches gm
           JOIN documents d ON gm.document_id = d.document_id
           LEFT JOIN (
               SELECT DISTINCT doc_id, country, document_title, instrument_type
               FROM pdip_clauses
           ) pc ON d.storage_key = 'pdip__' || pc.doc_id
           WHERE {where_str}
           ORDER BY gm.pattern_name, pc.country, d.storage_key""",
        params,
    ).fetchall()
    con.close()

    output_path = OUTPUT_DIR / "grep_candidates.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "storage_key",
                "pattern_name",
                "page_number",
                "matched_text",
                "context_before",
                "context_after",
                "run_id",
                "country",
                "document_title",
                "instrument_type",
            ]
        )
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    import sys

    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Exporting data (run_id={run_id})...")
    export_corpus_by_country()
    export_clause_families()
    export_grep_candidates(run_id)
    print("Done.")
