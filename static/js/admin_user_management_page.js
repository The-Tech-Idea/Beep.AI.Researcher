'use strict';

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-admin-auto-submit-select]').forEach((select) => {
        select.addEventListener('change', () => {
            if (select.form) {
                select.form.submit();
            }
        });
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
