(function () {
    function parseConfig() {
        var configElement = document.getElementById('document-viewer-config');
        if (!configElement) {
            return null;
        }

        try {
            return JSON.parse(configElement.textContent);
        } catch (error) {
            return null;
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function notifyUser(message, variant) {
        if (!message) {
            return;
        }

        if (window.beepUI && typeof window.beepUI.notify === 'function') {
            window.beepUI.notify(message, variant || 'info');
            return;
        }

        if (variant === 'error') {
            console.error(message);
            return;
        }

        console.log(message);
    }

    function setButtonLoading(button, loading, label) {
        if (!button) {
            return;
        }

        if (window.beepUI && typeof window.beepUI.setButtonLoading === 'function') {
            window.beepUI.setButtonLoading(button, loading, label);
            return;
        }

        if (!button.dataset.defaultLabel) {
            button.dataset.defaultLabel = button.textContent;
        }

        button.disabled = !!loading;
        button.textContent = loading ? (label || button.dataset.defaultLabel) : button.dataset.defaultLabel;
    }

    function buildRelatedFilesMarkup(relatedItems, projectId, relatedOpenFileLabel) {
        return (
            '<ul class="related-files-list">' +
            relatedItems.map(function (item) {
                var fileName = escapeHtml(item.filename || 'Project file');
                var snippet = item.snippet
                    ? '<div class="small mt-2">' + escapeHtml(item.snippet) + '</div>'
                    : '';
                var openLink = item.document_id
                    ? '<a class="text-decoration-none small" href="/researcher/projects/' + projectId + '/documents/' +
                        encodeURIComponent(item.document_id) + '?source_view=answer">' +
                        '<i class="bi bi-box-arrow-up-right me-1"></i>' + escapeHtml(relatedOpenFileLabel) +
                      '</a>'
                    : '';

                return (
                    '<li class="related-files-item">' +
                        '<div class="d-flex justify-content-between align-items-start gap-2">' +
                            '<strong>' + fileName + '</strong>' +
                            openLink +
                        '</div>' +
                        snippet +
                    '</li>'
                );
            }).join('') +
            '</ul>'
        );
    }

    function formatAnnotationRange(config, annotation) {
        return (config.annotationRangeLabel || 'Characters') + ' ' +
            annotation.start_offset + '-' + annotation.end_offset;
    }

    function renderAnnotations(config, annotations) {
        var annotationsList = document.getElementById('annotationsList');
        if (!annotationsList) {
            return;
        }

        if (!Array.isArray(annotations) || !annotations.length) {
            annotationsList.innerHTML = '<p class="annotation-list-empty">' +
                escapeHtml(config.annotationEmpty || 'No saved notes or highlights yet.') +
                '</p>';
            return;
        }

        annotationsList.innerHTML = annotations.map(function (annotation) {
            var selectedText = escapeHtml(annotation.selected_text || annotation.context_preview || '');
            var note = escapeHtml(annotation.note || '');
            var noteMarkup = note
                ? '<p class="annotation-card-note">' + note + '</p>'
                : '';

            return (
                '<article class="annotation-card" data-annotation-start="' + annotation.start_offset + '" data-annotation-end="' + annotation.end_offset + '">' +
                    '<div class="annotation-card-header">' +
                        '<div>' +
                            '<div class="annotation-card-title">' + escapeHtml(config.annotationDefaultTitle || 'Saved highlight') + '</div>' +
                            '<div class="annotation-card-range">' + escapeHtml(formatAnnotationRange(config, annotation)) + '</div>' +
                        '</div>' +
                        '<button type="button" class="annotation-delete-button" data-annotation-delete="' + annotation.id + '">' +
                            escapeHtml(config.annotationDeleteLabel || 'Delete') +
                        '</button>' +
                    '</div>' +
                    '<div class="annotation-card-quote">"' + selectedText + '"</div>' +
                    noteMarkup +
                    '<div class="annotation-card-meta">' + escapeHtml(annotation.context_preview || '') + '</div>' +
                '</article>'
            );
        }).join('');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var config = parseConfig();
        if (!config) {
            return;
        }

        var projectId = config.projectId;
        var docId = config.docId;
        var codedRefRanges = config.codedRefRanges || {};
        var selection = { start: 0, end: 0, text: '' };

        var docContent = document.getElementById('docContent');
        var viewerStatus = document.getElementById('viewerStatus');
        var viewerStatusText = document.getElementById('viewerStatusText');
        var relatedFilesPanel = document.getElementById('relatedFilesPanel');
        var relatedFilesBody = document.getElementById('relatedFilesBody');
        var relatedFilesSummary = document.getElementById('relatedFilesSummary');
        var codeSelect = document.getElementById('codeSelect');
        var annotationSelectionPreview = document.getElementById('annotationSelectionPreview');
        var annotationNoteInput = document.getElementById('annotationNoteInput');
        var annotationColorInput = document.getElementById('annotationColorInput');
        var saveAnnotationButton = document.getElementById('btnSaveAnnotation');
        var annotationsList = document.getElementById('annotationsList');
        var supportingSourcesPanelElement = document.getElementById('codingSuggestionSources');
        var supportingSourcesPanel = window.ProjectSupportingSources && supportingSourcesPanelElement
            ? window.ProjectSupportingSources.create(supportingSourcesPanelElement, {
                documentUrlTemplate: '/researcher/projects/' + projectId + '/documents/__DOC_ID__?source_view=answer',
                title: 'Files used for this code suggestion',
                intro: 'These project files helped suggest the current label for the highlighted passage.',
            })
            : null;

        function hasSelection() {
            return selection.end > selection.start && Boolean((selection.text || '').trim());
        }

        function updateSelectionPreview() {
            if (!annotationSelectionPreview) {
                return;
            }

            if (!hasSelection()) {
                annotationSelectionPreview.classList.add('is-empty');
                annotationSelectionPreview.textContent =
                    annotationSelectionPreview.dataset.emptyText || config.annotationSelectionRequired;
                return;
            }

            annotationSelectionPreview.classList.remove('is-empty');
            annotationSelectionPreview.textContent = selection.text.trim();
        }

        function clearSelectionState() {
            selection.start = 0;
            selection.end = 0;
            selection.text = '';
            updateSelectionPreview();
            if (window.getSelection) {
                var browserSelection = window.getSelection();
                if (browserSelection && typeof browserSelection.removeAllRanges === 'function') {
                    browserSelection.removeAllRanges();
                }
            }
        }

        function showViewerStatus(message, variant) {
            if (!viewerStatus || !viewerStatusText) {
                return;
            }

            viewerStatus.className = 'viewer-status is-visible';
            if (variant) {
                viewerStatus.classList.add(variant);
            }
            viewerStatusText.textContent = message;
        }

        function highlightRange(start, end) {
            if (!docContent) {
                return false;
            }

            var fullText = docContent.textContent || '';
            var safeStart = Math.max(0, Math.min(Number(start) || 0, fullText.length));
            var safeEnd = Math.max(safeStart, Math.min(Number(end) || 0, fullText.length));
            if (safeEnd <= safeStart) {
                return false;
            }

            var before = escapeHtml(fullText.slice(0, safeStart));
            var middle = escapeHtml(fullText.slice(safeStart, safeEnd));
            var after = escapeHtml(fullText.slice(safeEnd));
            docContent.innerHTML = before + '<mark class="viewer-highlight-mark" id="viewerHighlightedPassage">' +
                middle + '</mark>' + after;

            var highlighted = document.getElementById('viewerHighlightedPassage');
            if (highlighted) {
                highlighted.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return true;
        }

        function applyViewerContext() {
            var params = new URLSearchParams(window.location.search);
            var sourceView = params.get('source_view');
            var highlight = params.get('highlight');

            if (sourceView === 'reference') {
                showViewerStatus(
                    config.referenceContextMessage || 'This file was opened from a source detail page so you can review how that source connects to the file.',
                    'is-answer'
                );
            } else if (sourceView === 'answer') {
                showViewerStatus(
                    config.answerContextMessage || 'This file was opened from an answer so you can review the supporting passage in context.',
                    'is-answer'
                );
            }

            if (highlight && codedRefRanges[highlight]) {
                var range = codedRefRanges[highlight];
                if (highlightRange(range.start, range.end)) {
                    showViewerStatus(
                        config.highlightContextMessage || 'A saved relevant passage has been highlighted below to help you review the supporting text quickly.',
                        'is-highlight'
                    );
                }
            }
        }

        function captureSelection() {
            if (!docContent) {
                return;
            }

            var browserSelection = window.getSelection ? window.getSelection() : null;
            if (!browserSelection || !browserSelection.rangeCount) {
                clearSelectionState();
                return;
            }

            var range = browserSelection.getRangeAt(0);
            if (!docContent.contains(range.commonAncestorContainer)) {
                clearSelectionState();
                return;
            }

            var selectedText = range.toString();
            if (!selectedText.trim()) {
                clearSelectionState();
                return;
            }

            var preRange = document.createRange();
            preRange.setStart(docContent, 0);
            preRange.setEnd(range.startContainer, range.startOffset);
            selection.start = preRange.toString().length;
            selection.end = selection.start + selectedText.length;
            selection.text = selectedText;
            updateSelectionPreview();
        }

        async function loadAnnotations() {
            try {
                var response = await fetch('/projects/' + projectId + '/documents/' + docId + '/annotations');
                var payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || config.annotationSaveFailed);
                }
                renderAnnotations(config, payload.annotations || []);
            } catch (error) {
                renderAnnotations(config, []);
            }
        }

        if (docContent) {
            docContent.addEventListener('mouseup', captureSelection);
            docContent.addEventListener('keyup', captureSelection);
            applyViewerContext();
        } else {
            clearSelectionState();
        }

        var applyCodeButton = document.getElementById('btnApplyCode');
        if (applyCodeButton) {
            applyCodeButton.addEventListener('click', async function () {
                var codeId = codeSelect ? codeSelect.value : '';
                if (!codeId || !hasSelection()) {
                    notifyUser(config.selectCodeAlert, 'warning');
                    return;
                }

                try {
                var response = await fetch('/projects/' + projectId + '/code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code_id: parseInt(codeId, 10),
                        document_id: docId,
                        chunk_id: 'chunk-0',
                        start_offset: selection.start,
                        end_offset: selection.end,
                    }),
                });

                if (response.ok) {
                    window.location.reload();
                    return;
                }

                notifyUser(config.codeApplyFailed || 'Could not save the highlighted passage right now.', 'error');
                } catch (error) {
                    notifyUser(config.codeApplyFailed || 'Could not save the highlighted passage right now.', 'error');
                }
            });
        }

        loadAnnotations();

        if (saveAnnotationButton) {
            saveAnnotationButton.addEventListener('click', async function () {
                if (!hasSelection()) {
                    notifyUser(config.annotationSelectionRequired || config.selectTextFirst, 'warning');
                    return;
                }

                setButtonLoading(saveAnnotationButton, true, config.annotationSaveLoading || 'Saving...');
                try {
                    var response = await fetch('/projects/' + projectId + '/documents/' + docId + '/annotations', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            chunk_id: 'chunk-0',
                            start_offset: selection.start,
                            end_offset: selection.end,
                            note: annotationNoteInput ? annotationNoteInput.value : '',
                            highlight_color: annotationColorInput ? annotationColorInput.value : '#fef08a',
                        }),
                    });
                    var payload = await response.json();
                    if (!response.ok) {
                        throw new Error(payload.error || config.annotationSaveFailed);
                    }

                    if (annotationNoteInput) {
                        annotationNoteInput.value = '';
                    }
                    if (annotationColorInput) {
                        annotationColorInput.value = '#fef08a';
                    }
                    clearSelectionState();
                    await loadAnnotations();
                    notifyUser(config.annotationSaveSuccess, 'success');
                } catch (error) {
                    notifyUser(error.message || config.annotationSaveFailed, 'error');
                } finally {
                    setButtonLoading(saveAnnotationButton, false);
                }
            });
        }

        if (annotationsList) {
            annotationsList.addEventListener('click', async function (event) {
                var deleteButton = event.target.closest('[data-annotation-delete]');
                if (deleteButton) {
                    setButtonLoading(deleteButton, true, config.annotationDeleteLabel);
                    try {
                        var deleteResponse = await fetch(
                            '/projects/' + projectId + '/documents/' + docId + '/annotations/' +
                            deleteButton.getAttribute('data-annotation-delete'),
                            { method: 'DELETE' }
                        );
                        var deletePayload = await deleteResponse.json();
                        if (!deleteResponse.ok) {
                            throw new Error(deletePayload.error || config.annotationDeleteFailed);
                        }
                        await loadAnnotations();
                    } catch (error) {
                        notifyUser(error.message || config.annotationDeleteFailed, 'error');
                    } finally {
                        setButtonLoading(deleteButton, false);
                    }
                    return;
                }

                var card = event.target.closest('[data-annotation-start][data-annotation-end]');
                if (!card) {
                    return;
                }

                if (highlightRange(card.getAttribute('data-annotation-start'), card.getAttribute('data-annotation-end'))) {
                    showViewerStatus(
                        config.highlightContextMessage || 'A saved relevant passage has been highlighted below to help you review the supporting text quickly.',
                        'is-highlight'
                    );
                }
            });
        }

        var relatedLink = document.getElementById('relatedLink');
        if (relatedLink) {
            relatedLink.addEventListener('click', async function () {
                try {
                    var response = await fetch('/projects/' + projectId + '/documents/' + docId + '/related');
                    var payload = await response.json();
                    if (!relatedFilesPanel || !relatedFilesBody) {
                        return;
                    }

                    relatedFilesPanel.classList.add('is-visible');
                    if (relatedFilesSummary) {
                        relatedFilesSummary.textContent = payload.message || payload.note || config.relatedSummaryDefault;
                    }

                    if (Array.isArray(payload.related) && payload.related.length) {
                        relatedFilesBody.innerHTML = buildRelatedFilesMarkup(
                            payload.related,
                            projectId,
                            config.relatedOpenFile
                        );
                        return;
                    }

                    relatedFilesBody.innerHTML = '<p class="small mb-0">' + escapeHtml(config.noRelated) + '</p>';
                } catch (error) {
                    if (relatedFilesPanel) {
                        relatedFilesPanel.classList.add('is-visible');
                    }
                    if (relatedFilesBody) {
                        relatedFilesBody.innerHTML = '<p class="small mb-0">' + escapeHtml(config.noRelated) + '</p>';
                    }
                }
            });
        }

        var suggestButton = document.getElementById('btnSuggest');
        if (suggestButton) {
            suggestButton.addEventListener('click', async function () {
                if (!hasSelection()) {
                    notifyUser(config.selectTextFirst, 'warning');
                    return;
                }

                try {
                    var response = await fetch('/projects/' + projectId + '/codes/suggest', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: selection.text, document_id: docId }),
                    });
                    var payload = await response.json();

                    if (Array.isArray(payload.suggestions) && payload.suggestions.length && codeSelect) {
                        codeSelect.value = payload.suggestions[0].id;
                    }

                    if (supportingSourcesPanel) {
                        var renderedSources = supportingSourcesPanel.render(payload.supporting_sources || []);
                        if (renderedSources.length) {
                            showViewerStatus(
                                'A suggested label is selected below, and the files used for that suggestion are listed here for review.',
                                'is-answer'
                            );
                        }
                    }
                } catch (error) {
                    if (supportingSourcesPanel) {
                        supportingSourcesPanel.clear();
                    }
                    notifyUser(config.suggestFailed || 'Could not suggest a label right now.', 'error');
                }
            });
        }

        Array.prototype.forEach.call(document.querySelectorAll('.removeRef'), function (button) {
            button.addEventListener('click', async function () {
            try {
                var refId = button.dataset.refId;
                var response = await fetch('/projects/' + projectId + '/code/' + refId, { method: 'DELETE' });
                if (response.ok) {
                    window.location.reload();
                    return;
                }

                notifyUser(
                    config.codedPassageDeleteFailed || 'Could not remove the saved passage right now.',
                    'error'
                );
                } catch (error) {
                    notifyUser(
                        config.codedPassageDeleteFailed || 'Could not remove the saved passage right now.',
                        'error'
                    );
                }
            });
        });
    });
})();
