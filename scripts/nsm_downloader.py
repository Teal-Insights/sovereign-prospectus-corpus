#!/usr/bin/env python3
"""
NSM Downloader: Sovereign Bond Prospectus Retrieval Pipeline

Downloads prospectuses from the FCA National Storage Mechanism (NSM) for sovereign
issuers. Handles two-hop resolution (HTML metadata pages -> PDF links), resumable
downloads, and comprehensive error logging.

Usage:
    python nsm_downloader.py [--countries COUNTRY1,COUNTRY2,...] [--checkpoint CHECKPOINT.json]

Default: Download for all priority countries in order (Ghana, Zambia, Sri Lanka, ...)
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Constants
NSM_API_URL = "https://api.data.fca.org.uk/search?index=fca-nsm-searchdata"
PDF_HEADER = b"%PDF"
DEFAULT_TIMEOUT = 60
BACKOFF_FACTOR = 0.5
MAX_RETRIES = 5
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Default countries to download (priority order)
PRIORITY_COUNTRIES = [
    "Ghana",
    "Zambia",
    "Sri Lanka",
    "Ukraine",
    "Kenya",
    "Nigeria",
    "Serbia",
    "UAE - Abu Dhabi",
    "Saudi Arabia",
    "Angola",
]

# Document types that are prospectuses (not tender offers, issues, etc.)
PROSPECTUS_TYPES = {
    "Publication of a Prospectus",
    "Base Prospectus",
    "Publication of a Supplementary Prospectus",
}

# Base directory for script
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
for directory in [PDF_DIR, PROCESSED_DIR, LOGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Logging setup
LOG_FILE = LOGS_DIR / f"nsm_downloader_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(levelname)s: %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


class NSMDownloader:
    """Download sovereign bond prospectuses from FCA NSM API."""

    def __init__(self, checkpoint_file: Optional[Path] = None):
        """
        Initialize downloader with optional checkpoint for resumability.

        Args:
            checkpoint_file: Path to JSON checkpoint file with download status
        """
        self.session = self._create_session()
        self.checkpoint_file = checkpoint_file or PROCESSED_DIR / "download_checkpoint.json"
        self.checkpoint = self._load_checkpoint()
        self.downloads_log = PROCESSED_DIR / "downloads.jsonl"

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(REQUEST_HEADERS)
        return session

    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load existing checkpoint or create new one."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, "r") as f:
                checkpoint = json.load(f)
            logger.info(f"Loaded checkpoint: {len(checkpoint.get('downloaded', []))} already downloaded")
            return checkpoint
        else:
            return {
                "downloaded": [],
                "failed": [],
                "last_updated": datetime.now().isoformat(),
            }

    def _save_checkpoint(self) -> None:
        """Save checkpoint to file."""
        self.checkpoint["last_updated"] = datetime.now().isoformat()
        with open(self.checkpoint_file, "w") as f:
            json.dump(self.checkpoint, f, indent=2)
        logger.debug(f"Checkpoint saved: {len(self.checkpoint['downloaded'])} downloaded")

    def _is_pdf_valid(self, content: bytes) -> bool:
        """Validate PDF by checking header."""
        return content.startswith(PDF_HEADER)

    def _resolve_pdf_url(self, url: str) -> Optional[str]:
        """
        Resolve PDF URL, handling two-hop case (HTML metadata page -> PDF link).

        Args:
            url: URL to PDF or HTML metadata page

        Returns:
            Direct PDF URL if resolvable, None otherwise
        """
        try:
            response = self.session.head(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
            
            # If it's a PDF, return as-is
            if "application/pdf" in response.headers.get("content-type", ""):
                return url
            
            # Otherwise, try to fetch as HTML and extract PDF link
            if "text/html" in response.headers.get("content-type", ""):
                response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Look for common PDF link patterns
                pdf_link = None
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if href.lower().endswith(".pdf"):
                        pdf_link = urljoin(url, href)
                        break
                
                # Also check for common button/link text patterns
                if not pdf_link:
                    for link in soup.find_all("a", href=True):
                        text = (link.get_text() or "").lower()
                        if "pdf" in text or "download" in text:
                            href = link["href"]
                            if href.endswith(".pdf"):
                                pdf_link = urljoin(url, href)
                                break
                
                return pdf_link
            
            logger.warning(f"Unexpected content type for {url}: {response.headers.get('content-type')}")
            return None
        except Exception as e:
            logger.warning(f"Error resolving URL {url}: {e}")
            return None

    def _download_pdf(self, pdf_url: str, target_path: Path) -> bool:
        """
        Download PDF from URL with validation.

        Args:
            pdf_url: Direct URL to PDF file
            target_path: Path to save PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.session.get(pdf_url, timeout=DEFAULT_TIMEOUT, stream=True)
            response.raise_for_status()
            
            content = response.content
            if not self._is_pdf_valid(content):
                logger.warning(f"Invalid PDF header at {pdf_url}")
                return False
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, "wb") as f:
                f.write(content)
            
            logger.info(f"Downloaded: {target_path.name} ({len(content) / 1024:.1f} KB)")
            return True
        except Exception as e:
            logger.error(f"Error downloading {pdf_url}: {e}")
            return False

    def _query_nsm_api(self, country: str, from_offset: int = 0, size: int = 100) -> Optional[Dict[str, Any]]:
        """
        Query NSM API for a specific country.

        Args:
            country: Country name to search
            from_offset: Pagination offset
            size: Number of results per page

        Returns:
            API response dict or None on error
        """
        # Load issuer reference to get LEI
        ref_csv = DATA_DIR / "raw" / "sovereign_issuer_reference.csv"
        leis = []
        
        if ref_csv.exists():
            import csv
            with open(ref_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("country", "").strip() == country:
                        lei_str = row.get("leis", "").strip()
                        if lei_str:
                            leis = [lei for lei in lei_str.split(";") if lei.strip()]
                        break
        
        # Build request body
        payload = {
            "from": from_offset,
            "size": size,
            "sort": "submitted_date",
            "sortorder": "desc",
            "criteriaObj": {
                "criteria": [
                    {"name": "latest_flag", "value": "Y"},
                ],
                "dateCriteria": [],
            },
        }
        
        # Add search criteria: try LEI first, then name
        if leis:
            for lei in leis:
                payload["criteriaObj"]["criteria"].insert(
                    0,
                    {"name": "company_lei", "value": ["", lei, "disclose_org", ""]},
                )
            logger.debug(f"Querying {country} by LEI: {leis}")
        else:
            payload["criteriaObj"]["criteria"].insert(
                0,
                {"name": "company_lei", "value": [country, "", "disclose_org", "related_org"]},
            )
            logger.debug(f"Querying {country} by name")
        
        try:
            response = self.session.post(NSM_API_URL, json=payload, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error querying NSM API for {country}: {e}")
            return None

    def _process_hit(self, hit: Dict[str, Any], country: str) -> bool:
        """
        Process a single API hit: resolve PDF URL, download, log metadata.

        Args:
            hit: Single result from NSM API
            country: Country name

        Returns:
            True if successful, False otherwise
        """
        try:
            doc_headline = hit.get("_source", {}).get("headline", "Unknown")
            filing_date = hit.get("_source", {}).get("submitted_date", "Unknown")
            doc_type = hit.get("_source", {}).get("headline_category", "Unknown")
            url = hit.get("_source", {}).get("url", "")
            lei = hit.get("_source", {}).get("company_lei", "")
            
            # Skip non-prospectus documents
            if not any(pt in doc_headline for pt in PROSPECTUS_TYPES):
                logger.debug(f"Skipping non-prospectus: {doc_headline}")
                return False
            
            # Check if already downloaded
            doc_id = hit.get("_id", "")
            if doc_id in self.checkpoint["downloaded"]:
                logger.debug(f"Already downloaded: {doc_id}")
                return False
            
            # Resolve PDF URL (handle two-hop case)
            pdf_url = self._resolve_pdf_url(url)
            if not pdf_url:
                logger.warning(f"Could not resolve PDF URL for {doc_headline}")
                self.checkpoint["failed"].append({
                    "doc_id": doc_id,
                    "reason": "URL resolution failed",
                    "headline": doc_headline,
                })
                self._save_checkpoint()
                return False
            
            # Build filename: country_date_doctype.pdf
            date_str = filing_date.split("T")[0] if filing_date != "Unknown" else "unknown"
            doctype_clean = re.sub(r"[^a-z0-9]", "_", doc_type.lower())[:20]
            filename = f"{country.lower().replace(' ', '_')}_{date_str}_{doctype_clean}.pdf"
            target_path = PDF_DIR / country.lower().replace(" ", "_") / filename
            
            # Download PDF
            success = self._download_pdf(pdf_url, target_path)
            
            # Log metadata
            if success:
                metadata = {
                    "doc_id": doc_id,
                    "country": country,
                    "headline": doc_headline,
                    "filing_date": filing_date,
                    "doc_type": doc_type,
                    "lei": lei,
                    "original_url": url,
                    "pdf_url": pdf_url,
                    "local_path": str(target_path.relative_to(PROJECT_ROOT)),
                    "downloaded_at": datetime.now().isoformat(),
                }
                with open(self.downloads_log, "a") as f:
                    f.write(json.dumps(metadata) + "\n")
                
                self.checkpoint["downloaded"].append(doc_id)
                self._save_checkpoint()
                return True
            else:
                self.checkpoint["failed"].append({
                    "doc_id": doc_id,
                    "reason": "PDF download failed",
                    "headline": doc_headline,
                })
                self._save_checkpoint()
                return False
        except Exception as e:
            logger.error(f"Error processing hit: {e}")
            return False

    def download_country(self, country: str) -> int:
        """
        Download all prospectuses for a country.

        Args:
            country: Country name

        Returns:
            Number of prospectuses downloaded
        """
        logger.info(f"Starting download for {country}...")
        downloaded_count = 0
        from_offset = 0
        page_size = 100
        
        while True:
            logger.debug(f"{country}: Fetching results from offset {from_offset}")
            response = self._query_nsm_api(country, from_offset=from_offset, size=page_size)
            
            if not response:
                logger.error(f"{country}: API query failed at offset {from_offset}")
                break
            
            hits = response.get("hits", {}).get("hits", [])
            if not hits:
                logger.info(f"{country}: No more results (total pages: {from_offset // page_size + 1})")
                break
            
            for hit in hits:
                if self._process_hit(hit, country):
                    downloaded_count += 1
                # Small delay between requests
                time.sleep(0.1)
            
            from_offset += page_size
            # Avoid infinite loops for very large result sets
            if from_offset > 10000:
                logger.warning(f"{country}: Stopping at 10,000 results")
                break
        
        logger.info(f"{country}: Downloaded {downloaded_count} prospectuses")
        return downloaded_count

    def run(self, countries: Optional[List[str]] = None) -> None:
        """
        Execute download pipeline for specified countries.

        Args:
            countries: List of countries to download. Defaults to PRIORITY_COUNTRIES.
        """
        if countries is None:
            countries = PRIORITY_COUNTRIES
        
        logger.info(f"Starting NSM downloader pipeline for {len(countries)} countries")
        logger.info(f"Log file: {LOG_FILE}")
        logger.info(f"Downloads will be saved to: {PDF_DIR}")
        
        total_downloaded = 0
        for country in countries:
            try:
                count = self.download_country(country)
                total_downloaded += count
                # Pause between countries to avoid rate limiting
                time.sleep(2)
            except KeyboardInterrupt:
                logger.info("Interrupted by user. Checkpoint saved.")
                break
            except Exception as e:
                logger.error(f"Unexpected error for {country}: {e}")
                continue
        
        logger.info(f"Pipeline complete. Total downloaded: {total_downloaded}")
        logger.info(f"Checkpoint saved: {self.checkpoint_file}")
        logger.info(f"Metadata log: {self.downloads_log}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download sovereign bond prospectuses from FCA NSM"
    )
    parser.add_argument(
        "--countries",
        type=str,
        default=None,
        help="Comma-separated list of countries (default: all priority countries)",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to checkpoint JSON file for resuming downloads",
    )
    
    args = parser.parse_args()
    
    countries = None
    if args.countries:
        countries = [c.strip() for c in args.countries.split(",")]
    
    checkpoint_file = None
    if args.checkpoint:
        checkpoint_file = Path(args.checkpoint)
    
    downloader = NSMDownloader(checkpoint_file=checkpoint_file)
    downloader.run(countries=countries)


if __name__ == "__main__":
    main()
