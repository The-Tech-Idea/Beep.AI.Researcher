(function () {
    function showToast(message, variant) {
        if (!message) {
            return;
        }

        window.beepUI.notify(message, { variant: variant || 'info' });
    }

    function normalizeStatusLevel(level) {
        switch (String(level || '').trim()) {
            case 'success':
            case 'warning':
            case 'danger':
                return level;
            default:
                return 'secondary';
        }
    }

    function setStatusMessage(element, level, message) {
        if (!element) {
            return;
        }

        const normalizedLevel = normalizeStatusLevel(level);
        element.className = `project-settings__status project-settings__status--${normalizedLevel}`;
        element.textContent = message || '';
        element.hidden = !message;
    }

    function setValueIfPresent(element, value) {
        if (element) {
            element.value = value ?? '';
        }
    }

        function setCheckedIfPresent(element, checked) {
            if (element) {
                element.checked = Boolean(checked);
            }
        }

        function setTextIfPresent(element, value) {
            if (element) {
                element.textContent = value || '';
            }
        }

    function getTrimmedValue(element, fallback) {
        if (!element) {
            return fallback || '';
        }

        return (element.value || '').trim();
    }

    function getIntegerValue(element, fallback) {
        if (!element || element.value === '') {
            return fallback;
        }

        const parsed = Number.parseInt(element.value, 10);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    async function requestJson(url, options) {
        const response = await fetch(url, options);
        const payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok) {
            throw new Error(payload.error || payload.message || 'Request failed.');
        }

        return payload;
    }

    document.addEventListener('DOMContentLoaded', function () {
        const page = document.getElementById('projectSettingsPage');
        if (!page) {
            return;
        }

        const config = {
            projectId: page.dataset.projectId || '',
            projectApiBase: page.dataset.projectApiBase || '',
            initialCollectionId: (page.dataset.initialCollectionId || '').trim(),
            initialTemplateSlug: (page.dataset.initialTemplateSlug || '').trim(),
            initialQualityMode: (page.dataset.initialQualityMode || 'balanced').trim() || 'balanced',
            initialQualityModeSource: (page.dataset.initialQualityModeSource || 'project_default').trim() || 'project_default',
            savedMessage: page.dataset.savedMessage || 'Saved.',
            archiveConfirm: page.dataset.archiveConfirm || 'Archive this project?',
            deleteConfirm: page.dataset.deleteConfirm || 'Type DELETE to remove this project.',
            projectListUrl: '/projects',
        };

        const elements = {
            tempSlider: document.getElementById('aiTemperature'),
            tempValue: document.getElementById('tempValue'),
            settingsForm: document.getElementById('projectSettingsForm'),
            projectCategory: document.getElementById('projectCategory'),
            ragStatus: document.getElementById('ragProfileStatus'),
            ragLibraryStatus: document.getElementById('ragLibraryStatus'),
            ragSaveButton: document.getElementById('saveRagProfileBtn'),
            ragCollectionSelect: document.getElementById('ragCollectionSelect'),
            saveLibraryConnectionButton: document.getElementById('saveLibraryConnectionBtn'),
            disconnectLibraryButton: document.getElementById('disconnectLibraryBtn'),
            refreshLibraryListButton: document.getElementById('refreshLibraryListBtn'),
            ragQualityMode: document.getElementById('ragQualityMode'),
            ragChunkStrategy: document.getElementById('ragChunkStrategy'),
            ragEnrichContext: document.getElementById('ragEnrichContext'),
            ragChunkSize: document.getElementById('ragChunkSize'),
            ragChunkOverlap: document.getElementById('ragChunkOverlap'),
            ragMetadataLanguage: document.getElementById('ragMetadataLanguage'),
            ragDocumentTypeSelect: document.getElementById('ragDocumentTypeSelect'),
            ragMetadataDocumentKindCustom: document.getElementById('ragMetadataDocumentKindCustom'),
            ragDocumentTypeHint: document.getElementById('ragDocumentTypeHint'),
            ragMetadataSourceType: document.getElementById('ragMetadataSourceType'),
            graphReadingMode: document.getElementById('graphReadingMode'),
            graphReadingModeHint: document.getElementById('graphReadingModeHint'),
            ragFilterableFields: document.getElementById('ragFilterableFields'),
            recommendedTemplateHint: document.getElementById('recommendedTemplateHint'),
            useRecommendedTemplateBtn: document.getElementById('useRecommendedTemplateBtn'),
            chunkTemplateSelect: document.getElementById('chunkTemplateSelect'),
            chunkTemplateDescription: document.getElementById('chunkTemplateDescription'),
            chunkTemplateStatus: document.getElementById('chunkTemplateStatus'),
            applyChunkTemplateBtn: document.getElementById('applyChunkTemplateBtn'),
            refreshChunkTemplatesBtn: document.getElementById('refreshChunkTemplatesBtn'),
            removeChunkTemplateBtn: document.getElementById('removeChunkTemplateBtn'),
            currentSetupCollection: document.getElementById('currentSetupCollection'),
            currentSetupCollectionNote: document.getElementById('currentSetupCollectionNote'),
            currentSetupTemplate: document.getElementById('currentSetupTemplate'),
            currentSetupTemplateNote: document.getElementById('currentSetupTemplateNote'),
            currentSetupGraph: document.getElementById('currentSetupGraph'),
            currentSetupGraphNote: document.getElementById('currentSetupGraphNote'),
            currentSetupQuality: document.getElementById('currentSetupQuality'),
            currentSetupBehavior: document.getElementById('currentSetupBehavior'),
            currentSetupChipQuality: document.getElementById('currentSetupChipQuality'),
            currentSetupChipFileStyle: document.getElementById('currentSetupChipFileStyle'),
            currentSetupChipDocumentType: document.getElementById('currentSetupChipDocumentType'),
            currentSetupChipFilters: document.getElementById('currentSetupChipFilters'),
            exportButtons: document.querySelectorAll('[data-export-format]'),
            archiveProjectBtn: document.getElementById('archiveProjectBtn'),
            deleteProjectBtn: document.getElementById('deleteProjectBtn'),
        };

        const ragEditorElements = [
            elements.ragQualityMode,
            elements.ragChunkStrategy,
            elements.ragEnrichContext,
            elements.ragChunkSize,
            elements.ragChunkOverlap,
            elements.ragMetadataLanguage,
            elements.ragDocumentTypeSelect,
            elements.ragMetadataDocumentKindCustom,
            elements.ragMetadataSourceType,
            elements.graphReadingMode,
            elements.ragFilterableFields,
            elements.ragSaveButton,
        ].filter(Boolean);

        let collectionId = config.initialCollectionId;
        let cachedTemplateSlug = config.initialTemplateSlug;
        let availableCollections = [];
        let allTemplates = [];
        let currentTemplateSlug = config.initialTemplateSlug || '';
        let mappingContract = null;
        let recommendedTemplateSlug = '';
        let projectSuggestedTemplateSlug = '';
        let graphReadingContract = null;
        let availableGraphProfiles = [];
        let savedQualityMode = config.initialQualityMode;
        let savedQualityModeSource = config.initialQualityModeSource;
        let currentGraphReadingMode = 'library_default';
        let currentGraphProfileId = '';
        let currentDatabaseDefaultGraphProfileId = '';
        let currentGraphProfileLabel = '';
        let currentDatabaseDefaultGraphProfileLabel = '';
        let currentDatabaseDefaultChunkTemplateId = '';
        let currentDatabaseDefaultChunkTemplateName = '';
        let currentChunkingSource = 'quality_mode_default';
        let currentMetadataDefaultsSource = 'library_default';
        let currentMetadataSchemaSource = 'library_default';

        function setRagStatus(level, message) {
            setStatusMessage(elements.ragStatus, level, message);
        }

        function setLibraryStatus(level, message) {
            setStatusMessage(elements.ragLibraryStatus, level, message);
        }

        function setChunkTemplateStatus(level, message) {
            setStatusMessage(elements.chunkTemplateStatus, level, message);
        }

        function setRagEditorEnabled(enabled) {
            ragEditorElements.forEach(function (element) {
                element.disabled = !enabled;
            });
        }

        function syncTemperatureValue() {
            if (elements.tempSlider && elements.tempValue) {
                elements.tempValue.textContent = elements.tempSlider.value;
            }
        }

        function resetRagProfileEditor() {
            setValueIfPresent(elements.ragChunkStrategy, 'semantic');
            setCheckedIfPresent(elements.ragEnrichContext, false);
            setValueIfPresent(elements.ragChunkSize, 3200);
            setValueIfPresent(elements.ragChunkOverlap, 480);
            setValueIfPresent(elements.ragMetadataLanguage, '');
            setValueIfPresent(elements.ragMetadataSourceType, '');
            setValueIfPresent(elements.ragFilterableFields, '');
            currentGraphReadingMode = 'library_default';
            currentGraphProfileId = '';
            currentDatabaseDefaultGraphProfileId = '';
            currentGraphProfileLabel = '';
            currentDatabaseDefaultGraphProfileLabel = '';
            currentDatabaseDefaultChunkTemplateId = '';
            currentDatabaseDefaultChunkTemplateName = '';
            currentChunkingSource = 'quality_mode_default';
            currentMetadataDefaultsSource = 'library_default';
            currentMetadataSchemaSource = 'library_default';
            renderGraphReadingOptions();
            applyDocumentTypeValue('');
        }

        function getSelectedText(element, fallback) {
            if (!element || element.selectedIndex < 0) {
                return fallback || '';
            }

            const option = element.options[element.selectedIndex];
            return option && option.text ? option.text.trim() : (fallback || '');
        }

        function getOptionTextByValue(element, value, fallback) {
            if (!element) {
                return fallback || '';
            }

            const normalizedValue = String(value || '').trim();
            const option = Array.from(element.options || []).find(function (entry) {
                return String(entry.value || '').trim() === normalizedValue;
            });

            return option && option.text ? option.text.trim() : (fallback || '');
        }

        function normalizeCollections(collections) {
            return (collections || []).map(function (entry) {
                if (typeof entry === 'string') {
                    return { id: entry, name: entry };
                }

                if (!entry || typeof entry !== 'object') {
                    return null;
                }

                const id = entry.id || entry.collection_id || entry.name || entry.title;
                if (!id) {
                    return null;
                }

                return {
                    id: String(id),
                    name: String(entry.name || entry.title || entry.display_name || id),
                    documentCount: entry.document_count ?? entry.documents_count ?? null,
                };
            }).filter(Boolean);
        }

        function describeCollection(collection) {
            if (!collection) {
                return 'document library';
            }

            if (collection.documentCount === null || collection.documentCount === undefined) {
                return collection.name;
            }

            const fileLabel = collection.documentCount === 1 ? 'file' : 'files';
            return `${collection.name} (${collection.documentCount} ${fileLabel})`;
        }

        function getCurrentCollection() {
            return availableCollections.find(function (entry) {
                return entry.id === collectionId;
            }) || null;
        }

        function renderCollectionOptions() {
            const select = elements.ragCollectionSelect;
            if (!select) {
                return;
            }

            select.innerHTML = '';

            const placeholderOption = document.createElement('option');
            placeholderOption.value = '';
            placeholderOption.textContent = 'Choose a document library...';
            select.appendChild(placeholderOption);

            availableCollections.forEach(function (collection) {
                const option = document.createElement('option');
                option.value = collection.id;
                option.textContent = describeCollection(collection);
                option.selected = collection.id === collectionId;
                select.appendChild(option);
            });

            if (collectionId && !availableCollections.some(function (entry) { return entry.id === collectionId; })) {
                const currentOption = document.createElement('option');
                currentOption.value = collectionId;
                currentOption.textContent = `Current library (${collectionId})`;
                currentOption.selected = true;
                select.appendChild(currentOption);
            }
        }

        function updateLibraryActionState() {
            const selectedId = getTrimmedValue(elements.ragCollectionSelect, '');
            if (elements.saveLibraryConnectionButton) {
                elements.saveLibraryConnectionButton.disabled = !selectedId || selectedId === collectionId;
            }
            if (elements.disconnectLibraryButton) {
                elements.disconnectLibraryButton.disabled = !collectionId;
            }
        }

        function findDocumentTypeDefinition(documentType) {
            if (!mappingContract || !Array.isArray(mappingContract.document_types)) {
                return null;
            }

            return mappingContract.document_types.find(function (entry) {
                return entry.document_type === documentType;
            }) || null;
        }

        function renderDocumentTypeOptions() {
            const select = elements.ragDocumentTypeSelect;
            if (!select) {
                return;
            }

            const currentValue = getDocumentTypeValue();
            select.innerHTML = '';

            const placeholderOption = document.createElement('option');
            placeholderOption.value = '';
            placeholderOption.textContent = 'Choose the most common file type...';
            select.appendChild(placeholderOption);

            if (mappingContract && Array.isArray(mappingContract.document_types)) {
                mappingContract.document_types.forEach(function (definition) {
                    const option = document.createElement('option');
                    option.value = definition.document_type;
                    option.textContent = definition.label;
                    select.appendChild(option);
                });
            }

            const customOption = document.createElement('option');
            customOption.value = 'custom';
            customOption.textContent = 'Something else';
            select.appendChild(customOption);

            applyDocumentTypeValue(currentValue);
        }

        function applyDocumentTypeValue(value) {
            const select = elements.ragDocumentTypeSelect;
            const customInput = elements.ragMetadataDocumentKindCustom;

            if (!select || !customInput) {
                return;
            }

            const documentKind = (value || '').trim();
            const definition = findDocumentTypeDefinition(documentKind);

            if (!documentKind) {
                select.value = '';
                customInput.value = '';
                customInput.hidden = true;
                customInput.disabled = true;
                updateDocumentTypeGuidance();
                return;
            }

            if (definition) {
                select.value = definition.document_type;
                customInput.value = '';
                customInput.hidden = true;
                customInput.disabled = true;
                updateDocumentTypeGuidance();
                return;
            }

            select.value = 'custom';
            customInput.hidden = false;
            customInput.disabled = false;
            customInput.value = documentKind;
            updateDocumentTypeGuidance();
        }

        function getDocumentTypeValue() {
            const select = elements.ragDocumentTypeSelect;
            const customInput = elements.ragMetadataDocumentKindCustom;

            if (!select) {
                return '';
            }

            if (select.value === 'custom') {
                return getTrimmedValue(customInput, '');
            }

            return getTrimmedValue(select, '');
        }

        function updateDocumentTypeGuidance() {
            updateRecommendedTemplateGuidance();
        }

        function findGraphModeDefinition(mode) {
            if (!graphReadingContract || !Array.isArray(graphReadingContract.modes)) {
                return null;
            }

            return graphReadingContract.modes.find(function (entry) {
                return entry.mode === mode;
            }) || null;
        }

        function findAvailableGraphProfile(profileId) {
            const normalizedProfileId = String(profileId || '').trim();
            if (!normalizedProfileId) {
                return null;
            }

            return availableGraphProfiles.find(function (entry) {
                const optionProfileId = String(entry.profile_id || entry.id || '').trim();
                return optionProfileId === normalizedProfileId;
            }) || null;
        }

        function renderGraphReadingOptions() {
            const select = elements.graphReadingMode;
            if (!select) {
                return;
            }

            select.innerHTML = '';

            if (graphReadingContract && Array.isArray(graphReadingContract.modes)) {
                graphReadingContract.modes.forEach(function (definition) {
                    const option = document.createElement('option');
                    option.value = definition.mode;
                    option.textContent = definition.label;

                    const profileId = String(definition.graph_extraction_profile_id || '').trim();
                    if (profileId && !findAvailableGraphProfile(profileId)) {
                        option.disabled = true;
                        option.textContent = `${definition.label} (not ready)`;
                    }

                    select.appendChild(option);
                });
            }

            if (currentGraphReadingMode === 'custom') {
                const customOption = document.createElement('option');
                customOption.value = 'custom';
                customOption.textContent = 'Current saved setup';
                select.appendChild(customOption);
            }

            select.value = currentGraphReadingMode || 'library_default';
            updateGraphReadingGuidance();
        }

        function updateGraphReadingGuidance() {
            const select = elements.graphReadingMode;
            const hint = elements.graphReadingModeHint;
            if (!select || !hint) {
                return;
            }

            const selectedMode = getTrimmedValue(select, 'library_default');
            const definition = findGraphModeDefinition(selectedMode);

            if (selectedMode === 'custom') {
                const customProfile = findAvailableGraphProfile(currentGraphProfileId);
                hint.textContent = customProfile
                    ? `This project is using the saved file connection setup "${customProfile.name || customProfile.label || currentGraphProfileId}".`
                    : currentGraphProfileLabel
                        ? `This project is using the saved file connection setup "${currentGraphProfileLabel}".`
                    : 'This project is using a saved file connection setup.';
                return;
            }

            if (selectedMode === 'library_default') {
                if (currentDatabaseDefaultGraphProfileId) {
                    const defaultProfile = findAvailableGraphProfile(currentDatabaseDefaultGraphProfileId);
                    hint.textContent = defaultProfile
                        ? `Using the library default file connection setup: "${defaultProfile.name || defaultProfile.label || currentDatabaseDefaultGraphProfileId}".`
                        : currentDatabaseDefaultGraphProfileLabel
                            ? `Using the library default file connection setup: "${currentDatabaseDefaultGraphProfileLabel}".`
                        : 'This project will use the file connection setup already assigned to the document library.';
                } else {
                    hint.textContent = 'This project will use the file connection setup already assigned to the document library.';
                }
                return;
            }

            if (definition) {
                hint.textContent = definition.description;
                return;
            }

            hint.textContent = 'Choose how much help the assistant should use when connecting related files.';
        }

        function getSelectedGraphProfileId() {
            const selectedMode = getTrimmedValue(elements.graphReadingMode, 'library_default');
            if (!selectedMode || selectedMode === 'library_default') {
                return '';
            }

            if (selectedMode === 'custom') {
                return currentGraphProfileId;
            }

            const definition = findGraphModeDefinition(selectedMode);
            return definition ? String(definition.graph_extraction_profile_id || '').trim() : '';
        }

        function getCurrentTemplateSummary() {
            if (!collectionId) {
                return {
                    label: 'No document library selected',
                    note: 'Connect a document library to use a saved reading setup.',
                };
            }

            if (!currentTemplateSlug) {
                return {
                    label: currentDatabaseDefaultChunkTemplateName || 'Library default',
                    note: currentDatabaseDefaultChunkTemplateName
                        ? 'Using the saved default reading setup from the connected document library.'
                        : 'Using the library default reading setup.',
                };
            }

            const template = findTemplate(currentTemplateSlug);
            return {
                label: template ? template.name : currentTemplateSlug,
                note: 'This reading setup is saved on the connected document library for this project.',
            };
        }

        function getCurrentGraphSummary() {
            if (!collectionId) {
                return {
                    label: 'No document library selected',
                    note: 'Connect a document library to use saved file connections.',
                };
            }

            if (currentGraphReadingMode === 'custom') {
                const customProfile = findAvailableGraphProfile(currentGraphProfileId);
                return {
                    label: customProfile
                        ? (customProfile.name || customProfile.label || currentGraphProfileId)
                        : (currentGraphProfileLabel || 'Saved file connection setup'),
                    note: 'This file connection setup is saved on the connected document library for this project.',
                };
            }

            if (currentGraphReadingMode === 'library_default') {
                const defaultProfile = findAvailableGraphProfile(currentDatabaseDefaultGraphProfileId);
                return {
                    label: defaultProfile
                        ? (defaultProfile.name || defaultProfile.label || currentDatabaseDefaultGraphProfileId)
                        : (currentDatabaseDefaultGraphProfileLabel || 'Library default'),
                    note: 'Using the library default file connection setup.',
                };
            }

            const definition = findGraphModeDefinition(currentGraphReadingMode);
            return {
                label: definition ? definition.label : 'Project file connection setup',
                note: 'This file connection setup is saved on the connected document library for this project.',
            };
        }

        function getCurrentBehaviorSummary() {
            if (!collectionId) {
                return {
                    quality: 'Waiting for a document library',
                    note: 'Connect a document library to load the saved answer style and reading details.',
                    fileStyle: 'Not loaded yet',
                    documentType: 'Not set yet',
                    filters: 'Standard defaults',
                };
            }

            const qualityLabel = getOptionTextByValue(elements.ragQualityMode, savedQualityMode, 'Balanced help');
            const fileStyleLabel = getSelectedText(elements.ragChunkStrategy, 'Research articles and narrative writing');
            const enrichLabel = elements.ragEnrichContext && elements.ragEnrichContext.checked
                ? 'Nearby paragraphs are included to improve context.'
                : 'Only the most relevant passages are used for context.';
            const documentType = getDocumentTypeValue();
            const documentTypeDefinition = findDocumentTypeDefinition(documentType);
            const documentTypeLabel = documentTypeDefinition ? documentTypeDefinition.label : (documentType || 'Not set yet');
            const language = getTrimmedValue(elements.ragMetadataLanguage, '');
            const sourceType = getTrimmedValue(elements.ragMetadataSourceType, '');
            const details = [
                savedQualityModeSource === 'saved_project_choice'
                    ? 'Saved answer style is active for this project.'
                    : 'Standard answer style is active for this project.',
                describeChunkingSource(currentChunkingSource),
            ];

            details.push(enrichLabel);

            if (language) {
                details.push(`Main language: ${language}.`);
            }

            if (sourceType) {
                details.push(`Usual source: ${sourceType}.`);
            }

            details.push(describeMetadataDefaultsSource(currentMetadataDefaultsSource));
            details.push(describeMetadataSchemaSource(currentMetadataSchemaSource));

            return {
                quality: qualityLabel,
                note: details.join(' '),
                fileStyle: fileStyleLabel,
                documentType: documentTypeLabel,
                filters: describeFilterState(currentMetadataSchemaSource),
            };
        }

        function describeChunkingSource(source) {
            switch (String(source || '').trim()) {
                case 'collection_template_override':
                    return 'The saved file-reading setup comes from a saved reading setup assigned to this connected document library.';
                case 'collection_override':
                    return 'The saved file-reading settings were customized on this connected document library.';
                case 'database_template_default':
                    return 'The file-reading setup comes from the connected library default reading setup.';
                case 'database_profile_default':
                    return 'The file-reading setup comes from the connected library defaults.';
                default:
                    return 'The file-reading setup is using the standard defaults for this answer style.';
            }
        }

        function describeMetadataDefaultsSource(source) {
            switch (String(source || '').trim()) {
                case 'collection_override':
                    return 'Document type, language, and source details are saved on this connected document library.';
                default:
                    return 'Document type, language, and source details are still using the standard library defaults.';
            }
        }

        function describeMetadataSchemaSource(source) {
            switch (String(source || '').trim()) {
                case 'collection_override':
                    return 'Filter and narrowing fields are saved on this connected document library.';
                default:
                    return 'Filter and narrowing fields are still using the standard library defaults.';
            }
        }

        function describeFilterState(source) {
            return String(source || '').trim() === 'collection_override'
                ? 'Library-saved fields'
                : 'Standard defaults';
        }

        function updateCurrentLibrarySetupSummary() {
            const currentCollection = getCurrentCollection();
            const templateSummary = getCurrentTemplateSummary();
            const graphSummary = getCurrentGraphSummary();
            const behaviorSummary = getCurrentBehaviorSummary();

            setTextIfPresent(
                elements.currentSetupCollection,
                currentCollection ? describeCollection(currentCollection) : 'No document library selected'
            );
            setTextIfPresent(
                elements.currentSetupCollectionNote,
                currentCollection
                    ? 'This project is currently linked to the shared document library shown above.'
                    : 'Connect a document library to see the saved setup used by this project.'
            );
            setTextIfPresent(elements.currentSetupTemplate, templateSummary.label);
            setTextIfPresent(elements.currentSetupTemplateNote, templateSummary.note);
            setTextIfPresent(elements.currentSetupGraph, graphSummary.label);
            setTextIfPresent(elements.currentSetupGraphNote, graphSummary.note);
            setTextIfPresent(elements.currentSetupQuality, behaviorSummary.quality);
            setTextIfPresent(elements.currentSetupBehavior, behaviorSummary.note);
            setTextIfPresent(elements.currentSetupChipQuality, `Answer style: ${behaviorSummary.quality}`);
            setTextIfPresent(elements.currentSetupChipFileStyle, `File style: ${behaviorSummary.fileStyle}`);
            setTextIfPresent(elements.currentSetupChipDocumentType, `Document type: ${behaviorSummary.documentType}`);
            setTextIfPresent(elements.currentSetupChipFilters, `Filters: ${behaviorSummary.filters}`);
        }

        function findTemplate(templateSlug) {
            if (!templateSlug) {
                return null;
            }

            return allTemplates.find(function (template) {
                return (template.slug || template.id) === templateSlug;
            }) || null;
        }

        function updateRecommendedTemplateGuidance() {
            const definition = findDocumentTypeDefinition(getTrimmedValue(elements.ragDocumentTypeSelect, ''));
            const customDocumentType = getTrimmedValue(elements.ragMetadataDocumentKindCustom, '');
            const fallbackTemplateSlug = projectSuggestedTemplateSlug || (mappingContract && mappingContract.default_template_slug) || '';

            if (definition) {
                recommendedTemplateSlug = definition.template_slug || '';
                if (elements.ragDocumentTypeHint) {
                    elements.ragDocumentTypeHint.textContent = definition.description;
                }
            } else if (getTrimmedValue(elements.ragDocumentTypeSelect, '') === 'custom') {
                recommendedTemplateSlug = fallbackTemplateSlug;
                if (elements.ragDocumentTypeHint) {
                    elements.ragDocumentTypeHint.textContent = customDocumentType
                        ? `Using "${customDocumentType}" as the project's main file type. Keep the name short and easy for your team to understand.`
                        : 'Describe the main file type in plain language, such as policy memo, scanned report, or meeting notes.';
                }
            } else {
                recommendedTemplateSlug = fallbackTemplateSlug;
                if (elements.ragDocumentTypeHint) {
                    elements.ragDocumentTypeHint.textContent =
                        'Choose the file type that best matches most of the material in this project.';
                }
            }

            const template = findTemplate(recommendedTemplateSlug);
            const button = elements.useRecommendedTemplateBtn;
            const hint = elements.recommendedTemplateHint;

            if (!hint) {
                return;
            }

            if (!collectionId) {
                hint.textContent = 'Connect a document library first to see and apply the recommended reading setup.';
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            if (!recommendedTemplateSlug) {
                hint.textContent = 'No recommended reading setup is available yet.';
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            if (!template && allTemplates.length === 0) {
                hint.textContent = 'Loading available reading setups...';
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            if (!template) {
                hint.textContent = 'The recommended reading setup is not available for this project yet.';
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            if (template._source === 'researcher') {
                hint.textContent = `Recommended setup: "${template.name}". It must be added to the library before this project can use it.`;
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            if (currentTemplateSlug && currentTemplateSlug === recommendedTemplateSlug) {
                hint.textContent = `Recommended setup "${template.name}" is already applied to this project.`;
                if (button) {
                    button.disabled = true;
                }
                return;
            }

            hint.textContent = `Recommended setup: "${template.name}". Use it unless this project's files need a special reading setup.`;
            if (button) {
                button.disabled = false;
            }
        }

        function updateChunkTemplatePanelState() {
            const selectedTemplateSlug = getTrimmedValue(elements.chunkTemplateSelect, '');
            const selectedTemplate = findTemplate(selectedTemplateSlug);

            if (elements.applyChunkTemplateBtn) {
                elements.applyChunkTemplateBtn.disabled =
                    !selectedTemplateSlug ||
                    selectedTemplateSlug === currentTemplateSlug ||
                    Boolean(selectedTemplate && selectedTemplate._source === 'researcher');
            }

            if (elements.removeChunkTemplateBtn) {
                elements.removeChunkTemplateBtn.disabled = !currentTemplateSlug;
            }

            if (elements.chunkTemplateDescription) {
                elements.chunkTemplateDescription.textContent = selectedTemplate ? (selectedTemplate.description || '') : '';
            }

            updateRecommendedTemplateGuidance();
        }

        function resetChunkTemplatePanel() {
            allTemplates = [];
            currentTemplateSlug = '';
            projectSuggestedTemplateSlug = '';

            if (elements.chunkTemplateSelect) {
                elements.chunkTemplateSelect.innerHTML = '<option value="">Use library default reading setup</option>';
                elements.chunkTemplateSelect.disabled = true;
            }

            if (elements.refreshChunkTemplatesBtn) {
                elements.refreshChunkTemplatesBtn.disabled = true;
            }

            if (elements.chunkTemplateDescription) {
                elements.chunkTemplateDescription.textContent = '';
            }

            if (elements.chunkTemplateStatus) {
                elements.chunkTemplateStatus.hidden = true;
                elements.chunkTemplateStatus.textContent = '';
            }

            if (elements.applyChunkTemplateBtn) {
                elements.applyChunkTemplateBtn.disabled = true;
            }

            if (elements.removeChunkTemplateBtn) {
                elements.removeChunkTemplateBtn.disabled = true;
            }

            updateRecommendedTemplateGuidance();
        }

        async function loadTemplateMappingContract() {
            try {
                const data = await requestJson('/projects/rag/template-mapping-contract');
                mappingContract = data.contract || { document_types: [], default_template_slug: '' };
            } catch (error) {
                mappingContract = { document_types: [], default_template_slug: '' };
                console.error('Unable to load the reading setup recommendations.', error);
            }

            renderDocumentTypeOptions();
            updateRecommendedTemplateGuidance();
        }

        async function loadGraphReadingContract() {
            try {
                const data = await requestJson('/projects/rag/graph-reading-contract');
                graphReadingContract = data.contract || { default_mode: 'library_default', modes: [] };
                availableGraphProfiles = Array.isArray(data.available_profiles) ? data.available_profiles : [];
            } catch (error) {
                graphReadingContract = { default_mode: 'library_default', modes: [] };
                availableGraphProfiles = [];
                console.error('Unable to load the relationship options.', error);
            }

            renderGraphReadingOptions();
        }

        async function loadLibraryOptions() {
            const select = elements.ragCollectionSelect;
            if (!select) {
                return;
            }

            select.disabled = true;
            if (elements.refreshLibraryListButton) {
                elements.refreshLibraryListButton.disabled = true;
            }
            if (elements.saveLibraryConnectionButton) {
                elements.saveLibraryConnectionButton.disabled = true;
            }
            if (elements.disconnectLibraryButton) {
                elements.disconnectLibraryButton.disabled = true;
            }
            setLibraryStatus('secondary', 'Loading document libraries...');

            try {
                const data = await requestJson('/projects/rag/collections');
                availableCollections = normalizeCollections(data.collections);
                renderCollectionOptions();

                if (data.message && availableCollections.length === 0) {
                    setLibraryStatus('warning', data.message);
                } else if (collectionId) {
                    const currentCollection = getCurrentCollection();
                    setLibraryStatus(
                        'success',
                        currentCollection
                            ? `Connected to ${describeCollection(currentCollection)}.`
                            : `Connected to library ${collectionId}.`
                    );
                } else if (availableCollections.length === 0) {
                    setLibraryStatus('warning', 'No document libraries are available yet. Ask an administrator to create one first.');
                } else {
                    setLibraryStatus('secondary', 'Choose a document library for this project.');
                }
            } catch (error) {
                availableCollections = [];
                renderCollectionOptions();
                setLibraryStatus('danger', error.message || 'Unable to load document libraries.');
            } finally {
                select.disabled = false;
                if (elements.refreshLibraryListButton) {
                    elements.refreshLibraryListButton.disabled = false;
                }
                updateLibraryActionState();
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function saveLibraryConnection() {
            const nextCollectionId = getTrimmedValue(elements.ragCollectionSelect, '');
            if (!nextCollectionId) {
                setLibraryStatus('warning', 'Choose a document library before saving.');
                return;
            }

            if (nextCollectionId === collectionId) {
                setLibraryStatus('secondary', 'This project is already connected to that document library.');
                return;
            }

            if (elements.ragCollectionSelect) {
                elements.ragCollectionSelect.disabled = true;
            }
            if (elements.saveLibraryConnectionButton) {
                elements.saveLibraryConnectionButton.disabled = true;
            }
            if (elements.disconnectLibraryButton) {
                elements.disconnectLibraryButton.disabled = true;
            }
            setLibraryStatus('secondary', 'Saving document library connection...');

            try {
                const data = await requestJson(config.projectApiBase, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ collection_id: nextCollectionId }),
                });

                collectionId = getTrimmedValue({ value: data.collection_id || nextCollectionId }, '');
                renderCollectionOptions();
                updateLibraryActionState();

                const currentCollection = getCurrentCollection();
                setLibraryStatus(
                    'success',
                    currentCollection
                        ? `Saved. This project now uses ${describeCollection(currentCollection)}.`
                        : `Saved. This project now uses library ${collectionId}.`
                );

                setRagEditorEnabled(true);
                await loadRagProfile();
                await loadChunkTemplates();
            } catch (error) {
                setLibraryStatus('danger', error.message || 'Unable to save the document library connection.');
            } finally {
                if (elements.ragCollectionSelect) {
                    elements.ragCollectionSelect.disabled = false;
                }
                updateLibraryActionState();
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function disconnectLibraryConnection() {
            if (!collectionId) {
                return;
            }

            const confirmed = window.confirm(
                'Remove the current document library from this project? File-based answers will stay limited until another library is connected.'
            );
            if (!confirmed) {
                return;
            }

            if (elements.ragCollectionSelect) {
                elements.ragCollectionSelect.disabled = true;
            }
            if (elements.saveLibraryConnectionButton) {
                elements.saveLibraryConnectionButton.disabled = true;
            }
            if (elements.disconnectLibraryButton) {
                elements.disconnectLibraryButton.disabled = true;
            }
            setLibraryStatus('secondary', 'Removing document library connection...');

            try {
                const data = await requestJson(config.projectApiBase, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ collection_id: '' }),
                });

                collectionId = getTrimmedValue({ value: data.collection_id || '' }, '');
                cachedTemplateSlug = '';
                renderCollectionOptions();
                updateLibraryActionState();
                resetRagProfileEditor();
                resetChunkTemplatePanel();
                setRagEditorEnabled(false);
                setLibraryStatus('success', 'Document library removed from this project.');
                setRagStatus('warning', 'Choose a document library before changing reading settings.');
            } catch (error) {
                setLibraryStatus('danger', error.message || 'Unable to remove the document library connection.');
            } finally {
                if (elements.ragCollectionSelect) {
                    elements.ragCollectionSelect.disabled = false;
                }
                updateLibraryActionState();
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        function populateRagProfile(profile) {
            const chunking = profile.chunking || {};
            const metadataDefaults = profile.metadata_defaults || {};
            const metadataSchema = profile.metadata_schema || {};

            setValueIfPresent(elements.ragChunkStrategy, chunking.strategy || 'semantic');
            setCheckedIfPresent(elements.ragEnrichContext, chunking.enrich_context);
            setValueIfPresent(elements.ragChunkSize, chunking.chunk_size_chars || 3200);
            setValueIfPresent(elements.ragChunkOverlap, chunking.chunk_overlap_chars || 480);
            setValueIfPresent(elements.ragMetadataLanguage, metadataDefaults.language || '');
            setValueIfPresent(elements.ragMetadataSourceType, metadataDefaults.source_type || '');
            setValueIfPresent(elements.ragFilterableFields, (metadataSchema.filterable_fields || []).join(', '));
            currentChunkingSource = String(profile.chunking_source || 'quality_mode_default').trim() || 'quality_mode_default';
            currentMetadataDefaultsSource = String(profile.metadata_defaults_source || 'library_default').trim() || 'library_default';
            currentMetadataSchemaSource = String(profile.metadata_schema_source || 'library_default').trim() || 'library_default';
            applyDocumentTypeValue(metadataDefaults.document_kind || '');
        }

        function collectRagProfilePayload() {
            return {
                quality_mode: getTrimmedValue(elements.ragQualityMode, 'balanced'),
                graph_extraction_profile_id: getSelectedGraphProfileId(),
                organization_profile: {
                    chunking: {
                        strategy: getTrimmedValue(elements.ragChunkStrategy, 'semantic'),
                        chunk_size_chars: getIntegerValue(elements.ragChunkSize, 3200),
                        chunk_overlap_chars: getIntegerValue(elements.ragChunkOverlap, 480),
                        enrich_context: Boolean(elements.ragEnrichContext && elements.ragEnrichContext.checked),
                    },
                    metadata_defaults: {
                        language: getTrimmedValue(elements.ragMetadataLanguage, ''),
                        document_kind: getDocumentTypeValue(),
                        source_type: getTrimmedValue(elements.ragMetadataSourceType, ''),
                    },
                },
                metadata_schema: {
                    version: '2.0',
                    filterable_fields: getTrimmedValue(elements.ragFilterableFields, '')
                        .split(',')
                        .map(function (value) { return value.trim(); })
                        .filter(Boolean),
                },
            };
        }

        async function loadRagProfile() {
            if (!collectionId) {
                resetRagProfileEditor();
                setRagEditorEnabled(false);
                setRagStatus('warning', 'Choose a document library before changing reading settings.');
                return;
            }

            setRagEditorEnabled(false);
            setRagStatus('secondary', 'Loading document reading settings...');

            try {
                const qualityMode = String(savedQualityMode || config.initialQualityMode || 'balanced').trim() || 'balanced';
                const data = await requestJson(
                    `${config.projectApiBase}/rag/organization-profile?quality_mode=${encodeURIComponent(qualityMode)}`
                );

                populateRagProfile(data.organization_profile || {});
                currentGraphReadingMode = data.graph_reading_mode && data.graph_reading_mode.mode
                    ? data.graph_reading_mode.mode
                    : 'library_default';
                currentGraphProfileId = String(
                    (data.organization_profile && data.organization_profile.collection_graph_extraction_profile_id) || ''
                ).trim();
                currentDatabaseDefaultGraphProfileId = String(
                    (data.organization_profile && data.organization_profile.database_default_graph_extraction_profile_id) || ''
                ).trim();
                currentGraphProfileLabel = String(
                    (data.graph_reading_mode && data.graph_reading_mode.effective_graph_extraction_profile_label) || ''
                ).trim();
                currentDatabaseDefaultGraphProfileLabel = String(
                    (data.graph_reading_mode && data.graph_reading_mode.database_default_graph_extraction_profile_label) || ''
                ).trim();
                savedQualityMode = String(data.quality_mode || qualityMode || savedQualityMode).trim() || 'balanced';
                savedQualityModeSource = String(data.quality_mode_source || 'project_default').trim() || 'project_default';
                currentDatabaseDefaultChunkTemplateId = String(
                    (data.organization_profile && data.organization_profile.database_default_chunk_template_id) || ''
                ).trim();
                currentDatabaseDefaultChunkTemplateName = String(
                    (data.organization_profile && data.organization_profile.database_default_chunk_template_name) || ''
                ).trim();
                setValueIfPresent(elements.ragQualityMode, savedQualityMode);
                renderGraphReadingOptions();
                const selectedOption = elements.ragQualityMode
                    ? elements.ragQualityMode.options[elements.ragQualityMode.selectedIndex]
                    : null;
                const careLabel = selectedOption ? selectedOption.text : 'Balanced help';
                const currentCollection = getCurrentCollection();
                const collectionLabel = currentCollection ? describeCollection(currentCollection) : data.collection_id;
                setRagStatus('success', `Ready. This project is set to ${careLabel.toLowerCase()} for ${collectionLabel}.`);
            } catch (error) {
                setRagStatus('danger', error.message || 'Unable to load document reading settings.');
            } finally {
                setRagEditorEnabled(true);
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function saveRagProfile() {
            if (!collectionId) {
                setRagStatus('warning', 'Choose a document library before saving reading settings.');
                return;
            }

            setRagEditorEnabled(false);
            setRagStatus('secondary', 'Saving document reading settings...');

            try {
                const data = await requestJson(`${config.projectApiBase}/rag/organization-profile`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(collectRagProfilePayload()),
                });

                populateRagProfile(data.organization_profile || {});
                currentGraphReadingMode = data.graph_reading_mode && data.graph_reading_mode.mode
                    ? data.graph_reading_mode.mode
                    : getTrimmedValue(elements.graphReadingMode, 'library_default');
                currentGraphProfileId = String(
                    (data.organization_profile && data.organization_profile.collection_graph_extraction_profile_id) || ''
                ).trim();
                currentDatabaseDefaultGraphProfileId = String(
                    (data.organization_profile && data.organization_profile.database_default_graph_extraction_profile_id) || ''
                ).trim();
                currentGraphProfileLabel = String(
                    (data.graph_reading_mode && data.graph_reading_mode.effective_graph_extraction_profile_label) || ''
                ).trim();
                currentDatabaseDefaultGraphProfileLabel = String(
                    (data.graph_reading_mode && data.graph_reading_mode.database_default_graph_extraction_profile_label) || ''
                ).trim();
                savedQualityMode = String(data.quality_mode || getTrimmedValue(elements.ragQualityMode, 'balanced')).trim() || 'balanced';
                savedQualityModeSource = String(data.quality_mode_source || 'saved_project_choice').trim() || 'saved_project_choice';
                currentDatabaseDefaultChunkTemplateId = String(
                    (data.organization_profile && data.organization_profile.database_default_chunk_template_id) || ''
                ).trim();
                currentDatabaseDefaultChunkTemplateName = String(
                    (data.organization_profile && data.organization_profile.database_default_chunk_template_name) || ''
                ).trim();
                setValueIfPresent(elements.ragQualityMode, savedQualityMode);
                renderGraphReadingOptions();
                const currentCollection = getCurrentCollection();
                const collectionLabel = currentCollection ? describeCollection(currentCollection) : data.collection_id;
                setRagStatus('success', `Saved. The assistant will use the updated reading settings for ${collectionLabel}.`);
            } catch (error) {
                setRagStatus('danger', error.message || 'Unable to save document reading settings.');
            } finally {
                setRagEditorEnabled(true);
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function loadCurrentChunkTemplate() {
            try {
                const data = await requestJson(`${config.projectApiBase}/rag/chunk-template`);
                currentTemplateSlug = data.success && data.template
                    ? (data.template.slug || data.template.id || '')
                    : '';
                projectSuggestedTemplateSlug = data.suggested_slug || projectSuggestedTemplateSlug || '';
            } catch (error) {
                currentTemplateSlug = cachedTemplateSlug || '';
                console.error('Unable to load the current reading setup.', error);
            }

            if (elements.chunkTemplateSelect) {
                elements.chunkTemplateSelect.value = currentTemplateSlug || '';
            }

            updateChunkTemplatePanelState();
            updateCurrentLibrarySetupSummary();
        }

        function renderChunkTemplateOptions(serverTemplates, localOnly) {
            if (!elements.chunkTemplateSelect) {
                return;
            }

            elements.chunkTemplateSelect.innerHTML = '<option value="">Use library default reading setup</option>';

            if (serverTemplates.length > 0) {
                const availableGroup = document.createElement('optgroup');
                availableGroup.label = 'Available reading setups';
                serverTemplates.forEach(function (template) {
                    const option = document.createElement('option');
                    option.value = template.slug || template.id;
                    option.textContent = template.name + (template.is_default ? ' (default)' : '');
                    availableGroup.appendChild(option);
                });
                elements.chunkTemplateSelect.appendChild(availableGroup);
            }

            if (localOnly.length > 0) {
                const localGroup = document.createElement('optgroup');
                localGroup.label = 'Needs library setup first';
                localOnly.forEach(function (template) {
                    const option = document.createElement('option');
                    option.value = template.slug;
                    option.textContent = `${template.name} (needs setup first)`;
                    localGroup.appendChild(option);
                });
                elements.chunkTemplateSelect.appendChild(localGroup);
            }
        }

        async function loadChunkTemplates() {
            if (!collectionId) {
                resetChunkTemplatePanel();
                return;
            }

            if (elements.chunkTemplateSelect) {
                elements.chunkTemplateSelect.disabled = true;
            }
            if (elements.refreshChunkTemplatesBtn) {
                elements.refreshChunkTemplatesBtn.disabled = true;
            }
            if (elements.applyChunkTemplateBtn) {
                elements.applyChunkTemplateBtn.disabled = true;
            }
            if (elements.removeChunkTemplateBtn) {
                elements.removeChunkTemplateBtn.disabled = true;
            }

            try {
                const params = new URLSearchParams({ include_researcher: 'true' });
                const category = getTrimmedValue(elements.projectCategory, '');
                if (category) {
                    params.set('suggest_for', category);
                }

                const data = await requestJson(`/projects/rag/chunk-templates?${params.toString()}`);
                const serverTemplates = (data.templates || []).map(function (template) {
                    return Object.assign({}, template, { _source: 'server' });
                });
                const researcherTemplates = (data.researcher_templates || []).map(function (template) {
                    return Object.assign({}, template, { _source: 'researcher' });
                });
                const seenSlugs = new Set(serverTemplates.map(function (template) {
                    return template.slug || template.id;
                }));
                const localOnly = researcherTemplates.filter(function (template) {
                    return !seenSlugs.has(template.slug);
                });

                allTemplates = serverTemplates.concat(localOnly);
                projectSuggestedTemplateSlug = data.suggested_slug || projectSuggestedTemplateSlug || '';

                renderChunkTemplateOptions(serverTemplates, localOnly);

                if (elements.chunkTemplateSelect) {
                    elements.chunkTemplateSelect.disabled = false;
                }
                if (elements.refreshChunkTemplatesBtn) {
                    elements.refreshChunkTemplatesBtn.disabled = false;
                }

                await loadCurrentChunkTemplate();
            } catch (error) {
                setChunkTemplateStatus('danger', error.message || 'Unable to load reading setups.');
                if (elements.chunkTemplateSelect) {
                    elements.chunkTemplateSelect.disabled = false;
                }
                if (elements.refreshChunkTemplatesBtn) {
                    elements.refreshChunkTemplatesBtn.disabled = false;
                }
                updateRecommendedTemplateGuidance();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function persistProjectChunkTemplateSlug(templateSlug) {
            try {
                await requestJson(config.projectApiBase, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ chunk_template_slug: templateSlug || '' }),
                });
            } catch (error) {
                console.warn('Unable to persist the project chunk template slug.', error);
            }
        }

        async function applyChunkTemplate(templateSlug) {
            const selectedTemplateSlug = (templateSlug || getTrimmedValue(elements.chunkTemplateSelect, '')).trim();
            if (!selectedTemplateSlug || !collectionId) {
                return;
            }

            const template = findTemplate(selectedTemplateSlug);
            if (template && template._source === 'researcher') {
                setChunkTemplateStatus('warning', 'This reading setup still needs administrator setup before it can be used.');
                updateChunkTemplatePanelState();
                return;
            }

            if (elements.applyChunkTemplateBtn) {
                elements.applyChunkTemplateBtn.disabled = true;
            }
            if (elements.removeChunkTemplateBtn) {
                elements.removeChunkTemplateBtn.disabled = true;
            }
            setChunkTemplateStatus('secondary', 'Applying reading setup...');

            try {
                await requestJson(`${config.projectApiBase}/rag/chunk-template`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ template_id: selectedTemplateSlug }),
                });

                currentTemplateSlug = selectedTemplateSlug;
                cachedTemplateSlug = selectedTemplateSlug;
                if (elements.chunkTemplateSelect) {
                    elements.chunkTemplateSelect.value = selectedTemplateSlug;
                }
                await persistProjectChunkTemplateSlug(selectedTemplateSlug);
                await loadRagProfile();

                setChunkTemplateStatus(
                    'success',
                    `Reading setup "${template ? template.name : selectedTemplateSlug}" is now applied to this project.`
                );
            } catch (error) {
                setChunkTemplateStatus('danger', error.message || 'Unable to apply the reading setup.');
            } finally {
                updateChunkTemplatePanelState();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function removeChunkTemplate() {
            if (!currentTemplateSlug || !collectionId) {
                return;
            }

            const confirmed = window.confirm(
                'Remove the current reading setup? The document library will go back to its default reading behavior.'
            );
            if (!confirmed) {
                return;
            }

            if (elements.applyChunkTemplateBtn) {
                elements.applyChunkTemplateBtn.disabled = true;
            }
            if (elements.removeChunkTemplateBtn) {
                elements.removeChunkTemplateBtn.disabled = true;
            }
            setChunkTemplateStatus('secondary', 'Removing reading setup...');

            try {
                await requestJson(`${config.projectApiBase}/rag/chunk-template`, { method: 'DELETE' });
                currentTemplateSlug = '';
                cachedTemplateSlug = '';

                if (elements.chunkTemplateSelect) {
                    elements.chunkTemplateSelect.value = '';
                }

                await persistProjectChunkTemplateSlug('');
                await loadRagProfile();
                setChunkTemplateStatus('success', 'Reading setup removed. The document library will use its default behavior.');
            } catch (error) {
                setChunkTemplateStatus('danger', error.message || 'Unable to remove the reading setup.');
            } finally {
                updateChunkTemplatePanelState();
                updateCurrentLibrarySetupSummary();
            }
        }

        async function submitProjectSettings(event) {
            event.preventDefault();

            const payload = {
                name: getTrimmedValue(document.getElementById('projectName'), ''),
                description: document.getElementById('projectDescription')?.value || '',
                category: getTrimmedValue(elements.projectCategory, ''),
                status: getTrimmedValue(document.getElementById('projectStatus'), 'active'),
                tags: (document.getElementById('projectTags')?.value || '')
                    .split(',')
                    .map(function (value) { return value.trim(); })
                    .filter(Boolean),
                custom_instructions: document.getElementById('aiInstructions')?.value || '',
                citation_format: getTrimmedValue(document.getElementById('aiCitationFormat'), 'apa'),
                ai_language: getTrimmedValue(document.getElementById('aiLanguage'), 'en'),
                ai_temperature: Number.parseFloat(document.getElementById('aiTemperature')?.value || '0.7'),
            };

            try {
                await requestJson(config.projectApiBase, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                showToast(config.savedMessage, 'success');
            } catch (error) {
                console.error('Unable to save project settings.', error);
                showToast(error.message || 'Could not save project settings.', 'danger');
            }
        }

        async function archiveProject() {
            if (!window.confirm(config.archiveConfirm)) {
                return;
            }

            try {
                await requestJson(config.projectApiBase, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'archived' }),
                });
                window.location.href = config.projectListUrl;
            } catch (error) {
                console.error('Unable to archive project.', error);
                showToast(error.message || 'Could not archive the project.', 'danger');
            }
        }

        async function deleteProject() {
            const confirmText = window.prompt(config.deleteConfirm);
            if (confirmText !== 'DELETE') {
                return;
            }

            try {
                await requestJson(config.projectApiBase, { method: 'DELETE' });
                window.location.href = config.projectListUrl;
            } catch (error) {
                console.error('Unable to delete project.', error);
                showToast(error.message || 'Could not delete the project.', 'danger');
            }
        }

        if (elements.tempSlider) {
            elements.tempSlider.addEventListener('input', syncTemperatureValue);
        }

        if (elements.settingsForm) {
            elements.settingsForm.addEventListener('submit', submitProjectSettings);
        }

        if (elements.ragSaveButton) {
            elements.ragSaveButton.addEventListener('click', saveRagProfile);
        }

        if (elements.ragCollectionSelect) {
            elements.ragCollectionSelect.addEventListener('change', updateLibraryActionState);
        }

        if (elements.saveLibraryConnectionButton) {
            elements.saveLibraryConnectionButton.addEventListener('click', saveLibraryConnection);
        }

        if (elements.disconnectLibraryButton) {
            elements.disconnectLibraryButton.addEventListener('click', disconnectLibraryConnection);
        }

        if (elements.refreshLibraryListButton) {
            elements.refreshLibraryListButton.addEventListener('click', loadLibraryOptions);
        }

        if (elements.projectCategory) {
            elements.projectCategory.addEventListener('change', function () {
                if (collectionId) {
                    loadChunkTemplates();
                } else {
                    updateRecommendedTemplateGuidance();
                }
            });
        }

        if (elements.ragDocumentTypeSelect) {
            elements.ragDocumentTypeSelect.addEventListener('change', function () {
                if (elements.ragDocumentTypeSelect.value === 'custom') {
                    if (elements.ragMetadataDocumentKindCustom) {
                        elements.ragMetadataDocumentKindCustom.hidden = false;
                        elements.ragMetadataDocumentKindCustom.disabled = false;
                        elements.ragMetadataDocumentKindCustom.focus();
                    }
                } else if (elements.ragMetadataDocumentKindCustom) {
                    elements.ragMetadataDocumentKindCustom.hidden = true;
                    elements.ragMetadataDocumentKindCustom.disabled = true;
                    elements.ragMetadataDocumentKindCustom.value = '';
                }

                updateRecommendedTemplateGuidance();
            });
        }

        if (elements.ragMetadataDocumentKindCustom) {
            elements.ragMetadataDocumentKindCustom.addEventListener('input', updateRecommendedTemplateGuidance);
        }

        if (elements.graphReadingMode) {
            elements.graphReadingMode.addEventListener('change', updateGraphReadingGuidance);
        }

        if (elements.ragQualityMode) {
            elements.ragQualityMode.value = config.initialQualityMode;
            elements.ragQualityMode.addEventListener('change', function () {
                if (!collectionId) {
                    return;
                }
                setRagStatus('secondary', 'Save Reading Settings to apply the new answer style to this project.');
            });
        }

        if (elements.applyChunkTemplateBtn) {
            elements.applyChunkTemplateBtn.addEventListener('click', function () {
                applyChunkTemplate();
            });
        }

        if (elements.useRecommendedTemplateBtn) {
            elements.useRecommendedTemplateBtn.addEventListener('click', function () {
                if (!recommendedTemplateSlug) {
                    return;
                }
                applyChunkTemplate(recommendedTemplateSlug);
            });
        }

        if (elements.removeChunkTemplateBtn) {
            elements.removeChunkTemplateBtn.addEventListener('click', removeChunkTemplate);
        }

        if (elements.refreshChunkTemplatesBtn) {
            elements.refreshChunkTemplatesBtn.addEventListener('click', loadChunkTemplates);
        }

        if (elements.chunkTemplateSelect) {
            elements.chunkTemplateSelect.addEventListener('change', updateChunkTemplatePanelState);
        }

        elements.exportButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                const format = button.dataset.exportFormat || 'json';
                window.location.href = `/projects/${config.projectId}/export?format=${encodeURIComponent(format)}`;
            });
        });

        if (elements.archiveProjectBtn) {
            elements.archiveProjectBtn.addEventListener('click', archiveProject);
        }

        if (elements.deleteProjectBtn) {
            elements.deleteProjectBtn.addEventListener('click', deleteProject);
        }

        syncTemperatureValue();
        updateLibraryActionState();
        updateRecommendedTemplateGuidance();
        updateCurrentLibrarySetupSummary();

        (async function initialize() {
            await loadTemplateMappingContract();
            await loadGraphReadingContract();
            await loadLibraryOptions();

            if (collectionId) {
                setRagEditorEnabled(true);
                await loadRagProfile();
                await loadChunkTemplates();
            } else {
                setRagEditorEnabled(false);
                resetChunkTemplatePanel();
                setRagStatus('warning', 'Choose a document library before changing reading settings.');
            }
        })();
    });
})();
