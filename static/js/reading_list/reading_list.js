'use strict';

(function () {
    const listEl = document.getElementById('rl-list');
    const emptyEl = document.getElementById('rl-empty');
    const loadingEl = document.getElementById('rl-loading');
    const statusEl = document.getElementById('rl-status');
    const filterEl = document.getElementById('rl-status-filter');

    let moveTarget = null;

    function showStatus(msg, type = 'danger') {
        statusEl.className = `alert alert-${type} mb-3`;
        statusEl.textContent = msg;
        statusEl.classList.remove('d-none');
    }

    function setLoading(on) {
        loadingEl.classList.toggle('d-none', !on);
        listEl.classList.toggle('d-none', on);
    }

    function statusLabel(s) {
        return { unread: 'Unread', reading: 'Reading', done: 'Done' }[s] || s;
    }

    function renderItem(item) {
        const d = document.createElement('div');
        d.className = 'rl-item-card';
        d.dataset.id = item.id;

        const tagHtml = (item.topic_tags || [])
            .map(t => `<span class="badge bg-secondary me-1">${t}</span>`).join('');

        d.innerHTML = `
            <div class="rl-item-body">
                <div class="rl-item-title">
                    ${item.url ? `<a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>` : item.title}
                </div>
                <div class="rl-item-meta mt-1">
                    <span class="badge bg-info text-dark">${statusLabel(item.status)}</span>
                    ${tagHtml}
                </div>
            </div>
            <div class="rl-item-actions">
                <select class="form-select form-select-sm rl-status-select" data-id="${item.id}" style="max-width:110px">
                    <option value="unread" ${item.status === 'unread' ? 'selected' : ''}>Unread</option>
                    <option value="reading" ${item.status === 'reading' ? 'selected' : ''}>Reading</option>
                    <option value="done" ${item.status === 'done' ? 'selected' : ''}>Done</option>
                </select>
                <button class="btn btn-outline-secondary btn-sm rl-move-btn" data-id="${item.id}" title="Add to project">
                    <i class="bi bi-folder-plus"></i>
                </button>
                <button class="btn btn-outline-danger btn-sm rl-delete-btn" data-id="${item.id}" title="Delete">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
        return d;
    }

    function loadList() {
        const status = filterEl.value;
        const qs = status ? `?status=${encodeURIComponent(status)}` : '';
        setLoading(true);
        statusEl.classList.add('d-none');

        fetch(`/reading-list/data${qs}`)
            .then(r => r.json())
            .then(data => {
                setLoading(false);
                listEl.innerHTML = '';
                const items = data.items || [];
                if (items.length === 0) {
                    emptyEl.classList.remove('d-none');
                } else {
                    emptyEl.classList.add('d-none');
                    items.forEach(item => listEl.appendChild(renderItem(item)));
                }
            })
            .catch(() => {
                setLoading(false);
                showStatus('Could not load reading list.');
            });
    }

    listEl.addEventListener('change', function (e) {
        const sel = e.target.closest('.rl-status-select');
        if (!sel) return;
        const id = sel.dataset.id;

        fetch(`/reading-list/${id}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: sel.value }),
        }).then(r => r.json()).then(resp => {
            if (!resp.ok) showStatus(resp.error || 'Status update failed');
        }).catch(() => showStatus('Status update failed'));
    });

    listEl.addEventListener('click', function (e) {
        const moveBtn = e.target.closest('.rl-move-btn');
        if (moveBtn) {
            moveTarget = moveBtn.dataset.id;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('rl-move-modal'));
            loadProjects().then(() => modal.show());
            return;
        }

        const delBtn = e.target.closest('.rl-delete-btn');
        if (delBtn) {
            const id = delBtn.dataset.id;
            if (!confirm('Remove this item from your reading list?')) return;
            fetch(`/reading-list/${id}`, { method: 'DELETE' })
                .then(r => r.json())
                .then(resp => {
                    if (resp.ok) {
                        const card = listEl.querySelector(`.rl-item-card[data-id="${id}"]`);
                        if (card) card.remove();
                        if (!listEl.querySelector('.rl-item-card')) emptyEl.classList.remove('d-none');
                    } else {
                        showStatus(resp.error || 'Delete failed');
                    }
                })
                .catch(() => showStatus('Delete failed'));
        }
    });

    function loadProjects() {
        const sel = document.getElementById('rl-project-select');
        sel.innerHTML = '<option>Loading…</option>';
        return fetch('/projects/')
            .then(r => r.json())
            .then(data => {
                sel.innerHTML = '';
                (data.projects || []).forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.title || p.name;
                    sel.appendChild(opt);
                });
            });
    }

    document.getElementById('rl-move-confirm-btn').addEventListener('click', function () {
        const projectId = document.getElementById('rl-project-select').value;
        if (!moveTarget || !projectId) return;
        fetch(`/reading-list/${moveTarget}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: projectId }),
        }).then(r => r.json()).then(resp => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('rl-move-modal'));
            modal.hide();
            if (resp.ok) {
                showStatus('Added to project successfully.', 'success');
            } else {
                showStatus(resp.error || 'Move failed');
            }
        }).catch(() => showStatus('Move failed'));
    });

    filterEl.addEventListener('change', loadList);

    loadList();
}());
