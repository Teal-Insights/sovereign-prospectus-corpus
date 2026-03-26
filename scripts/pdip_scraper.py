#!/usr/bin/env python3
"""
PDIP (Public Debt Is Public) Scraper
Comprehensive downloader for Georgetown's sovereign debt document corpus
API: https://publicdebtispublic.mdi.georgetown.edu/api/

The API requires browser-like headers (Sec-Fetch-Site: same-origin) to
authenticate. No login or token needed — just proper request headers.

This script:
1. Enumerates all documents via paginated search API
2. Saves complete metadata (JSON + CSV)
3. Downloads PDFs with atomic writes and resumability
4. Provides CLI for metadata, download, and stats commands
"""

import argparse
import csv
import json
import logging
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests
import urllib3

# Suppress SSL warnings (for development with self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
PDIP_API_BASE = "https://publicdebtispublic.mdi.georgetown.edu/api"
SEARCH_ENDPOINT = f"{PDIP_API_BASE}/search/"
PDF_ENDPOINT_TEMPLATE = f"{PDIP_API_BASE}/pdf"

# Rate limiting
REQUEST_DELAY_SECONDS = 0.5

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PDIPScraper:
    """Main scraper class for PDIP documents."""

    def __init__(self, base_path: Path, auth_token: Optional[str] = None):
        self.base_path = Path(base_path)
        self.data_dir = self.base_path / "data" / "pdip"
        self.pdfs_dir = self.base_path / "data" / "pdfs" / "pdip"
        
        # Create directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdfs_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.data_dir / "metadata.json"
        self.csv_file = self.data_dir / "pdip_document_inventory.csv"
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/134.0.0.0 Safari/537.36"
            ),
            "Origin": "https://publicdebtispublic.mdi.georgetown.edu",
            "Referer": "https://publicdebtispublic.mdi.georgetown.edu/search/",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
        # Disable SSL verification for development
        self.session.verify = False

        # Add authentication if provided
        if auth_token:
            self.session.headers.update({
                "Authorization": f"Bearer {auth_token}"
            })
            logger.info("Authentication token configured")

    def _delay(self):
        """Polite rate limiting."""
        time.sleep(REQUEST_DELAY_SECONDS)

    def fetch_metadata(self) -> dict:
        """
        Fetch all documents from PDIP search API via pagination.
        Returns: {"total": int, "results": [{"id": str, ...}, ...]}
        
        NOTE: As of 2026-03-25, this endpoint returns 401 Unauthorized.
        Possible solutions:
        1. Pass auth token via --token parameter
        2. Contact PDIP/Georgetown for API access
        3. Use web scraping approach (in development)
        """
        logger.info("Starting metadata collection from PDIP API...")
        logger.info(f"Endpoint: {SEARCH_ENDPOINT}")
        
        all_results = []
        page = 1
        page_size = 100
        total_documents = None
        last_error = None
        
        while True:
            self._delay()
            
            payload = {
                "filters": {},
                "page": page,
                "pageSize": page_size,
                "sortBy": "date",
                "sortOrder": "asc"
            }
            
            try:
                logger.info(f"Fetching page {page} (pageSize={page_size})...")
                response = self.session.post(SEARCH_ENDPOINT, json=payload, timeout=30)
                
                if response.status_code == 401:
                    logger.error("API returned 401 Unauthorized")
                    logger.error("The PDIP API requires authentication.")
                    logger.error("Possible solutions:")
                    logger.error("  1. Provide auth token: python pdip_scraper.py metadata --token YOUR_TOKEN")
                    logger.error("  2. Contact Georgetown Law (Massive Data Institute)")
                    logger.error("  3. Check if API access has changed since documentation was written")
                    raise RuntimeError("API Authentication Required")
                
                response.raise_for_status()
                
                data = response.json()
                total_documents = data.get("total", 0)
                results = data.get("results", [])
                
                logger.info(f"Page {page}: got {len(results)} documents (total: {total_documents})")
                
                all_results.extend(results)
                
                # Check if we've fetched all documents
                if len(all_results) >= total_documents:
                    break
                
                page += 1
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.error(f"API error on page {page}: {type(e).__name__}: {e}")
                raise
            except RuntimeError as e:
                logger.error(str(e))
                raise
        
        logger.info(f"Metadata collection complete: {len(all_results)} documents")
        
        return {
            "total": total_documents,
            "results": all_results,
            "fetch_timestamp": datetime.now().isoformat()
        }

    def save_metadata_json(self, metadata: dict):
        """Save raw API response to JSON."""
        logger.info(f"Saving metadata to {self.metadata_file}...")
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved {len(metadata['results'])} documents to {self.metadata_file}")

    def save_metadata_csv(self, metadata: dict):
        """Save summarized metadata to CSV."""
        logger.info(f"Saving CSV inventory to {self.csv_file}...")
        
        rows = []
        for doc in metadata["results"]:
            meta = doc.get("metadata", {})
            # Helper to join list values for CSV
            def _join(val):
                if isinstance(val, list):
                    return "; ".join(str(v) for v in val if v)
                return str(val) if val else ""

            row = {
                "id": doc.get("id", ""),
                "document_title": doc.get("document_title", ""),
                "tag_status": doc.get("tag_status", ""),
                "country": _join(meta.get("DebtorCountry", "")),
                "instrument_type": _join(meta.get("InstrumentType", "")),
                "creditor_country": _join(meta.get("CreditorCountry", "")),
                "creditor_type": _join(meta.get("CreditorType", "")),
                "entity_type": _join(meta.get("BorrowerEntityType", "")),
                "document_date": _join(meta.get("DocumentDate", "")),
                "maturity_date": _join(meta.get("InstrumentMaturityDate", "")),
            }
            rows.append(row)
        
        fieldnames = [
            "id",
            "document_title",
            "tag_status",
            "country",
            "instrument_type",
            "creditor_country",
            "creditor_type",
            "entity_type",
            "document_date",
            "maturity_date",
        ]
        
        with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"Saved CSV with {len(rows)} documents to {self.csv_file}")

    def download_pdfs(
        self,
        countries: Optional[list[str]] = None,
        annotated_only: bool = False,
    ):
        """
        Download PDFs from PDIP.
        
        Args:
            countries: List of country codes (e.g., ["Ghana", "Senegal"]). None = all.
            annotated_only: If True, only download documents with tag_status="Annotated".
        """
        # Load metadata
        if not self.metadata_file.exists():
            logger.error(f"Metadata file not found: {self.metadata_file}")
            logger.error("Run 'python pdip_scraper.py metadata' first.")
            return
        
        with open(self.metadata_file) as f:
            metadata = json.load(f)
        
        results = metadata.get("results", [])
        
        # Filter documents
        to_download = []
        for doc in results:
            # Filter by annotation status
            if annotated_only and doc.get("tag_status") != "Annotated":
                continue
            
            # Filter by country
            if countries:
                doc_countries = doc.get("metadata", {}).get("DebtorCountry", [])
                if isinstance(doc_countries, str):
                    doc_countries = [doc_countries]
                doc_countries_lower = [c.lower() for c in doc_countries if c]
                countries_lower = [c.lower() for c in countries]
                if not any(dc in countries_lower for dc in doc_countries_lower):
                    continue
            
            to_download.append(doc)
        
        logger.info(f"Will download {len(to_download)} documents")
        
        # Download each PDF
        downloaded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, doc in enumerate(to_download, 1):
            doc_id = doc.get("id", "")
            raw_country = doc.get("metadata", {}).get("DebtorCountry", ["unknown"])
            if isinstance(raw_country, list):
                country = raw_country[0] if raw_country else "unknown"
            else:
                country = raw_country
            country_code = country.lower().replace(" ", "_")
            
            # Determine target path
            country_dir = self.pdfs_dir / country_code
            country_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = country_dir / f"{doc_id}.pdf"
            part_path = country_dir / f"{doc_id}.pdf.part"
            
            # Check if already downloaded
            if pdf_path.exists():
                logger.info(f"[{i}/{len(to_download)}] {doc_id}: already downloaded, skipping")
                skipped_count += 1
                continue
            
            # Download to .part file
            url = f"{PDF_ENDPOINT_TEMPLATE}/{doc_id}"
            try:
                logger.info(f"[{i}/{len(to_download)}] {doc_id}: downloading from {url}...")
                self._delay()
                response = self.session.get(url, timeout=30, stream=True)
                response.raise_for_status()
                
                # Write to .part file
                with open(part_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Verify file size (basic check)
                if part_path.stat().st_size == 0:
                    logger.warning(f"{doc_id}: downloaded file is empty, removing")
                    part_path.unlink()
                    failed_count += 1
                    continue
                
                # Atomic rename
                part_path.rename(pdf_path)
                file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
                logger.info(f"[{i}/{len(to_download)}] {doc_id}: saved ({file_size_mb:.2f} MB)")
                downloaded_count += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"[{i}/{len(to_download)}] {doc_id}: download failed: {e}")
                try:
                    if part_path.exists():
                        part_path.unlink()
                except OSError:
                    logger.warning(f"{doc_id}: could not remove .part file")
                failed_count += 1
            except IOError as e:
                logger.error(f"[{i}/{len(to_download)}] {doc_id}: file write error: {e}")
                try:
                    if part_path.exists():
                        part_path.unlink()
                except OSError:
                    logger.warning(f"{doc_id}: could not remove .part file")
                failed_count += 1
        
        logger.info(f"\nDownload summary:")
        logger.info(f"  Downloaded: {downloaded_count}")
        logger.info(f"  Skipped (already present): {skipped_count}")
        logger.info(f"  Failed: {failed_count}")

    def print_stats(self):
        """Print summary statistics."""
        if not self.metadata_file.exists():
            logger.error(f"Metadata file not found: {self.metadata_file}")
            return
        
        with open(self.metadata_file) as f:
            metadata = json.load(f)
        
        results = metadata.get("results", [])
        total = metadata.get("total", 0)
        
        # Count by country
        countries = {}
        annotated_count = 0
        for doc in results:
            meta_country = doc.get("metadata", {}).get("DebtorCountry", ["Unknown"])
            # Handle both string and list formats
            if isinstance(meta_country, list):
                country = meta_country[0] if meta_country else "Unknown"
            else:
                country = meta_country
            countries[country] = countries.get(country, 0) + 1
            if doc.get("tag_status") == "Annotated":
                annotated_count += 1
        
        # Count PDFs downloaded
        pdf_count = 0
        for pdf_file in self.pdfs_dir.rglob("*.pdf"):
            pdf_count += 1
        
        print("\n" + "=" * 70)
        print("PDIP Document Corpus Statistics")
        print("=" * 70)
        print(f"Total documents in PDIP: {total}")
        print(f"Documents with metadata: {len(results)}")
        print(f"Annotated documents: {annotated_count}")
        print(f"PDFs downloaded locally: {pdf_count}")
        print(f"\nMetadata file: {self.metadata_file}")
        print(f"CSV inventory: {self.csv_file}")
        print(f"PDFs directory: {self.pdfs_dir}")
        
        if countries:
            print(f"\nDocuments by country:")
            for country in sorted(countries.keys()):
                count = countries[country]
                print(f"  {country:30s}: {count:4d}")
        
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="PDIP (Public Debt Is Public) Document Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch metadata only
  python pdip_scraper.py metadata

  # Fetch metadata with authentication token
  python pdip_scraper.py metadata --token YOUR_JWT_TOKEN

  # Print statistics
  python pdip_scraper.py stats

  # Download all PDFs
  python pdip_scraper.py download --all

  # Download PDFs for specific countries
  python pdip_scraper.py download --countries ghana,senegal

  # Download only annotated documents
  python pdip_scraper.py download --annotated-only

