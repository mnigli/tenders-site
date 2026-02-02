#!/usr/bin/env python3
"""
מכרזי דוברות ויחסי ציבור - סקריפט סריקה מורחב
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

# Extended keywords for filtering PR/Communications/Marketing tenders
# These keywords must appear in the TITLE to be considered relevant
KEYWORDS = [
    # דוברות והסברה
    'דוברות', 'דובר', 'הסברה', 'דיפלומטיה ציבורית',
    # יחסי ציבור
    'יחסי ציבור', 'יח"צ',
    # תקשורת - specific to communications/PR field
    'ייעוץ תקשורתי', 'ניהול משברים', 'אסטרטגיה תקשורתית',
    'תקשורת שיווקית',
    # פרסום ושיווק
    'שירותי פרסום', 'משרד פרסום', 'סוכנות פרסום', 'פרסום ושיווק',
    'שיווקי', 'קמפיין פרסומי', 'פרסומת', 'פרסום',
    # מדיה ודיגיטל
    'מדיה חברתית', 'רשתות חברתיות', 'ניהול עמודים',
    'מדיה דיגיטלית', 'סושיאל', 'מדיה',
    # קמפיינים ומיתוג
    'קמפיין', 'מיתוג', 'זהות מותגית', 'לוגו',
    # תוכן ועריכה
    'כתיבת תוכן', 'הפקת תוכן', 'עריכת תוכן', 'תוכן שיווקי',
    'הפקת סרטונים', 'הפקת וידאו', 'סרטון תדמית', 'תוכן',
    # ניטור וניתוח
    'ניטור תקשורת', 'ניתוח מדיה', 'סקירת עיתונות',
    # אירועים
    'הפקת אירועים', 'ניהול אירועים', 'כנסים ואירועים',
    # חיפוש נוסף
    'תדמית', 'קהל יעד', 'מסרים', 'עיצוב גרפי', 'דיגיטל'
]

# Words that indicate NOT a PR/communications tender (exclusion list)
EXCLUDE_KEYWORDS = [
    'רפואי', 'רפואה', 'ציוד רפואי', 'אספקת ציוד',
    'בניה', 'בנייה', 'תשתיות', 'שיפוץ',
    'מזון', 'הסעדה', 'ניקיון',
    'רכב', 'רכבים', 'דלק',
    'מחשבים', 'תוכנה', 'מערכות מידע',
    'אבטחה', 'שמירה', 'בטחון',
    'חשמל', 'אינסטלציה', 'תחזוקה'
]

# Extended categories mapping
CATEGORY_MAP = {
    'דוברות': ['דוברות', 'דובר', 'spokesman', 'הסברה', 'דיפלומטיה ציבורית'],
    'יחסי ציבור': ['יחסי ציבור', 'יח"צ', 'PR', 'public relations', 'ניהול משברים'],
    'תקשורת': ['תקשורת', 'ייעוץ תקשורתי', 'communications', 'אסטרטגיה תקשורתית'],
    'פרסום': ['פרסום', 'קמפיין', 'advertising', 'campaign', 'קריאייטיב', 'creative'],
    'שיווק': ['שיווק', 'marketing', 'קידום', 'קופירייטינג', 'כתיבה שיווקית'],
    'מדיה': ['מדיה', 'רשתות חברתיות', 'דיגיטל', 'social media', 'סושיאל'],
    'מיתוג': ['מיתוג', 'branding', 'brand', 'זהות מותגית', 'לוגו'],
    'תוכן': ['תוכן', 'content', 'עריכה', 'וידאו', 'הפקה'],
    'אירועים': ['אירועים', 'events', 'כנסים', 'השקות']
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
        """Check if text contains relevant keywords and doesn't contain exclusion keywords"""
        text_lower = text.lower()

        # First check if text contains exclusion keywords - if so, skip
        if any(excl.lower() in text_lower for excl in EXCLUDE_KEYWORDS):
            return False

        # Then check if text contains relevant keywords
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

    # Extended search keywords
    SEARCH_KEYWORDS = [
        'דוברות', 'יחסי ציבור', 'תקשורת', 'פרסום',
        'שיווק', 'מדיה', 'מיתוג', 'קמפיין',
        'רשתות חברתיות', 'דיגיטל', 'הסברה', 'תוכן'
    ]

    def scrape(self, include_historical: bool = False, max_pages: int = 5) -> list:
        """Scrape tenders from mr.gov.il

        Args:
            include_historical: If True, search all tenders (not just new ones)
            max_pages: Maximum number of pages to scrape per keyword
        """
        tenders = []
        logger.info("Scraping mr.gov.il...")

        try:
            # Search for relevant keywords
            for keyword in self.SEARCH_KEYWORDS:
                # Build query - include historical or only new
                if include_historical:
                    q_param = ':uploadDateDesc'  # All tenders, sorted by date
                else:
                    q_param = ':uploadDateDesc:itemStatus:new'  # Only new tenders

                # Scrape multiple pages
                for page in range(max_pages):
                    params = {
                        'text': keyword,
                        'q': q_param,
                        'sort': 'uploadDateDesc',
                        'page': page
                    }

                    response = self.session.get(self.SEARCH_URL, params=params, timeout=30)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        page_tenders = self._parse_results(soup)
                        tenders.extend(page_tenders)

                        # If no results on this page, stop pagination for this keyword
                        if not page_tenders:
                            break
                    else:
                        logger.warning(f"Failed to fetch mr.gov.il for keyword '{keyword}' page {page}: {response.status_code}")
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

        logger.info(f"Found {len(unique_tenders)} tenders from mr.gov.il")
        return unique_tenders

    def _parse_results(self, soup: BeautifulSoup) -> list:
        """Parse search results page"""
        tenders = []

        # Find tender cards - correct selector for mr.gov.il
        items = soup.find_all('div', class_='result-container')

        # Fallback selectors
        if not items:
            items = soup.find_all('div', class_='product-item') or soup.find_all('article')

        logger.info(f"Found {len(items)} result containers")

        for item in items:
            try:
                # Get full text for analysis
                full_text = item.get_text()

                # Skip exemptions (פטור) - only include actual tenders
                if 'פטור' in full_text and 'מכרז' not in full_text:
                    logger.debug("Skipping exemption (פטור)")
                    continue

                # Also check status field - skip if status is "פטור"
                if 'סטטוס: פטור' in full_text or 'סטטוס:פטור' in full_text:
                    logger.debug("Skipping exemption by status")
                    continue

                # Extract title from link
                link = item.find('a', href=lambda h: h and '/p/' in h)
                if not link:
                    continue

                title = link.get_text(strip=True)

                # IMPORTANT: Only check keywords in the TITLE, not full text
                # Because full text contains "תאריך פרסום" etc. which gives false positives
                if not title or not self.matches_keywords(title):
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
                        categories=self.categorize(title + ' ' + full_text),
                        source="mr.gov.il",
                        url=url
                    )
                    tenders.append(tender)
                    logger.info(f"Found tender: {title[:50]}...")

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
    Extended to include more municipalities
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


