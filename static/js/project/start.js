(function () {
    const root = document.getElementById('projectStartApp');
    if (!root) {
        return;
    }

    const config = {
        projectId: root.dataset.projectId || '',
        projectName: root.dataset.projectName || 'this project',
        projectApiBase: root.dataset.projectApiBase || '',
        collectionsUrl: root.dataset.collectionsUrl || '',
        templateMappingUrl: root.dataset.templateMappingUrl || '',
        graphReadingUrl: root.dataset.graphReadingUrl || '',
        chunkTemplatesUrl: root.dataset.chunkTemplatesUrl || '',
        overviewUrl: root.dataset.overviewUrl || '',
        settingsUrl: root.dataset.settingsUrl || '',
        initialCollectionId: root.dataset.initialCollectionId || '',
        initialQualityMode: root.dataset.initialQualityMode || 'balanced',
    };

    const elements = {
        form: document.getElementById('projectStartForm'),
        status: document.getElementById('projectStartStatus'),
        collection: document.getElementById('projectStartCollection'),
        qualityMode: document.getElementById('projectStartQualityMode'),
        documentType: document.getElementById('projectStartDocumentType'),
        documentTypeCustom: document.getElementById('projectStartDocumentTypeCustom'),
        documentTypeHint: document.getElementById('projectStartDocumentTypeHint'),
        graphMode: document.getElementById('projectStartGraphMode'),
        graphModeHint: document.getElementById('projectStartGraphModeHint'),
        suggestionName: document.getElementById('projectStartSuggestionName'),
        suggestionDescription: document.getElementById('projectStartSuggestionDescription'),
        suggestionNote: document.getElementById('projectStartSuggestionNote'),
        saveButton: document.getElementById('projectStartSaveBtn'),
    };

    let mappingContract = { default_template_slug: '', document_types: [] };
    let graphContract = { default_mode: 'library_default', modes: [] };
    let availableGraphProfiles = [];
    let availableCollections = [];
    let templatesBySlug = new Map();
    let currentGraphProfileId = '';
    let currentGraphProfileLabel = '';

    function getTrimmedValue(element, fallbackValue) {
        if (!element || typeof element.value !== 'string') {
            return fallbackValue || '';
        }
        const value = element.value.trim();
        return value || (fallbackValue || '');
    }

    async function requestJson(url, options) {
        const response = await fetch(url, Object.assign({
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        }, options || {}));
        const data = await response.json().catch(function () {
            return {};
        });
        if (!response.ok) {
            throw new Error(data.error || data.message || 'Request failed.');
        }
        return data;
    }

    function setStatus(level, message) {
        if (!elements.status) {
            return;
        }
        elements.status.className = 'project-start__status';
        elements.status.classList.add('is-' + (level || 'info'));
        elements.status.textContent = message;
    }

    function setSavingState(isSaving) {
        if (elements.saveButton) {
            elements.saveButton.disabled = isSaving;
        }
        [
            elements.collection,
            elements.qualityMode,
            elements.documentType,
            elements.documentTypeCustom,
            elements.graphMode,
        ].forEach(function (element) {
            if (element) {
                element.disabled = isSaving;
            }
        });
    }

    function findDocumentTypeDefinition(documentType) {
        return (mappingContract.document_types || []).find(function (definition) {
            return String(definition.document_type || '').trim() === String(documentType || '').trim();
        }) || null;
    }

    function renderCollections() {
        if (!elements.collection) {
            return;
        }
        elements.collection.innerHTML = '';

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = availableCollections.length
            ? 'Choose a document library...'
            : 'No document libraries are available yet';
        elements.collection.appendChild(placeholder);

        availableCollections.forEach(function (collection) {
            const option = document.createElement('option');
            option.value = collection.id || collection.collection_id || '';
            option.textContent = collection.name || collection.label || option.value;
            elements.collection.appendChild(option);
        });

        elements.collection.value = config.initialCollectionId || '';
    }

    function renderDocumentTypes() {
        if (!elements.documentType) {
            return;
        }

        elements.documentType.innerHTML = '';
        (mappingContract.document_types || []).forEach(function (definition) {
            const option = document.createElement('option');
            option.value = definition.document_type || '';
            option.textContent = definition.label || definition.document_type || '';
            elements.documentType.appendChild(option);
        });

        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = 'Other file type';
        elements.documentType.appendChild(customOption);
    }

    function findGraphModeDefinition(mode) {
        return (graphContract.modes || []).find(function (definition) {
            return String(definition.mode || '').trim() === String(mode || '').trim();
        }) || null;
    }

    function ensureCurrentCustomGraphOption() {
        if (!elements.graphMode || !currentGraphProfileId) {
            return;
        }
        const exists = Array.from(elements.graphMode.options).some(function (option) {
            return option.value === 'custom';
        });
        if (exists) {
            return;
        }
        const option = document.createElement('option');
        option.value = 'custom';
        option.textContent = currentGraphProfileLabel || 'Current saved file connection setup';
        elements.graphMode.appendChild(option);
    }

    function renderGraphModes() {
        if (!elements.graphMode) {
            return;
        }

        elements.graphMode.innerHTML = '';
        (graphContract.modes || []).forEach(function (definition) {
            const option = document.createElement('option');
            option.value = definition.mode || '';
            option.textContent = definition.label || definition.mode || '';

            const profileId = String(definition.graph_extraction_profile_id || '').trim();
            if (profileId && !availableGraphProfiles.some(function (profile) {
                return String(profile.profile_id || profile.id || '').trim() === profileId;
            })) {
                option.disabled = true;
                option.textContent = (definition.label || definition.mode || '') + ' (needs library setup first)';
            }
            elements.graphMode.appendChild(option);
        });

        ensureCurrentCustomGraphOption();
    }

    function updateDocumentTypeUi() {
        if (!elements.documentType || !elements.documentTypeHint || !elements.documentTypeCustom) {
            return;
        }

        const selectedValue = getTrimmedValue(elements.documentType, '');
        if (selectedValue === 'custom') {
            elements.documentTypeCustom.hidden = false;
            elements.documentTypeHint.textContent = getTrimmedValue(elements.documentTypeCustom, '')
                ? 'Use a short plain-language file type that your team will understand.'
                : 'Describe the main file type in plain language, such as policy memo, scanned report, or meeting notes.';
        } else {
            elements.documentTypeCustom.hidden = true;
            elements.documentTypeCustom.value = '';
            const definition = findDocumentTypeDefinition(selectedValue);
            elements.documentTypeHint.textContent = definition
                ? (definition.description || 'Choose the file type that best matches most of the material in this project.')
                : 'Choose the file type that best matches most of the material in this project.';
        }
        updateSuggestedSetup();
    }

    function updateGraphModeHint() {
        if (!elements.graphModeHint || !elements.graphMode) {
            return;
        }
        const selectedMode = getTrimmedValue(elements.graphMode, 'library_default');
        if (selectedMode === 'custom') {
            elements.graphModeHint.textContent = currentGraphProfileLabel
                ? 'This project is already using the saved file connection setup "' + currentGraphProfileLabel + '".'
                : 'This project is already using a saved file connection setup.';
            return;
        }

        const definition = findGraphModeDefinition(selectedMode);
        elements.graphModeHint.textContent = definition
            ? (definition.description || 'Choose how much help the assistant should use when connecting related files.')
            : 'Choose how much help the assistant should use when connecting related files.';
    }

    function getSuggestedTemplateSlug() {
        const selectedType = getTrimmedValue(elements.documentType, '');
        const definition = findDocumentTypeDefinition(selectedType);
        if (definition && definition.template_slug) {
            return String(definition.template_slug).trim();
        }
        return String(mappingContract.default_template_slug || '').trim();
    }

    function updateSuggestedSetup() {
        const suggestedSlug = getSuggestedTemplateSlug();
        const template = templatesBySlug.get(suggestedSlug) || null;

        if (!elements.suggestionName || !elements.suggestionDescription || !elements.suggestionNote) {
            return;
        }

        elements.suggestionNote.className = 'project-start__suggestion-note';

        if (!suggestedSlug) {
            elements.suggestionName.textContent = 'Library default reading setup';
            elements.suggestionDescription.textContent = 'This project will follow the default reading setup already saved on the document library.';
            elements.suggestionNote.textContent = 'No special reading setup needs to be applied.';
            return;
        }

        if (!template) {
            elements.suggestionName.textContent = 'Suggested reading setup';
            elements.suggestionDescription.textContent = 'The app has a suggested reading setup for this file type, but it is not available yet.';
            elements.suggestionNote.textContent = 'The project will use the library default for now.';
            elements.suggestionNote.classList.add('is-warning');
            return;
        }

        elements.suggestionName.textContent = template.name || suggestedSlug;
        elements.suggestionDescription.textContent = template.description || 'This setup matches the main file type you selected.';
        if (template.isAvailable) {
            elements.suggestionNote.textContent = 'This setup is ready and will be applied when you save.';
            elements.suggestionNote.classList.add('is-ready');
        } else {
            elements.suggestionNote.textContent = 'This setup still needs library setup first, so the project will use the library default for now.';
            elements.suggestionNote.classList.add('is-warning');
        }
    }

    function getSelectedDocumentTypeValue() {
        const selectedType = getTrimmedValue(elements.documentType, '');
        if (selectedType === 'custom') {
            return getTrimmedValue(elements.documentTypeCustom, '');
        }
        return selectedType;
    }

    function getSelectedGraphProfileId() {
        const selectedMode = getTrimmedValue(elements.graphMode, 'library_default');
        if (selectedMode === 'custom') {
            return currentGraphProfileId;
        }
        const definition = findGraphModeDefinition(selectedMode);
        return definition ? String(definition.graph_extraction_profile_id || '').trim() : '';
    }

    function normalizeMetadataSchema(metadataSchema) {
        if (metadataSchema && typeof metadataSchema === 'object') {
            return {
                version: metadataSchema.version || '2.0',
                filterable_fields: Array.isArray(metadataSchema.filterable_fields) ? metadataSchema.filterable_fields : [],
            };
        }
        return {
            version: '2.0',
            filterable_fields: [],
        };
    }

    async function loadContracts() {
        const [collections, mapping, graph, templates] = await Promise.all([
            requestJson(config.collectionsUrl),
            requestJson(config.templateMappingUrl),
            requestJson(config.graphReadingUrl),
            requestJson(config.chunkTemplatesUrl),
        ]);

        availableCollections = Array.isArray(collections.collections) ? collections.collections : [];
        mappingContract = mapping.contract || { default_template_slug: '', document_types: [] };
        graphContract = graph.contract || { default_mode: 'library_default', modes: [] };
        availableGraphProfiles = Array.isArray(graph.available_profiles) ? graph.available_profiles : [];

        templatesBySlug = new Map();
        (templates.templates || []).forEach(function (template) {
            const slug = String(template.slug || template.id || '').trim();
            if (!slug) {
                return;
            }
            templatesBySlug.set(slug, {
                name: template.name || slug,
                description: template.description || '',
                isAvailable: true,
            });
        });
        (templates.researcher_templates || []).forEach(function (template) {
            const slug = String(template.slug || '').trim();
            if (!slug || templatesBySlug.has(slug)) {
                return;
            }
            templatesBySlug.set(slug, {
                name: template.name || slug,
                description: template.description || '',
                isAvailable: false,
            });
        });

        renderCollections();
        renderDocumentTypes();
        renderGraphModes();
    }

    function applyCurrentDocumentType(documentKind) {
        const normalized = String(documentKind || '').trim();
        if (!elements.documentType) {
            return;
        }
        const matchesKnownType = (mappingContract.document_types || []).some(function (definition) {
            return String(definition.document_type || '').trim() === normalized;
        });

        if (!normalized) {
            elements.documentType.selectedIndex = 0;
        } else if (matchesKnownType) {
            elements.documentType.value = normalized;
        } else {
            elements.documentType.value = 'custom';
            if (elements.documentTypeCustom) {
                elements.documentTypeCustom.value = normalized;
            }
        }
        updateDocumentTypeUi();
    }

    async function loadCurrentSetup() {
        if (elements.qualityMode) {
            elements.qualityMode.value = config.initialQualityMode || 'balanced';
        }

        if (!config.initialCollectionId) {
            updateDocumentTypeUi();
            updateGraphModeHint();
            return;
        }

        try {
            const profileResponse = await requestJson(
                config.projectApiBase + '/rag/organization-profile?quality_mode=' + encodeURIComponent(config.initialQualityMode || 'balanced')
            );

            const organizationProfile = profileResponse.organization_profile || {};
            if (elements.collection) {
                elements.collection.value = config.initialCollectionId;
            }
            if (elements.qualityMode) {
                elements.qualityMode.value = profileResponse.quality_mode || config.initialQualityMode || 'balanced';
            }

            currentGraphProfileId = String(
                organizationProfile.collection_graph_extraction_profile_id || organizationProfile.graph_extraction_profile_id || ''
            ).trim();
            currentGraphProfileLabel = String(
                (profileResponse.graph_reading_mode && profileResponse.graph_reading_mode.effective_graph_extraction_profile_label) || ''
            ).trim();
            renderGraphModes();
            if (elements.graphMode) {
                elements.graphMode.value = (profileResponse.graph_reading_mode && profileResponse.graph_reading_mode.mode) || 'library_default';
            }

            const metadataDefaults = organizationProfile.metadata_defaults || {};
            applyCurrentDocumentType(metadataDefaults.document_kind || '');
        } catch (error) {
            updateDocumentTypeUi();
            updateGraphModeHint();
            setStatus('warning', 'The project page opened, but the saved setup could not be loaded. You can still choose new setup options below.');
            return;
        }

        updateGraphModeHint();
    }

    async function saveSetup(event) {
        event.preventDefault();

        const collectionId = getTrimmedValue(elements.collection, '');
        const qualityMode = getTrimmedValue(elements.qualityMode, 'balanced');
        const documentTypeValue = getSelectedDocumentTypeValue();
        const graphProfileId = getSelectedGraphProfileId();
        const suggestedTemplateSlug = getSuggestedTemplateSlug();
        const suggestedTemplate = templatesBySlug.get(suggestedTemplateSlug) || null;

        if (!collectionId) {
            setStatus('warning', 'Choose a document library before saving.');
            return;
        }

        setSavingState(true);
        setStatus('info', 'Saving project setup...');

        try {
            await requestJson(config.projectApiBase, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    collection_id: collectionId,
                    rag_quality_mode: qualityMode,
                }),
            });

            const currentProfileResponse = await requestJson(
                config.projectApiBase + '/rag/organization-profile?quality_mode=' + encodeURIComponent(qualityMode)
            );
            const currentProfile = currentProfileResponse.organization_profile || {};
            const currentMetadataDefaults = currentProfile.metadata_defaults || {};
            const payload = {
                quality_mode: qualityMode,
                graph_extraction_profile_id: graphProfileId,
                organization_profile: {
                    chunking: currentProfile.chunking || {
                        strategy: 'semantic',
                        chunk_size_chars: 3200,
                        chunk_overlap_chars: 480,
                        enrich_context: true,
                    },
                    metadata_defaults: {
                        language: currentMetadataDefaults.language || '',
                        document_kind: documentTypeValue,
                        source_type: currentMetadataDefaults.source_type || '',
                    },
                },
                metadata_schema: normalizeMetadataSchema(currentProfile.metadata_schema),
            };

            if (suggestedTemplate && suggestedTemplate.isAvailable) {
                payload.chunk_template_id = suggestedTemplateSlug;
            }

            await requestJson(config.projectApiBase + '/rag/organization-profile', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            await requestJson(config.projectApiBase, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    collection_id: collectionId,
                    rag_quality_mode: qualityMode,
                    chunk_template_slug: suggestedTemplate && suggestedTemplate.isAvailable ? suggestedTemplateSlug : '',
                }),
            });

            if (suggestedTemplate && suggestedTemplate.isAvailable) {
                setStatus('success', 'Saved. Opening the project with the suggested reading setup.');
            } else {
                setStatus(
                    'success',
                    'Saved. Opening the project now. The library default reading setup will be used until the suggested setup is ready.'
                );
            }

            window.location.href = config.overviewUrl;
        } catch (error) {
            setStatus('danger', error.message || 'Unable to save the project setup.');
        } finally {
            setSavingState(false);
        }
    }

    async function initialize() {
        setStatus('info', 'Loading setup choices...');
        try {
            await loadContracts();
            await loadCurrentSetup();
            updateSuggestedSetup();
            updateGraphModeHint();
            setStatus('info', 'Choose the library and starting reading options for this project.');
        } catch (error) {
            setStatus('danger', error.message || 'Unable to load the project setup page.');
        }
    }

    if (elements.documentType) {
        elements.documentType.addEventListener('change', updateDocumentTypeUi);
    }
    if (elements.documentTypeCustom) {
        elements.documentTypeCustom.addEventListener('input', updateDocumentTypeUi);
    }
    if (elements.graphMode) {
        elements.graphMode.addEventListener('change', updateGraphModeHint);
    }
    if (elements.form) {
        elements.form.addEventListener('submit', saveSetup);
    }

    initialize();
})();
