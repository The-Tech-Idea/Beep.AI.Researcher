/* Retention policy page — full rewrite with affected docs list */
(function () {
    'use strict';

    var cfgEl = document.getElementById('retention-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var retentionUrl = cfg.retentionUrl;
    var documentsUrl = cfg.documentsUrl;
    var strings = cfg.strings || {};
    if (!projectId || !retentionUrl || !documentsUrl) return;

    var input = document.getElementById('retentionDays');
    var actionSelect = document.getElementById('retentionAction');
    var btn = document.getElementById('btnSave');
    var summaryText = document.getElementById('policySummaryText');
    var affectedList = document.getElementById('affectedList');
    var affectedCount = document.getElementById('affectedCount');
    var deleteWarning = document.getElementById('deleteWarning');

    function syncDeleteWarning() {
        if (!actionSelect || !deleteWarning) return;
        deleteWarning.hidden = actionSelect.value !== 'delete';
    }

    // ── Load current policy ─────────────────────────────────────────────
    async function loadPolicy() {
        try {
            var r = await fetch(retentionUrl);
            var j = await r.json();
            if (input) input.value = j.retention_days || '';
            if (actionSelect && j.action) actionSelect.value = j.action;
            updateSummary(j.retention_days, j.action || 'flag');
            loadAffectedDocs(j.retention_days);
            syncDeleteWarning();
        } catch (e) {
            if (summaryText) summaryText.textContent = strings.noPolicyConfigured || 'No policy configured.';
        }
    }

    // ── Update summary text ─────────────────────────────────────────────
    function updateSummary(days, action) {
        if (!summaryText) return;
        if (!days || days <= 0) {
            summaryText.textContent = strings.noRetentionLimit || 'No retention limit — all documents are kept indefinitely.';
        } else {
            var actionLabel = action === 'delete'
                ? (strings.actionDeleted || 'deleted')
                : action === 'archive'
                    ? (strings.actionArchived || 'archived')
                    : (strings.actionFlagged || 'flagged for review');
            summaryText.textContent = 'Documents older than ' + days + ' day' + (days > 1 ? 's' : '') +
                ' will be ' + actionLabel + '.';
        }
    }

    // ── Load affected documents ─────────────────────────────────────────
    async function loadAffectedDocs(retentionDays) {
        if (!affectedList) return;
        if (!retentionDays || retentionDays <= 0) {
            affectedList.innerHTML = '<div class="retention-message retention-message--muted py-4"><i class="bi bi-check-circle retention-message--success me-1"></i>' +
                (strings.affectedNoneWithNoLimit || 'No retention limit set — no documents affected.') + '</div>';
            if (affectedCount) affectedCount.textContent = '0';
            return;
        }

        try {
            var r = await fetch(documentsUrl);
            var j = await r.json();
            var docs = j.documents || [];
            var cutoff = new Date();
            cutoff.setDate(cutoff.getDate() - retentionDays);

            var affected = docs.filter(function (d) {
                var uploadDate = new Date(d.uploaded_at || d.created_at || '');
                return uploadDate < cutoff;
            });

            if (affectedCount) affectedCount.textContent = affected.length;

            if (!affected.length) {
                affectedList.innerHTML = '<div class="retention-message retention-message--success py-4"><i class="bi bi-check-circle me-1"></i>' +
                    (strings.affectedNoneWithinPolicy || 'No documents exceed the retention period.') + '</div>';
                return;
            }

            affectedList.innerHTML = affected.map(function (d) {
                var date = (d.uploaded_at || d.created_at || '').slice(0, 10);
                var daysOld = Math.floor((Date.now() - new Date(d.uploaded_at || d.created_at).getTime()) / 86400000);
                return '<div class="list-group-item retention-affected-row">' +
                    '<div><i class="bi bi-file-earmark-text retention-document-icon me-2"></i>' +
                    '<span>' + escapeHtml(d.filename) + '</span></div>' +
                    '<div class="retention-affected-meta">' +
                    '<small class="retention-document-date">' + date + '</small>' +
                    '<span class="retention-age-badge">' + daysOld + (strings.daysOldSuffix || 'd old') + '</span>' +
                    '</div></div>';
            }).join('');
        } catch (e) {
            affectedList.innerHTML = '<div class="retention-message retention-message--error py-3">' +
                (strings.affectedLoadFailed || 'Failed to load documents.') + '</div>';
        }
    }

    // ── Save policy ─────────────────────────────────────────────────────
    if (btn) {
        btn.addEventListener('click', async function () {
            var days = input.value ? parseInt(input.value) : null;
            var action = actionSelect ? actionSelect.value : 'flag';
            btn.disabled = true;
            try {
                var r = await fetch(retentionUrl, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ retention_days: days, action: action })
                });
                if (r.ok) {
                    window.beepUI.notify(strings.policySaved || 'Retention policy saved.', { variant: 'success' });
                    updateSummary(days, action);
                    loadAffectedDocs(days);
                    syncDeleteWarning();
                } else {
                    window.beepUI.notify(strings.policySaveFailed || 'Failed to save retention policy.', { variant: 'danger' });
                }
            } finally {
                btn.disabled = false;
            }
        });
    }

    if (actionSelect) {
        actionSelect.addEventListener('change', syncDeleteWarning);
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // Init
    loadPolicy();
})();
