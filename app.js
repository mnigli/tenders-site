// Configuration
const ITEMS_PER_PAGE = 20;
let currentPage = 1;
let allTenders = [];
let filteredTenders = [];
let sourceStats = {};

// DOM Elements
const tendersBody = document.getElementById('tenders-body');
const searchInput = document.getElementById('search');
const sourceSelect = document.getElementById('source');
const statusSelect = document.getElementById('status');
const categorySelect = document.getElementById('category');
const clearFiltersBtn = document.getElementById('clear-filters');
const prevButton = document.getElementById('prev-page');
const nextButton = document.getElementById('next-page');
const pageInfo = document.getElementById('page-info');
const totalTendersEl = document.getElementById('total-tenders');
const filteredTendersEl = document.getElementById('filtered-tenders');
const openTendersEl = document.getElementById('open-tenders');
const closingSoonEl = document.getElementById('closing-soon');
const lastUpdateEl = document.getElementById('last-update-date');
const sourceStatsEl = document.getElementById('source-stats');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    await loadTenders();
    setupEventListeners();
}

// Load tenders from JSON file
async function loadTenders() {
    try {
        const response = await fetch('data/tenders.json');
        if (!response.ok) {
            throw new Error('Failed to load tenders data');
        }
        const data = await response.json();
        allTenders = data.tenders || [];
        sourceStats = data.sources || {};
        lastUpdateEl.textContent = data.lastUpdate || 'לא זמין';

        // Show source stats
        if (data.sources) {
            displaySourceStats(data.sources);
        }

        // Show notice if there's a note
        if (data.note) {
            showNotice(data.note);
        }

        filteredTenders = [...allTenders];
        updateStats();
        renderTenders();
    } catch (error) {
        console.error('Error loading tenders:', error);
        tendersBody.innerHTML = `
            <tr>
                <td colspan="7" class="no-results">
                    <h3>לא ניתן לטעון את הנתונים</h3>
                    <p>אנא נסה שוב מאוחר יותר</p>
                </td>
            </tr>
        `;
    }
}

// Display source statistics
function displaySourceStats(sources) {
    const sourceNames = {
        'mr.gov.il': 'מר"מ',
        'tender.gov.il': 'מכרזים ממלכתי',
        'municipal': 'עיריות',
        'government-company': 'חברות ממשלתיות'
    };

    const parts = [];
    for (const [source, count] of Object.entries(sources)) {
        if (count > 0) {
            parts.push(`${sourceNames[source] || source}: ${count}`);
        }
    }

    if (sourceStatsEl && parts.length > 0) {
        sourceStatsEl.textContent = `מקורות: ${parts.join(' | ')}`;
    }
}

// Show notice banner
function showNotice(message) {
    const notice = document.createElement('div');
    notice.className = 'notice-banner';
    notice.innerHTML = `
        <p>${message}</p>
        <button onclick="this.parentElement.remove()">✕</button>
    `;
    const stats = document.querySelector('.stats');
    if (stats && stats.parentElement) {
        stats.parentElement.insertBefore(notice, stats);
    }
}

// Setup event listeners
function setupEventListeners() {
    searchInput.addEventListener('input', debounce(filterTenders, 300));
    sourceSelect.addEventListener('change', filterTenders);
    statusSelect.addEventListener('change', filterTenders);
    categorySelect.addEventListener('change', filterTenders);
    clearFiltersBtn.addEventListener('click', clearFilters);
    prevButton.addEventListener('click', () => changePage(-1));
    nextButton.addEventListener('click', () => changePage(1));
}

// Clear all filters
function clearFilters() {
    searchInput.value = '';
    sourceSelect.value = '';
    statusSelect.value = '';
    categorySelect.value = '';
    filterTenders();
}

// Filter tenders
function filterTenders() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const sourceFilter = sourceSelect.value;
    const statusFilter = statusSelect.value;
    const categoryFilter = categorySelect.value;

    filteredTenders = allTenders.filter(tender => {
        // Search filter - search in title, publisher, and tender number
        const matchesSearch = !searchTerm ||
            tender.title.toLowerCase().includes(searchTerm) ||
            tender.publisher.toLowerCase().includes(searchTerm) ||
            tender.tenderNumber.toLowerCase().includes(searchTerm) ||
            (tender.description && tender.description.toLowerCase().includes(searchTerm));

        // Source filter
        const matchesSource = !sourceFilter || tender.source === sourceFilter;

        // Status filter
        const tenderStatus = getTenderStatus(tender.deadline);
        const matchesStatus = !statusFilter || tenderStatus === statusFilter;

        // Category filter
        const matchesCategory = !categoryFilter ||
            tender.categories.some(cat => cat.includes(categoryFilter));

        return matchesSearch && matchesSource && matchesStatus && matchesCategory;
    });

    currentPage = 1;
    updateStats();
    renderTenders();
}

// Get tender status based on deadline
function getTenderStatus(deadline) {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const daysUntilDeadline = Math.ceil((deadlineDate - now) / (1000 * 60 * 60 * 24));

    if (daysUntilDeadline < 0) return 'closed';
    if (daysUntilDeadline <= 7) return 'closing-soon';
    return 'open';
}

