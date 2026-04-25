(function () {
    function parseConfig() {
        var configElement = document.getElementById('report-config');
        if (!configElement) {
            return {};
        }

        try {
            return JSON.parse(configElement.textContent);
        } catch (error) {
            return {};
        }
    }

    function updateSidebarCounts(projectId, units) {
        if (!projectId) {
            return;
        }

        fetch('/researcher/api/projects/' + projectId + '/overview-stats')
            .then(function (response) { return response.json(); })
            .then(function (payload) {
                var codeCount = document.getElementById('sidebarCodeCount');
                var extractionCount = document.getElementById('sidebarExtractionCount');
                var referenceCount = document.getElementById('sidebarRefCount');
                var answerCount = document.getElementById('sidebarAnswerCount');

                if (codeCount) {
                    codeCount.textContent = (payload.code_count || 0) + ' ' + units.codes;
                }
                if (extractionCount) {
                    extractionCount.textContent = (payload.extraction_count || 0) + ' ' + units.extractions;
                }
                if (referenceCount) {
                    referenceCount.textContent = (payload.reference_count || 0) + ' ' + units.references;
                }
                if (answerCount) {
                    answerCount.textContent = (payload.answer_count || 0) + ' ' + units.answers;
                }
            })
            .catch(function () { /* noop */ });
    }

    function bindInsertRefreshButtons() {
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-insert-refresh]'),
            function (button) {
                button.addEventListener('click', function () {
                    var type = button.getAttribute('data-insert-refresh');
                    if (window.fetchInsertableData && type) {
                        window.fetchInsertableData(type);
                    }
                });
            }
        );
    }

    function bindHeaderButtons() {
        var saveButton = document.getElementById('saveReportButton');
        var shareButton = document.getElementById('shareReportButton');

        if (saveButton) {
            saveButton.addEventListener('click', function () {
                if (window.saveReport) {
                    window.saveReport();
                }
            });
        }

        if (shareButton) {
            shareButton.addEventListener('click', function () {
                if (window.goToSharePage) {
                    window.goToSharePage();
                }
            });
        }
    }

    function buildButtonIcon(iconName, extraClass) {
        var icon = document.createElement('i');
        icon.className = 'bi bi-' + iconName + ' report-button-icon';
        if (extraClass) {
            icon.classList.add(extraClass);
        }
        icon.setAttribute('aria-hidden', 'true');
        return icon;
    }

    function buildButtonLabel(text) {
        var label = document.createElement('span');
        label.textContent = text;
        return label;
    }

    function setGenerateButtonContent(button, label, isLoading) {
        if (!button) {
            return;
        }

        var iconName = isLoading ? 'arrow-repeat' : 'stars';
        var iconClass = isLoading ? 'report-button-spinner' : '';
        button.replaceChildren(buildButtonIcon(iconName, iconClass), buildButtonLabel(label));
    }

    function showMessage(message) {
        if (message) {
            window.beepUI.notify(message);
        }
    }

    function bindAiWriteModal(config) {
        var generateButton = document.getElementById('btnGenerateWrite');
        if (generateButton) {
            generateButton.addEventListener('click', async function () {
                var promptElement = document.getElementById('aiWritePrompt');
                var resultElement = document.getElementById('aiWriteResult');
                var resultTextElement = document.getElementById('aiWriteResultText');
                var prompt = promptElement ? promptElement.value.trim() : '';
                if (!prompt) {
                    return;
                }

                generateButton.disabled = true;
                setGenerateButtonContent(generateButton, config.generatingLabel, true);

                try {
                    var response = await fetch(config.writeSectionEndpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompt: prompt }),
                    });
                    var payload = await response.json();
                    if (!response.ok) {
                        throw new Error(payload.error || 'Unable to draft this section.');
                    }

                    var text = payload.text || payload.content || '';
                    if (text && resultTextElement && resultElement) {
                        resultTextElement.textContent = text;
                        resultElement.hidden = false;
                        if (window.renderReportSupportingSources) {
                            window.renderReportSupportingSources(payload.supporting_sources || [], {
                                title: 'Files used for this drafted section',
                                intro: 'These project files supported the latest drafted section on this page.',
                            });
                        }
                    }
                } catch (error) {
                    showMessage(error.message);
                } finally {
                    generateButton.disabled = false;
                    setGenerateButtonContent(generateButton, config.generateLabel, false);
                }
            });
        }

        var insertButton = document.getElementById('btnInsertAiWrite');
        if (insertButton) {
            insertButton.addEventListener('click', function () {
                var textElement = document.getElementById('aiWriteResultText');
                var text = textElement ? textElement.textContent : '';
                if (window.quill && text) {
                    var selection = window.quill.getSelection(true) || { index: window.quill.getLength() - 1, length: 0 };
                    window.quill.insertText(selection.index, text + '\n');
                    var modalElement = document.getElementById('aiWriteModal');
                    if (modalElement) {
                        var modal = window.bootstrap && window.bootstrap.Modal.getInstance(modalElement);
                        if (modal) {
                            modal.hide();
                        }
                    }
                }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var config = parseConfig();
        window.REPORT_I18N = config;

        var sidebar = document.getElementById('dataSidebar');
        var toggleButton = document.getElementById('toggleDataSidebar');
        if (toggleButton && sidebar) {
            toggleButton.addEventListener('click', function () {
                sidebar.classList.toggle('open');
            });
        }

        bindHeaderButtons();
        bindInsertRefreshButtons();
        bindAiWriteModal({
            writeSectionEndpoint: config.writeSectionEndpoint || '',
            generatingLabel: config.generatingLabel || 'Generating...',
            generateLabel: config.generateButtonLabel || 'Generate',
        });

        updateSidebarCounts(config.projectId, {
            codes: config.unitsCodes || 'codes',
            extractions: config.unitsExtractions || 'tables',
            references: config.unitsReferences || 'references',
            answers: config.unitsAnswers || 'answers',
        });
    });
})();
