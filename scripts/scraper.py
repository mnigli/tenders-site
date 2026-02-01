#!/usr/bin/env python3
"""
מכרזי דוברות ויחסי ציבור - סקריפט סריקה
סורק מכרזים ממקורות ממשלתיים ועירוניים בישראל
"""

import json
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Keywords for filtering PR/Communications tenders
KEYWORDS = [
    'דוברות', 'יחסי ציבור', 'תקשורת', 'פרסום', 'מדיה',
    'ייעוץ תקשורתי', 'ניהול משברים', 'רשתות חברתיות',
    'דיגיטל', 'קמפיין', 'מיתוג', 'שיווק', 'הסברה',
    'PR', 'public relations', 'communications'
]

# Categories mapping
CATEGORY_MAP = {
    'דוברות': ['דוברות', 'דובר', 'spokesman'],
    'יחסי ציבור': ['יחסי ציבור', 'יח"צ', 'PR', 'public relations'],
    'תקשורת': ['תקשורת', 'ייעוץ תקשורתי', 'communications'],
    'פרסום': ['פרסום', 'קמפיין', 'advertising'],
    'מדיה': ['מדיה', 'רשתות חברתיות', 'דיגיטל', 'social media']
}


@dataclass
class Tender:
    """Represents a tender/RFP"""
    tenderNumber: str
    title: str
    publisher: str
    deadline: str
    categories: list
    source: str
    url: str
    description: str = ""


