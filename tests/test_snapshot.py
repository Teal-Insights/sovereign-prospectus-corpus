"""Tests for the static snapshot builder (src/corpus/snapshot.py)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb
import polars as pl

from corpus.snapshot import build_snapshot, extract_toc, resolve_country, slugify

if TYPE_CHECKING:
    from pathlib import Path


class TestSlugify:
    def test_source_and_native_id(self):
        assert slugify("nsm__101126915") == "nsm-101126915"

    def test_edgar_accession_number(self):
        assert slugify("edgar__0001193125-20-188103") == "edgar-0001193125-20-188103"

    def test_uppercase_and_symbols(self):
        assert slugify("PDIP__Doc (Final).v2") == "pdip-doc-final-v2"


class TestExtractToc:
    def test_extracts_h2_and_h3_with_offsets(self):
        md = "# Title\n\n## Section One\n\ntext\n\n### Sub A\n\nmore"
        toc = extract_toc(md)
        assert [(e["level"], e["title"]) for e in toc] == [(2, "Section One"), (3, "Sub A")]
        for entry in toc:
            assert md[entry["offset"]] == "#"

    def test_ignores_h1_and_plain_text(self):
        assert extract_toc("# Only Title\n\nno headings here") == []

    def test_captures_edgar_h5_headings(self):
        md = "text\n\n##### RISK FACTORS\n\nbody"
        assert extract_toc(md) == [{"level": 5, "title": "RISK FACTORS", "offset": 6}]


class TestResolveCountry:
    def test_known_sovereign_issuer(self):
        meta = resolve_country("FEDERATIVE REPUBLIC OF BRAZIL")
        assert meta["country_code"] == "BRA"
        assert meta["region"] == "Latin America & Caribbean"
        assert meta["income_group"] == "Upper middle income"
        assert meta["is_sovereign"] is True

    def test_unknown_issuer(self):
        meta = resolve_country("NOT A REAL ISSUER")
        assert meta["country_code"] is None
        assert meta["country_name"] == "Unknown"
        assert meta["income_group"] == "Unknown"

    def test_none_issuer(self):
        assert resolve_country(None)["country_name"] == "Unknown"


def _seed_db(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE documents (
            document_id INTEGER PRIMARY KEY,
            storage_key VARCHAR,
            source VARCHAR,
            native_id VARCHAR,
            issuer_name VARCHAR,
            title VARCHAR,
            doc_type VARCHAR,
            publication_date DATE,
            source_page_url VARCHAR,
            download_url VARCHAR,
            page_count INTEGER
        )
        """
    )
    conn.execute("CREATE TABLE document_markdown (document_id INTEGER, markdown_text VARCHAR)")
    conn.execute(
        "CREATE TABLE document_pages (document_id INTEGER, page_number INTEGER, page_text VARCHAR)"
    )
    conn.execute(
        "INSERT INTO documents VALUES "
        "(1, 'nsm__111', 'nsm', '111', 'FEDERATIVE REPUBLIC OF BRAZIL', 'Brazil 2031 Notes',"
        " 'prospectus', DATE '2026-01-15', 'https://example.test/filing/111', "
        " 'https://example.test/dl/111.pdf', 2),"
        "(2, 'edgar__222', 'edgar', '222', NULL, 'Untitled Filing', NULL, NULL,"
        " NULL, 'https://example.test/dl/222.htm', 1),"
        "(3, 'pdip__333', 'pdip', '333', 'NOBODY KNOWS', NULL, 'supplement', NULL,"
        " NULL, NULL, NULL)"
    )
    conn.execute("INSERT INTO document_markdown VALUES (1, '# Doc\n\n## Terms\n\nBody text')")
    conn.execute(
        "INSERT INTO document_pages VALUES (2, 1, 'page one text'), (2, 2, 'page two text')"
    )
    conn.close()


class TestBuildSnapshot:
    def test_end_to_end(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        out_dir = tmp_path / "snapshot"

        stats = build_snapshot(db_path, out_dir)

        assert stats["document_count"] == 3
        assert stats["text_file_count"] == 2
        assert stats["documents_by_source"] == {"edgar": 1, "nsm": 1, "pdip": 1}

        frame = pl.read_parquet(out_dir / "documents.parquet")
        assert frame.height == 3
        row = frame.filter(pl.col("slug") == "nsm-111").row(0, named=True)
        assert row["country_name"] == "Brazil"
        assert row["region"] == "Latin America & Caribbean"
        assert row["filing_url"] == "https://example.test/filing/111"
        assert row["has_text"] is True
        assert row["text_source"] == "markdown"

        # Markdown doc: text + toc
        doc1 = json.loads((out_dir / "text" / "nsm-111.json").read_text())
        assert doc1["text_source"] == "markdown"
        assert doc1["toc"] == [{"level": 2, "title": "Terms", "offset": 7}]
        assert "Body text" in doc1["text"]

        # Pages-fallback doc: concatenated pages, empty toc
        doc2 = json.loads((out_dir / "text" / "edgar-222.json").read_text())
        assert doc2["text_source"] == "pages"
        assert doc2["text"] == "page one text\n\npage two text"
        assert doc2["toc"] == []
        # download_url used when source_page_url is missing
        assert doc2["filing_url"] == "https://example.test/dl/222.htm"

        # Doc without text: no JSON file, has_text False
        assert not (out_dir / "text" / "pdip-333.json").exists()
        row3 = frame.filter(pl.col("slug") == "pdip-333").row(0, named=True)
        assert row3["has_text"] is False
        assert row3["country_name"] == "Unknown"

        manifest = json.loads((out_dir / "MANIFEST.json").read_text())
        assert manifest["schema_version"] == 1
        assert manifest["document_count"] == 3
        assert manifest["components"]["text_files"] == 2

    def test_limit(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        out_dir = tmp_path / "snapshot"

        stats = build_snapshot(db_path, out_dir, limit=1)

        assert stats["document_count"] == 1
        frame = pl.read_parquet(out_dir / "documents.parquet")
        assert frame["slug"].to_list() == ["nsm-111"]
