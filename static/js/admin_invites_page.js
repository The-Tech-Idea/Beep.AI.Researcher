'use strict';

document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', async (event) => {
        const copyButton = event.target.closest('[data-copy-text]');
        if (!copyButton) {
            return;
        }

        const text = copyButton.dataset.copyText;
        if (!text) {
            return;
        }

        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            window.prompt('Copy invite URL', text);
        }
    });

    document.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const confirmMessage = form.dataset.adminConfirm;
        if (confirmMessage && !window.confirm(confirmMessage)) {
            event.preventDefault();
        }
    }, true);
});
