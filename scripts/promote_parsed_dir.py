#!/usr/bin/env python3
"""Promote parsed_docling/ to parsed/ and re-parse EDGAR HTML files.

Strategy (from spec v2):
1. Rename data/parsed/ → data/parsed.pymupdf.bak/ (backup old PyMuPDF outputs)
2. Rename data/parsed_docling/ → data/parsed/ (promote Docling outputs)
3. Re-run `corpus parse --source edgar` to regenerate EDGAR HTML/TXT outputs

Result: one authoritative data/parsed/ directory with Docling for PDFs
and HTMLParser for EDGAR.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSED_DIR = PROJECT_ROOT / "data" / "parsed"
DOCLING_DIR = PROJECT_ROOT / "data" / "parsed_docling"
BACKUP_DIR = PROJECT_ROOT / "data" / "parsed.pymupdf.bak"


def main() -> None:
    # Step 1: Backup old parsed dir
    if PARSED_DIR.exists():
        if BACKUP_DIR.exists():
            print(f"Backup already exists at {BACKUP_DIR}, removing old backup...")
            shutil.rmtree(BACKUP_DIR)
        print(f"Backing up {PARSED_DIR} → {BACKUP_DIR}")
        PARSED_DIR.rename(BACKUP_DIR)
    else:
        print(f"No existing {PARSED_DIR} to back up")

    # Step 2: Promote Docling outputs
    if not DOCLING_DIR.exists():
        print(f"ERROR: {DOCLING_DIR} does not exist. Run the overnight parse first.")
        sys.exit(1)

    print(f"Promoting {DOCLING_DIR} → {PARSED_DIR}")
    DOCLING_DIR.rename(PARSED_DIR)

    # Step 3: Re-parse EDGAR
    print("Re-parsing EDGAR HTML/TXT files...")
    result = subprocess.run(
        ["uv", "run", "corpus", "parse", "run", "--source", "edgar", "--run-id", "edgar-reparse"],
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    if result.returncode != 0:
        print(f"WARNING: EDGAR re-parse exited with code {result.returncode}")
    else:
        print("EDGAR re-parse complete")

    print("Done. data/parsed/ now contains Docling PDF outputs + EDGAR HTML outputs.")


if __name__ == "__main__":
    main()