AUTHENTICATION NOTE:
As of 2026-03-25, the PDIP API requires authentication. Possible solutions:
1. Contact Georgetown Law / Massive Data Institute for API access
2. Check if PDIP has published an API key or public endpoint
3. Use the --token parameter with a JWT bearer token if you have one
4. Wait for the API to be made public
        """,
    )
    
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="JWT authentication token for PDIP API",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Metadata command
    subparsers.add_parser("metadata", help="Fetch and save metadata from PDIP API")
    
    # Stats command
    subparsers.add_parser("stats", help="Print corpus statistics")
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download PDFs")
    download_parser.add_argument(
        "--all",
        action="store_true",
        help="Download all documents",
    )
    download_parser.add_argument(
        "--countries",
        type=str,
        help="Comma-separated country names (e.g., 'Ghana,Senegal')",
    )
    download_parser.add_argument(
        "--annotated-only",
        action="store_true",
        help="Only download annotated documents",
    )
    
    args = parser.parse_args()
    
    # Determine base path (script directory's parent = project root)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    scraper = PDIPScraper(project_root, auth_token=args.token)
    
    if args.command == "metadata":
        try:
            metadata = scraper.fetch_metadata()
            scraper.save_metadata_json(metadata)
            scraper.save_metadata_csv(metadata)
            logger.info("Metadata collection complete")
        except RuntimeError as e:
            logger.error(f"Failed to fetch metadata: {e}")
            sys.exit(1)
        
    elif args.command == "stats":
        scraper.print_stats()
        
    elif args.command == "download":
        countries = None
        if args.countries:
            countries = [c.strip() for c in args.countries.split(",")]
        
        scraper.download_pdfs(
            countries=countries,
            annotated_only=args.annotated_only,
        )
        
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
