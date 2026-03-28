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

    con = duckdb.connect(str(DB_PATH), read_only=True)
    pdip_rows = con.execute(
        """SELECT country, COUNT(DISTINCT doc_id) as docs
           FROM pdip_clauses
           WHERE country IS NOT NULL
           GROUP BY country"""
    ).fetchall()
    con.close()

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
    }
    for country_name, doc_count in pdip_rows:
        code = pdip_country_to_code.get(country_name, "")
        if code:
            counts[(country_name, code, "pdip")] += doc_count

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
    con.close()

    output_path = OUTPUT_DIR / "clause_families.csv"
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label_family", "annotations", "docs"])
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output_path}")


def export_grep_candidates() -> None:
    """Export grep match candidates with context for the Shiny eval explorer."""
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        """SELECT d.storage_key,
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
           WHERE d.source = 'pdip'
           ORDER BY gm.pattern_name, pc.country, d.storage_key"""
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
    print("Exporting data for Quarto book and Shiny app...")
    export_corpus_by_country()
    export_clause_families()
    export_grep_candidates()
    print("Done.")
