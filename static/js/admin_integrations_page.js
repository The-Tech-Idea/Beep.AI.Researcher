'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('admin-integrations-config');
    if (!configNode) {
        return;
    }

    const config = JSON.parse(configNode.textContent);

    const setTestResult = (serviceId, message, state) => {
        const resultNode = document.getElementById(`test-result-${serviceId}`);
        if (!resultNode) {
            return;
        }

        resultNode.textContent = message;
        resultNode.dataset.state = state;
    };

    const runIntegrationTest = async (button) => {
        const serviceId = button.dataset.serviceId;
        if (!serviceId) {
            return;
        }

        button.disabled = true;
        setTestResult(serviceId, config.testingLabel, 'loading');

        try {
            const response = await fetch(`${config.testPathRoot}/${serviceId}/test`, { method: 'POST' });
            const payload = await response.json();
            const prefix = payload.success ? config.successPrefix : config.errorPrefix;
            setTestResult(serviceId, `${prefix}${payload.message}`, payload.success ? 'success' : 'error');
        } catch (error) {
            setTestResult(serviceId, `${config.errorPrefix}${config.requestFailedPrefix}${error}`, 'error');
        } finally {
            button.disabled = false;
        }
    };

    const disableIntegration = async (button) => {
        const serviceId = button.dataset.serviceId;
        if (!serviceId || !window.confirm(config.disableConfirm)) {
            return;
        }

        button.disabled = true;

        try {
            await fetch(`${config.testPathRoot}/${serviceId}/disable`, { method: 'POST' });
            window.location.reload();
        } finally {
            button.disabled = false;
        }
    };

    document.addEventListener('click', (event) => {
        const testButton = event.target.closest('.admin-integrations-test-button');
        if (testButton) {
            void runIntegrationTest(testButton);
            return;
        }

        const disableButton = event.target.closest('.admin-integrations-disable-button');
        if (disableButton) {
            void disableIntegration(disableButton);
        }
    });
});
