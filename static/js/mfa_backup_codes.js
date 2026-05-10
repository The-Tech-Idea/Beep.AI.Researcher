'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const configNode = document.getElementById('mfa-backup-codes-config');
    if (!configNode) {
        return;
    }

    let config;
    try {
        config = JSON.parse(configNode.textContent);
    } catch (e) {
        return;
    }
    const codesBox = document.getElementById('codesBox');
    const copyButton = document.getElementById('copyBackupCodesBtn');
    const printButton = document.getElementById('printBackupCodesBtn');
    const form = document.getElementById('mfaBackupCodesForm');
    const statusNode = document.getElementById('mfaBackupCodesStatus');

    const showStatus = (message) => {
        if (!statusNode) {
            return;
        }

        statusNode.textContent = message;
        statusNode.hidden = !message;
    };

    copyButton?.addEventListener('click', async () => {
        if (!codesBox) {
            return;
        }

        const text = Array.from(codesBox.querySelectorAll('div'))
            .map((node) => node.textContent.trim())
            .join('\n');

        if (!navigator.clipboard?.writeText) {
            showStatus(config.copyUnavailable);
            return;
        }

        try {
            await navigator.clipboard.writeText(text);
            showStatus(config.copySuccess);
        } catch (error) {
            showStatus(config.copyUnavailable);
        }
    });

    printButton?.addEventListener('click', () => {
        window.print();
    });

    form?.addEventListener('submit', (event) => {
        if (!window.confirm(config.confirmRegenerate)) {
            event.preventDefault();
        }
    });
});