def main(include_historical: bool = False):
    """Main function to run all scrapers

    Args:
        include_historical: If True, search historical tenders (last 6 months)
    """
    logger.info("Starting tender scraping...")
    if include_historical:
        logger.info("*** HISTORICAL MODE: Searching all tenders (including closed) ***")

    all_tenders = []

    # Initialize and run MRGov scraper with historical option
    mr_scraper = MRGovScraper()
    try:
        tenders = mr_scraper.scrape(include_historical=include_historical, max_pages=10 if include_historical else 3)
        all_tenders.extend(tenders)
    except Exception as e:
        logger.error(f"MRGovScraper failed: {e}")

    # Run other scrapers normally (they don't support historical mode yet)
    other_scrapers = [
        TenderGovScraper(),
        MunicipalScraper()
    ]

    for scraper in other_scrapers:
        try:
            tenders = scraper.scrape()
            all_tenders.extend(tenders)
        except Exception as e:
            logger.error(f"Scraper {scraper.__class__.__name__} failed: {e}")

    # Convert to dict format
    tenders_data = [asdict(t) for t in all_tenders]

    # Sort by deadline (closest first for open, most recent for closed)
    tenders_data.sort(key=lambda x: x['deadline'], reverse=include_historical)

    # Create output
    output = {
        "lastUpdate": datetime.now().strftime('%Y-%m-%d %H:%M'),
        "tenders": tenders_data
    }

    # Add note if no tenders found or if in historical mode
    if not tenders_data:
        output["note"] = "כרגע אין מכרזים פתוחים בתחום יחסי ציבור ודוברות. המערכת סורקת אוטומטית כל שבוע."
    elif include_historical:
        output["note"] = f"מצב בדיקה היסטורית: נמצאו {len(tenders_data)} מכרזים מהחצי שנה האחרונה."

    # Save to file
    output_path = Path(__file__).parent.parent / 'data' / 'tenders.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(tenders_data)} tenders to {output_path}")

    return len(tenders_data)


if __name__ == '__main__':
    import sys
    # Check if --historical flag is passed
    include_historical = '--historical' in sys.argv
    main(include_historical=include_historical)
