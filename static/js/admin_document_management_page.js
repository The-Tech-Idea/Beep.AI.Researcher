'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const detailsModalElement = document.getElementById('adminDocumentDetailsModal');
    const detailsBody = document.getElementById('adminDocumentDetailsBody');
    const detailsTitle = document.getElementById('adminDocumentDetailsTitle');
    const selectAll = document.getElementById('adminSelectAllDocuments');
    const checkboxes = Array.from(document.querySelectorAll('.admin-doc-checkbox'));
    const selectedCount = document.getElementById('adminSelectedDocumentsCount');
    const bulkForm = document.getElementById('adminDocumentBulkForm');
    const bulkIds = document.getElementById('adminBulkDocumentIds');

    function updateBulkSelection() {
        const selected = checkboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
        if (selectedCount) selectedCount.textContent = String(selected.length);
        if (bulkIds) bulkIds.value = selected.join(',');
        if (selectAll) {
            selectAll.checked = selected.length > 0 && selected.length === checkboxes.length;
            selectAll.indeterminate = selected.length > 0 && selected.length < checkboxes.length;
        }
    }

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checkboxes.forEach((checkbox) => {
                checkbox.checked = selectAll.checked;
            });
            updateBulkSelection();
        });
    }
    checkboxes.forEach((checkbox) => checkbox.addEventListener('change', updateBulkSelection));

    if (bulkForm) {
        bulkForm.addEventListener('submit', (event) => {
            updateBulkSelection();
            if (!bulkIds || !bulkIds.value) {
                event.preventDefault();
                window.alert('Select at least one document.');
            }
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
        const owner = payload.owner || {};
        const project = payload.project || {};
        const storage = payload.storage || {};
        const storageReference = storage.reference || {};
        const ingestion = payload.ingestion_state || {};
        return `
            <div class="d-flex justify-content-end mb-3">
                <button type="button" class="btn btn-sm btn-outline-secondary" id="adminDocumentDetailsAdvancedToggle">
                    <i class="bi bi-gear-wide-connected me-1"></i>Show Advanced
                </button>
            </div>
            <div class="row g-3">
                <div class="col-md-6">
                    <h6>Document</h6>
                    <dl class="row small mb-0">
                        <dt class="col-5">Filename</dt><dd class="col-7">${escapeHtml(doc.filename)}</dd>
                        <dt class="col-5">Type</dt><dd class="col-7">${escapeHtml(doc.file_type)}</dd>
                        <dt class="col-5">Size</dt><dd class="col-7">${escapeHtml(doc.size_formatted)}</dd>
                        <dt class="col-5">Archived</dt><dd class="col-7">${escapeHtml(doc.archived_at || 'No')}</dd>
                    </dl>
                </div>
                <div class="col-md-6">
                    <h6>Owner and Project</h6>
                    <dl class="row small mb-0">
                        <dt class="col-5">Owner</dt><dd class="col-7">${escapeHtml(owner.username || owner.email || 'unknown')}</dd>
                        <dt class="col-5">Project</dt><dd class="col-7">${escapeHtml(project.name || 'unknown')}</dd>
                        <dt class="col-5">Storage backend</dt><dd class="col-7">${escapeHtml(storage.backend || 'unknown')}</dd>
                        <dt class="col-5">Object exists</dt><dd class="col-7">${storage.exists ? 'Yes' : 'No'}</dd>
                        <dt class="col-5">Object</dt><dd class="col-7 text-break">${escapeHtml(storageReference.name || 'not recorded')}</dd>
                    </dl>
                </div>
                <div class="col-md-6">
                    <h6>Extraction</h6>
                    <dl class="row small mb-0">
                        <dt class="col-5">Status</dt><dd class="col-7">${escapeHtml(doc.extraction_status || 'pending')}</dd>
                        <dt class="col-5">Parser</dt><dd class="col-7">${escapeHtml(doc.parser_name || 'pending')}</dd>
                        <dt class="col-5">Version</dt><dd class="col-7">${escapeHtml(doc.parser_version || 'unknown')}</dd>
                        <dt class="col-5">Quality</dt><dd class="col-7">${escapeHtml(doc.extraction_quality || 'unknown')}</dd>
                        <dt class="col-5">Pages</dt><dd class="col-7">${escapeHtml(doc.page_count || 0)}</dd>
                        <dt class="col-5">Tables</dt><dd class="col-7">${escapeHtml(doc.table_count || 0)}</dd>
                        <dt class="col-5">Images</dt><dd class="col-7">${escapeHtml(doc.image_count || 0)}</dd>
                    </dl>
                </div>
                <div class="col-md-6">
                    <h6>AI Server</h6>
                    <dl class="row small mb-0">
                        <dt class="col-5">RAG status</dt><dd class="col-7">${escapeHtml(doc.rag_sync_status || 'not_indexed')}</dd>
                        <dt class="col-5">Collection</dt><dd class="col-7 text-break">${escapeHtml(doc.rag_collection_id || 'not linked')}</dd>
                        <dt class="col-5">Last sync</dt><dd class="col-7">${escapeHtml(doc.rag_synced_at || 'never')}</dd>
                    </dl>
                </div>
                <div class="col-md-6">
                    <h6>Ingestion State</h6>
                    <dl class="row small mb-0">
                        <dt class="col-5">Status</dt><dd class="col-7">${escapeHtml(ingestion.ingestion_status || 'not recorded')}</dd>
                        <dt class="col-5">Duplicate of</dt><dd class="col-7">${escapeHtml(ingestion.duplicate_of_document_id || 'none')}</dd>
                        <dt class="col-5">Last error</dt><dd class="col-7 text-break">${escapeHtml(ingestion.last_error || 'none')}</dd>
                        <dt class="col-5">Updated</dt><dd class="col-7">${escapeHtml(ingestion.updated_at || 'never')}</dd>
                    </dl>
                </div>
                <div class="col-12 d-none" id="adminDocumentDetailsAdvanced">
                    <div class="alert alert-warning small">
                        These settings expose internal identifiers used for storage repair and AI Server sync.
                    </div>
                    <h6>Advanced</h6>
                    <dl class="row small mb-0">
                        <dt class="col-md-3">Document hash</dt><dd class="col-md-9 text-break">${escapeHtml(doc.document_hash || 'missing')}</dd>
                        <dt class="col-md-3">Storage key hash</dt><dd class="col-md-9 text-break">${escapeHtml(storageReference.sha256 || 'missing')}</dd>
                        <dt class="col-md-3">RAG document id</dt><dd class="col-md-9 text-break">${escapeHtml(doc.rag_document_id || 'missing')}</dd>
                        <dt class="col-md-3">Content hash</dt><dd class="col-md-9 text-break">${escapeHtml(doc.rag_content_hash || 'missing')}</dd>
                    </dl>
                </div>
                ${doc.extraction_warnings || doc.rag_sync_message ? `
                <div class="col-12">
                    <h6>Messages</h6>
                    <pre class="small bg-light border rounded p-2 mb-0">${escapeHtml([doc.extraction_warnings, doc.rag_sync_message].filter(Boolean).join('\n'))}</pre>
                </div>` : ''}
            </div>
        `;
    }

    document.addEventListener('click', async (event) => {
        const button = event.target.closest('[data-document-details-url]');
        if (!button || !detailsModalElement || !detailsBody) {
            return;
        }
        detailsBody.innerHTML = '<div class="admin-document-management-muted">Loading...</div>';
        const modal = window.bootstrap ? new window.bootstrap.Modal(detailsModalElement) : null;
        if (modal) modal.show();
        try {
            const response = await fetch(button.dataset.documentDetailsUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const payload = await response.json();
            const doc = payload.document || {};
            if (detailsTitle) detailsTitle.textContent = doc.filename || 'Document Details';
            detailsBody.innerHTML = renderDetails(payload);
            bindDetailsAdvancedToggle();
        } catch (error) {
            detailsBody.innerHTML = '<div class="text-danger">Failed to load document details.</div>';
        }
    });

    function bindDetailsAdvancedToggle() {
        const toggle = document.getElementById('adminDocumentDetailsAdvancedToggle');
        const section = document.getElementById('adminDocumentDetailsAdvanced');
        if (!toggle || !section) {
            return;
        }
        const storageKey = 'adminDocumentDetailsAdvanced';
        const setVisible = (visible) => {
            section.classList.toggle('d-none', !visible);
            toggle.innerHTML = visible
                ? '<i class="bi bi-gear-wide me-1"></i>Hide Advanced'
                : '<i class="bi bi-gear-wide-connected me-1"></i>Show Advanced';
            window.sessionStorage.setItem(storageKey, visible ? '1' : '');
        };
        setVisible(window.sessionStorage.getItem(storageKey) === '1');
        toggle.addEventListener('click', () => {
            setVisible(section.classList.contains('d-none'));
        });
    }

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const confirmMessage = form.dataset.adminConfirm;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            event.preventDefault();
        }
    }, true);
});
