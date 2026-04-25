(function () {
    'use strict';

    var cfgEl = document.getElementById('contradictions-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }

    var projectId = cfg.projectId;
    var i18n = cfg.i18n || {};
    if (!projectId) return;

    var queryEl = document.getElementById('contradictionQuery');
    var btn = document.getElementById('btnDetect');
    var resultsEl = document.getElementById('contradictionResults');
    var progressEl = document.getElementById('detectProgress');
    var docSelectorEl = document.getElementById('docSelector');
    var auditBannerEl = document.getElementById('contradictionAuditBanner');

    var docSelector = null;
    if (docSelectorEl && window.DocumentSelector) {
        docSelector = new DocumentSelector(docSelectorEl, projectId);
        docSelector.load();
    }

    renderEmptyState();

    if (btn) {
        btn.addEventListener('click', async function () {
            var query = (queryEl.value || '').trim();
            if (!query) {
                renderError(i18n.missingQuery || 'Enter a statement or research question to review.');
                if (queryEl) {
                    queryEl.focus();
                }
                return;
            }

            btn.disabled = true;
            setProgressVisible(true);

            try {
                var body = { query: query };
                var docIds = docSelector ? docSelector.getSelectedIds() : [];
                if (docIds.length) body.document_ids = docIds;

                var r = await fetch('/projects/' + projectId + '/contradictions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                var j = await r.json();
                renderResults(j);
            } catch (err) {
                renderError(err.message);
            } finally {
                btn.disabled = false;
                setProgressVisible(false);
            }
        });
    }

    function setProgressVisible(isVisible) {
        if (progressEl) {
            progressEl.hidden = !isVisible;
        }
    }

    function setAuditBannerVisible(isVisible) {
        if (auditBannerEl) {
            auditBannerEl.hidden = !isVisible;
        }
    }

    function renderEmptyState() {
        if (!resultsEl) return;
        resultsEl.innerHTML =
            '<div class="card review-panel review-empty-state contradictions-empty-card">' +
                '<div class="card-body contradictions-empty-body">' +
                    '<i class="bi bi-search contradictions-empty-icon"></i>' +
                    '<h5 class="contradictions-empty-title">' + escapeHtml(i18n.emptyTitle || 'Nothing checked yet') + '</h5>' +
                    '<p class="contradictions-empty-copy">' + escapeHtml(i18n.emptyBody || 'Enter a statement above to check whether your files agree.') + '</p>' +
                '</div>' +
            '</div>';
        setAuditBannerVisible(false);
    }

    function renderError(message) {
        if (!resultsEl) return;
        resultsEl.innerHTML =
            '<div class="contradictions-message contradictions-message--error">' +
                '<i class="bi bi-x-circle contradictions-message-icon" aria-hidden="true"></i>' +
                '<div class="contradictions-message-text">' +
                    escapeHtml(message || 'Something went wrong while reviewing your files.') +
                '</div>' +
            '</div>';
        setAuditBannerVisible(false);
    }

    function renderResults(data) {
        if (!resultsEl) return;

        var contradictions = data.contradictions || [];
        if (!contradictions.length) {
            resultsEl.innerHTML =
                '<div class="contradictions-message contradictions-message--success">' +
                    '<i class="bi bi-check-circle contradictions-message-icon" aria-hidden="true"></i>' +
                    '<div class="contradictions-message-text">' +
                        escapeHtml(data.message || 'No clear disagreements were found in the reviewed files.') +
                    '</div>' +
                '</div>';
            setAuditBannerVisible(true);
            return;
        }

        var count = contradictions.length;
        var heading = count === 1
            ? (i18n.summarySingle || '1 possible disagreement found')
            : (i18n.summaryMulti || '{count} possible disagreements found').replace('{count}', String(count));

        var html =
            '<div class="card review-panel mb-3">' +
                '<div class="card-header d-flex justify-content-between align-items-center gap-2 flex-wrap">' +
                    '<div class="d-flex align-items-center gap-2">' +
                        '<i class="bi bi-exclamation-triangle contradictions-summary-icon" aria-hidden="true"></i>' +
                        '<span class="fw-semibold">' + escapeHtml(heading) + '</span>' +
                    '</div>' +
                    '<span class="contradictions-summary-note">' + escapeHtml(data.message || '') + '</span>' +
                '</div>' +
            '</div>';

        contradictions.forEach(function (item, index) {
            html += renderResultCard(item, index);
        });

        resultsEl.innerHTML = html;
        setAuditBannerVisible(true);
    }

    function renderResultCard(item, index) {
        var sourceA = normaliseSource(item.source_a, item.claim_a || item.statement_a || '');
        var sourceB = normaliseSource(item.source_b, item.claim_b || item.statement_b || '');
        var explanation = item.explanation || '';
        var severity = item.severity || 'medium';
        var severityMeta = getSeverityMeta(severity);

        var html =
            '<div class="card review-panel mb-3">' +
                '<div class="card-header d-flex justify-content-between align-items-center gap-2 flex-wrap">' +
                    '<div class="fw-semibold">' +
                        escapeHtml((i18n.supportingView || 'Review item') + ' ' + (index + 1)) +
                    '</div>' +
                    '<span class="badge ' + severityMeta.badge + '">' + escapeHtml(severityMeta.label) + '</span>' +
                '</div>' +
                '<div class="card-body">';

        if (sourceA.text) {
            html += renderSourceBlock(sourceA, 'A');
        }
        if (sourceB.text) {
            html += renderSourceBlock(sourceB, 'B');
        }
        if (explanation) {
            html +=
                '<div class="contradictions-note-panel">' +
                    '<div class="contradictions-note-heading">' + escapeHtml(i18n.reviewNote || 'Why this may matter') + '</div>' +
                    '<div class="contradictions-note-copy">' + escapeHtml(explanation) + '</div>' +
                '</div>';
        }
        html += '</div></div>';
        return html;
    }

    function renderSourceBlock(source, labelSuffix) {
        var html =
            '<div class="contradictions-source-card">' +
                '<div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">' +
                    '<div class="small fw-semibold">' +
                        escapeHtml((i18n.fileSays || 'What the file says') + ' ' + labelSuffix) +
                    '</div>';
        if (source.documentId) {
            html +=
                    '<a class="contradictions-open-file-link" href="/researcher/projects/' + projectId +
                    '/documents/' + source.documentId + '?source_view=answer">' +
                        '<i class="bi bi-box-arrow-up-right" aria-hidden="true"></i>' + escapeHtml(i18n.openFile || 'Open file') +
                    '</a>';
        }
        html +=
                '</div>' +
                '<blockquote class="contradictions-source-quote">' +
                    escapeHtml(source.text) +
                '</blockquote>' +
                '<div class="contradictions-source-meta">' +
                    '<i class="bi bi-file-earmark-text contradictions-source-meta-icon" aria-hidden="true"></i>' + escapeHtml(source.filename || 'Project file') +
                '</div>' +
            '</div>';
        return html;
    }

    function normaliseSource(source, fallbackText) {
        if (!source) {
            return { text: fallbackText || '', filename: '', documentId: null };
        }
        if (typeof source === 'string') {
            return { text: source || fallbackText || '', filename: '', documentId: null };
        }
        return {
            text: source.claim || source.statement || source.text || fallbackText || '',
            filename: source.filename || source.source || '',
            documentId: source.document_id || source.id || null
        };
    }

    function getSeverityMeta(value) {
        if (value === 'high') {
            return { badge: 'contradictions-severity-pill contradictions-severity-high', label: i18n.severityHigh || 'Needs attention' };
        }
        if (value === 'low') {
            return { badge: 'contradictions-severity-pill contradictions-severity-low', label: i18n.severityLow || 'Worth a quick review' };
        }
        return { badge: 'contradictions-severity-pill contradictions-severity-medium', label: i18n.severityMedium || 'Review this carefully' };
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
})();
