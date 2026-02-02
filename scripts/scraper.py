#!/usr/bin/env python3
"""
מכרזי דוברות ויחסי ציבור - סקריפט סריקה גורפת
סורק את כל המכרזים (לא פטורים) ומסנן באתר עצמו
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

# Extended categories mapping - used for categorization in the website
CATEGORY_MAP = {
    'דוברות': ['דוברות', 'דובר', 'spokesman', 'הסברה', 'דיפלומטיה ציבורית'],
    'יחסי ציבור': ['יחסי ציבור', 'יח"צ', 'PR', 'public relations', 'ניהול משברים'],
    'תקשורת': ['תקשורת', 'ייעוץ תקשורתי', 'communications', 'אסטרטגיה תקשורתית'],
    'פרסום': ['פרסום', 'קמפיין', 'advertising', 'campaign', 'קריאייטיב', 'creative'],
    'שיווק': ['שיווק', 'marketing', 'קידום', 'קופירייטינג', 'כתיבה שיווקית'],
    'מדיה': ['מדיה', 'רשתות חברתיות', 'דיגיטל', 'social media', 'סושיאל'],
    'מיתוג': ['מיתוג', 'branding', 'brand', 'זהות מותגית', 'לוגו'],
    'תוכן': ['תוכן', 'content', 'עריכה', 'וידאו', 'הפקה'],
    'אירועים': ['אירועים', 'events', 'כנסים', 'השקות'],
    'עיצוב': ['עיצוב', 'גרפי', 'design', 'graphic'],
    'אחר': []  # Default category
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
    docType: str = "מכרז"  # מכרז, פטור, הודעה


class TenderScraper:
    """Base scraper class"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        # Disable SSL verification for problematic sites
        self.session.verify = False

        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def categorize(self, text: str) -> list:
        """Categorize tender based on content"""
        categories = []
        text_lower = text.lower()

        for category, keywords in CATEGORY_MAP.items():
            if category == 'אחר':
                continue
            if any(kw.lower() in text_lower for kw in keywords):
                categories.append(category)

        return categories if categories else ['אחר']

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
    גישה גורפת: אוסף את כל המכרזים (לא פטורים), סינון באתר
    """

    BASE_URL = "https://mr.gov.il"
    SEARCH_URL = f"{BASE_URL}/ilgstorefront/he/search"

    def scrape(self, max_pages: int = 20) -> list:
        """Scrape ALL tenders from mr.gov.il (excluding exemptions)

        Args:
            max_pages: Maximum number of pages to scrape
        """
        tenders = []
        logger.info("Scraping mr.gov.il - COMPREHENSIVE MODE (all tenders, no exemptions)...")

        try:
            # Scrape all recent tenders sorted by date
            for page in range(max_pages):
                params = {
                    'q': ':uploadDateDesc',  # All items, sorted by upload date
                    'sort': 'uploadDateDesc',
                    'page': page
                }

                response = self.session.get(self.SEARCH_URL, params=params, timeout=30)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    page_tenders = self._parse_results(soup)

                    if not page_tenders:
                        logger.info(f"No more results at page {page}, stopping.")
                        break

                    tenders.extend(page_tenders)
                    logger.info(f"Page {page}: Found {len(page_tenders)} tenders (total: {len(tenders)})")
                else:
                    logger.warning(f"Failed to fetch mr.gov.il page {page}: {response.status_code}")
                    break

        except Exception as e:
            logger.error(f"Error scraping mr.gov.il: {e}")

        # Remove duplicates based on tender number
        seen = set()
        unique_tenders = []
        for tender in tenders:
            if tender.tenderNumber not in seen:
                seen.add(tender.tenderNumber)
                unique_tenders.append(tender)

        logger.info(f"Found {len(unique_tenders)} unique tenders from mr.gov.il")
        return unique_tenders

    def _parse_results(self, soup: BeautifulSoup) -> list:
        """Parse search results page - collect ALL tenders, skip exemptions"""
        tenders = []

        # Find tender cards - correct selector for mr.gov.il
        items = soup.find_all('div', class_='result-container')

        # Fallback selectors
        if not items:
            items = soup.find_all('div', class_='product-item') or soup.find_all('article')

        for item in items:
            try:
                # Get full text for analysis
                full_text = item.get_text()

                # Determine document type
                doc_type = "מכרז"

                # Skip exemptions (פטור) - we only want actual tenders
                if 'פטור' in full_text:
                    # Check if it's truly an exemption
                    if 'סטטוס: פטור' in full_text or 'סטטוס:פטור' in full_text:
                        continue  # Skip exemptions
                    if 'הודעת פטור' in full_text or 'הודעות פטור' in full_text:
                        continue  # Skip exemption notices
                    # If "פטור" appears but also "מכרז", might be a tender mentioning exemption
                    if 'מכרז' not in full_text:
                        continue  # Skip if no mention of tender

                # Extract title from link
                link = item.find('a', href=lambda h: h and '/p/' in h)
                if not link:
                    continue

                title = link.get_text(strip=True)
                if not title:
                    continue

                # Extract URL
                url = link.get('href', '')
                if url and not url.startswith('http'):
                    url = f"{self.BASE_URL}{url}"

                # Extract tender number from URL or text
                tender_num = self._extract_tender_number_from_url(url) or self._extract_tender_number(item)

                # Extract deadline - look for "מועד אחרון להגשה"
                deadline = self._extract_deadline_from_text(full_text)

                # Extract publisher - look for "שם המפרסם"
                publisher = self._extract_publisher_from_text(full_text)

                if tender_num and title:
                    tender = Tender(
                        tenderNumber=tender_num,
                        title=title,
                        publisher=publisher,
                        deadline=deadline or datetime.now().strftime('%Y-%m-%d'),
                        categories=self.categorize(title),  # Only categorize by title
                        source="mr.gov.il",
                        url=url,
                        docType=doc_type
                    )
                    tenders.append(tender)

            except Exception as e:
                logger.debug(f"Error parsing item: {e}")
                continue

        return tenders

    def _extract_tender_number_from_url(self, url: str) -> str:
        """Extract tender number from URL like /p/4000613481"""
        match = re.search(r'/p/(\d+)', url)
        if match:
            return match.group(1)
        return ""

    def _extract_deadline_from_text(self, text: str) -> Optional[str]:
        """Extract deadline from full text"""
        # Look for "מועד אחרון להגשה: DD/MM/YYYY"
        match = re.search(r'מועד אחרון להגשה[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})', text)
        if match:
            return self.parse_date(match.group(1))

        # Look for any date pattern as fallback
        match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{4})', text)
        if match:
            return self.parse_date(match.group(1))

        return None

    def _extract_publisher_from_text(self, text: str) -> str:
        """Extract publisher from full text"""
        # Look for "שם המפרסם: ..."
        match = re.search(r'שם המפרסם[:\s]*([^\n]+?)(?:\n|מס)', text)
        if match:
            return match.group(1).strip()
        return "משרד ממשלתי"

    def _extract_tender_number(self, item) -> str:
        """Extract tender number from item"""
        text = item.get_text()

        # Look for "מס' פרסום: XXXXXXXXXX"
        match = re.search(r"מס['\"]?\s*פרסום[:\s]*(\d+)", text)
        if match:
            return match.group(1)

        # Look for tender number pattern
        match = re.search(r'מכרז\s*(?:מספר|#)?\s*:?\s*([A-Za-z0-9\-\/]+)', text)
        if match:
            return match.group(1)

        # Try to find numeric ID (10+ digits)
        match = re.search(r'(\d{10,})', text)
        if match:
            return match.group(1)

        return f"MR-{datetime.now().strftime('%Y%m%d%H%M%S')}"


class TenderGovScraper(TenderScraper):
    """
    Scraper for tender.gov.il - מערכת המכרזים הממלכתית
    גישה גורפת: אוסף את כל המכרזים
    """

    BASE_URL = "https://www.gov.il"
    API_URL = f"{BASE_URL}/he/api/BuresApi/Index"

    def scrape(self) -> list:
        """Scrape ALL tenders from tender.gov.il / gov.il"""
        tenders = []
        logger.info("Scraping tender.gov.il - COMPREHENSIVE MODE...")

        try:
            # Try the official government tenders API - get more results
            params = {
                'skip': 0,
                'limit': 500,  # Get more results
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
        """Parse API response - collect ALL tenders"""
        tenders = []

        results = data.get('results', []) or data.get('items', [])

        for item in results:
            try:
                title = item.get('Title', '') or item.get('title', '')
                if not title:
                    continue

                tender = Tender(
                    tenderNumber=str(item.get('TenderId', '') or item.get('id', '')),
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
        """Fallback HTML scraping - collect ALL tenders"""
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
    גישה גורפת: אוסף את כל המכרזים מעיריות
    """

    MUNICIPALITIES = {
        # ערים גדולות
        'tel-aviv': {
            'name': 'עיריית תל אביב-יפו',
            'url': 'https://www.tel-aviv.gov.il/Tenders/Pages/TendersList.aspx',
            'prefix': 'TLV'
        },
        'jerusalem': {
            'name': 'עיריית ירושלים',
            'url': 'https://www.jerusalem.muni.il/he/residents/tenders/',
            'prefix': 'JLM'
        },
        'haifa': {
            'name': 'עיריית חיפה',
            'url': 'https://www.haifa.muni.il/tenders',
            'prefix': 'HFA'
        },
        'beersheba': {
            'name': 'עיריית באר שבע',
            'url': 'https://www.beer-sheva.muni.il/Residents/tenders/Pages/default.aspx',
            'prefix': 'BSH'
        },
        'rishon': {
            'name': 'עיריית ראשון לציון',
            'url': 'https://www.rishonlezion.muni.il/Residents/Tenders/Pages/default.aspx',
            'prefix': 'RLZ'
        },
        # ערים נוספות
        'petah-tikva': {
            'name': 'עיריית פתח תקווה',
            'url': 'https://www.petah-tikva.muni.il/Residents/Tenders/Pages/default.aspx',
            'prefix': 'PTK'
        },
        'netanya': {
            'name': 'עיריית נתניה',
            'url': 'https://www.netanya.muni.il/Tenders/Pages/default.aspx',
            'prefix': 'NTN'
        },
        'ashdod': {
            'name': 'עיריית אשדוד',
            'url': 'https://www.ashdod.muni.il/Tenders/Pages/default.aspx',
            'prefix': 'ASD'
        },
        'holon': {
            'name': 'עיריית חולון',
            'url': 'https://www.holon.muni.il/Residents/Tenders/Pages/default.aspx',
            'prefix': 'HLN'
        },
        'bnei-brak': {
            'name': 'עיריית בני ברק',
            'url': 'https://www.bnei-brak.muni.il/tenders',
            'prefix': 'BBK'
        },
        'ramat-gan': {
            'name': 'עיריית רמת גן',
            'url': 'https://www.ramat-gan.muni.il/Residents/Tenders/Pages/default.aspx',
            'prefix': 'RMG'
        },
        'bat-yam': {
            'name': 'עיריית בת ים',
            'url': 'https://www.bat-yam.muni.il/tenders',
            'prefix': 'BTY'
        },
        'ashkelon': {
            'name': 'עיריית אשקלון',
            'url': 'https://www.ashkelon.muni.il/tenders',
            'prefix': 'ASK'
        },
        'rehovot': {
            'name': 'עיריית רחובות',
            'url': 'https://www.rehovot.muni.il/Residents/Tenders/Pages/default.aspx',
            'prefix': 'RHV'
        },
        'herzliya': {
            'name': 'עיריית הרצליה',
            'url': 'https://www.herzliya.muni.il/Tenders/Pages/default.aspx',
            'prefix': 'HRZ'
        },
        'kfar-saba': {
            'name': 'עיריית כפר סבא',
            'url': 'https://www.kfar-saba.muni.il/tenders',
            'prefix': 'KFS'
        },
        'raanana': {
            'name': 'עיריית רעננה',
            'url': 'https://www.raanana.muni.il/tenders',
            'prefix': 'RNN'
        },
        'modiin': {
            'name': 'עיריית מודיעין-מכבים-רעות',
            'url': 'https://www.modiin.muni.il/tenders',
            'prefix': 'MDN'
        },
        'nazareth': {
            'name': 'עיריית נצרת',
            'url': 'https://www.nazareth.muni.il/tenders',
            'prefix': 'NZR'
        },
        'eilat': {
            'name': 'עיריית אילת',
            'url': 'https://www.eilat.muni.il/tenders',
            'prefix': 'ELT'
        }
    }

    def scrape(self) -> list:
        """Scrape ALL tenders from multiple municipalities"""
        all_tenders = []

        for city_id, city_info in self.MUNICIPALITIES.items():
            logger.info(f"Scraping {city_info['name']}...")
            tenders = self._scrape_municipality(city_id, city_info)
            all_tenders.extend(tenders)

        logger.info(f"Found {len(all_tenders)} tenders from municipalities")
        return all_tenders

    def _scrape_municipality(self, city_id: str, city_info: dict) -> list:
        """Scrape single municipality - collect ALL tenders"""
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
        """Parse municipal tenders page - collect ALL tenders"""
        tenders = []

        # Common selectors for municipal sites (SharePoint based and others)
        items = (
            soup.find_all('div', class_='tender-row') or
            soup.find_all('tr', class_='tender') or
            soup.find_all('article', class_='tender') or
            soup.find_all('li', class_='tender-item') or
            soup.find_all('div', class_='ms-listviewtable') or
            soup.find_all('tr', class_='ms-itmhover') or
            soup.find_all('div', class_='dfwp-item')
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
                if not title:
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


class GovernmentCompaniesScraper(TenderScraper):
    """
    Scraper for government companies tenders
    חברות ממשלתיות כמו חברת החשמל, מקורות, רכבת ישראל וכו'
    """

    COMPANIES = {
        'israel-electric': {
            'name': 'חברת החשמל',
            'url': 'https://www.iec.co.il/tenders',
            'prefix': 'IEC'
        },
        'mekorot': {
            'name': 'מקורות',
            'url': 'https://www.mekorot.co.il/tenders',
            'prefix': 'MKR'
        },
        'israel-railways': {
            'name': 'רכבת ישראל',
            'url': 'https://www.rail.co.il/tenders',
            'prefix': 'ISR'
        },
        'israel-post': {
            'name': 'דואר ישראל',
            'url': 'https://www.israelpost.co.il/tenders',
            'prefix': 'POST'
        },
        'airports-authority': {
            'name': 'רשות שדות התעופה',
            'url': 'https://www.iaa.gov.il/tenders',
            'prefix': 'IAA'
        },
        'ports-company': {
            'name': 'חברת נמלי ישראל',
            'url': 'https://www.israports.co.il/tenders',
            'prefix': 'PORT'
        },
        'bezeq': {
            'name': 'בזק',
            'url': 'https://www.bezeq.co.il/tenders',
            'prefix': 'BZK'
        },
        'egged': {
            'name': 'אגד',
            'url': 'https://www.egged.co.il/tenders',
            'prefix': 'EGD'
        },
        'dan': {
            'name': 'דן',
            'url': 'https://www.dan.co.il/tenders',
            'prefix': 'DAN'
        }
    }

    def scrape(self) -> list:
        """Scrape ALL tenders from government companies"""
        all_tenders = []

        for company_id, company_info in self.COMPANIES.items():
            logger.info(f"Scraping {company_info['name']}...")
            tenders = self._scrape_company(company_id, company_info)
            all_tenders.extend(tenders)

        logger.info(f"Found {len(all_tenders)} tenders from government companies")
        return all_tenders

    def _scrape_company(self, company_id: str, company_info: dict) -> list:
        """Scrape single government company"""
        tenders = []

        try:
            response = self.session.get(company_info['url'], timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Parse tenders from HTML - use common patterns
                items = (
                    soup.find_all('div', class_=re.compile(r'tender|item')) or
                    soup.find_all('article') or
                    soup.find_all('tr', class_=re.compile(r'tender|item'))
                )

                for item in items:
                    title_el = item.find(['h2', 'h3', 'h4', 'a'])
                    if title_el:
                        title = title_el.get_text(strip=True)
                        if title:
                            tender = Tender(
                                tenderNumber=f"{company_info['prefix']}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                title=title,
                                publisher=company_info['name'],
                                deadline=datetime.now().strftime('%Y-%m-%d'),
                                categories=self.categorize(title),
                                source="government-company",
                                url=company_info['url']
                            )
                            tenders.append(tender)
            else:
                logger.warning(f"Failed to fetch {company_info['name']}: {response.status_code}")

        except Exception as e:
            logger.debug(f"Error scraping {company_info['name']}: {e}")

        return tenders


def main():
    """Main function to run all scrapers - COMPREHENSIVE MODE"""
    logger.info("Starting COMPREHENSIVE tender scraping...")
    logger.info("Collecting ALL tenders (excluding exemptions), filtering will be done in the website")

    all_tenders = []

    # Run all scrapers
    scrapers = [
        MRGovScraper(),
        TenderGovScraper(),
        MunicipalScraper(),
        GovernmentCompaniesScraper()
    ]

    for scraper in scrapers:
        try:
            tenders = scraper.scrape()
            all_tenders.extend(tenders)
            logger.info(f"{scraper.__class__.__name__}: {len(tenders)} tenders")
        except Exception as e:
            logger.error(f"Scraper {scraper.__class__.__name__} failed: {e}")

    # Remove duplicates based on tender number
    seen = set()
    unique_tenders = []
    for tender in all_tenders:
        if tender.tenderNumber not in seen:
            seen.add(tender.tenderNumber)
            unique_tenders.append(tender)

    # Convert to dict format
    tenders_data = [asdict(t) for t in unique_tenders]

    # Sort by deadline (closest first)
    tenders_data.sort(key=lambda x: x['deadline'])

    # Create output
    output = {
        "lastUpdate": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "tenders": tenders_data,
        "totalCount": len(tenders_data),
        "sources": {
            "mr.gov.il": len([t for t in tenders_data if t['source'] == 'mr.gov.il']),
            "tender.gov.il": len([t for t in tenders_data if t['source'] == 'tender.gov.il']),
            "municipal": len([t for t in tenders_data if t['source'] == 'municipal']),
            "government-company": len([t for t in tenders_data if t['source'] == 'government-company'])
        }
    }

    # Add note
    if not tenders_data:
        output["note"] = "לא נמצאו מכרזים. המערכת סורקת אוטומטית כל שבוע."
    else:
        output["note"] = f"נמצאו {len(tenders_data)} מכרזים ממגוון מקורות. השתמש בפילטרים באתר לחיפוש ממוקד."

    # Save to file
    output_path = Path(__file__).parent.parent / 'data' / 'tenders.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(tenders_data)} tenders to {output_path}")

    return len(tenders_data)


if __name__ == '__main__':
    main()
