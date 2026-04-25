(function () {
    'use strict';

    let config = {};
    const configNode = document.getElementById('profile-config');
    if (configNode?.textContent) {
        try {
            config = JSON.parse(configNode.textContent);
        } catch (error) {
            console.error('Failed to parse profile config.', error);
        }
    }

    document.querySelectorAll('.profile-confirm-form').forEach((form) => {
        form.addEventListener('submit', (event) => {
            const message = form.dataset.confirmMessage || config.disableMfaConfirm || 'Are you sure?';
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
})();
