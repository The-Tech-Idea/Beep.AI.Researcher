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

    async function requestJson(url, options) {
        var response = await fetch(url, options);
        var payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok) {
            throw new Error(payload.error || payload.message || 'Request failed.');
        }

        return payload;
    }

    function getCollectionName(collections, collectionId) {
        var normalizedCollectionId = trimValue(collectionId, '');
        if (!normalizedCollectionId || !Array.isArray(collections)) {
            return '';
        }

        for (var index = 0; index < collections.length; index += 1) {
            var entry = collections[index];
            if (!entry || typeof entry !== 'object') {
                continue;
            }

            var entryId = trimValue(entry.collection_id || entry.id || entry.name, '');
            if (entryId === normalizedCollectionId) {
                return trimValue(entry.name || entry.title || entry.display_name || entryId, normalizedCollectionId);
            }
        }

        return normalizedCollectionId;
    }

    function formatQualityModeLabel(qualityMode, container) {
        var normalized = trimValue(qualityMode, 'balanced');
        var labels = {
            fast: trimValue(container.dataset.qualityFastLabel, 'Quick overview'),
            balanced: trimValue(container.dataset.qualityBalancedLabel, 'Balanced help'),
            deep: trimValue(container.dataset.qualityDeepLabel, 'Careful review'),
        };

        return labels[normalized] || labels.balanced;
    }

    function describeReadingSetup(profile) {
        var source = trimValue(profile.chunking_source, 'quality_mode_default');
        var name = trimValue(
            profile.chunk_template_name || profile.database_default_chunk_template_name,
            'Library default'
        );

        var note = 'Using the saved reading setup from the connected document library.';
        if (source === 'collection_template_override' || source === 'collection_override') {
            note = 'This project is using a saved reading setup on the connected document library.';
        } else if (source === 'database_template_default' || source === 'database_profile_default') {
            note = 'Using the default reading setup saved on the connected document library.';
        } else if (source === 'quality_mode_default') {
            note = 'Using the standard reading setup for this answer style.';
        }

        return {
            name: name,
            note: note,
        };
    }

    function describeFileConnections(graphReadingMode) {
        var mode = graphReadingMode && typeof graphReadingMode === 'object' ? graphReadingMode : {};
        var name = trimValue(
            mode.effective_graph_extraction_profile_label || mode.database_default_graph_extraction_profile_label,
            'Library default'
        );
        var note = 'Using the connected document library file connection setup.';
        if (trimValue(mode.mode, 'library_default') === 'library_default') {
            note = 'Using the default file connection setup from the connected document library.';
        } else if (trimValue(mode.mode, '') === 'custom') {
            note = 'This project is using a saved custom file connection setup on the connected document library.';
        }

        return {
            name: name,
            note: note,
        };
    }

    function buildSummaryMarkup(options) {
        var intro = options.intro
            || 'This page is using the saved document library setup for this project.';

        return (
            '<section class="project-library-summary project-library-summary--ready">' +
                '<div class="project-library-summary__header">' +
                    '<div>' +
                        '<p class="project-library-summary__eyebrow">' + escapeHtml(options.eyebrow || 'Current library setup') + '</p>' +
                        '<h2 class="project-library-summary__title">' + escapeHtml(options.title || 'Saved setup now in use') + '</h2>' +
                    '</div>' +
                    '<p class="project-library-summary__intro">' + escapeHtml(intro) + '</p>' +
                '</div>' +
                '<div class="project-library-summary__grid">' +
                    '<article class="project-library-summary__item">' +
                        '<span class="project-library-summary__label">Document library</span>' +
                        '<strong class="project-library-summary__value">' + escapeHtml(options.collectionName) + '</strong>' +
                        '<p class="project-library-summary__note">' + escapeHtml(options.collectionNote) + '</p>' +
                    '</article>' +
                    '<article class="project-library-summary__item">' +
                        '<span class="project-library-summary__label">Reading setup</span>' +
                        '<strong class="project-library-summary__value">' + escapeHtml(options.readingName) + '</strong>' +
                        '<p class="project-library-summary__note">' + escapeHtml(options.readingNote) + '</p>' +
                    '</article>' +
                    '<article class="project-library-summary__item">' +
                        '<span class="project-library-summary__label">Answer style</span>' +
                        '<strong class="project-library-summary__value">' + escapeHtml(options.qualityName) + '</strong>' +
                        '<p class="project-library-summary__note">' + escapeHtml(options.qualityNote) + '</p>' +
                    '</article>' +
                    '<article class="project-library-summary__item">' +
                        '<span class="project-library-summary__label">File connections</span>' +
                        '<strong class="project-library-summary__value">' + escapeHtml(options.graphName) + '</strong>' +
                        '<p class="project-library-summary__note">' + escapeHtml(options.graphNote) + '</p>' +
                    '</article>' +
                '</div>' +
                '<div class="project-library-summary__actions">' +
                    '<a class="project-library-summary__action" href="' + escapeHtml(options.settingsUrl) + '">Open settings</a>' +
                '</div>' +
            '</section>'
        );
    }

    function buildEmptyMarkup(container) {
        var startUrl = trimValue(container.dataset.startUrl, '#');
        var settingsUrl = trimValue(container.dataset.settingsUrl, '#');
        return (
            '<section class="project-library-summary project-library-summary--empty">' +
                '<div class="project-library-summary__header">' +
                    '<div>' +
                        '<p class="project-library-summary__eyebrow">Current library setup</p>' +
                        '<h2 class="project-library-summary__title">Connect a document library</h2>' +
                    '</div>' +
                    '<p class="project-library-summary__intro">Choose a document library so this project can read files, connect related material, and answer with saved reading settings.</p>' +
                '</div>' +
                '<div class="project-library-summary__actions">' +
                    '<a class="project-library-summary__action project-library-summary__action--primary" href="' + escapeHtml(startUrl) + '">Open setup</a>' +
                    '<a class="project-library-summary__action" href="' + escapeHtml(settingsUrl) + '">Open settings</a>' +
                '</div>' +
            '</section>'
        );
    }

    function buildErrorMarkup(container, message) {
        var settingsUrl = trimValue(container.dataset.settingsUrl, '#');
        return (
            '<section class="project-library-summary project-library-summary--error">' +
                '<div class="project-library-summary__header">' +
                    '<div>' +
                        '<p class="project-library-summary__eyebrow">Current library setup</p>' +
                        '<h2 class="project-library-summary__title">Library setup could not be loaded</h2>' +
                    '</div>' +
                    '<p class="project-library-summary__intro">' + escapeHtml(message || 'Check the document library connection in project settings.') + '</p>' +
                '</div>' +
                '<div class="project-library-summary__actions">' +
                    '<a class="project-library-summary__action" href="' + escapeHtml(settingsUrl) + '">Open settings</a>' +
                '</div>' +
            '</section>'
        );
    }

    function renderLoading(container) {
        container.innerHTML = (
            '<section class="project-library-summary project-library-summary--loading">' +
                '<p class="project-library-summary__loading">Loading saved library setup...</p>' +
            '</section>'
        );
    }

    async function loadSummary(container) {
        var collectionId = trimValue(container.dataset.collectionId, '');
        if (!collectionId) {
            container.innerHTML = buildEmptyMarkup(container);
            return;
        }

        var projectApiBase = trimValue(container.dataset.projectApiBase, '');
        var collectionsUrl = trimValue(container.dataset.collectionsUrl, '');
        if (!projectApiBase || !collectionsUrl) {
            container.innerHTML = buildErrorMarkup(container, 'The saved library setup is missing required page configuration.');
            return;
        }

        renderLoading(container);

        try {
            var qualityMode = trimValue(container.dataset.qualityMode, 'balanced');
            var results = await Promise.all([
                requestJson(projectApiBase + '/rag/organization-profile?quality_mode=' + encodeURIComponent(qualityMode)),
                requestJson(collectionsUrl),
            ]);
            var profilePayload = results[0] || {};
            var collectionsPayload = results[1] || {};
            var profile = profilePayload.organization_profile || {};
            var graphReadingMode = profilePayload.graph_reading_mode || {};
            var reading = describeReadingSetup(profile);
            var fileConnections = describeFileConnections(graphReadingMode);
            var collectionName = getCollectionName(collectionsPayload.collections, collectionId);
            var qualityName = formatQualityModeLabel(profilePayload.quality_mode || qualityMode, container);

            container.innerHTML = buildSummaryMarkup({
                collectionName: collectionName || collectionId,
                collectionNote: 'This project is currently connected to the saved document library shown here.',
                readingName: reading.name,
                readingNote: reading.note,
                qualityName: qualityName,
                qualityNote: 'Answers on this project start from the saved answer style shown here.',
                graphName: fileConnections.name,
                graphNote: fileConnections.note,
                settingsUrl: trimValue(container.dataset.settingsUrl, '#'),
            });
        } catch (error) {
            container.innerHTML = buildErrorMarkup(container, error && error.message ? error.message : '');
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var containers = document.querySelectorAll('[data-library-setup-summary]');
        if (!containers.length) {
            return;
        }

        Array.prototype.forEach.call(containers, function (container) {
            loadSummary(container);
        });
    });
})();
