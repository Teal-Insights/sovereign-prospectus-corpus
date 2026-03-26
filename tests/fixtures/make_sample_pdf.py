#!/usr/bin/env python3
"""Generate a minimal fixture PDF for parser tests."""

from pathlib import Path

import fitz  # PyMuPDF

FIXTURE_DIR = Path(__file__).parent
OUTPUT = FIXTURE_DIR / "sample.pdf"


def main() -> None:
    doc = fitz.open()

    # Page 1
    page1 = doc.new_page()
    page1.insert_text(
        (72, 72),
        "Republic of Testland\nSovereign Bond Prospectus\n\n"
        "This offering circular relates to the issuance of bonds by the Republic of Testland.",
        fontsize=12,
    )

    # Page 2
    page2 = doc.new_page()
    page2.insert_text(
        (72, 72),
        "Collective Action Clauses\n\n"
        "The Bonds contain collective action clauses which permit defined majorities "
        "to bind all holders.",
        fontsize=12,
    )

    doc.save(str(OUTPUT))
    doc.close()
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
