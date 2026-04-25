/* Coding matrix page — row/col totals, uncoded highlight, clickable cells, CSV export */
(function () {
    'use strict';

    var cfgEl = document.getElementById('matrix-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var i18n = cfg.i18n || {};
    if (!projectId) return;

    var thead      = document.getElementById('matrixHeader');
    var tbody      = document.getElementById('matrixBody');
    var btnRefresh = document.getElementById('btnRefreshMatrix');
    var btnExport  = document.getElementById('btnExportMatrixCSV');

    // Offcanvas excerpt panel
    var excerptPanel      = document.getElementById('excerptPanel');
    var excerptPanelBody  = document.getElementById('excerptPanelBody');
    var excerptPanelTitle = document.getElementById('excerptPanelTitle');
    var bsOffcanvas = null;
    if (excerptPanel && window.bootstrap) {
        bsOffcanvas = new bootstrap.Offcanvas(excerptPanel);
    }

    // Store last matrix data for export
    var lastRows = [], lastCols = [], lastMatrix = [];

    function loadMatrix() {
        tbody.innerHTML =
            '<tr><td class="matrix-loading-cell" colspan="50">' +
            '<div class="matrix-loading-indicator"><span class="matrix-loading-spinner" aria-hidden="true"></span>Loading\u2026</div></td></tr>';

        fetch('/projects/' + projectId + '/matrices')
            .then(function (r) { return r.json(); })
            .then(function (j) {
                lastRows   = j.rows    || [];
                lastCols   = j.columns || [];
                lastMatrix = j.matrix  || [];

                if (!lastRows.length || !lastCols.length) {
                    thead.innerHTML = '';
                    tbody.innerHTML =
                        '<tr><td class="matrix-empty-cell" colspan="50">' +
                        '<i class="bi bi-grid-3x3 matrix-empty-icon"></i>' +
                        (i18n.noData || 'Add documents and apply codes to see the matrix.') +
                        '</td></tr>';
                    return;
                }

                render(lastRows, lastCols, lastMatrix);
            })
            .catch(function () {
                tbody.innerHTML =
                    '<tr><td class="matrix-error-cell" colspan="50">Failed to load matrix.</td></tr>';
            });
    }

    function render(rows, cols, matrix) {
        // ── Header row ────────────────────────────────────────
        thead.innerHTML =
            '<tr class="matrix-header-row">' +
            '<th class="matrix-header-cell matrix-header-sticky">' +
            (i18n.document || 'Document') + '</th>' +
            cols.map(function (c) {
                return '<th class="matrix-header-cell small">' +
                    escapeHtml(c) + '</th>';
            }).join('') +
            '<th class="matrix-header-cell matrix-header-total">' +
            (i18n.total || 'Total') + '</th>' +
            '</tr>';

        // ── Body rows ─────────────────────────────────────────
        var colTotals = cols.map(function () { return 0; });

        var bodyHtml = rows.map(function (rowLabel, i) {
            var rowTotal = 0;
            var cells = cols.map(function (colLabel, j) {
                var count = (matrix[i] && matrix[i][j] !== undefined) ? matrix[i][j] : 0;
                if (count > 0) { rowTotal++; colTotals[j] += count; }
                var cls = 'matrix-cell';
                if (count > 0) {
                    cls += ' fw-bold is-clickable';
                    cls += count > 5 ? ' is-high' : count > 2 ? ' is-medium' : ' is-low';
                } else {
                    cls += ' is-empty';
                }
                return '<td class="' + cls + '"' +
                    (count > 0
                        ? ' data-row="' + i + '" data-col="' + j + '"' +
                          ' data-doc="' + escapeAttr(rowLabel) + '"' +
                          ' data-code="' + escapeAttr(colLabel) + '"'
                        : '') +
                    '>' + count + '</td>';
            });

            // 5d: Yellow row highlight for uncoded documents
            var rowClass = rowTotal === 0 ? ' class="matrix-row--uncoded"' : '';
            var uncodedBadge = rowTotal === 0
                ? '<span class="matrix-uncoded-badge" title="' +
                  escapeAttr(i18n.uncodedTitle || 'No codes applied') +
                  '"><i class="bi bi-exclamation-triangle"></i></span>'
                : '';
            var headerClass = rowTotal === 0 ? 'matrix-row-header is-uncoded' : 'matrix-row-header';

            return '<tr' + rowClass + '>' +
                '<th class="' + headerClass + '">' +
                '<i class="bi bi-file-earmark-text matrix-row-icon me-1"></i>' +
                escapeHtml(rowLabel) + uncodedBadge + '</th>' +
                cells.join('') +
                '<td class="matrix-total-cell">' + rowTotal + '</td>' +
                '</tr>';
        }).join('');

        // 5c: Totals row
        var grandTotal = colTotals.reduce(function (a, b) { return a + b; }, 0);
        bodyHtml +=
            '<tr class="matrix-totals-row">' +
            '<th class="matrix-row-header matrix-totals-header">' +
            (i18n.totalsRow || 'Totals') + '</th>' +
            colTotals.map(function (t) { return '<td class="matrix-cell">' + t + '</td>'; }).join('') +
            '<td class="matrix-total-cell">' + grandTotal + '</td>' +
            '</tr>';

        tbody.innerHTML = bodyHtml;

        // 5b: Clickable cells for excerpt panel
        tbody.querySelectorAll('.matrix-cell[data-doc]').forEach(function (cell) {
            cell.addEventListener('click', function () {
                openExcerptPanel(cell.dataset.doc, cell.dataset.code);
            });
        });
    }

    function openExcerptPanel(docName, codeName) {
        if (!bsOffcanvas) return;
        if (excerptPanelTitle) excerptPanelTitle.textContent = codeName + ' — ' + docName;
        if (excerptPanelBody) {
            excerptPanelBody.innerHTML =
                '<div class="matrix-loading-indicator matrix-excerpt-body"><span class="matrix-loading-spinner" aria-hidden="true"></span>' +
                (i18n.excerptLoading || 'Loading excerpts\u2026') + '</div>';
        }
        bsOffcanvas.show();

        fetch('/projects/' + projectId + '/codes?doc=' + encodeURIComponent(docName) + '&code=' + encodeURIComponent(codeName))
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var excerpts = j.excerpts || j.codes || [];
                if (!excerpts.length) {
                    excerptPanelBody.innerHTML =
                        '<p class="matrix-excerpt-body">' + (i18n.excerptEmpty || 'No excerpts found.') + '</p>';
                    return;
                }
                excerptPanelBody.innerHTML = excerpts.map(function (e) {
                    var text = typeof e === 'string' ? e : (e.text || e.excerpt || JSON.stringify(e));
                    return '<blockquote class="matrix-excerpt-quote">' +
                        '<p class="matrix-excerpt-text">' + escapeHtml(text) + '</p>' +
                        '</blockquote>';
                }).join('');
            })
            .catch(function () {
                excerptPanelBody.innerHTML =
                    '<p class="matrix-excerpt-body">' + (i18n.excerptEmpty || 'No excerpts available.') + '</p>';
            });
    }

    // 5e: CSV export
    function doExportCSV() {
        if (!lastRows.length || !lastCols.length) return;
        var csv = csvEscape(i18n.document || 'Document') + ',' +
            lastCols.map(csvEscape).join(',') + ',' + csvEscape(i18n.total || 'Total') + '\n';

        var colTotals = lastCols.map(function () { return 0; });
        lastRows.forEach(function (rowLabel, i) {
            var rowTotal = 0;
            var cells = lastCols.map(function (c, j) {
                var v = (lastMatrix[i] && lastMatrix[i][j] !== undefined) ? lastMatrix[i][j] : 0;
                if (v > 0) { rowTotal++; colTotals[j] += v; }
                return v;
            });
            csv += csvEscape(rowLabel) + ',' + cells.join(',') + ',' + rowTotal + '\n';
        });
        var grandTotal = colTotals.reduce(function (a, b) { return a + b; }, 0);
        csv += csvEscape(i18n.totalsRow || 'Totals') + ',' + colTotals.join(',') + ',' + grandTotal + '\n';

        var blob = new Blob([csv], { type: 'text/csv' });
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement('a');
        a.href     = url;
        a.download = i18n.exportFilename || 'coding_matrix.csv';
        a.click();
        URL.revokeObjectURL(url);
    }

    if (btnExport)  btnExport.addEventListener('click', doExportCSV);
    if (btnRefresh) btnRefresh.addEventListener('click', loadMatrix);

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function csvEscape(val) {
        var s = String(val || '');
        if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) {
            return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    }

    loadMatrix();
})();
