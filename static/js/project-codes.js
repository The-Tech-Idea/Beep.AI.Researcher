document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    function applyDynamicCodeStyles(root) {
        (root || document).querySelectorAll('[data-bg]').forEach(el => {
            el.style.setProperty('--code-accent-color', el.dataset.bg || '');
        });
        (root || document).querySelectorAll('[data-border-color]').forEach(el => {
            el.style.setProperty('--code-accent-color', el.dataset.borderColor || '');
        });
    }

    // Parse Translation Payload
    const i18nDataElement = document.getElementById('codes-i18n-data');
    if (i18nDataElement) {
        try {
            window.CODES_I18N = JSON.parse(i18nDataElement.textContent);
        } catch (e) {
            console.error("Failed to parse CODES_I18N JSON:", e);
            window.CODES_I18N = {};
        }
    } else {
        window.CODES_I18N = {};
    }

    // Apply Dynamic Colors stored in data attributes
    applyDynamicCodeStyles(document);

    // Color Picker UI
    let selectedColor = '#6366f1';
    document.querySelectorAll('#colorPicker .spa-color-dot[data-color]').forEach(item => {
        item.addEventListener('click', () => {
            document.querySelectorAll('#colorPicker .spa-color-dot[data-color]').forEach(i => i.classList.remove('selected'));
            item.classList.add('selected');
            selectedColor = item.dataset.color;
        });
    });

    // Form Toggle Buttons
    const addCodeBtn = document.getElementById('addCodeBtn');
    const formContainer = document.getElementById('addCodeFormContainer');
    if (addCodeBtn) {
        addCodeBtn.addEventListener('click', () => {
            formContainer.hidden = !formContainer.hidden;
        });
    }

    const createFirstCodeBtn = document.getElementById('createFirstCodeBtn');
    if (createFirstCodeBtn && addCodeBtn) {
        createFirstCodeBtn.addEventListener('click', () => {
            addCodeBtn.click();
        });
    }

    const cancelAddCodeBtn = document.getElementById('cancelAddCodeBtn');
    if (cancelAddCodeBtn) {
        cancelAddCodeBtn.addEventListener('click', () => {
            formContainer.hidden = true;
            const input = document.getElementById('newCodeName');
            if (input) input.value = '';
        });
    }

    const saveNewCodeBtn = document.getElementById('saveNewCodeBtn');
    if (saveNewCodeBtn) {
        saveNewCodeBtn.addEventListener('click', () => {
            const name = document.getElementById('newCodeName').value.trim();
            if (!name) return;
            const projectId = window.CODES_I18N.projectId;
            if (!projectId) return;

            fetch(`/api/projects/${projectId}/codes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, color: selectedColor })
            })
                .then(r => r.json())
                .then(() => location.reload());
        });
    }

    const exportCodesBtn = document.getElementById('exportCodesBtn');
    if (exportCodesBtn) {
        exportCodesBtn.addEventListener('click', () => {
            const projectId = window.CODES_I18N.projectId;
            if (projectId) window.location.href = `/projects/${projectId}/codes/export`;
        });
    }

    // Global Event Delegation for dynamic list items
    document.addEventListener('click', function (e) {
        const editBtn = e.target.closest('.code-edit-btn');
        if (editBtn) {
            e.stopPropagation();
            // Implement inline edit later if required
            return;
        }

        const deleteBtn = e.target.closest('.code-delete-btn');
        if (deleteBtn) {
            e.stopPropagation();
            if (confirm(window.CODES_I18N.confirm_delete || "Delete this code?")) {
                const id = deleteBtn.dataset.codeId;
                const projectId = window.CODES_I18N.projectId;
                fetch(`/api/projects/${projectId}/codes/${id}`, { method: 'DELETE' })
                    .then(() => location.reload());
            }
            return;
        }

        const removeExcerptBtn = e.target.closest('.excerpt-remove-btn');
        if (removeExcerptBtn) {
            e.stopPropagation();
            const id = removeExcerptBtn.dataset.excerptId;
            const projectId = window.CODES_I18N.projectId;
            fetch(`/api/projects/${projectId}/excerpts/${id}`, { method: 'DELETE' })
                .then(() => location.reload());
            return;
        }

        const selectItem = e.target.closest('.code-select-btn');
        if (selectItem) {
            const codeId = selectItem.dataset.codeId;
            document.querySelectorAll('.spa-list-item').forEach(item => item.classList.remove('active'));
            selectItem.classList.add('active');

            const projectId = window.CODES_I18N.projectId;
            if (!projectId) return;

            fetch(`/api/projects/${projectId}/codes/${codeId}`)
                .then(r => r.json())
                .then(code => {
                    document.getElementById('detailName').textContent = code.name;
                    document.getElementById('detailDescription').textContent = code.description || window.CODES_I18N.no_description || 'No description';
                    const detailColor = document.getElementById('detailColor');
                    detailColor.dataset.bg = code.color;

                    const c = document.getElementById('codeExcerpts');
                    if (code.excerpts && code.excerpts.length > 0) {
                        c.innerHTML = code.excerpts.map(e => `
                            <div class="excerpt-item">
                                <blockquote class="excerpt-quote codes-excerpt-quote" data-border-color="${code.color}">"${e.text}"</blockquote>
                                <div class="excerpt-meta">
                                    <a href="/researcher/projects/${projectId}/documents/${e.document_id}/view?highlight=${e.id}" class="codes-excerpt-document-link">
                                        <i class="bi bi-file-earmark-text me-1"></i>${e.document_name}</a>
                                    <button class="btn btn-sm excerpt-remove-btn codes-excerpt-remove-button" data-excerpt-id="${e.id}" type="button"><i class="bi bi-x"></i></button>
                                </div>
                            </div>`).join('');
                    } else {
                        const emptyTitle = window.CODES_I18N.excerpts_empty_title || "No Excerpts";
                        const emptyDesc = window.CODES_I18N.excerpts_empty_desc || "No text highlighted yet.";
                        c.innerHTML = `<div class="spa-empty"><i class="bi bi-quote"></i><p>${emptyTitle}</p><span>${emptyDesc}</span></div>`;
                    }
                    applyDynamicCodeStyles(document);
                });
        }
    });
});
