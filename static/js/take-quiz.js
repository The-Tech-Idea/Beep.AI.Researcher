/* Take-quiz page — question stepper with immediate feedback and scoring */
(function () {
    'use strict';

    var cfgEl = document.getElementById('take-quiz-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }

    var contentEl = document.getElementById('quizContent');
    if (!contentEl) return;
    var projectId = cfg.projectId || contentEl.dataset.projectId;
    var quizId = cfg.quizId || contentEl.dataset.quizId;
    if (!projectId || !quizId) return;

    var progressEl = document.getElementById('questionProgress');
    var progressBar = document.getElementById('progressBar');
    var i18n = cfg.i18n || {};

    var questions = [];
    var currentIndex = 0;
    var userAnswers = {}; // { question_id: selected_index }

    // ── Load quiz ───────────────────────────────────────────────────────
    async function loadQuiz() {
        try {
            var r = await fetch('/projects/' + projectId + '/quizzes/' + quizId);
            var j = await r.json();
            questions = j.questions || [];
            if (!questions.length) {
                contentEl.innerHTML = '<p class="take-quiz-empty">' + escapeHtml(i18n.empty || 'This quiz has no questions yet.') + '</p>';
                return;
            }
            currentIndex = 0;
            showQuestion(0);
        } catch (e) {
            contentEl.innerHTML = '<div class="take-quiz-message take-quiz-message--error">' +
                escapeHtml(i18n.load_error || 'Could not load this quiz.') +
                '</div>';
        }
    }

    // ── Show question ───────────────────────────────────────────────────
    function showQuestion(idx) {
        var q = questions[idx];
        if (!q) return;
        updateProgress(idx);

        var letters = ['A', 'B', 'C', 'D', 'E', 'F'];
        var selected = userAnswers[q.id];
        var answered = selected !== undefined;

        var html = '<div class="mb-4">';
        html += '<h5 class="mb-3">' + escapeHtml(q.question) + '</h5>';
        html += '<div class="d-grid gap-2">';

        q.options.forEach(function (opt, i) {
            var isSelected = selected === i;
            var isCorrect = i === q.correct_index;
            var cls = 'btn take-quiz-option-button text-start d-flex align-items-center gap-2';
            if (answered) {
                if (isCorrect) cls += ' is-correct';
                else if (isSelected && !isCorrect) cls += ' is-incorrect';
                else cls += ' is-muted';
            }
            html += '<button class="' + cls + '" data-option="' + i + '"' +
                (answered ? ' disabled' : '') + '>';
            html += '<span class="take-quiz-option-badge">' + letters[i] + '</span>';
            html += '<span>' + escapeHtml(opt) + '</span>';
            if (answered && isCorrect) html += '<i class="bi bi-check-circle-fill ms-auto take-quiz-option-state"></i>';
            if (answered && isSelected && !isCorrect) html += '<i class="bi bi-x-circle-fill ms-auto take-quiz-option-state"></i>';
            html += '</button>';
        });

        html += '</div></div>';

        // Navigation
        html += '<div class="d-flex justify-content-between mt-4">';
        if (idx > 0) {
            html += '<button class="btn btn-outline-secondary" id="btnPrev">' +
                '<i class="bi bi-arrow-left me-1"></i>' + escapeHtml(i18n.previous || 'Previous question') + '</button>';
        } else {
            html += '<div></div>';
        }

        if (answered) {
            if (idx < questions.length - 1) {
                html += '<button class="btn btn-primary" id="btnNext">' +
                    escapeHtml(i18n.next || 'Next question') + ' <i class="bi bi-arrow-right ms-1"></i></button>';
            } else {
                html += '<button class="btn take-quiz-finish-button" id="btnFinish">' +
                    '<i class="bi bi-check2-circle me-1"></i>' + escapeHtml(i18n.finish || 'Finish quiz') + '</button>';
            }
        }
        html += '</div>';

        contentEl.innerHTML = html;

        // Bind option selection
        if (!answered) {
            contentEl.querySelectorAll('[data-option]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    userAnswers[q.id] = parseInt(btn.dataset.option);
                    showQuestion(idx); // re-render with feedback
                });
            });
        }

        // Bind navigation
        var btnPrev = document.getElementById('btnPrev');
        var btnNext = document.getElementById('btnNext');
        var btnFinish = document.getElementById('btnFinish');
        if (btnPrev) btnPrev.addEventListener('click', function () { currentIndex--; showQuestion(currentIndex); });
        if (btnNext) btnNext.addEventListener('click', function () { currentIndex++; showQuestion(currentIndex); });
        if (btnFinish) btnFinish.addEventListener('click', submitQuiz);
    }

    // ── Update progress ─────────────────────────────────────────────────
    function updateProgress(idx) {
        var answered = Object.keys(userAnswers).length;
        if (progressEl) {
            var progressText = i18n.progress || 'Question {current} of {total} ({answered} answered)';
            progressEl.textContent = progressText
                .replace('{current}', idx + 1)
                .replace('{total}', questions.length)
                .replace('{answered}', answered);
        }
        if (progressBar) progressBar.style.width = ((idx + 1) / questions.length * 100) + '%';
    }

    // ── Submit quiz ─────────────────────────────────────────────────────
    async function submitQuiz() {
        var answers = questions.map(function (q) {
            return { question_id: q.id, selected: userAnswers[q.id] !== undefined ? userAnswers[q.id] : -1 };
        });

        try {
            var r = await fetch('/projects/' + projectId + '/quizzes/' + quizId + '/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answers: answers }),
            });
            var j = await r.json();
            showResults(j);
        } catch (e) {
            alert((i18n.submit_error || 'Could not submit your answers.') + ' ' + e.message);
        }
    }

    // ── Show results ────────────────────────────────────────────────────
    function showResults(result) {
        var pct = result.percentage || 0;
        var tone = pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'danger';

        var html = '<div class="text-center py-4">';
        html += '<div class="display-4 fw-bold take-quiz-score take-quiz-score--' + tone + '">' + pct + '%</div>';
        html += '<h5 class="mt-2">' + escapeHtml(i18n.score_label || 'Score') + ': ' + result.score + ' / ' + result.total + '</h5>';
        html += '<div class="progress mx-auto mt-3 take-quiz-results-progress">';
        html += '<div class="take-quiz-results-progress-bar take-quiz-results-progress-bar--' + tone + '" style="width:' + pct + '%"></div></div>';

        html += '<div class="mt-4">';
        html += '<a href="/researcher/projects/' + projectId + '/quizzes" class="btn btn-primary me-2" data-spa-link>' +
            '<i class="bi bi-arrow-left me-1"></i>' + escapeHtml(i18n.back_to_list || 'Back to quizzes') + '</a>';
        html += '<button class="btn btn-outline-secondary" id="btnRetake">' +
            '<i class="bi bi-arrow-repeat me-1"></i>' + escapeHtml(i18n.retry || 'Try again') + '</button>';
        html += '</div></div>';

        contentEl.innerHTML = html;
        if (progressEl) progressEl.textContent = i18n.completed || 'Completed';
        if (progressBar) progressBar.style.width = '100%';

        var btnRetake = document.getElementById('btnRetake');
        if (btnRetake) {
            btnRetake.addEventListener('click', function () {
                userAnswers = {};
                currentIndex = 0;
                showQuestion(0);
            });
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    loadQuiz();
})();
