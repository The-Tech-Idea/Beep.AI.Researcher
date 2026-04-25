'use strict';

(function () {
    const statusEl = document.getElementById('ri-status');
    const container = document.getElementById('ri-topics-container');
    const topicInput = document.getElementById('ri-topic-input');
    const addBtn = document.getElementById('ri-topic-add-btn');
    const saveBtn = document.getElementById('ri-save-btn');
    const inferBtn = document.getElementById('ri-infer-btn');
    const sourcesSaveBtn = document.getElementById('ri-sources-save-btn');

    function showStatus(msg, type = 'success') {
        statusEl.className = `alert alert-${type} mb-3`;
        statusEl.textContent = msg;
        statusEl.classList.remove('d-none');
        setTimeout(() => statusEl.classList.add('d-none'), 4000);
    }

    function getTopics() {
        return Array.from(container.querySelectorAll('.ri-chip'))
            .map(c => c.dataset.topic);
    }

    function addChip(topic) {
        const t = (topic || '').trim();
        if (!t) return;
        if (getTopics().includes(t)) return;

        const chip = document.createElement('span');
        chip.className = 'ri-chip';
        chip.dataset.topic = t;
        chip.innerHTML = `
            ${t}
            <button type="button" class="ri-chip-remove" aria-label="Remove ${t}">
                <i class="bi bi-x"></i>
            </button>
        `;
        container.appendChild(chip);
    }

    container.addEventListener('click', function (e) {
        const btn = e.target.closest('.ri-chip-remove');
        if (btn) btn.closest('.ri-chip').remove();
    });

    addBtn.addEventListener('click', function () {
        addChip(topicInput.value);
        topicInput.value = '';
        topicInput.focus();
    });

    topicInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addChip(topicInput.value);
            topicInput.value = '';
        }
    });

    saveBtn.addEventListener('click', function () {
        const declared_topics = getTopics();
        saveBtn.disabled = true;

        fetch('/settings/research-interests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ declared_topics }),
        }).then(r => r.json()).then(resp => {
            saveBtn.disabled = false;
            if (resp.ok) {
                showStatus('Research interests saved.');
            } else {
                showStatus(resp.error || 'Save failed', 'danger');
            }
        }).catch(() => {
            saveBtn.disabled = false;
            showStatus('Save failed', 'danger');
        });
    });

    sourcesSaveBtn.addEventListener('click', function () {
        const preferred_sources = Array.from(
            document.querySelectorAll('.ri-source-check:checked')
        ).map(c => c.value);

        sourcesSaveBtn.disabled = true;
        fetch('/settings/research-interests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferred_sources }),
        }).then(r => r.json()).then(resp => {
            sourcesSaveBtn.disabled = false;
            if (resp.ok) {
                showStatus('Preferred sources saved.');
            } else {
                showStatus(resp.error || 'Save failed', 'danger');
            }
        }).catch(() => {
            sourcesSaveBtn.disabled = false;
            showStatus('Save failed', 'danger');
        });
    });

    inferBtn.addEventListener('click', function () {
        inferBtn.disabled = true;
        inferBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running…';

        fetch('/settings/research-interests/trigger-inference', { method: 'POST' })
            .then(r => r.json())
            .then(resp => {
                inferBtn.disabled = false;
                inferBtn.innerHTML = '<i class="bi bi-cpu me-1"></i>Re-infer from library';
                if (resp.ok) {
                    showStatus('Inference job queued. Refresh to see updated topics.');
                } else {
                    showStatus(resp.error || 'Inference failed', 'danger');
                }
            })
            .catch(() => {
                inferBtn.disabled = false;
                inferBtn.innerHTML = '<i class="bi bi-cpu me-1"></i>Re-infer from library';
                showStatus('Inference failed', 'danger');
            });
    });
}());
