/**
 * Package Availability UI Handler — dynamically disables feature buttons
 * when their required packages are not installed.
 *
 * Reads tooltip strings from window.BEEP_I18N (set by template context).
 * Falls back to English only if i18n keys are missing.
 */
(function () {
    'use strict';

    // Package status is injected by the template context processor
    var packages = window.BEEP_PACKAGES || {};

    // i18n keys injected by template
    var i18n = window.BEEP_I18N || {};

    /**
     * Get tooltip for a package, using i18n keys
     */
    function getTooltip(pkg) {
        var key = 'feature.disabled.' + pkg;
        return i18n[key] || i18n['feature.disabled.tooltip'] || 'Install required package from Admin > Optional Packages.';
    }

    /**
     * Apply disabled state to a button
     */
    function disableButton(btn) {
        btn.classList.add('btn--package-disabled');
        btn.setAttribute('aria-disabled', 'true');
        btn.removeAttribute('href');
        btn.setAttribute('role', 'button');
        btn.style.cursor = 'not-allowed';

        var pkg = btn.dataset.package;
        var tooltip = getTooltip(pkg);

        // Add tooltip
        var tooltipEl = document.createElement('span');
        tooltipEl.className = 'feature-tooltip__content';
        tooltipEl.textContent = tooltip;

        var wrapper = document.createElement('span');
        wrapper.className = 'feature-tooltip';
        wrapper.style.display = 'inline-flex';

        var parent = btn.parentNode;
        parent.replaceChild(wrapper, btn);
        wrapper.appendChild(btn);
        wrapper.appendChild(tooltipEl);
    }

    /**
     * Check package status on page load
     */
    function checkPackages() {
        // Handle buttons with data-package attribute
        document.querySelectorAll('[data-package]').forEach(function (btn) {
            var pkg = btn.dataset.package;
            if (!packages[pkg]) {
                disableButton(btn);
            }
        });

        // Handle sections with data-section-package attribute
        document.querySelectorAll('[data-section-package]').forEach(function (section) {
            var pkg = section.dataset.sectionPackage;
            if (!packages[pkg]) {
                section.classList.add('feature-section--disabled');
                section.setAttribute('data-disabled-reason', getTooltip(pkg));
            }
        });

        // Handle nav items with data-nav-package attribute
        document.querySelectorAll('[data-nav-package]').forEach(function (navItem) {
            var pkg = navItem.dataset.navPackage;
            navItem.classList.add('nav-item--package-required');
            if (packages[pkg]) {
                navItem.classList.add('package-available');
            } else {
                navItem.classList.add('package-unavailable');
                navItem.title = getTooltip(pkg);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkPackages);
    } else {
        checkPackages();
    }

    // Expose for manual re-check after package install
    window.BEEP_RECHECK_PACKAGES = checkPackages;
})();
