(function () {
    document.addEventListener('DOMContentLoaded', function () {
        var banner = document.getElementById('extractionIntroBanner');
        var dismissButton = document.getElementById('dismissExtractionBanner');
        var storageKey = 'extraction_intro_dismissed';

        if (banner && !window.localStorage.getItem(storageKey)) {
            banner.hidden = false;
        }

        if (banner && dismissButton) {
            dismissButton.addEventListener('click', function () {
                banner.hidden = true;
                window.localStorage.setItem(storageKey, '1');
            });
        }

        Array.prototype.forEach.call(
            document.querySelectorAll('[data-bs-toggle="tooltip"]'),
            function (element) {
                if (window.bootstrap && window.bootstrap.Tooltip) {
                    new window.bootstrap.Tooltip(element);
                }
            }
        );
    });
})();
