(function () {
    'use strict';

    const refreshButton = document.getElementById('btnRefreshAudit');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            window.location.reload();
        });
    }

    document.querySelectorAll('[data-bs-toggle="popover"]').forEach((element) => {
        bootstrap.Popover.getOrCreateInstance(element);
    });
})();
