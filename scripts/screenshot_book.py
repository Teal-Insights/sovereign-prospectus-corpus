# scripts/screenshot_book.py
"""Take screenshots of rendered Quarto book pages for visual inspection.

Usage:
    uv run python3 scripts/screenshot_book.py

Outputs screenshots to demo/reviews/screenshots/ (gitignored).
Requires: quarto render demo/ to have been run first.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

BOOK_DIR = Path(__file__).resolve().parent.parent / "demo" / "_book"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "demo" / "reviews" / "screenshots"


def screenshot_book() -> None:
    html_files = sorted(BOOK_DIR.glob("*.html"))
    if not html_files:
        print(f"No HTML files in {BOOK_DIR}. Run 'quarto render demo/' first.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        for html_file in html_files:
            url = f"file://{html_file}"
            page.goto(url, wait_until="networkidle")
            out_path = OUTPUT_DIR / f"{html_file.stem}.png"
            page.screenshot(path=str(out_path), full_page=True)
            print(f"  {html_file.name} -> {out_path.name}")

        browser.close()

    print(f"\n{len(html_files)} screenshots saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    screenshot_book()
