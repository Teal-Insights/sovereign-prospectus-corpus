#!/usr/bin/env python3
"""
PublicDebtIsPublic Data Extraction Script Template
===================================================

This script provides the framework for extracting annotation data from the PDIP platform.
Supports three phases:
  Phase 1: Document inventory scraping
  Phase 2: Clause annotation extraction
  Phase 3: Full clause text extraction

Usage:
    python pdip_extraction_script_template.py --phase 1 --output documents.csv
    python pdip_extraction_script_template.py --phase 2 --input documents.csv --output clauses.csv
    python pdip_extraction_script_template.py --phase 3 --input clauses.csv --output clause_texts.json
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://publicdebtispublic.mdi.georgetown.edu"
REQUEST_DELAY = 1.5  # seconds between requests (respectful scraping)
MAX_RETRIES = 3
TIMEOUT = 30

# Clause categories and types (from reconnaissance)
CLAUSE_CATEGORIES = {
    'Financial Terms': [
        'Commitment', 'Currency of Denomination and/or Payment', 'Exchange-eligible debt',
        'Final Repayment/Maturity Date(s)', 'Interest', 'Fees', 'Purpose', 'Maturity',
        'Use of Proceeds'
    ],
    'Disbursement': [
        'Utilization/Borrowing'
    ],
    'Repayment/Payments': [
        'Deferral of Payments', 'Maturity Extension', 'Mandatory Prepayment/Cancellation',
        'Voluntary Prepayments', 'Redemption/Repurchase/Early Repayment', 'Additional Amounts'
    ],
    'Definitions': [
        'Indebtedness'
    ],
    'Representations and Warranties': [
        'Authorizations and Approvals', 'Exchange Controls (R & W)', 'Commercial Acts',
        'Power and Authority', 'Sanctions (R & W)', 'Status of Obligation/Pari Passu (R & W)',
        'No Security'
    ],
    'Conditions Precedent': [
        'Conditions (Effectiveness)', 'Conditions (Utilization)'
    ],
    'Borrower Covenants/Undertakings': [
        'Anti-corruption/AML', 'Books and Records', 'Compliance with Authorizations',
        'Limits on External Indebtedness', 'Negative Pledge', 'Lien/Permitted Lien',
        'Information', 'Notification'
    ],
    'Events of Default and Consequences': []  # Subclauses vary
}


class PDIPScraper:
    """Base scraper class for PublicDebtIsPublic platform"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; PDIPBot/1.0; +https://github.com/)',
        })
        self.last_request_time = 0

    def _respectful_delay(self):
        """Implement rate limiting to be respectful to the server"""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    def _fetch_with_retry(self, url: str, max_retries: int = MAX_RETRIES) -> Optional[requests.Response]:
        """Fetch URL with retry logic"""
        for attempt in range(max_retries):
            try:
                self._respectful_delay()
                response = self.session.get(url, timeout=TIMEOUT)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def extract_doc_id(self, doc_url: str) -> Optional[str]:
        """Extract document ID from URL or text
        Example: /pdf/VEN85/ -> VEN85
        """
        match = re.search(r'/pdf/([A-Z0-9]+)/', doc_url)
        return match.group(1) if match else None

    def close(self):
        """Clean up resources"""
        self.session.close()


