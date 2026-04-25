(function () {
    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function trimValue(value, fallback) {
        var normalized = String(value || '').trim();
        return normalized || (fallback || '');
    }

    function normalizeSources(items, maxItems) {
        var normalized = [];
        var seen = {};
        var list = Array.isArray(items) ? items : [];
        var limit = typeof maxItems === 'number' && maxItems > 0 ? maxItems : 8;

        for (var index = 0; index < list.length; index += 1) {
            var entry = list[index];
            if (!entry || typeof entry !== 'object') {
                continue;
            }

            var sourceName = trimValue(
                entry.source || entry.filename || entry.document_name || entry.name,
                'Project file'
            );
            var documentId = trimValue(entry.document_id || entry.id, '');
            var snippet = trimValue(entry.snippet || entry.excerpt || entry.summary, '');
            var key = [documentId.toLowerCase(), sourceName.toLowerCase(), snippet.toLowerCase()].join('|');

            if (seen[key]) {
                continue;
            }

            seen[key] = true;
            normalized.push({
                source: sourceName,
                documentId: documentId,
                snippet: snippet,
            });

            if (normalized.length >= limit) {
                break;
            }
        }

        return normalized;
    }

    function buildDocumentUrl(documentUrlTemplate, documentId) {
        var template = trimValue(documentUrlTemplate, '');
        var normalizedDocumentId = trimValue(documentId, '');
        if (!template || !normalizedDocumentId) {
            return '';
        }

        return template.replace('__DOC_ID__', encodeURIComponent(normalizedDocumentId));
    }

    function buildPanelMarkup(sources, options) {
        var title = trimValue(options.title, 'Files used for this result');
        var intro = trimValue(
            options.intro,
            'These project files supported the latest generated result on this page.'
        );
        var eyebrow = trimValue(options.eyebrow, 'Used from your files');
        var linkLabel = trimValue(options.linkLabel, 'Open file');
        var documentUrlTemplate = trimValue(options.documentUrlTemplate, '');

        var itemsMarkup = sources.map(function (source) {
            var sourceName = escapeHtml(source.source);
            var snippet = source.snippet
                ? '<p class="project-supporting-sources__snippet">' + escapeHtml(source.snippet) + '</p>'
                : '';
            var documentUrl = buildDocumentUrl(documentUrlTemplate, source.documentId);
            var openLink = documentUrl
                ? '<a class="project-supporting-sources__link" href="' + escapeHtml(documentUrl) + '">' +
                    escapeHtml(linkLabel) +
                  '</a>'
                : '';

            return (
                '<article class="project-supporting-sources__item">' +
                    '<div class="project-supporting-sources__item-head">' +
                        '<strong class="project-supporting-sources__name">' + sourceName + '</strong>' +
                        openLink +
                    '</div>' +
                    snippet +
                '</article>'
            );
        }).join('');

        return (
            '<section class="project-supporting-sources" role="region" aria-live="polite">' +
                '<div class="project-supporting-sources__header">' +
                    '<div>' +
                        '<p class="project-supporting-sources__eyebrow">' + escapeHtml(eyebrow) + '</p>' +
                        '<h2 class="project-supporting-sources__title">' + escapeHtml(title) + '</h2>' +
                    '</div>' +
                    '<p class="project-supporting-sources__intro">' + escapeHtml(intro) + '</p>' +
                '</div>' +
                '<div class="project-supporting-sources__list">' + itemsMarkup + '</div>' +
            '</section>'
        );
    }

    function create(container, options) {
        var baseOptions = options || {};

        function clear() {
            if (!container) {
                return;
            }
            container.innerHTML = '';
            container.hidden = true;
        }

        function render(items, overrideOptions) {
            if (!container) {
                return [];
            }

            var sources = normalizeSources(items, (overrideOptions || {}).maxItems || baseOptions.maxItems);
            if (!sources.length) {
                clear();
                return [];
            }

            var effectiveOptions = Object.assign({}, baseOptions, overrideOptions || {});
            container.innerHTML = buildPanelMarkup(sources, effectiveOptions);
            container.hidden = false;
            return sources;
        }

        clear();
        return {
            clear: clear,
            render: render,
        };
    }

    window.ProjectSupportingSources = {
        create: create,
    };
})();
