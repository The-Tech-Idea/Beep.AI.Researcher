(function initProjectDocuments() {
    'use strict';

    // Parse Translation Payload
    const i18nDataElement = document.getElementById('documents-i18n-data');
    if (i18nDataElement) {
        try {
            window.DOCUMENTS_I18N = JSON.parse(i18nDataElement.textContent);
        } catch (e) {
            console.error("Failed to parse DOCUMENTS_I18N JSON:", e);
            window.DOCUMENTS_I18N = {};
        }
    } else {
        window.DOCUMENTS_I18N = {};
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const uploadBtnEmpty = document.getElementById('uploadBtnEmpty');
    const uploadZoneCard = document.getElementById('uploadZoneCard');
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    function showMessage(message, variant) {
        if (message) {
            window.beepUI.notify(message, { variant: variant || 'info' });
        }
    }

    if (uploadBtn && uploadZoneCard) {
        uploadBtn.addEventListener('click', () => {
            uploadZoneCard.hidden = !uploadZoneCard.hidden;
        });
    }

    if (uploadBtnEmpty && uploadBtn) {
        uploadBtnEmpty.addEventListener('click', () => uploadBtn.click());
    }

    if (uploadZone && fileInput) {
        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', e => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', e => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        fileInput.addEventListener('change', e => handleFiles(e.target.files));
    }

    async function handleFiles(files) {
        if (!files || files.length === 0) return;
        const projectId = window.DOCUMENTS_I18N.projectId;
        if (!projectId) {
            showMessage('Project ID not found. Cannot upload.', 'error');
            return;
        }

        const originalText = uploadZone.innerHTML;
        uploadZone.innerHTML = `<div class="documents-upload-progress" role="status">
            <div class="documents-upload-spinner" aria-hidden="true"></div>
            <p class="documents-upload-progress-text">Uploading ${files.length} file(s)...</p>
        </div>`;

        let allSuccess = true;
        for (let i = 0; i < files.length; i++) {
            const formData = new FormData();
            formData.append('file', files[i]);
            try {
                const response = await fetch(`/projects/${projectId}/documents/upload`, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Requested-With': 'SPA' } // If needed by backend
                });
                if (!response.ok) {
                    const err = await response.json();
                    console.error(`Failed to upload ${files[i].name}:`, err);
                    allSuccess = false;
                }
            } catch (error) {
                console.error(`Error uploading ${files[i].name}:`, error);
                allSuccess = false;
            }
        }

        if (!allSuccess) {
            uploadZone.innerHTML = originalText;
            showMessage('Some files failed to upload. Check console for details.', 'warning');
            return;
        }

        // Refresh the page or SPA view
        if (window.BeepSPA) {
            window.BeepSPA.navigateTo('project-documents');
        } else {
            window.location.reload();
        }
    }

    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.doc-checkbox');
    const bulkBar = document.getElementById('bulkActionsBar');
    const selectedCount = document.getElementById('selectedCount');

    function loadDocumentActivity() {
        const activityApi = window.DOCUMENTS_I18N.activity_api;
        if (!activityApi) {
            return;
        }

        fetch(activityApi)
            .then(r => r.ok ? r.json() : {})
            .then(data => {
                Object.entries(data).forEach(([docId, counts]) => {
                    ['codes', 'extractions', 'flashcards'].forEach(type => {
                        const badge = document.querySelector(`.doc-activity-${type}[data-doc-id="${docId}"] span`);
                        const wrap = document.querySelector(`.doc-activity-${type}[data-doc-id="${docId}"]`);
                        if (badge && wrap && counts[type] > 0) {
                            badge.textContent = counts[type];
                            wrap.hidden = false;
                        }
                    });
                });
            })
            .catch(() => {});
    }

    if (selectAll) {
        selectAll.addEventListener('change', () => {
            checkboxes.forEach(cb => cb.checked = selectAll.checked);
            updateBulkBar();
        });
        checkboxes.forEach(cb => cb.addEventListener('change', updateBulkBar));
    }

    function updateBulkBar() {
        const count = document.querySelectorAll('.doc-checkbox:checked').length;
        if (selectedCount) selectedCount.textContent = count;
        if (bulkBar) {
            bulkBar.hidden = count === 0;
        }
    }

    // Global event delegation (only bind once to prevent duplicate triggers in SPA)
    if (!window.DOCUMENTS_EVENTS_BOUND) {
        window.DOCUMENTS_EVENTS_BOUND = true;
        document.addEventListener('click', function (e) {
            const viewBtn = e.target.closest('.view-doc-btn');
            if (viewBtn) {
                e.stopPropagation();
                const id = viewBtn.dataset.docId;
                const projectId = window.DOCUMENTS_I18N?.projectId;
                if (projectId && id) window.location.href = `/researcher/projects/${projectId}/documents/${id}`;
                return;
            }

            const downloadBtn = e.target.closest('.download-doc-btn');
            if (downloadBtn) {
                e.stopPropagation();
                const id = downloadBtn.dataset.docId;
                const projectId = window.DOCUMENTS_I18N?.projectId;
                if (projectId && id) window.location.href = `/researcher/projects/${projectId}/documents/${id}/download`;
                return;
            }

            const deleteBtn = e.target.closest('.delete-doc-btn');
            if (deleteBtn) {
                e.stopPropagation();
                if (confirm(window.DOCUMENTS_I18N?.confirm_delete || 'Delete this document?')) {
                    const id = deleteBtn.dataset.docId;
                    const projectId = window.DOCUMENTS_I18N?.projectId;
                    if (projectId && id) {
                        fetch(`/projects/${projectId}/documents/${id}`, {
                            method: 'DELETE',
                            headers: { 'X-Requested-With': 'SPA' }
                        }).then(r => {
                            if (r.ok) {
                                if (window.BeepSPA) {
                                    window.BeepSPA.navigateTo('project-documents');
                                } else {
                                    window.location.reload();
                                }
                            } else {
                                showMessage('Failed to delete document.', 'error');
                            }
                        });
                    }
                }
                return;
            }
        });
    }

    loadDocumentActivity();
})();
