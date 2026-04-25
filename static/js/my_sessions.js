(function () {
    'use strict';

    document.querySelectorAll('.revoke-session-form').forEach((form) => {
        form.addEventListener('submit', (event) => {
            const message = form.dataset.confirmMessage || 'Revoke this session?';
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
})();
