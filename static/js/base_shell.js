(function () {
    function initThemeSwitcher() {
        var htmlElement = document.documentElement;
        var themeButtons = document.querySelectorAll('.theme-btn');
        if (!themeButtons.length) {
            return;
        }

        var mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

        function getSavedTheme() {
            return window.localStorage.getItem('theme') || 'system';
        }

        function resolveTheme(theme) {
            if (theme === 'system') {
                return mediaQuery.matches ? 'dark' : 'light';
            }
            return theme;
        }

        function applyTheme(theme) {
            var resolvedTheme = resolveTheme(theme);
            htmlElement.setAttribute('data-bs-theme', resolvedTheme);
            window.localStorage.setItem('theme', theme);
            Array.prototype.forEach.call(themeButtons, function (button) {
                button.classList.toggle('active', button.getAttribute('data-theme-value') === theme);
            });
        }

        applyTheme(getSavedTheme());

        Array.prototype.forEach.call(themeButtons, function (button) {
            button.addEventListener('click', function () {
                applyTheme(button.getAttribute('data-theme-value') || 'system');
            });
        });

        if (typeof mediaQuery.addEventListener === 'function') {
            mediaQuery.addEventListener('change', function () {
                if ((window.localStorage.getItem('theme') || 'system') === 'system') {
                    applyTheme('system');
                }
            });
        }
    }

    function initAiStatusIndicator() {
        var indicator = document.getElementById('ai-server-status');
        var statusText = document.getElementById('ai-status-text');
        if (!indicator || !statusText) {
            return;
        }

        function setStatus(payload) {
            indicator.classList.remove('connected', 'warning', 'error');

            if (payload.token_valid) {
                indicator.classList.add('connected');
                indicator.title = 'Connected';
                statusText.textContent = 'AI \u2713';
                return;
            }

            if (payload.server_reachable) {
                indicator.classList.add('warning');
                indicator.title = 'Not authenticated';
                statusText.textContent = 'AI \u26A0';
                return;
            }

            indicator.classList.add('error');
            indicator.title = 'Cannot reach AI Server';
            statusText.textContent = 'AI \u2715';
        }

        async function checkStatus() {
            try {
                var response = await window.fetch('/check-ai-server');
                setStatus(await response.json());
            } catch (error) {
                setStatus({ server_reachable: false, token_valid: false });
            }
        }

        checkStatus();
        window.setInterval(checkStatus, 30000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        initThemeSwitcher();
        initAiStatusIndicator();
    });
})();
