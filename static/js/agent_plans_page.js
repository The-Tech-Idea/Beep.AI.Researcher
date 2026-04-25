(function () {
    'use strict';

    function $(id) {
        return document.getElementById(id);
    }

    function getTranslations() {
        var element = $('agent-plans-i18n');
        if (!element) {
            return {};
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error('Failed to parse agent plans translations.', error);
            return {};
        }
    }

    function translate(translations, key, vars) {
        var text = translations[key] || key;
        if (!vars) {
            return text;
        }

        Object.keys(vars).forEach(function (name) {
            text = text.replace('{' + name + '}', vars[name]);
        });
        return text;
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function getStatusBadgeClass(normalizedStatus) {
        if (normalizedStatus.includes('wait')) {
            return 'agent-plans-status-badge-waiting';
        }
        if (normalizedStatus.includes('complete') || normalizedStatus.includes('success')) {
            return 'agent-plans-status-badge-completed';
        }
        if (normalizedStatus.includes('error') || normalizedStatus.includes('fail')) {
            return 'agent-plans-status-badge-failed';
        }
        if (normalizedStatus.includes('run') || normalizedStatus.includes('progress') || normalizedStatus.includes('execut')) {
            return 'agent-plans-status-badge-running';
        }
        return 'agent-plans-status-badge-default';
    }

    async function api(url, method, body) {
        var response = await fetch(url, {
            method: method || 'GET',
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined
        });
        var payload = await response.json().catch(function () { return {}; });
        if (!response.ok || payload.success === false) {
            throw new Error(payload.error || payload.message || ('HTTP ' + response.status));
        }
        return payload;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var translations = getTranslations();
        var objectiveEl = $('planObjective');
        var includeProjectEl = $('includeSelectedProject');
        var statusBadgeEl = $('statusBadge');
        var sessionMetaEl = $('sessionMeta');
        var statusJsonEl = $('planStatusJson');
        var friendlySummaryEl = $('friendlySummary');
        var planTimelineEl = $('planTimeline');
        var approvalHintEl = $('approvalHint');
        var runBtn = $('runPlanBtn');
        var approveBtn = $('approveBtn');
        var rejectBtn = $('rejectBtn');
        var tableBody = $('plansTableBody');
        var createPlanBtn = $('createPlanBtn');
        var refreshBtn = $('plansRefreshBtn');
        var currentSessionId = null;

        function setButtonsEnabled(enabled) {
            runBtn.disabled = !enabled;
            approveBtn.disabled = !enabled;
            rejectBtn.disabled = !enabled;
        }

        function toStatusLabel(status) {
            var normalized = String(status || '').toLowerCase();
            if (normalized.includes('complete') || normalized.includes('success') || normalized === 'done') {
                return translate(translations, 'status_completed');
            }
            if (normalized.includes('wait')) {
                return translate(translations, 'status_waiting');
            }
            if (normalized.includes('run') || normalized.includes('progress') || normalized.includes('execut')) {
                return translate(translations, 'status_running');
            }
            if (normalized.includes('error') || normalized.includes('fail')) {
                return translate(translations, 'status_failed');
            }
            if (!normalized) {
                return translate(translations, 'status_unknown');
            }
            return normalized.charAt(0).toUpperCase() + normalized.slice(1);
        }

        function setStatusText(status) {
            var normalized = String(status || '').toLowerCase();
            statusBadgeEl.textContent = status || 'unknown';
            statusBadgeEl.className = 'badge agent-plans-status-badge ' + getStatusBadgeClass(normalized);
        }

        function summarizeCurrentStep(data) {
            var total = data.total_steps || 0;
            var idx = data.current_step_index || 0;
            var statusLabel = toStatusLabel(data.status);
            var step = data.current_step || null;
            var stepType = step && step.type ? String(step.type).replace(/_/g, ' ') : null;
            var reason = data.awaiting_approval_reason || (step && step.reason) || '';

            if (statusLabel === translate(translations, 'status_waiting')) {
                return reason
                    ? translate(translations, 'summary_waiting_reason', { reason: reason })
                    : translate(translations, 'summary_waiting');
            }
            if (statusLabel === translate(translations, 'status_completed')) {
                return total
                    ? translate(translations, 'summary_completed', { total: total })
                    : translate(translations, 'summary_completed_nototal');
            }
            if (statusLabel === translate(translations, 'status_running')) {
                return stepType
                    ? translate(translations, 'summary_running_type', { idx: idx || '?', total: total || '?', type: stepType })
                    : translate(translations, 'summary_running', { idx: idx || '?', total: total || '?' });
            }
            if (statusLabel === translate(translations, 'status_failed')) {
                return translate(translations, 'summary_failed');
            }
            return translate(translations, 'summary_default', { status: statusLabel });
        }

        function renderTimeline(data) {
            var steps = Array.isArray(data.steps) ? data.steps : [];
            if (!steps.length) {
                planTimelineEl.innerHTML = '<li class="list-group-item small text-muted">' + translate(translations, 'no_steps') + '</li>';
                return;
            }

            planTimelineEl.innerHTML = steps.map(function (step, index) {
                var label = toStatusLabel(step.status);
                var type = (step.type || ('step_' + (index + 1))).replace(/_/g, ' ');
                var description = step.description || step.reason || '';
                var badgeClass = getStatusBadgeClass(String(step.status || '').toLowerCase());

                return (
                    '<li class="list-group-item">' +
                        '<div class="d-flex justify-content-between align-items-center gap-2">' +
                            '<div>' +
                                '<div class="small fw-semibold">' + escapeHtml(translate(translations, 'step_label', { n: index + 1, type: type })) + '</div>' +
                                (description ? '<div class="small text-muted">' + escapeHtml(description) + '</div>' : '') +
                            '</div>' +
                            '<span class="badge agent-plans-status-badge ' + badgeClass + '">' + escapeHtml(label) + '</span>' +
                        '</div>' +
                    '</li>'
                );
            }).join('');
        }

        function selectedProjectId() {
            var saved = window.localStorage.getItem('spa_project_id');
            if (!saved || !includeProjectEl.checked) {
                return null;
            }
            var parsed = parseInt(saved, 10);
            return Number.isFinite(parsed) ? parsed : null;
        }

        function renderSessions(sessions) {
            if (!Array.isArray(sessions) || !sessions.length) {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-muted small">' + translate(translations, 'no_sessions') + '</td></tr>';
                return;
            }

            tableBody.innerHTML = sessions.map(function (session) {
                var status = session.status || 'unknown';
                return (
                    '<tr data-session-id="' + escapeHtml(session.session_id || '') + '">' +
                        '<td class="small">' + escapeHtml(session.session_id || '') + '</td>' +
                        '<td><span class="badge agent-plans-status-badge agent-plans-status-badge-light">' + escapeHtml(status) + '</span></td>' +
                        '<td class="small">' + escapeHtml(session.objective || '-') + '</td>' +
                        '<td class="small">' + escapeHtml(session.updated_at || session.created_at || '-') + '</td>' +
                        '<td class="text-end"><button class="btn btn-outline-primary btn-sm plan-open-btn" data-session-id="' + escapeHtml(session.session_id || '') + '">' + escapeHtml(translate(translations, 'open_btn')) + '</button></td>' +
                    '</tr>'
                );
            }).join('');
        }

        async function loadSessions() {
            var data = await api('/researcher/api/agent-plans/list?limit=30');
            renderSessions(data.sessions || []);
        }

        async function loadStatus(sessionId) {
            var data = await api('/researcher/api/agent-plans/' + encodeURIComponent(sessionId) + '/status');
            currentSessionId = data.session_id || sessionId;
            setButtonsEnabled(true);
            setStatusText(data.status);
            sessionMetaEl.textContent = translate(translations, 'session_meta', {
                id: currentSessionId,
                idx: data.current_step_index || 0,
                total: data.total_steps || 0
            });
            friendlySummaryEl.textContent = summarizeCurrentStep(data);
            renderTimeline(data);
            statusJsonEl.textContent = JSON.stringify(data, null, 2);
            approvalHintEl.classList.toggle('d-none', !String(data.status || '').toLowerCase().includes('wait'));
        }

        async function createPlan() {
            var objective = (objectiveEl.value || '').trim();
            if (!objective) {
                alert(translate(translations, 'alert_no_objective'));
                return;
            }

            var payload = { objective: objective };
            var projectId = selectedProjectId();
            if (projectId) {
                payload.project_id = projectId;
            }

            var data = await api('/researcher/api/agent-plans/create', 'POST', payload);
            if (!data.session_id) {
                throw new Error('Session ID was not returned.');
            }

            objectiveEl.value = '';
            await loadSessions();
            await loadStatus(data.session_id);
        }

        async function runPlan() {
            if (!currentSessionId) {
                return;
            }

            var data = await api('/researcher/api/agent-plans/' + encodeURIComponent(currentSessionId) + '/execute', 'POST', {
                max_iterations: 8,
                timeout_seconds: 45
            });
            await loadStatus(data.session_id || currentSessionId);
            await loadSessions();
        }

        async function submitApproval(approved) {
            if (!currentSessionId) {
                return;
            }

            var notes = window.prompt(approved ? translate(translations, 'approve_prompt') : translate(translations, 'reject_prompt'), '') || '';
            var data = await api('/researcher/api/agent-plans/' + encodeURIComponent(currentSessionId) + '/approve', 'POST', {
                approved: approved,
                notes: notes
            });
            await loadStatus(data.session_id || currentSessionId);
            await loadSessions();
        }

        document.addEventListener('click', async function (event) {
            var openButton = event.target.closest('.plan-open-btn');
            if (!openButton) {
                return;
            }

            var sessionId = openButton.getAttribute('data-session-id');
            if (!sessionId) {
                return;
            }

            try {
                await loadStatus(sessionId);
            } catch (error) {
                alert(error.message);
            }
        });

        createPlanBtn.addEventListener('click', async function () {
            try {
                await createPlan();
            } catch (error) {
                alert(error.message);
            }
        });
        runBtn.addEventListener('click', async function () {
            try {
                await runPlan();
            } catch (error) {
                alert(error.message);
            }
        });
        approveBtn.addEventListener('click', async function () {
            try {
                await submitApproval(true);
            } catch (error) {
                alert(error.message);
            }
        });
        rejectBtn.addEventListener('click', async function () {
            try {
                await submitApproval(false);
            } catch (error) {
                alert(error.message);
            }
        });
        refreshBtn.addEventListener('click', async function () {
            try {
                await loadSessions();
                if (currentSessionId) {
                    await loadStatus(currentSessionId);
                }
            } catch (error) {
                alert(error.message);
            }
        });

        if (window.__agentPlansRefreshTimer) {
            clearInterval(window.__agentPlansRefreshTimer);
        }
        window.__agentPlansRefreshTimer = setInterval(async function () {
            try {
                if (currentSessionId) {
                    await loadStatus(currentSessionId);
                }
                await loadSessions();
            } catch (error) {
                // Keep the page stable if polling fails.
            }
        }, 10000);

        statusBadgeEl.textContent = translate(translations, 'no_session_badge');
        sessionMetaEl.textContent = translate(translations, 'select_session');
        friendlySummaryEl.textContent = translate(translations, 'no_session_summary');
        setButtonsEnabled(false);
    });
})();
