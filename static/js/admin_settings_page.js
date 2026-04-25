(function () {
    'use strict';

    function loadConfig() {
        const node = document.getElementById('admin-settings-config');
        if (!node?.textContent) {
            return null;
        }

        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            console.error('Failed to parse admin settings config.', error);
            return null;
        }
    }

    function setHiddenState(id, visible) {
        const element = document.getElementById(id);
        if (element) {
            element.hidden = !visible;
        }
    }

    function setInlineResult(element, message, tone) {
        if (!element) {
            return;
        }

        element.textContent = message;
        element.className = 'small admin-settings-inline-result';
        if (tone === 'success') {
            element.classList.add('admin-settings-inline-result--success');
            return;
        }

        if (tone === 'error') {
            element.classList.add('admin-settings-inline-result--error');
        }
    }

    function renderBlockResult(container, message, tone) {
        if (!container) {
            return;
        }

        container.textContent = '';
        const result = document.createElement('div');
        result.className = 'admin-settings-request-result small';
        if (tone === 'success') {
            result.classList.add('admin-settings-request-result--success');
        } else if (tone === 'error') {
            result.classList.add('admin-settings-request-result--error');
        }

        result.textContent = message;
        container.appendChild(result);
    }

    function initializeTabPersistence() {
        const storedTab = sessionStorage.getItem('adminSettingsTab');
        if (storedTab) {
            const button = document.querySelector(`[data-bs-target="${storedTab}"]`);
            if (button) {
                bootstrap.Tab.getOrCreateInstance(button).show();
            }
        }

        document.querySelectorAll('#settingsTabs button[data-bs-toggle="tab"]').forEach((button) => {
            button.addEventListener('shown.bs.tab', (event) => {
                sessionStorage.setItem('adminSettingsTab', event.target.dataset.bsTarget);
            });
        });
    }

    function initializeVisibilityToggles() {
        const updateEmailFields = () => {
            const method = document.querySelector('input[name="mail_auth_method"]:checked')?.value || 'smtp';
            setHiddenState('smtpFields', method === 'smtp');
            setHiddenState('ms365Fields', method === 'oauth2_ms365');
            setHiddenState('googleFields', method === 'oauth2_google');
        };

        const updateStorageFields = () => {
            const backend = document.querySelector('input[name="storage_backend"]:checked')?.value || 'local';
            setHiddenState('stLocalFields', backend === 'local');
            setHiddenState('stSMBFields', backend === 'smb');
            setHiddenState('stS3Fields', backend === 's3');
            setHiddenState('stAzureFields', backend === 'azure_blob');
        };

        const updateSsoFields = () => {
            const provider = document.querySelector('input[name="sso_provider"]:checked')?.value || 'none';
            setHiddenState('ldapFields', provider === 'ldap');
            setHiddenState('oidcFields', provider === 'oidc');
            setHiddenState('samlFields', provider === 'saml2');
        };

        document.querySelectorAll('input[name="mail_auth_method"]').forEach((radio) => {
            radio.addEventListener('change', updateEmailFields);
        });
        document.querySelectorAll('input[name="storage_backend"]').forEach((radio) => {
            radio.addEventListener('change', updateStorageFields);
        });
        document.querySelectorAll('input[name="sso_provider"]').forEach((radio) => {
            radio.addEventListener('change', updateSsoFields);
        });

        updateEmailFields();
        updateStorageFields();
        updateSsoFields();
    }

    function initializeEmailTest(config) {
        const button = document.getElementById('testEmailBtn');
        const result = document.getElementById('testEmailResult');
        if (!button || !result || !config?.emailTestUrl) {
            return;
        }

        button.addEventListener('click', async () => {
            setInlineResult(result, config.emailSendingLabel, 'info');
            try {
                const response = await fetch(config.emailTestUrl, { method: 'POST' });
                const data = await response.json();
                const fallbackMessage = data.success ? config.emailSentLabel : config.emailFailedLabel;
                setInlineResult(result, data.message || fallbackMessage, data.success ? 'success' : 'error');
            } catch (error) {
                setInlineResult(result, config.requestFailedLabel, 'error');
            }
        });
    }

    function initializeStorageTest(config) {
        const button = document.getElementById('testStorageBtn');
        const result = document.getElementById('storageTestResult');
        if (!button || !result || !config?.storageTestUrl) {
            return;
        }

        button.addEventListener('click', async () => {
            renderBlockResult(result, config.storageTestingLabel, 'info');
            try {
                const response = await fetch(config.storageTestUrl, { method: 'POST' });
                const data = await response.json();
                const fallbackMessage = data.success ? config.storageConnectedLabel : config.storageFailedLabel;
                renderBlockResult(result, data.message || fallbackMessage, data.success ? 'success' : 'error');
            } catch (error) {
                renderBlockResult(result, config.requestFailedLabel, 'error');
            }
        });
    }

    function initializeServiceStatus(config) {
        const button = document.getElementById('refresh-service-status');
        const output = document.getElementById('service-status-output');
        if (!button || !output || !config?.connectionStatusUrl) {
            return;
        }

        button.addEventListener('click', async () => {
            output.textContent = config.serviceCheckingLabel;
            try {
                const response = await fetch(config.connectionStatusUrl);
                const data = await response.json();
                output.textContent = config.serviceStatusTemplate
                    .replace('{service}', data.server_reachable ? config.serviceReachableLabel : config.serviceUnreachableLabel)
                    .replace('{token}', data.token_valid ? config.tokenValidLabel : config.tokenInvalidLabel);
            } catch (error) {
                output.textContent = config.serviceCheckFailedLabel;
            }
        });
    }

    const config = loadConfig();
    initializeTabPersistence();
    initializeVisibilityToggles();
    initializeEmailTest(config);
    initializeStorageTest(config);
    initializeServiceStatus(config);
})();
