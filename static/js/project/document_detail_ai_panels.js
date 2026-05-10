/**
 * Phase 4 — Document Detail AI Panels.
 * Auto-extract panel (Summary | Key Findings | Tables) + Flashcard preview.
 * Loaded on document detail pages. All CSS uses design-system tokens.
 * All user-facing strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var projectId = window.location.pathname.match(/\/projects\/(\d+)/);
    var docId = window.location.pathname.match(/\/documents\/(\d+)/);
    projectId = projectId ? projectId[1] : null;
    docId = docId ? docId[1] : null;
    if (!projectId || !docId) return;

    // ── Auto-Extract Panel ───────────────────────────────────────────────

    var extractBtn = document.getElementById('btnAutoExtract');
    var extractResult = document.getElementById('autoExtractResult');
    var extractLoading = document.getElementById('autoExtractLoading');
    var extractError = document.getElementById('autoExtractError');

    if (extractBtn) {
        extractBtn.addEventListener('click', function () {
            extractBtn.disabled = true;
            extractBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + t('document_ai.extracting');
            hide(extractError);
            hide(extractResult);
            show(extractLoading);

            fetch('/projects/' + projectId + '/documents/' + docId + '/auto-extract')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    extractBtn.disabled = false;
                    extractBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i>' + t('document_ai.auto_extract');
                    hide(extractLoading);

                    if (data.error) {
                        extractError.textContent = data.error;
                        show(extractError);
                        return;
                    }

                    renderExtractResult(data);
                })
                .catch(function (e) {
                    extractBtn.disabled = false;
                    extractBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i>' + t('document_ai.auto_extract');
                    hide(extractLoading);
                    extractError.textContent = t('document_ai.error.extraction_failed') + e.message;
                    show(extractError);
                });
        });
    }

    function renderExtractResult(data) {
        var summaryEl = document.getElementById('extractSummary');
        var findingsEl = document.getElementById('extractFindings');
        var tablesEl = document.getElementById('extractTables');

        if (summaryEl) summaryEl.innerHTML = data.summary ? '<p>' + esc(data.summary) + '</p>' : '<p class="text-muted">' + t('document_ai.no_summary') + '</p>';

        if (findingsEl) {
            findingsEl.innerHTML = '';
            (data.findings || []).forEach(function (f) {
                var li = document.createElement('li');
                li.textContent = f;
                findingsEl.appendChild(li);
            });
        }

        if (tablesEl) {
            tablesEl.innerHTML = '';
            (data.tables || []).forEach(function (table) {
                var div = document.createElement('div');
                div.className = 'mb-3';
                div.innerHTML = '<h6>' + esc(table.title || t('document_ai.table_default')) + '</h6>';
                if (table.headers && table.rows) {
                    var tbl = document.createElement('table');
                    tbl.className = 'table table-sm table-dark';
                    var thead = document.createElement('thead');
                    var tr = document.createElement('tr');
                    table.headers.forEach(function (h) {
                        var th = document.createElement('th');
                        th.textContent = h;
                        tr.appendChild(th);
                    });
                    thead.appendChild(tr);
                    tbl.appendChild(thead);
                    var tbody = document.createElement('tbody');
                    table.rows.forEach(function (row) {
                        var tr2 = document.createElement('tr');
                        row.forEach(function (cell) {
                            var td = document.createElement('td');
                            td.textContent = cell;
                            tr2.appendChild(td);
                        });
                        tbody.appendChild(tr2);
                    });
                    tbl.appendChild(tbody);
                    div.appendChild(tbl);
                }
                tablesEl.appendChild(div);
            });
                    table.appendChild(thead);
                    var tbody = document.createElement('tbody');
                    t.rows.forEach(function (row) {
                        var tr2 = document.createElement('tr');
                        row.forEach(function (cell) {
                            var td = document.createElement('td');
                            td.textContent = cell;
                            tr2.appendChild(td);
                        });
                        tbody.appendChild(tr2);
                    });
                    table.appendChild(tbody);
                    div.appendChild(table);
                }
                tablesEl.appendChild(div);
            });
        }

        show(extractResult);
    }

    // ── Flashcard Preview ────────────────────────────────────────────────

    var flashcardBtn = document.getElementById('btnGenerateFlashcards');
    var flashcardResult = document.getElementById('flashcardResult');
    var flashcardLoading = document.getElementById('flashcardLoading');
    var flashcardError = document.getElementById('flashcardError');

    if (flashcardBtn) {
        flashcardBtn.addEventListener('click', function () {
            flashcardBtn.disabled = true;
            flashcardBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + t('document_ai.generating');
            hide(flashcardError);
            hide(flashcardResult);
            show(flashcardLoading);

            fetch('/projects/' + projectId + '/documents/' + docId + '/generate-flashcards', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ count: 6 }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    flashcardBtn.disabled = false;
                    flashcardBtn.innerHTML = '<i class="bi bi-card-text me-1"></i>' + t('document_ai.generate_flashcards');
                    hide(flashcardLoading);

                    if (data.error) {
                        flashcardError.textContent = data.error;
                        show(flashcardError);
                        return;
                    }

                    renderFlashcards(data.flashcards || []);
                })
                .catch(function (e) {
                    flashcardBtn.disabled = false;
                    flashcardBtn.innerHTML = '<i class="bi bi-card-text me-1"></i>' + t('document_ai.generate_flashcards');
                    hide(flashcardLoading);
                    flashcardError.textContent = t('document_ai.error.generation_failed') + e.message;
                    show(flashcardError);
                });
        });
    }

    function renderFlashcards(cards) {
        var grid = document.getElementById('flashcardGrid');
        if (!grid) return;

        grid.innerHTML = '';
        cards.forEach(function (card, i) {
            var div = document.createElement('div');
            div.className = 'flashcard-preview';
            div.innerHTML =
                '<div class="flashcard-preview__front">' + esc(card.question || '') + '</div>' +
                '<div class="flashcard-preview__back">' + esc(card.answer || '') + '</div>' +
                    '<div class="flashcard-preview__actions">' +
                        '<input type="checkbox" class="form-check-input flashcard-select" data-idx="' + i + '" checked>' +
                        '<span class="small text-muted">' + t('document_ai.flashcard.select') + '</span>' +
                    '</div>';
            grid.appendChild(div);
        });

        show(flashcardResult);
    }

    // ── Helpers ──────────────────────────────────────────────────────────

    function show(el) { if (el) el.removeAttribute('hidden'); }
    function hide(el) { if (el) el.setAttribute('hidden', ''); }
    function esc(str) { var el = document.createElement('span'); el.textContent = str || ''; return el.innerHTML; }
})();
