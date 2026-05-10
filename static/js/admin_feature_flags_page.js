(function() {
    'use strict';

    const config = JSON.parse(document.getElementById('feature-flags-config')?.textContent || '{}');
    if (!config.toggleUrl) return;

    const toggleUrl = config.toggleUrl;
    const toggleAllUrl = config.toggleAllUrl;

    function showFlash(message, type) {
        const existing = document.querySelector('.admin-feature-flags-message');
        if (existing) existing.remove();

        const flash = document.createElement('div');
        flash.className = `admin-feature-flags-message admin-feature-flags-message--${type}`;
        flash.setAttribute('role', 'alert');
        flash.textContent = message;

        const header = document.querySelector('.page-header');
        if (header) {
            header.parentNode.insertBefore(flash, header.nextSibling);
        }
        setTimeout(() => flash.remove(), 4000);
    }

    async function toggleFeature(featureName, enabled) {
        try {
            const response = await fetch(toggleUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feature_name: featureName, enabled })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || config.errorToggle);
            return data;
        } catch (err) {
            throw err;
        }
    }

    async function toggleAll(enabled) {
        try {
            const response = await fetch(toggleAllUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || config.errorBulk);
            return data;
        } catch (err) {
            throw err;
        }
    }

    function updateFeatureUI(featureName, enabled) {
        const toggle = document.querySelector(`.feature-toggle[data-feature="${featureName}"]`);
        const card = document.querySelector(`.admin-feature-flag-card[data-feature="${featureName}"]`);
        const tableRow = document.querySelector(`.admin-feature-flags-table tr[data-feature="${featureName}"]`);

        if (toggle) {
            toggle.checked = enabled;
        }

        if (card) {
            if (enabled) {
                card.classList.add('admin-feature-flag-card--enabled');
            } else {
                card.classList.remove('admin-feature-flag-card--enabled');
            }
        }

        if (tableRow) {
            const statusCell = tableRow.querySelector('td:last-child');
            if (statusCell) {
                statusCell.innerHTML = enabled
                    ? `<span class="admin-feature-flag-status admin-feature-flag-status--enabled"><i class="bi bi-check-circle-fill"></i> ${config.enabledLabel}</span>`
                    : `<span class="admin-feature-flag-status admin-feature-flag-status--disabled"><i class="bi bi-x-circle-fill"></i> ${config.disabledLabel}</span>`;
            }
        }

        updateCategoryToggles();
        updateSummary();
    }

    function updateCategoryToggles() {
        document.querySelectorAll('.category-toggle').forEach(categoryToggle => {
            const category = categoryToggle.dataset.category;
            const toggles = document.querySelectorAll(`.feature-toggle`);
            const categoryFeatures = Array.from(toggles).filter(t => {
                const card = t.closest('.admin-feature-flag-card');
                return card && card.closest(`.admin-feature-flags-category-card`)?.querySelector('.card-header .badge')?.textContent.trim();
            });

            const cards = document.querySelectorAll(`.admin-feature-flag-card`);
            let allEnabled = true;
            let anyEnabled = false;

            cards.forEach(card => {
                const toggle = card.querySelector('.feature-toggle');
                if (toggle) {
                    if (toggle.checked) anyEnabled = true;
                    else allEnabled = false;
                }
            });

            categoryToggle.checked = allEnabled;
            categoryToggle.indeterminate = !allEnabled && anyEnabled;
        });
    }

    function updateSummary() {
        const total = document.querySelectorAll('.feature-toggle').length;
        const enabled = document.querySelectorAll('.feature-toggle:checked').length;
        const summary = document.querySelector('.admin-feature-flags-summary');
        if (summary) {
            summary.innerHTML = `<span class="badge bg-success">${enabled}</span> / ${total} ${config.enabledLabel}`;
        }
    }

    document.querySelectorAll('.feature-toggle').forEach(toggle => {
        toggle.addEventListener('change', async function() {
            const featureName = this.dataset.feature;
            const enabled = this.checked;

            this.disabled = true;

            try {
                await toggleFeature(featureName, enabled);
                updateFeatureUI(featureName, enabled);
                showFlash(`${config.successToggle}`, 'success');
            } catch (err) {
                this.checked = !enabled;
                showFlash(`${config.errorToggle}: ${err.message}`, 'error');
            } finally {
                this.disabled = false;
            }
        });
    });

    document.querySelectorAll('.category-toggle').forEach(categoryToggle => {
        categoryToggle.addEventListener('change', async function() {
            const enabled = this.checked;
            const cards = document.querySelectorAll('.admin-feature-flag-card');

            this.disabled = true;

            for (const card of cards) {
                const toggle = card.querySelector('.feature-toggle');
                if (toggle) {
                    const featureName = toggle.dataset.feature;
                    toggle.disabled = true;
                    try {
                        await toggleFeature(featureName, enabled);
                        updateFeatureUI(featureName, enabled);
                    } catch (err) {
                        toggle.disabled = false;
                    }
                }
            }

            this.disabled = false;
            showFlash(config.successBulk, 'success');
        });
    });

    const enableAllBtn = document.getElementById('btn-enable-all');
    if (enableAllBtn) {
        enableAllBtn.addEventListener('click', async function() {
            if (!confirm(config.confirmEnableAll)) return;

            this.disabled = true;
            try {
                await toggleAll(true);
                document.querySelectorAll('.feature-toggle').forEach(toggle => {
                    updateFeatureUI(toggle.dataset.feature, true);
                });
                showFlash(config.successBulk, 'success');
            } catch (err) {
                showFlash(`${config.errorBulk}: ${err.message}`, 'error');
            } finally {
                this.disabled = false;
            }
        });
    }

    const disableAllBtn = document.getElementById('btn-disable-all');
    if (disableAllBtn) {
        disableAllBtn.addEventListener('click', async function() {
            if (!confirm(config.confirmDisableAll)) return;

            this.disabled = true;
            try {
                await toggleAll(false);
                document.querySelectorAll('.feature-toggle').forEach(toggle => {
                    updateFeatureUI(toggle.dataset.feature, false);
                });
                showFlash(config.successBulk, 'success');
            } catch (err) {
                showFlash(`${config.errorBulk}: ${err.message}`, 'error');
            } finally {
                this.disabled = false;
            }
        });
    }

    const resetBtn = document.getElementById('btn-reset-defaults');
    if (resetBtn) {
        resetBtn.addEventListener('click', async function() {
            if (!confirm(config.confirmResetDefaults)) return;

            this.disabled = true;
            try {
                const response = await fetch(config.resetDefaultsUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || config.errorBulk);

                for (const [featureName, info] of Object.entries(data.features)) {
                    updateFeatureUI(featureName, info.enabled);
                }
                showFlash(config.successBulk, 'success');
            } catch (err) {
                showFlash(`${config.errorBulk}: ${err.message}`, 'error');
            } finally {
                this.disabled = false;
            }
        });
    }
})();