class Phase1DocumentInventory(PDIPScraper):
    """Phase 1: Scrape all documents to create inventory"""

    def scrape_all_documents(self, max_pages: Optional[int] = None) -> List[Dict]:
        """Scrape all documents from search results"""
        documents = []
        page = 1
        max_pages = max_pages or 999999  # No limit

        while page <= max_pages:
            logger.info(f"Scraping page {page}...")
            url = f"{self.base_url}/search/?page={page}&sortBy=date&sortOrder=asc"

            response = self._fetch_with_retry(url)
            if not response:
                logger.error(f"Failed to fetch page {page}, stopping")
                break

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all document result cards
            doc_cards = soup.find_all('article', class_='document-result')
            if not doc_cards:
                logger.info(f"No more documents found on page {page}, stopping")
                break

            for doc_card in doc_cards:
                try:
                    doc = self.parse_document_card(doc_card)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"Error parsing document card: {e}")

            logger.info(f"Extracted {len(doc_cards)} documents from page {page}")
            page += 1

        return documents

    def parse_document_card(self, doc_card) -> Optional[Dict]:
        """Parse a single document result card"""
        try:
            # Extract title link
            title_elem = doc_card.find('h2', class_='document-title')
            title_link = title_elem.find('a') if title_elem else None

            if not title_link:
                return None

            title = title_link.get_text(strip=True)
            doc_url = title_link.get('href', '')
            doc_id = self.extract_doc_id(doc_url)

            # Extract metadata (Instrument, Borrower, Creditor, etc.)
            metadata = {}
            for info_item in doc_card.find_all('span', class_='info-item'):
                label_elem = info_item.find('strong')
                if label_elem:
                    label = label_elem.get_text(strip=True)
                    value = info_item.get_text(strip=True)
                    value = value.replace(label, '', 1).strip(' • ')
                    metadata[label] = value

            # Determine if annotated
            status_text = doc_card.get_text()
            status = 'Annotated' if 'Status: Annotated' in status_text else 'Unannotated'

            return {
                'doc_id': doc_id,
                'title': title,
                'url': f"{self.base_url}{doc_url}" if doc_url.startswith('/') else doc_url,
                'instrument_type': metadata.get('Instrument', ''),
                'borrower': metadata.get('Borrower', ''),
                'creditor': metadata.get('Creditor', ''),
                'maturity_date': metadata.get('Maturity Date', ''),
                'contract_date': metadata.get('Contract Date', ''),
                'entity_type': metadata.get('Entity Type', ''),
                'status': status,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error parsing document card: {e}")
            return None

    def save_to_csv(self, documents: List[Dict], output_path: str = 'documents.csv'):
        """Save document inventory to CSV"""
        if not documents:
            logger.warning("No documents to save")
            return

        df = pd.DataFrame(documents)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {len(documents)} documents to {output_path}")


class Phase2ClauseExtraction(PDIPScraper):
    """Phase 2: Extract clause annotations for annotated documents"""

    def extract_clause_tags(self, doc_id: str) -> Optional[Dict]:
        """Extract clause tags from a document page"""
        url = f"{self.base_url}/pdf/{doc_id}/"
        response = self._fetch_with_retry(url)

        if not response:
            logger.warning(f"Failed to fetch document {doc_id}")
            return None

        try:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for clause tag elements in the right panel
            # Note: These selectors may need adjustment based on actual HTML structure
            clauses = {}

            # Find Tagged Clauses section
            tagged_clauses_section = soup.find('h2', string=re.compile('Tagged Clauses'))
            if not tagged_clauses_section:
                logger.warning(f"No 'Tagged Clauses' section found for {doc_id}")
                return {'doc_id': doc_id, 'clauses': {}}

            # Extract clause tags (implementation depends on actual HTML structure)
            # This is a placeholder - actual implementation requires inspecting the HTML
            current_category = None
            for elem in tagged_clauses_section.find_next_siblings():
                if elem.name in ['h3', 'h4']:  # Category header
                    current_category = elem.get_text(strip=True)
                    clauses[current_category] = []
                elif elem.name == 'span' and 'clause-tag' in elem.get('class', []):
                    if current_category:
                        clauses[current_category].append(elem.get_text(strip=True))

            return {
                'doc_id': doc_id,
                'clauses': clauses,
                'extracted_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error extracting clauses from {doc_id}: {e}")
            return None

    def process_annotated_documents(self, inventory_path: str) -> List[Dict]:
        """Process all annotated documents from inventory"""
        df = pd.read_csv(inventory_path)
        annotated = df[df['status'] == 'Annotated']

        results = []
        for idx, row in annotated.iterrows():
            logger.info(f"Processing {row['doc_id']} ({idx + 1}/{len(annotated)})")
            doc_data = self.extract_clause_tags(row['doc_id'])
            if doc_data:
                results.append(doc_data)

        return results

    def save_to_csv(self, results: List[Dict], output_path: str = 'clause_annotations.csv'):
        """Save clause annotations in normalized format"""
        rows = []
        for doc_result in results:
            doc_id = doc_result['doc_id']
            for category, clauses in doc_result.get('clauses', {}).items():
                for clause_type in clauses:
                    rows.append({
                        'doc_id': doc_id,
                        'clause_type': clause_type,
                        'clause_category': category,
                        'is_present': 1
                    })

        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False)
            logger.info(f"Saved {len(rows)} clause annotations to {output_path}")


class Phase3FullTextExtraction(PDIPScraper):
    """Phase 3: Extract full clause text (requires browser automation or API)"""

    async def extract_clause_text(self, doc_id: str) -> Optional[Dict]:
        """
        Extract full clause text. This requires browser automation (Playwright/Selenium)
        or reverse-engineered API endpoints.

        Placeholder implementation - would need Playwright installed:
            pip install playwright
        """
        # This is a placeholder. Full implementation would use:
        # from playwright.async_api import async_playwright
        #
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch()
        #     page = await browser.new_page()
        #     await page.goto(f'{self.base_url}/pdf/{doc_id}/')
        #     # Extract clause text from page...

        logger.warning("Phase 3 requires Playwright. Install with: pip install playwright")
        return None


def main():
    parser = argparse.ArgumentParser(description='Extract data from PublicDebtIsPublic platform')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3], required=True,
                        help='Extraction phase to run')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--input', type=str, help='Input file path (for phases 2+)')
    parser.add_argument('--max-pages', type=int, default=None, help='Max pages to scrape (phase 1)')

    args = parser.parse_args()

    if args.phase == 1:
        logger.info("=== Phase 1: Document Inventory ===")
        scraper = Phase1DocumentInventory()
        documents = scraper.scrape_all_documents(max_pages=args.max_pages)
        output_path = args.output or 'documents.csv'
        scraper.save_to_csv(documents, output_path)
        scraper.close()
        logger.info(f"Extracted {len(documents)} documents")

    elif args.phase == 2:
        logger.info("=== Phase 2: Clause Extraction ===")
        if not args.input:
            logger.error("Phase 2 requires --input (path to documents.csv)")
            return

        scraper = Phase2ClauseExtraction()
        results = scraper.process_annotated_documents(args.input)
        output_path = args.output or 'clause_annotations.csv'
        scraper.save_to_csv(results, output_path)
        scraper.close()
        logger.info(f"Extracted clauses from {len(results)} documents")

    elif args.phase == 3:
        logger.info("=== Phase 3: Full Text Extraction ===")
        logger.error("Phase 3 not yet implemented. Requires Playwright/Selenium.")
        logger.info("Install: pip install playwright")


if __name__ == '__main__':
    main()
