/* Quizzes page logic — full rewrite with doc selector, quiz list, scores */
(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────
    var cfgEl = document.getElementById('quizzes-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    if (!projectId) return;

    // ── DOM refs ────────────────────────────────────────────────────────
    var listEl = document.getElementById('quizzesList');
    var btnGenerate = document.getElementById('btnGenerate');
    var genProgress = document.getElementById('genProgress');
    var docSelectorEl = document.getElementById('docSelector');
    var flashcardBanner = document.getElementById('quizzesFlashcardBanner');
    var flashcardBannerDismiss = document.getElementById('quizzesFlashcardBannerDismiss');
    var supportingSourcesPanelEl = document.getElementById('quizzesSupportingSources');
    var supportingSourcesPanel = window.ProjectSupportingSources && supportingSourcesPanelEl
        ? window.ProjectSupportingSources.create(supportingSourcesPanelEl, {
            documentUrlTemplate: '/researcher/projects/' + projectId + '/documents/__DOC_ID__?source_view=answer',
            title: 'Files used to create this quiz',
            intro: 'These project files supported the latest quiz created on this page.',
        })
        : null;

    if (flashcardBanner && window.localStorage && window.localStorage.getItem('quizzes_fc_banner')) {
        flashcardBanner.hidden = true;
    }

    if (flashcardBannerDismiss) {
        flashcardBannerDismiss.addEventListener('click', function () {
            if (window.localStorage) {
                window.localStorage.setItem('quizzes_fc_banner', '1');
            }
            if (flashcardBanner) {
                flashcardBanner.hidden = true;
            }
        });
    }

    // ── Difficulty help text ─────────────────────────────────────────────
    var diffHelp = {
        easy: cfg.i18n ? cfg.i18n.diff_easy_help : 'Source documents shown as hints.',
        standard: cfg.i18n ? cfg.i18n.diff_standard_help : 'Standard difficulty.',
        hard: cfg.i18n ? cfg.i18n.diff_hard_help : 'No hints shown.'
    };
    document.querySelectorAll('input[name="quizDifficulty"]').forEach(function (r) {
        r.addEventListener('change', function () {
            var helpEl = document.getElementById('diffHelpText');
            if (helpEl) helpEl.textContent = diffHelp[r.value] || '';
        });
    });

    // ── Document selector ──────────────────────────────────────────────
    var docSelector = null;
    if (docSelectorEl && window.DocumentSelector) {
        docSelector = new DocumentSelector(docSelectorEl, projectId);
        docSelector.load();
    }

    function showMessage(message) {
        if (message) {
            window.beepUI.notify(message);
        }
    }

    function setGenerateProgressVisible(isVisible) {
        if (genProgress) {
            genProgress.hidden = !isVisible;
        }
    }

    // ── Load quizzes ────────────────────────────────────────────────────
    async function load() {
        try {
            var r = await fetch('/projects/' + projectId + '/quizzes');
            var j = await r.json();
            renderQuizzes(j.quizzes || []);
        } catch (e) {
            if (listEl) {
                listEl.innerHTML = '<div class="quizzes-message quizzes-message--error">' +
                    escapeHtml(cfg.i18n.load_error || 'Could not load quizzes.') +
                    '</div>';
            }
        }
    }

    // ── Render quiz list ────────────────────────────────────────────────
    function renderQuizzes(quizzes) {
        if (!listEl) return;
        if (!quizzes.length) {
            listEl.innerHTML =
                '<div class="spa-empty quizzes-empty-state">' +
                '<i class="bi bi-question-circle quizzes-empty-icon"></i>' +
                '<h5 class="quizzes-empty-title">' + escapeHtml(cfg.i18n.empty_title || 'No quizzes yet') + '</h5>' +
                '<p class="quizzes-empty-copy">' + escapeHtml(cfg.i18n.empty_desc || 'Choose files and create a quiz when you are ready to check what you remember.') + '</p></div>';
            return;
        }

        var html = '<div class="row g-3">';
        quizzes.forEach(function (q) {
            var score = q.best_score !== null && q.best_score !== undefined
                ? '<span class="quizzes-score-badge">\uD83C\uDFC6 ' + q.best_score + '%</span>' : '';
            var attempts = q.attempt_count || 0;
            var lastScore = attempts > 0 && q.best_score !== null
                ? '<div class="quizzes-last-score">' + escapeHtml(cfg.i18n.last_score || 'Last score') + ': <strong>' + q.best_score + '%</strong>' +
                  (q.attempt_count > 1 ? ' &middot; ' + q.attempt_count + ' ' + escapeHtml(cfg.i18n.attempts_suffix || 'attempts') : '') + '</div>'
                : '';
            html +=
                '<div class="col-md-6" id="qz-' + q.id + '">' +
                '<div class="card h-100 quizzes-card-shell">' +
                '<div class="card-body quizzes-card-body">' +
                '<div class="d-flex align-items-start justify-content-between">' +
                '<div>' +
                '<h6 class="quizzes-card-title">' + escapeHtml(q.name) + '</h6>' +
                '<small class="quizzes-questions-meta">' + (q.question_count || 0) + ' ' + escapeHtml(cfg.i18n.questions_suffix || 'questions') + '</small>' +
                lastScore +
                '</div>' +
                '<div class="d-flex gap-1">' + score + '</div>' +
                '</div>' +
                '<div class="quizzes-action-row">' +
                '<a href="/researcher/projects/' + projectId + '/quizzes/' + q.id + '/take" ' +
                'class="quizzes-start-button" data-spa-link>' +
                '<i class="bi bi-play-fill quizzes-button-icon" aria-hidden="true"></i>' + escapeHtml(cfg.i18n.start_quiz || 'Start quiz') + '</a>' +
                '<button class="quizzes-delete-button qz-delete-btn" type="button" ' +
                'data-qz-id="' + q.id + '" title="' + escapeHtml(cfg.i18n.delete_label || 'Delete') + '"><i class="bi bi-trash"></i></button>' +
                '</div>' +
                '</div></div></div>';
        });
        html += '</div>';
        listEl.innerHTML = html;

        // Bind delete
        listEl.querySelectorAll('.qz-delete-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                deleteQuiz(parseInt(btn.dataset.qzId));
            });
        });
    }

    // ── Delete quiz ─────────────────────────────────────────────────────
    async function deleteQuiz(qzId) {
        if (!confirm(cfg.i18n.delete_confirm || 'Remove this quiz?')) return;
        try {
            var r = await fetch('/projects/' + projectId + '/quizzes/' + qzId, { method: 'DELETE' });
            if (r.ok) {
                var el = document.getElementById('qz-' + qzId);
                if (el) el.remove();
                var remaining = listEl.querySelectorAll('.card').length;
                if (remaining === 0) load();
            }
        } catch (e) { /* ignore */ }
    }

    // ── Generate quiz ───────────────────────────────────────────────────
    if (btnGenerate) {
        btnGenerate.addEventListener('click', async function () {
            var docIds = docSelector ? docSelector.getSelectedIds() : [];
            var name = (document.getElementById('quizName').value || '').trim() || 'Quiz';
            var limit = parseInt(document.getElementById('qzLimit').value) || 5;
            var diffEl = document.querySelector('input[name="quizDifficulty"]:checked');
            var difficulty = diffEl ? diffEl.value : 'standard';

            btnGenerate.disabled = true;
            setGenerateProgressVisible(true);

            try {
                var body = { name: name, limit: limit, difficulty: difficulty };
                if (docIds.length) body.document_ids = docIds;

                var r = await fetch('/projects/' + projectId + '/quiz', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });

                if (r.ok) {
                    var payload = await r.json().catch(function () { return {}; });
                    if (supportingSourcesPanel) {
                        supportingSourcesPanel.render(payload.supporting_sources || []);
                    }
                    if (payload.note) showMessage(payload.note);
                    load();
                } else {
                    var err = await r.json().catch(function () { return {}; });
                    showMessage(err.error || cfg.i18n.generate_error || 'Could not create the quiz.');
                }
            } catch (e) {
                showMessage(cfg.i18n.network_error || ('Could not create the quiz: ' + e.message));
            } finally {
                btnGenerate.disabled = false;
                setGenerateProgressVisible(false);
            }
        });
    }

    // ── Helpers ──────────────────────────────────────────────────────────
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    load();
})();
