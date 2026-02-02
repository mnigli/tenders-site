// Configuration
const ITEMS_PER_PAGE = 15;
let currentPage = 1;
let allTenders = [];
let filteredTenders = [];

// DOM Elements
const tendersBody = document.getElementById('tenders-body');
const searchInput = document.getElementById('search');
const sourceSelect = document.getElementById('source');
const statusSelect = document.getElementById('status');
const categorySelect = document.getElementById('category');
const prevButton = document.getElementById('prev-page');
const nextButton = document.getElementById('next-page');
const pageInfo = document.getElementById('page-info');
const totalTendersEl = document.getElementById('total-tenders');
const openTendersEl = document.getElementById('open-tenders');
const closingSoonEl = document.getElementById('closing-soon');
const lastUpdateEl = document.getElementById('last-update-date');

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
        lastUpdateEl.textContent = data.lastUpdate || 'לא זמין';

        // Show notice if there's a note (e.g., demo mode)
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

// Show notice banner
function showNotice(message) {
    const notice = document.createElement('div');
    notice.className = 'notice-banner';
    notice.innerHTML = `
        <p>📢 ${message}</p>
        <button onclick="this.parentElement.remove()">✕</button>
    `;
    document.querySelector('.container').insertBefore(notice, document.querySelector('.stats'));
}

// Setup event listeners
function setupEventListeners() {
    searchInput.addEventListener('input', debounce(filterTenders, 300));
    sourceSelect.addEventListener('change', filterTenders);
    statusSelect.addEventListener('change', filterTenders);
    categorySelect.addEventListener('change', filterTenders);
    prevButton.addEventListener('click', () => changePage(-1));
    nextButton.addEventListener('click', () => changePage(1));
}

// Filter tenders
function filterTenders() {
    const searchTerm = searchInput.value.toLowerCase();
    const sourceFilter = sourceSelect.value;
    const statusFilter = statusSelect.value;
    const categoryFilter = categorySelect.value;

    filteredTenders = allTenders.filter(tender => {
        // Search filter
        const matchesSearch = !searchTerm ||
            tender.title.toLowerCase().includes(searchTerm) ||
            tender.publisher.toLowerCase().includes(searchTerm) ||
            tender.tenderNumber.toLowerCase().includes(searchTerm);

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

    totalTendersEl.textContent = filteredTenders.length;
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
                    <p>נסה לשנות את פרמטרי החיפוש</p>
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
        'demo': 'דוגמה'
    };

    const formattedDate = formatHebrewDate(tender.deadline);
    const categories = tender.categories.map(cat =>
        `<span class="category-tag">${cat}</span>`
    ).join(' ');

    return `
        <tr>
            <td>${tender.tenderNumber}</td>
            <td>${tender.title}</td>
            <td>${tender.publisher}</td>
            <td>
                <span class="status-badge ${statusClass[status]}">${statusText[status]}</span>
                <br><small>${formattedDate}</small>
            </td>
            <td>${categories}</td>
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
