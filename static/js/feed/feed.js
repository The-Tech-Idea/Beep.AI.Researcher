/* global: spa (optional) */
'use strict';

(function () {
    const list = document.getElementById('feed-list');
    const empty = document.getElementById('feed-empty');
    const loading = document.getElementById('feed-loading');
    const status = document.getElementById('feed-status');
    const projectSelect = document.getElementById('feed-project-select');
    const projectConfirmBtn = document.getElementById('feed-save-project-confirm-btn');
    const speedStorageKey = 'feedAudioPlaybackRate';

    let saveProjectTarget = null;

    function showStatus(msg, type = 'danger') {
        status.className = `alert alert-${type} mb-3`;
        status.textContent = msg;
        status.classList.remove('d-none');
    }

    function hideStatus() {
        status.classList.add('d-none');
    }

    function setLoading(on) {
        loading.classList.toggle('d-none', !on);
        list.classList.toggle('d-none', on);
    }

    function renderScore(score) {
        const pct = Math.round((score || 0) * 100);
        let cls = 'secondary';
        if (pct >= 70) cls = 'success';
        else if (pct >= 40) cls = 'warning';
        return `<span class="badge bg-${cls} feed-relevance-badge">${pct}% match</span>`;
    }

    function renderItem(item) {
        const d = document.createElement('div');
        const isDismissed = Boolean(item.is_dismissed ?? item.dismissed);
        const isSaved = Boolean(item.is_saved ?? item.saved);
        d.className = 'feed-item-card' + (isDismissed ? ' is-dismissed' : '');
        d.dataset.id = item.id;

        let date = '';
        if (item.publication_date) {
            date = ` · Published ${item.publication_date}`;
        } else if (item.recommended_date) {
            date = ` · Recommended ${item.recommended_date}`;
        }
        const source = item.source ? ` · ${item.source}` : '';
        const authors = item.authors ? `<span>${item.authors}</span>` : '';
        const reason = item.reason ? `<div class="feed-item-reason">${item.reason}</div>` : '';

        d.innerHTML = `
            <div class="d-flex justify-content-between align-items-start gap-2">
                <div class="feed-item-title">
                    ${item.url
                        ? `<a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>`
                        : item.title}
                </div>
                <div>${renderScore(item.relevance_score)}</div>
            </div>
            <div class="feed-item-meta">${authors}${date}${source}</div>
            ${reason}
            ${item.abstract ? `<div class="feed-item-abstract">${item.abstract}</div>` : ''}
            <div class="feed-item-actions">
                <button class="btn btn-outline-primary btn-sm feed-save-btn" data-id="${item.id}" ${isSaved ? 'disabled' : ''}>
                    <i class="bi bi-bookmark me-1"></i>${isSaved ? 'Saved' : 'Save'}
                </button>
                <button class="btn btn-outline-secondary btn-sm feed-project-btn" data-id="${item.id}" ${isSaved ? 'disabled' : ''}>
                    <i class="bi bi-folder-plus me-1"></i>Project
                </button>
                <button class="btn btn-outline-secondary btn-sm feed-listen-btn" data-id="${item.id}">
                    <i class="bi bi-headphones me-1"></i>Listen
                </button>
                <button class="btn btn-outline-secondary btn-sm feed-dismiss-btn" data-id="${item.id}" ${isDismissed ? 'disabled' : ''}>
                    <i class="bi bi-eye-slash me-1"></i>${isDismissed ? 'Dismissed' : 'Dismiss'}
                </button>
            </div>
            <div class="feed-item-audio-slot"></div>
        `;
        return d;
    }

    function getStoredPlaybackRate() {
        const stored = window.localStorage.getItem(speedStorageKey);
        return ['0.75', '1', '1.25', '1.5', '2'].includes(stored) ? stored : '1';
    }

    function pauseOtherPlayers(exceptCardId) {
        list.querySelectorAll('.feed-item-card').forEach(card => {
            if (card.dataset.id === String(exceptCardId)) return;
            const audio = card.querySelector('.feed-audio-player');
            if (audio) {
                audio.pause();
            }
        });
    }

    function removeAudioPlayer(card) {
        if (!card) return;
        const slot = card.querySelector('.feed-item-audio-slot');
        const audio = slot?.querySelector('.feed-audio-player');
        if (audio) {
            audio.pause();
            if (audio.dataset.objectUrl) {
                URL.revokeObjectURL(audio.dataset.objectUrl);
            }
        }
        if (slot) {
            slot.innerHTML = '';
        }
    }

    function renderAudioPlayer(card, audioBlob) {
        const slot = card.querySelector('.feed-item-audio-slot');
        if (!slot) return;

        removeAudioPlayer(card);

        const objectUrl = URL.createObjectURL(audioBlob);
        const selectedRate = getStoredPlaybackRate();
        slot.innerHTML = `
            <div class="feed-item-audio">
                <audio class="feed-audio-player" controls preload="metadata"></audio>
                <div class="feed-item-audio-toolbar">
                    <label class="feed-item-audio-speed-label" for="feed-audio-speed-${card.dataset.id}">Speed</label>
                    <select class="form-select form-select-sm feed-audio-speed-select" id="feed-audio-speed-${card.dataset.id}">
                        <option value="0.75" ${selectedRate === '0.75' ? 'selected' : ''}>0.75x</option>
                        <option value="1" ${selectedRate === '1' ? 'selected' : ''}>1x</option>
                        <option value="1.25" ${selectedRate === '1.25' ? 'selected' : ''}>1.25x</option>
                        <option value="1.5" ${selectedRate === '1.5' ? 'selected' : ''}>1.5x</option>
                        <option value="2" ${selectedRate === '2' ? 'selected' : ''}>2x</option>
                    </select>
                    <button class="btn btn-outline-secondary btn-sm feed-audio-close-btn" type="button">Close</button>
                </div>
            </div>
        `;

        const audio = slot.querySelector('.feed-audio-player');
        const speedSelect = slot.querySelector('.feed-audio-speed-select');
        const closeBtn = slot.querySelector('.feed-audio-close-btn');
        audio.src = objectUrl;
        audio.dataset.objectUrl = objectUrl;
        audio.playbackRate = Number(selectedRate);

        audio.addEventListener('play', () => pauseOtherPlayers(card.dataset.id));
        speedSelect.addEventListener('change', () => {
            audio.playbackRate = Number(speedSelect.value);
            window.localStorage.setItem(speedStorageKey, speedSelect.value);
        });
        closeBtn.addEventListener('click', () => removeAudioPlayer(card));

        audio.play().catch(() => {});
    }

    function markCardSaved(card) {
        if (!card) return;

        const saveBtn = card.querySelector('.feed-save-btn');
        const projectBtn = card.querySelector('.feed-project-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="bi bi-bookmark-check me-1"></i>Saved';
        }
        if (projectBtn) {
            projectBtn.disabled = true;
            projectBtn.innerHTML = '<i class="bi bi-folder-check me-1"></i>Saved';
        }
    }

    function loadFeed(force) {
        setLoading(true);
        hideStatus();

        const url = force ? '/feed/refresh' : '/feed/data';
        const opts = force ? { method: 'POST' } : { method: 'GET' };

        fetch(url, opts)
            .then(r => r.json())
            .then(data => {
                setLoading(false);
                list.innerHTML = '';
                const items = data.items || [];
                if (items.length === 0) {
                    empty.classList.remove('d-none');
                } else {
                    empty.classList.add('d-none');
                    items.forEach(item => list.appendChild(renderItem(item)));
                }
            })
            .catch(() => {
                setLoading(false);
                showStatus('Could not load feed. Please try again.');
            });
    }

    function dismiss(itemId) {
        return fetch(`/feed/${itemId}/dismiss`, { method: 'POST' })
            .then(r => r.json());
    }

    function saveItem(itemId) {
        return fetch(`/feed/${itemId}/save`, { method: 'POST' })
            .then(r => r.json());
    }

    function loadProjects() {
        projectSelect.innerHTML = '<option>Loading…</option>';
        projectConfirmBtn.disabled = true;

        return fetch('/projects/')
            .then(r => r.json())
            .then(data => {
                projectSelect.innerHTML = '';
                const projects = data.projects || [];
                if (!projects.length) {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'No projects available';
                    projectSelect.appendChild(opt);
                    projectConfirmBtn.disabled = true;
                    return;
                }

                projects.forEach(project => {
                    const opt = document.createElement('option');
                    opt.value = project.id;
                    opt.textContent = project.title || project.name;
                    projectSelect.appendChild(opt);
                });
                projectConfirmBtn.disabled = false;
            });
    }

    function saveToProject(itemId, projectId) {
        return fetch(`/feed/${itemId}/save-to-project`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: projectId }),
        }).then(r => r.json());
    }

    async function loadAudioSummary(itemId) {
        const response = await fetch(`/feed/${itemId}/audio-summary`);
        if (!response.ok) {
            let message = 'Listen failed';
            try {
                const payload = await response.json();
                message = payload.error || message;
            } catch (_) {
                // Ignore JSON parse failures for binary/error responses.
            }
            throw new Error(message);
        }
        return response.blob();
    }

    list.addEventListener('click', function (e) {
        const dismissBtn = e.target.closest('.feed-dismiss-btn');
        if (dismissBtn) {
            const id = dismissBtn.dataset.id;
            dismissBtn.disabled = true;
            dismiss(id).then(resp => {
                if (resp.ok) {
                    const card = list.querySelector(`.feed-item-card[data-id="${id}"]`);
                    if (card) card.classList.add('is-dismissed');
                } else {
                    dismissBtn.disabled = false;
                    showStatus(resp.error || 'Dismiss failed');
                }
            }).catch(() => {
                dismissBtn.disabled = false;
                showStatus('Dismiss failed');
            });
        }

        const saveBtn = e.target.closest('.feed-save-btn');
        if (saveBtn) {
            const id = saveBtn.dataset.id;
            saveBtn.disabled = true;
            saveItem(id).then(resp => {
                if (resp.ok) {
                    const card = list.querySelector(`.feed-item-card[data-id="${id}"]`);
                    markCardSaved(card);
                } else {
                    saveBtn.disabled = false;
                    showStatus(resp.error || 'Save failed');
                }
            }).catch(() => {
                saveBtn.disabled = false;
                showStatus('Save failed');
            });
            return;
        }

        const projectBtn = e.target.closest('.feed-project-btn');
        if (projectBtn) {
            saveProjectTarget = projectBtn.dataset.id;
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('feed-save-project-modal'));
            loadProjects()
                .then(() => modal.show())
                .catch(() => showStatus('Could not load projects.'));
            return;
        }

        const listenBtn = e.target.closest('.feed-listen-btn');
        if (listenBtn) {
            const id = listenBtn.dataset.id;
            const card = list.querySelector(`.feed-item-card[data-id="${id}"]`);
            const existingAudio = card?.querySelector('.feed-audio-player');
            if (existingAudio) {
                if (existingAudio.paused) {
                    pauseOtherPlayers(id);
                    existingAudio.play().catch(() => {});
                } else {
                    existingAudio.pause();
                }
                return;
            }

            listenBtn.disabled = true;
            listenBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Loading';
            loadAudioSummary(id)
                .then(audioBlob => {
                    listenBtn.disabled = false;
                    listenBtn.innerHTML = '<i class="bi bi-headphones me-1"></i>Listen';
                    if (card) {
                        renderAudioPlayer(card, audioBlob);
                    }
                })
                .catch(error => {
                    listenBtn.disabled = false;
                    listenBtn.innerHTML = '<i class="bi bi-headphones me-1"></i>Listen';
                    showStatus(error.message || 'Listen failed');
                });
        }
    });

    projectConfirmBtn.addEventListener('click', function () {
        const projectId = projectSelect.value;
        if (!saveProjectTarget || !projectId) return;

        projectConfirmBtn.disabled = true;
        saveToProject(saveProjectTarget, projectId)
            .then(resp => {
                projectConfirmBtn.disabled = false;
                if (resp.ok) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('feed-save-project-modal'));
                    modal?.hide();
                    const card = list.querySelector(`.feed-item-card[data-id="${saveProjectTarget}"]`);
                    markCardSaved(card);
                    showStatus('Saved to project successfully.', 'success');
                    saveProjectTarget = null;
                } else {
                    showStatus(resp.error || 'Save to project failed');
                }
            })
            .catch(() => {
                projectConfirmBtn.disabled = false;
                showStatus('Save to project failed');
            });
    });

    document.getElementById('feed-refresh-btn').addEventListener('click', () => loadFeed(true));
    document.getElementById('feed-empty-refresh-btn').addEventListener('click', () => loadFeed(true));

    loadFeed(false);
}());
