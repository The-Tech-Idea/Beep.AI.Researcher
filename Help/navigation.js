/**
 * Beep.AI.Researcher Help -- Sidebar Navigation & Theme Toggle
 * Adapted from TheTechIdeaWeb Help navigation system
 */
class NavigationManager {
    constructor() {
        this.currentPage = this.getCurrentPage();
        this.navigation = this.getNavigation();
    }

    getCurrentPage() {
        return window.location.pathname.split('/').pop() || 'index.html';
    }

    getNavigation() {
        return [
            { id: 'nav-home', label: 'Home', icon: 'bi-house-door', href: 'index.html', active: this.currentPage === 'index.html' },
            {
                id: 'nav-getting-started', label: 'Getting Started', icon: 'bi-rocket',
                children: [
                    { label: 'Overview', href: 'getting-started.html', active: this.currentPage === 'getting-started.html' },
                    { label: 'Installation', href: 'installation.html', active: this.currentPage === 'installation.html' },
                    { label: 'First Login', href: 'first-login.html', active: this.currentPage === 'first-login.html' },
                ]
            },
            {
                id: 'nav-projects', label: 'Projects', icon: 'bi-folder',
                children: [
                    { label: 'Creating Projects', href: 'projects.html', active: this.currentPage === 'projects.html' },
                    { label: 'Project Overview', href: 'project-overview.html', active: this.currentPage === 'project-overview.html' },
                    { label: 'Project Settings', href: 'project-settings.html', active: this.currentPage === 'project-settings.html' },
                    { label: 'Members & Collaboration', href: 'project-members.html', active: this.currentPage === 'project-members.html' },
                ]
            },
            {
                id: 'nav-documents', label: 'Documents', icon: 'bi-file-earmark-text',
                children: [
                    { label: 'Uploading Documents', href: 'documents.html', active: this.currentPage === 'documents.html' },
                    { label: 'Document Viewer', href: 'document-viewer.html', active: this.currentPage === 'document-viewer.html' },
                    { label: 'Web Search & Import', href: 'web-search.html', active: this.currentPage === 'web-search.html' },
                    { label: 'Library Sources', href: 'library-sources.html', active: this.currentPage === 'library-sources.html' },
                ]
            },
            {
                id: 'nav-codes', label: 'Codes & Themes', icon: 'bi-tags',
                children: [
                    { label: 'Code Browser', href: 'codes.html', active: this.currentPage === 'codes.html' },
                    { label: 'Applying Codes', href: 'applying-codes.html', active: this.currentPage === 'applying-codes.html' },
                    { label: 'AI Code Suggestions', href: 'ai-code-suggestions.html', active: this.currentPage === 'ai-code-suggestions.html' },
                ]
            },
            {
                id: 'nav-extraction', label: 'Extraction', icon: 'bi-table',
                children: [
                    { label: 'Extraction Schemas', href: 'extraction.html', active: this.currentPage === 'extraction.html' },
                    { label: 'Running Extraction', href: 'running-extraction.html', active: this.currentPage === 'running-extraction.html' },
                    { label: 'Field Validation', href: 'field-validation.html', active: this.currentPage === 'field-validation.html' },
                ]
            },
            {
                id: 'nav-chat', label: 'Chat & AI', icon: 'bi-chat-dots',
                children: [
                    { label: 'Project Chat', href: 'chat.html', active: this.currentPage === 'chat.html' },
                    { label: 'Chat Tools', href: 'chat-tools.html', active: this.currentPage === 'chat-tools.html' },
                    { label: 'Quality Modes', href: 'quality-modes.html', active: this.currentPage === 'quality-modes.html' },
                ]
            },
            {
                id: 'nav-report', label: 'Reports & Writing', icon: 'bi-journal-text',
                children: [
                    { label: 'Report Builder', href: 'report-builder.html', active: this.currentPage === 'report-builder.html' },
                    { label: 'Writing Assistant', href: 'writing-assistant.html', active: this.currentPage === 'writing-assistant.html' },
                    { label: 'Manuscripts', href: 'manuscripts.html', active: this.currentPage === 'manuscripts.html' },
                    { label: 'Citation Management', href: 'citations.html', active: this.currentPage === 'citations.html' },
                ]
            },
            {
                id: 'nav-references', label: 'References', icon: 'bi-bookmark',
                children: [
                    { label: 'Reference Library', href: 'references.html', active: this.currentPage === 'references.html' },
                    { label: 'Zotero Sync', href: 'zotero-sync.html', active: this.currentPage === 'zotero-sync.html' },
                    { label: 'DOI Validation', href: 'doi-validation.html', active: this.currentPage === 'doi-validation.html' },
                ]
            },
            {
                id: 'nav-data', label: 'Data & Charts', icon: 'bi-bar-chart',
                children: [
                    { label: 'Data Upload', href: 'data-upload.html', active: this.currentPage === 'data-upload.html' },
                    { label: 'Charts', href: 'charts.html', active: this.currentPage === 'charts.html' },
                    { label: 'Statistics', href: 'statistics.html', active: this.currentPage === 'statistics.html' },
                ]
            },
            {
                id: 'nav-training', label: 'Training', icon: 'bi-lightbulb',
                children: [
                    { label: 'Flashcards', href: 'flashcards.html', active: this.currentPage === 'flashcards.html' },
                    { label: 'Quizzes', href: 'quizzes.html', active: this.currentPage === 'quizzes.html' },
                ]
            },
            {
                id: 'nav-tasks', label: 'Tasks', icon: 'bi-kanban',
                children: [
                    { label: 'Task Management', href: 'tasks.html', active: this.currentPage === 'tasks.html' },
                    { label: 'AI Task Suggestions', href: 'task-suggestions.html', active: this.currentPage === 'task-suggestions.html' },
                ]
            },
            {
                id: 'nav-synthesis', label: 'Evidence Synthesis', icon: 'bi-diagram-3',
                children: [
                    { label: 'Synthesis Reports', href: 'synthesis.html', active: this.currentPage === 'synthesis.html' },
                    { label: 'Contradiction Analysis', href: 'contradiction.html', active: this.currentPage === 'contradiction.html' },
                ]
            },
            {
                id: 'nav-discovery', label: 'AI Discovery', icon: 'bi-stars',
                children: [
                    { label: 'Personalized Feed', href: 'feed.html', active: this.currentPage === 'feed.html' },
                    { label: 'Reading List', href: 'reading-list.html', active: this.currentPage === 'reading-list.html' },
                    { label: 'Research Interests', href: 'research-interests.html', active: this.currentPage === 'research-interests.html' },
                ]
            },
            {
                id: 'nav-export', label: 'Export', icon: 'bi-download',
                children: [
                    { label: 'Data Export', href: 'export.html', active: this.currentPage === 'export.html' },
                    { label: 'Export Formats', href: 'export-formats.html', active: this.currentPage === 'export-formats.html' },
                ]
            },
            {
                id: 'nav-admin', label: 'Administration', icon: 'bi-gear',
                children: [
                    { label: 'Admin Dashboard', href: 'admin-dashboard.html', active: this.currentPage === 'admin-dashboard.html' },
                    { label: 'User Management', href: 'admin-users.html', active: this.currentPage === 'admin-users.html' },
                    { label: 'Feature Flags', href: 'admin-feature-flags.html', active: this.currentPage === 'admin-feature-flags.html' },
                    { label: 'Storage & Quotas', href: 'admin-storage.html', active: this.currentPage === 'admin-storage.html' },
                ]
            },
        ];
    }

