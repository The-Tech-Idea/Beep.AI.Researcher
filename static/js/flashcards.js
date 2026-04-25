/* Flashcards page logic — full rewrite with document selector, flip cards, delete */
(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────
    var cfgEl = document.getElementById('flashcards-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var docViewerBaseUrl = (cfg.docViewerUrl || '').replace('/0', '/'); // e.g. /researcher/projects/5/documents/
    var i18n = cfg.i18n || {};
    if (!projectId) return;

    // ── DOM refs ────────────────────────────────────────────────────────
    var listEl = document.getElementById('flashcardsList');
    var btnGenerate = document.getElementById('btnGenerate');
    var genProgress = document.getElementById('genProgress');
    var fcStats = document.getElementById('fcStats');
    var docSelectorEl = document.getElementById('docSelector');
    var supportingSourcesPanelEl = document.getElementById('flashcardsSupportingSources');
    var supportingSourcesPanel = window.ProjectSupportingSources && supportingSourcesPanelEl
        ? window.ProjectSupportingSources.create(supportingSourcesPanelEl, {
            documentUrlTemplate: '/researcher/projects/' + projectId + '/documents/__DOC_ID__?source_view=answer',
            title: 'Files used to create these study cards',
            intro: 'These project files supported the latest study cards created on this page.',
        })
        : null;

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

    function setQuizCtaVisible(isVisible) {
        var cta = document.getElementById('flashcardsQuizCta');
        if (cta) {
            cta.hidden = !isVisible;
        }
    }

    function formatCardCount(count) {
        if (count === 0) return i18n.stats_zero || '0 study cards';
        if (count === 1) return i18n.stats_one || '1 study card';
        return (i18n.stats_many || '{count} study cards').replace('{count}', count);
    }

    // ── Load existing flashcards ────────────────────────────────────────
    async function load() {
        try {
            var r = await fetch('/projects/' + projectId + '/flashcards');
            var j = await r.json();
            var cards = j.flashcards || [];
            renderCards(cards);
            if (fcStats) fcStats.textContent = formatCardCount(cards.length);
        } catch (e) {
            if (listEl) {
                listEl.innerHTML = '<div class="flashcards-message flashcards-message--error">' +
                    escapeHtml(i18n.load_error || 'Could not load study cards.') +
                    '</div>';
            }
        }
    }

    // ── Render cards ────────────────────────────────────────────────────
    function renderCards(cards) {
        if (!listEl) return;
        if (!cards.length) {
            listEl.innerHTML =
                '<div class="spa-empty flashcards-empty-state">' +
                '<i class="bi bi-card-text flashcards-empty-icon"></i>' +
                '<h5 class="flashcards-empty-title">' + escapeHtml(i18n.empty_title || 'No study cards yet') + '</h5>' +
                '<p class="flashcards-empty-copy">' + escapeHtml(i18n.empty_desc || 'Choose files and create study cards when you are ready to review.') + '</p></div>';
            setQuizCtaVisible(false);
            return;
        }

        var html = '<div class="row g-3">';
        cards.forEach(function (c) {
            html +=
                '<div class="col-md-6" id="fc-' + c.id + '">' +
                '<div class="card fc-card h-100" data-fc-id="' + c.id + '" tabindex="0"' +
                ' title="Click to flip">' +
                '<div class="card-body position-relative flashcards-card-body">' +
                '<div class="fc-front flashcards-card-face">' +
                '<div class="d-flex align-items-start gap-2">' +
                '<i class="bi bi-question-circle flashcards-card-icon flashcards-card-icon--front flashcards-card-icon-offset" aria-hidden="true"></i>' +
                '<div class="flex-grow-1">' + escapeHtml(c.front) + '</div>' +
                '</div>' +
                '</div>' +
                '<div class="fc-back flashcards-card-face" hidden>' +
                '<div class="d-flex align-items-start gap-2">' +
                '<i class="bi bi-lightbulb flashcards-card-icon flashcards-card-icon--back flashcards-card-icon-offset" aria-hidden="true"></i>' +
                '<div class="flex-grow-1">' + escapeHtml(c.back) +
                (c.document_id && docViewerBaseUrl
                    ? '<div class="mt-2">' +
                      '<a href="' + docViewerBaseUrl + c.document_id + '" target="_blank" rel="noopener" ' +
                      'class="flashcards-source-link">' +
                      '<i class="bi bi-file-earmark-text" aria-hidden="true"></i>' +
                      (i18n.source_link || 'Read in') + ' ' + escapeHtml(c.document_name || 'source document') + ' \u2192' +
                      '</a></div>'
                    : '') +
                '</div>' +
                '</div>' +
                '</div>' +
                '<div class="d-flex justify-content-between align-items-center mt-3">' +
                '<small class="flashcards-flip-hint"><i class="bi bi-hand-index flashcards-flip-hint-icon" aria-hidden="true"></i>' + escapeHtml(i18n.flip_hint || 'Click to flip') + '</small>' +
                '<button class="flashcards-delete-button fc-delete-btn" data-fc-id="' + c.id + '" type="button"' +
                ' title="' + escapeHtml(i18n.delete_label || 'Delete') + '"><i class="bi bi-trash"></i></button>' +
                '</div>' +
                '</div></div></div>';
        });
        html += '</div>';
        listEl.innerHTML = html;

        setQuizCtaVisible(true);

        // Bind flip
        listEl.querySelectorAll('.fc-card').forEach(function (card) {
            function toggleCardFaces() {
                var front = card.querySelector('.fc-front');
                var back = card.querySelector('.fc-back');
                if (!front || !back) {
                    return;
                }

                front.hidden = !front.hidden;
                back.hidden = !back.hidden;
            }

            card.addEventListener('click', function (e) {
                if (e.target.closest('.fc-delete-btn')) return;
                if (e.target.closest('.flashcards-source-link')) return;
                toggleCardFaces();
            });
            card.addEventListener('keydown', function (e) {
                if (e.target.closest('.fc-delete-btn')) return;
                if (e.key !== 'Enter' && e.key !== ' ') return;
                e.preventDefault();
                toggleCardFaces();
            });
        });

        // Bind delete
        listEl.querySelectorAll('.fc-delete-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteCard(parseInt(btn.dataset.fcId));
            });
        });
    }

    // ── Delete card ─────────────────────────────────────────────────────
    async function deleteCard(cardId) {
        try {
            var r = await fetch('/projects/' + projectId + '/flashcards/' + cardId, { method: 'DELETE' });
            if (r.ok) {
                var el = document.getElementById('fc-' + cardId);
                if (el) el.remove();
                var remaining = listEl.querySelectorAll('.fc-card').length;
                if (fcStats) fcStats.textContent = formatCardCount(remaining);
                if (remaining === 0) load(); // show empty state
            }
        } catch (e) { /* ignore */ }
    }

    // ── Generate ────────────────────────────────────────────────────────
    if (btnGenerate) {
        btnGenerate.addEventListener('click', async function () {
            var docIds = docSelector ? docSelector.getSelectedIds() : [];
            var limit = parseInt(document.getElementById('fcLimit').value) || 5;

            btnGenerate.disabled = true;
            setGenerateProgressVisible(true);

            try {
                var body = { limit: limit };
                if (docIds.length) body.document_ids = docIds;

                var r = await fetch('/projects/' + projectId + '/flashcards', {
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
                    load(); // refresh
                } else {
                    var err = await r.json().catch(function () { return {}; });
                    showMessage(err.error || i18n.generate_error || 'Could not create study cards.');
                }
            } catch (e) {
                showMessage(i18n.network_error || ('Could not create study cards: ' + e.message));
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

    // ── Init ────────────────────────────────────────────────────────────
    load();
})();
