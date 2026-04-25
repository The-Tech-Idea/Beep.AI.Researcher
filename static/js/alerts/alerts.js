'use strict';

(function () {
    const listEl = document.getElementById('alerts-list');
    const emptyEl = document.getElementById('alerts-empty');
    const loadingEl = document.getElementById('alerts-loading');
    const statusEl = document.getElementById('alerts-status');
    const unreadToggle = document.getElementById('alerts-unread-toggle');
    const markAllBtn = document.getElementById('alerts-mark-all-btn');

    function showStatus(msg, type = 'danger') {
        statusEl.className = `alert alert-${type} mb-3`;
        statusEl.textContent = msg;
        statusEl.classList.remove('d-none');
    }

    function setLoading(on) {
        loadingEl.classList.toggle('d-none', !on);
        listEl.classList.toggle('d-none', on);
    }

    function renderItem(alert) {
        const d = document.createElement('div');
        d.className = 'alert-item-card' + (alert.is_read ? '' : ' is-unread');
        d.dataset.id = alert.id;

        const matchedAt = alert.matched_at || alert.alert_date || alert.created_at;
        const date = matchedAt ? new Date(matchedAt).toLocaleDateString() : '';
        const source = alert.source ? ` · ${alert.source}` : '';

        d.innerHTML = `
            ${!alert.is_read ? '<div class="alert-item-unread-dot"></div>' : '<div style="width:8px"></div>'}
            <div class="alert-item-body">
                <div class="alert-item-title">
                    ${alert.url
                        ? `<a href="${alert.url}" target="_blank" rel="noopener noreferrer">${alert.title}</a>`
                        : alert.title}
                </div>
                <div class="alert-item-meta mt-1">${date}${source}</div>
            </div>
            <div class="alert-item-actions">
                ${!alert.is_read
                    ? `<button class="btn btn-outline-secondary btn-sm alerts-mark-read-btn" data-id="${alert.id}" title="Mark read">
                           <i class="bi bi-check2"></i>
                       </button>`
                    : ''}
            </div>
        `;
        return d;
    }

    function loadAlerts() {
        const qs = unreadToggle.checked ? '?unread=1' : '';
        setLoading(true);
        statusEl.classList.add('d-none');

        fetch(`/alerts/data${qs}`)
            .then(r => r.json())
            .then(data => {
                setLoading(false);
                listEl.innerHTML = '';
                const items = data.alerts || [];
                if (items.length === 0) {
                    emptyEl.classList.remove('d-none');
                } else {
                    emptyEl.classList.add('d-none');
                    items.forEach(item => listEl.appendChild(renderItem(item)));
                }
            })
            .catch(() => {
                setLoading(false);
                showStatus('Could not load alerts.');
            });
    }

    listEl.addEventListener('click', function (e) {
        const btn = e.target.closest('.alerts-mark-read-btn');
        if (!btn) return;
        const id = btn.dataset.id;
        btn.disabled = true;

        fetch(`/alerts/${id}/read`, { method: 'POST' })
            .then(r => r.json())
            .then(resp => {
                if (resp.ok) {
                    const card = listEl.querySelector(`.alert-item-card[data-id="${id}"]`);
                    if (card) {
                        card.classList.remove('is-unread');
                        btn.remove();
                        card.querySelector('.alert-item-unread-dot')?.remove();
                    }
                    window.aiDiscoveryNav?.refreshAlertsCount?.();
                } else {
                    btn.disabled = false;
                    showStatus(resp.error || 'Mark read failed');
                }
            })
            .catch(() => {
                btn.disabled = false;
                showStatus('Mark read failed');
            });
    });

    markAllBtn.addEventListener('click', function () {
        markAllBtn.disabled = true;
        fetch('/alerts/mark-all-read', { method: 'POST' })
            .then(r => r.json())
            .then(resp => {
                markAllBtn.disabled = false;
                if (resp.ok) {
                    window.aiDiscoveryNav?.refreshAlertsCount?.();
                    loadAlerts();
                } else {
                    showStatus(resp.error || 'Mark all read failed');
                }
            })
            .catch(() => {
                markAllBtn.disabled = false;
                showStatus('Mark all read failed');
            });
    });

    unreadToggle.addEventListener('change', loadAlerts);

    loadAlerts();
}());
