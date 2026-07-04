"""Tests for the static snapshot builder (src/corpus/snapshot.py)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import duckdb
import polars as pl
import pytest

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
            assert entry["offset_utf16"] == entry["offset"]  # no astral chars

    def test_ignores_h1_and_plain_text(self):
        assert extract_toc("# Only Title\n\nno headings here") == []

    def test_captures_edgar_h5_headings(self):
        md = "text\n\n##### RISK FACTORS\n\nbody"
        toc = extract_toc(md)
        assert [(e["level"], e["title"], e["offset"]) for e in toc] == [(5, "RISK FACTORS", 6)]

    def test_bare_hash_line_is_not_a_heading(self):
        # A "##" with no same-line text must not swallow the newline and
        # claim the next line as its title (234 corpus docs have these)
        toc = extract_toc("##\n\nnot a title\n\n## Real Heading\n")
        assert [(e["title"], e["offset"]) for e in toc] == [("Real Heading", 17)]

    def test_mojibake_titles_filtered(self):
        # CID-font extraction garbage: mostly symbols, should not become ToC
        md = "## '(7$/+$0(172 '$6 $®(6 *(!\n\n## Normal Section\n"
        assert [e["title"] for e in extract_toc(md)] == ["Normal Section"]

    def test_offset_utf16_accounts_for_astral_chars(self):
        # One astral char (surrogate pair in UTF-16) before the heading
        md = "\U0001f600 intro\n\n## After Emoji\n"
        (entry,) = extract_toc(md)
        assert md[entry["offset"]] == "#"
        assert entry["offset_utf16"] == entry["offset"] + 1


class TestResolveCountry:
    def test_known_sovereign_issuer(self):
        meta = resolve_country("FEDERATIVE REPUBLIC OF BRAZIL")
        assert meta["country_code"] == "BRA"
        assert meta["region"] == "Latin America & Caribbean"
        assert meta["is_sovereign"] is True

    def test_unknown_issuer(self):
        meta = resolve_country("NOT A REAL ISSUER")
        assert meta["country_code"] is None
        assert meta["country_name"] == "Unknown"
        assert meta["income_group"] == "Unknown"

    def test_none_issuer(self):
        assert resolve_country(None)["country_name"] == "Unknown"


_DOC_COLUMNS = (
    "document_id, storage_key, source, native_id, issuer_name, title, doc_type, "
    "publication_date, source_page_url, download_url, page_count, scope_status, "
    "is_sovereign, file_path"
)


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
            page_count INTEGER,
            scope_status VARCHAR DEFAULT 'in_scope',
            is_sovereign BOOLEAN,
            file_path VARCHAR
        )
        """
    )
    conn.execute("CREATE TABLE document_markdown (document_id INTEGER, markdown_text VARCHAR)")
    conn.execute(
        "CREATE TABLE document_pages (document_id INTEGER, page_number INTEGER, page_text VARCHAR)"
    )
    conn.execute(
        f"INSERT INTO documents ({_DOC_COLUMNS}) VALUES "
        "(1, 'nsm__111', 'nsm', '111', 'FEDERATIVE REPUBLIC OF BRAZIL', 'Brazil 2031 Notes',"
        " 'prospectus', DATE '2026-01-15', 'https://example.test/filing/111', "
        " 'https://example.test/dl/111.pdf', 2, 'in_scope', TRUE, 'data/original/nsm__111.pdf'),"
        "(2, 'edgar__222', 'edgar', '222', NULL, 'Untitled Filing', NULL, NULL,"
        " NULL, 'https://example.test/dl/222.htm', 1, 'in_scope', TRUE,"
        " 'data/original/edgar__222.htm'),"
        "(3, 'pdip__333', 'pdip', '333', 'NOBODY KNOWS', NULL, 'supplement', NULL,"
        " NULL, NULL, NULL, 'in_scope', TRUE, 'data/original/pdip__333.paper'),"
        "(9, 'nsm__999', 'nsm', '999', 'QUARANTINED ISSUER', 'Bad Parse', NULL, NULL,"
        " NULL, NULL, NULL, 'quarantine', TRUE, NULL)"
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
        # Quarantined document is excluded from the snapshot
        assert "nsm-999" not in frame["slug"].to_list()
        row = frame.filter(pl.col("slug") == "nsm-111").row(0, named=True)
        assert row["country_name"] == "Brazil"
        assert row["filing_url"] == "https://example.test/filing/111"
        assert row["has_text"] is True
        assert row["text_source"] == "markdown"
        assert row["text_bytes"] > 0
        assert row["no_text_reason"] is None

        # Markdown doc: text + toc, no page anchors
        doc1 = json.loads((out_dir / "text" / "nsm-111.json").read_text())
        assert doc1["schema_version"] == 1
        assert doc1["text_source"] == "markdown"
        assert [(e["title"], e["offset"]) for e in doc1["toc"]] == [("Terms", 7)]
        assert doc1["pages"] == []
        assert "Body text" in doc1["text"]

        # Pages-fallback doc: concatenated pages with page-boundary offsets
        doc2 = json.loads((out_dir / "text" / "edgar-222.json").read_text())
        assert doc2["text_source"] == "pages"
        assert doc2["text"] == "page one text\n\npage two text"
        assert doc2["toc"] == []
        assert doc2["pages"] == [
            {"page_number": 1, "offset": 0},
            {"page_number": 2, "offset": 15},
        ]
        assert doc2["text"][15:].startswith("page two")
        assert doc2["filing_url"] == "https://example.test/dl/222.htm"

        # Doc without text: no JSON file, reason recorded
        assert not (out_dir / "text" / "pdip-333.json").exists()
        row3 = frame.filter(pl.col("slug") == "pdip-333").row(0, named=True)
        assert row3["has_text"] is False
        assert row3["no_text_reason"] == "paper_filing"
        assert row3["country_name"] == "Unknown"

        manifest = json.loads((out_dir / "MANIFEST.json").read_text())
        assert manifest == stats  # on-disk manifest identical to returned stats
        assert manifest["unmapped_issuers"] == ["NOBODY KNOWS"]
        assert manifest["sovereign_flag_conflicts"] == []
        assert manifest["components"]["text_files"] == 2

    def test_limit(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        out_dir = tmp_path / "snapshot"

        stats = build_snapshot(db_path, out_dir, limit=1)

        assert stats["document_count"] == 1
        frame = pl.read_parquet(out_dir / "documents.parquet")
        assert frame["slug"].to_list() == ["nsm-111"]

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute(
            "CREATE TABLE documents (document_id INTEGER, storage_key VARCHAR,"
            " source VARCHAR, native_id VARCHAR, issuer_name VARCHAR, title VARCHAR,"
            " doc_type VARCHAR, publication_date DATE, source_page_url VARCHAR,"
            " download_url VARCHAR, page_count INTEGER, scope_status VARCHAR,"
            " is_sovereign BOOLEAN, file_path VARCHAR)"
        )
        conn.execute("CREATE TABLE document_markdown (document_id INTEGER, markdown_text VARCHAR)")
        conn.execute(
            "CREATE TABLE document_pages (document_id INTEGER, page_number INTEGER,"
            " page_text VARCHAR)"
        )
        conn.close()

        stats = build_snapshot(db_path, tmp_path / "snapshot")

        assert stats["document_count"] == 0
        frame = pl.read_parquet(tmp_path / "snapshot" / "documents.parquet")
        assert frame.height == 0
        assert "slug" in frame.columns

    def test_whitespace_markdown_falls_back_to_pages(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        conn = duckdb.connect(str(db_path))
        conn.execute("INSERT INTO document_markdown VALUES (2, '   \n\n  ')")
        conn.close()

        build_snapshot(db_path, tmp_path / "snapshot")

        doc2 = json.loads((tmp_path / "snapshot" / "text" / "edgar-222.json").read_text())
        assert doc2["text_source"] == "pages"
        assert doc2["text"] == "page one text\n\npage two text"

    def test_full_build_removes_stale_text_files(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        out_dir = tmp_path / "snapshot"
        (out_dir / "text").mkdir(parents=True)
        stale = out_dir / "text" / "nsm-gone.json"
        stale.write_text("{}")
        orphan = out_dir / "text" / "nsm-crash.json.part"
        orphan.write_text("truncated")

        stats = build_snapshot(db_path, out_dir)

        assert not stale.exists()
        assert not orphan.exists()
        assert stats["stale_text_files_removed"] == 1

    def test_limit_build_keeps_other_text_files(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        out_dir = tmp_path / "snapshot"
        (out_dir / "text").mkdir(parents=True)
        other = out_dir / "text" / "edgar-222.json"
        other.write_text("{}")

        stats = build_snapshot(db_path, out_dir, limit=1)

        assert other.exists()
        assert stats["stale_text_files_removed"] == 0

    def test_slug_collision_raises(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        conn = duckdb.connect(str(db_path))
        conn.execute(
            f"INSERT INTO documents ({_DOC_COLUMNS}) VALUES "
            "(4, 'nsm__111.b', 'nsm', '111.b', NULL, 'Colliding Doc', NULL, NULL,"
            " NULL, NULL, NULL, 'in_scope', TRUE, NULL),"
            "(5, 'nsm__111-b', 'nsm', '111-b', NULL, 'Colliding Doc 2', NULL, NULL,"
            " NULL, NULL, NULL, 'in_scope', TRUE, NULL)"
        )
        conn.close()

        with pytest.raises(ValueError, match="Slug collision"):
            build_snapshot(db_path, tmp_path / "snapshot")

    def test_degenerate_slug_raises(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        conn = duckdb.connect(str(db_path))
        conn.execute(
            f"INSERT INTO documents ({_DOC_COLUMNS}) VALUES "
            "(6, 'nsm__中国', 'nsm', '中国', NULL, 'CJK-only id', NULL, NULL,"
            " NULL, NULL, NULL, 'in_scope', TRUE, NULL)"
        )
        conn.close()

        with pytest.raises(ValueError, match="Degenerate slug"):
            build_snapshot(db_path, tmp_path / "snapshot")

    def test_sovereign_flag_conflict_surfaced(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        conn = duckdb.connect(str(db_path))
        # Map says Brazil is sovereign True; DB row disagrees
        conn.execute("UPDATE documents SET is_sovereign = FALSE WHERE document_id = 1")
        conn.close()

        stats = build_snapshot(db_path, tmp_path / "snapshot")

        assert stats["sovereign_flag_conflicts"] == ["FEDERATIVE REPUBLIC OF BRAZIL"]

    def test_display_name_normalized(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        _seed_db(db_path)
        conn = duckdb.connect(str(db_path))
        conn.execute(
            f"INSERT INTO documents ({_DOC_COLUMNS}) VALUES "
            "(7, 'nsm__777', 'nsm', '777', 'National Investment Fund of Somewhere;', NULL,"
            " NULL, NULL, NULL, NULL, NULL, 'in_scope', TRUE, NULL)"
        )
        conn.close()

        build_snapshot(db_path, tmp_path / "snapshot")

        frame = pl.read_parquet(tmp_path / "snapshot" / "documents.parquet")
        row = frame.filter(pl.col("slug") == "nsm-777").row(0, named=True)
        assert row["display_name"] == "National Investment Fund of Somewhere"
        assert row["issuer_name"] == "National Investment Fund of Somewhere;"  # raw preserved
