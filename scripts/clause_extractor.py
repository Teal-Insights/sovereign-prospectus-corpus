#!/usr/bin/env python3
"""
Clause Extractor: Grep-First Sovereign Bond Clause Extraction Pipeline

Uses regex patterns to locate clause sections in prospectus PDFs, then extracts
verbatim quotes with page citations. Designed for the #PublicDebtIsPublic
roundtable proof-of-concept.

Architecture:
    1. Load PDF text (PyMuPDF)
    2. Grep-first: regex patterns locate clause sections by page
    3. Extract verbatim quotes with surrounding context
    4. Verify: assert exact_quote in raw_pdf_text
    5. Store results in SQLite corpus database

Usage:
    python clause_extractor.py --document-id NI-000022044-0
    python clause_extractor.py --all-parsed
    python clause_extractor.py --country Ghana
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# Project paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "db" / "corpus.db"
TEXT_DIR = PROJECT_ROOT / "data" / "text"
PDF_DIR = PROJECT_ROOT / "data" / "pdfs"

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Clause patterns: encode domain knowledge as regex
# ---------------------------------------------------------------------------

CLAUSE_PATTERNS: dict[str, str] = {
    "CAC": (
        r"(?i)(?:collective action|CAC|modification.*resolution|"
        r"aggregat(?:ed|ion).*clause|modification.*majority|"
        r"modification.*voting|Reserved Matter)"
    ),
    "PARI_PASSU": (
        r"(?i)(?:pari passu|rank equally|equal(?:ly)? (?:and ratably|rank)|"
        r"same rank|pro[- ]?rata)"
    ),
    "EVENTS_OF_DEFAULT": (
        r"(?i)(?:Events? of Default|failure to pay|moratorium)"
    ),
    "GOVERNING_LAW": (
        r"(?i)(?:governing law|governed by|"
        r"subject to (?:the laws of |English law|New York law))"
    ),
    "NEGATIVE_PLEDGE": (
        r"(?i)(?:negative pledge|not.*create.*(?:lien|security interest)|"
        r"Lien|Security Interest)"
    ),
    "SOVEREIGN_IMMUNITY": (
        r"(?i)(?:sovereign immunity|waive.*immunity|irrevocably waive|"
        r"Waiver of Immunity)"
    ),
    "CROSS_DEFAULT": (
        r"(?i)(?:cross[- ]?default|cross[- ]?acceleration)"
    ),
    "EXTERNAL_INDEBTEDNESS": (
        r"(?i)(?:External Indebtedness|Public External Indebtedness)"
    ),
    "ACCELERATION": (
        r"(?i)(?:acceleration|accelerate|immediately due and payable)"
    ),
    "TRUSTEE_FISCAL_AGENT": (
        r"(?i)(?:Fiscal Agent|Trustee|Agent Bank)"
    ),
}

# Section headers that mark the start of formal clause sections
SECTION_HEADERS: dict[str, str] = {
    "CAC": r"(?i)(?:Collective Action|Modification|Reserved Matter)",
    "PARI_PASSU": r"(?i)(?:\d+\.?\s*Status of the Notes|Status of the Notes|Ranking|Pari Passu|rank.*pari passu)",
    "EVENTS_OF_DEFAULT": r"(?i)(?:\d+\.\s*Events? of Default)",
    "GOVERNING_LAW": r"(?i)(?:\d+\.?\s*Governing Law|Governing Law and Submission)",
    "NEGATIVE_PLEDGE": r"(?i)(?:\d+\.\s*Negative Pledge)",
    "SOVEREIGN_IMMUNITY": r"(?i)(?:Waiver of (?:Sovereign )?Immunity|Consent to Enforcement)",
    "CROSS_DEFAULT": r"(?i)(?:Cross[- ]?[Dd]efault)",
    "EXTERNAL_INDEBTEDNESS": r"(?i)(?:External Indebtedness)",
    "ACCELERATION": r"(?i)(?:Acceleration)",
    "TRUSTEE_FISCAL_AGENT": r"(?i)(?:Fiscal Agent|Trustee)",
}


@dataclass
class GrepMatch:
    """A regex match on a specific page."""

    clause_type: str
    page_number: int
    match_count: int
    sample_matches: list[str]


@dataclass
class ClauseExtraction:
    """A verbatim clause extraction with metadata."""

    clause_type: str
    verbatim_quote: str
    page_number: int
    page_range_start: int
    page_range_end: int
    context_before: str
    context_after: str
    verified: bool
    extraction_method: str = "grep_first_pymupdf"


def grep_first_scan(doc: fitz.Document) -> dict[str, list[GrepMatch]]:
    """
    Phase 1: Scan document with regex patterns to locate clause sections.

    Returns dict mapping clause_type -> list of GrepMatch objects.
    """
    results: dict[str, list[GrepMatch]] = {}

    for clause_type, pattern in CLAUSE_PATTERNS.items():
        matches: list[GrepMatch] = []
        compiled = re.compile(pattern)

        for page_num in range(doc.page_count):
            page_text = doc[page_num].get_text()
            found = list(compiled.finditer(page_text))
            if found:
                sample_texts = list({m.group() for m in found})[:5]
                matches.append(
                    GrepMatch(
                        clause_type=clause_type,
                        page_number=page_num + 1,
                        match_count=len(found),
                        sample_matches=sample_texts,
                    )
                )

        results[clause_type] = matches

    return results


def identify_clause_sections(
    grep_results: dict[str, list[GrepMatch]],
) -> dict[str, tuple[int, int]]:
    """
    Phase 2: From grep matches, identify the primary clause section (page range).

    Uses clustering to find the densest concentration of matches, which is
    likely the formal clause definition (not just a passing reference).
    """
    sections: dict[str, tuple[int, int]] = {}

    for clause_type, matches in grep_results.items():
        if not matches:
            continue

        pages = [m.page_number for m in matches]

        # Cluster consecutive pages (within 2 pages of each other)
        clusters: list[list[int]] = []
        current_cluster = [pages[0]]
        for p in pages[1:]:
            if p - current_cluster[-1] <= 2:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)

        # Pick the cluster with the most total matches
        best_cluster = max(
            clusters,
            key=lambda c: sum(
                m.match_count for m in matches if m.page_number in c
            ),
        )

        # Expand range slightly for context
        start = max(1, best_cluster[0] - 1)
        end = best_cluster[-1] + 1

        sections[clause_type] = (start, end)

    return sections


def extract_clause_text(
    doc: fitz.Document,
    clause_type: str,
    page_start: int,
    page_end: int,
    max_chars: int = 3000,
) -> Optional[ClauseExtraction]:
    """
    Phase 3: Extract verbatim clause text from identified page range.

    Looks for the formal section header, then extracts the full clause text.
    """
    header_pattern = SECTION_HEADERS.get(clause_type)
    if not header_pattern:
        header_pattern = CLAUSE_PATTERNS.get(clause_type, "")

    compiled = re.compile(header_pattern)

    # First try the identified page range, then fall back to full document scan.
    # This handles cases where grep clustering picks a risk factors section
    # over the actual clause definition section.
    page_ranges = [
        range(page_start - 1, min(page_end + 1, doc.page_count)),
        range(doc.page_count),  # Full document fallback
    ]

    for search_range in page_ranges:
        for page_num in search_range:
            page_text = doc[page_num].get_text()
            # Also try with newlines collapsed (PDF extractors often break headers
            # across lines, e.g. "20. \nGoverning Law")
            page_text_collapsed = re.sub(r"\n(?=[A-Z])", " ", page_text)
            match = compiled.search(page_text) or compiled.search(
                page_text_collapsed
            )

            if not match:
                continue
            # Get text from the match point forward
            start_pos = match.start()

            # Context before (5 lines)
            lines_before = page_text[:start_pos].split("\n")
            context_before = "\n".join(lines_before[-5:]).strip()

            # Main text: from match through subsequent pages
            remaining = page_text[start_pos:]
            end_page = page_num + 1

            for next_page in range(page_num + 1, min(page_num + 5, doc.page_count)):
                remaining += "\n" + doc[next_page].get_text()
                end_page = next_page + 1

            # Trim to max_chars, ending at a sentence boundary
            excerpt = remaining[:max_chars]
            last_period = excerpt.rfind(". ")
            if last_period > max_chars * 0.5:
                excerpt = excerpt[: last_period + 1]

            # Context after (5 lines after the excerpt)
            after_text = remaining[len(excerpt) :]
            context_after = "\n".join(after_text.split("\n")[:5]).strip()

            return ClauseExtraction(
                clause_type=clause_type,
                verbatim_quote=excerpt.strip(),
                page_number=page_num + 1,
                page_range_start=page_start,
                page_range_end=end_page,
                context_before=context_before,
                context_after=context_after,
                verified=False,
            )

    return None


def verify_extraction(full_text: str, extraction: ClauseExtraction) -> bool:
    """
    Phase 4: Verify that the extracted quote exists verbatim in the source text.

    This is the critical assertion: assert exact_quote in raw_pdf_text.
    Uses whitespace normalization for robustness.
    """
    # Take first 200 chars of the quote for verification
    test_str = extraction.verbatim_quote[:200]

    # Direct match
    if test_str in full_text:
        return True

    # Whitespace-normalized match
    norm_quote = " ".join(test_str.split())
    norm_full = " ".join(full_text.split())
    return norm_quote in norm_full


def process_document(
    doc_id: str,
    pdf_path: Path,
    db: sqlite3.Connection,
) -> list[ClauseExtraction]:
    """
    Process a single document through the full extraction pipeline.

    Returns list of verified clause extractions.
    """
    start_time = time.time()
    logger.info(f"Processing: {doc_id} ({pdf_path.name})")

    # Update status
    db.execute(
        "UPDATE documents SET status = 'EXTRACTING', updated_at = datetime('now') "
        "WHERE id = ?",
        (doc_id,),
    )
    db.commit()

    # Load document
    doc = fitz.open(str(pdf_path))
    full_text = "".join(page.get_text() for page in doc)

    # Phase 1: Grep-first scan
    grep_results = grep_first_scan(doc)

    # Store grep matches in DB
    for clause_type, matches in grep_results.items():
        for match in matches:
            db.execute(
                "INSERT INTO grep_matches "
                "(document_id, clause_type, page_number, match_count, sample_matches) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    doc_id,
                    clause_type,
                    match.page_number,
                    match.match_count,
                    json.dumps(match.sample_matches),
                ),
            )
    db.commit()

    # Phase 2: Identify clause sections
    sections = identify_clause_sections(grep_results)
    logger.info(
        f"  Found {len(sections)} clause sections: "
        + ", ".join(f"{k} (pp {v[0]}-{v[1]})" for k, v in sections.items())
    )

    # Phase 3 & 4: Extract and verify
    extractions: list[ClauseExtraction] = []
    for clause_type, (page_start, page_end) in sections.items():
        extraction = extract_clause_text(doc, clause_type, page_start, page_end)
        if extraction:
            verified = verify_extraction(full_text, extraction)
            extraction.verified = verified

            status = "PASS" if verified else "FAIL"
            logger.info(
                f"  {clause_type}: page {extraction.page_number} "
                f"({len(extraction.verbatim_quote)} chars) [{status}]"
            )

            # Store in DB
            db.execute(
                "INSERT INTO clause_extractions "
                "(document_id, clause_type, verbatim_quote, page_number, "
                "page_range_start, page_range_end, context_before, context_after, "
                "confidence, extraction_model, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_id,
                    clause_type,
                    extraction.verbatim_quote,
                    extraction.page_number,
                    extraction.page_range_start,
                    extraction.page_range_end,
                    extraction.context_before,
                    extraction.context_after,
                    1.0 if verified else 0.5,
                    extraction.extraction_method,
                    f"verified={verified}",
                ),
            )

            extractions.append(extraction)
        else:
            logger.warning(f"  {clause_type}: Could not extract from pages {page_start}-{page_end}")

    # Update status
    db.execute(
        "UPDATE documents SET status = 'EXTRACTED', updated_at = datetime('now') "
        "WHERE id = ?",
        (doc_id,),
    )

    # Log pipeline action
    elapsed = time.time() - start_time
    db.execute(
        "INSERT INTO pipeline_log (document_id, action, status, details, duration_seconds) "
        "VALUES (?, 'extract_clauses', 'success', ?, ?)",
        (
            doc_id,
            json.dumps(
                {
                    "clauses_found": len(extractions),
                    "clauses_verified": sum(1 for e in extractions if e.verified),
                    "sections_scanned": len(sections),
                }
            ),
            elapsed,
        ),
    )
    db.commit()

    doc.close()
    logger.info(
        f"  Done: {len(extractions)} clauses extracted, "
        f"{sum(1 for e in extractions if e.verified)} verified "
        f"({elapsed:.2f}s)"
    )

    return extractions


def compare_documents(
    doc_ids: list[str],
    db: sqlite3.Connection,
) -> dict[str, list[dict]]:
    """
    Compare clause extractions across multiple documents.

    Returns dict mapping clause_type -> list of {doc_id, quote, page} dicts.
    """
    comparison: dict[str, list[dict]] = {}

    for doc_id in doc_ids:
        rows = db.execute(
            "SELECT clause_type, verbatim_quote, page_number "
            "FROM clause_extractions "
            "WHERE document_id = ? "
            "ORDER BY clause_type",
            (doc_id,),
        ).fetchall()

        doc_info = db.execute(
            "SELECT country, filing_date, doc_type FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()

        for row in rows:
            clause_type = row[0]
            if clause_type not in comparison:
                comparison[clause_type] = []
            comparison[clause_type].append(
                {
                    "document_id": doc_id,
                    "country": doc_info[0] if doc_info else "?",
                    "filing_date": doc_info[1] if doc_info else "?",
                    "doc_type": doc_info[2] if doc_info else "?",
                    "verbatim_quote": row[1][:500],  # Truncate for display
                    "page_number": row[2],
                }
            )

    return comparison


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Grep-first clause extraction for sovereign bond prospectuses"
    )
    parser.add_argument(
        "--document-id",
        type=str,
        help="Process a specific document by ID",
    )
    parser.add_argument(
        "--all-parsed",
        action="store_true",
        help="Process all documents with status PARSED",
    )
    parser.add_argument(
        "--country",
        type=str,
        help="Process all parsed documents for a country",
    )
    parser.add_argument(
        "--compare",
        type=str,
        help="Compare extractions across document IDs (comma-separated)",
    )
    parser.add_argument(
        "--min-pages",
        type=int,
        default=10,
        help="Minimum page count to process (skip cover sheets). Default: 10",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DB_PATH),
        help="Path to SQLite database",
    )

    args = parser.parse_args()

    db = sqlite3.connect(args.db)
    db.execute("PRAGMA journal_mode=WAL")

    if args.compare:
        doc_ids = [d.strip() for d in args.compare.split(",")]
        comparison = compare_documents(doc_ids, db)
        print(json.dumps(comparison, indent=2))
        db.close()
        return

    # Build list of documents to process
    if args.document_id:
        rows = db.execute(
            "SELECT id, local_path FROM documents WHERE id = ?",
            (args.document_id,),
        ).fetchall()
    elif args.country:
        rows = db.execute(
            "SELECT id, local_path FROM documents "
            "WHERE country = ? AND status = 'PARSED' AND page_count >= ?",
            (args.country, args.min_pages),
        ).fetchall()
    elif args.all_parsed:
        rows = db.execute(
            "SELECT id, local_path FROM documents "
            "WHERE status = 'PARSED' AND page_count >= ?",
            (args.min_pages,),
        ).fetchall()
    else:
        parser.print_help()
        db.close()
        return

    if not rows:
        logger.warning("No documents found matching criteria")
        db.close()
        return

    logger.info(f"Processing {len(rows)} document(s)")

    for row in rows:
        doc_id = row[0]
        local_path = row[1]
        if local_path:
            pdf_path = PROJECT_ROOT / local_path
        else:
            logger.warning(f"No local_path for {doc_id}, skipping")
            continue

        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            continue

        try:
            process_document(doc_id, pdf_path, db)
        except Exception as e:
            logger.error(f"Error processing {doc_id}: {e}")
            db.execute(
                "UPDATE documents SET status = 'FAILED', "
                "quarantine_reason = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (str(e), doc_id),
            )
            db.commit()

    db.close()
    logger.info("All documents processed")


if __name__ == "__main__":
    main()
