/**
 * Phase 4 Writing Assistant UI — extends the Writing Studio (report.html).
 *
 * Features:
 * - Analyse button: runs writing quality analysis on selected text, shows inline annotation overlay
 * - Citation Draft modal: themed paragraph draft with inline [Cite: DOI] markers
 * - Readability bar: passive voice %, hedge density, avg sentence length
 *
 * All user-facing strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var configEl = document.getElementById('report-config');
    if (!configEl) return;

    var cfg;
    try { cfg = JSON.parse(configEl.textContent); } catch (e) { return; }

    if (!cfg.analyseEndpoint) return;

    var projectId = cfg.projectId;

    // ── Helpers ──────────────────────────────────────────────────────────────

    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return document.querySelectorAll(sel); }
    function show(el) { if (el) el.removeAttribute('hidden'); }
    function hide(el) { if (el) el.setAttribute('hidden', ''); }

    // ── Quill editor reference (set after report_page.js initialises) ────────

    var quill = null;
    function getQuill() {
        if (quill) return quill;
        if (typeof window.reportQuill !== 'undefined') {
            quill = window.reportQuill;
        }
        return quill;
    }

    // ── Analyse button ───────────────────────────────────────────────────────

    var analyseBtn = $('#analyseSelectedBtn');
    var analysisModalEl = $('#analysisOverlayModal');
    var analysisModal;
    if (analysisModalEl && typeof bootstrap !== 'undefined') {
        analysisModal = new bootstrap.Modal(analysisModalEl);
    }

    if (analyseBtn) {
        analyseBtn.addEventListener('click', function () {
            var q = getQuill();
            if (!q) {
                showToast(t('writing_assistant.toast.editor_not_ready'), 'warning');
                return;
            }
            var selected = q.getSelectedText();
            if (!selected || selected.trim().length < 20) {
                showToast(t('writing_assistant.toast.select_text'), 'warning');
                return;
            }

            if (analysisModal) analysisModal.show();
            showLoading();
            runAnalysis(selected);
        });
    }

    function runAnalysis(text) {
        fetch(cfg.analyseEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            hideLoading();
            if (data.error) {
                showError(data.error);
                return;
            }
            renderAnalysisResult(data);
        })
        .catch(function (e) {
            hideLoading();
            showError(t('writing_assistant.error.analysis_failed') + e.message);
        });
    }

    function showLoading() {
        show($('#analysisOverlayLoading'));
        hide($('#analysisOverlayResult'));
        hide($('#analysisOverlayError'));
    }

    function showError(msg) {
        hide($('#analysisOverlayLoading'));
        hide($('#analysisOverlayResult'));
        var errEl = $('#analysisOverlayError');
        errEl.textContent = msg;
        show(errEl);
    }

    function renderAnalysisResult(data) {
        hide($('#analysisOverlayLoading'));
        hide($('#analysisOverlayError'));
        show($('#analysisOverlayResult'));

        $('#analysisOverall').textContent = data.overall_score != null ? data.overall_score.toFixed(1) + t('writing_assistant.score_suffix') : t('writing_assistant.score_not_available');
        $('#analysisTone').textContent = data.tone_score != null ? data.tone_score.toFixed(1) : t('writing_assistant.score_not_available');
        $('#analysisClarity').textContent = data.clarity_score != null ? data.clarity_score.toFixed(1) : t('writing_assistant.score_not_available');
        $('#analysisGrammar').textContent = data.grammar_score != null ? data.grammar_score.toFixed(1) : t('writing_assistant.score_not_available');

        // Colour the overall score
        var overallEl = $('#analysisOverall');
        if (data.overall_score != null) {
            overallEl.className = 'writing-analysis-score-value wq-' + scoreTier(data.overall_score);
        }

        // Issues list
        var issuesEl = $('#analysisIssues');
        issuesEl.innerHTML = '';
        if (!data.issues || data.issues.length === 0) {
            issuesEl.innerHTML = '<p class="text-success"><i class="bi bi-check-circle"></i> ' + t('writing_assistant.no_issues') + '</p>';
        } else {
            data.issues.forEach(function (issue, idx) {
                var item = document.createElement('div');
                item.className = 'writing-analysis-issue';
                item.innerHTML =
                    '<div class="d-flex align-items-start gap-2">' +
                        stanceBadge(issue.type, issue.severity) +
                        '<div class="flex-grow-1">' +
                            '<strong>' + esc(issue.text) + '</strong>' +
                            '<div class="text-muted small">' + esc(issue.suggestion) + '</div>' +
                        '</div>' +
                        '<button class="btn btn-sm btn-outline-success wq-apply-btn" data-idx="' + idx + '" data-offset="' + issue.offset + '" data-length="' + issue.length + '" data-suggestion="' + escAttr(issue.suggestion) + '">' + t('writing_assistant.button.applied') + '</button>' +
                    '</div>';
                issuesEl.appendChild(item);
            });

            // Bind apply buttons
            issuesEl.querySelectorAll('.wq-apply-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    applyFix(btn.dataset.offset, btn.dataset.length, btn.dataset.suggestion, btn);
                });
            });
        }

        // Suggestions list
        var suggEl = $('#analysisSuggestions');
        suggEl.innerHTML = '';
        (data.suggestions || []).forEach(function (s) {
            var li = document.createElement('li');
            li.textContent = s;
            suggEl.appendChild(li);
        });

        // Update readability bar if scores are available
        updateReadabilityBar(data);
    }

    function scoreTier(score) {
        if (score >= 80) return 'excellent';
        if (score >= 60) return 'good';
        if (score >= 40) return 'fair';
        return 'poor';
    }

    function stanceBadge(type, severity) {
        var typeLabels = {
            passive_voice: t('writing_assistant.issue_type.passive_voice'),
            hedge: t('writing_assistant.issue_type.hedge'),
            wordy: t('writing_assistant.issue_type.wordy'),
            clarity: t('writing_assistant.issue_type.clarity'),
            grammar: t('writing_assistant.issue_type.grammar'),
            tone: t('writing_assistant.issue_type.tone')
        };
        var icons = {
            passive_voice: 'bi-chat-left-text',
            hedge: 'bi-question-circle',
            wordy: 'bi-text-paragraph',
            clarity: 'bi-lightbulb',
            grammar: 'bi-spellcheck',
            tone: 'bi-chat-square-text',
        };
        var colors = { error: 'danger', warning: 'warning', info: 'info' };
        var color = colors[severity] || 'info';
        return '<span class="badge bg-' + color + '"><i class="bi ' + (icons[type] || 'bi-info-circle') + '"></i> ' + esc(typeLabels[type] || type) + '</span> ';
    }

    function applyFix(offset, length, suggestion, btn) {
        var q = getQuill();
        if (!q) return;

        var content = q.getText();
        var before = content.slice(0, parseInt(offset));
        var after = content.slice(parseInt(offset) + parseInt(length));
        q.setText(before + suggestion + after);

        btn.textContent = t('writing_assistant.button.applied');
        btn.disabled = true;
        btn.classList.remove('btn-outline-success');
        btn.classList.add('btn-success');
        showToast(t('writing_assistant.toast.fix_applied'), 'success');
    }

    function updateReadabilityBar(data) {
        var bar = $('#writingQualityBar');
        if (!bar) return;

        if (data.overall_score != null) {
            $('#wqOverall').textContent = data.overall_score.toFixed(1);
        }
        if (data.tone_score != null) {
            $('#wqTone').textContent = data.tone_score.toFixed(1);
        }
        if (data.clarity_score != null) {
            $('#wqClarity').textContent = data.clarity_score.toFixed(1);
        }
        if (data.grammar_score != null) {
            $('#wqGrammar').textContent = data.grammar_score.toFixed(1);
        }
        if (data.issues && data.issues.length > 0) {
            $('#wqIssues').textContent = data.issues.length + ' ' + (t('writing_assistant.issues_found') || 'issues found');
        }
        show(bar);
    }

    // ── Citation Draft Modal ─────────────────────────────────────────────────

    var draftBtn = $('#btnGenerateCitationDraft');
    var draftThemeInput = $('#citationDraftTheme');
    var draftResultEl = $('#citationDraftResult');
    var draftTextEl = $('#citationDraftText');
    var draftErrorEl = $('#citationDraftError');
    var draftCitationsEl = $('#citationDraftCitations');
    var draftCitationListEl = $('#citationDraftCitationList');
    var insertDraftBtn = $('#btnInsertCitationDraft');

    var lastDraft = '';

    if (draftBtn && draftThemeInput) {
        draftBtn.addEventListener('click', function () {
            var theme = draftThemeInput.value.trim();
            if (!theme) {
                showToast(t('writing_assistant.toast.enter_theme'), 'warning');
                return;
            }
            draftBtn.disabled = true;
            draftBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + t('writing_assistant.button.generating');
            hide(draftResultEl);
            hide(draftErrorEl);
            hide(draftCitationsEl);

            fetch(cfg.citationDraftEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme: theme }),
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                draftBtn.disabled = false;
                draftBtn.innerHTML = '<i class="bi bi-stars report-button-icon" aria-hidden="true"></i><span>' + t('writing_assistant.button.generate_draft') + '</span>';

                if (data.error) {
                    draftErrorEl.textContent = data.error;
                    show(draftErrorEl);
                    return;
                }

                lastDraft = data.draft || '';
                draftTextEl.textContent = lastDraft;
                show(draftResultEl);

                if (data.formatted_citations && data.formatted_citations.length > 0) {
                    draftCitationListEl.innerHTML = '';
                    data.formatted_citations.forEach(function (c) {
                        var div = document.createElement('div');
                        div.className = 'mb-1 small';
                        div.textContent = c.formatted || (c.title + (c.authors ? ' — ' + c.authors.join(', ') : ''));
                        draftCitationListEl.appendChild(div);
                    });
                    show(draftCitationsEl);
                }
            })
            .catch(function (e) {
                draftBtn.disabled = false;
                draftBtn.innerHTML = '<i class="bi bi-stars report-button-icon" aria-hidden="true"></i><span>' + t('writing_assistant.button.generate_draft') + '</span>';
                draftErrorEl.textContent = t('writing_assistant.error.draft_failed') + e.message;
                show(draftErrorEl);
            });
        });
    }

    if (insertDraftBtn) {
        insertDraftBtn.addEventListener('click', function () {
            var q = getQuill();
            if (!q || !lastDraft) return;
            var cursor = q.getSelection();
            if (cursor) {
                q.insertText(cursor.index, lastDraft + '\n\n');
            } else {
                q.insertText(q.getLength(), '\n\n' + lastDraft);
            }
            showToast(t('writing_assistant.toast.draft_inserted'), 'success');
            var citationModal = bootstrap.Modal.getInstance($('#citationDraftModal'));
            if (citationModal) citationModal.hide();
        });
    }

    // Re-analyse button in modal
    var reanalyseBtn = $('#btnReanalyse');
    if (reanalyseBtn) {
        reanalyseBtn.addEventListener('click', function () {
            var q = getQuill();
            if (!q) return;
            var selected = q.getSelectedText();
            if (!selected || selected.trim().length < 20) {
                selected = q.getText();
            }
            showLoading();
            runAnalysis(selected);
        });
    }

    // ── Toast helper ─────────────────────────────────────────────────────────

    function showToast(msg, type) {
        var existing = document.querySelector('.writing-assistant-toast');
        if (existing) existing.remove();

        var colors = {
            success: 'var(--color-success, #198754)',
            warning: 'var(--color-warning, #fd7e14)',
            error: 'var(--color-error, #dc3545)',
        };

        var toast = document.createElement('div');
        toast.className = 'writing-assistant-toast';
        toast.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:9999;padding:0.75rem 1rem;border-radius:0.5rem;color:var(--text-inverse,#fff);font-size:0.85rem;max-width:400px;opacity:0;transition:opacity 0.3s ease;';
        toast.style.background = colors[type] || colors.info;

        toast.textContent = msg;
        document.body.appendChild(toast);

        requestAnimationFrame(function () {
            toast.style.opacity = '1';
        });

        setTimeout(function () {
            toast.style.opacity = '0';
            setTimeout(function () { toast.remove(); }, 300);
        }, 3000);
    }

    // ── Utility ──────────────────────────────────────────────────────────────

    function esc(str) {
        var el = document.createElement('span');
        el.textContent = str || '';
        return el.innerHTML;
    }

    function escAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

})();
