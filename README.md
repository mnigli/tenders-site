# מכרזי דוברות ויחסי ציבור - ישראל

אתר לאיסוף והצגת מכרזים ממשלתיים ועירוניים בתחומי דוברות, יחסי ציבור ותקשורת.

## מבנה הפרויקט

```
tenders-site/
├── index.html          # דף הבית
├── styles.css          # עיצוב האתר
├── app.js              # לוגיקה צד לקוח
├── data/
│   └── tenders.json    # נתוני המכרזים
├── scripts/
│   ├── scraper.py      # סקריפט סריקה
│   └── requirements.txt
└── .github/
    └── workflows/
        ├── scrape.yml  # סריקה שבועית אוטומטית
        └── deploy.yml  # פריסה ל-GitHub Pages
```

## התקנה והפעלה

### הפעלה מקומית

1. פתח את הקובץ `index.html` בדפדפן
2. או הרץ שרת מקומי:
   ```bash
   # Python 3
   python -m http.server 8000

   # Node.js
   npx serve
   ```

### הפעלת הסקריפט באופן ידני

```bash
cd scripts
pip install -r requirements.txt
python scraper.py
```

## פריסה ל-GitHub Pages

1. צור repository חדש ב-GitHub
2. העלה את הקבצים:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/tenders-site.git
   git push -u origin main
   ```

3. הגדר GitHub Pages:
   - לך ל-Settings > Pages
   - בחר Source: "GitHub Actions"

4. הגדר הרשאות Actions:
   - לך ל-Settings > Actions > General
   - תחת "Workflow permissions" בחר "Read and write permissions"

5. האתר יהיה זמין בכתובת:
   `https://YOUR_USERNAME.github.io/tenders-site/`

## מקורות נתונים

הסקריפט סורק את המקורות הבאים:

- **מר"מ** (mr.gov.il) - מנהל הרכש הממשלתי
- **מערכת המכרזים הממלכתית** (tender.gov.il/gov.il)
- **אתרי עיריות**:
  - תל אביב-יפו
  - ירושלים
  - חיפה
  - באר שבע
  - ראשון לציון

## מילות מפתח לסינון

הסקריפט מחפש מכרזים המכילים את המונחים:
- דוברות
- יחסי ציבור / יח"צ
- תקשורת / ייעוץ תקשורתי
- פרסום / קמפיין
- מדיה / רשתות חברתיות
- מיתוג / שיווק

## תזמון אוטומטי

הסריקה רצה אוטומטית כל יום ראשון בשעה 06:00 בבוקר (שעון ישראל).

ניתן להריץ סריקה ידנית:
1. לך ל-Actions > Weekly Tender Scrape
2. לחץ "Run workflow"

## התאמה אישית

### הוספת עיריות נוספות

ערוך את `scripts/scraper.py` והוסף ל-`MUNICIPALITIES`:

```python
'city-name': {
    'name': 'שם העירייה',
    'url': 'כתובת דף המכרזים',
    'prefix': 'קידומת למספר מכרז'
}
```

### שינוי תזמון הסריקה

ערוך את `.github/workflows/scrape.yml` ושנה את ה-cron:
```yaml
schedule:
  - cron: '0 3 * * 0'  # כל ראשון ב-03:00 UTC
```

## רישיון

MIT License