    getNavigationHTML() {
        return `
            <div class="logo">
                <div class="logo-icon"><i class="bi bi-cpu"></i></div>
                <div class="logo-text">
                    <h2>Beep.AI.Researcher</h2>
                    <span class="version">Help v1.0</span>
                </div>
            </div>
            <div class="search-container">
                <input type="text" class="search-input" placeholder="Search documentation..." id="searchInput" onkeyup="filterNavigation(this.value)">
            </div>
            <ul class="nav-menu" id="navMenu">
                ${this.navigation.map(item => this.renderNavItem(item)).join('')}
            </ul>
        `;
    }

    renderNavItem(item) {
        if (item.children && item.children.length > 0) {
            const isActive = item.children.some(child => child.active);
            return `
                <li class="has-submenu ${isActive ? 'open' : ''}" id="${item.id}">
                    <a href="${item.children[0].href}" class="${item.children.some(c => c.active) ? 'active' : ''}">
                        <i class="bi ${item.icon}"></i>${item.label}
                    </a>
                    <ul class="submenu">
                        ${item.children.map(child => `<li><a href="${child.href}" class="${child.active ? 'active' : ''}">${child.label}</a></li>`).join('')}
                    </ul>
                </li>
            `;
        }
        return `
            <li id="${item.id}">
                <a href="${item.href}" class="${item.active ? 'active' : ''}">
                    <i class="bi ${item.icon}"></i>${item.label}
                </a>
            </li>
        `;
    }

    initialize() {
        document.getElementById('sidebar').innerHTML = this.getNavigationHTML();
        this.initializeSubmenus();
    }

    initializeSubmenus() {
        document.querySelectorAll('.has-submenu > a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const parent = link.closest('.has-submenu');
                parent.classList.toggle('open');
            });
        });
    }
}

// Global functions for inline event handlers
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('beep-researcher-docs-theme', next);
    const icon = document.querySelector('.theme-toggle i');
    icon.className = next === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
}

function filterNavigation(query) {
    const items = document.querySelectorAll('#navMenu li');
    const q = query.toLowerCase();
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(q) ? '' : 'none';
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const nav = new NavigationManager();
    nav.initialize();

    // Load saved theme
    const savedTheme = localStorage.getItem('beep-researcher-docs-theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        const icon = document.querySelector('.theme-toggle i');
        if (icon) icon.className = savedTheme === 'dark' ? 'bi bi-sun' : 'bi bi-moon';
    }

    // Auto-open active parent
    const activeSub = document.querySelector('.submenu a.active');
    if (activeSub) {
        const parent = activeSub.closest('.has-submenu');
        if (parent) parent.classList.add('open');
    }
});
