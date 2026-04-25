(function () {
    function parseConfig() {
        var element = document.getElementById("report-share-config");
        if (!element) {
            return {};
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return {};
        }
    }

    function showShareMessage(message) {
        if (message) {
            window.beepUI.notify(message);
        }
    }

    function createPreviewState(message, isError) {
        var container = document.createElement("div");
        container.className = "report-share-preview-state" + (isError ? " report-share-preview-state--error" : "");

        var icon = document.createElement("i");
        icon.className = "bi " + (isError ? "bi-x-circle" : "bi-exclamation-triangle") + " report-share-preview-empty-icon";
        icon.setAttribute("aria-hidden", "true");

        var text = document.createElement("span");
        text.className = "report-share-preview-state__message";
        text.textContent = message;

        container.appendChild(icon);
        container.appendChild(text);
        return container;
    }

    function setPreviewState(previewElement, message, isError) {
        previewElement.replaceChildren(createPreviewState(message, isError));
    }

    document.addEventListener("DOMContentLoaded", function () {
        var config = parseConfig();
        var reportHtml = "";
        var previewElement = document.getElementById("reportPreview");
        var emailForm = document.getElementById("emailForm");
        var emailSubmitButton = document.getElementById("emailSubmitBtn");
        var securePdfExportCard = document.getElementById("securePdfExportCard");
        var docxExportCard = document.getElementById("docxExportCard");

        async function loadSavedDraft() {
            try {
                var response = await window.fetch(config.draftEndpoint);
                var data = await response.json();
                reportHtml = ((data.draft || {}).html_content || "").trim();
                if (!reportHtml) {
                    reportHtml = (window.localStorage.getItem(config.draftKey) || "").trim();
                }

                if (reportHtml) {
                    previewElement.innerHTML = reportHtml;
                    return;
                }

                setPreviewState(previewElement, config.draftEmptyLabel || "No saved report draft is available yet.", false);
                emailSubmitButton.disabled = true;
            } catch (error) {
                setPreviewState(previewElement, config.draftLoadErrorLabel || "Could not load the saved report draft.", true);
                emailSubmitButton.disabled = true;
            }
        }

        function exportPdf() {
            if (!reportHtml) {
                showShareMessage(config.exportSaveRequiredLabel || "Save the report before exporting it.");
                return;
            }

            var form = document.createElement("form");
            var input = document.createElement("input");
            form.method = "POST";
            form.action = config.pdfExportEndpoint;
            input.type = "hidden";
            input.name = "html_content";
            input.value = reportHtml;
            form.appendChild(input);
            document.body.appendChild(form);
            form.submit();
            form.remove();
        }

        function exportDocx() {
            if (!reportHtml) {
                showShareMessage(config.exportSaveRequiredLabel || "Save the report before exporting it.");
                return;
            }

            var blob = new Blob([
                '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"></head><body>' +
                reportHtml +
                "</body></html>"
            ], {
                type: "application/msword;charset=utf-8"
            });

            var url = URL.createObjectURL(blob);
            var anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = "report.doc";
            anchor.click();
            URL.revokeObjectURL(url);
        }

        function bindActionCard(element, handler) {
            if (!element) {
                return;
            }

            element.addEventListener("click", handler);
            element.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handler();
                }
            });
        }

        bindActionCard(securePdfExportCard, exportPdf);
        bindActionCard(docxExportCard, exportDocx);

        if (emailForm) {
            emailForm.addEventListener("submit", async function (event) {
                event.preventDefault();

                if (!reportHtml) {
                    showShareMessage(config.sendSaveRequiredLabel || "Save the report before sending it.");
                    return;
                }

                window.beepUI.setButtonLoading(emailSubmitButton, true, {
                    loadingLabel: config.sendingLabel || "Sending..."
                });

                try {
                    var response = await window.fetch(config.emailEndpoint, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            email: document.getElementById("emailTo").value,
                            subject: document.getElementById("emailSubject").value,
                            content: reportHtml
                        })
                    });
                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(data.error || config.emailErrorLabel || "Could not send the report.");
                    }

                    showShareMessage(data.message || config.emailSuccessLabel || "Report emailed successfully.");
                    document.getElementById("emailTo").value = "";
                } catch (error) {
                    showShareMessage(error.message || config.emailErrorLabel || "Could not send the report.");
                } finally {
                    window.beepUI.setButtonLoading(emailSubmitButton, false);
                }
            });
        }

        loadSavedDraft();
    });
})();
