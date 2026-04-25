window.initReportEditor = function () {
    const editorEl = document.getElementById('editorArea');
    if (!editorEl || editorEl.classList.contains('ql-container')) return;

    const cfg = window.REPORT_I18N || {};
    const projectId = cfg.projectId;
    const draftKey = projectId ? `beep_project_report_${projectId}` : '';
    const supportingSourcesPanelEl = document.getElementById('reportSupportingSources');
    const supportingSourcesPanel = window.ProjectSupportingSources && supportingSourcesPanelEl
        ? window.ProjectSupportingSources.create(supportingSourcesPanelEl, {
            documentUrlTemplate: `/researcher/projects/${projectId}/documents/__DOC_ID__?source_view=answer`,
            title: 'Files used for the latest writing help',
            intro: 'These project files supported the latest writing help used on this page.',
        })
        : null;

    window.renderReportSupportingSources = function (sources, overrides) {
        if (!supportingSourcesPanel) {
            return [];
        }
        return supportingSourcesPanel.render(sources || [], overrides || {});
    };

    const icons = Quill.import('ui/icons');
    icons.summarize = '<i class="bi bi-file-earmark-text report-toolbar-icon"></i>';
    icons.expand = '<i class="bi bi-arrows-angle-expand report-toolbar-icon"></i>';
    icons.improve = '<i class="bi bi-magic report-toolbar-icon report-toolbar-icon--accent"></i>';
    icons.paraphrase = '<i class="bi bi-arrow-repeat report-toolbar-icon"></i>';
    icons.grammar = '<i class="bi bi-spellcheck report-toolbar-icon"></i>';
    icons.citation = '<i class="bi bi-bookmark-check report-toolbar-icon"></i>';

    const quill = new Quill('#editorArea', {
        theme: 'snow',
        modules: {
            toolbar: {
                container: [
                    [{ header: [1, 2, 3, false] }],
                    ['bold', 'italic', 'underline'],
                    [{ list: 'ordered' }, { list: 'bullet' }],
                    ['blockquote', 'link'],
                    ['clean'],
                    ['summarize', 'expand', 'improve', 'paraphrase', 'grammar', 'citation']
                ],
                handlers: {
                    summarize: function () { window.aiAssist('summarize'); },
                    expand: function () { window.aiAssist('expand'); },
                    improve: function () { window.aiAssist('tone'); },
                    paraphrase: function () { window.aiAssist('paraphrase'); },
                    grammar: function () { window.aiAssist('grammar'); },
                    citation: function () { window.aiAssist('citation'); }
                }
            }
        }
    });
    window.quill = quill;

    const toolbarTitles = {
        summarize: 'Summarize selection',
        expand: 'Add more detail',
        improve: 'Improve writing',
        paraphrase: 'Rewrite clearly',
        grammar: 'Check grammar',
        citation: 'Find supporting files'
    };
    Object.keys(toolbarTitles).forEach(function (action) {
        const button = document.querySelector('.ql-' + action);
        if (button) button.title = toolbarTitles[action];
    });

    const wordCountEl = document.getElementById('wordCount');
    function updateWordCount() {
        const text = quill.getText() || '';
        const words = text.trim().split(/\s+/).filter(function (word) { return word.length > 0; }).length;
        if (wordCountEl) {
            wordCountEl.textContent = words + ' ' + (cfg.wordcount_suffix || 'words');
        }
    }
    quill.on('text-change', updateWordCount);

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showMessage(message) {
        if (message) {
            window.beepUI.notify(message);
        }
    }

    function getSelectionContext() {
        const range = quill.getSelection();
        if (range && range.length > 0) {
            return {
                range: range,
                text: quill.getText(range.index, range.length).trim()
            };
        }
        return {
            range: null,
            text: quill.getText().trim()
        };
    }

    async function loadDraft() {
        let htmlContent = '';

        if (draftKey) {
            htmlContent = localStorage.getItem(draftKey) || '';
        }

        if (!htmlContent && cfg.draftEndpoint) {
            const response = await fetch(cfg.draftEndpoint);
            const data = await response.json();
            htmlContent = ((data.draft || {}).html_content || '').trim();
        }

        if (htmlContent) {
            quill.clipboard.dangerouslyPasteHTML(htmlContent);
        }

        if (draftKey) {
            try {
                const pending = JSON.parse(localStorage.getItem('report_pending_' + projectId) || '[]');
                if (pending.length) {
                    pending.forEach(function (item) {
                        const insertionIndex = quill.getLength() - 1;
                        quill.insertText(insertionIndex, '\nFrom project answers\n', { bold: true });
                        quill.insertText(quill.getLength() - 1, (item.content || '') + '\n');
                        if (item.sources && item.sources.length) {
                            quill.insertText(
                                quill.getLength() - 1,
                                (cfg.support_label || 'Supporting files') + ': ' + item.sources.map(function (source) {
                                    return source.name;
                                }).join(', ') + '\n',
                                { italic: true, color: '#6c757d' }
                            );
                        }
                    });
                    localStorage.removeItem('report_pending_' + projectId);
                }
            } catch (error) {
                console.warn('Could not read queued report content.', error);
            }
        }

        updateWordCount();
    }

    window.saveReport = function (silent) {
        silent = Boolean(silent);
        if (!cfg.draftEndpoint) return Promise.resolve();

        const htmlContent = quill.root.innerHTML;
        if (draftKey) {
            localStorage.setItem(draftKey, htmlContent);
        }

        return fetch(cfg.draftEndpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: document.title.replace(/\s+\|.*$/, ''),
                html_content: htmlContent
            })
        })
            .then(function (response) { return response.json().then(function (body) { return { ok: response.ok, body: body }; }); })
            .then(function (result) {
                if (!result.ok) {
                    throw new Error(result.body.error || 'Unable to save the draft.');
                }
                if (!silent) {
                    showMessage(result.body.message || cfg.save_success || 'Draft saved.');
                }
                return result.body;
            });
    };

    window.goToSharePage = function () {
        window.saveReport(true)
            .catch(function (error) {
                console.warn('Draft save failed before opening share page.', error);
            })
            .finally(function () {
                if (cfg.shareUrl) window.location.href = cfg.shareUrl;
            });
    };

    window.aiAssist = async function (action) {
        const context = getSelectionContext();
        if (!context.text) {
            showMessage(cfg.select_text || 'Select some text first.');
            return;
        }

        if (action === 'citation') {
            if (!cfg.citationEndpoint) {
                showMessage(cfg.ai_unavailable || 'Writing help is not available right now.');
                return;
            }
            const citationResponse = await fetch(cfg.citationEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft: context.text, max_citations: 3 })
            });
            const citationData = await citationResponse.json();
            if (!citationResponse.ok) {
                showMessage(citationData.error || cfg.ai_unavailable || 'Writing help is not available right now.');
                return;
            }

            const citations = citationData.citations || [];
            if (!citations.length) {
                showMessage(citationData.message || 'No supporting files were found for this selection.');
                return;
            }

            const citationBlock = citations.map(function (item) {
                const fileName = item.filename || 'Project file';
                const snippet = item.snippet || '';
                return '<p><strong>' + escapeHtml(fileName) + '</strong><br>' + escapeHtml(snippet) + '</p>';
            }).join('');
            window.renderReportSupportingSources(
                citations.map(function (item) {
                    return {
                        source: item.filename || 'Project file',
                        document_id: item.document_id || '',
                        snippet: item.snippet || '',
                    };
                }),
                {
                    title: 'Files used for the latest citation help',
                    intro: 'These project files matched the latest citation request on this page.',
                }
            );
            const insertAt = context.range ? context.range.index + context.range.length : quill.getLength() - 1;
            quill.clipboard.dangerouslyPasteHTML(insertAt, '<h3>' + escapeHtml(cfg.support_label || 'Supporting files') + '</h3>' + citationBlock);
            updateWordCount();
            return;
        }

        if (!cfg.assistEndpoint) {
            showMessage(cfg.ai_unavailable || 'Writing help is not available right now.');
            return;
        }

        const assistResponse = await fetch(cfg.assistEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: context.text, action: action })
        });
        const assistData = await assistResponse.json();
        if (!assistResponse.ok) {
            showMessage(assistData.error || cfg.ai_unavailable || 'Writing help is not available right now.');
            return;
        }

        window.renderReportSupportingSources(assistData.supporting_sources || []);

        const suggested = (assistData.suggested || '').trim();
        if (!suggested) {
            showMessage(cfg.ai_unavailable || 'Writing help is not available right now.');
            return;
        }

        if (context.range) {
            quill.deleteText(context.range.index, context.range.length);
            quill.insertText(context.range.index, suggested);
            quill.setSelection(context.range.index + suggested.length, 0);
        } else {
            quill.insertText(quill.getLength() - 1, '\n' + suggested + '\n');
        }
        updateWordCount();
    };

    window.fetchInsertableData = function (type) {
        const containerId = 'insert' + type.charAt(0).toUpperCase() + type.slice(1) + 'List';
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '<div class="report-loading-state report-loading-state--block"><div class="report-loading-spinner report-loading-spinner--inline" aria-hidden="true"></div>' +
            '<span class="report-loading-copy">' + escapeHtml(cfg.loading_label || 'Loading project material...') + '</span></div>';

        if (type === 'codes') {
            fetch('/projects/' + projectId + '/codes')
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const codes = data.codes || [];
                    if (!codes.length) {
                        container.innerHTML = '<div class="report-runtime-state report-runtime-state--empty">' + escapeHtml(cfg.empty_codes || 'No codes are available yet.') + '</div>';
                        return;
                    }
                    container.innerHTML = codes.map(function (code) {
                        const name = escapeHtml(code.name || code.code || '');
                        return '<div class="col-6"><div class="report-runtime-card report-runtime-card--fill"><div class="report-runtime-card-body report-runtime-card-row">' +
                            '<div class="report-runtime-card-copy"><i class="bi bi-tag-fill report-runtime-item-icon report-button-icon" aria-hidden="true"></i><span class="report-runtime-card-title">' + name + '</span></div>' +
                            '<button class="report-insert-action insert-btn" type="button" data-insert-type="code" data-insert-val="' + escapeAttr(name) + '">' + escapeHtml(cfg.insert_label || 'Insert') + '</button>' +
                            '</div></div></div>';
                    }).join('');
                })
                .catch(function () {
                    container.innerHTML = '<div class="report-runtime-state report-runtime-state--error">Could not load project codes.</div>';
                });
            return;
        }

        if (type === 'extractions') {
            fetch('/projects/' + projectId + '/extractions')
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const results = data.results || [];
                    if (!results.length) {
                        container.innerHTML = '<div class="report-runtime-state report-runtime-state--empty">' + escapeHtml(cfg.empty_extractions || 'No saved data tables are available yet.') + '</div>';
                        return;
                    }
                    container.innerHTML = results.map(function (result) {
                        let parsed = {};
                        try { parsed = JSON.parse(result.data_json || '{}'); } catch (error) { parsed = {}; }
                        const summary = Object.entries(parsed).map(function (entry) {
                            return escapeHtml(entry[0]) + ': ' + escapeHtml(String(entry[1]));
                        }).join(', ');
                        return '<div class="report-runtime-card"><div class="report-runtime-card-body">' +
                            '<h6 class="report-runtime-card-title report-runtime-card-heading">Document ' + escapeHtml(String(result.document_id || '')) + '</h6>' +
                            '<p class="report-runtime-card-summary">' + (summary || 'Saved table entry') + '</p>' +
                            '<button class="report-insert-action insert-btn" type="button" data-insert-type="extraction" data-insert-val="' + escapeAttr(summary || 'Saved table entry') + '">' + escapeHtml(cfg.insert_label || 'Insert') + '</button>' +
                            '</div></div>';
                    }).join('');
                })
                .catch(function () {
                    container.innerHTML = '<div class="report-runtime-state report-runtime-state--error">Could not load saved data tables.</div>';
                });
            return;
        }

        if (type === 'tasks') {
            fetch('/projects/' + projectId + '/tasks')
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const tasks = data.tasks || [];
                    if (!tasks.length) {
                        container.innerHTML = '<div class="report-runtime-state report-runtime-state--empty">' + escapeHtml(cfg.empty_tasks || 'No project tasks are available yet.') + '</div>';
                        return;
                    }
                    container.innerHTML = tasks.map(function (task) {
                        const title = escapeHtml(task.title || task.name || '');
                        return '<div class="report-runtime-list-item report-runtime-card-row report-runtime-list-item-body">' +
                            '<div class="report-runtime-card-copy"><i class="bi bi-circle report-runtime-item-icon--task report-button-icon" aria-hidden="true"></i><span class="report-runtime-card-title">' + title + '</span></div>' +
                            '<button class="report-insert-action insert-btn" type="button" data-insert-type="task" data-insert-val="' + escapeAttr(title) + '">' + escapeHtml(cfg.insert_label || 'Insert') + '</button>' +
                            '</div>';
                    }).join('');
                })
                .catch(function () {
                    container.innerHTML = '<div class="report-runtime-state report-runtime-state--error">Could not load project tasks.</div>';
                });
            return;
        }

        if (type === 'flashcards') {
            fetch('/projects/' + projectId + '/flashcards')
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    const cards = data.flashcards || [];
                    if (!cards.length) {
                        container.innerHTML = '<div class="report-runtime-state report-runtime-state--empty">' + escapeHtml(cfg.empty_flashcards || 'No study cards are available yet.') + '</div>';
                        return;
                    }
                    container.innerHTML = cards.map(function (card) {
                        const front = escapeHtml(card.front || '');
                        const back = escapeHtml(card.back || '');
                        return '<div class="report-runtime-card"><div class="report-runtime-card-body">' +
                            '<h6 class="report-runtime-card-title report-runtime-card-heading"><i class="bi bi-question-circle report-runtime-item-icon--flashcard report-button-icon" aria-hidden="true"></i>' + front + '</h6>' +
                            '<p class="report-runtime-card-summary">' + back + '</p>' +
                            '<button class="report-insert-action insert-btn" type="button" data-insert-type="flashcard" data-insert-val="' + escapeAttr(front + '|' + back) + '">' + escapeHtml(cfg.insert_label || 'Insert') + '</button>' +
                            '</div></div>';
                    }).join('');
                })
                .catch(function () {
                    container.innerHTML = '<div class="report-runtime-state report-runtime-state--error">Could not load study cards.</div>';
                });
        }
    };

    window.insertEditorBlock = function (type, content) {
        const range = quill.getSelection(true) || { index: quill.getLength() - 1 };
        let blockHtml = '';

        if (type === 'code') {
            blockHtml = '<span class="report-inline-code-chip">#' + escapeHtml(content) + '</span>&nbsp;';
        } else if (type === 'extraction') {
            blockHtml = '<blockquote><em>' + escapeHtml(content) + '</em></blockquote><p><br></p>';
        } else if (type === 'task') {
            blockHtml = '<p><strong>Task:</strong> ' + escapeHtml(content) + '</p>';
        } else if (type === 'flashcard') {
            const parts = String(content || '').split('|');
            blockHtml = '<div class="report-inline-flashcard">' +
                '<p class="report-inline-flashcard-question">Question: ' + escapeHtml(parts[0] || '') + '</p>' +
                '<p class="report-inline-flashcard-answer">Answer: ' + escapeHtml(parts[1] || '') + '</p></div><p><br></p>';
        }

        quill.clipboard.dangerouslyPasteHTML(range.index, blockHtml);
        quill.setSelection(range.index + 1, 0);
        updateWordCount();

        const modalEl = document.getElementById('insertDataModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
    };

    document.addEventListener('click', function (event) {
        const button = event.target.closest('.insert-btn');
        if (button && button.dataset.insertType) {
            window.insertEditorBlock(button.dataset.insertType, button.dataset.insertVal || '');
        }
    });

    document.addEventListener('shown.bs.tab', function (event) {
        if (event.target.id === 'tab-codes') window.fetchInsertableData('codes');
        if (event.target.id === 'tab-extractions') window.fetchInsertableData('extractions');
        if (event.target.id === 'tab-tasks') window.fetchInsertableData('tasks');
        if (event.target.id === 'tab-flashcards') window.fetchInsertableData('flashcards');
    });

    const insertModal = document.getElementById('insertDataModal');
    if (insertModal) {
        insertModal.addEventListener('shown.bs.modal', function () {
            window.fetchInsertableData('codes');
        });
    }

    loadDraft().catch(function (error) {
        console.error('Could not load the report draft.', error);
        showMessage('Could not load the report draft.');
    });
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', window.initReportEditor);
} else {
    setTimeout(window.initReportEditor, 100);
}