// Update statistics
function updateStats() {
    const now = new Date();
    const oneWeekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

    let openCount = 0;
    let closingSoonCount = 0;

    filteredTenders.forEach(tender => {
        const deadline = new Date(tender.deadline);
        if (deadline > now) {
            openCount++;
            if (deadline <= oneWeekFromNow) {
                closingSoonCount++;
            }
        }
    });

    totalTendersEl.textContent = allTenders.length;
    filteredTendersEl.textContent = filteredTenders.length;
    openTendersEl.textContent = openCount;
    closingSoonEl.textContent = closingSoonCount;
}

// Render tenders table
function renderTenders() {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const tendersToShow = filteredTenders.slice(startIndex, endIndex);

    if (tendersToShow.length === 0) {
        tendersBody.innerHTML = `
            <tr>
                <td colspan="7" class="no-results">
                    <h3>לא נמצאו מכרזים</h3>
                    <p>נסה לשנות את פרמטרי החיפוש או לנקות את הפילטרים</p>
                </td>
            </tr>
        `;
    } else {
        tendersBody.innerHTML = tendersToShow.map(tender => createTenderRow(tender)).join('');
    }

    updatePagination();
}

// Create table row for tender
function createTenderRow(tender) {
    const status = getTenderStatus(tender.deadline);
    const statusText = {
        'open': 'פתוח',
        'closing-soon': 'נסגר בקרוב',
        'closed': 'נסגר'
    };
    const statusClass = {
        'open': 'status-open',
        'closing-soon': 'status-closing-soon',
        'closed': 'status-closed'
    };

    const sourceNames = {
        'mr.gov.il': 'מר"מ',
        'tender.gov.il': 'מכרזים ממלכתי',
        'municipal': 'עירייה',
        'government-company': 'חברה ממשלתית'
    };

    const formattedDate = formatHebrewDate(tender.deadline);
    const categories = tender.categories.map(cat =>
        `<span class="category-tag">${cat}</span>`
    ).join(' ');

    // Truncate long titles
    const maxTitleLength = 80;
    const displayTitle = tender.title.length > maxTitleLength
        ? tender.title.substring(0, maxTitleLength) + '...'
        : tender.title;

    return `
        <tr class="${status === 'closed' ? 'row-closed' : ''}">
            <td class="tender-number">${tender.tenderNumber}</td>
            <td class="tender-title" title="${tender.title}">${displayTitle}</td>
            <td>${tender.publisher}</td>
            <td>
                <span class="status-badge ${statusClass[status]}">${statusText[status]}</span>
                <br><small>${formattedDate}</small>
            </td>
            <td class="categories">${categories}</td>
            <td><span class="source-badge">${sourceNames[tender.source] || tender.source}</span></td>
            <td>
                <a href="${tender.url}" target="_blank" class="btn">צפייה</a>
            </td>
        </tr>
    `;
}

// Format date in Hebrew
function formatHebrewDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('he-IL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Change page
function changePage(direction) {
    currentPage += direction;
    renderTenders();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Update pagination controls
function updatePagination() {
    const totalPages = Math.ceil(filteredTenders.length / ITEMS_PER_PAGE);

    prevButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage >= totalPages || totalPages === 0;

    pageInfo.textContent = totalPages > 0
        ? `עמוד ${currentPage} מתוך ${totalPages}`
        : 'אין תוצאות';
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ===========================================
// SCAN NOW FUNCTIONALITY
// ===========================================

// Cloudflare Worker URL - UPDATE THIS after creating your worker!
const WORKER_URL = 'https://tenders-trigger.YOUR_SUBDOMAIN.workers.dev';

// Trigger scan function
async function triggerScan() {
    const btn = document.getElementById('scan-now-btn');
    const status = document.getElementById('scan-status');

    // Check if worker URL is configured
    if (WORKER_URL.includes('YOUR_SUBDOMAIN')) {
        // Fallback: open GitHub Actions page
        window.open('https://github.com/mnigli/tenders-site/actions/workflows/scrape.yml', '_blank');
        status.textContent = "לחץ על 'Run workflow' בעמוד שנפתח";
        status.className = 'scan-status info';
        return;
    }

    // Disable button during request
    btn.disabled = true;
    btn.textContent = 'מפעיל...';
    status.textContent = '';
    status.className = 'scan-status';

    try {
        const response = await fetch(WORKER_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.success) {
            status.textContent = '✓ הסריקה הופעלה! הנתונים יתעדכנו תוך כ-2 דקות';
            status.className = 'scan-status success';
            btn.textContent = 'הופעל!';

            // Re-enable button after 30 seconds
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = 'סרוק עכשיו';
            }, 30000);

            // Reload data after 2 minutes
            setTimeout(() => {
                status.textContent = 'מרענן נתונים...';
                loadTenders();
            }, 120000);
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Scan trigger error:', error);
        status.textContent = '✗ שגיאה - נסה שוב מאוחר יותר';
        status.className = 'scan-status error';
        btn.disabled = false;
        btn.textContent = 'סרוק עכשיו';

        // Fallback: open GitHub Actions page
        setTimeout(() => {
            if (confirm('האם לפתוח את GitHub Actions להפעלה ידנית?')) {
                window.open('https://github.com/mnigli/tenders-site/actions/workflows/scrape.yml', '_blank');
            }
        }, 1000);
    }
}
