/* Theme switcher (py-web skill). */
(function () {
    const html = document.documentElement;
    const btns = document.querySelectorAll('.theme-btn');

    function getPreferredTheme() {
        return localStorage.getItem('theme') || 'system';
    }

    function applyTheme(theme) {
        btns.forEach(b => {
            b.classList.remove('active');
            b.style.backgroundColor = '';
            b.style.color = '';
        });
        const active = document.querySelector(`.theme-btn[data-theme-value="${theme}"]`);
        if (active) {
            active.classList.add('active');
            active.style.backgroundColor = 'var(--bs-primary)';
            active.style.color = '#fff';
        }
        const resolved = theme === 'system'
            ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : theme;
        html.setAttribute('data-theme', resolved);
        html.setAttribute('data-bs-theme', resolved);
        if (theme === 'system') localStorage.removeItem('theme');
        else localStorage.setItem('theme', theme);
    }

    applyTheme(getPreferredTheme());
    btns.forEach(b => b.addEventListener('click', () => applyTheme(b.getAttribute('data-theme-value'))));
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (!localStorage.getItem('theme')) applyTheme('system');
    });
})();
