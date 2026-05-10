/**
 * Phase 6 Library Analytics UI.
 * All user-facing strings use window.BEEP_I18N translations.
 */
(function () {
    'use strict';

    var t = window.BEEP_I18N || function(k) { return k; };

    var loadingEl = document.getElementById('analyticsLoading');
    var contentEl = document.getElementById('analyticsContent');
    var topRefsBody = document.getElementById('topRefsBody');
    var growthChart = document.getElementById('growthChart');
    var exportBtn = document.getElementById('btnExportCSV');

    if (!loadingEl || !contentEl) return;

    fetch('/references/analytics/data')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            loadingEl.setAttribute('hidden', '');
            contentEl.removeAttribute('hidden');

            // Top references
            topRefsBody.innerHTML = '';
            (data.top_references || []).forEach(function (r, i) {
                var tr = document.createElement('tr');
                tr.innerHTML =
                    '<td class="text-muted">' + (i + 1) + '</td>' +
                '<td>' + esc(r.title || t('analytics.untitled')) + '</td>' +
                '<td class="small text-muted">' + esc(r.project_name || '') + '</td>' +
                '<td class="small text-muted">' + esc(r.doi || '—') + '</td>' +
                    '<td><span class="badge bg-info">' + r.usage_score + '</span></td>';
                topRefsBody.appendChild(tr);
            });

            // Simple growth bar chart using inline CSS
            if (growthChart) {
                var years = data.temporal_growth || [];
                var maxCount = 0;
                years.forEach(function (y) { if (y.count > maxCount) maxCount = y.count; });

                growthChart.innerHTML = '';
                var container = document.createElement('div');
                container.style.cssText = 'display:flex;align-items:flex-end;height:250px;gap:4px;padding:0 1rem;';

                years.forEach(function (y) {
                    var bar = document.createElement('div');
                    var h = maxCount > 0 ? Math.max(4, (y.count / maxCount) * 230) : 4;
                    bar.style.cssText = 'flex:1;background:var(--bs-info,#0dcaf0);border-radius:4px 4px 0 0;height:' + h + 'px;min-width:20px;position:relative;cursor:pointer;';
                    bar.title = y.year + ': ' + y.count + ' references';
                    bar.innerHTML = '<span style="position:absolute;top:-1.2rem;left:50%;transform:translateX(-50%);font-size:0.65rem;color:var(--bs-secondary-color);">' + y.count + '</span>';
                    bar.innerHTML += '<span style="position:absolute;bottom:-1.2rem;left:50%;transform:translateX(-50%);font-size:0.6rem;color:var(--bs-secondary-color);">' + y.year + '</span>';
                    container.appendChild(bar);
                });

                growthChart.appendChild(container);
            }
        })
        .catch(function (e) {
            loadingEl.innerHTML = '<div class="alert alert-danger">' + t('analytics.error.failed') + e.message + '</div>';
        });

    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            fetch('/references/analytics/data')
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var csv = t('analytics.csv.header') + '\n';
                    (data.top_references || []).forEach(function (r, i) {
                        csv += (i + 1) + ',"' + (r.title || '') + '","' + (r.project_name || '') + '","' + (r.doi || '') + '",' + r.usage_score + '\n';
                    });
                    var blob = new Blob([csv], { type: 'text/csv' });
                    var url = URL.createObjectURL(blob);
                    var a = document.createElement('a');
                    a.href = url;
                    a.download = 'library_analytics.csv';
                    a.click();
                    URL.revokeObjectURL(url);
                })
                .catch(function () {
                    showToast(t('analytics.error.export_failed') || 'Export failed', 'error');
                });
        });
    }

    function esc(str) { var el = document.createElement('span'); el.textContent = str || ''; return el.innerHTML; }
})();
