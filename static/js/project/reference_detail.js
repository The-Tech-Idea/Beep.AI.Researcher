(function () {
    function parseConfig() {
        var element = document.getElementById("reference-detail-config");
        if (!element) {
            return {};
        }

        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return {};
        }
    }

    function notify(message, variant) {
        if (!message) {
            return;
        }
        window.beepUI.notify(message, { variant: variant || "danger" });
    }

    function setButtonLoading(element, isLoading, config) {
        window.beepUI.setButtonLoading(element, isLoading, {
            loadingLabel: config.loadingLabel || "Loading..."
        });
    }

    function buildDownloadUrl(config, style) {
        return (config.downloadUrlTemplate || "").replace("STYLE_TOKEN", encodeURIComponent(style));
    }

    function buildAttachmentImportUrl(config, attachmentItemKey) {
        return (config.attachmentImportUrlTemplate || "").replace(
            "ATTACHMENT_KEY_TOKEN",
            encodeURIComponent(attachmentItemKey || "")
        );
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function bindExportPreview(config) {
        var preview = document.getElementById("referenceExportPreview");
        var copyButton = document.getElementById("referenceCopyBtn");
        var downloadButton = document.getElementById("referenceDownloadBtn");
        var tabButtons = document.querySelectorAll("[data-reference-export-style]");
        var currentStyle = config.defaultStyle || "apa";

        function setActiveStyle(style) {
            currentStyle = Object.prototype.hasOwnProperty.call(config.exportContent || {}, style) ? style : "apa";

            if (preview) {
                preview.textContent = (config.exportContent || {})[currentStyle] || "";
            }
            if (downloadButton) {
                downloadButton.href = buildDownloadUrl(config, currentStyle);
            }

            Array.prototype.forEach.call(tabButtons, function (button) {
                var isActive = button.getAttribute("data-reference-export-style") === currentStyle;
                button.classList.toggle("is-active", isActive);
            });
        }

        Array.prototype.forEach.call(tabButtons, function (button) {
            button.addEventListener("click", function () {
                setActiveStyle(button.getAttribute("data-reference-export-style") || "apa");
            });
        });

        if (copyButton) {
            copyButton.addEventListener("click", async function () {
                setButtonLoading(copyButton, true, config);
                try {
                    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
                        throw new Error(config.copyFailedLabel || "Could not copy this citation.");
                    }

                    await navigator.clipboard.writeText((config.exportContent || {})[currentStyle] || "");
                    notify(config.copySuccessLabel || "Citation copied.", "success");
                } catch (error) {
                    notify(error.message || config.copyFailedLabel || "Could not copy this citation.", "danger");
                } finally {
                    setButtonLoading(copyButton, false, config);
                }
            });
        }

        setActiveStyle(currentStyle);
    }

    function bindDocumentLinking(config) {
        var linkButton = document.getElementById("referenceLinkBtn");
        var documentSelect = document.getElementById("referenceLinkDocumentSelect");
        var contextInput = document.getElementById("referenceLinkContextInput");

        if (!linkButton || !documentSelect || !config.linkUrl) {
            return;
        }

        linkButton.addEventListener("click", async function () {
            var documentId = documentSelect.value;
            if (!documentId) {
                notify(config.linkRequiredLabel || "Choose a file to link first.", "danger");
                return;
            }

            var payload = {
                document_id: Number(documentId),
                citation_context: contextInput && contextInput.value ? contextInput.value.trim() : null
            };

            setButtonLoading(linkButton, true, config);
            try {
                var response = await window.fetch(config.linkUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    body: JSON.stringify(payload)
                });
                var result = await response.json().catch(function () { return {}; });
                if (!response.ok) {
                    throw new Error(result.error || config.linkFailedLabel || "Could not link this file.");
                }

                notify(config.linkSuccessLabel || "File linked to this source.", "success");
                window.location.reload();
            } catch (error) {
                notify(error.message || config.linkFailedLabel || "Could not link this file.", "danger");
            } finally {
                setButtonLoading(linkButton, false, config);
            }
        });
    }

    function bindDocumentRemoval(config) {
        var removeButtons = document.querySelectorAll("[data-reference-remove-document]");
        if (!removeButtons.length || !config.removeUrlTemplate) {
            return;
        }

        Array.prototype.forEach.call(removeButtons, function (button) {
            button.addEventListener("click", async function () {
                var documentId = button.getAttribute("data-reference-remove-document");
                if (!documentId) {
                    return;
                }

                setButtonLoading(button, true, config);
                try {
                    var response = await window.fetch(
                        config.removeUrlTemplate.replace("999999999", encodeURIComponent(documentId)),
                        {
                            method: "DELETE",
                            headers: { "Accept": "application/json" }
                        }
                    );
                    var result = await response.json().catch(function () { return {}; });
                    if (!response.ok) {
                        throw new Error(result.error || config.removeFailedLabel || "Could not remove this file link.");
                    }

                    notify(config.removeSuccessLabel || "File link removed.", "success");
                    window.location.reload();
                } catch (error) {
                    notify(error.message || config.removeFailedLabel || "Could not remove this file link.", "danger");
                } finally {
                    setButtonLoading(button, false, config);
                }
            });
        });
    }

    function bindAttachmentImport(config) {
        var importButtons = document.querySelectorAll("[data-reference-import-attachment]");
        if (!importButtons.length || !config.attachmentImportUrlTemplate) {
            return;
        }

        Array.prototype.forEach.call(importButtons, function (button) {
            button.addEventListener("click", async function () {
                var attachmentItemKey = button.getAttribute("data-reference-import-attachment");
                if (!attachmentItemKey) {
                    return;
                }

                setButtonLoading(button, true, config);
                try {
                    var response = await window.fetch(buildAttachmentImportUrl(config, attachmentItemKey), {
                        method: "POST",
                        headers: { "Accept": "application/json" }
                    });
                    var result = await response.json().catch(function () { return {}; });
                    if (!response.ok) {
                        throw new Error(result.error || config.attachmentImportFailedLabel || "Could not add this attachment to the project files.");
                    }

                    notify(result.message || config.attachmentImportSuccessLabel || "Attachment added to the project files.", "success");
                    window.location.reload();
                } catch (error) {
                    notify(error.message || config.attachmentImportFailedLabel || "Could not add this attachment to the project files.", "danger");
                } finally {
                    setButtonLoading(button, false, config);
                }
            });
        });
    }

    function buildAttachmentMarkup(attachment, config) {
        var chips = [];
        if (attachment.filename) {
            chips.push('<span class="reference-detail-attachment-chip">' + escapeHtml(attachment.filename) + "</span>");
        }
        if (attachment.content_type) {
            chips.push('<span class="reference-detail-attachment-chip">' + escapeHtml(attachment.content_type) + "</span>");
        }
        if (attachment.link_mode) {
            chips.push('<span class="reference-detail-attachment-chip">' + escapeHtml(attachment.link_mode) + "</span>");
        }

        var actionMarkup = attachment.open_url
            ? '<a href="' + escapeHtml(attachment.open_url) + '" target="_blank" rel="noopener" class="reference-detail-attachment-link">' +
                escapeHtml(config.externalAttachmentOpenLabel || "Open attachment") +
              "</a>"
            : '<span class="reference-detail-attachment-link is-disabled">' +
                escapeHtml(config.externalAttachmentUnavailableLabel || "Open in Zotero") +
              "</span>";

        if (attachment.can_import && attachment.item_key) {
            actionMarkup += (
                '<button type="button" class="reference-detail-inline-button" data-reference-import-attachment="' +
                escapeHtml(attachment.item_key) +
                '">' +
                escapeHtml(config.attachmentImportLabel || "Add to project files") +
                "</button>"
            );
        }

        return (
            '<article class="reference-detail-attachment-card">' +
                '<div class="reference-detail-attachment-card__body">' +
                    '<h4 class="reference-detail-attachment-card__title">' + escapeHtml(attachment.title || "Attachment") + "</h4>" +
                    '<div class="reference-detail-attachment-meta">' + chips.join("") + "</div>" +
                "</div>" +
                '<div class="reference-detail-attachment-card__actions">' + actionMarkup + "</div>" +
            "</article>"
        );
    }

    function bindExternalAttachments(config) {
        var list = document.getElementById("referenceExternalAttachmentsList");
        var empty = document.getElementById("referenceExternalAttachmentsEmpty");
        if (!list || !empty || !config.externalAttachmentsUrl) {
            return;
        }

        var hadServerAttachments = list.children.length > 0;

        function showEmpty(message) {
            empty.textContent = message;
            empty.classList.remove("is-hidden");
        }

        function showList(attachments) {
            if (!attachments.length) {
                list.innerHTML = "";
                showEmpty(config.externalAttachmentsEmptyLabel || "No external attachments found for this source yet.");
                return;
            }

            list.innerHTML = attachments.map(function (attachment) {
                return buildAttachmentMarkup(attachment, config);
            }).join("");
            empty.classList.add("is-hidden");
        }

        showEmpty(config.externalAttachmentsLoadingLabel || "Loading external attachments...");

        window.fetch(config.externalAttachmentsUrl, {
            headers: { "Accept": "application/json" }
        })
            .then(function (response) {
                return response.json().catch(function () {
                    return {};
                }).then(function (payload) {
                    if (!response.ok) {
                        throw new Error(payload.error || config.externalAttachmentsFailedLabel || "Could not load external attachments.");
                    }
                    return payload;
                });
            })
            .then(function (payload) {
                showList(Array.isArray(payload.attachments) ? payload.attachments : []);
                bindAttachmentImport(config);
            })
            .catch(function (error) {
                if (hadServerAttachments) {
                    empty.classList.add("is-hidden");
                    notify(error.message || config.externalAttachmentsFailedLabel || "Could not load external attachments.", "warning");
                    return;
                }

                showEmpty(error.message || config.externalAttachmentsFailedLabel || "Could not load external attachments.");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var config = parseConfig();
        bindExportPreview(config);
        bindDocumentLinking(config);
        bindDocumentRemoval(config);
        bindAttachmentImport(config);
        bindExternalAttachments(config);
    });
})();
