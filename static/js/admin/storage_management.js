(function () {
    const btn = document.getElementById('btn-toggle-advanced');
    const section = document.getElementById('advanced-section');
    const key = 'beep_advanced_admin_storage';

    function render(enabled) {
        if (!btn || !section) return;
        section.classList.toggle('d-none', !enabled);
        btn.innerHTML = enabled
            ? '<i class="bi bi-gear-wide me-1"></i>Hide Advanced'
            : '<i class="bi bi-gear-wide-connected me-1"></i>Show Advanced';
    }

    if (btn && section) {
        render(sessionStorage.getItem(key) === '1');
        btn.addEventListener('click', function () {
            const enabled = section.classList.contains('d-none');
            sessionStorage.setItem(key, enabled ? '1' : '');
            render(enabled);
        });
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[ch]));
    }

    function renderDetails(payload) {
        const doc = payload.document || {};
        const ingestion = payload.ingestion_state || {};
        const storageReference = payload.storage?.reference || {};
        return `
            <dl class="row small mb-0">
                <dt class="col-4">Filename</dt><dd class="col-8">${escapeHtml(doc.filename)}</dd>
                <dt class="col-4">Object</dt><dd class="col-8 text-break">${escapeHtml(storageReference.name || 'not recorded')}</dd>
                <dt class="col-4">Object exists</dt><dd class="col-8">${payload.storage?.exists ? 'Yes' : 'No'}</dd>
                <dt class="col-4">Parser</dt><dd class="col-8">${escapeHtml(doc.parser_name || 'pending')}</dd>
                <dt class="col-4">Extraction</dt><dd class="col-8">${escapeHtml(doc.extraction_status || 'pending')}</dd>
                <dt class="col-4">AI Server</dt><dd class="col-8">${escapeHtml(doc.rag_sync_status || 'not_indexed')}</dd>
                <dt class="col-4">Ingestion</dt><dd class="col-8">${escapeHtml(ingestion.ingestion_status || 'not recorded')}</dd>
            </dl>
        `;
    }

    document.addEventListener('click', async (event) => {
        const button = event.target.closest('[data-document-details-url]');
        if (!button) return;
        const modalElement = document.getElementById('adminDocumentDetailsModal');
        const body = document.getElementById('adminDocumentDetailsBody');
        const title = document.getElementById('adminDocumentDetailsTitle');
        if (!modalElement || !body) return;
        body.innerHTML = '<div class="text-muted">Loading...</div>';
        const modal = window.bootstrap ? new window.bootstrap.Modal(modalElement) : null;
        if (modal) modal.show();
        try {
            const response = await fetch(button.dataset.documentDetailsUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const payload = await response.json();
            if (title) title.textContent = payload.document?.filename || 'Document Details';
            body.innerHTML = renderDetails(payload);
        } catch (error) {
            body.innerHTML = '<div class="text-danger">Failed to load document details.</div>';
        }
    });

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        const message = form.dataset.adminConfirm;
        if (message && !window.confirm(message)) {
            event.preventDefault();
        }
    }, true);
})();
