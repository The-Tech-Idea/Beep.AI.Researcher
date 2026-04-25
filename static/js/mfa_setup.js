'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('mfa-setup-config');
    const copyButton = document.getElementById('copyManualSecretBtn');
    const secretInput = document.getElementById('manualSecret');

    if (!configNode || !copyButton || !secretInput) {
        return;
    }

    const config = JSON.parse(configNode.textContent);
    const originalMarkup = copyButton.innerHTML;

    copyButton.addEventListener('click', async () => {
        if (!navigator.clipboard?.writeText) {
            return;
        }

        try {
            await navigator.clipboard.writeText(secretInput.value);
            copyButton.innerHTML = config.copySuccessIcon;
            window.setTimeout(() => {
                copyButton.innerHTML = originalMarkup;
            }, 1500);
        } catch (error) {
            copyButton.setAttribute('title', config.copyUnavailable);
        }
    });
});
