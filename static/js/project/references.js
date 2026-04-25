(function () {
    var bibliographyContent = "";

    function showReferenceMessage(message) {
        if (message) {
            window.beepUI.notify(message, { variant: "danger" });
        }
    }

    function parseConfig() {
        var element = document.getElementById("references-config");
        if (!element) {
            return {};
        }
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return {};
        }
    }

    function initTooltips() {
        Array.prototype.forEach.call(
            document.querySelectorAll('[data-bs-toggle="tooltip"]'),
            function (element) {
                if (window.bootstrap && window.bootstrap.Tooltip) {
                    new window.bootstrap.Tooltip(element);
                }
            }
        );
    }

    function bindReferenceForm(config) {
        var form = document.getElementById("addRefForm");
        if (!form) {
            return;
        }

        form.addEventListener("submit", async function (event) {
            event.preventDefault();

            var saveButton = document.getElementById("saveRefBtn");
            var authorsRaw = document.getElementById("refAuthors").value.trim();
            var payload = {
                title: document.getElementById("refTitle").value.trim(),
                authors: authorsRaw ? authorsRaw.split(";").map(function (author) {
                    return author.trim();
                }).filter(Boolean) : [],
                year: parseInt(document.getElementById("refYear").value, 10) || null,
                doi: document.getElementById("refDoi").value.trim() || null,
                publication: document.getElementById("refPublication").value.trim() || null,
                tags: document.getElementById("refTags") ? document.getElementById("refTags").value.trim() || null : null,
                document_id: document.getElementById("refDocument") ? document.getElementById("refDocument").value || null : null
            };

            window.beepUI.setButtonLoading(saveButton, true, {
                loadingLabel: config.loadingLabel || "Loading..."
            });

            try {
                var response = await window.fetch("/projects/" + config.projectId + "/references", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    window.location.reload();
                    return;
                }

                var result = await response.json().catch(function () { return {}; });
                showReferenceMessage(result.error || config.saveFailedLabel || "Failed to save reference.");
            } catch (error) {
                showReferenceMessage(config.networkErrorLabel || "Network error while saving reference.");
            } finally {
                window.beepUI.setButtonLoading(saveButton, false);
            }
        });
    }

    function renderImportSummary(result, config) {
        var summaryNode = document.getElementById("referenceImportSummary");
        var refreshButton = document.getElementById("referenceImportRefreshBtn");
        if (!summaryNode) {
            return;
        }

        var summaryParts = [
            (config.importCreatedLabel || "Created") + ": " + (result.created || 0),
            (config.importDuplicateLabel || "Skipped duplicates") + ": " + (result.duplicate_skipped || 0),
            (config.importInvalidLabel || "Skipped invalid") + ": " + (result.invalid_skipped || 0)
        ];

        summaryNode.hidden = false;
        summaryNode.textContent = (config.importSuccessLabel || "Import finished.") + " " + summaryParts.join(" | ");

        if (refreshButton) {
            refreshButton.hidden = (result.created || 0) === 0;
        }
    }

    function bindReferenceImport(config) {
        var importButton = document.getElementById("referenceImportBtn");
        var refreshButton = document.getElementById("referenceImportRefreshBtn");
        var formatSelect = document.getElementById("referenceImportFormat");
        var fileInput = document.getElementById("referenceImportFile");
        var contentInput = document.getElementById("referenceImportContent");
        var summaryNode = document.getElementById("referenceImportSummary");

        if (!importButton || !formatSelect || !config.importUrl) {
            return;
        }

        if (refreshButton) {
            refreshButton.addEventListener("click", function () {
                window.location.reload();
            });
        }

        importButton.addEventListener("click", async function () {
            var format = formatSelect.value || "bibtex";
            var pastedContent = contentInput ? contentInput.value.trim() : "";
            var selectedFile = fileInput && fileInput.files ? fileInput.files[0] : null;

            if (!pastedContent && !selectedFile) {
                window.beepUI.notify(
                    config.importEmptyLabel || "Add pasted content or choose a file to import.",
                    { variant: "danger" }
                );
                return;
            }

            var formData = new FormData();
            formData.append("format", format);
            if (selectedFile) {
                formData.append("file", selectedFile);
            }
            if (pastedContent) {
                formData.append("content", pastedContent);
            }

            if (summaryNode) {
                summaryNode.hidden = true;
                summaryNode.textContent = "";
            }
            if (refreshButton) {
                refreshButton.hidden = true;
            }

            window.beepUI.setButtonLoading(importButton, true, {
                loadingLabel: config.loadingLabel || "Loading..."
            });

            try {
                var response = await window.fetch(config.importUrl, {
                    method: "POST",
                    body: formData
                });
                var result = await response.json().catch(function () { return {}; });
                if (!response.ok) {
                    throw new Error(result.error || config.importFailedLabel || "Could not import references.");
                }

                renderImportSummary(result, config);
                window.beepUI.notify(
                    config.importSuccessLabel || "Import finished.",
                    { variant: "success" }
                );
                if (contentInput) {
                    contentInput.value = "";
                }
                if (fileInput) {
                    fileInput.value = "";
                }
            } catch (error) {
                window.beepUI.notify(
                    error.message || config.importFailedLabel || "Could not import references.",
                    { variant: "danger" }
                );
            } finally {
                window.beepUI.setButtonLoading(importButton, false);
            }
        });
    }

    function buildBibliographyQuery(config) {
        var params = new URLSearchParams();
        var styleSelect = document.getElementById("bibliographyStyleSelect");
        var style = styleSelect ? styleSelect.value || "apa" : "apa";

        params.set("style", style);
        if (config.selectedCollection && config.selectedCollection !== "all") {
            params.set("collection", config.selectedCollection);
        }
        if (config.selectedTag) {
            params.set("tag", config.selectedTag);
        }
        if (config.searchQuery) {
            params.set("q", config.searchQuery);
        }
        return params;
    }

    function updateBibliographyDownloadLink(config) {
        var link = document.getElementById("bibliographyDownloadLink");
        if (!link || !config.bibliographyExportUrl) {
            return;
        }

        var params = buildBibliographyQuery(config);
        link.href = config.bibliographyExportUrl + "?" + params.toString();
    }

    function setBibliographyStatus(message) {
        var statusNode = document.getElementById("bibliographyStatusText");
        if (statusNode) {
            statusNode.textContent = message || "";
        }
    }

    function renderBibliographyPreview(result, config) {
        var emptyNode = document.getElementById("bibliographyPreviewEmpty");
        var listNode = document.getElementById("bibliographyPreviewList");
        var rawNode = document.getElementById("bibliographyPreviewRaw");
        var truncatedNode = document.getElementById("bibliographyTruncatedNote");

        bibliographyContent = result.content || "";
        updateBibliographyDownloadLink(config);

        if (!result.total_count) {
            setBibliographyStatus(config.bibliographyEmptyLabel || "No references in this view yet.");
            if (emptyNode) {
                emptyNode.hidden = false;
            }
            if (listNode) {
                listNode.hidden = true;
                listNode.innerHTML = "";
            }
            if (rawNode) {
                rawNode.hidden = true;
                rawNode.textContent = "";
            }
            if (truncatedNode) {
                truncatedNode.hidden = true;
            }
            return;
        }

        setBibliographyStatus(config.bibliographyReadyLabel || "Bibliography preview is ready.");
        if (emptyNode) {
            emptyNode.hidden = true;
        }

        if (result.preview_mode === "raw") {
            if (listNode) {
                listNode.hidden = true;
                listNode.innerHTML = "";
            }
            if (rawNode) {
                rawNode.hidden = false;
                rawNode.textContent = result.preview_content || "";
            }
        } else {
            if (rawNode) {
                rawNode.hidden = true;
                rawNode.textContent = "";
            }
            if (listNode) {
                listNode.hidden = false;
                listNode.innerHTML = "";
                (result.entries || []).forEach(function (entry) {
                    var item = document.createElement("li");
                    item.textContent = entry;
                    listNode.appendChild(item);
                });
            }
        }

        if (truncatedNode) {
            truncatedNode.hidden = !result.truncated;
        }
    }

    async function copyBibliographyContent(config) {
        if (!bibliographyContent) {
            window.beepUI.notify(
                config.bibliographyEmptyLabel || "No references in this view yet.",
                { variant: "danger" }
            );
            return;
        }

        try {
            if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
                await navigator.clipboard.writeText(bibliographyContent);
            } else {
                var textarea = document.createElement("textarea");
                textarea.value = bibliographyContent;
                textarea.setAttribute("readonly", "readonly");
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.focus();
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
            }

            window.beepUI.notify(
                config.bibliographyCopySuccessLabel || "Bibliography copied.",
                { variant: "success" }
            );
        } catch (error) {
            window.beepUI.notify(
                config.bibliographyCopyFailedLabel || "Could not copy the bibliography.",
                { variant: "danger" }
            );
        }
    }

    async function loadBibliographyPreview(config) {
        var previewButton = document.getElementById("bibliographyPreviewBtn");
        if (!config.bibliographyPreviewUrl) {
            return;
        }

        var previewUrl = new URL(config.bibliographyPreviewUrl, window.location.origin);
        var params = buildBibliographyQuery(config);
        params.forEach(function (value, key) {
            previewUrl.searchParams.set(key, value);
        });

        setBibliographyStatus(config.bibliographyLoadingLabel || "Loading bibliography preview...");
        updateBibliographyDownloadLink(config);
        if (previewButton) {
            window.beepUI.setButtonLoading(previewButton, true, {
                loadingLabel: config.loadingLabel || "Loading..."
            });
        }

        try {
            var response = await window.fetch(previewUrl.toString(), {
                headers: { "Accept": "application/json" }
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok) {
                throw new Error(result.error || config.networkErrorLabel || "Could not load bibliography preview.");
            }

            renderBibliographyPreview(result, config);
        } catch (error) {
            bibliographyContent = "";
            setBibliographyStatus(error.message || config.networkErrorLabel || "Could not load bibliography preview.");
            window.beepUI.notify(
                error.message || config.networkErrorLabel || "Could not load bibliography preview.",
                { variant: "danger" }
            );
        } finally {
            if (previewButton) {
                window.beepUI.setButtonLoading(previewButton, false);
            }
        }
    }

    function bindBibliographyPreview(config) {
        var previewButton = document.getElementById("bibliographyPreviewBtn");
        var copyButton = document.getElementById("bibliographyCopyBtn");
        var styleSelect = document.getElementById("bibliographyStyleSelect");
        if (!previewButton || !styleSelect) {
            return;
        }

        previewButton.addEventListener("click", function () {
            loadBibliographyPreview(config);
        });

        styleSelect.addEventListener("change", function () {
            updateBibliographyDownloadLink(config);
            loadBibliographyPreview(config);
        });

        if (copyButton) {
            copyButton.addEventListener("click", function () {
                copyBibliographyContent(config);
            });
        }
    }

    function setZoteroStatus(message) {
        var statusNode = document.getElementById("zoteroStatusText");
        if (statusNode) {
            statusNode.textContent = message || "";
        }
    }

    function populateZoteroCollections(collections, config) {
        var select = document.getElementById("zoteroCollectionSelect");
        if (!select) {
            return;
        }

        select.innerHTML = "";
        var allOption = document.createElement("option");
        allOption.value = "";
        allOption.textContent = config.zoteroCollectionAllLabel || "All items";
        select.appendChild(allOption);

        (collections || []).forEach(function (entry) {
            var option = document.createElement("option");
            option.value = entry.key || "";
            option.textContent = entry.name || entry.key || "";
            select.appendChild(option);
        });
    }

    async function loadZoteroStatus(config) {
        var controls = document.getElementById("zoteroControls");
        if (!config.zoteroStatusUrl) {
            return;
        }

        setZoteroStatus(config.zoteroLoadingLabel || "Checking Zotero connection...");
        if (controls) {
            controls.hidden = true;
        }

        try {
            var response = await window.fetch(config.zoteroStatusUrl, {
                headers: { "Accept": "application/json" }
            });
            var result = await response.json().catch(function () { return {}; });
            if (!response.ok) {
                throw new Error(result.error || config.zoteroSyncFailedLabel || "Could not load Zotero status.");
            }

            setZoteroStatus(result.message || (
                result.ready
                    ? (config.zoteroConnectedLabel || "Zotero is connected.")
                    : (config.zoteroNotConnectedLabel || "Connect Zotero to start importing.")
            ));

            if (result.ready) {
                populateZoteroCollections(result.collections || [], config);
                if (controls) {
                    controls.hidden = false;
                }
            }
        } catch (error) {
            setZoteroStatus(error.message || config.zoteroSyncFailedLabel || "Could not load Zotero status.");
        }
    }

    function bindZoteroSync(config) {
        var button = document.getElementById("zoteroSyncBtn");
        var collectionSelect = document.getElementById("zoteroCollectionSelect");
        if (!button || !config.zoteroSyncUrl) {
            return;
        }

        button.addEventListener("click", async function () {
            var payload = {
                collection_key: collectionSelect ? collectionSelect.value || null : null
            };

            window.beepUI.setButtonLoading(button, true, {
                loadingLabel: config.loadingLabel || "Loading..."
            });

            try {
                var response = await window.fetch(config.zoteroSyncUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                var result = await response.json().catch(function () { return {}; });

                if (!response.ok) {
                    throw new Error(result.error || config.zoteroSyncFailedLabel || "Could not sync from Zotero.");
                }

                window.beepUI.notify(
                    config.zoteroSyncSuccessLabel || "Zotero references imported.",
                    { variant: "success" }
                );
                window.location.reload();
            } catch (error) {
                window.beepUI.notify(
                    error.message || config.zoteroSyncFailedLabel || "Could not sync from Zotero.",
                    { variant: "danger" }
                );
            } finally {
                window.beepUI.setButtonLoading(button, false);
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var config = parseConfig();
        initTooltips();
        bindReferenceForm(config);
        bindReferenceImport(config);
        bindBibliographyPreview(config);
        bindZoteroSync(config);
        loadBibliographyPreview(config);
        loadZoteroStatus(config);
    });
})();
