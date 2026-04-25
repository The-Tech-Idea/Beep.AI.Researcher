/**
 * Reusable Document Selector Component
 * 
 * Renders a multi-select checkbox list of project documents.
 * Usage:
 *   const selector = new DocumentSelector(containerEl, projectId);
 *   await selector.load();
 *   const ids = selector.getSelectedIds();
 */
class DocumentSelector {
    constructor(container, projectId, options = {}) {
        this.container = container;
        this.projectId = projectId;
        this.documents = [];
        this.selectAll = options.selectAll !== false; // default: select all
        this.onChange = options.onChange || null;
    }

    async load() {
        try {
            const r = await fetch('/projects/' + this.projectId + '/documents');
            const j = await r.json();
            this.documents = j.documents || [];
        } catch (e) {
            this.documents = [];
        }
        this.render();
    }

    render() {
        if (!this.documents.length) {
            this.container.innerHTML =
                '<div class="document-selector document-selector--empty">' +
                '<div class="document-selector__empty">' +
                '<i class="bi bi-info-circle document-selector__empty-icon" aria-hidden="true"></i>' +
                '<span class="document-selector__empty-copy">No documents in this project. Upload documents first.</span>' +
                '</div></div>';
            return;
        }

        let html = '<div class="document-selector">';
        html += '<div class="document-selector__toolbar">';
        html += '<label class="document-selector__select-all">';
        html += '<input type="checkbox" class="form-check-input document-selector__checkbox doc-select-all" ' +
            (this.selectAll ? 'checked' : '') + '>';
        html += '<span class="document-selector__select-label">Select All</span></label>';
        html += '<span class="document-selector__count doc-count">' + this.documents.length + ' docs</span></div>';
        html += '<div class="document-selector__list">';

        for (const doc of this.documents) {
            const size = this._formatSize(doc.file_size || 0);
            const checked = this.selectAll ? 'checked' : '';
            html += '<label class="document-selector__item doc-item">';
            html += '<input type="checkbox" class="form-check-input document-selector__checkbox doc-check" ' +
                'data-doc-id="' + doc.id + '" ' + checked + '>';
            html += '<i class="bi bi-file-earmark-text document-selector__file-icon" aria-hidden="true"></i>';
            html += '<span class="document-selector__name">' + this._escapeHtml(doc.filename) + '</span>';
            html += '<span class="document-selector__size">' + size + '</span>';
            html += '</label>';
        }

        html += '</div></div>';
        this.container.innerHTML = html;

        // Bind events
        const selectAllCb = this.container.querySelector('.doc-select-all');
        if (selectAllCb) {
            selectAllCb.addEventListener('change', () => {
                this.container.querySelectorAll('.doc-check').forEach(cb => {
                    cb.checked = selectAllCb.checked;
                });
                this._updateCount();
            });
        }
        this.container.querySelectorAll('.doc-check').forEach(cb => {
            cb.addEventListener('change', () => this._updateCount());
        });
        this._updateCount();
    }

    _updateCount() {
        const total = this.container.querySelectorAll('.doc-check').length;
        const checked = this.container.querySelectorAll('.doc-check:checked').length;
        const badge = this.container.querySelector('.doc-count');
        if (badge) badge.textContent = checked + '/' + total + ' selected';
        const selectAllCb = this.container.querySelector('.doc-select-all');
        if (selectAllCb) selectAllCb.checked = (checked === total);
        if (this.onChange) this.onChange(this.getSelectedIds());
    }

    getSelectedIds() {
        const ids = [];
        this.container.querySelectorAll('.doc-check:checked').forEach(cb => {
            ids.push(parseInt(cb.dataset.docId));
        });
        return ids;
    }

    _formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1048576).toFixed(1) + ' MB';
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use
window.DocumentSelector = DocumentSelector;
