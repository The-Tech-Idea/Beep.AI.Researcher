/**
 * Phase 2 Evidence Synthesis UI.
 * All user-facing strings use config-based translations (window.BEEP_I18N).
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var questionEl = document.getElementById('synthesisQuestion');
    var projectEl = document.getElementById('synthesisProject');
    var maxEvidenceEl = document.getElementById('synthesisMaxEvidence');
    var qualityEl = document.getElementById('synthesisQuality');
    var runBtn = document.getElementById('btnRunSynthesis');
    var loadingEl = document.getElementById('synthesisLoading');
    var errorEl = document.getElementById('synthesisError');
    var resultEl = document.getElementById('synthesisResult');
    var answerEl = document.getElementById('resultAnswer');
    var confidenceEl = document.getElementById('resultConfidence');
    var evidenceBody = document.getElementById('evidenceTableBody');
    var statsEl = document.getElementById('synthesisStats');
    var pastLoadingEl = document.getElementById('pastReportsLoading');
    var pastListEl = document.getElementById('pastReportsList');

    if (!questionEl || !runBtn) return;

    // Load projects
    fetch('/researcher/api/projects')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            (data.projects || []).forEach(function (p) {
                var opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                projectEl.appendChild(opt);
            });
        })
        .catch(function () { /* silently fail — project dropdown will be empty */ });

    runBtn.addEventListener('click', function () {
        var projectId = projectEl.value;
        var question = questionEl.value.trim();
        if (!projectId) { showToast(t('synthesis.toast.select_project'), 'warning'); return; }
        if (!question) { showToast(t('synthesis.toast.enter_question'), 'warning'); return; }

        runBtn.disabled = true;
        runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + t('synthesis.button.synthesising');
        hide(errorEl);
        hide(resultEl);
        show(loadingEl);

        fetch('/projects/' + projectId + '/synthesis/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                max_evidence: parseInt(maxEvidenceEl.value),
                quality_mode: qualityEl.value,
            }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i>' + t('synthesis.synthesise');
            hide(loadingEl);

            if (data.error) {
                errorEl.textContent = data.error;
                show(errorEl);
                return;
            }

            renderResult(data);
        })
        .catch(function (e) {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="bi bi-lightning-charge me-1"></i>' + t('synthesis.synthesise');
            hide(loadingEl);
            errorEl.textContent = t('synthesis.error.failed') + e.message;
            show(errorEl);
        });
    });

    function renderResult(data) {
        answerEl.textContent = data.answer || t('synthesis.answer.empty');

        // Confidence badge
        var conf = data.confidence || 'mixed';
        var confLabels = {
            supporting: t('synthesis.confidence.supporting'),
            contradicting: t('synthesis.confidence.contradicting'),
            mixed: t('synthesis.confidence.mixed')
        };
        var badgeClass = conf === 'supporting' ? 'bg-success' : conf === 'contradicting' ? 'bg-danger' : 'bg-warning text-dark';
        confidenceEl.className = 'badge ' + badgeClass;
        confidenceEl.textContent = confLabels[conf] || conf;

        // Evidence table
        evidenceBody.innerHTML = '';
        (data.evidence || []).forEach(function (ev, i) {
            var tr = document.createElement('tr');
            var polarity = ev.polarity || 'mentioning';
            tr.innerHTML =
                '<td class="text-muted">' + (i + 1) + '</td>' +
                '<td class="small">' + esc(ev.snippet || '') + '</td>' +
                '<td><span class="evidence-stance" data-stance="' + polarity + '"></span></td>' +
                '<td class="text-muted small">' + ((ev.score || 0).toFixed(2)) + '</td>' +
                '<td><button class="btn btn-sm btn-outline-secondary wq-flag-btn" data-row="' + i + '" title="' + t('synthesis.evidence.flag_stance') + '"><i class="bi bi-flag"></i></button></td>';
            evidenceBody.appendChild(tr);

            // Render stance badge
            var stanceSpan = tr.querySelector('.evidence-stance');
            if (window.BEEP_COMPONENTS && window.BEEP_COMPONENTS.StanceBadge) {
                new window.BEEP_COMPONENTS.StanceBadge(stanceSpan, polarity);
            } else {
                stanceSpan.textContent = polarity;
            }
        });

        // Stats
        statsEl.innerHTML = '';
        [
            { label: t('synthesis.confidence.supporting'), value: data.supporting_count || 0, color: 'success' },
            { label: t('synthesis.confidence.contradicting'), value: data.contradicting_count || 0, color: 'danger' },
            { label: t('synthesis.confidence.mixed'), value: data.mentioning_count || 0, color: 'secondary' },
        ].forEach(function (s) {
            var div = document.createElement('div');
            div.className = 'col-md-4';
            div.innerHTML = '<div class="card bg-dark border-secondary"><div class="card-body text-center"><h4 class="text-' + s.color + '">' + s.value + '</h4><small class="text-muted">' + s.label + '</small></div></div>';
            statsEl.appendChild(div);
        });

        show(resultEl);

        // Bind flag buttons
        evidenceBody.querySelectorAll('.wq-flag-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var row = parseInt(btn.dataset.row);
                var polarities = ['supporting', 'contradicting', 'mentioning'];
                var current = polarities.indexOf((btn.closest('tr').querySelector('.evidence-stance').textContent || 'mentioning').toLowerCase());
                var next = polarities[(current + 1) % 3];
                btn.closest('tr').querySelector('.evidence-stance').textContent = next;
                showToast(t('synthesis.toast.stance_changed') + ' ' + next, 'info');
            });
        });
    }

    function show(el) { if (el) el.removeAttribute('hidden'); }
    function hide(el) { if (el) el.setAttribute('hidden', ''); }
    function esc(str) { var el = document.createElement('span'); el.textContent = str || ''; return el.innerHTML; }
    function showToast(msg, type) {
        var toast = document.createElement('div');
        var colors = {
            success: 'var(--color-success, #198754)',
            warning: 'var(--color-warning, #fd7e14)',
            error: 'var(--color-error, #dc3545)',
            info: 'var(--color-info, #0dcaf0)',
        };
        toast.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:9999;padding:0.75rem 1rem;border-radius:0.5rem;color:var(--text-inverse,#fff);font-size:0.85rem;max-width:400px;opacity:0;transition:opacity 0.3s ease;';
        toast.style.background = colors[type] || colors.info;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { toast.remove(); }, 300); }, 3000);
    }
})();
