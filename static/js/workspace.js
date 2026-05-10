/**
 * Beep.AI.Researcher — SPA Navigation Controller
 * 
 * Converts the multi-page Flask app into a Jenni-style single-page experience.
 * - Sidebar clicks load content via fetch() into the main area
 * - Browser back/forward works via History API
 * - Project selector updates all project-scoped nav links
 * - Sidebar collapse, mobile menu, keyboard shortcuts
 */
(function () {
    'use strict';

    // ─── DOM Lookup ──────────────────────────────────────────
    const sidebar = document.getElementById('spa-sidebar');
    const contentInner = document.getElementById('spa-content-inner');
    const loading = document.getElementById('spa-loading');
    const breadcrumb = document.getElementById('spa-page-title');
    const projectSel = document.getElementById('spa-project-select');

    const collapseBtn = document.getElementById('sidebar-collapse-btn');
    const mobileBtn = document.getElementById('mobile-menu-btn');
    const chatTrigger = document.getElementById('spa-chat-trigger');
    const newProjectBtn = document.getElementById('new-project-btn');

    if (!contentInner) return; // not on SPA page

    // ─── Route Map ───────────────────────────────────────────
    // Maps data-spa-id → URL builder function
    // Only simple top-level pages use SPA partial loading.
    // Project pages use full page navigation (they have their own sidebar/layout).
    const SPA_ROUTES = {
        'dashboard': () => '/researcher/?partial=1',
        'library': () => '/references?partial=1',
        'documents': () => '/researcher/documents?partial=1',
        'agent-plans': () => '/researcher/agent-plans?partial=1',
        'feed': () => '/feed?partial=1',
        'reading-list': () => '/reading-list?partial=1',
        'alerts': () => '/alerts?partial=1',
        'tenants': () => '/researcher/tenants?partial=1',
        'profile': () => '/auth/profile?partial=1',
    };

    // Project routes — full page navigation (no partial)
    const PROJECT_ROUTES = {
        'project-overview': (pid) => `/researcher/projects/${pid}/overview`,
        'project-documents': (pid) => `/researcher/projects/${pid}/documents`,
        'project-search': (pid) => `/researcher/projects/${pid}/search`,
        'project-codes': (pid) => `/researcher/projects/${pid}/codes`,
        'project-data': (pid) => `/researcher/projects/${pid}/data`,
        'project-tasks': (pid) => `/researcher/projects/${pid}/tasks`,
        'project-report': (pid) => `/researcher/projects/${pid}/report`,
        'project-extraction': (pid) => `/researcher/projects/${pid}/extraction`,
        'project-contradictions': (pid) => `/researcher/projects/${pid}/contradictions`,
        'project-matrix': (pid) => `/researcher/projects/${pid}/matrix`,
        'project-document-map': (pid) => `/researcher/projects/${pid}/map`,
        'project-map': (pid) => `/researcher/projects/${pid}/map`,
        'project-flashcards': (pid) => `/researcher/projects/${pid}/flashcards`,
        'project-quizzes': (pid) => `/researcher/projects/${pid}/quizzes`,
        'project-stats': (pid) => `/researcher/projects/${pid}/stats`,
        'project-scheduled-reports': (pid) => `/researcher/projects/${pid}/scheduled-reports`,
        'project-reports': (pid) => `/researcher/projects/${pid}/scheduled-reports`,
        'project-retention': (pid) => `/researcher/projects/${pid}/retention`,
        'project-hallucination': (pid) => `/researcher/projects/${pid}/hallucination-audit`,
        'project-hallucination-audit': (pid) => `/researcher/projects/${pid}/hallucination-audit`,
        'project-members': (pid) => `/researcher/projects/${pid}/members`,
        'project-settings': (pid) => `/researcher/projects/${pid}/settings`,
    };

    // Combined lookup for labels/detection
    const ROUTES = Object.assign({}, SPA_ROUTES, PROJECT_ROUTES);

    // Human-readable labels for breadcrumb
    const LABELS = {
        'dashboard': 'Home',
        'library': 'Library',
        'documents': 'Documents',
        'agent-plans': 'Guided AI Plans',
        'feed': 'My Feed',
        'reading-list': 'Reading List',
        'alerts': 'Alerts',
        'tenants': 'Tenants',
        'profile': 'Profile',
        'project-overview': 'Overview',
        'project-documents': 'Documents',
        'project-search': 'Search & Chat',
        'project-codes': 'Codes',
        'project-data': 'Data & Charts',
        'project-tasks': 'Tasks',
        'project-report': 'Report',
        'project-extraction': 'Extraction',
        'project-contradictions': 'Contradictions',
        'project-matrix': 'Matrix',
        'project-document-map': 'Document Map',
        'project-map': 'Document Map',
        'project-flashcards': 'Flashcards',
        'project-quizzes': 'Quizzes',
        'project-stats': 'Stats',
        'project-scheduled-reports': 'Scheduled Reports',
        'project-reports': 'Scheduled Reports',
        'project-retention': 'Retention',
        'project-hallucination': 'Hallucination Audit',
        'project-hallucination-audit': 'Hallucination Audit',
        'project-members': 'Members',
        'project-settings': 'Settings',
    };

    // ─── State ───────────────────────────────────────────────
    let currentView = 'dashboard';
    let currentProjectId = null;
    let projectsCache = [];

    function toggleContentLoading(isLoading) {
        if (loading) {
            loading.hidden = !isLoading;
        }
        contentInner.classList.toggle('spa-content-inner--loading', isLoading);
        contentInner.setAttribute('aria-busy', isLoading ? 'true' : 'false');
    }

    function createRuntimeState(options) {
        const state = document.createElement('div');
        state.className = `spa-empty spa-runtime-state spa-runtime-state--${options.tone || 'info'}`;

        const icon = document.createElement('i');
        icon.className = `bi ${options.icon} spa-runtime-state__icon`;
        icon.setAttribute('aria-hidden', 'true');
        state.appendChild(icon);

        if (options.title) {
            const title = document.createElement('h4');
            title.className = 'spa-runtime-state__title';
            title.textContent = options.title;
            state.appendChild(title);
        }

        const message = document.createElement('p');
        message.className = 'spa-runtime-state__message';
        message.textContent = options.message;
        state.appendChild(message);

        if (options.actionLabel && typeof options.action === 'function') {
            const action = document.createElement('button');
            action.type = 'button';
            action.className = 'spa-runtime-state__action';
            action.textContent = options.actionLabel;
            action.addEventListener('click', options.action);
            state.appendChild(action);
        }

        return state;
    }

    function renderRuntimeState(options) {
        contentInner.replaceChildren(createRuntimeState(options));
    }

    async function openNewProjectWorkspace() {
        if (currentView !== 'dashboard' || !document.getElementById('newProjectModal')) {
            await navigateTo('dashboard');
        }

        const modalElement = document.getElementById('newProjectModal');
        if (modalElement && window.bootstrap && window.bootstrap.Modal) {
            window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
            return;
        }

        const dashboardUrl = new URL('/researcher/', window.location.origin);
        dashboardUrl.searchParams.set('new_project', '1');
        window.location.href = dashboardUrl.toString();
    }

    // ─── Init: Load Projects List ────────────────────────────
    async function loadProjects() {
        try {
            const resp = await fetch('/researcher/api/projects-list');
            if (resp.ok) {
                projectsCache = await resp.json();
            } else {
                // Fallback: parse from server-rendered HTML if API not available
                projectsCache = [];
            }
        } catch (e) {
            projectsCache = [];
        }
        renderProjectSelect();
    }

    function renderProjectSelect() {
        if (!projectSel) return;
        const saved = localStorage.getItem('spa_project_id');
        let html = '<option value="">— Select Project —</option>';
        projectsCache.forEach(p => {
            const sel = (String(p.id) === saved) ? ' selected' : '';
            html += `<option value="${p.id}"${sel}>${escapeHtml(p.name)}</option>`;
        });
        projectSel.innerHTML = html;

        // Restore saved project
        if (saved && projectsCache.find(p => String(p.id) === saved)) {
            currentProjectId = saved;
        }
    }

    // ─── SPA Navigation Core ─────────────────────────────────
    async function navigateTo(viewId, pushState = true) {
        const routeFn = ROUTES[viewId];
        if (!routeFn) {
            console.warn('Unknown SPA view:', viewId);
            return;
        }

        // Project-scoped views need a project selected
        if (viewId.startsWith('project-')) {
            if (!currentProjectId) {
                showNoProjectMessage();
                return;
            }
            // Project pages do full page navigation — they have their own layout
            const url = routeFn(currentProjectId);
            localStorage.setItem('spa_project_id', currentProjectId);
            window.location.href = url;
            return;
        }

        const url = routeFn();

        // Show loading
        toggleContentLoading(true);

        try {
            const resp = await fetch(url, {
                headers: { 'X-Requested-With': 'SPA' }
            });

            if (resp.redirected) {
                // Auth redirect etc — do full navigation
                window.location.href = resp.url;
                return;
            }

            if (!resp.ok) {
                renderRuntimeState({
                    tone: 'warning',
                    icon: 'bi-exclamation-triangle',
                    title: 'Could not open this page',
                    message: `Failed to load content (${resp.status}).`,
                    actionLabel: 'Go Home',
                    action: () => navigateTo('dashboard'),
                });
                return;
            }

            const html = await resp.text();
            contentInner.innerHTML = html;
            currentView = viewId;

            // Scroll to top BEFORE updating UI to prevent scroll jump
            const spaContent = document.getElementById('spa-content');
            if (spaContent) spaContent.scrollTop = 0;

            // Update UI
            updateActiveNav(viewId);
            updateBreadcrumb(viewId);
            reInitScripts();

            // Push browser history
            if (pushState) {
                const stateUrl = url.replace('?partial=1', '').replace('&partial=1', '');
                history.pushState({ view: viewId, projectId: currentProjectId }, '', stateUrl);
            }

        } catch (err) {
            console.error('SPA navigation error:', err);
            renderRuntimeState({
                tone: 'danger',
                icon: 'bi-wifi-off',
                title: 'Network error',
                message: 'Check your connection and try again.',
                actionLabel: 'Retry',
                action: () => navigateTo(viewId),
            });
        } finally {
            toggleContentLoading(false);
        }
    }

    function showNoProjectMessage() {
        renderRuntimeState({
            tone: 'info',
            icon: 'bi-folder2-open',
            title: 'Select a Project',
            message: 'Choose a project from the sidebar to get started.',
            actionLabel: 'Open Home',
            action: () => navigateTo('dashboard'),
        });
    }

    // ─── Active State & Breadcrumb ───────────────────────────
    function updateActiveNav(viewId) {
        document.querySelectorAll('.spa-nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.spaId === viewId);
        });
    }

    function updateBreadcrumb(viewId) {
        if (!breadcrumb) return;
        let label = LABELS[viewId] || 'Home';
        if (viewId.startsWith('project-') && currentProjectId) {
            const proj = projectsCache.find(p => String(p.id) === String(currentProjectId));
            if (proj) {
                label = `${escapeHtml(proj.name)} / ${label}`;
            }
        }
        breadcrumb.textContent = label;
    }

    // ─── Re-init JS in loaded content ────────────────────────
    function reInitScripts() {
        // Execute any inline <script> tags in loaded content
        const scripts = contentInner.querySelectorAll('script');
        scripts.forEach(oldScript => {
            // Skip non-executable script types (JSON data blocks, templates, etc.)
            if (oldScript.type && oldScript.type !== 'text/javascript' && oldScript.type !== 'module') return;

            const newScript = document.createElement('script');
            // Copy ALL attributes (id, src, type, data-*, etc.) from the original
            Array.from(oldScript.attributes).forEach(attr => {
                newScript.setAttribute(attr.name, attr.value);
            });
            if (!oldScript.src) {
                newScript.textContent = `(()=>{${oldScript.textContent}})();`;
            }
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });

        // Re-init Bootstrap tooltips & dropdowns
        const tooltipTriggerList = contentInner.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));

        // Re-bind any inner SPA links
        bindInnerLinks();
    }

    function bindInnerLinks() {
        // Links inside loaded content that should use SPA navigation
        contentInner.querySelectorAll('a[data-spa-link]').forEach(bindNavLink);

        // Project links in loaded content — let them navigate normally (full page)
        // No interception needed; project pages use full page loads.
    }

    // ─── Project Select Handler ──────────────────────────────

    if (projectSel) {
        projectSel.addEventListener('change', function () {
            currentProjectId = this.value || null;
            if (currentProjectId) {
                localStorage.setItem('spa_project_id', currentProjectId);
                // Full page navigation to project overview
                window.location.href = `/researcher/projects/${currentProjectId}/overview`;
            } else {
                localStorage.removeItem('spa_project_id');
                navigateTo('dashboard');
            }
        });
    }

    // ─── Sidebar Collapse ────────────────────────────────────
    if (collapseBtn) {
        const saved = localStorage.getItem('spa_sidebar_collapsed');
        if (saved === '1') sidebar.classList.add('collapsed');

        collapseBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('spa_sidebar_collapsed', sidebar.classList.contains('collapsed') ? '1' : '0');
        });
    }

    // ─── Mobile Menu ─────────────────────────────────────────
    if (mobileBtn) {
        mobileBtn.addEventListener('click', () => {
            document.getElementById('workspaceSidebar')?.classList.remove('open');
            sidebar.classList.toggle('mobile-open');
        });
        // Close on content click (mobile)
        document.getElementById('spa-main')?.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
        });
    }

    // ─── Keyboard Shortcuts ──────────────────────────────────
    document.addEventListener('keydown', (e) => {
        // Ctrl+Shift+A → toggle chat
        if (e.ctrlKey && e.shiftKey && e.key === 'A') {
            e.preventDefault();
            const chatPanel = document.getElementById('chat-panel');
            if (chatPanel) chatPanel.classList.toggle('open');
            document.body.classList.toggle('chat-panel-open');
        }
        // Ctrl+Shift+S → toggle sidebar
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            e.preventDefault();
            sidebar?.classList.toggle('collapsed');
        }
    });

    // ─── Chat Trigger ────────────────────────────────────────
    if (chatTrigger) {
        chatTrigger.addEventListener('click', () => {
            const chatPanel = document.getElementById('chat-panel');
            if (chatPanel) chatPanel.classList.toggle('open');
            document.body.classList.toggle('chat-panel-open');
        });
    }

    // ─── New Project Button ──────────────────────────────────
    if (newProjectBtn) {
        newProjectBtn.addEventListener('click', async () => {
            try {
                await openNewProjectWorkspace();
            } catch (err) {
                console.error('Unable to open the new project flow.', err);
                const dashboardUrl = new URL('/researcher/', window.location.origin);
                dashboardUrl.searchParams.set('new_project', '1');
                window.location.href = dashboardUrl.toString();
            }
        });
    }

    // ─── Bind Sidebar Nav Links ──────────────────────────────
    function bindNavLink(el) {
        if (el.hasAttribute('data-spa-bound')) return;
        el.setAttribute('data-spa-bound', '1');

        el.addEventListener('click', function (e) {
            const viewId = this.dataset.spaId;
            if (!viewId) return; // let it navigate normally (logout, admin, etc.)

            // Project tabs need a project
            if (this.hasAttribute('data-spa-project-tab') && !currentProjectId) {
                e.preventDefault();
                showNoProjectMessage();
                return;
            }

            e.preventDefault();
            navigateTo(viewId);
            // Close mobile sidebar
            sidebar.classList.remove('mobile-open');
        });
    }

    document.querySelectorAll('.spa-nav-item[data-spa-link]').forEach(bindNavLink);

    // ─── Browser Back/Forward ────────────────────────────────
    window.addEventListener('popstate', (e) => {
        if (e.state?.view) {
            currentProjectId = e.state.projectId || null;
            if (projectSel && currentProjectId) projectSel.value = currentProjectId;
            navigateTo(e.state.view, false);
        }
    });

    // ─── Initial State ───────────────────────────────────────
    // Set initial history state
    history.replaceState({ view: 'dashboard', projectId: null }, '', window.location.href);

    // Load projects and detect current view from URL
    loadProjects().then(() => {
        const path = window.location.pathname;
        const match = path.match(/\/researcher\/projects\/(\d+)\/([\w-]+)/);
        if (match) {
            currentProjectId = match[1];
            localStorage.setItem('spa_project_id', currentProjectId);
            if (projectSel) projectSel.value = currentProjectId;
            const viewId = 'project-' + match[2];
            if (ROUTES[viewId]) {
                updateActiveNav(viewId);
                updateBreadcrumb(viewId);
                currentView = viewId;
            }
        } else if (path.includes('/references')) {
            updateActiveNav('library');
            currentView = 'library';
        } else if (path.includes('/tenants')) {
            updateActiveNav('tenants');
            currentView = 'tenants';
        } else {
            updateActiveNav('dashboard');
            currentView = 'dashboard';
        }
        // Bind inner links in the server-rendered initial content
        bindInnerLinks();
    });

    // ─── Helpers ─────────────────────────────────────────────
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ─── Public API ──────────────────────────────────────────
    window.BeepSPA = {
        navigateTo,
        loadProjects,
        getCurrentProject: () => currentProjectId,
        setProject: (id) => {
            currentProjectId = id;
            if (projectSel) projectSel.value = id;
            localStorage.setItem('spa_project_id', id);
        },
    };

})();
