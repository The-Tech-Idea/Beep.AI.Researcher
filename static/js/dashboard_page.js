(function () {
    'use strict';

    function getConfig() {
        var element = document.getElementById('dashboard-page-config');
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error('Failed to parse dashboard page config.', error);
            return null;
        }
    }

    function navigateSpa(route) {
        if (window.BeepSPA && route) {
            window.BeepSPA.navigateTo(route);
            return true;
        }

        return false;
    }

    function showDashboardMessage(message, variant) {
        if (!message) {
            return;
        }

        window.beepUI.notify(message, { variant: variant || 'info' });
    }

    function openProjectModal() {
        var modalElement = document.getElementById('newProjectModal');
        if (!modalElement || typeof bootstrap === 'undefined' || !bootstrap.Modal) {
            return false;
        }

        bootstrap.Modal.getOrCreateInstance(modalElement).show();
        return true;
    }

    function maybeOpenProjectModalFromUrl() {
        var currentUrl = new URL(window.location.href);
        if (currentUrl.searchParams.get('new_project') !== '1') {
            return;
        }

        if (!openProjectModal()) {
            return;
        }

        currentUrl.searchParams.delete('new_project');
        var cleanUrl = currentUrl.pathname + (currentUrl.search ? currentUrl.search : '') + currentUrl.hash;
        window.history.replaceState(window.history.state, '', cleanUrl);
    }

    function bindTenantFilter(config) {
        var tenantFilter = document.getElementById('tenantFilter');
        if (!tenantFilter) {
            return;
        }

        tenantFilter.addEventListener('change', function () {
            var value = tenantFilter.value;
            window.location.href = value ? config.baseUrl + '?tenant_id=' + value : config.baseUrl;
        });
    }

    function bindFeatureCards() {
        document.querySelectorAll('[data-dashboard-route]').forEach(function (card) {
            function handleActivation() {
                navigateSpa(card.dataset.dashboardRoute);
            }

            card.addEventListener('click', handleActivation);
            card.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleActivation();
                }
            });
        });
    }

    function bindProjectCards(config) {
        document.querySelectorAll('.spa-project-card[data-project-id]').forEach(function (card) {
            function handleActivation() {
                var projectId = card.dataset.projectId;
                var projectUrl = card.dataset.projectUrl;
                if (window.BeepSPA && projectId) {
                    window.BeepSPA.setProject(parseInt(projectId, 10));
                    window.BeepSPA.navigateTo(config.defaultProjectRoute);
                    return;
                }

                if (projectUrl) {
                    window.location.href = projectUrl;
                }
            }

            card.addEventListener('click', handleActivation);
            card.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleActivation();
                }
            });
        });
    }

    function bindProjectCreation(config) {
        var createButton = document.getElementById('btnCreateProject');
        if (!createButton) {
            return;
        }

        createButton.addEventListener('click', async function () {
            var name = document.getElementById('newProjectName').value.trim();
            if (!name) {
                showDashboardMessage(config.projectNameRequired, 'danger');
                return;
            }

            var description = document.getElementById('newProjectDesc').value.trim();
            var tenantSelect = document.getElementById('newProjectTenant');
            var tenantId = tenantSelect ? tenantSelect.value : null;
            var body = { name: name, description: description };
            if (tenantId) {
                body.tenant_id = parseInt(tenantId, 10);
            }

            try {
                var response = await fetch(config.createProjectUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                var payload = {};

                try {
                    payload = await response.json();
                } catch (error) {
                    payload = {};
                }

                if (response.ok && payload.id) {
                    if (window.BeepSPA) {
                        window.BeepSPA.setProject(payload.id);
                        window.BeepSPA.loadProjects();
                    }

                    var modalElement = document.getElementById('newProjectModal');
                    var modal = modalElement && typeof bootstrap !== 'undefined' && bootstrap.Modal
                        ? bootstrap.Modal.getOrCreateInstance(modalElement)
                        : null;
                    if (modal) {
                        modal.hide();
                    }

                    window.location.href = payload.start_url || ('/researcher/projects/' + payload.id + '/start');
                    return;
                }

                showDashboardMessage(payload.error || config.createFailed, 'danger');
            } catch (error) {
                console.error('Failed to create project from dashboard modal.', error);
                showDashboardMessage(config.createFailed, 'danger');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var config = getConfig();
        if (!config) {
            return;
        }

        bindTenantFilter(config);
        bindFeatureCards();
        bindProjectCards(config);
        bindProjectCreation(config);
        maybeOpenProjectModalFromUrl();
    });
})();
