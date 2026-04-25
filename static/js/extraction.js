/* Extraction page logic — visual field builder, presets, rich results, What Next tiles */
(function () {
    'use strict';

    // ── Config ──────────────────────────────────────────────────────────
    var cfgEl = document.getElementById('extraction-config');
    var cfg = {};
    try { cfg = JSON.parse(cfgEl.textContent); } catch (e) { /* noop */ }
    var projectId = cfg.projectId;
    var i18n = cfg.i18n || {};
    var reportAppendUrl = cfg.reportAppendUrl || '';
    if (!projectId) return;

    // ── DOM refs ────────────────────────────────────────────────────────
    var schemaListEl       = document.getElementById('schemaList');
    var runPanel           = document.getElementById('runPanel');
    var emptyState         = document.getElementById('emptyState');
    var activeSchemaNameEl = document.getElementById('activeSchemaName');
    var btnRunExtraction   = document.getElementById('btnRunExtraction');
    var extractProgress    = document.getElementById('extractProgress');
    var extractProgressMsg = document.getElementById('extractProgressMsg');
    var extractEta         = document.getElementById('extractEta');
    var resultsArea        = document.getElementById('resultsArea');
    var btnCreateSchema    = document.getElementById('btnCreateSchema');
    var btnExportCSV       = document.getElementById('btnExportCSV');
    var btnInsertReport    = document.getElementById('btnInsertReport');
    var resultsCount       = document.getElementById('resultsCount');
    var docSelectorEl      = document.getElementById('docSelector');
    var whatNextPanel      = document.getElementById('whatNextPanel');
    var statsBanner        = document.getElementById('extractionStatsBanner');
    var runFieldCallout    = document.getElementById('runFieldCallout');
    var runFieldList       = document.getElementById('runFieldList');
    var btnExportCSVTile   = document.getElementById('btnExportCSVTile');
    var fieldBuilderEl     = document.getElementById('fieldBuilder');
    var fieldBuilderEmpty  = document.getElementById('fieldBuilderEmpty');
    var schemaFieldsHidden = document.getElementById('schemaFields');

    var activeSchemaId = null;
    var activeSchemaFields = [];   // [{field, type}]
    var docSelector = null;
    var docNameMap = {};           // doc_id → doc_name
    var supportingSourcesPanelEl = document.getElementById('extractionSupportingSources');
    var supportingSourcesPanel = window.ProjectSupportingSources && supportingSourcesPanelEl
        ? window.ProjectSupportingSources.create(supportingSourcesPanelEl, {
            documentUrlTemplate: '/researcher/projects/' + projectId + '/documents/__DOC_ID__?source_view=answer',
            title: 'Files used to fill this data table',
            intro: 'These project files supported the latest data table collection run on this page.',
        })
        : null;

    // ── Preset templates ────────────────────────────────────────────────
    var PRESETS = {
        literature: {
            name: 'Literature Review',
            fields: [
                {field: 'Author', type: 'string'},
                {field: 'Year', type: 'number'},
                {field: 'Title', type: 'string'},
                {field: 'Journal', type: 'string'},
                {field: 'Sample Size', type: 'number'},
                {field: 'Key Findings', type: 'string'},
                {field: 'Methodology', type: 'string'}
            ]
        },
        clinical: {
            name: 'Clinical Study',
            fields: [
                {field: 'Study Design', type: 'string'},
                {field: 'Population', type: 'string'},
                {field: 'Intervention', type: 'string'},
                {field: 'Control', type: 'string'},
                {field: 'Outcome Measure', type: 'string'},
                {field: 'Result', type: 'string'},
                {field: 'Adverse Effects', type: 'string'}
            ]
        },
        survey: {
            name: 'Survey Analysis',
            fields: [
                {field: 'Survey Name', type: 'string'},
                {field: 'Respondents', type: 'number'},
                {field: 'Question', type: 'string'},
                {field: 'Response Options', type: 'string'},
                {field: 'Key Finding', type: 'string'}
            ]
        },
        general: {
            name: 'General Data',
            fields: [
                {field: 'Topic', type: 'string'},
                {field: 'Source', type: 'string'},
                {field: 'Date', type: 'string'},
                {field: 'Summary', type: 'string'},
                {field: 'Notes', type: 'string'}
            ]
        }
    };

    // Bind preset buttons
    document.querySelectorAll('.preset-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var preset = PRESETS[btn.dataset.preset];
            if (!preset) return;
            document.getElementById('schemaName').value = preset.name;
            setFieldBuilderRows(preset.fields);
        });
    });

    // ── Field builder ────────────────────────────────────────────────────
    function setFieldBuilderRows(fields) {
        if (fieldBuilderEl) {
            fieldBuilderEl.querySelectorAll('.field-row').forEach(function (r) { r.remove(); });
        }
        fields.forEach(function (f) { addFieldRow(f.field, f.type); });
        syncFieldsHidden();
    }

    function addFieldRow(fieldName, fieldType) {
        if (!fieldBuilderEl) return;
        if (fieldBuilderEmpty) fieldBuilderEmpty.hidden = true;
        var row = document.createElement('div');
        row.className = 'field-row extraction-field-row';
        row.innerHTML =
            '<input type="text" class="form-control form-control-sm extraction-field-name-input field-name"' +
                ' placeholder="Field name" value="' + escapeAttr(fieldName || '') + '">' +
            '<select class="form-select form-select-sm field-type extraction-field-type-select">' +
                '<option value="string"'  + (fieldType === 'string'  ? ' selected' : '') + '>Text</option>' +
                '<option value="number"'  + (fieldType === 'number'  ? ' selected' : '') + '>Number</option>' +
                '<option value="date"'    + (fieldType === 'date'    ? ' selected' : '') + '>Date</option>' +
                '<option value="boolean"' + (fieldType === 'boolean' ? ' selected' : '') + '>Yes/No</option>' +
            '</select>' +
            '<button type="button" class="remove-field-btn extraction-field-remove-button" tabindex="-1" aria-label="Remove field">' +
                '<i class="bi bi-x" aria-hidden="true"></i></button>';

        row.querySelector('.remove-field-btn').addEventListener('click', function () {
            row.remove();
            if (fieldBuilderEl && !fieldBuilderEl.querySelectorAll('.field-row').length) {
                if (fieldBuilderEmpty) fieldBuilderEmpty.hidden = false;
            }
            syncFieldsHidden();
        });
        row.querySelector('.field-name').addEventListener('input', syncFieldsHidden);
        row.querySelector('select').addEventListener('change', syncFieldsHidden);

        fieldBuilderEl.appendChild(row);
        syncFieldsHidden();
    }

    function syncFieldsHidden() {
        var fields = [];
        if (fieldBuilderEl) {
            fieldBuilderEl.querySelectorAll('.field-row').forEach(function (row) {
                var name = row.querySelector('.field-name').value.trim();
                var type = row.querySelector('select').value;
                if (name) fields.push({field: name, type: type});
            });
        }
        activeSchemaFields = fields;
        if (schemaFieldsHidden) schemaFieldsHidden.value = JSON.stringify(fields);
    }

    var btnAddField = document.getElementById('btnAddField');
    if (btnAddField) {
        btnAddField.addEventListener('click', function () { addFieldRow('', 'string'); });
    }

    // ── Document selector ─────────────────────────────────────────────────
    if (docSelectorEl && window.DocumentSelector) {
        docSelector = new DocumentSelector(docSelectorEl, projectId);
        docSelector.load();
    }

    function showMessage(message) {
        if (!message) {
            return;
        }

        window.beepUI.notify(message);
    }

    // ── Fetch document name map ───────────────────────────────────────────
    fetch('/projects/' + projectId + '/documents')
        .then(function (r) { return r.json(); })
        .then(function (j) {
            (j.documents || []).forEach(function (d) {
                docNameMap[d.id] = d.name || ('Doc #' + d.id);
            });
        })
        .catch(function () { /* noop */ });

    // ── Load schemas ──────────────────────────────────────────────────────
    async function loadSchemas() {
        try {
            var r = await fetch('/projects/' + projectId + '/extraction/schemas');
            var j = await r.json();
            renderSchemas(j.schemas || []);
        } catch (e) {
            if (schemaListEl) {
                schemaListEl.innerHTML = '<div class="extraction-schema-feedback">' +
                    escapeHtml(i18n.loadFailed || 'This section could not be loaded right now.') +
                    '</div>';
            }
        }
    }

    function renderSchemas(schemas) {
        if (!schemaListEl) return;
        if (!schemas.length) {
            schemaListEl.innerHTML =
                '<div class="extraction-schema-empty-state">' +
                '<i class="bi bi-inbox extraction-schema-empty-state-icon" aria-hidden="true"></i>' +
                (i18n.noTemplatesYet || 'No saved tables yet. Create one above.') + '</div>';
            return;
        }
        var html = '';
        schemas.forEach(function (s) {
            var active = s.id === activeSchemaId ? ' extraction-schema-item--active' : '';
            var meta = [];
            if (s.run_count != null) {
                meta.push(
                    '<span class="extraction-schema-meta-item">' +
                    '<i class="bi bi-cpu extraction-schema-meta-icon" aria-hidden="true"></i>' +
                    s.run_count + ' runs</span>'
                );
            }
            if (s.doc_count != null) {
                meta.push(
                    '<span class="extraction-schema-meta-item">' +
                    '<i class="bi bi-file-earmark extraction-schema-meta-icon" aria-hidden="true"></i>' +
                    s.doc_count + ' docs</span>'
                );
            }
            var metaHtml = meta.length
                ? '<span class="extraction-schema-meta">' + meta.join('<span class="extraction-schema-meta-separator">&middot;</span>') + '</span>'
                : '';
            html +=
                '<div class="extraction-schema-item' + active + '">' +
                '<button type="button" class="schema-item extraction-schema-select"' +
                ' data-schema-id="' + s.id + '"' +
                ' data-schema-name="' + escapeAttr(s.name) + '"' +
                ' data-schema-fields="' + escapeAttr(JSON.stringify(s.fields || [])) + '">' +
                '<span class="extraction-schema-name"><i class="bi bi-layout-text-window extraction-schema-icon" aria-hidden="true"></i>' + escapeHtml(s.name) + '</span>' +
                metaHtml +
                '</button>' +
                '<button type="button" class="delete-schema-btn extraction-schema-delete-button"' +
                ' data-schema-id="' + s.id + '" title="Delete" aria-label="Delete schema"><i class="bi bi-trash" aria-hidden="true"></i></button>' +
                '</div>';
        });
        schemaListEl.innerHTML = html;

        schemaListEl.querySelectorAll('.schema-item').forEach(function (item) {
            item.addEventListener('click', function (e) {
                var fields = [];
                try { fields = JSON.parse(item.dataset.schemaFields || '[]'); } catch (ex) { /* noop */ }
                selectSchema(parseInt(item.dataset.schemaId), item.dataset.schemaName, fields);
            });
        });

        schemaListEl.querySelectorAll('.delete-schema-btn').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (!confirm(i18n.deleteConfirm || 'Delete this template?')) return;
                deleteSchema(parseInt(btn.dataset.schemaId));
            });
        });
    }

    function selectSchema(schemaId, schemaName, fields) {
        activeSchemaId = schemaId;
        if (supportingSourcesPanel) supportingSourcesPanel.clear();
        if (emptyState)         emptyState.hidden = true;
        if (runPanel)           runPanel.hidden = false;
        if (activeSchemaNameEl) activeSchemaNameEl.textContent = schemaName;

        // 8b: field list callout in run panel
        if (runFieldCallout && runFieldList && fields && fields.length) {
            runFieldList.textContent = fields.map(function (f) { return f.field || f; }).join(' · ');
            runFieldCallout.hidden = false;
        } else if (runFieldCallout) {
            runFieldCallout.hidden = true;
        }

        schemaListEl.querySelectorAll('.extraction-schema-item').forEach(function (item) {
            var trigger = item.querySelector('.schema-item');
            item.classList.toggle('extraction-schema-item--active', trigger && parseInt(trigger.dataset.schemaId) === schemaId);
        });

        loadResults();
    }

    async function deleteSchema(schemaId) {
        try {
            var r = await fetch('/projects/' + projectId + '/extraction/schemas/' + schemaId, { method: 'DELETE' });
            if (r.ok) {
                if (activeSchemaId === schemaId) {
                    activeSchemaId = null;
                    if (runPanel)    runPanel.hidden = true;
                    if (emptyState)  emptyState.hidden = false;
                    showPostResultsUI(false);
                }
                loadSchemas();
            }
        } catch (e) { /* noop */ }
    }

    // ── Create schema ─────────────────────────────────────────────────────
    if (btnCreateSchema) {
        btnCreateSchema.addEventListener('click', async function () {
            var name   = document.getElementById('schemaName').value.trim();
            var fields = schemaFieldsHidden ? schemaFieldsHidden.value.trim() : '[]';
            if (!name)                      { showMessage(i18n.noNameAlert   || 'Enter a name for this table.'); return; }
            if (!fields || fields === '[]') { showMessage(i18n.noFieldsAlert || 'Add at least one column.');    return; }

            btnCreateSchema.disabled = true;
            try {
                var r = await fetch('/projects/' + projectId + '/extraction/schemas', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, schema_json: fields }),
                });
                if (r.ok) {
                    document.getElementById('schemaName').value = '';
                    if (fieldBuilderEl) fieldBuilderEl.querySelectorAll('.field-row').forEach(function (r) { r.remove(); });
                    if (fieldBuilderEmpty)  fieldBuilderEmpty.hidden = false;
                    if (schemaFieldsHidden) schemaFieldsHidden.value = '';
                    loadSchemas();
                } else {
                    var err = await r.json().catch(function () { return {}; });
                    showMessage(err.error || i18n.createTemplateError || 'The table could not be created.');
                }
            } catch (e) {
                showMessage((i18n.networkErrorPrefix || 'Network error: ') + e.message);
            } finally {
                btnCreateSchema.disabled = false;
            }
        });
    }

    // ── Run extraction ────────────────────────────────────────────────────
    if (btnRunExtraction) {
        btnRunExtraction.addEventListener('click', async function () {
            if (!activeSchemaId) return;
            var docIds = docSelector ? docSelector.getSelectedIds() : [];

            btnRunExtraction.disabled = true;
            if (extractProgress)    extractProgress.hidden = false;
            if (extractProgressMsg) extractProgressMsg.textContent = i18n.extracting || 'Reading your files and filling in the table...';

            var etaSeconds = 15;
            var etaInterval = setInterval(function () {
                if (etaSeconds > 0) {
                    etaSeconds--;
                    if (extractEta) extractEta.textContent = '~' + etaSeconds + 's';
                }
            }, 1000);

            try {
                var body = { schema_id: activeSchemaId };
                if (docIds.length === 1)    body.document_id  = docIds[0];
                else if (docIds.length > 1) body.document_ids = docIds;

                var r = await fetch('/projects/' + projectId + '/extract', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                var j = await r.json();
                if (!r.ok) {
                    throw new Error(j.error || j.message || (i18n.runErrorPrefix || 'Could not complete data collection.'));
                }
                if (supportingSourcesPanel) {
                    supportingSourcesPanel.render(collectSupportingSources(j.results || []));
                }
                showMessage(j.message || i18n.runCompleted || 'Data collection is complete.');
                loadResults();
            } catch (e) {
                showMessage((i18n.runErrorPrefix || 'Could not complete data collection: ') + e.message);
            } finally {
                clearInterval(etaInterval);
                btnRunExtraction.disabled = false;
                if (extractProgress) extractProgress.hidden = true;
                if (extractEta)      extractEta.textContent = '';
            }
        });
    }

    // ── Load results ──────────────────────────────────────────────────────
    async function loadResults() {
        if (!resultsArea) return;
        try {
            var r = await fetch('/projects/' + projectId + '/extractions');
            var j = await r.json();
            var results = (j.results || []).filter(function (res) {
                return res.schema_id === activeSchemaId;
            });
            renderResults(results);
        } catch (e) {
            resultsArea.innerHTML = '<div class="extraction-results-message">' +
                escapeHtml(i18n.resultsLoadFailed || 'The saved results could not be loaded.') +
                '</div>';
        }
    }

    function showPostResultsUI(hasResults) {
        if (btnInsertReport) btnInsertReport.hidden = !hasResults;
        if (btnExportCSV)    btnExportCSV.hidden = !hasResults;
        if (statsBanner)     statsBanner.hidden = !hasResults;
        if (whatNextPanel)   whatNextPanel.hidden = !hasResults;
        if (resultsCount) {
            resultsCount.textContent = (window._extractionResults || []).length;
            resultsCount.hidden = !hasResults;
        }
    }

    function renderResults(results) {
        if (!results.length) {
            resultsArea.innerHTML =
                '<div class="extraction-results-empty-state">' +
                '<i class="bi bi-inbox extraction-results-empty-icon" aria-hidden="true"></i>' +
                '<p class="extraction-results-empty-copy">' +
                escapeHtml(i18n.resultsEmpty || 'No results yet. Start data collection to see a filled table here.') +
                '</p></div>';
            showPostResultsUI(false);
            return;
        }

        var allKeys = new Set();
        results.forEach(function (res) {
            var data = {};
            try { data = JSON.parse(res.data_json || '{}'); } catch (e) { /* noop */ }
            res._parsed = data;
            if (typeof data === 'object' && !Array.isArray(data)) {
                Object.keys(data).forEach(function (k) { allKeys.add(k); });
            }
        });
        var keys = Array.from(allKeys);

        var html;
        if (!keys.length) {
            // Fallback: raw display
            html = '<div class="table-responsive"><table class="extraction-results-table">' +
                '<thead class="extraction-results-table-head"><tr><th>Document</th><th>Data</th></tr></thead><tbody>';
            results.forEach(function (res) {
                var docName = docNameMap[res.document_id] || ('Doc #' + (res.document_id || '—'));
                html += '<tr><td>' + escapeHtml(docName) + '</td>' +
                    '<td><pre class="extraction-results-raw">' + escapeHtml(res.data_json) + '</pre></td></tr>';
            });
            html += '</tbody></table></div>';
        } else {
            // 9b: document name (linked) instead of raw ID
            html = '<div class="table-responsive">' +
                '<table class="extraction-results-table" id="extractionResultsTable">' +
                '<thead class="extraction-results-table-head"><tr><th>Document</th>';
            keys.forEach(function (k) { html += '<th>' + escapeHtml(k) + '</th>'; });
            html += '</tr></thead><tbody>';

            results.forEach(function (res) {
                var docId   = res.document_id;
                var docName = docNameMap[docId] || ('Doc #' + (docId || '—'));
                html += '<tr><td>' +
                    '<a href="/researcher/projects/' + projectId + '/documents/' + docId + '?source_view=answer" class="extraction-results-document-link">' +
                    '<i class="bi bi-file-earmark-text extraction-results-document-icon" aria-hidden="true"></i>' +
                    escapeHtml(docName) + '</a></td>';
                keys.forEach(function (k) {
                    var val = res._parsed[k];
                    if (val === undefined || val === null) val = '—';
                    else if (typeof val === 'object') val = JSON.stringify(val);
                    else val = String(val);
                    html += '<td>' + escapeHtml(val) + '</td>';
                });
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }

        resultsArea.innerHTML = html;
        window._extractionResults = results;
        window._extractionKeys    = keys;
        showPostResultsUI(true);
    }

    function collectSupportingSources(results) {
        var collected = [];
        results.forEach(function (result) {
            var itemSources = Array.isArray(result.supporting_sources) ? result.supporting_sources : [];
            itemSources.forEach(function (source) {
                collected.push(source);
            });
        });
        return collected;
    }

    // ── Insert results into Report (6a) ───────────────────────────────────
    if (btnInsertReport) {
        btnInsertReport.addEventListener('click', function () {
            var results = window._extractionResults || [];
            var keys    = window._extractionKeys    || [];
            if (!results.length) return;

            var md = '## Extraction Results\n\n';
            md += '| Document | ' + keys.join(' | ') + ' |\n';
            md += '|---|' + keys.map(function () { return '---'; }).join('|') + '|\n';
            results.forEach(function (res) {
                var docName = docNameMap[res.document_id] || ('Doc #' + (res.document_id || '—'));
                var cells = [docName].concat(keys.map(function (k) {
                    var v = res._parsed ? res._parsed[k] : '';
                    if (v === undefined || v === null) v = '';
                    else if (typeof v === 'object') v = JSON.stringify(v);
                    return String(v).replace(/\|/g, '\\|');
                }));
                md += '| ' + cells.join(' | ') + ' |\n';
            });

            localStorage.setItem('report_pending_' + projectId, md);
            if (reportAppendUrl) {
                fetch(reportAppendUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: md })
                }).catch(function () { /* noop */ });
            }
            showMessage(i18n.insertReportDone || 'Added to Report');
        });
    }

    // ── CSV export ────────────────────────────────────────────────────────
    function doExportCSV() {
        var results = window._extractionResults || [];
        var keys    = window._extractionKeys    || [];
        if (!results.length) return;

        var csv = 'Document,' + keys.map(csvEscape).join(',') + '\n';
        results.forEach(function (res) {
            var docName = docNameMap[res.document_id] || (res.document_id || '');
            var row = [docName];
            keys.forEach(function (k) {
                var val = res._parsed ? res._parsed[k] : '';
                if (val === undefined || val === null) val = '';
                else if (typeof val === 'object') val = JSON.stringify(val);
                row.push(val);
            });
            csv += row.map(csvEscape).join(',') + '\n';
        });

        var blob = new Blob([csv], { type: 'text/csv' });
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement('a');
        a.href     = url;
        a.download = 'extraction_results.csv';
        a.click();
        URL.revokeObjectURL(url);
    }

    if (btnExportCSV)     btnExportCSV.addEventListener('click',     doExportCSV);
    if (btnExportCSVTile) btnExportCSVTile.addEventListener('click', doExportCSV);

    // ── Helpers ───────────────────────────────────────────────────────────
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

    // ── Init ──────────────────────────────────────────────────────────────
    loadSchemas();
})();
