(function () {
    'use strict';

    var banner = document.querySelector('[data-document-map-banner]');
    if (!banner) {
        return;
    }

    var storageKey = 'map_banner';
    if (window.localStorage.getItem(storageKey)) {
        banner.remove();
        return;
    }

    var dismissButton = banner.querySelector('[data-dismiss-map-banner]');
    if (!dismissButton) {
        return;
    }

    dismissButton.addEventListener('click', function () {
        window.localStorage.setItem(storageKey, '1');
        banner.remove();
    });
})();
