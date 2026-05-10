'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('mfa-setup-config');
    const copyButton = document.getElementById('copyManualSecretBtn');
    const secretInput = document.getElementById('manualSecret');

    if (!configNode || !copyButton || !secretInput) {
        return;
    }

    let config;
    try {
        config = JSON.parse(configNode.textContent);
    } catch (e) {
        return;
    }

    const originalText = copyButton.textContent.trim();

    copyButton.addEventListener('click', async () => {
        if (!navigator.clipboard?.writeText) {
            copyButton.setAttribute('title', config.copyUnavailable);
            return;
        }

        try {
            await navigator.clipboard.writeText(secretInput.value);
            copyButton.textContent = config.copySuccess;
            window.setTimeout(() => {
                copyButton.innerHTML = '<i class="bi bi-clipboard"></i> ' + originalText;
            }, 1500);
        } catch (error) {
            copyButton.setAttribute('title', config.copyUnavailable);
        }
    });
});
