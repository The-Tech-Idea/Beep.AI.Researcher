/* Statistics page — full rewrite: summary cards, charts, data source stats */
(function () {
    'use strict';

    var cfgEl = document.getElementById('stats-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var strings = cfg.strings || {};
    var chartColors = cfg.chartColors || {};
    if (!projectId) return;

    function resolveCssColor(value, fallback) {
        if (!value) {
            return fallback;
        }

        if (!value.startsWith('var(')) {
            return value;
        }

        var probe = document.createElement('span');
        probe.hidden = true;
        probe.style.color = value;
        document.body.appendChild(probe);
        var resolved = window.getComputedStyle(probe).color;
        probe.remove();
        return resolved || fallback;
    }

    function resolvePalette(values, fallbackValues) {
        return (values && values.length ? values : fallbackValues).map(function (value, index) {
            return resolveCssColor(value, fallbackValues[index] || fallbackValues[0]);
        });
    }

    // ── Summary stats ───────────────────────────────────────────────────
    async function loadSummary() {
        try {
            // Documents
            var docRes = await fetch('/projects/' + projectId + '/documents');
            var docData = await docRes.json();
            var docs = docData.documents || [];
            var el = document.getElementById('statDocs');
            if (el) el.textContent = docs.length;

            // Flashcards
            var fcRes = await fetch('/projects/' + projectId + '/flashcards');
            var fcData = await fcRes.json();
            var fcEl = document.getElementById('statFlashcards');
            if (fcEl) fcEl.textContent = (fcData.flashcards || []).length;

            // Quizzes
            var qzRes = await fetch('/projects/' + projectId + '/quizzes');
            var qzData = await qzRes.json();
            var qzEl = document.getElementById('statQuizzes');
            if (qzEl) qzEl.textContent = (qzData.quizzes || []).length;

            // Codes
            var cRes = await fetch('/projects/' + projectId + '/codes');
            var cData = await cRes.json();
            var cEl = document.getElementById('statCodes');
            if (cEl) cEl.textContent = (cData.codes || []).length;

            // Render charts
            renderDocTypeChart(docs);
            renderActivityChart(docs);
        } catch (e) {
            /* Silently handle — cards will show — */
        }
    }

    // ── Doc type pie chart ──────────────────────────────────────────────
    function renderDocTypeChart(docs) {
        var canvas = document.getElementById('chartDocTypes');
        if (!canvas || typeof Chart === 'undefined') return;

        var types = {};
        docs.forEach(function (d) {
            var ext = (d.filename || '').split('.').pop().toUpperCase() || (strings.unknownType || 'Unknown');
            types[ext] = (types[ext] || 0) + 1;
        });

        var labels = Object.keys(types);
        var data = Object.values(types);
        var colors = resolvePalette(chartColors.docTypes, [
            '#6366f1', '#a855f7', '#d946ef', '#ec4899', '#f97316', '#22d3ee', '#38f9d7', '#43e97b'
        ]);

        new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 0,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12 } }
                }
            }
        });
    }

    // ── Activity timeline bar chart ─────────────────────────────────────
    function renderActivityChart(docs) {
        var canvas = document.getElementById('chartActivity');
        if (!canvas || typeof Chart === 'undefined') return;

        var months = {};
        docs.forEach(function (d) {
            var date = d.uploaded_at || d.created_at || '';
            var month = date ? date.slice(0, 7) : 'Unknown';
            months[month] = (months[month] || 0) + 1;
        });

        var sortedMonths = Object.keys(months).sort();
        var data = sortedMonths.map(function (m) { return months[m]; });
        var activityBarColor = resolveCssColor(chartColors.activityBar, 'rgba(99, 102, 241, 0.6)');

        new Chart(canvas.getContext('2d'), {
            type: 'bar',
            data: {
                labels: sortedMonths,
                datasets: [{
                    label: strings.docTypeLabel || 'Documents Added',
                    data: data,
                    backgroundColor: activityBarColor,
                    borderRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    // ── Data source describe & crosstab ─────────────────────────────────
    var sourceSelect = document.getElementById('sourceSelect');
    var btnDescribe = document.getElementById('btnDescribe');
    var btnCrosstab = document.getElementById('btnCrosstab');

    function loadColumns() {
        var sid = sourceSelect.value;
        if (!sid) return;
        fetch('/projects/' + projectId + '/data/sources/' + sid)
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var cols = j.columns || [];
                var opts = cols.map(function (c) { return '<option value="' + c + '">' + c + '</option>'; }).join('');
                var describeCols = document.getElementById('describeCols');
                describeCols.innerHTML = '<label class="form-label small">' + (strings.columnsLabel || 'Columns') +
                    '</label><input type="text" id="describeColsInput" class="form-control form-control-sm" placeholder="col1,col2">';
                document.getElementById('rowCol').innerHTML = '<option value="">' + (strings.selectColumn || 'Select') + '</option>' + opts;
                document.getElementById('colCol').innerHTML = '<option value="">' + (strings.selectColumn || 'Select') + '</option>' + opts;
            })
            .catch(function () { /* silently fail — columns will be empty */ });
    }

    if (sourceSelect) {
        sourceSelect.addEventListener('change', loadColumns);
    }

    if (btnDescribe) {
        btnDescribe.addEventListener('click', async function () {
            var sid = sourceSelect.value;
            var describeResults = document.getElementById('describeResults');
            if (!sid) { describeResults.textContent = strings.selectSource || 'Select a data source.'; return; }
            var colInput = document.getElementById('describeColsInput');
            var cols = colInput ? colInput.value.split(',').map(function (s) { return s.trim(); }).filter(Boolean) : [];
            try {
            var r = await fetch('/projects/' + projectId + '/stats/describe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_id: parseInt(sid), columns: cols })
            });
            var j = await r.json();
            describeResults.textContent = JSON.stringify(j.stats || {}, null, 2);
            } catch (e) {
                describeResults.textContent = strings.describeFailed || 'Describe failed: ' + e.message;
            }
        });
    }

    if (btnCrosstab) {
        btnCrosstab.addEventListener('click', async function () {
            var sid = sourceSelect.value;
            var row = document.getElementById('rowCol').value;
            var col = document.getElementById('colCol').value;
            var crosstabResults = document.getElementById('crosstabResults');
            if (!sid || !row || !col) { crosstabResults.textContent = strings.selectBoth || 'Select source and both columns.'; return; }
            try {
            var r = await fetch('/projects/' + projectId + '/stats/crosstab', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source_id: parseInt(sid), row_column: row, column_column: col })
            });
            var j = await r.json();
            crosstabResults.textContent = JSON.stringify(j, null, 2);
            } catch (e) {
                crosstabResults.textContent = strings.crosstabFailed || 'Crosstab failed: ' + e.message;
            }
        });
    }

    if (cfg.hasSources) loadColumns();

    // Init
    loadSummary();
})();
