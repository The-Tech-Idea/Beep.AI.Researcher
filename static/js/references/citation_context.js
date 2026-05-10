/**
 * Phase 6 — Citation Context UI.
 * Shows how a reference is cited in other papers (polarity analysis).
 * All CSS uses design-system tokens. All strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var refId = window.location.pathname.match(/\/references\/(\d+)/);
    refId = refId ? refId[1] : null;
    if (!refId) return;

    var contextsList = document.getElementById('contextsList');
    var refreshBtn = document.getElementById('btnRefreshContext');

    if (!contextsList) return;

    loadContexts();

    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>' + t('references.citation_context.refreshing');
            fetch('/references/' + refId + '/citation-context/refresh', { method: 'POST' })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>' + t('references.citation_context.refresh');
                    loadContexts();
                })
                .catch(function (e) {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>' + t('references.citation_context.refresh');
                    showToast(t('references.citation_context.error.refresh_failed') + e.message, 'error');
                });
        });
    }

    function loadContexts() {
        fetch('/references/' + refId + '/citation-context')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var summary = data.summary || {};
                document.getElementById('supportingCount').textContent = summary.supporting || 0;
                document.getElementById('contradictingCount').textContent = summary.contradicting || 0;
                document.getElementById('mentioningCount').textContent = summary.mentioning || 0;

                contextsList.innerHTML = '';
                var contexts = data.contexts || [];
                if (contexts.length === 0) {
                    contextsList.innerHTML = '<div class="text-center py-5 text-muted"><i class="bi bi-chat-square-text fs-1 mb-3"></i><p>' + t('references.citation_context.empty_state') + '</p></div>';
                    return;
                }

                contexts.forEach(function (ctx) {
                    var item = document.createElement('div');
                    item.className = 'references-list__item';
                    var stanceHtml = '<span class="citation-context-stance" data-stance="' + (ctx.polarity || 'mentioning') + '"></span>';
                    item.innerHTML =
                        '<div class="references-list__content">' +
                            '<div class="references-list__title">' + esc(ctx.snippet || '') + '</div>' +
                            '<div class="references-list__meta">' +
                                (ctx.intent ? '<span class="badge bg-secondary me-1">' + esc(ctx.intent) + '</span>' : '') +
                                (ctx.citing_doi ? '<code class="small">' + esc(ctx.citing_doi) + '</code>' : '') +
                            '</div>' +
                        '</div>' +
                        '<div>' + stanceHtml + '</div>';
                    contextsList.appendChild(item);

                    var stanceSpan = item.querySelector('.citation-context-stance');
                    if (window.BEEP_COMPONENTS && window.BEEP_COMPONENTS.StanceBadge) {
                        new window.BEEP_COMPONENTS.StanceBadge(stanceSpan, ctx.polarity || 'mentioning');
                    } else {
                        stanceSpan.textContent = ctx.polarity || 'mentioning';
                    }
                });
            })
            .catch(function (e) {
                contextsList.innerHTML = '<div class="alert alert-danger">' + t('references.citation_context.error.load_failed') + e.message + '</div>';
            });
    }

    function esc(str) {
        var el = document.createElement('span');
        el.textContent = str || '';
        return el.innerHTML;
    }

    function showToast(msg, type) {
        var toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:9999;padding:0.75rem 1rem;border-radius:var(--radius-md);color:#fff;font-size:var(--text-sm);';
        toast.style.background = type === 'error' ? 'var(--color-error)' : 'var(--color-success)';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(function () { toast.style.opacity = '0'; setTimeout(function () { toast.remove(); }, 300); }, 3000);
    }
})();