class TenderScraper:
    """Base scraper class"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def matches_keywords(self, text: str) -> bool:
        """Check if text contains relevant keywords"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in KEYWORDS)

    def categorize(self, text: str) -> list:
        """Categorize tender based on content"""
        categories = []
        text_lower = text.lower()

        for category, keywords in CATEGORY_MAP.items():
            if any(kw.lower() in text_lower for kw in keywords):
                categories.append(category)

        return categories if categories else ['תקשורת']

    def parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to ISO format"""
        date_formats = [
            '%d/%m/%Y',
            '%d.%m.%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%y',
        ]

        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None


class MRGovScraper(TenderScraper):
    """
    Scraper for mr.gov.il - מנהל הרכש הממשלתי (Government Procurement Administration)
    """

    BASE_URL = "https://mr.gov.il"
    SEARCH_URL = f"{BASE_URL}/ilgstorefront/he/search"

    def scrape(self) -> list:
        """Scrape tenders from mr.gov.il"""
        tenders = []
        logger.info("Scraping mr.gov.il...")

        try:
            # Search for relevant keywords
            for keyword in ['דוברות', 'יחסי ציבור', 'תקשורת', 'פרסום']:
                params = {
                    'q': keyword,
                    'sort': 'relevance'
                }

                response = self.session.get(self.SEARCH_URL, params=params, timeout=30)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    tenders.extend(self._parse_results(soup))
                else:
                    logger.warning(f"Failed to fetch mr.gov.il for keyword '{keyword}': {response.status_code}")

        except Exception as e:
            logger.error(f"Error scraping mr.gov.il: {e}")

        # Remove duplicates based on tender number
        seen = set()
        unique_tenders = []
        for tender in tenders:
            if tender.tenderNumber not in seen:
                seen.add(tender.tenderNumber)
                unique_tenders.append(tender)

        logger.info(f"Found {len(unique_tenders)} tenders from mr.gov.il")
        return unique_tenders

    def _parse_results(self, soup: BeautifulSoup) -> list:
        """Parse search results page"""
        tenders = []

        # Find tender cards/items
        items = soup.find_all('div', class_='product-item') or soup.find_all('article')

        for item in items:
            try:
                title_el = item.find('h2') or item.find('h3') or item.find(class_='title')
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                if not self.matches_keywords(title):
                    continue

                # Extract tender number
                tender_num = item.get('data-code', '') or self._extract_tender_number(item)

                # Extract URL
                link = item.find('a', href=True)
                url = link['href'] if link else ''
                if url and not url.startswith('http'):
                    url = f"{self.BASE_URL}{url}"

                # Extract deadline
                deadline_el = item.find(class_='deadline') or item.find(text=re.compile(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'))
                deadline = self._extract_date(deadline_el) if deadline_el else None

                # Extract publisher
                publisher_el = item.find(class_='publisher') or item.find(class_='ministry')
                publisher = publisher_el.get_text(strip=True) if publisher_el else "משרד ממשלתי"

                if tender_num and title and deadline:
                    tender = Tender(
                        tenderNumber=tender_num,
                        title=title,
                        publisher=publisher,
                        deadline=deadline,
                        categories=self.categorize(title),
                        source="mr.gov.il",
                        url=url
                    )
                    tenders.append(tender)

            except Exception as e:
                logger.debug(f"Error parsing item: {e}")
                continue

        return tenders

    def _extract_tender_number(self, item) -> str:
        """Extract tender number from item"""
        text = item.get_text()
        match = re.search(r'מכרז\s*(?:מספר|#)?\s*:?\s*([A-Za-z0-9\-\/]+)', text)
        if match:
            return match.group(1)
        return f"MR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _extract_date(self, element) -> str:
        """Extract and parse date from element"""
        if hasattr(element, 'get_text'):
            text = element.get_text()
        else:
            text = str(element)

        match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})', text)
        if match:
            return self.parse_date(match.group(1)) or datetime.now().strftime('%Y-%m-%d')

        return datetime.now().strftime('%Y-%m-%d')


class TenderGovScraper(TenderScraper):
    """
    Scraper for tender.gov.il - מערכת המכרזים הממלכתית
    """

    BASE_URL = "https://www.gov.il"
    API_URL = f"{BASE_URL}/he/api/BuresApi/Index"

    def scrape(self) -> list:
        """Scrape tenders from tender.gov.il / gov.il"""
        tenders = []
        logger.info("Scraping tender.gov.il...")

        try:
            # Try the official government tenders API
            params = {
                'skip': 0,
                'limit': 100,
                'OfficeId': '',
                'Type': 'all'
            }

            response = self.session.get(self.API_URL, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                tenders.extend(self._parse_api_results(data))
            else:
                # Fallback to HTML scraping
                logger.info("API unavailable, trying HTML scraping...")
                tenders.extend(self._scrape_html())

        except Exception as e:
            logger.error(f"Error scraping tender.gov.il: {e}")

        logger.info(f"Found {len(tenders)} tenders from tender.gov.il")
        return tenders

    def _parse_api_results(self, data: dict) -> list:
        """Parse API response"""
        tenders = []

        results = data.get('results', []) or data.get('items', [])

        for item in results:
            try:
                title = item.get('Title', '') or item.get('title', '')

                if not self.matches_keywords(title):
                    continue

                tender = Tender(
                    tenderNumber=item.get('TenderId', '') or item.get('id', ''),
                    title=title,
                    publisher=item.get('OfficeName', '') or item.get('office', 'משרד ממשלתי'),
                    deadline=self.parse_date(item.get('EndDate', '')) or datetime.now().strftime('%Y-%m-%d'),
                    categories=self.categorize(title),
                    source="tender.gov.il",
                    url=item.get('Url', '') or f"{self.BASE_URL}/he/departments/tenders/{item.get('TenderId', '')}"
                )
                tenders.append(tender)

            except Exception as e:
                logger.debug(f"Error parsing API item: {e}")
                continue

        return tenders

    def _scrape_html(self) -> list:
        """Fallback HTML scraping"""
        tenders = []
        url = f"{self.BASE_URL}/he/departments/tenders"

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Parse tenders from HTML
                items = soup.find_all('div', class_='tender-item') or soup.find_all('article')

                for item in items:
                    title_el = item.find('h2') or item.find('h3')
                    if title_el:
                        title = title_el.get_text(strip=True)
                        if self.matches_keywords(title):
                            tender = Tender(
                                tenderNumber=f"GOV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                title=title,
                                publisher="משרד ממשלתי",
                                deadline=datetime.now().strftime('%Y-%m-%d'),
                                categories=self.categorize(title),
                                source="tender.gov.il",
                                url=url
                            )
                            tenders.append(tender)

        except Exception as e:
            logger.error(f"HTML scraping failed: {e}")

        return tenders


class MunicipalScraper(TenderScraper):
    """
    Scraper for municipal tenders (various city websites)
    """

    MUNICIPALITIES = {
        'tel-aviv': {
            'name': 'עיריית תל אביב-יפו',
            'url': 'https://www.tel-aviv.gov.il/Tenders/Pages/TendersList.aspx',
            'prefix': 'TLV'
        },
        'jerusalem': {
            'name': 'עיריית ירושלים',
            'url': 'https://www.jerusalem.muni.il/he/tenders/',
            'prefix': 'JLM'
        },
        'haifa': {
            'name': 'עיריית חיפה',
            'url': 'https://www.haifa.muni.il/tenders',
            'prefix': 'HFA'
        },
        'beersheba': {
            'name': 'עיריית באר שבע',
            'url': 'https://www.beer-sheva.muni.il/tenders',
            'prefix': 'BSH'
        },
        'rishon': {
            'name': 'עיריית ראשון לציון',
            'url': 'https://www.rishonlezion.muni.il/tenders',
            'prefix': 'RLZ'
        }
    }

    def scrape(self) -> list:
        """Scrape tenders from multiple municipalities"""
        all_tenders = []

        for city_id, city_info in self.MUNICIPALITIES.items():
            logger.info(f"Scraping {city_info['name']}...")
            tenders = self._scrape_municipality(city_id, city_info)
            all_tenders.extend(tenders)

        logger.info(f"Found {len(all_tenders)} tenders from municipalities")
        return all_tenders

    def _scrape_municipality(self, city_id: str, city_info: dict) -> list:
        """Scrape single municipality"""
        tenders = []

        try:
            response = self.session.get(city_info['url'], timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                tenders = self._parse_municipal_page(soup, city_info)
            else:
                logger.warning(f"Failed to fetch {city_info['name']}: {response.status_code}")

        except Exception as e:
            logger.error(f"Error scraping {city_info['name']}: {e}")

        return tenders

    def _parse_municipal_page(self, soup: BeautifulSoup, city_info: dict) -> list:
        """Parse municipal tenders page"""
        tenders = []

        # Common selectors for municipal sites
        items = (
            soup.find_all('div', class_='tender-row') or
            soup.find_all('tr', class_='tender') or
            soup.find_all('article', class_='tender') or
            soup.find_all('li', class_='tender-item') or
            soup.find_all('div', class_='ms-listviewtable')
        )

        for item in items:
            try:
                # Extract title
                title_el = item.find(['h2', 'h3', 'h4', 'a', 'span'], class_=re.compile(r'title|name|subject'))
                if not title_el:
                    title_el = item.find('td', class_='title') or item.find(['a', 'span'])

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)

                if not self.matches_keywords(title):
                    continue

                # Extract tender number
                num_el = item.find(text=re.compile(r'מספר|מכרז|#')) or item.find(class_=re.compile(r'number|id'))
                tender_num = self._extract_number(num_el, city_info['prefix'])

                # Extract deadline
                date_el = item.find(text=re.compile(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}'))
                deadline = self._extract_date(date_el) if date_el else datetime.now().strftime('%Y-%m-%d')

                # Extract URL
                link = item.find('a', href=True)
                url = link['href'] if link else city_info['url']
                if url and not url.startswith('http'):
                    base = city_info['url'].rsplit('/', 1)[0]
                    url = f"{base}/{url}"

                tender = Tender(
                    tenderNumber=tender_num,
                    title=title,
                    publisher=city_info['name'],
                    deadline=deadline,
                    categories=self.categorize(title),
                    source="municipal",
                    url=url
                )
                tenders.append(tender)

            except Exception as e:
                logger.debug(f"Error parsing municipal item: {e}")
                continue

        return tenders

    def _extract_number(self, element, prefix: str) -> str:
        """Extract tender number"""
        if element:
            text = str(element)
            match = re.search(r'(\d+[/-]?\d*)', text)
            if match:
                return f"{prefix}-{match.group(1)}"

        return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _extract_date(self, element) -> str:
        """Extract date from element"""
        if element:
            text = str(element)
            match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})', text)
            if match:
                return self.parse_date(match.group(1)) or datetime.now().strftime('%Y-%m-%d')

        return datetime.now().strftime('%Y-%m-%d')


def main():
    """Main function to run all scrapers"""
    logger.info("Starting tender scraping...")

    all_tenders = []

    # Initialize scrapers
    scrapers = [
        MRGovScraper(),
        TenderGovScraper(),
        MunicipalScraper()
    ]

    # Run all scrapers
    for scraper in scrapers:
        try:
            tenders = scraper.scrape()
            all_tenders.extend(tenders)
        except Exception as e:
            logger.error(f"Scraper {scraper.__class__.__name__} failed: {e}")

    # Convert to dict format
    tenders_data = [asdict(t) for t in all_tenders]

    # Sort by deadline (closest first)
    tenders_data.sort(key=lambda x: x['deadline'])

    # Create output
    output = {
        "lastUpdate": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "tenders": tenders_data
    }

    # Save to file
    output_path = Path(__file__).parent.parent / 'data' / 'tenders.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(tenders_data)} tenders to {output_path}")

    return len(tenders_data)


if __name__ == '__main__':
    main()
