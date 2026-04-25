(function () {
    'use strict';

    function getConfig() {
        var element = document.getElementById('references-page-config');
        if (!element) {
            return null;
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            console.error('Failed to parse references page config.', error);
            return null;
        }
    }

    function buildUrl(template, values) {
        return Object.keys(values).reduce(function (url, key) {
            return url.replace('__' + key + '__', values[key]);
        }, template);
    }

    function createStatus(message, tone, iconClass) {
        var status = document.createElement('span');
        status.className = 'references-page-status references-page-status--' + tone;

        if (iconClass) {
            var icon = document.createElement('i');
            icon.className = 'bi ' + iconClass + ' references-page-status__icon';
            icon.setAttribute('aria-hidden', 'true');
            status.appendChild(icon);
        }

        var text = document.createElement('span');
        text.textContent = message;
        status.appendChild(text);
        return status;
    }

    function setStatusContent(container, message, tone, iconClass) {
        container.replaceChildren(createStatus(message, tone, iconClass));
    }

    function setBatchSummary(container, labels, counts) {
        var entries = [
            { key: 'total', label: labels.total, value: counts.total },
            { key: 'valid', label: labels.valid, value: counts.valid },
            { key: 'invalid', label: labels.invalid, value: counts.invalid },
            { key: 'skipped', label: labels.skipped, value: counts.skipped }
        ];

        container.replaceChildren();
        entries.forEach(function (entry) {
            var chip = document.createElement('span');
            chip.className = 'references-page-batch-chip references-page-batch-chip--' + entry.key;
            chip.textContent = entry.label + ': ' + entry.value;
            container.appendChild(chip);
        });
    }

    async function bindExport(config) {
        var projectSelect = document.getElementById('referenceExportProject');
        var styleSelect = document.getElementById('referenceExportStyle');
        var exportButton = document.getElementById('referenceExportBtn');
        if (!projectSelect || !exportButton) {
            return;
        }

        exportButton.addEventListener('click', function () {
            var projectId = projectSelect.value;
            var style = styleSelect ? styleSelect.value : 'apa';
            if (!projectId) {
                return;
            }

            window.location.href = buildUrl(config.exportUrlTemplate, {
                PROJECT_ID: projectId,
                STYLE: style
            });
        });
    }

    function bindImport(config) {
        var importButton = document.getElementById('referenceImportBtn');
        var importProject = document.getElementById('referenceImportProject');
        var importFormat = document.getElementById('referenceImportFormat');
        var importContent = document.getElementById('referenceImportContent');
        var importFile = document.getElementById('referenceImportFile');
        var importStatus = document.getElementById('referenceImportStatus');
        if (!importButton || !importProject || !importFormat || !importContent || !importStatus) {
            return;
        }

        importButton.addEventListener('click', async function () {
            var projectId = importProject.value;
            if (!projectId) {
                return;
            }

            var formData = new FormData();
            formData.append('format', importFormat.value);
            formData.append('content', importContent.value || '');
            if (importFile && importFile.files && importFile.files.length > 0) {
                formData.append('file', importFile.files[0]);
            }

            setStatusContent(importStatus, importButton.dataset.importing || 'Importing...', 'muted');
            try {
                var response = await fetch(buildUrl(config.importUrlTemplate, { PROJECT_ID: projectId }), {
                    method: 'POST',
                    body: formData
                });
                var data = await response.json();
                if (!response.ok) {
                    setStatusContent(importStatus, data.error || (importButton.dataset.failed || 'Import failed'), 'danger');
                    return;
                }

                setStatusContent(
                    importStatus,
                    (config.createdLabel || 'Created') + ': ' + (data.created || 0) +
                    ', ' + (config.skippedLabel || 'Skipped') + ': ' + (data.skipped || 0),
                    'success',
                    'bi-check-circle'
                );
                window.setTimeout(function () {
                    window.location.reload();
                }, 500);
            } catch (error) {
                setStatusContent(importStatus, importButton.dataset.failed || 'Import failed', 'danger', 'bi-x-circle');
            }
        });
    }

    function bindSingleDoiValidation(config) {
        var doiInput = document.getElementById('doiInput');
        var validateButton = document.getElementById('btnValidateDoi');
        var projectSelect = document.getElementById('referenceExportProject');
        var result = document.getElementById('doiResult');
        if (!doiInput || !validateButton || !result) {
            return;
        }

        validateButton.addEventListener('click', async function () {
            var doi = doiInput.value.trim();
            if (!doi) {
                return;
            }

            setStatusContent(result, validateButton.dataset.checking || 'Checking…', 'muted');
            validateButton.disabled = true;
            try {
                var projectId = projectSelect ? projectSelect.value : '0';
                var response = await fetch(buildUrl(config.validateDoiUrlTemplate, { PROJECT_ID: projectId }), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ doi: doi })
                });
                var data = await response.json();
                if (data.valid) {
                    var metadata = data.metadata || {};
                    setStatusContent(
                        result,
                        (validateButton.dataset.valid || 'Valid') + (metadata.title ? ' — ' + metadata.title : ''),
                        'success',
                        'bi-check-circle'
                    );
                } else {
                    setStatusContent(
                        result,
                        (validateButton.dataset.invalid || 'Invalid') + (data.error ? ' — ' + data.error : ''),
                        'danger',
                        'bi-x-circle'
                    );
                }
            } catch (error) {
                setStatusContent(result, (config.errorLabel || 'Error') + ': ' + error.message, 'danger', 'bi-x-circle');
            } finally {
                validateButton.disabled = false;
            }
        });
    }

    function bindBatchDoiValidation(config) {
        var batchButton = document.getElementById('btnValidateBatch');
        var batchProject = document.getElementById('doiBatchProject');
        var batchResult = document.getElementById('doiBatchResult');
        if (!batchButton || !batchProject || !batchResult) {
            return;
        }

        batchButton.addEventListener('click', async function () {
            var projectId = batchProject.value;
            if (!projectId) {
                return;
            }

            setStatusContent(batchResult, batchButton.dataset.checking || 'Checking…', 'muted');
            batchButton.disabled = true;
            try {
                var response = await fetch(buildUrl(config.validateBatchUrlTemplate, { PROJECT_ID: projectId }), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                var data = await response.json();
                setBatchSummary(batchResult, {
                    total: batchButton.dataset.total || 'Total',
                    valid: batchButton.dataset.valid || 'Valid',
                    invalid: batchButton.dataset.invalid || 'Invalid',
                    skipped: batchButton.dataset.skipped || 'Skipped'
                }, {
                    total: data.total || 0,
                    valid: data.valid || 0,
                    invalid: data.invalid || 0,
                    skipped: data.skipped || 0
                });
            } catch (error) {
                setStatusContent(batchResult, (config.errorLabel || 'Error') + ': ' + error.message, 'danger', 'bi-x-circle');
            } finally {
                batchButton.disabled = false;
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var config = getConfig();
        if (!config) {
            return;
        }

        bindExport(config);
        bindImport(config);
        bindSingleDoiValidation(config);
        bindBatchDoiValidation(config);
    });
})();
